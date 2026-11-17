"""Stored lot relationships and shipment locations; investigation leads are not proof of cause."""

from datetime import datetime, timezone
from typing import get_args

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import current_user, log_entry, party, regulator, scope
from app.database import get_db
from app.graph import build_batch_graph, creates_cycle
from app.models import (Analysis, Batch, BatchLot, BatchRelationship, ContainmentDecision, DecisionSource, LabResult,
                        Organization, Shipment, ShipmentManifest, SyntheticBatch, User)
from app.schemas import (DecisionCreate, OrganizationCreate, OrganizationOut, OrganizationType, RelationshipCreate,
                         ShipmentCreate)

# Every route needs a signed-in user. What a company user may see and write is decided per route with app.auth.scope.
router = APIRouter(prefix="/api", dependencies=[Depends(current_user)])
SUPPLY_ORDER = get_args(OrganizationType)


def commit(db: Session):
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "record conflicts with an existing ID, lot code or reference") from error


def require(db: Session, model, id_, label):
    record = db.get(model, id_)
    if record is None:
        raise HTTPException(404, f"{label} {id_} not found")
    return record


def batch_document(db: Session, batch: Batch) -> dict:
    lot = db.get(BatchLot, batch.batch_id)
    org = db.get(Organization, batch.organization_id)
    return {"batch_id": batch.batch_id, "lot_code": lot.lot_code if lot else None,
            "product_name": batch.product_name, "organization_id": batch.organization_id,
            "organization_name": org.name, "organization_type": org.type,
            "produced_at": batch.produced_at, "status": batch.status, "synthetic": db.get(SyntheticBatch, batch.batch_id) is not None}


def shipment_document(db: Session, ship: Shipment) -> dict:
    manifest = db.get(ShipmentManifest, ship.shipment_id)
    return {"shipment_id": ship.shipment_id, "shipment_code": manifest.shipment_code if manifest else str(ship.shipment_id),
            "batch_id": ship.batch_id, "from_org_id": ship.from_org_id, "to_org_id": ship.to_org_id,
            "from_name": require(db, Organization, ship.from_org_id, "organization").name,
            "to_name": require(db, Organization, ship.to_org_id, "organization").name,
            "quantity": ship.quantity, "quantity_unit": manifest.quantity_unit if manifest else None,
            "status": ship.status, "departed_at": ship.departed_at, "eta": ship.eta}


def visible_batches(db: Session, user: User):
    """Query of the batches a user may see."""
    visible = scope(db, user)
    return db.query(Batch) if visible is None else db.query(Batch).filter(Batch.batch_id.in_(visible))


def require_visible(db: Session, user: User, batch_id: int) -> None:
    """A batch outside a company's view answers exactly like one that does not exist."""
    visible = scope(db, user)
    if visible is not None and batch_id not in visible:
        raise HTTPException(404, f"batch {batch_id} not found")


@router.get("/organizations", response_model=list[OrganizationOut])
def organizations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(Organization).order_by(Organization.organization_id)
    visible = scope(db, user)
    if visible is not None:  # a company: itself, its trading partners and the makers of the lots it can see
        ids = {user.organization_id}
        ids.update(id_ for pair in db.query(Shipment.from_org_id, Shipment.to_org_id).filter(party(user.organization_id))
                   for id_ in pair)
        ids.update(id_ for (id_,) in db.query(Batch.organization_id).filter(Batch.batch_id.in_(visible)))
        query = query.filter(Organization.organization_id.in_(ids))
    return query.all()


@router.post("/organizations", status_code=201, response_model=OrganizationOut)
def create_organization(data: OrganizationCreate, user: User = Depends(regulator), db: Session = Depends(get_db)):
    org = Organization(**data.model_dump())
    db.add(org)
    log_entry(db, user, org)
    commit(db)
    db.refresh(org)
    return org


@router.get("/shipments")
def shipments(user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(Shipment).order_by(Shipment.shipment_id)
    if user.role != "regulator":
        query = query.filter(party(user.organization_id))
    return [shipment_document(db, ship) for ship in query]


@router.post("/shipments", status_code=201)
def create_shipment(data: ShipmentCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "regulator":
        require_visible(db, user, data.batch_id)
        if user.organization_id not in (data.from_org_id, data.to_org_id):
            raise HTTPException(403, "you can record only shipments your own organization sent or received")
    require(db, Batch, data.batch_id, "batch")
    require(db, Organization, data.from_org_id, "organization")
    require(db, Organization, data.to_org_id, "organization")
    if db.get(Shipment, data.shipment_id):
        raise HTTPException(409, "shipment ID already exists")
    values = data.model_dump(exclude={"shipment_code", "quantity_unit"})
    ship = Shipment(**values)
    db.add(ship)
    db.flush()
    db.add(ShipmentManifest(shipment_id=ship.shipment_id, from_org_id=ship.from_org_id,
                            shipment_code=data.shipment_code, quantity_unit=data.quantity_unit))
    log_entry(db, user, ship)
    commit(db)
    return shipment_document(db, ship)


@router.get("/batch-relationships")
def relationships(user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = db.query(BatchRelationship).order_by(BatchRelationship.id)
    if user.role != "regulator":  # what went into its own products; what others made from its lots is theirs to share
        query = (query.join(Batch, Batch.batch_id == BatchRelationship.child_batch_id)
                 .filter(Batch.organization_id == user.organization_id))
    return [{"id": r.id, "parent_batch_id": r.parent_batch_id, "child_batch_id": r.child_batch_id,
             "quantity_used": r.quantity_used} for r in query]


@router.post("/batch-relationships", status_code=201)
def create_relationship(data: RelationshipCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "regulator":
        product = db.get(Batch, data.child_batch_id)
        if product is None or product.organization_id != user.organization_id:
            raise HTTPException(403, "you can record ingredients only for lots your own organization made")
        require_visible(db, user, data.parent_batch_id)
    require(db, Batch, data.parent_batch_id, "batch")
    require(db, Batch, data.child_batch_id, "batch")
    graph = build_batch_graph(db)
    if graph.has_edge(data.parent_batch_id, data.child_batch_id):
        raise HTTPException(409, "ingredient relationship already exists")
    if creates_cycle(graph, data.parent_batch_id, data.child_batch_id):
        raise HTTPException(400, "ingredient relationship would create a cycle")
    row = BatchRelationship(**data.model_dump())
    db.add(row)
    db.flush()
    log_entry(db, user, row)
    commit(db)
    return {"id": row.id, **data.model_dump()}


@router.get("/lots/resolve")
def resolve_lot(lot_code: str, organization_id: int | None = None, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    query = db.query(BatchLot).filter(BatchLot.lot_code == lot_code)
    if organization_id is not None:
        query = query.filter(BatchLot.organization_id == organization_id)
    visible = scope(db, user)
    lots = [lot for lot in query if visible is None or lot.batch_id in visible]
    if not lots:
        raise HTTPException(404, "lot is not linked to a stored batch")
    if len(lots) != 1:
        raise HTTPException(409, "lot code belongs to multiple producers; choose its organization")
    return batch_document(db, require(db, Batch, lots[0].batch_id, "batch"))


@router.get("/trace/batches")
def trace_batches(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [batch_document(db, batch) for batch in visible_batches(db, user).order_by(Batch.batch_id)]


def selection_key(batch_ids) -> str:
    return ",".join(map(str, sorted(set(batch_ids))))


def containment(selected, downstream, included, shipment_rows, ranking, batches) -> dict:
    """Two bounded hold options. Extended is recommended only when one ingredient links several products under review."""
    def option(ids):
        return {"batch_ids": sorted(ids), "shipment_ids": [s.shipment_id for s in shipment_rows if s.batch_id in ids]}
    codes = {b["batch_id"]: b["lot_code"] or f"Batch {b['batch_id']}" for b in batches}
    shared = ranking[0] if ranking and ranking[0]["flagged_product_count"] > 1 else None
    basis = (f"{codes[shared['batch_id']]} is an ingredient of {shared['flagged_product_count']} of the {len(selected)} "
             "products under investigation, so other stock made from it may also be affected." if shared else
             "No ingredient is shared by more than one product under investigation, so hold only those lots and "
             "anything made from them.")
    return {"recommended": "extended" if shared else "targeted", "basis": basis,
            "options": {"targeted": option(selected | downstream), "extended": option(included)},
            "note": "Simulated action: an approval is recorded, but no hold is sent to any site."}


def decision_document(db: Session, d: ContainmentDecision) -> dict:
    at = d.decided_at if d.decided_at.tzinfo else d.decided_at.replace(tzinfo=timezone.utc)  # SQLite drops the zone
    source = db.get(DecisionSource, d.decision_id)
    return {"decision_id": d.decision_id, "scope": d.scope, "decision": d.decision, "batch_ids": d.batch_ids,
            "shipment_ids": d.shipment_ids, "officer": d.officer, "reason": d.reason, "decided_at": at.isoformat(),
            "analysis_id": source.analysis_id if source else None}


def lab_document(lab: LabResult) -> dict:
    return {"lab_result_id": lab.lab_result_id, "batch_id": lab.batch_id, "tested_at": lab.tested_at,
            "contaminant": lab.contaminant, "result": lab.result}


def organization_summary(db: Session, graph: nx.DiGraph, batches: list[dict], shipments: list[dict]) -> list[dict]:
    """Who made or handled the traced lots, suppliers first, with quantities per lot and unit.

    `remaining` is received minus sent on: stock that may still be on site, was used in production (`used_in`) or was
    sold. It is None where the lot was made, because production quantity is not recorded.
    """
    made = {b["batch_id"]: b["organization_id"] for b in batches}
    holdings: dict[tuple, dict] = {}

    def holding(org, ship):
        return holdings.setdefault((org, ship["batch_id"], ship["quantity_unit"]), {"received": 0, "incoming": 0, "sent": 0})

    for ship in shipments:
        # ponytail: a held shipment counts as neither sent nor arrived; record where it was stopped to place it
        holding(ship["to_org_id"], ship)["received" if ship["status"] == "delivered" else "incoming"] += ship["quantity"]
        holding(ship["from_org_id"], ship)["sent"] += ship["quantity"] if ship["status"] in ("in_transit", "delivered") else 0
    orgs = db.query(Organization).filter(
        Organization.organization_id.in_(set(made.values()) | {org for org, _, _ in holdings})).all()
    orgs.sort(key=lambda o: (SUPPLY_ORDER.index(o.type) if o.type in SUPPLY_ORDER else len(SUPPLY_ORDER), o.organization_id))
    return [{"organization_id": o.organization_id, "name": o.name, "type": o.type,
             "produced_batch_ids": sorted(batch for batch, org in made.items() if org == o.organization_id),
             "holdings": [{"batch_id": batch, "unit": unit, **quantities,
                           "remaining": None if made[batch] == o.organization_id else quantities["received"] - quantities["sent"],
                           "used_in": sorted(c for c in graph.successors(batch) if made.get(c) == o.organization_id)}
                          for (org, batch, unit), quantities in sorted(holdings.items(), key=lambda kv: (kv[0][1], kv[0][2] or ""))
                          if org == o.organization_id]}
            for o in orgs]


def trace_document(db: Session, batch_ids: list[int], user: User) -> dict:
    """The investigation around the selected lots. A regulator gets the whole chain. A company gets the part it is a
    party to: the lots it made, used or moved, its own shipments, and lab results on the lots it made."""
    selected = set(batch_ids)
    visible = scope(db, user)  # None: everything
    for id_ in selected:
        if visible is not None and id_ not in visible:
            raise HTTPException(404, f"batch {id_} not found")  # the same answer as for a lot that does not exist
        require(db, Batch, id_, "batch")
    graph = build_batch_graph(db)
    graph.add_nodes_from(selected)
    ancestors = {id_: nx.ancestors(graph, id_) for id_ in selected}
    upstream = set().union(*ancestors.values()) - selected
    downstream = set().union(*(nx.descendants(graph, id_) for id_ in selected)) - selected
    # Other products that used an upstream lot also need review, even at a different factory.
    related = set().union(*(nx.descendants(graph, id_) for id_ in upstream)) if upstream else set()
    related -= selected | upstream | downstream
    if visible is not None:
        upstream, downstream, related = upstream & visible, downstream & visible, related & visible
    included = selected | upstream | downstream | related
    batches = [batch_document(db, b) for b in db.query(Batch).filter(Batch.batch_id.in_(included)).order_by(Batch.batch_id)]
    ranking = []
    for id_ in upstream:
        matched = sorted(id2 for id2 in selected if id_ in ancestors[id2])
        ranking.append({"batch_id": id_, "matched_batch_ids": matched, "flagged_product_count": len(matched),
                        "total_distance": sum(nx.shortest_path_length(graph, id_, id2) for id2 in matched)})
    ranking.sort(key=lambda r: (-r["flagged_product_count"], r["total_distance"], r["batch_id"]))
    shipment_query = db.query(Shipment).filter(Shipment.batch_id.in_(included))
    labs = db.query(LabResult).filter(LabResult.batch_id.in_(included))
    decisions = db.query(ContainmentDecision).filter_by(selection=selection_key(selected)).order_by(ContainmentDecision.decision_id.desc())
    # Positives this selection does not reach: the prompt to widen the investigation.
    elsewhere = (db.query(LabResult).filter(LabResult.result == "positive", LabResult.batch_id.notin_(included))
                 .order_by(LabResult.tested_at.desc(), LabResult.lab_result_id).limit(10))
    if visible is not None:
        shipment_query = shipment_query.filter(party(user.organization_id))
        labs = labs.join(Batch, Batch.batch_id == LabResult.batch_id).filter(Batch.organization_id == user.organization_id)
        decisions, elsewhere = [], []  # the ministry's records, and other companies' results
    shipment_rows = shipment_query.order_by(Shipment.shipment_id).all()
    shipments = [shipment_document(db, ship) for ship in shipment_rows]
    labs = labs.order_by(LabResult.tested_at, LabResult.lab_result_id)
    return {"selected_batch_ids": sorted(selected), "upstream": sorted(upstream), "downstream": sorted(downstream),
            "related": sorted(related), "batches": batches,
            "edges": [[a, b] for a, b in sorted(graph.edges) if a in included and b in included],
            "shipments": shipments, "organizations": organization_summary(db, graph, batches, shipments),
            "source_ranking": ranking,
            "lab_results": [lab_document(lab) for lab in labs],
            "positive_elsewhere": [{**lab_document(lab), "batch": batch_document(db, db.get(Batch, lab.batch_id))}
                                   for lab in elsewhere],
            "containment": containment(selected, downstream, included, shipment_rows, ranking, batches),
            "decisions": [decision_document(db, d) for d in decisions],
            "interpretation": "Shared ingredients are investigation leads, not proven causes. Related stock needs review, not an automatic recall."}


@router.get("/trace")
def investigate(batch_ids: list[int] = Query(min_length=1, max_length=20), user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    return trace_document(db, batch_ids, user)


@router.get("/organizations/{organization_id}/lots")
def organization_lots(organization_id: int, limit: int = Query(20, ge=1, le=200), user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    """Lots to investigate when the lead is a company rather than a lot, newest first: what it made, plus what it
    received or sent on without making something from it. Ingredients it used are left out, because tracing its
    products already reaches them. `total` shows when `limit` cut the list short. A company can ask only about itself."""
    if user.role != "regulator" and organization_id != user.organization_id:
        raise HTTPException(404, f"organization {organization_id} not found")
    org = require(db, Organization, organization_id, "organization")
    made = {id_ for (id_,) in db.query(Batch.batch_id).filter(Batch.organization_id == organization_id)}
    moved = {id_ for (id_,) in db.query(Shipment.batch_id).filter(party(organization_id))}
    graph = build_batch_graph(db)
    handled = {id_ for id_ in moved - made if not (id_ in graph and made.intersection(graph.successors(id_)))}
    # ponytail: the IN list grows with the lots a site has handled; join on shipments once a site passes ~30k lots
    rows = (db.query(Batch).filter(Batch.batch_id.in_(made | handled))
            .order_by(Batch.produced_at.desc(), Batch.batch_id.desc()).limit(limit))
    return {"organization": {"organization_id": org.organization_id, "name": org.name, "type": org.type},
            "lots": [{**batch_document(db, batch), "relation": "produced" if batch.batch_id in made else "handled"}
                     for batch in rows],
            "total": len(made | handled)}


@router.post("/decisions", status_code=201)
def decide(data: DecisionCreate, user: User = Depends(regulator), db: Session = Depends(get_db)):
    # The hold list is recomputed from stored records and the officer is the signed-in user: neither comes from the client.
    held = trace_document(db, data.batch_ids, user)["containment"]["options"][data.scope]
    if data.analysis_id:
        require(db, Analysis, data.analysis_id, "analysis")
    row = ContainmentDecision(selection=selection_key(data.batch_ids), scope=data.scope, decision=data.decision,
                              officer=user.name, reason=data.reason.strip(),
                              decided_at=datetime.now(timezone.utc), **held)
    db.add(row)
    db.flush()
    log_entry(db, user, row)
    if data.analysis_id:
        db.add(DecisionSource(decision_id=row.decision_id, analysis_id=data.analysis_id))
    commit(db)
    return decision_document(db, row)


@router.post("/demo/seed", dependencies=[Depends(regulator)])
def demo_seed(db: Session = Depends(get_db)):
    from app.seed import seed_demo
    return seed_demo(db)
