import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.analysis import router as analysis_router
from app.database import Base, engine, get_db
from app.models import Batch, BatchLot, LabResult, Organization, SensorReading, Shipment
from app.risk import rule_based_risk_score
from app.schemas import (
    BatchCreate,
    BatchOut,
    LabResultCreate,
    LabResultOut,
    SensorReadingCreate,
    SensorReadingOut,
)
from app.trace import batch_document, commit, require, router as trace_router, trace_document

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tracefront API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("TRACEFRONT_CORS", "http://localhost:3000").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(analysis_router)
app.include_router(trace_router)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "analysis_storage": "database"}


@app.get("/api/batches", response_model=list[BatchOut])
def list_batches(db: Session = Depends(get_db)):
    return [batch_document(db, batch) for batch in db.query(Batch).order_by(Batch.batch_id)]


@app.post("/api/batches", response_model=BatchOut, status_code=201)
def create_batch(batch: BatchCreate, db: Session = Depends(get_db)):
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
    commit(db)
    return batch_document(db, db_batch)


@app.post("/api/sensor-readings", response_model=SensorReadingOut)
def ingest_sensor_reading(reading: SensorReadingCreate, db: Session = Depends(get_db)):
    require(db, Shipment, reading.shipment_id, "shipment")
    db_reading = SensorReading(**reading.model_dump())
    db.add(db_reading)
    commit(db)
    db.refresh(db_reading)
    return db_reading


@app.post("/api/lab-results", response_model=LabResultOut)
def ingest_lab_result(result: LabResultCreate, db: Session = Depends(get_db)):
    require(db, Batch, result.batch_id, "batch")
    db_result = LabResult(**result.model_dump())
    db.add(db_result)
    commit(db)
    db.refresh(db_result)
    return db_result


@app.get("/api/batches/{batch_id}/trace")
def trace_batch(batch_id: int, db: Session = Depends(get_db)):
    return {"batch_id": batch_id, **trace_document(db, [batch_id])}


@app.get("/api/shipments/{shipment_id}/risk")
def shipment_risk(shipment_id: int, db: Session = Depends(get_db)):
    return rule_based_risk_score(db, shipment_id)
