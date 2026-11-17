"""Stored lot relationships and shipment locations; investigation leads are not proof of cause."""

from datetime import datetime, timezone
from typing import get_args

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.graph import build_batch_graph, creates_cycle
from app.models import (Analysis, Batch, BatchLot, BatchRelationship, ContainmentDecision, DecisionSource, LabResult,
                        Organization, Shipment, ShipmentManifest, SyntheticBatch)
from app.schemas import (DecisionCreate, OrganizationCreate, OrganizationOut, OrganizationType, RelationshipCreate,
                         ShipmentCreate)

router = APIRouter(prefix="/api")
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


@router.get("/organizations", response_model=list[OrganizationOut])
def organizations(db: Session = Depends(get_db)):
    return db.query(Organization).order_by(Organization.organization_id).all()


@router.post("/organizations", status_code=201, response_model=OrganizationOut)
def create_organization(data: OrganizationCreate, db: Session = Depends(get_db)):
    org = Organization(**data.model_dump())
    db.add(org)
    commit(db)
    db.refresh(org)
    return org


@router.get("/shipments")
def shipments(db: Session = Depends(get_db)):
    return [shipment_document(db, ship) for ship in db.query(Shipment).order_by(Shipment.shipment_id)]


@router.post("/shipments", status_code=201)
def create_shipment(data: ShipmentCreate, db: Session = Depends(get_db)):
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
    commit(db)
    return shipment_document(db, ship)


@router.get("/batch-relationships")
def relationships(db: Session = Depends(get_db)):
    return [{"id": r.id, "parent_batch_id": r.parent_batch_id, "child_batch_id": r.child_batch_id,
             "quantity_used": r.quantity_used} for r in db.query(BatchRelationship).order_by(BatchRelationship.id)]


@router.post("/batch-relationships", status_code=201)
def create_relationship(data: RelationshipCreate, db: Session = Depends(get_db)):
    require(db, Batch, data.parent_batch_id, "batch")
    require(db, Batch, data.child_batch_id, "batch")
    graph = build_batch_graph(db)
    if graph.has_edge(data.parent_batch_id, data.child_batch_id):
        raise HTTPException(409, "ingredient relationship already exists")
    if creates_cycle(graph, data.parent_batch_id, data.child_batch_id):
        raise HTTPException(400, "ingredient relationship would create a cycle")
    row = BatchRelationship(**data.model_dump())
    db.add(row)
    commit(db)
    return {"id": row.id, **data.model_dump()}


@router.get("/lots/resolve")
def resolve_lot(lot_code: str, organization_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(BatchLot).filter(BatchLot.lot_code == lot_code)
    if organization_id is not None:
        query = query.filter(BatchLot.organization_id == organization_id)
    lots = query.all()
    if not lots:
        raise HTTPException(404, "lot is not linked to a stored batch")
    if len(lots) != 1:
        raise HTTPException(409, "lot code belongs to multiple producers; choose its organization")
    return batch_document(db, require(db, Batch, lots[0].batch_id, "batch"))


@router.get("/trace/batches")
def trace_batches(db: Session = Depends(get_db)):
    return [batch_document(db, batch) for batch in db.query(Batch).order_by(Batch.batch_id)]


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


def trace_document(db: Session, batch_ids: list[int]) -> dict:
    selected = set(batch_ids)
    for id_ in selected:
        require(db, Batch, id_, "batch")
    graph = build_batch_graph(db)
    graph.add_nodes_from(selected)
    ancestors = {id_: nx.ancestors(graph, id_) for id_ in selected}
    upstream = set().union(*ancestors.values()) - selected
    downstream = set().union(*(nx.descendants(graph, id_) for id_ in selected)) - selected
    # Other products that used an upstream lot also need review, even at a different factory.
    related = set().union(*(nx.descendants(graph, id_) for id_ in upstream)) if upstream else set()
    related -= selected | upstream | downstream
    included = selected | upstream | downstream | related
    batches = [batch_document(db, b) for b in db.query(Batch).filter(Batch.batch_id.in_(included)).order_by(Batch.batch_id)]
    ranking = []
    for id_ in upstream:
        matched = sorted(id2 for id2 in selected if id_ in ancestors[id2])
        ranking.append({"batch_id": id_, "matched_batch_ids": matched, "flagged_product_count": len(matched),
                        "total_distance": sum(nx.shortest_path_length(graph, id_, id2) for id2 in matched)})
    ranking.sort(key=lambda r: (-r["flagged_product_count"], r["total_distance"], r["batch_id"]))
    shipment_rows = db.query(Shipment).filter(Shipment.batch_id.in_(included)).order_by(Shipment.shipment_id).all()
    shipments = [shipment_document(db, ship) for ship in shipment_rows]
    labs =db.query(LabResult).filter(LabResult.batch_id.in_(included)).order_by(LabResult.tested_at, LabResult.lab_result_id)
    decisions = db.query(ContainmentDecision).filter_by(selection=selection_key(selected)).order_by(ContainmentDecision.decision_id.desc())
    # Positives this selection does not reach: the prompt to widen the investigation.
    elsewhere = (db.query(LabResult).filter(LabResult.result == "positive", LabResult.batch_id.notin_(included))
                 .order_by(LabResult.tested_at.desc(), LabResult.lab_result_id).limit(10))
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
def investigate(batch_ids: list[int] = Query(min_length=1, max_length=20), db: Session = Depends(get_db)):
    return trace_document(db, batch_ids)


@router.get("/organizations/{organization_id}/lots")
def organization_lots(organization_id: int, limit: int = Query(20, ge=1, le=200), db: Session = Depends(get_db)):
    """Lots to investigate when the lead is a company rather than a lot, newest first: what it made, plus what it
    received or sent on without making something from it. Ingredients it used are left out, because tracing its
    products already reaches them. `total` shows when `limit` cut the list short."""
    org = require(db, Organization, organization_id, "organization")
    made = {id_ for (id_,) in db.query(Batch.batch_id).filter(Batch.organization_id == organization_id)}
    moved = {id_ for (id_,) in db.query(Shipment.batch_id).filter(
        or_(Shipment.from_org_id == organization_id, Shipment.to_org_id == organization_id))}
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
def decide(data: DecisionCreate, db: Session = Depends(get_db)):
    # The hold list is recomputed from stored records, never taken from the client.
    held = trace_document(db, data.batch_ids)["containment"]["options"][data.scope]
    if data.analysis_id:
        require(db, Analysis, data.analysis_id, "analysis")
    row = ContainmentDecision(selection=selection_key(data.batch_ids), scope=data.scope, decision=data.decision,
                              officer=data.officer.strip(), reason=data.reason.strip(),
                              decided_at=datetime.now(timezone.utc), **held)
    db.add(row)
    db.flush()
    if data.analysis_id:
        db.add(DecisionSource(decision_id=row.decision_id, analysis_id=data.analysis_id))
    commit(db)
    return decision_document(db, row)


@router.post("/demo/seed")
def demo_seed(db: Session = Depends(get_db)):
    from app.seed import seed_demo
    return seed_demo(db)
