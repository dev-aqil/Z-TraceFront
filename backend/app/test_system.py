"""HTTP integration checks against an isolated, foreign-key-enforced SQLite database."""

import csv
from datetime import datetime
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# One company's records as an import file. The ingredient row comes first: row order must not matter.
CHAIN = [
    {"record": "ingredient", "lot_code": "IP-9", "ingredient_lot_code": "IF-1", "quantity": "40"},
    {"record": "organisation", "name": "Import Farm", "type": "supplier"},
    {"record": "organization", "name": "Import Factory", "type": "factory"},
    {"record": "organization", "name": "Import Depot", "type": "warehouse"},
    {"record": "organization", "name": "Import Shop", "type": "store"},
    {"record": "lot", "producer": "Import Farm", "lot_code": "IF-1", "product": "Spinach", "produced_at": "2026-11-01 06:00"},
    {"record": "lot", "producer": "Import Factory", "lot_code": "IP-9", "product": "Spinach pie", "produced_at": "2026-11-02T06:00:00"},
    {"record": "shipment", "shipment_code": "IMP-S1", "lot_code": "IF-1", "from": "Import Farm", "to": "import factory",
     "quantity": "50", "unit": "kg", "status": "delivered"},
    {"record": "shipment", "shipment_code": "IMP-S2", "lot_code": "IP-9", "from": "Import Factory", "to": "Import Depot",
     "quantity": "1000", "unit": "units", "status": "delivered"},
    {"record": "shipment", "shipment_code": "IMP-S3", "lot_code": "IP-9", "from": "Import Depot", "to": "Import Shop",
     "quantity": "300", "unit": "units", "status": "in_transit"},
]


class SystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="tracefront-tests-")
        cls.env = {**os.environ, "DATABASE_URL": "sqlite:///" + str(Path(cls.temp.name) / "test.db")}
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.start()

    @classmethod
    def start(cls):
        # The Windows venv executable is a launcher. Start the interpreter directly so stop() owns the server.
        script = (f"import sys; sys.path[:] = {sys.path!r}; import uvicorn; "
                  f"uvicorn.run('app.main:app', host='127.0.0.1', port={cls.port})")
        cls.process = subprocess.Popen(
            [getattr(sys, "_base_executable", sys.executable), "-B", "-c", script],
            cwd=Path(__file__).resolve().parents[1], env=cls.env,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        for _ in range(100):
            if cls.process.poll() is not None:
                raise RuntimeError(cls.process.stderr.read().decode())
            try:
                with urlopen(f"http://127.0.0.1:{cls.port}/api/health", timeout=1) as response:
                    if response.status == 200:
                        return
            except (URLError, TimeoutError):
                time.sleep(0.2)
        cls.stop()
        raise RuntimeError("test API did not become ready")

    @classmethod
    def stop(cls):
        cls.process.terminate()
        try:
            cls.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.process.kill()
            cls.process.wait(timeout=5)
        cls.process.stderr.close()

    @classmethod
    def tearDownClass(cls):
        cls.stop()
        cls.temp.cleanup()

    def call(self, path, body=None, *, raw=None, content_type="application/json"):
        data = json.dumps(body).encode() if body is not None else raw
        req = Request(f"http://127.0.0.1:{self.port}{path}", data=data,
                      headers={"Content-Type": content_type})
        try:
            with urlopen(req, timeout=15) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def upload(self, csv_text, path="/api/analyses"):
        boundary = "tracefront-test-boundary"
        raw = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sensor.csv\"\r\n"
               f"Content-Type: text/csv\r\n\r\n{csv_text}\r\n--{boundary}--\r\n").encode()
        return self.call(path, raw=raw, content_type=f"multipart/form-data; boundary={boundary}")

    def import_records(self, rows):
        """Send trace records as one CSV whose columns are the union of the rows' keys."""
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=list(dict.fromkeys(key for row in rows for key in row)), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return self.upload(out.getvalue(), "/api/records/import")

    def test_import_builds_a_traceable_chain_and_repeating_it_adds_nothing(self):
        code, result = self.import_records(CHAIN)
        self.assertEqual(code, 200, result)
        self.assertEqual(result["created"], {"organizations": 4, "lots": 2, "ingredients": 1, "shipments": 3})
        pie = self.call("/api/lots/resolve?lot_code=IP-9")[1]
        self.assertEqual((pie["organization_name"], pie["produced_at"]), ("Import Factory", "2026-11-02T06:00:00"))
        spinach = self.call("/api/lots/resolve?lot_code=IF-1")[1]["batch_id"]
        _, trace = self.call(f"/api/trace?batch_ids={pie['batch_id']}")
        self.assertEqual(trace["upstream"], [spinach])
        self.assertEqual({(s["shipment_code"], s["to_name"], s["quantity_unit"]) for s in trace["shipments"]},
                         {("IMP-S1", "Import Factory", "kg"), ("IMP-S2", "Import Depot", "units"),
                          ("IMP-S3", "Import Shop", "units")})
        before = len(self.call("/api/batches")[1])
        code, again = self.import_records(CHAIN)
        self.assertEqual(code, 200, again)
        self.assertEqual(again["created"], {"organizations": 0, "lots": 0, "ingredients": 0, "shipments": 0})
        self.assertEqual(again["existing"], result["created"])
        self.assertEqual(len(self.call("/api/batches")[1]), before)

    def test_the_downloadable_template_imports_as_it_is(self):
        template = Path(__file__).resolve().parents[2] / "frontend" / "public" / "trace_records_template.csv"
        code, result = self.upload(template.read_text(encoding="utf-8"), "/api/records/import")
        self.assertEqual(code, 200, result)
        self.assertEqual(result["created"], {"organizations": 4, "lots": 2, "ingredients": 1, "shipments": 3})

    def test_import_with_bad_rows_names_them_and_changes_nothing(self):
        code, result = self.import_records([
            {"record": "organization", "name": "Rejected Farm", "type": "supplier"},
            {"record": "lot", "producer": "Nobody Ltd", "lot_code": "X-1", "product": "Rice", "produced_at": "2026-11-01"},
            {"record": "lot", "producer": "Rejected Farm", "lot_code": "X-2", "product": "Rice", "produced_at": "01/11/2026"},
            {"record": "shipment", "shipment_code": "X-S1", "lot_code": "X-404", "from": "Rejected Farm",
             "to": "Rejected Farm", "quantity": "5", "unit": "kg", "status": "delivered"},
            {"record": "pallet", "name": "?"},
        ])
        self.assertEqual(code, 400, result)
        for expected in ("nothing was imported", "row 2: unknown organization 'Nobody Ltd'", "row 3: produced_at",
                         "row 4: unknown lot 'X-404'", "row 5: record"):
            self.assertIn(expected, result["detail"])
        self.assertNotIn("Rejected Farm", [org["name"] for org in self.call("/api/organizations")[1]])

    def test_import_refuses_an_ingredient_cycle_and_two_lots_on_one_shipment_code(self):
        base = [{"record": "organization", "name": "Loop Factory", "type": "factory"},
                {"record": "organization", "name": "Loop Shop", "type": "store"},
                {"record": "lot", "producer": "Loop Factory", "lot_code": "LP-1", "product": "Dough", "produced_at": "2026-11-01"},
                {"record": "lot", "producer": "Loop Factory", "lot_code": "LP-2", "product": "Bread", "produced_at": "2026-11-02"}]
        code, cycle = self.import_records(base + [
            {"record": "ingredient", "lot_code": "LP-2", "ingredient_lot_code": "LP-1", "quantity": "1"},
            {"record": "ingredient", "lot_code": "LP-1", "ingredient_lot_code": "LP-2", "quantity": "1"}])
        self.assertEqual(code, 400, cycle)
        self.assertIn("row 6: ", cycle["detail"])
        self.assertIn("cycle", cycle["detail"])
        ship = {"record": "shipment", "shipment_code": "LP-S", "from": "Loop Factory", "to": "Loop Shop",
                "quantity": "10", "unit": "units", "status": "delivered"}
        code, mixed = self.import_records(base + [{**ship, "lot_code": "LP-1"}, {**ship, "lot_code": "LP-2"}])
        self.assertEqual(code, 400, mixed)
        self.assertIn("row 6: ", mixed["detail"])
        self.assertIn("one lot per shipment code", mixed["detail"])

    def test_trace_lists_who_made_and_handled_each_lot_with_quantities(self):
        self.assertEqual(self.call("/api/demo/seed", {})[0], 200)
        orgs = {org["name"]: org for org in self.call("/api/trace?batch_ids=910042")[1]["organizations"]}
        self.assertEqual(list(orgs)[:3], ["Greenfield Farm", "Food Processing", "Central Kitchen, QSR Group A"])  # suppliers first

        def holding(name, batch):
            return next(h for h in orgs[name]["holdings"] if h["batch_id"] == batch)

        self.assertEqual(holding("Warehouse KL", 910042), {"batch_id": 910042, "unit": "units", "received": 1200,
                                                           "incoming": 0, "sent": 700, "remaining": 500, "used_in": []})
        self.assertEqual((holding("Store KL-03", 910042)["received"], holding("Store KL-03", 910042)["incoming"]), (0, 400))
        self.assertEqual(holding("Store KL-04", 910042)["remaining"], 300)
        kitchen = orgs["Central Kitchen, QSR Group A"]
        self.assertEqual((kitchen["type"], kitchen["produced_batch_ids"]), ("factory", [910042]))
        # Production quantity is not recorded, so nothing can be said about what the maker still has.
        self.assertEqual((holding(kitchen["name"], 910042)["sent"], holding(kitchen["name"], 910042)["remaining"]), (1200, None))
        lettuce = holding(kitchen["name"], 910102)
        self.assertEqual((lettuce["received"], lettuce["unit"], lettuce["used_in"]), (10, "kg", [910042]))
        self.assertEqual(holding("Warehouse JB", 910017)["incoming"], 600)  # pending: not yet there

    def test_a_trace_can_start_from_an_organization(self):
        self.assertEqual(self.call("/api/demo/seed", {})[0], 200)

        def lots(org):
            _, body = self.call(f"/api/organizations/{org}/lots")
            self.assertEqual(body["total"], len(body["lots"]))
            return [(lot["lot_code"], lot["relation"]) for lot in body["lots"]]

        self.assertEqual(lots(910001), [("L-102", "produced")])
        self.assertEqual(lots(910003), [("CW-42", "produced")])  # its ingredient lots are reached by the trace itself
        self.assertEqual(lots(910005), [("CW-42", "handled")])
        self.assertEqual(lots(910007), [("CW-42", "handled")])
        self.assertEqual(self.call("/api/organizations/910001/lots")[1]["organization"]["name"], "Greenfield Farm")
        self.assertEqual(self.call("/api/organizations/99999999/lots")[0], 404)

    def test_seed_and_cross_factory_trace(self):
        self.assertEqual(self.call("/api/demo/seed", {})[0], 200)
        self.assertEqual(self.call("/api/demo/seed", {})[0], 200)
        _, first = self.call("/api/trace?batch_ids=910042")
        self.assertIn(910091, first["related"])
        self.assertTrue(all(b["synthetic"] for b in first["batches"]))
        self.assertIn(910017, first["related"])
        self.assertTrue(any(s["to_name"] == "Store JB-01" for s in first["shipments"]))
        _, both = self.call("/api/trace?batch_ids=910042&batch_ids=910091")
        self.assertEqual(both["source_ranking"][0]["batch_id"], 910102)
        self.assertEqual(both["source_ranking"][0]["flagged_product_count"], 2)
        self.assertEqual(both["source_ranking"][0]["matched_batch_ids"], [910042, 910091])
        self.assertEqual(self.call("/api/lots/resolve?lot_code=RM-402")[1]["batch_id"], 910402)
        self.assertEqual(self.call("/api/batches/910042/trace")[1]["upstream"], [910102, 910402])
        _, chicken = self.call("/api/trace?batch_ids=910402")
        self.assertEqual([b["product_name"] for b in chicken["batches"] if b["batch_id"] == 910402], ["Marinated chicken"])
        self.assertIn("SHIP-017", [s["shipment_code"] for s in chicken["shipments"]])
        self.assertEqual([lab["batch_id"] for lab in chicken["lab_results"]], [910042])
        self.assertEqual([lab["batch_id"] for lab in chicken["positive_elsewhere"]], [910091])  # salad: no chicken
        self.assertEqual(both["positive_elsewhere"], [])
        self.assertEqual(self.call("/api/trace?batch_ids=99999999")[0], 404)
        self.assertEqual(self.call("/api/trace")[0], 422)

    def test_containment_decision_is_recorded_and_survives_restart(self):
        self.assertEqual(self.call("/api/demo/seed", {})[0], 200)
        self.assertEqual(self.call("/api/trace?batch_ids=910042")[1]["containment"]["recommended"], "targeted")
        _, both = self.call("/api/trace?batch_ids=910042&batch_ids=910091")
        options = both["containment"]["options"]
        self.assertEqual(both["containment"]["recommended"], "extended")
        self.assertEqual(len(options["targeted"]["shipment_ids"]), 5)  # CW-42 and CS-91 movements only
        self.assertEqual(len(options["extended"]["shipment_ids"]), 9)  # plus lettuce, SHIP-017 and veggie-wrap movements
        _, analysis = self.upload("shipment_id,batch_id\nSHIP-017,RM-402\n")
        body = {"batch_ids": [910091, 910042], "scope": "extended", "decision": "approved",
                "officer": "Test Officer", "reason": "Shared lettuce lot", "analysis_id": analysis["analysis_id"]}
        code, made = self.call("/api/decisions", body)
        self.assertEqual(code, 201)
        self.assertEqual(made["shipment_ids"], options["extended"]["shipment_ids"])
        self.assertEqual(made["analysis_id"], analysis["analysis_id"])
        self.assertEqual(self.call("/api/decisions", {**body, "analysis_id": "analysis-missing"})[0], 404)
        self.assertEqual(self.call("/api/decisions", {**body, "officer": " "})[0], 422)
        self.assertEqual(self.call("/api/decisions", {**body, "scope": "everything"})[0], 422)
        self.assertEqual(self.call("/api/decisions", {**body, "batch_ids": [99999999]})[0], 404)
        type(self).stop()
        type(self).start()
        self.assertEqual(self.call("/api/trace?batch_ids=910042&batch_ids=910091")[1]["decisions"], [made])

    def test_write_validation_and_scoped_lots(self):
        for org in (501, 502):
            self.assertEqual(self.call("/api/organizations", {
                "organization_id": org, "name": f"Producer {org}", "type": "supplier"})[0], 201)
            self.assertEqual(self.call("/api/batches", {
                "batch_id": org, "organization_id": org, "product_name": "Test ingredient",
                "produced_at": "2026-10-17T00:00:00", "lot_code": "SHARED-CODE"})[0], 201)
        self.assertEqual(self.call("/api/lots/resolve?lot_code=SHARED-CODE")[0], 409)
        self.assertEqual(self.call("/api/lots/resolve?lot_code=SHARED-CODE&organization_id=502")[1]["batch_id"], 502)
        self.assertEqual(self.call("/api/batches", {
            "batch_id": 503, "organization_id": 501, "product_name": "Duplicate",
            "produced_at": "2026-10-17T00:00:00", "lot_code": "SHARED-CODE"})[0], 409)
        self.assertEqual(self.call("/api/batches", {
            "batch_id": 504, "organization_id": 9999999, "product_name": "Missing producer",
            "produced_at": "2026-10-17T00:00:00"})[0], 404)
        edge = {"parent_batch_id": 501, "child_batch_id": 502, "quantity_used": 1}
        self.assertEqual(self.call("/api/batch-relationships", edge)[0], 201)
        self.assertEqual(self.call("/api/batch-relationships", edge)[0], 409)
        self.assertEqual(self.call("/api/batch-relationships", {
            **edge, "parent_batch_id": 502, "child_batch_id": 501})[0], 400)
        self.assertEqual(self.call("/api/lab-results", {
            "batch_id": 999999, "tested_at": "2026-10-17T00:00:00", "result": "positive"})[0], 404)
        self.assertEqual(self.call("/api/sensor-readings", {
            "shipment_id": 999999, "timestamp": "2026-10-17T00:00:00", "temperature": 3})[0], 404)
        shipment = {"shipment_id": 501, "shipment_code": "TEST-SHIP", "batch_id": 501, "from_org_id": 501,
                    "to_org_id": 502, "quantity": 100, "quantity_unit": "kg"}
        self.assertEqual(self.call("/api/shipments", shipment)[0], 201)
        self.assertEqual(self.call("/api/shipments", shipment)[0], 409)
        self.assertEqual(self.call("/api/shipments", {**shipment, "shipment_id": 502, "batch_id": 999999})[0], 404)
        _, trace = self.call("/api/trace?batch_ids=501")
        self.assertEqual(trace["shipments"][0]["quantity_unit"], "kg")

    def test_seed_conflict_rolls_back_all_new_rows(self):
        from fastapi import HTTPException
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.database import Base
        from app.models import Batch, Organization
        from app.seed import seed_demo
        engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "conflict.db"))
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as db:
                db.add(Organization(organization_id=910009, name="Existing customer", type="store"))
                db.commit()
                with self.assertRaises(HTTPException) as error:
                    seed_demo(db)
                self.assertEqual(error.exception.status_code, 409)
                self.assertEqual(db.query(Organization).count(), 1)
                self.assertEqual(db.query(Organization).first().name, "Existing customer")
                self.assertEqual(db.query(Batch).count(), 0)
        finally:
            engine.dispose()

    def test_seed_upgrades_only_its_own_earlier_values(self):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session
        from app.database import Base
        from app.models import Batch, Organization
        from app.seed import seed_demo
        engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "legacy.db"))
        try:
            Base.metadata.create_all(engine)
            with Session(engine) as db:  # rows exactly as the first seed version wrote them
                db.add_all([Organization(organization_id=910002, name="Poultry Supplier", type="supplier"),
                            Organization(organization_id=910003, name="FreshBite Factory KL", type="factory")])
                db.flush()
                db.add(Batch(batch_id=910402, product_name="Chilled chicken", organization_id=910002,
                             produced_at=datetime(2026, 10, 17, 4), status="normal"))
                db.commit()
                seed_demo(db)
                self.assertEqual(db.get(Organization, 910002).name, "Food Processing")
                self.assertEqual(db.get(Organization, 910003).name, "Central Kitchen, QSR Group A")
                self.assertEqual(db.get(Batch, 910402).product_name, "Marinated chicken")
        finally:
            engine.dispose()

    def test_upload_survives_process_restart(self):
        code, result = self.upload("shipment_id,batch_id,temperature_c,reading_time\nS1,B1,12,2026-10-17T00:00:00Z\n")
        self.assertEqual(code, 201)
        path = f"/api/analyses/{result['analysis_id']}"
        before = self.call(path + "/findings")[1]
        network = self.call(path + "/distribution")[1]
        self.assertEqual(len(before["findings"]), 1)
        type(self).stop()
        type(self).start()
        self.assertEqual(self.call(path + "/findings"), (200, before))
        self.assertEqual(self.call(path + "/distribution"), (200, network))
        self.assertEqual(self.call("/api/analyses/missing/findings")[0], 404)


if __name__ == "__main__":
    unittest.main()
