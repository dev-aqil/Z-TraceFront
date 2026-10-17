"""HTTP integration checks against an isolated, foreign-key-enforced SQLite database."""

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
        self.assertEqual(self.call("/api/trace?batch_ids=99999999")[0], 404)
        self.assertEqual(self.call("/api/trace")[0], 422)

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

    def test_upload_survives_process_restart(self):
        boundary = "tracefront-test-boundary"
        raw = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sensor.csv\"\r\n"
               "Content-Type: text/csv\r\n\r\nshipment_id,batch_id,temperature_c,reading_time\n"
               f"S1,B1,12,2026-10-17T00:00:00Z\n\r\n--{boundary}--\r\n").encode()
        code, result = self.call("/api/analyses", raw=raw, content_type=f"multipart/form-data; boundary={boundary}")
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
