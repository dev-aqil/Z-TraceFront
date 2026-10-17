"""Stored lot relationships and shipment locations; investigation leads are not proof of cause."""

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.graph import build_batch_graph
from app.models import Batch, BatchLot, BatchRelationship, LabResult, Organization, Shipment, ShipmentManifest, SyntheticBatch
from app.schemas import OrganizationCreate, OrganizationOut, RelationshipCreate, ShipmentCreate

router = APIRouter(prefix="/api")


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
    if data.parent_batch_id == data.child_batch_id or (
        data.child_batch_id in graph and data.parent_batch_id in graph
        and nx.has_path(graph, data.child_batch_id, data.parent_batch_id)
    ):
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
    labs = db.query(LabResult).filter(LabResult.batch_id.in_(included)).order_by(LabResult.tested_at, LabResult.lab_result_id)
    return {"selected_batch_ids": sorted(selected), "upstream": sorted(upstream), "downstream": sorted(downstream),
            "related": sorted(related), "batches": batches,
            "edges": [[a, b] for a, b in sorted(graph.edges) if a in included and b in included],
            "shipments": [shipment_document(db, ship) for ship in shipment_rows], "source_ranking": ranking,
            "lab_results": [{"lab_result_id": lab.lab_result_id, "batch_id": lab.batch_id, "tested_at": lab.tested_at,
                             "contaminant": lab.contaminant, "result": lab.result} for lab in labs],
            "interpretation": "Shared ingredients are investigation leads, not proven causes. Related stock needs review, not an automatic recall."}


@router.get("/trace")
def investigate(batch_ids: list[int] = Query(min_length=1, max_length=20), db: Session = Depends(get_db)):
    return trace_document(db, batch_ids)


@router.post("/demo/seed")
def demo_seed(db: Session = Depends(get_db)):
    from app.seed import seed_demo
    return seed_demo(db)
