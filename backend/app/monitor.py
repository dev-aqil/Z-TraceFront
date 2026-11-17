"""Live cold-chain monitoring. Each shipment's stored sensor readings are replayed through the food-risk-ml monitor in
time order, so a reading that arrives late still lands in its place. Levels:

  ok         every reading within the shipment's limit
  excursion  the latest reading is above the limit
  recovered  back within the limit, but it was above it: the evidence stays
  critical   USDA danger-zone time used up. Sticky: cooling down again does not undo time spent warm.

silent_minutes counts the minutes since the last reading of a shipment still moving (pending or in transit); a sensor
silent for longer than max_gap_minutes means the shipment is not being watched.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analysis import DEFAULT_PROFILE, PROFILE_NAMES, RULES, ColdChainMonitor
from app.auth import current_user, party, regulator
from app.database import get_db
from app.models import Batch, SensorReading, Shipment, ShipmentManifest, SyntheticBatch, User
from app.trace import batch_document, commit, require, shipment_document

router = APIRouter(prefix="/api/monitor", dependencies=[Depends(current_user)])

LEVELS = ("critical", "excursion", "recovered", "ok")  # most urgent first


def watch(db: Session, ship: Shipment, now: datetime) -> dict:
    # ponytail: replays the whole history on every request; keep per-shipment monitor state once a shipment holds
    # tens of thousands of readings
    manifest = db.get(ShipmentManifest, ship.shipment_id)
    profile = (manifest.cold_chain_profile if manifest else None) or DEFAULT_PROFILE
    readings = (db.query(SensorReading).filter(SensorReading.shipment_id == ship.shipment_id,
                                               SensorReading.temperature.isnot(None))
                .order_by(SensorReading.timestamp, SensorReading.reading_id).all())
    monitor = ColdChainMonitor(RULES)
    monitor.register("shipment", profile)
    for reading in readings:
        state = monitor.update("shipment", reading.timestamp.replace(tzinfo=timezone.utc), reading.temperature)
    alerts = monitor.streams["shipment"].alerts
    level = state["status"]
    if level == "ok" and any(alert["rule"] == "EXCURSION" for alert in alerts):
        level = "recovered"
    last, peak = readings[-1], max(readings, key=lambda r: r.temperature)
    moving = ship.status in ("pending", "in_transit")
    return {"shipment": shipment_document(db, ship), "lot": batch_document(db, db.get(Batch, ship.batch_id)),
            "profile": profile, "profile_name": PROFILE_NAMES.get(profile, profile), "limit_c": state["limit_c"],
            "level": level, "latest": {"temperature": last.temperature, "at": at(last)},
            "peak": {"temperature": peak.temperature, "at": at(peak)},
            "minutes_above_limit": state["minutes_above_limit"],
            "minutes_in_danger_zone": state["minutes_in_danger_zone"], "data_gaps": state["data_gaps"],
            "silent_minutes": max(0, round((now - last.timestamp.replace(tzinfo=timezone.utc)).total_seconds() / 60))
                              if moving else None,
            "max_gap_minutes": RULES["max_gap_minutes"], "alerts": alerts,
            "readings": [{"at": at(r), "temperature": r.temperature} for r in readings]}


def at(reading: SensorReading) -> str:
    return reading.timestamp.replace(tzinfo=timezone.utc).isoformat()


@router.get("")
def monitored(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Every shipment with temperature readings that the user may see, most urgent first."""
    with_readings = db.query(SensorReading.shipment_id).filter(SensorReading.temperature.isnot(None))
    query = db.query(Shipment).filter(Shipment.shipment_id.in_(with_readings))
    if user.role != "regulator":
        query = query.filter(party(user.organization_id))
    now = datetime.now(timezone.utc)
    return sorted((watch(db, ship, now) for ship in query),
                  key=lambda m: (LEVELS.index(m["level"]), m["shipment"]["shipment_id"]))


@router.delete("/{shipment_id}/readings")
def clear_readings(shipment_id: int, user: User = Depends(regulator), db: Session = Depends(get_db)):
    """Reset a demo replay. Readings on a real shipment are evidence and are never deleted here."""
    ship = require(db, Shipment, shipment_id, "shipment")
    if db.get(SyntheticBatch, ship.batch_id) is None:
        raise HTTPException(409, "only readings of a synthetic demo shipment can be cleared; "
                                 "readings of a real shipment are kept as evidence")
    deleted = db.query(SensorReading).filter(SensorReading.shipment_id == shipment_id).delete()
    commit(db)
    return {"deleted": deleted}
