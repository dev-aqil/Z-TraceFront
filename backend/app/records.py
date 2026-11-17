"""Bulk import of trace records, so each organization can load what it made, used and shipped in one file.

One row per record. The `record` column names its kind, which decides the other columns that are read:

  organization  name, type (supplier | factory | warehouse | store)
                [registration_no, address, contact_name, email, phone]
  lot           producer, lot_code, product, produced_at
  ingredient    lot_code [producer], ingredient_lot_code [ingredient_producer], quantity [unit]
  shipment      shipment_code, lot_code [producer], from, to, quantity, unit, status [departed_at, eta, profile]

A shipment's profile is its cold-chain limit (food-risk-ml configs/cold_chain_rules.toml, e.g. poultry_chilled or
frozen); without one, live sensor readings are checked against the FDA Food Code 5 °C limit.

Organizations are matched by name (ignoring case), lots by producer and lot code, shipments by sender and shipment
code. A row whose record is already stored is counted as existing and left unchanged, so the same file can be sent
twice and two organizations can describe the same lot. The one exception is an organization's contact details, which
the organization itself or the ministry can change by sending its row again. Row order does not matter. Any problem
rejects the whole file. An ingredient lot must not be newer than the lot it went into, and a shipment must not leave
before its lot was produced. Give ingredient quantities the same unit as the shipments, or they cannot be subtracted
from what a site still holds.
A producer column may be left out when the lot code belongs to one producer only. Dates are ISO (YYYY-MM-DD or
YYYY-MM-DD HH:MM): 01/11/2026 is refused rather than guessed as January or November.

A regulator may import anything. A company user may import only records its own organization is a party to:
lots it made, ingredients of those lots, and shipments it sent or received. It may also declare another company's
lot (the one step back the law asks it to record), but only together with a shipment or ingredient row that ties
the lot to it. Rows can refer only to lots the company can already see or that the file itself declares, so a file
cannot be used to find out which lots other companies hold.
"""

import math
from datetime import datetime, timezone
from itertools import count
from typing import get_args

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.analysis import MAX_UPLOAD_BYTES, RULES, read_frame, text
from app.auth import current_user, log_entry, scope
from app.database import get_db
from app.graph import build_batch_graph, creates_cycle
from app.models import Batch, BatchLot, BatchRelationship, Organization, Shipment, ShipmentManifest, User
from app.schemas import OrganizationContact, OrganizationType, ShipmentStatus

router = APIRouter(prefix="/api/records", dependencies=[Depends(current_user)])

MAX_PROBLEMS = 20  # listed in one error message
# Optional columns on an organization row -> the stored contact field.
CONTACT_COLUMNS = {"registration_no": "registration_no", "address": "address", "contact_name": "contact_name",
                   "email": "contact_email", "phone": "contact_phone"}


class RowError(Exception):
    pass


def need(row: dict, field: str) -> str:
    if row.get(field) is None:
        raise RowError(f"{field} is empty")
    return row[field]


def choice(row: dict, field: str, allowed: tuple) -> str:
    value = need(row, field).lower()
    if value not in allowed:
        raise RowError(f"{field} {row[field]!r} is not one of {', '.join(allowed)}")
    return value


def amount(row: dict) -> float:
    value = need(row, "quantity")
    try:
        number = float(value)
    except ValueError:
        number = math.nan
    if not (math.isfinite(number) and number > 0):
        raise RowError(f"quantity {value!r} is not a positive number")
    return number


def when(row: dict, field: str) -> datetime | None:
    value = row.get(field)
    if value is None:
        return None
    try:
        at = datetime.fromisoformat(value)
    except ValueError:
        raise RowError(f"{field} {value!r} is not a date; write it as YYYY-MM-DD or YYYY-MM-DD HH:MM") from None
    return at.astimezone(timezone.utc).replace(tzinfo=None) if at.tzinfo else at  # the tables store no time zone


@router.post("/import")
def import_records(file: UploadFile, user: User = Depends(current_user), db: Session = Depends(get_db)):
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file is larger than 10 MB")
    df = read_frame(file.filename or "upload", raw, aliases={})
    if "record" not in df:
        raise HTTPException(400, "missing column: record (organization, lot, ingredient or shipment)")
    rows = [(n, row) for n, row in enumerate(({k: text(v) for k, v in r.items()} for r in df.to_dict("records")), 1)
            if any(v is not None for v in row.values())]  # spreadsheets often end with blank rows
    if not rows:
        raise HTTPException(400, "the file has no rows")

    # ponytail: every organization, lot and shipment code is loaded per import, and new IDs are max + 1, so two
    # imports at the same moment can collide (409, send again). Query per row and use sequences when that hurts.
    orgs: dict[str, list[int]] = {}
    for org in db.query(Organization):
        orgs.setdefault(org.name.casefold(), []).append(org.organization_id)
    lots: dict[str, dict[int, int]] = {}  # lot code -> producer -> batch
    for lot in db.query(BatchLot):
        lots.setdefault(lot.lot_code, {})[lot.organization_id] = lot.batch_id
    manifests = {(m.from_org_id, m.shipment_code): m.shipment_id for m in db.query(ShipmentManifest)}
    maker = {batch: producer for producers in lots.values() for producer, batch in producers.items()}
    made_at = dict(db.query(Batch.batch_id, Batch.produced_at).all())
    contacts_updated: set[int] = set()
    graph = build_batch_graph(db)
    ids = {model: count((db.query(func.max(key)).scalar() or 0) + 1) for model, key in
           ((Organization, Organization.organization_id), (Batch, Batch.batch_id), (Shipment, Shipment.shipment_id))}
    company = user.role != "regulator"
    visible = scope(db, user)  # the lots a company's rows may refer to (None: any); its own lot rows add to it
    untied: dict[int, int] = {}  # another company's lot created by this file -> its row, until a row ties it to the importer

    def add(record, logged=False):
        db.add(record)
        db.flush()  # parents must exist before the rows that reference them
        if logged:
            log_entry(db, user, record)

    def org_id(row, field):
        name = need(row, field)
        found = orgs.get(name.casefold(), [])
        if len(found) != 1:
            raise RowError(f"unknown organization {name!r}; add an organization row for it" if not found else
                           f"{len(found)} stored organizations are named {name!r}; rename one before importing")
        return found[0]

    def batch_id(row, code_field="lot_code", producer_field="producer"):
        code = need(row, code_field)
        producers = lots.get(code, {})
        if row.get(producer_field):
            producer = org_id(row, producer_field)
            found = [producers[producer]] if producer in producers else []
        else:
            found = list(producers.values())
        if visible is not None:  # a lot the company cannot see is reported exactly like one that does not exist
            found = [batch for batch in found if batch in visible]
        if len(found) != 1:
            raise RowError(f"unknown lot {code!r}; add a lot row for it" if not found else
                           f"lot code {code!r} belongs to {len(found)} producers; fill in {producer_field}")
        return found[0]

    # Each handler takes a row and its number, and returns True when it stored a new record, False when it was there.
    def organization(row, n):
        name, kind = need(row, "name"), choice(row, "type", get_args(OrganizationType))
        details = {field: row[column] for column, field in CONTACT_COLUMNS.items() if row.get(column) is not None}
        try:
            OrganizationContact(**details)
        except ValidationError as error:
            column = next(c for c, field in CONTACT_COLUMNS.items() if field == error.errors()[0]["loc"][0])
            raise RowError(f"{column} {row[column]!r} is not valid") from None
        stored = orgs.get(name.casefold())
        if stored is None:
            new = Organization(organization_id=next(ids[Organization]), name=name, type=kind, **details)
            add(new, logged=True)
            orgs[name.casefold()] = [new.organization_id]
            return True
        # Contact details are the one thing an import changes on a stored record, and only the organization itself
        # or the ministry may change them. Anyone else's values are ignored.
        if details and len(stored) == 1 and (not company or stored[0] == user.organization_id):
            org = db.get(Organization, stored[0])
            changed = {field: value for field, value in details.items() if getattr(org, field) != value}
            for field, value in changed.items():
                setattr(org, field, value)
            if changed:
                log_entry(db, user, org)
                contacts_updated.add(org.organization_id)
        return False

    def lot_row(row, n):
        producer, code, product = org_id(row, "producer"), need(row, "lot_code"), need(row, "product")
        need(row, "produced_at")
        made = when(row, "produced_at")
        stored = lots.get(code, {}).get(producer)
        if stored is None:
            batch = Batch(batch_id=next(ids[Batch]), product_name=product, organization_id=producer,
                          produced_at=made, status="normal")
            add(batch, logged=True)
            add(BatchLot(batch_id=batch.batch_id, organization_id=producer, lot_code=code))
            lots.setdefault(code, {})[producer] = batch.batch_id
            maker[batch.batch_id], made_at[batch.batch_id] = producer, made
            if company and producer != user.organization_id:
                untied[batch.batch_id] = n
        if visible is not None:
            visible.add(lots[code][producer])  # named with its producer and code, so later rows may refer to it
        return stored is None

    def ingredient(row, n):
        child, parent = batch_id(row), batch_id(row, "ingredient_lot_code", "ingredient_producer")
        used = amount(row)
        if company and maker[child] != user.organization_id:
            raise RowError("you can record ingredients only for lots your own organization made")
        untied.pop(parent, None)
        if graph.has_edge(parent, child):
            return False
        if creates_cycle(graph, parent, child):
            raise RowError("this link would create a cycle: a lot cannot be an ingredient of itself or of its own ingredients")
        if made_at[parent] > made_at[child]:
            raise RowError("the ingredient lot was produced after the lot it is said to be in")
        graph.add_edge(parent, child)
        add(BatchRelationship(parent_batch_id=parent, child_batch_id=child, quantity_used=used,
                              quantity_unit=row.get("unit")), logged=True)
        return True

    def shipment(row, n):
        code, batch = need(row, "shipment_code"), batch_id(row)
        sender, receiver = org_id(row, "from"), org_id(row, "to")
        quantity, unit, status = amount(row), need(row, "unit"), choice(row, "status", get_args(ShipmentStatus))
        departed, eta = when(row, "departed_at"), when(row, "eta")
        profile = choice(row, "profile", tuple(RULES["profiles"])) if row.get("profile") is not None else None
        if sender == receiver:
            raise RowError("from and to are the same organization")
        if company and user.organization_id not in (sender, receiver):
            raise RowError("you can record only shipments your own organization sent or received")
        if departed is not None and departed < made_at[batch]:
            raise RowError("departed_at is before the lot was produced")
        untied.pop(batch, None)
        stored = manifests.get((sender, code))
        if stored is not None:
            if db.get(Shipment, stored).batch_id != batch:
                # ponytail: one lot per shipment code; mixed loads need a shipment-lot link table
                raise RowError(f"shipment {code!r} from this sender already carries another lot. There is one lot per "
                               f"shipment code, so number the lots ({code}-A, {code}-B)")
            return False
        ship = Shipment(shipment_id=next(ids[Shipment]), batch_id=batch, from_org_id=sender, to_org_id=receiver,
                        quantity=quantity, status=status, departed_at=departed, eta=eta)
        add(ship, logged=True)
        add(ShipmentManifest(shipment_id=ship.shipment_id, from_org_id=sender, shipment_code=code, quantity_unit=unit,
                             cold_chain_profile=profile))
        manifests[(sender, code)] = ship.shipment_id
        return True

    # In this order, so a row can refer to an organization or lot declared anywhere in the file.
    handlers = {"organization": organization, "lot": lot_row, "ingredient": ingredient, "shipment": shipment}
    names = {"organization": "organizations", "lot": "lots", "ingredient": "ingredients", "shipment": "shipments"}
    created, existing, problems = dict.fromkeys(names.values(), 0), dict.fromkeys(names.values(), 0), []
    kinds = {n: (row.get("record") or "").lower().replace("organisation", "organization") for n, row in rows}
    problems +=[(n, f"record {row.get('record')!r} is not one of {', '.join(handlers)}")
                 for n, row in rows if kinds[n] not in handlers]
    try:
        for kind, handle in handlers.items():
            for n, row in rows:
                if kinds[n] != kind:
                    continue
                try:
                    (created if handle(row, n) else existing)[names[kind]] += 1
                except RowError as error:
                    problems.append((n, str(error)))
        problems += [(n, "this lot belongs to another company. You can add it only with a shipment to or from your "
                         "organization, or as an ingredient of one of your own lots, in the same file")
                     for n in untied.values()]
        if problems:
            problems.sort()
            more = f"; and {len(problems) - MAX_PROBLEMS} more" if len(problems) > MAX_PROBLEMS else ""
            raise HTTPException(400, f"nothing was imported; {len(problems)} row(s) need fixing: "
                                + "; ".join(f"row {n}: {message}" for n, message in problems[:MAX_PROBLEMS]) + more)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "the import conflicts with records stored at the same moment; nothing was imported, "
                                 "send the file again") from error
    return {"rows": len(rows), "created": created, "existing": existing, "contacts_updated": len(contacts_updated)}
