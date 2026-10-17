"""HTTP integration checks against an isolated, foreign-key-enforced SQLite database."""

from datetime import datetime
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

    def upload(self, csv_text):
        boundary = "tracefront-test-boundary"
        raw = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sensor.csv\"\r\n"
               f"Content-Type: text/csv\r\n\r\n{csv_text}\r\n--{boundary}--\r\n").encode()
        return self.call("/api/analyses", raw=raw, content_type=f"multipart/form-data; boundary={boundary}")

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
