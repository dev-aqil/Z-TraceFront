from sqlalchemy.orm import Session

from app.models import SensorReading

TEMP_THRESHOLD_C = 7.0  # above this for refrigerated goods counts as an excursion


def rule_based_risk_score(db: Session, shipment_id: int) -> dict:
    """Transparent rule-based priority score, not a calibrated contamination probability.
    ponytail: placeholder until a trained model (XGBoost/GBM) replaces it, see section 21 of the project summary.
    """
    readings = (
        db.query(SensorReading)
        .filter(SensorReading.shipment_id == shipment_id)
        .order_by(SensorReading.timestamp)
        .all()
    )
    if not readings:
        return {"shipment_id": shipment_id, "score": 0, "level": "UNKNOWN", "reasons": ["no sensor data"]}

    excursions = [r for r in readings if r.temperature is not None and r.temperature > TEMP_THRESHOLD_C]
    reasons = []
    score = 0

    if excursions:
        score += min(60, len(excursions) * 15)
        reasons.append(f"{len(excursions)} temperature excursion(s) above {TEMP_THRESHOLD_C}°C")

    max_temp = max((r.temperature for r in readings if r.temperature is not None), default=None)
    if max_temp is not None and max_temp > TEMP_THRESHOLD_C + 5:
        score += 25
        reasons.append(f"peak temperature {max_temp}°C")

    score = min(100, score)
    level = "HIGH" if score >= 70 else "MEDIUM" if score >= 35 else "LOW"

    return {"shipment_id": shipment_id, "score": score, "level": level, "reasons": reasons or ["no anomalies detected"]}
