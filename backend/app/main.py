import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.analysis import router as analysis_router
from app.auth import current_user, log_entry, router as auth_router
from app.database import Base, engine, get_db
from app.models import Batch, BatchLot, LabResult, Organization, SensorReading, Shipment, User
from app.records import router as records_router
from app.risk import rule_based_risk_score
from app.schemas import (
    BatchCreate,
    BatchOut,
    LabResultCreate,
    LabResultOut,
    SensorReadingCreate,
    SensorReadingOut,
)
from app.trace import batch_document, commit, require, router as trace_router, trace_document, visible_batches

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tracefront API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("TRACEFRONT_CORS", "http://localhost:3000").split(","),
    allow_credentials=True,  # the session cookie; origins are an explicit list, never "*"
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(analysis_router)
app.include_router(records_router)
app.include_router(trace_router)


# The only route besides sign-in that needs no session: deploy scripts and the preflight check call it.
@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "analysis_storage": "database"}


@app.get("/api/batches", response_model=list[BatchOut])
def list_batches(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [batch_document(db, batch) for batch in visible_batches(db, user).order_by(Batch.batch_id)]


@app.post("/api/batches", response_model=BatchOut, status_code=201)
def create_batch(batch: BatchCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "regulator" and batch.organization_id != user.organization_id:
        raise HTTPException(403, "you can add lots only for your own organization here; declare a supplier's lot "
                                 "through a record import, together with its delivery to you")
    require(db, Organization, batch.organization_id, "organization")
    if db.get(Batch, batch.batch_id):
        raise HTTPException(409, "batch ID already exists")
    if batch.lot_code and db.query(BatchLot).filter_by(organization_id=batch.organization_id, lot_code=batch.lot_code).first():
        raise HTTPException(409, "lot code already exists for this producer")
    db_batch = Batch(**batch.model_dump(exclude={"lot_code"}))
    db.add(db_batch)
    db.flush()
    if batch.lot_code:
        db.add(BatchLot(batch_id=batch.batch_id, organization_id=batch.organization_id, lot_code=batch.lot_code))
    log_entry(db, user, db_batch)
    commit(db)
    return batch_document(db, db_batch)


@app.post("/api/sensor-readings", response_model=SensorReadingOut)
def ingest_sensor_reading(reading: SensorReadingCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ship = db.get(Shipment, reading.shipment_id)
    if ship is None or (user.role != "regulator" and user.organization_id not in (ship.from_org_id, ship.to_org_id)):
        raise HTTPException(404, f"shipment {reading.shipment_id} not found")
    db_reading = SensorReading(**reading.model_dump())
    db.add(db_reading)  # not written to the entry log: readings arrive by the thousand
    commit(db)
    db.refresh(db_reading)
    return db_reading


@app.post("/api/lab-results", response_model=LabResultOut)
def ingest_lab_result(result: LabResultCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    batch = db.get(Batch, result.batch_id)
    if user.role != "regulator" and (batch is None or batch.organization_id != user.organization_id):
        # One answer whether the lot is someone else's or does not exist.
        raise HTTPException(403, "you can record lab results only for lots your own organization made")
    require(db, Batch, result.batch_id, "batch")
    db_result = LabResult(**result.model_dump())
    db.add(db_result)
    db.flush()
    log_entry(db, user, db_result)
    commit(db)
    db.refresh(db_result)
    return db_result


@app.get("/api/batches/{batch_id}/trace")
def trace_batch(batch_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"batch_id": batch_id, **trace_document(db, [batch_id], user)}


@app.get("/api/shipments/{shipment_id}/risk")
def shipment_risk(shipment_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.role != "regulator":
        ship = db.get(Shipment, shipment_id)
        if ship is None or user.organization_id not in (ship.from_org_id, ship.to_org_id):
            raise HTTPException(404, f"shipment {shipment_id} not found")
    return rule_based_risk_score(db, shipment_id)
