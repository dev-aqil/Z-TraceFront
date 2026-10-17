"""Add a deterministic synthetic incident. Existing records are never deleted, and never changed unless they still hold
an earlier version of this scenario's own values (LEGACY)."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.database import Base, SessionLocal, engine
from app.models import Batch, BatchLot, BatchRelationship, LabResult, Organization, Shipment, ShipmentManifest, SyntheticBatch

WRAP, SALAD, LETTUCE = 910042, 910091, 910102
# Values written by earlier versions of this seed. Only these exact values are upgraded; anything else is a conflict.
# v2 renamed them to match the bundled supplier_shipments.csv, so an uploaded RM-402 finding lands on the same lot.
LEGACY = {("organizations", 910002): {"name": "Poultry Supplier"},
          ("organizations", 910003): {"name": "FreshBite Factory KL"},
          ("batches", 910402): {"product_name": "Chilled chicken"}}


def seed_demo(db):
    def ensure(model, key, **values):
        existing = db.get(model, key)
        if existing:
            differs = {name: value for name, value in values.items() if getattr(existing, name) != value}
            old = LEGACY.get((model.__tablename__, key), {})
            if any(name not in old or getattr(existing, name) != old[name] for name in differs):
                raise HTTPException(409, f"demo ID conflicts with existing {model.__tablename__} record {key}; nothing was changed")
            for name, value in differs.items():
                setattr(existing, name, value)
            return
        primary = next(iter(model.__table__.primary_key)).name
        db.add(model(**{primary: key, **values}))
        db.flush()

    try:
        for id_, name, kind in [
            (910001, "Greenfield Farm", "supplier"), (910002, "Food Processing", "supplier"),
            (910003, "Central Kitchen, QSR Group A", "factory"), (910004, "FreshBite Factory JB", "factory"),
            (910005, "Warehouse KL", "warehouse"), (910006, "Warehouse JB", "warehouse"),
            (910007, "Store KL-03", "store"), (910008, "Store KL-04", "store"),
            (910009, "Store JB-01", "store"),
        ]:
            ensure(Organization, id_, name=name, type=kind)
        for id_, code, product, org in [
            (LETTUCE, "L-102", "Lettuce", 910001), (910402, "RM-402", "Marinated chicken", 910002),
            (WRAP, "CW-42", "Chicken wrap", 910003), (SALAD, "CS-91", "Caesar salad", 910004),
            (910017, "VW-17", "Veggie wrap", 910004),
        ]:
            ensure(Batch, id_, product_name=product, organization_id=org,
                   produced_at=datetime(2026, 10, 17, 4), status="normal")
            ensure(BatchLot, id_, organization_id=org, lot_code=code)
            ensure(SyntheticBatch, id_, scenario="shared-ingredient-v1")
        for index, (parent, child, quantity) in enumerate([
            (LETTUCE, WRAP, 10.0), (LETTUCE, SALAD, 15.0), (LETTUCE, 910017, 8.0), (910402, WRAP, 20.0),
        ], 910001):
            ensure(BatchRelationship, index, parent_batch_id=parent, child_batch_id=child, quantity_used=quantity)
        # Ingredient transport to both factories, followed by product transport to warehouses and stores.
        for index, (batch, from_, to, quantity, status, code, unit) in enumerate([
            (LETTUCE, 910001, 910003, 10, "delivered", "T17-KL", "kg"),
            (LETTUCE, 910001, 910004, 23, "delivered", "T18-JB", "kg"),
            (WRAP, 910003, 910005, 1200, "delivered", "CW-WH", "units"),
            (SALAD, 910004, 910006, 900, "delivered", "CS-WH", "units"),
            (WRAP, 910005, 910007, 400, "in_transit", "CW-KL03", "units"),
            (WRAP, 910005, 910008, 300, "delivered", "CW-KL04", "units"),
            (SALAD, 910006, 910009, 250, "in_transit", "CS-JB01", "units"),
            (910017, 910004, 910006, 600, "pending", "VW-WH", "units"),
            (910402, 910002, 910003, 20, "delivered", "SHIP-017", "kg"),  # the excursion shipment in supplier_shipments.csv
        ], 910001):
            ensure(Shipment, index, batch_id=batch, from_org_id=from_, to_org_id=to, quantity=float(quantity),
                   status=status, departed_at=datetime(2026, 10, 17, 6) if status != "pending" else None,
                   eta=datetime(2026, 10, 17, 9))
            ensure(ShipmentManifest, index, from_org_id=from_, shipment_code=code, quantity_unit=unit)
        # The salad has no chicken, so its positive points past the RM-402 excursion to the shared lettuce lot.
        for id_, batch, hour in [(910001, WRAP, 8), (910002, SALAD, 10)]:
            ensure(LabResult, id_, batch_id=batch, tested_at=datetime(2026, 10, 17, hour),
                   contaminant="Salmonella (simulated)", result="positive")
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "demo conflicts with existing data; nothing was changed") from error
    return {"synthetic": True, "selected_batch_ids": [WRAP], "second_batch_id": SALAD,
            "shared_ingredient_id": LETTUCE, "message": "Synthetic scenario loaded; existing records were preserved."}


if __name__ == "__main__":
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        print(seed_demo(session))
