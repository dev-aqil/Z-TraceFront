"""Generate fictional food supply-chain records for pre-event exploration only.

This is preparation data, not Datathon submission code or a validated safety model.
Run with Python 3.10+ from any working directory.
"""

import csv
import random
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


SEED = 20261017
OUT = Path(__file__).resolve().parent / "synthetic-practice"
RNG = random.Random(SEED)
START = datetime(2024, 1, 1)
END = datetime(2025, 12, 31)
STATES = ["Johor", "Kedah", "Kelantan", "Melaka", "Negeri Sembilan", "Pahang",
          "Perak", "Perlis", "Pulau Pinang", "Sabah", "Sarawak", "Selangor",
          "Terengganu", "Kuala Lumpur"]
INGREDIENTS = [
    "lettuce", "spinach", "cabbage", "carrot", "tomato", "cucumber", "onion", "chilli",
    "potato", "mushroom", "chicken", "beef", "fish", "shrimp", "egg", "milk",
    "yogurt", "cheese", "tofu", "rice", "wheat flour", "noodles", "bread", "sesame",
    "peanut", "soy sauce", "coconut milk", "lime", "ginger", "garlic", "herbs", "lentils",
]
PRODUCT_PREFIX = ["Fresh", "Daily", "Ready", "Family", "Market", "Garden", "Kitchen", "Chilled"]
PRODUCT_SUFFIX = ["Bowl", "Salad", "Wrap", "Meal", "Pack", "Mix", "Tray", "Kit", "Portion", "Box"]


def date_between(start, end):
    return start + timedelta(days=RNG.randint(0, (end - start).days))


def stamp(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def write_csv(name, fields, rows):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / name).open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{name}: {len(rows):,}")


def main():
    suppliers = [
        {"supplier_id": f"SUP-{i:03d}", "display_name": f"Fictional Supplier {i:03d}",
         "state": STATES[(i - 1) % len(STATES)]}
        for i in range(1, 49)
    ]
    ingredients = [
        {"ingredient_id": f"ING-{i:03d}", "name": name,
         "storage_class": "chilled" if name in {"chicken", "beef", "fish", "shrimp", "egg", "milk", "yogurt", "cheese", "tofu", "lettuce", "spinach"} else "ambient"}
        for i, name in enumerate(INGREDIENTS, 1)
    ]
    warehouses = [
        {"warehouse_id": f"WH-{i:03d}", "display_name": f"Fictional Distribution Hub {i:02d}",
         "state": STATES[(i * 3) % len(STATES)]}
        for i in range(1, 17)
    ]
    retailers = [
        {"retailer_id": f"RET-{i:04d}", "display_name": f"Fictional Outlet {i:04d}",
         "state": STATES[(i * 5) % len(STATES)]}
        for i in range(1, 601)
    ]
    products, recipes = [], []
    for i in range(1, 121):
        product_id = f"PRD-{i:03d}"
        product_ingredients = RNG.sample(ingredients, RNG.randint(2, 5))
        products.append({"product_id": product_id,
                         "display_name": f"{PRODUCT_PREFIX[(i-1) % len(PRODUCT_PREFIX)]} {PRODUCT_SUFFIX[((i-1)//len(PRODUCT_PREFIX)) % len(PRODUCT_SUFFIX)]} {i:03d}",
                         "storage_class": "chilled" if any(x["storage_class"] == "chilled" for x in product_ingredients) else "ambient"})
        for item in product_ingredients:
            recipes.append({"product_id": product_id, "ingredient_id": item["ingredient_id"]})

    ingredient_lots = []
    lots_by_ingredient = defaultdict(list)
    remaining_kg = {}
    for i in range(1, 6001):
        ingredient = ingredients[(i - 1) % len(ingredients)]
        received = date_between(START, END)
        lot = {"ingredient_lot_id": f"IL-{i:06d}", "ingredient_id": ingredient["ingredient_id"],
               "supplier_id": suppliers[RNG.randrange(len(suppliers))]["supplier_id"],
               "received_at": stamp(received), "quantity_kg": RNG.randint(1200, 3000)}
        ingredient_lots.append(lot)
        remaining_kg[lot["ingredient_lot_id"]] = lot["quantity_kg"]
        lots_by_ingredient[lot["ingredient_id"]].append((received, lot["ingredient_lot_id"]))
    for values in lots_by_ingredient.values():
        values.sort()

    recipe_map = defaultdict(list)
    for row in recipes:
        recipe_map[row["product_id"]].append(row["ingredient_id"])
    production_runs, lot_inputs, finished_lots = [], [], []
    downstream = defaultdict(list)
    for i in range(1, 15001):
        product = products[(i - 1) % len(products)]
        made = date_between(START + timedelta(days=110), END)
        run_id, finished_id = f"RUN-{i:06d}", f"FL-{i:06d}"
        production_runs.append({"run_id": run_id, "product_id": product["product_id"],
                                "produced_at": stamp(made), "factory_id": f"FACT-{1 + (i % 8):02d}"})
        finished_lots.append({"finished_lot_id": finished_id, "run_id": run_id,
                              "units_produced": RNG.randint(300, 1800),
                              "best_before": (made + timedelta(days=14 if product["storage_class"] == "chilled" else 180)).date().isoformat()})
        for ingredient_id in recipe_map[product["product_id"]]:
            input_kg = RNG.randint(5, 150)
            eligible = [lot_id for received, lot_id in lots_by_ingredient[ingredient_id]
                        if timedelta(0) <= made - received <= timedelta(days=100)
                        and remaining_kg[lot_id] >= input_kg]
            if not eligible:
                raise RuntimeError(f"Insufficient recent stock for {ingredient_id} on {made.date()}")
            ingredient_lot_id = RNG.choice(eligible)
            remaining_kg[ingredient_lot_id] -= input_kg
            lot_inputs.append({"run_id": run_id, "ingredient_lot_id": ingredient_lot_id,
                               "input_kg": input_kg})
            downstream[ingredient_lot_id].append(finished_id)

    shipments, readings, excursion_shipments = [], [], []
    for i, lot in enumerate(finished_lots, 1):
        run = production_runs[i - 1]
        produced = datetime.strptime(run["produced_at"], "%Y-%m-%dT%H:%M:%SZ")
        product = products[(i - 1) % len(products)]
        shipment_count = RNG.randint(2, 3)
        total_units = int(lot["units_produced"] * RNG.uniform(0.65, 0.9))
        allocated = 0
        for j in range(shipment_count):
            shipment_id = f"SHP-{len(shipments)+1:06d}"
            depart = produced + timedelta(hours=RNG.randint(6, 48))
            arrive = depart + timedelta(hours=RNG.randint(2, 16))
            retailer = RNG.choice(retailers)
            units = (total_units - allocated) if j == shipment_count - 1 else total_units // shipment_count
            allocated += units
            shipments.append({"shipment_id": shipment_id, "finished_lot_id": lot["finished_lot_id"],
                              "warehouse_id": RNG.choice(warehouses)["warehouse_id"],
                              "retailer_id": retailer["retailer_id"], "departed_at": stamp(depart),
                              "arrived_at": stamp(arrive), "units": units})
            excursion = product["storage_class"] == "chilled" and RNG.random() < 0.08
            if excursion:
                excursion_shipments.append(shipment_id)
            for k in range(6):
                t = depart + (arrive - depart) * (k / 5)
                temperature = RNG.uniform(1, 5) if product["storage_class"] == "chilled" else RNG.uniform(18, 28)
                if excursion and k in (2, 3, 4):
                    temperature = RNG.uniform(9, 15)
                readings.append({"shipment_id": shipment_id, "measured_at": stamp(t),
                                 "temperature_c": f"{temperature:.1f}", "sensor_id": f"SNS-{(i % 32)+1:03d}"})

    incident_reports, incident_truth, trace_truth = [], [], []
    used_ingredient_lots = list(downstream)
    for i in range(1, 2401):
        case_id = f"CASE-{i:05d}"
        if i <= 800:
            lot_id = RNG.choice(used_ingredient_lots)
            text = RNG.choice([
                f"Supplier says check ingredient batch {lot_id}; lab review pending.",
                f"Quality team flagged {lot_id.replace('-', ' ')} in inbound records.",
                f"Possible issue with incoming lot {lot_id.lower()}; trace downstream use.",
            ])
            kind, entity_type, entity_id = "ingredient_quality_review", "ingredient_lot", lot_id
            for finished_id in sorted(set(downstream[lot_id])):
                trace_truth.append({"case_id": case_id, "affected_finished_lot_id": finished_id})
        elif i <= 1600:
            lot_id = RNG.choice(finished_lots)["finished_lot_id"]
            text = RNG.choice([
                f"Packaging line review for finished batch {lot_id}.",
                f"Lab sample requested from {lot_id.replace('-', ' ')}.",
                f"Check product lot {lot_id.lower()} before release.",
            ])
            kind, entity_type, entity_id = "finished_lot_quality_review", "finished_lot", lot_id
            trace_truth.append({"case_id": case_id, "affected_finished_lot_id": lot_id})
        else:
            shipment_id = RNG.choice(excursion_shipments)
            text = RNG.choice([
                f"Temperature excursion on truck shipment {shipment_id}; hold for review.",
                f"Sensor alert during delivery {shipment_id.replace('-', ' ')}; inspect cold chain.",
                f"Check logger for {shipment_id.lower()}; possible warm interval.",
            ])
            kind, entity_type, entity_id = "cold_chain_review", "shipment", shipment_id
        incident_reports.append({"case_id": case_id, "report_type": kind,
                                 "report_text": text, "status": "review_required"})
        incident_truth.append({"case_id": case_id, "target_type": entity_type,
                               "target_id": entity_id})

    for name, fields, rows in [
        ("suppliers.csv", ["supplier_id", "display_name", "state"], suppliers),
        ("ingredients.csv", ["ingredient_id", "name", "storage_class"], ingredients),
        ("warehouses.csv", ["warehouse_id", "display_name", "state"], warehouses),
        ("retailers.csv", ["retailer_id", "display_name", "state"], retailers),
        ("products.csv", ["product_id", "display_name", "storage_class"], products),
        ("recipes.csv", ["product_id", "ingredient_id"], recipes),
        ("ingredient_lots.csv", ["ingredient_lot_id", "ingredient_id", "supplier_id", "received_at", "quantity_kg"], ingredient_lots),
        ("production_runs.csv", ["run_id", "product_id", "produced_at", "factory_id"], production_runs),
        ("lot_inputs.csv", ["run_id", "ingredient_lot_id", "input_kg"], lot_inputs),
        ("finished_lots.csv", ["finished_lot_id", "run_id", "units_produced", "best_before"], finished_lots),
        ("shipments.csv", ["shipment_id", "finished_lot_id", "warehouse_id", "retailer_id", "departed_at", "arrived_at", "units"], shipments),
        ("temperature_readings.csv", ["shipment_id", "measured_at", "temperature_c", "sensor_id"], readings),
        ("incident_reports.csv", ["case_id", "report_type", "report_text", "status"], incident_reports),
        ("answer_key_incident_targets.csv", ["case_id", "target_type", "target_id"], incident_truth),
        ("answer_key_downstream_lots.csv", ["case_id", "affected_finished_lot_id"], trace_truth),
    ]:
        write_csv(name, fields, rows)


if __name__ == "__main__":
    main()
