"""Cold-chain rules on hand-made and SIMULATED readings (no real sensor data exists)."""

from datetime import datetime, timedelta

import pytest

from src.coldchain.rules import SCENARIOS, ColdChainMonitor, load_rules, simulate

T0 = datetime(2026, 1, 1, 8, 0)


def feed(mon, sid, temps, every=1.0):
    return [mon.update(sid, T0 + timedelta(minutes=i * every), c) for i, c in enumerate(temps)]


def test_every_profile_cites_a_source():
    rules = load_rules()
    assert rules["profiles"] and all(p["source"] and "max_c" in p for p in rules["profiles"].values())


def test_sample_and_hold_minutes_and_excursion_alert_once():
    mon = ColdChainMonitor()
    mon.register("truck1", "poultry_chilled")
    out = feed(mon, "truck1", [2.0, 5.0, 5.0, 5.0, 2.0, 2.0])
    assert [o["status"] for o in out] == ["ok", "excursion", "excursion", "excursion", "ok", "ok"]
    assert out[-1]["minutes_above_limit"] == 3.0 and out[-1]["minutes_in_danger_zone"] == 3.0
    assert sum(a["rule"] == "EXCURSION" for o in out for a in o["new_alerts"]) == 1
    assert "853/2004" in out[1]["new_alerts"][0]["source"]


def test_danger_zone_time_turns_critical_and_stays_critical():
    mon = ColdChainMonitor()
    mon.register("a", "red_meat_chilled")
    out = feed(mon, "a", [10.0] * 121 + [2.0] * 5)  # 120 min above 4.4 °C, then cooled again
    assert out[119]["status"] == "excursion" and out[120]["status"] == "critical"
    assert out[-1]["status"] == "critical"  # cooling down does not undo time already spent warm
    mon.register("hot", "red_meat_chilled")
    assert feed(mon, "hot", [35.0] * 61)[-1]["status"] == "critical"  # 1-hour rule above 90 °F


def test_gap_is_not_bridged_and_is_reported():
    mon = ColdChainMonitor()
    mon.register("s", "poultry_chilled")
    mon.update("s", T0, 10.0)
    r = mon.update("s", T0 + timedelta(minutes=60), 10.0)
    assert r["minutes_above_limit"] == 0 and r["data_gaps"] == 1 and r["new_alerts"][0]["rule"] == "DATA_GAP"


def test_calibration_offset_and_bad_input():
    mon = ColdChainMonitor()
    mon.register("s", "poultry_chilled", offset_c=-0.5)  # sensor known to read 0.5 °C high
    assert mon.update("s", T0, 4.3)["status"] == "ok"
    with pytest.raises(ValueError, match="earlier"):
        mon.update("s", T0 - timedelta(minutes=1), 2.0)
    with pytest.raises(ValueError, match="non-finite"):
        mon.update("s", T0 + timedelta(minutes=1), float("nan"))
    with pytest.raises(KeyError):
        mon.register("x", "ice_cream")


@pytest.mark.parametrize("scenario, expected", [
    ("normal", "ok"), ("door_open", "ok"), ("compressor_failure", "critical"), ("sensor_dropout", "ok")])
def test_simulated_scenarios(scenario, expected):
    assert scenario in SCENARIOS
    mon = ColdChainMonitor()
    mon.register("sim", "poultry_chilled")
    out = [mon.update("sim", t, c) for t, c in simulate(scenario, T0)]
    assert out[-1]["status"] == expected
    assert (out[-1]["data_gaps"] > 0) == (scenario == "sensor_dropout")
    if scenario == "door_open":  # brief excursion recorded, but far from the 2-hour danger-zone limit
        assert 15 <= out[-1]["minutes_above_limit"] <= 25


def test_cli_reads_csv_streams_and_benchmarks(tmp_path):
    from src.coldchain.rules import cold_chain_cli
    rows = ["stream_id,time,temp_c"] + [f"truckA,2026-01-01T08:{m:02d}:00,{2.0 if m < 5 else 9.0}" for m in range(10)] \
        + [f"truckB,2026-01-01T08:{m:02d}:00,1.5" for m in range(10)]
    (tmp_path / "r.csv").write_text("\n".join(rows))
    out = cold_chain_cli("red_meat_chilled", tmp_path / "r.csv", "normal", 0.0, benchmark=500)
    assert out["simulated"] is False
    assert out["streams"]["truckA"]["status"] == "excursion" and out["streams"]["truckB"]["status"] == "ok"
    assert out["streams"]["truckA"]["alerts"][0]["rule"] == "EXCURSION"
    assert out["benchmark"]["readings"] == 500 and out["benchmark"]["readings_per_second"] > 0
