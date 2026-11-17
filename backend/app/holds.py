"""Holds: an approved containment decision keeps its lots on hold until an officer lifts it.

Nothing about a hold is written to the lots or shipments. "On hold" is worked out from the decisions and their
releases, so the append-only decision history stays the single record. Each affected organization sees the hold when
it signs in and is asked to acknowledge it; the ministry sees who has and who has not.

Nothing is sent by email or SMS. Recording past movements of a held lot stays allowed, because an investigation
needs exactly those records.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import current_user, log_entry, regulator, scope, utc
from app.database import get_db
from app.models import Batch, ContainmentDecision, HoldAcknowledgement, HoldRelease, Organization, Shipment, User
from app.schemas import HoldReleaseCreate, OrganizationOut, supply_rank

router = APIRouter(prefix="/api/holds", dependencies=[Depends(current_user)])
CACHE = "held_batches"


def held_batches(db: Session) -> set[int]:
    """Lots under an approved decision that has not been lifted. Worked out once per request."""
    # ponytail: reads every approved decision; keep a table of active holds once there are thousands of them
    if CACHE not in db.info:
        lifted = {id_ for (id_,) in db.query(HoldRelease.decision_id)}
        db.info[CACHE] = {batch for decision in db.query(ContainmentDecision).filter_by(decision="approved")
                          if decision.decision_id not in lifted for batch in decision.batch_ids}
    return db.info[CACHE]


def holds_changed(db: Session) -> None:
    db.info.pop(CACHE, None)


def affected(db: Session, decision: ContainmentDecision) -> set[int]:
    """The organizations that made a held lot, or sent or received a shipment of one."""
    ids = {id_ for (id_,) in db.query(Batch.organization_id).filter(Batch.batch_id.in_(decision.batch_ids))}
    for pair in db.query(Shipment.from_org_id, Shipment.to_org_id).filter(Shipment.batch_id.in_(decision.batch_ids)):
        ids.update(pair)
    return ids


def hold_document(db: Session, decision: ContainmentDecision, user: User) -> dict:
    """A company gets the held lots it can see and its own acknowledgement, not the list of who else is affected."""
    from app.trace import batch_document  # app.trace imports this module

    release = db.get(HoldRelease, decision.decision_id)
    acknowledged = {a.organization_id: a for a in db.query(HoldAcknowledgement).filter_by(decision_id=decision.decision_id)}
    visible = scope(db, user)
    site_ids = affected(db, decision) if user.role == "regulator" else {user.organization_id}
    sites = sorted(db.query(Organization).filter(Organization.organization_id.in_(site_ids)),
                   key=lambda org: (supply_rank(org.type), org.organization_id))
    lots = db.query(Batch).filter(Batch.batch_id.in_(decision.batch_ids)).order_by(Batch.batch_id)

    def site(org):
        seen = acknowledged.get(org.organization_id)
        return {**OrganizationOut.model_validate(org).model_dump(),
                "acknowledged_at": utc(seen.acknowledged_at).isoformat() if seen else None,
                "acknowledged_by": db.get(User, seen.user_id).name if seen else None}

    return {"decision_id": decision.decision_id, "scope": decision.scope, "officer": decision.officer,
            "reason": decision.reason, "decided_at": utc(decision.decided_at).isoformat(),
            "released": release and {"officer": release.officer, "reason": release.reason,
                                     "released_at": utc(release.released_at).isoformat()},
            "lots": [batch_document(db, batch) for batch in lots if visible is None or batch.batch_id in visible],
            "sites": [site(org) for org in sites]}


@router.get("")
def holds(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Holds in force first, then lifted ones, newest first. A company gets only the holds that affect it."""
    decisions = db.query(ContainmentDecision).filter_by(decision="approved").order_by(ContainmentDecision.decision_id.desc())
    documents = [hold_document(db, decision, user) for decision in decisions
                 if user.role == "regulator" or user.organization_id in affected(db, decision)]
    return sorted(documents, key=lambda hold: hold["released"] is not None)


@router.post("/{decision_id}/acknowledge")
def acknowledge(decision_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role == "regulator":
        raise HTTPException(403, "a hold is acknowledged by the organizations it affects")
    decision = db.get(ContainmentDecision, decision_id)
    if decision is None or decision.decision != "approved" or user.organization_id not in affected(db, decision):
        raise HTTPException(404, f"hold {decision_id} not found")
    if db.get(HoldRelease, decision_id):
        raise HTTPException(409, "this hold has been lifted, so there is nothing to acknowledge")
    if db.get(HoldAcknowledgement, (decision_id, user.organization_id)) is None:
        db.add(HoldAcknowledgement(decision_id=decision_id, organization_id=user.organization_id, user_id=user.user_id,
                                   acknowledged_at=datetime.now(timezone.utc)))
        try:
            db.commit()
        except IntegrityError:  # a colleague acknowledged at the same moment: that is the same outcome
            db.rollback()
    return hold_document(db, decision, user)


@router.post("/{decision_id}/release")
def release(decision_id: int, data: HoldReleaseCreate, user: User = Depends(regulator), db: Session = Depends(get_db)):
    decision = db.get(ContainmentDecision, decision_id)
    if decision is None:
        raise HTTPException(404, f"decision {decision_id} not found")
    if decision.decision != "approved":
        raise HTTPException(409, "that recommendation was rejected, so it holds nothing")
    if db.get(HoldRelease, decision_id):
        raise HTTPException(409, "this hold has already been lifted")
    row = HoldRelease(decision_id=decision_id, officer=user.name, reason=data.reason.strip(),
                      released_at=datetime.now(timezone.utc))
    db.add(row)
    log_entry(db, user, row)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "this hold has already been lifted") from error
    holds_changed(db)
    return hold_document(db, decision, user)
