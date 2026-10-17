import io
import json

import pandas as pd
from fastapi import HTTPException

from app.analysis import analyse, coverage, distribution

COLUMNS = ["Shipment ID", "Batch ID", "product", "route", "distributor", "profile", "destination", "delivered_to",
           "Shipment time", "Temperature", "humidity_pct", "planned_arrival", "actual_arrival",
           "dispatched_qty", "received_qty"]


def rows():
    def r(ship, batch, **kw):
        return {"Shipment ID": ship, "Batch ID": batch, "distributor": "Food Processing", **kw}
    out = [  # excursion (8.4 > 7) plus an 80-minute gap
        r("SHIP-017", "RM-402", product="Marinated chicken", route="Protein", profile="red_meat_chilled",
          destination="QSR Group A", **{"Shipment time": "2026-10-17T07:00:00Z", "Temperature": "3"}),
        r("SHIP-017", "RM-402", **{"Shipment time": "2026-10-17T07:10:00Z", "Temperature": "8.4"}),
        r("SHIP-017", "RM-402", **{"Shipment time": "2026-10-17T08:30:00Z", "Temperature": "3"}),
        r("SHIP-024", "RM-415", route="Marinades", planned_arrival="2026-10-17T09:00:00Z",
          actual_arrival="2026-10-17T10:35:00Z"),
        r("SHIP-029", "RM-411", route="Produce", humidity_pct="83"),
        r("SHIP-034", "RM-426", route="Produce", dispatched_qty="240", received_qty="228"),
        r("SHIP-042", "RM-436", route="Dry", destination="KITCHEN-21", delivered_to="KITCHEN-24"),
        r("SHIP-050", "RM-440", route="Dry", destination="Bakery B", **{"Shipment time": "2026-10-17T07:00:00Z",
                                                                        "Temperature": "2"}),
    ]
    # 6 °C (inside the 4.4-60 °C danger zone) every 10 min for 130 min: USDA 2-hour rule trips
    out += [r("SHIP-060", "RM-450", route="Protein", **{"Shipment time": f"2026-10-17T{6 + m // 60:02d}:{m % 60:02d}:00Z",
                                                        "Temperature": "6"}) for m in range(0, 140, 10)]
    return out


def csv_bytes(records):
    return pd.DataFrame(records, columns=COLUMNS).to_csv(index=False).encode()


def by_type(findings):
    return {(f["shipment_id"], f["anomaly_type"]): f for f in findings}


def test_each_rule_fires_once_and_clean_shipment_has_none():
    _, findings = analyse("s.csv", csv_bytes(rows()))
    got = by_type(findings)
    assert set(got) == {("SHIP-017", "temperature_excursion"), ("SHIP-017", "sensor_gap"),
                        ("SHIP-024", "shipment_delay"), ("SHIP-029", "humidity_excursion"),
                        ("SHIP-034", "quantity_mismatch"), ("SHIP-042", "destination_mismatch"),
                        ("SHIP-060", "temperature_excursion")}
    assert got[("SHIP-017", "temperature_excursion")]["severity"] == "medium"
    assert got[("SHIP-017", "temperature_excursion")]["evidence"][0]["observed_value"] == 8.4
    assert got[("SHIP-017", "sensor_gap")]["evidence"][0]["observed_value"] == 80
    assert got[("SHIP-024", "shipment_delay")]["evidence"][0]["observed_value"] == 95
    assert got[("SHIP-060", "temperature_excursion")]["severity"] == "high"  # > 2 h in the danger zone
    assert findings[0]["severity"] == "high" and [f["finding_id"] for f in findings][:2] == ["finding-001", "finding-002"]
    assert all(f["priority_score"] is None and f["evidence"] for f in findings)
    json.dumps(findings)  # plain JSON types only


def test_distribution_flags_only_shipments_with_findings():
    df, findings = analyse("s.csv", csv_bytes(rows()))
    graph = distribution(df, findings)
    nodes = {n["id"]: n for n in graph["nodes"]}
    batch = "batch:Food Processing:Protein:RM-402"
    assert nodes["shipment:SHIP-017"]["flagged"] and nodes[batch]["flagged"]
    assert not nodes["shipment:SHIP-050"]["flagged"] and not nodes["root:Food Processing"]["flagged"]
    assert nodes[batch]["label"] == "RM-402 · Marinated chicken"
    assert ["route:Food Processing:Protein", batch] in graph["edges"] and [batch, "shipment:SHIP-017"] in graph["edges"]
    assert len(graph["edges"]) == len({tuple(e) for e in graph["edges"]})


def test_json_and_xlsx_match_csv():
    frame = pd.DataFrame(rows(), columns=COLUMNS)
    xlsx = io.BytesIO()
    frame.to_excel(xlsx, index=False)
    want = by_type(analyse("s.csv", csv_bytes(rows()))[1]).keys()
    assert by_type(analyse("s.json", json.dumps(rows()).encode())[1]).keys() == want
    assert by_type(analyse("s.xlsx", xlsx.getvalue())[1]).keys() == want


def test_same_route_name_does_not_connect_different_distributors():
    import networkx as nx
    df, findings = analyse("s.csv", b"shipment_id,batch_id,distributor,route\nS1,B,A,Cold\nS2,B,C,Cold\n")
    graph = nx.DiGraph(distribution(df, findings)["edges"])
    assert "shipment:S1" in nx.descendants(graph, "root:A")
    assert "shipment:S2" not in nx.descendants(graph, "root:A")
    assert "shipment:S1" not in nx.descendants(graph, "root:C")


def rejected(name, raw):
    try:
        analyse(name, raw)
    except HTTPException as e:
        return e.status_code == 400
    return False


def test_bad_input_is_rejected_not_dropped():
    assert rejected("s.txt", b"x")
    assert rejected("s.csv", b"batch_id\nRM-1\n")                                   # no shipment_id
    assert rejected("s.csv", b"shipment_id,batch_id,temperature_c,reading_time\nS,B,abc,2026-10-17T07:00:00Z\n")
    assert rejected("s.csv", b"shipment_id,batch_id,temperature_c\nS,B,5\n")         # reading without a time
    assert rejected("s.csv", b"shipment_id,batch_id\nS,B1\nS,B2\n")                  # two batches in one shipment
    assert rejected("s.csv", b"shipment_id,batch_id,profile,temperature_c,reading_time\nS,B,warm,5,2026-10-17\n")


def test_coverage_reports_checks_without_data():
    df, findings = analyse("ids.csv", b"shipment_id,batch_id\nS1,B1\nS2,B2\n")
    assert findings == []
    assert all(c["shipments_checked"] == 0 and c["shipments_total"] == 2 for c in coverage(df))
    checked = {c["check"]: c["shipments_checked"] for c in coverage(analyse("s.csv", csv_bytes(rows()))[0])}
    # temperature: SHIP-017/050/060; delay needs both times (SHIP-024); destination needs both fields (SHIP-042)
    assert checked == {"temperature": 3, "humidity": 1, "delay": 1, "quantity": 1, "destination": 1}


if __name__ == "__main__":
    test_each_rule_fires_once_and_clean_shipment_has_none()
    test_distribution_flags_only_shipments_with_findings()
    test_json_and_xlsx_match_csv()
    test_same_route_name_does_not_connect_different_distributors()
    test_bad_input_is_rejected_not_dropped()
    test_coverage_reports_checks_without_data()
    print("ok")
