"""Shipment-file analysis behind the frontend: upload a file, then read its findings (contracts/ml-findings.schema.json)
and its distribution tree. Rules, not a trained model, so priority_score is always null.

Temperature goes through the food-risk-ml cold-chain monitor (published product limits, USDA danger zone, data gaps),
the same code benchmarked on LinuxONE. Delay, humidity, quantity and destination compare the file with itself or with
the review limits below.

One row per sensor reading or event. Shipment-level columns may repeat on every row; the first filled value is used.
Required: shipment_id, batch_id. Optional: record_id, product, route, distributor, profile, destination, delivered_to,
reading_time, temperature_c, humidity_pct, planned_arrival, actual_arrival, dispatched_qty, received_qty.
Headers are matched loosely ("Batch ID" -> batch_id).
"""

import io
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Analysis

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "food-risk-ml"))
from src.coldchain.rules import ColdChainMonitor, load_rules  # noqa: E402

router = APIRouter(prefix="/api/analyses")

RULES = load_rules()
MODEL_VERSION = "cold-chain-rules-1"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DEFAULT_PROFILE = "tcs_food_us"  # FDA Food Code 5 °C; a `profile` column overrides it per shipment
# Display names for the cold_chain_rules.toml profiles; a profile missing here shows its key.
PROFILE_NAMES = {"poultry_chilled": "chilled poultry", "red_meat_chilled": "chilled red meat",
                 "offal_chilled": "chilled offal", "tcs_food_us": "TCS food", "frozen": "frozen food"}
# Review limits set by the operator, not regulatory limits: tune them per customer.
DELAY_LIMIT_MIN = 30.0
HUMIDITY_MAX_PCT = 75.0

ALIASES = {"temperature": "temperature_c", "shipment_time": "reading_time", "humidity": "humidity_pct"}
NUMBERS = ("temperature_c", "humidity_pct", "dispatched_qty", "received_qty")
TIMES = ("reading_time", "planned_arrival", "actual_arrival")
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def text(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) or not str(v).strip() else str(v).strip()


def parse(col: pd.Series, convert) -> pd.Series:
    """Convert a column, rejecting values that are present but invalid instead of silently dropping them."""
    blank = col.map(text).isna()
    out = convert(col.where(~blank))
    bad = out.isna() & ~blank
    if bad.any():
        i = bad.idxmax()
        raise HTTPException(400, f"{col.name}: {col[i]!r} in row {i + 1} is not valid")
    return out


def read_table(filename: str, raw: bytes) -> pd.DataFrame:
    readers = {".csv": lambda b: pd.read_csv(b, dtype=str),
               ".xlsx": lambda b: pd.read_excel(b, dtype=str),
               ".json": lambda b: pd.read_json(b, orient="records", dtype=False, convert_dates=False)}
    ext = Path(filename).suffix.lower()
    if ext not in readers:
        raise HTTPException(400, "file must be .csv, .xlsx or .json")
    try:
        df = readers[ext](io.BytesIO(raw))
    except Exception as e:  # each parser raises its own error types for malformed files
        raise HTTPException(400, f"could not read the {ext} file: {e}") from e

    cols = [ALIASES.get(n, n) for n in (re.sub(r"[^a-z0-9]+", "_", str(c).lower()).strip("_") for c in df.columns)]
    if len(set(cols)) != len(cols):
        raise HTTPException(400, f"duplicate columns after normalising headers: {cols}")
    df.columns = cols
    missing = [c for c in ("shipment_id", "batch_id") if c not in df]
    if missing:
        raise HTTPException(400, f"missing column(s): {', '.join(missing)}")
    if df.empty:
        raise HTTPException(400, "the file has no rows")

    df = df.reset_index(drop=True)
    for c in df.columns:
        if c in NUMBERS:
            df[c] = parse(df[c], lambda s: pd.to_numeric(s, errors="coerce").replace([np.inf, -np.inf], np.nan))
        elif c in TIMES:
            df[c] = parse(df[c], lambda s: pd.to_datetime(s, errors="coerce", utc=True, format="mixed"))
        else:
            df[c] = df[c].map(text)
    for c in ("shipment_id", "batch_id"):
        if df[c].isna().any():
            raise HTTPException(400, f"{c} is empty in row {df[c].isna().idxmax() + 1}")
    if "temperature_c" in df:
        times = df["reading_time"] if "reading_time" in df else pd.Series(pd.NaT, index=df.index)
        untimed = df.temperature_c.notna() & times.isna()
        if untimed.any():
            raise HTTPException(400, f"temperature_c in row {untimed.idxmax() + 1} has no reading_time")
    ids = pd.Series([f"row-{i + 1}" for i in df.index], index=df.index)
    df["record_id"] = df["record_id"].fillna(ids) if "record_id" in df else ids
    return df


def first(rows: pd.DataFrame, col: str):
    """First filled value of a shipment-level column, and the record it came from."""
    s = rows[col].dropna() if col in rows else ()
    return (s.iloc[0], rows.at[s.index[0], "record_id"]) if len(s) else (None, None)


def num(x):
    x = float(x)
    return int(x) if x.is_integer() else round(x, 3)


def ev(record, field, observed, threshold=None, unit=None, at=None) -> dict:
    return {"source_record_id": record, "field": field, "observed_value": observed, "threshold_value": threshold,
            "unit": unit, "observed_at": None if at is None or pd.isna(at) else at.isoformat()}


def shipment_findings(ship: str, rows: pd.DataFrame, monitor: ColdChainMonitor) -> list[dict]:
    batch, out = rows.batch_id.iloc[0], []

    def add(kind, severity, summary, *evidence):
        out.append({"finding_id": "", "batch_id": batch, "shipment_id": ship, "anomaly_type": kind,
                    "severity": severity, "priority_score": None, "summary": summary, "evidence": list(evidence)})

    readings = rows[rows.temperature_c.notna()] if "temperature_c" in rows else rows.iloc[:0]
    if len(readings):
        readings = readings.sort_values("reading_time", kind="stable")
        profile = first(rows, "profile")[0] or DEFAULT_PROFILE
        if profile not in RULES["profiles"]:
            raise HTTPException(400, f"shipment {ship}: unknown profile {profile!r}; use one of {sorted(RULES['profiles'])}")
        monitor.register(ship, profile)
        limit, source, dz = RULES["profiles"][profile]["max_c"], RULES["profiles"][profile]["source"], RULES["danger_zone"]
        gaps, critical, prev = [], None, None
        for rec, t, c in zip(readings.record_id, readings.reading_time, readings.temperature_c):
            state = monitor.update(ship, t.to_pydatetime(), c)
            for alert in state["new_alerts"]:
                if alert["rule"] == "DATA_GAP":
                    gaps.append((rec, t, (t - prev).total_seconds() / 60))
                elif alert["rule"] == "CRITICAL":
                    hot = state["minutes_above_hot"] >= dz["hot_limit_minutes"]
                    field, cap = ("minutes_above_hot", "hot_limit_minutes") if hot else ("minutes_in_danger_zone", "limit_minutes")
                    critical = (ev(rec, field, round(state[field]), dz[cap], "min", t), alert["message"])
            prev = t

        peak = readings.loc[readings.temperature_c.idxmax()]
        if peak.temperature_c > limit or critical:
            summary = (f"Peak temperature {peak.temperature_c:.1f} °C; the limit for {PROFILE_NAMES.get(profile, profile)} "
                       f"is {limit:g} °C ({source}).")
            evidence = [ev(peak.record_id, "temperature_c", num(peak.temperature_c), limit, "C", peak.reading_time)]
            if critical:
                summary += f" Danger zone: {critical[1]}."
                evidence.append(critical[0])
            add("temperature_excursion", "high" if critical else "medium", summary, *evidence)
        if gaps:
            rec, t, minutes = max(gaps, key=lambda g: g[2])
            cap = RULES["max_gap_minutes"]
            more = f" ({len(gaps)} gaps in total)" if len(gaps) > 1 else ""
            add("sensor_gap", "medium", f"No temperature reading for {minutes:.0f} min, over the {cap:g}-minute "
                f"limit{more}. Temperature during a gap is unknown.",
                ev(rec, "reading_gap_minutes", round(minutes), cap, "min", t))

    if "humidity_pct" in rows and rows.humidity_pct.notna().any():
        peak = rows.loc[rows.humidity_pct.idxmax()]
        if peak.humidity_pct > HUMIDITY_MAX_PCT:
            add("humidity_excursion", "medium", f"Humidity reached {peak.humidity_pct:g}% RH, above the "
                f"{HUMIDITY_MAX_PCT:g}% review limit.",
                ev(peak.record_id, "humidity_pct", num(peak.humidity_pct), HUMIDITY_MAX_PCT, "%", peak.get("reading_time")))

    (planned, _), (actual, rec) = first(rows, "planned_arrival"), first(rows, "actual_arrival")
    if planned is not None and actual is not None:
        late = (actual - planned).total_seconds() / 60
        if late > DELAY_LIMIT_MIN:
            add("shipment_delay", "medium", f"Arrived {late:.0f} min after the planned time, beyond the "
                f"{DELAY_LIMIT_MIN:g}-minute review limit.", ev(rec, "arrival_delay_minutes", round(late), DELAY_LIMIT_MIN, "min", actual))

    (sent, sent_rec), (got, got_rec) = first(rows, "dispatched_qty"), first(rows, "received_qty")
    if sent is not None and got is not None and got != sent:
        add("quantity_mismatch", "medium", f"Received {num(got)} against {num(sent)} dispatched "
            f"({num(abs(got - sent))} {'short' if got < sent else 'over'}).",
            ev(got_rec, "received_qty", num(got)), ev(sent_rec, "dispatched_qty", num(sent)))

    (planned_to, plan_rec), (went_to, went_rec) = first(rows, "destination"), first(rows, "delivered_to")
    if planned_to and went_to and planned_to.casefold() != went_to.casefold():
        add("destination_mismatch", "low", f"Delivered to {went_to}; the manifest lists {planned_to}.",
            ev(went_rec, "delivered_to", went_to), ev(plan_rec, "destination", planned_to))
    return out


def analyse(filename: str, raw: bytes) -> tuple[pd.DataFrame, list[dict]]:
    df = read_table(filename, raw)
    monitor, findings = ColdChainMonitor(RULES), []
    for ship, rows in df.groupby("shipment_id", sort=False):
        if rows.batch_id.nunique() > 1:
            # ponytail: one batch per shipment; mixed loads need a shipment-batch link table
            raise HTTPException(400, f"shipment {ship} lists more than one batch_id; use one shipment_id per batch")
        findings += shipment_findings(ship, rows, monitor)
    findings.sort(key=lambda f: SEVERITY_ORDER[f["severity"]])
    for n, f in enumerate(findings, 1):
        f["finding_id"] = f"finding-{n:03d}"
    return df, findings


def distribution(df: pd.DataFrame, findings: list[dict]) -> dict:
    """Distributor -> route -> batch -> shipment (recipient). Batches and shipments with findings are flagged."""
    flagged = {f["shipment_id"] for f in findings}
    nodes, edges = {}, {}

    def node(id_, kind, label, detail=None, hot=False):
        n = nodes.setdefault(id_, {"id": id_, "kind": kind, "label": label, "detail": detail, "flagged": False})
        n["flagged"] |= hot
        return id_

    for ship, rows in df.groupby("shipment_id", sort=False):
        hot, batch, product = ship in flagged, rows.batch_id.iloc[0], first(rows, "product")[0]
        distributor = first(rows, "distributor")[0] or "Supplier"
        route = first(rows, "route")[0] or "Unassigned route"
        destination = first(rows, "destination")[0] or first(rows, "delivered_to")[0] or "Unknown destination"
        path = [node(f"root:{distributor}", "root", distributor, "Distributor"),
                node(f"route:{distributor}:{route}", "route", route),
                node(f"batch:{distributor}:{route}:{batch}", "batch", f"{batch} · {product}" if product else batch, hot=hot),
                node(f"shipment:{ship}", "recipient", destination, ship, hot)]
        edges.update(dict.fromkeys(zip(path, path[1:])))
    return {"nodes": list(nodes.values()), "edges": [list(e) for e in edges]}


def stored(db: Session, analysis_id: str) -> Analysis:
    analysis = db.get(Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
    return analysis


@router.post("", status_code=201)
def create_analysis(file: UploadFile, db: Session = Depends(get_db)):
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file is larger than 10 MB")
    dataset_id = file.filename or "upload"
    df, findings = analyse(dataset_id, raw)
    analysis_id = f"analysis-{uuid4().hex[:12]}"
    generated_at = datetime.now(timezone.utc)
    db.add(Analysis(analysis_id=analysis_id, dataset_id=dataset_id, generated_at=generated_at,
                    findings={"schema_version": "1.0", "analysis_id": analysis_id, "dataset_id": dataset_id,
                              "generated_at": generated_at.isoformat(), "model_version": MODEL_VERSION,
                              "findings": findings},
                    distribution={"analysis_id": analysis_id, **distribution(df, findings)}))
    db.commit()
    return {"analysis_id": analysis_id, "dataset_id": dataset_id, "rows": len(df),
            "shipments": df.shipment_id.nunique(), "batches": df.batch_id.nunique(), "findings": len(findings)}


@router.get("/{analysis_id}/findings")
def get_findings(analysis_id: str, db: Session = Depends(get_db)):
    return stored(db, analysis_id).findings


@router.get("/{analysis_id}/distribution")
def get_distribution(analysis_id: str, db: Session = Depends(get_db)):
    return stored(db, analysis_id).distribution
