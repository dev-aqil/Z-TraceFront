"""Real-time cold-chain monitor: published temperature rules (configs/cold_chain_rules.toml) applied to a stream of
sensor readings. Rules, not a learned model: there is no cold-chain dataset with outcomes to learn from or score
against, so this module makes no accuracy claim.

Readings arrive one at a time and cost O(1) each, so it runs on a live feed. Time is integrated sample-and-hold:
the interval after a reading is charged at that reading's temperature until the next reading. Gaps longer than
`max_gap_minutes` are never bridged; they raise DATA_GAP, because missing data is unknown, not "in range".

Statuses: ok -> excursion (above the product limit now) -> critical (USDA danger-zone time exhausted). Critical is
sticky: time already spent warm cannot be undone by cooling down again.
"""

import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from src.config import ROOT

RULES_FILE = ROOT / "configs" / "cold_chain_rules.toml"


def load_rules(path: Path = RULES_FILE) -> dict:
    with open(path, "rb") as f:
        return tomllib.load(f)


@dataclass
class Stream:
    profile: str
    offset_c: float = 0.0  # calibration: added to every raw reading (sensors read off; set per sensor)
    last_time: datetime | None = None
    last_c: float | None = None
    minutes_above_limit: float = 0.0
    minutes_in_danger_zone: float = 0.0
    minutes_above_hot: float = 0.0
    excursion_open: bool = False
    critical: bool = False
    data_gaps: int = 0
    alerts: list = field(default_factory=list)


class ColdChainMonitor:
    def __init__(self, rules: dict | None = None):
        self.rules = rules or load_rules()
        self.streams: dict[str, Stream] = {}

    def register(self, stream_id: str, profile: str, offset_c: float = 0.0) -> None:
        if profile not in self.rules["profiles"]:
            raise KeyError(f"unknown profile {profile!r}; configured: {sorted(self.rules['profiles'])}")
        self.streams[stream_id] = Stream(profile, offset_c)

    def update(self, stream_id: str, time: datetime, raw_c: float) -> dict:
        s = self.streams[stream_id]
        prof, dz = self.rules["profiles"][s.profile], self.rules["danger_zone"]
        c, new = float(raw_c) + s.offset_c, []
        if not np.isfinite(c):
            raise ValueError(f"{stream_id}: non-finite reading {raw_c!r}")

        if s.last_time is not None:
            minutes = (time - s.last_time).total_seconds() / 60
            if minutes < 0:
                raise ValueError(f"{stream_id}: reading at {time} is earlier than the previous one ({s.last_time})")
            if minutes > self.rules["max_gap_minutes"]:
                s.data_gaps += 1
                new.append(self._alert("DATA_GAP", time, f"no reading for {minutes:.0f} min "
                                       f"(> {self.rules['max_gap_minutes']:.0f}); interval not counted",
                                       "monitoring policy: gaps are unknown, never assumed in range"))
            else:  # charge the elapsed interval at the previous reading's temperature
                if s.last_c > prof["max_c"]:
                    s.minutes_above_limit += minutes
                if dz["low_c"] < s.last_c < dz["high_c"]:
                    s.minutes_in_danger_zone += minutes
                    if s.last_c > dz["hot_c"]:
                        s.minutes_above_hot += minutes

        if c > prof["max_c"] and not s.excursion_open:
            new.append(self._alert("EXCURSION", time, f"{c:.2f} °C is above the {s.profile} limit of "
                                   f"{prof['max_c']:.2f} °C", prof["source"]))
        s.excursion_open = c > prof["max_c"]
        if not s.critical and (s.minutes_in_danger_zone >= dz["limit_minutes"]
                               or s.minutes_above_hot >= dz["hot_limit_minutes"]):
            s.critical = True
            new.append(self._alert("CRITICAL", time, f"{s.minutes_in_danger_zone:.0f} min above "
                                   f"{dz['low_c']} °C ({s.minutes_above_hot:.0f} min above {dz['hot_c']} °C): USDA "
                                   f"limit is {dz['limit_minutes']:.0f} min, or {dz['hot_limit_minutes']:.0f} min above "
                                   f"{dz['hot_c']} °C", "USDA FSIS danger-zone guidance (2-hour / 1-hour rule)"))
        s.last_time, s.last_c = time, c
        s.alerts += new
        return {"stream_id": stream_id, "time": time.isoformat(), "temp_c": round(c, 3), "profile": s.profile,
                "status": "critical" if s.critical else "excursion" if s.excursion_open else "ok",
                "limit_c": prof["max_c"], "minutes_above_limit": round(s.minutes_above_limit, 2),
                "minutes_in_danger_zone": round(s.minutes_in_danger_zone, 2),
                "minutes_above_hot": round(s.minutes_above_hot, 2), "data_gaps": s.data_gaps, "new_alerts": new}

    @staticmethod
    def _alert(rule: str, time: datetime, message: str, source: str) -> dict:
        return {"rule": rule, "time": time.isoformat(), "message": message, "source": source}


def cold_chain_cli(profile: str, readings: Path | None, scenario: str, offset_c: float, benchmark: int) -> dict:
    """Alert timeline and final state per stream; optional throughput timing on simulated readings."""
    import time as clock

    import pandas as pd
    mon = ColdChainMonitor()
    if readings:
        df = pd.read_csv(readings, dtype={"stream_id": str}, parse_dates=["time"])
        rows, simulated = df[["stream_id", "time", "temp_c"]].itertuples(index=False), False
    else:
        rows = (("sim", t, c) for t, c in simulate(scenario, datetime(2026, 1, 1, 6, 0)))
        simulated = True
    last = {}
    for sid, t, c in rows:
        if sid not in mon.streams:
            mon.register(sid, profile, offset_c)
        last[sid] = mon.update(sid, pd.Timestamp(t).to_pydatetime(), c)
    out = {"simulated": simulated, "scenario": scenario if simulated else None, "profile": profile,
           "streams": {sid: {k: v for k, v in r.items() if k != "new_alerts"} | {"alerts": mon.streams[sid].alerts}
                       for sid, r in last.items()}}
    if benchmark:
        feed = simulate("compressor_failure", datetime(2026, 1, 1), minutes=benchmark, every=1.0)
        bench = ColdChainMonitor(mon.rules)
        bench.register("bench", profile)
        t0 = clock.perf_counter()
        for t, c in feed:
            bench.update("bench", t, c)
        secs = clock.perf_counter() - t0
        out["benchmark"] = {"readings": len(feed), "seconds": round(secs, 4), "readings_per_second": round(len(feed) / secs),
                            "mean_latency_us": round(1e6 * secs / len(feed), 2)}
    return out


SCENARIOS = ("normal", "door_open", "compressor_failure", "sensor_dropout")


def simulate(scenario: str, start: datetime, minutes: int = 360, every: float = 1.0, base_c: float = 2.5,
             seed: int = 0) -> list[tuple[datetime, float]]:
    """SIMULATED readings for demos and tests. Not measurements: nothing derived from them is evidence."""
    if scenario not in SCENARIOS:
        raise ValueError(f"scenario must be one of {SCENARIOS}")
    rng = np.random.default_rng(seed)
    out = []
    for i in range(int(minutes / every)):
        m = i * every
        c = base_c + rng.normal(0, 0.2)
        if scenario == "door_open" and 120 <= m < 140:      # doors open during unloading: brief rise
            c = 6.5 + rng.normal(0, 0.3)
        elif scenario == "compressor_failure" and m >= 60:  # refrigeration fails: warms toward ambient 28 °C
            c = 28 - (28 - base_c) * np.exp(-(m - 60) / 90) + rng.normal(0, 0.2)
        elif scenario == "sensor_dropout" and 150 <= m < 190:
            continue
        out.append((start + timedelta(minutes=m), float(c)))
    return out
