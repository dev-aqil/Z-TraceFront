"""HTTP integration checks against an isolated, foreign-key-enforced SQLite database."""

import csv
from datetime import datetime
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PASSWORD = "correct horse battery"

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
        try:
            cls.add_user("officer@moh.test", "Test Officer", "regulator")
            cls.cookie = cls.sign_in("officer@moh.test")  # the default caller is a ministry officer
        except BaseException:  # tearDownClass does not run when setUpClass fails; do not leave the server behind
            cls.tearDownClass()
            raise

    @classmethod
    def database(cls):
        from sqlalchemy import create_engine
        return create_engine(cls.env["DATABASE_URL"])

    @classmethod
    def add_user(cls, email, name, role, organization_id=None):
        """Accounts are made on the server, never over HTTP, so write to the test database directly."""
        from sqlalchemy.orm import Session
        from app.auth import create_user
        engine = cls.database()
        try:
            with Session(engine) as db:
                create_user(db, email, name, PASSWORD, role, organization_id)
        finally:
            engine.dispose()

    @classmethod
    def sign_in(cls, email):
        req = Request(f"http://127.0.0.1:{cls.port}/api/auth/login", headers={"Content-Type": "application/json"},
                      data=json.dumps({"email": email, "password": PASSWORD}).encode())
        with urlopen(req, timeout=15) as response:
            return response.headers["Set-Cookie"].split(";")[0]

    def entered_by(self, kind, record_id):
        from sqlalchemy.orm import Session
        from app.models import Entry, User
        engine = self.database()
        try:
            with Session(engine) as db:
                return [email for (email,) in db.query(User.email).join(Entry, Entry.user_id == User.user_id)
                        .filter(Entry.kind == kind, Entry.record_id == str(record_id))]
        finally:
            engine.dispose()

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

    def call(self, path, body=None, *, raw=None, content_type="application/json", method=None, cookie=...):
        """`cookie` defaults to the ministry officer's session; pass None to call without one."""
        data = json.dumps(body).encode() if body is not None else raw
        cookie = self.cookie if cookie is ... else cookie
        req = Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method,
                      headers={"Content-Type": content_type, **({"Cookie": cookie} if cookie else {})})
        try:
            with urlopen(req, timeout=15) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def upload(self, csv_text, path="/api/analyses", cookie=...):
        boundary = "tracefront-test-boundary"
        raw = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"sensor.csv\"\r\n"
               f"Content-Type: text/csv\r\n\r\n{csv_text}\r\n--{boundary}--\r\n").encode()
        return self.call(path, raw=raw, content_type=f"multipart/form-data; boundary={boundary}", cookie=cookie)

    def import_records(self, rows, cookie=...):
        """Send trace records as one CSV whose columns are the union of the rows' keys."""
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=list(dict.fromkeys(key for row in rows for key in row)), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return self.upload(out.getvalue(), "/api/records/import", cookie)

    def test_every_route_needs_a_session(self):
        _, spec = self.call("/openapi.json", cookie=None)
        open_routes = {("/api/health", "get"), ("/api/auth/login", "post")}
        checked = 0
        for path, methods in spec["paths"].items():
            for method in methods:
                if (path, method) in open_routes:
                    continue
                code, _ = self.call(re.sub(r"\{[^}]+\}", "1", path), method=method.upper(), cookie=None)
                self.assertEqual(code, 401, f"{method.upper()} {path} answered without a session")
                checked += 1
        self.assertGreater(checked, 20)
        self.assertEqual(self.call("/api/health", cookie=None)[0], 200)
        self.assertEqual(self.call("/api/auth/me")[1]["role"], "regulator")

    def test_sign_in_rejects_wrong_passwords_then_locks_the_account(self):
        self.add_user("locked@moh.test", "Locked Officer", "regulator")

        def attempt(password, email="locked@moh.test"):
            return self.call("/api/auth/login", {"email": email, "password": password}, cookie=None)

        code, wrong = attempt("not the password")
        self.assertEqual(code, 401)
        self.assertEqual(attempt(PASSWORD, "nobody@moh.test"), (401, wrong))  # an unknown email looks the same
        for _ in range(4):
            attempt("not the password")
        self.assertEqual(attempt(PASSWORD), (401, wrong))  # five failures: locked, even with the right password

    def test_signing_out_ends_the_session(self):
        self.add_user("leaver@moh.test", "Leaving Officer", "regulator")
        cookie = self.sign_in("Leaver@MOH.test")  # the case of an email does not matter
        self.assertEqual(self.call("/api/auth/me", cookie=cookie)[1]["name"], "Leaving Officer")
        self.assertEqual(self.call("/api/auth/logout", method="POST", cookie=cookie)[0], 200)
        self.assertEqual(self.call("/api/auth/me", cookie=cookie)[0], 401)

    def test_a_company_sees_one_step_back_and_one_step_forward(self):
        self.assertEqual(self.call("/api/demo/seed", {})[0], 200)
        self.add_user("stock@warehouse-kl.test", "Warehouse Clerk", "company", 910005)
        self.add_user("qa@central-kitchen.test", "Kitchen QA", "company", 910003)
        warehouse, kitchen = self.sign_in("stock@warehouse-kl.test"), self.sign_in("qa@central-kitchen.test")
        self.assertEqual(self.call("/api/auth/me", cookie=warehouse)[1]["organization_name"], "Warehouse KL")
        self.assertEqual([b["lot_code"] for b in self.call("/api/trace/batches", cookie=warehouse)[1]], ["CW-42"])
        _, trace = self.call("/api/trace?batch_ids=910042", cookie=warehouse)
        self.assertEqual((trace["upstream"], trace["related"]), ([], []))  # what went into the wrap is the kitchen's record
        self.assertEqual({s["shipment_code"] for s in trace["shipments"]}, {"CW-WH", "CW-KL03", "CW-KL04"})
        partners = ["Central Kitchen, QSR Group A", "Warehouse KL", "Store KL-03", "Store KL-04"]
        self.assertEqual([org["name"] for org in trace["organizations"]], partners)
        self.assertEqual((trace["lab_results"], trace["positive_elsewhere"], trace["decisions"]), ([], [], []))
        self.assertEqual(self.call("/api/trace?batch_ids=910091", cookie=warehouse)[0], 404)  # a lot it never handled
        self.assertEqual(self.call("/api/lots/resolve?lot_code=L-102", cookie=warehouse)[0], 404)
        self.assertEqual(self.call("/api/organizations/910004/lots", cookie=warehouse)[0], 404)
        own_lots = self.call("/api/organizations/910005/lots", cookie=warehouse)[1]["lots"]
        self.assertEqual([lot["lot_code"] for lot in own_lots], ["CW-42"])
        self.assertEqual({org["name"] for org in self.call("/api/organizations", cookie=warehouse)[1]}, set(partners))
        self.assertEqual({s["shipment_code"] for s in self.call("/api/shipments", cookie=warehouse)[1]},
                         {"CW-WH", "CW-KL03", "CW-KL04"})
        self.assertEqual(self.call("/api/batch-relationships", cookie=warehouse)[1], [])
        _, own = self.call("/api/trace?batch_ids=910042", cookie=kitchen)
        self.assertEqual((own["upstream"], own["related"]), ([910102, 910402], []))  # its ingredients, not other factories' products
        self.assertEqual([lab["batch_id"] for lab in own["lab_results"]], [910042])  # results on the lot it made
        self.assertEqual(len(self.call("/api/batch-relationships", cookie=kitchen)[1]), 2)

    def test_a_company_cannot_do_what_only_the_ministry_does(self):
        self.assertEqual(self.call("/api/demo/seed", {})[0], 200)
        self.add_user("manager@store-kl03.test", "Store Manager", "company", 910007)
        store = self.sign_in("manager@store-kl03.test")
        decision = {"batch_ids": [910042], "scope": "targeted", "decision": "approved", "reason": "Test"}
        organization = {"organization_id": 880001, "name": "Self-made Regulator", "type": "store"}
        for path, body in (("/api/demo/seed", {}), ("/api/decisions", decision), ("/api/organizations", organization)):
            self.assertEqual(self.call(path, body, cookie=store)[0], 403, path)

    def test_a_company_writes_only_records_it_is_party_to(self):
        wheat = {"record": "lot", "producer": "Party Farm", "lot_code": "PF-1", "product": "Wheat", "produced_at": "2026-11-01"}
        ship = {"record": "shipment", "shipment_code": "PT-1", "quantity": "5", "unit": "kg", "status": "delivered"}
        code, _ = self.import_records([  # the ministry sets up three companies and a delivery of wheat to the mill
            {"record": "organization", "name": "Party Farm", "type": "supplier"},
            {"record": "organization", "name": "Party Mill", "type": "factory"},
            {"record": "organization", "name": "Party Bakery", "type": "factory"},
            wheat,
            {"record": "lot", "producer": "Party Mill", "lot_code": "PM-1", "product": "Flour", "produced_at": "2026-11-02"},
            {"record": "lot", "producer": "Party Bakery", "lot_code": "PB-1", "product": "Bread", "produced_at": "2026-11-03"},
            {**ship, "lot_code": "PF-1", "from": "Party Farm", "to": "Party Mill"}])
        self.assertEqual(code, 200)
        ids = {org["name"]: org["organization_id"] for org in self.call("/api/organizations")[1]}
        self.add_user("qa@party-mill.test", "Mill QA", "company", ids["Party Mill"])
        mill = self.sign_in("qa@party-mill.test")

        def refused(rows, reason):
            code, body = self.import_records(rows, cookie=mill)
            self.assertEqual(code, 400, body)
            self.assertIn(reason, body["detail"])

        refused([{**ship, "shipment_code": "PT-2", "lot_code": "PM-1", "from": "Party Bakery", "to": "Party Farm"}],
                "your own organization sent or received")
        refused([{"record": "ingredient", "lot_code": "PF-1", "ingredient_lot_code": "PM-1", "quantity": "1"}],
                "lots your own organization made")
        # A lot it never handled cannot be referred to: it looks the same as a lot that does not exist.
        refused([{**ship, "shipment_code": "PT-3", "lot_code": "PB-1", "from": "Party Mill", "to": "Party Bakery"}],
                "unknown lot 'PB-1'")
        barley = {**wheat, "lot_code": "PF-9", "product": "Barley"}
        refused([barley], "belongs to another company")  # nothing ties it to the mill
        code, ok = self.import_records([  # the same lot with its delivery to the mill, and the mill's own lot made from it
            barley, {**ship, "shipment_code": "PT-4", "lot_code": "PF-9", "from": "Party Farm", "to": "Party Mill"},
            {"record": "lot", "producer": "Party Mill", "lot_code": "PM-2", "product": "Barley flour", "produced_at": "2026-11-06"},
            {"record": "ingredient", "lot_code": "PM-2", "ingredient_lot_code": "PF-9", "quantity": "3"}], cookie=mill)
        self.assertEqual((code, ok.get("created")), (200, {"organizations": 0, "lots": 2, "ingredients": 1, "shipments": 1}), ok)
        barley_id = self.call("/api/lots/resolve?lot_code=PF-9")[1]["batch_id"]
        self.assertEqual(self.entered_by("batches", barley_id), ["qa@party-mill.test"])  # the record shows who declared it
        # Single-record writes follow the same rule.
        batch = {"batch_id": 770001, "product_name": "Flour", "produced_at": "2026-11-07T00:00:00", "lot_code": "PM-3"}
        self.assertEqual(self.call("/api/batches", {**batch, "organization_id": ids["Party Bakery"]}, cookie=mill)[0], 403)
        self.assertEqual(self.call("/api/batches", {**batch, "organization_id": ids["Party Mill"]}, cookie=mill)[0], 201)
        bread = self.call("/api/lots/resolve?lot_code=PB-1")[1]["batch_id"]
        lab = {"tested_at": "2026-11-07T00:00:00", "contaminant": "Salmonella", "result": "negative"}
        self.assertEqual(self.call("/api/lab-results", {**lab, "batch_id": bread}, cookie=mill)[0], 403)
        self.assertEqual(self.call("/api/lab-results", {**lab, "batch_id": 770001}, cookie=mill)[0], 200)
        movement = {"shipment_id": 770001, "shipment_code": "PT-5", "from_org_id": ids["Party Mill"],
                    "to_org_id": ids["Party Bakery"], "quantity": 1, "quantity_unit": "kg"}
        self.assertEqual(self.call("/api/shipments", {**movement, "batch_id": bread}, cookie=mill)[0], 404)
        self.assertEqual(self.call("/api/shipments", {**movement, "batch_id": 770001}, cookie=mill)[0], 201)

    def test_an_upload_analysis_is_private_to_the_company_that_made_it(self):
        self.assertEqual(self.call("/api/demo/seed", {})[0], 200)
        self.add_user("uploads@store-kl04.test", "Store Uploader", "company", 910008)
        self.add_user("other@store-jb01.test", "Other Store", "company", 910009)
        owner, other = self.sign_in("uploads@store-kl04.test"), self.sign_in("other@store-jb01.test")
        code, made = self.upload("shipment_id,batch_id\nS1,B1\n", cookie=owner)
        self.assertEqual(code, 201, made)
        for part in ("findings", "distribution"):
            path = f"/api/analyses/{made['analysis_id']}/{part}"
            self.assertEqual([self.call(path, cookie=who)[0] for who in (owner, other, self.cookie)], [200, 404, 200])

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

        self.assertEqual(holding("Warehouse KL", 910042), {"batch_id": 910042, "unit": "units", "received": 1200, "incoming": 0,
                                                           "sent": 700, "used": 0, "remaining": 500, "used_in": []})
        self.assertEqual((holding("Store KL-03", 910042)["received"], holding("Store KL-03", 910042)["incoming"]), (0, 400))
        self.assertEqual(holding("Store KL-04", 910042)["remaining"], 300)
        kitchen = orgs["Central Kitchen, QSR Group A"]
        self.assertEqual((kitchen["type"], kitchen["produced_batch_ids"]), ("factory", [910042]))
        # Production quantity is not recorded, so nothing can be said about what the maker still has.
        self.assertEqual((holding(kitchen["name"], 910042)["sent"], holding(kitchen["name"], 910042)["remaining"]), (1200, None))
        lettuce = holding(kitchen["name"], 910102)
        self.assertEqual((lettuce["received"], lettuce["unit"], lettuce["used_in"]), (10, "kg", [910042]))
        self.assertEqual((lettuce["used"], lettuce["remaining"]), (10, 0))  # all of it went into the wrap
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

    def test_an_approved_hold_reaches_each_affected_site_until_it_is_lifted(self):
        code, _ = self.import_records([
            {"record": "organization", "name": "Hold Farm", "type": "supplier"},
            {"record": "organization", "name": "Hold Shop", "type": "store"},
            {"record": "organization", "name": "Hold Bystander", "type": "store"},
            {"record": "lot", "producer": "Hold Farm", "lot_code": "HF-1", "product": "Sprouts", "produced_at": "2026-11-10"},
            {"record": "shipment", "shipment_code": "HF-S1", "lot_code": "HF-1", "from": "Hold Farm", "to": "Hold Shop",
             "quantity": "40", "unit": "kg", "status": "delivered"}])
        self.assertEqual(code, 200)
        ids = {org["name"]: org["organization_id"] for org in self.call("/api/organizations")[1]}
        users = {"Hold Farm": "farm@hold.test", "Hold Shop": "shop@hold.test", "Hold Bystander": "bystander@hold.test"}
        for name, email in users.items():
            self.add_user(email, f"{name} user", "company", ids[name])
        farm, shop, bystander = (self.sign_in(email) for email in users.values())
        lot = self.call("/api/lots/resolve?lot_code=HF-1")[1]
        self.assertFalse(lot["on_hold"])
        body = {"batch_ids": [lot["batch_id"]], "scope": "targeted", "decision": "approved", "reason": "Positive sample"}
        hold = self.call("/api/decisions", body)[1]["decision_id"]
        rejected = self.call("/api/decisions", {**body, "decision": "rejected"})[1]["decision_id"]

        def holds(cookie=...):
            return {h["decision_id"]: h for h in self.call("/api/holds", cookie=cookie)[1]}

        self.assertNotIn(rejected, holds())  # a rejected recommendation holds nothing
        self.assertEqual([(site["name"], site["acknowledged_at"]) for site in holds()[hold]["sites"]],
                         [("Hold Farm", None), ("Hold Shop", None)])
        mine = holds(shop)[hold]
        self.assertEqual(([b["lot_code"] for b in mine["lots"]], mine["reason"], mine["released"]), (["HF-1"], "Positive sample", None))
        self.assertEqual([site["name"] for site in mine["sites"]], ["Hold Shop"])  # a company is not shown who else is affected
        self.assertTrue(self.call("/api/trace/batches", cookie=shop)[1][0]["on_hold"])
        self.assertTrue(self.call(f"/api/trace?batch_ids={lot['batch_id']}", cookie=shop)[1]["shipments"][0]["on_hold"])
        self.assertEqual(holds(bystander), {})
        acknowledge = f"/api/holds/{hold}/acknowledge"
        self.assertEqual(self.call(acknowledge, method="POST", cookie=bystander)[0], 404)
        self.assertEqual(self.call(acknowledge, method="POST")[0], 403)  # the ministry does not acknowledge its own hold
        code, done = self.call(acknowledge, method="POST", cookie=shop)
        self.assertEqual(code, 200, done)
        self.assertEqual(self.call(acknowledge, method="POST", cookie=shop)[1], done)  # acknowledging twice changes nothing
        self.assertEqual([(site["name"], bool(site["acknowledged_at"]), site["acknowledged_by"]) for site in holds()[hold]["sites"]],
                         [("Hold Farm", False, None), ("Hold Shop", True, "Hold Shop user")])
        lift = f"/api/holds/{hold}/release"
        self.assertEqual(self.call(lift, {"reason": "Retest negative"}, cookie=farm)[0], 403)
        self.assertEqual(self.call(f"/api/holds/{rejected}/release", {"reason": "Not a hold"})[0], 409)
        self.assertEqual(self.call(lift, {"reason": " "})[0], 422)
        code, lifted = self.call(lift, {"reason": "Retest negative"})
        self.assertEqual((code, lifted["released"]["reason"], lifted["released"]["officer"]), (200, "Retest negative", "Test Officer"))
        self.assertEqual(self.call(lift, {"reason": "Again"})[0], 409)
        self.assertEqual(holds(farm)[hold]["released"]["reason"], "Retest negative")  # each site is told it was lifted
        self.assertFalse(self.call("/api/lots/resolve?lot_code=HF-1")[1]["on_hold"])
        self.assertEqual(self.call(acknowledge, method="POST", cookie=farm)[0], 409)  # nothing is left to acknowledge

    def test_contact_details_come_with_an_organization_and_only_it_or_the_ministry_changes_them(self):
        org = {"record": "organization", "name": "Contact Dairy", "type": "factory", "registration_no": "MOH-PRM-0042",
               "address": "Lot 5, Jalan Susu, Kluang", "contact_name": "Nur Aina", "email": "qa@contact-dairy.test",
               "phone": "07-555 0100"}
        code, made = self.import_records([org, {"record": "organization", "name": "Contact Rival", "type": "factory"}])
        self.assertEqual((code, made["created"]["organizations"]), (200, 2), made)

        def stored():
            return next(o for o in self.call("/api/organizations")[1] if o["name"] == "Contact Dairy")

        dairy = stored()
        self.assertEqual((dairy["registration_no"], dairy["address"], dairy["contact_name"], dairy["contact_email"], dairy["contact_phone"]),
                         ("MOH-PRM-0042", "Lot 5, Jalan Susu, Kluang", "Nur Aina", "qa@contact-dairy.test", "07-555 0100"))
        rival_id = next(o["organization_id"] for o in self.call("/api/organizations")[1] if o["name"] == "Contact Rival")
        self.add_user("qa@contact-dairy.test", "Nur Aina", "company", dairy["organization_id"])
        self.add_user("qa@contact-rival.test", "Rival QA", "company", rival_id)
        own, rival = self.sign_in("qa@contact-dairy.test"), self.sign_in("qa@contact-rival.test")
        code, ignored = self.import_records([{**org, "phone": "000"}], cookie=rival)
        self.assertEqual((code, ignored["contacts_updated"], stored()["contact_phone"]), (200, 0, "07-555 0100"))  # not its organization
        code, changed = self.import_records([{**org, "phone": "07-555 0199"}], cookie=own)
        self.assertEqual((code, changed["contacts_updated"], stored()["contact_phone"]), (200, 1, "07-555 0199"))
        self.assertEqual(self.import_records([{**org, "email": "not-an-email"}], cookie=own)[0], 400)

    def test_records_that_contradict_the_calendar_are_refused(self):
        base = [{"record": "organization", "name": "Clock Factory", "type": "factory"},
                {"record": "organization", "name": "Clock Shop", "type": "store"},
                {"record": "lot", "producer": "Clock Factory", "lot_code": "CK-OLD", "product": "Jam", "produced_at": "2026-11-01"},
                {"record": "lot", "producer": "Clock Factory", "lot_code": "CK-NEW", "product": "Fruit", "produced_at": "2026-11-05"}]
        code, late = self.import_records(base + [
            {"record": "ingredient", "lot_code": "CK-OLD", "ingredient_lot_code": "CK-NEW", "quantity": "1", "unit": "kg"}])
        self.assertEqual(code, 400, late)
        self.assertIn("row 5: ", late["detail"])
        self.assertIn("produced after", late["detail"])
        code, early = self.import_records(base + [
            {"record": "shipment", "shipment_code": "CK-S1", "lot_code": "CK-NEW", "from": "Clock Factory", "to": "Clock Shop",
             "quantity": "1", "unit": "kg", "status": "delivered", "departed_at": "2026-11-04"}])
        self.assertEqual(code, 400, early)
        self.assertIn("before the lot was produced", early["detail"])
        self.assertEqual(self.import_records(base)[0], 200)
        old, new = (self.call(f"/api/lots/resolve?lot_code={code}")[1]["batch_id"] for code in ("CK-OLD", "CK-NEW"))
        link = {"parent_batch_id": new, "child_batch_id": old, "quantity_used": 1, "quantity_unit": "kg"}
        self.assertEqual(self.call("/api/batch-relationships", link)[0], 400)  # the single-record route checks it too
        code, forward = self.call("/api/batch-relationships", {**link, "parent_batch_id": old, "child_batch_id": new})
        self.assertEqual((code, forward["quantity_unit"]), (201, "kg"))

    def test_new_columns_are_added_to_tables_that_already_exist(self):
        from sqlalchemy import create_engine, inspect, text
        import app.models  # noqa: F401  (registers the tables)
        from app.database import add_missing_columns
        engine = create_engine("sqlite:///" + str(Path(self.temp.name) / "old-schema.db"))
        try:
            with engine.begin() as db:  # the organizations table as the first release created it
                db.execute(text("CREATE TABLE organizations (organization_id INTEGER PRIMARY KEY, "
                                "name VARCHAR NOT NULL, type VARCHAR NOT NULL)"))
                db.execute(text("INSERT INTO organizations VALUES (1, 'Old Farm', 'supplier')"))
            add_missing_columns(engine)
            add_missing_columns(engine)  # running it again changes nothing
            self.assertIn("contact_phone", {column["name"] for column in inspect(engine).get_columns("organizations")})
            with engine.connect() as db:
                rows = db.execute(text("SELECT name, contact_phone FROM organizations")).all()
            self.assertEqual([tuple(row) for row in rows], [("Old Farm", None)])
        finally:
            engine.dispose()

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
                "officer": "Someone Else", "reason": "Shared lettuce lot", "analysis_id": analysis["analysis_id"]}
        code, made = self.call("/api/decisions", body)
        self.assertEqual(code, 201)
        self.assertEqual(made["shipment_ids"], options["extended"]["shipment_ids"])
        self.assertEqual(made["analysis_id"], analysis["analysis_id"])
        self.assertEqual(made["officer"], "Test Officer")  # the signed-in officer, whatever name the request carried
        self.assertEqual(self.call("/api/decisions", {**body, "analysis_id": "analysis-missing"})[0], 404)
        self.assertEqual(self.call("/api/decisions", {**body, "reason": " "})[0], 422)
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
