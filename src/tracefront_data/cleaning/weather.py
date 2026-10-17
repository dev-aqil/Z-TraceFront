"""Expand GHCN monthly element records without losing values or flags."""

from __future__ import annotations

import calendar
from collections import Counter
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import re

from tracefront_data.cleaning.common import Table, string_columns


def clean_noaa(path: Path, directory: Path, cutoff: date, source: dict) -> dict:
    columns = string_columns(["station_id", "element", "unit", "measurement_flag", "quality_flag", "source_flag", "observation_status"])
    columns.update(observation_date={"datatype": "date", "temporal_semantics": "Publisher daily reporting date; timezone/availability unknown"},
                   source_day_of_month={"datatype": "integer", "role": "lineage"},
                   raw_value={"datatype": "integer", "missing_sentinel": -9999},
                   value={"datatype": "decimal", "nullable": True, "unit_column": "unit"})
    table = Table(directory, "daily_observations", columns, grain="Station x calendar date x element, including missing observations",
                  source=source,
                  transformations=["Parse fixed-width monthly element rows into valid calendar day records",
                                   "Remove only nonexistent calendar-day sentinel padding; record counts separately",
                                   "Convert temperature tenths Celsius to Celsius and PRCP tenths mm to mm exactly",
                                   "Retain raw integer, measurement/quality/source flag characters including blanks/case",
                                   "Null -9999 values; retain quality-flagged numeric observations with explicit status",
                                   "Quarantine malformed/conflicting monthly records and physically invalid daily values"],
                  missing_semantics=["-9999 means publisher missing, never zero rainfall/temperature",
                                     "Blank MFLAG means no measurement information applicable; blank QFLAG means no failed QA check",
                                     "Blank SFLAG means no source; all literal flag characters survive",
                                     "Quality-flagged numeric values remain visible and are not automatically fit for features",
                                     "Trace/estimated/presumed-zero distinctions remain encoded by original MFLAG; no imputation"])
    lines = path.read_text(encoding="ascii").splitlines()
    key_values = {}
    conflicting = set()
    for line in lines:
        key = line[:21]
        if key in key_values and key_values[key] != line:
            conflicting.add(key)
        key_values.setdefault(key, line)
    monthly = {"raw_rows": len(lines), "accepted_rows": 0, "rejected_rows": 0, "duplicate_rows": 0,
               "malformed_rows": 0, "invalid_date_rows": 0, "missing_critical_identifiers": 0}
    seen = set()
    flags = {name: Counter() for name in ["measurement_flag", "quality_flag", "source_flag"]}
    padding = missing = 0
    with (directory / "monthly_records.rejected.jsonl").open("w", encoding="utf-8") as rejected:
        for row_number, line in enumerate(lines, 1):
            errors = []
            key = line[:21]
            if len(line) != 269:
                monthly["malformed_rows"] += 1
                errors.append("malformed_monthly_width")
            if key in seen:
                monthly["duplicate_rows"] += 1
                if key not in conflicting:
                    errors.append("exact_duplicate_monthly_record")
            seen.add(key)
            if key in conflicting:
                errors.append("conflicting_monthly_record_all_versions_quarantined")
            if not re.fullmatch(r"[A-Z0-9]{11}", line[:11]):
                monthly["missing_critical_identifiers"] += 1
                errors.append("missing_or_invalid_station_id")
            try:
                year, month = int(line[11:15]), int(line[15:17])
                date(year, month, 1)
                if year < 1800 or date(year, month, 1) > cutoff:
                    raise ValueError("implausible monthly date")
                days = calendar.monthrange(year, month)[1]
            except ValueError:
                monthly["invalid_date_rows"] += 1
                errors.append("invalid_monthly_date")
                days = 0
            element = line[17:21]
            if element not in {"TMIN", "TMAX", "TAVG", "PRCP"}:
                errors.append("unreviewed_weather_element_unit")
            if len(line) == 269 and days:
                for day in range(days + 1, 32):
                    offset = 21 + (day - 1) * 8
                    if line[offset:offset + 8] != "-9999   ":
                        errors.append("noncalendar_padding_contains_data_or_flags")
            if errors:
                monthly["rejected_rows"] += 1
                rejected.write(json.dumps({"source_row_number": row_number, "reason_codes": sorted(set(errors)),
                                           "raw_values": line}, sort_keys=True) + "\n")
                continue
            monthly["accepted_rows"] += 1
            padding += 31 - days
            for day in range(1, days + 1):
                offset = 21 + (day - 1) * 8
                value_raw = line[offset:offset + 5]
                mflag, qflag, sflag = line[offset + 5:offset + 8]
                table.observe({"raw_value": value_raw, "measurement_flag": mflag,
                               "quality_flag": qflag, "source_flag": sflag})
                observation_date = date(year, month, day)
                errors = []
                if observation_date > cutoff:
                    table.stats["invalid_date_rows"] += 1
                    errors.append("future_daily_date")
                try:
                    raw_number = int(value_raw)
                    value = None if raw_number == -9999 else Decimal(raw_number) / Decimal(10)
                    if value is not None and ((element == "PRCP" and value < 0)
                            or element.startswith("T") and value < Decimal("-273.15")):
                        raise ValueError("physically impossible weather value")
                except ValueError:
                    table.stats["invalid_numeric_rows"] += 1
                    errors.append("invalid_daily_value")
                    value = None
                if errors:
                    table.reject(row_number, {"day": day, "raw_slot": line[offset:offset + 8]}, errors, line[:11])
                    continue
                if value is None:
                    missing += 1
                for field, flag in zip(flags, (mflag, qflag, sflag)):
                    flags[field][flag] += 1
                status = ("publisher_missing_quality_flagged" if value is None and qflag != " " else
                          "publisher_missing" if value is None else "quality_flagged" if qflag != " " else "reported_unflagged")
                if qflag != " ":
                    table.issue(row_number, "quality_flagged_observation_retained", "quality_flag",
                                {"date": observation_date.isoformat(), "flag": qflag})
                table.accept(row_number, {"station_id": line[:11], "element": element,
                    "observation_date": observation_date.isoformat(), "source_day_of_month": day,
                    "raw_value": raw_number, "value": format(value, "f") if value is not None else None,
                    "unit": "mm" if element == "PRCP" else "degC", "measurement_flag": mflag,
                    "quality_flag": qflag, "source_flag": sflag, "observation_status": status})
    if monthly["raw_rows"] != monthly["accepted_rows"] + monthly["rejected_rows"]:
        raise ValueError("NOAA monthly row accounting failed")
    return {"tables": {"daily_observations": table.close()}, "monthly_input_accounting": monthly,
            "known_ambiguities": ["Missing source months are not expanded into a continuous historical calendar",
                                  "Quality-flagged values remain questionable; reporting date is not availability or an assumed UTC timestamp"],
            "excluded_noncalendar_padding_slots": padding, "calendar_day_missing_sentinel_count": missing,
            "preserved_flag_counts": {k: dict(sorted(v.items())) for k, v in flags.items()}}
