from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.analysis import router as analysis_router
from app.database import Base, engine, get_db
from app.graph import trace_backward, trace_forward
from app.models import Batch, LabResult, SensorReading
from app.risk import rule_based_risk_score
from app.schemas import (
    BatchCreate,
    BatchOut,
    LabResultCreate,
    LabResultOut,
    SensorReadingCreate,
    SensorReadingOut,
)

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tracefront API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(analysis_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/batches", response_model=list[BatchOut])
def list_batches(db: Session = Depends(get_db)):
    return db.query(Batch).all()


@app.post("/api/batches", response_model=BatchOut)
def create_batch(batch: BatchCreate, db: Session = Depends(get_db)):
    db_batch = Batch(**batch.model_dump())
    db.add(db_batch)
    db.commit()
    db.refresh(db_batch)
    return db_batch


@app.post("/api/sensor-readings", response_model=SensorReadingOut)
def ingest_sensor_reading(reading: SensorReadingCreate, db: Session = Depends(get_db)):
    db_reading = SensorReading(**reading.model_dump())
    db.add(db_reading)
    db.commit()
    db.refresh(db_reading)
    return db_reading


@app.post("/api/lab-results", response_model=LabResultOut)
def ingest_lab_result(result: LabResultCreate, db: Session = Depends(get_db)):
    db_result = LabResult(**result.model_dump())
    db.add(db_result)
    db.commit()
    db.refresh(db_result)
    return db_result


@app.get("/api/batches/{batch_id}/trace")
def trace_batch(batch_id: int, db: Session = Depends(get_db)):
    if not db.query(Batch).filter(Batch.batch_id == batch_id).first():
        raise HTTPException(404, "batch not found")
    return {
        "batch_id": batch_id,
        "upstream": trace_backward(db, batch_id),
        "downstream": trace_forward(db, batch_id),
    }


@app.get("/api/shipments/{shipment_id}/risk")
def shipment_risk(shipment_id: int, db: Session = Depends(get_db)):
    return rule_based_risk_score(db, shipment_id)
