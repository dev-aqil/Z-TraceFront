# Food recall data workspace (pre-event preparation)

This folder contains two separate data sources for exploring Adam's Live Food Recaller idea. **All simulated company, product, lot, shipment, sensor, and incident records are fictional.** Do not present them as Malaysian food-safety records or as evidence that a model can predict contamination.

## Real historical recall archive

`real/openfda/food-enforcement-0001-of-0001.json.zip` is the openFDA Food Enforcement bulk download, retrieved 16 October 2026 UTC. The [download index](https://api.fda.gov/download.json) reported an export date of 14 October 2026 and 29,485 records. The archive was checked and contains 29,485 records. `real/openfda/download-metadata.json` records the source URL and version metadata.

The [openFDA Food Enforcement API](https://open.fda.gov/apis/food/enforcement/) describes U.S. FDA enforcement reports. It is useful for examining actual recall descriptions, reasons, classification, and product code wording. It does not supply this project's complete supplier-to-factory-to-retailer graph or temperature sensor readings. Do not use historical enforcement reports as a live public alert feed. Check [openFDA terms](https://open.fda.gov/license/) before redistributing derived data.

## Fictional practice data

Run `python adam-food-recall-data/generate_practice_data.py` from the workspace root to regenerate `synthetic-practice/*.csv`. The script needs only Python's standard library and uses seed `20261017`. The current export models 2024 through 2025 and has:

| Category | Rows |
| --- | ---: |
| Suppliers, ingredients, warehouses, retailers, products | 48, 32, 16, 600, 120 |
| Recipes and ingredient lots | 440, 6,000 |
| Production runs, ingredient inputs, finished lots | 15,000, 55,000, 15,000 |
| Shipments and temperature readings | 37,562, 225,372 |
| Incident reports and target answer key | 2,400 each |
| Downstream finished-lot answer key | 8,387 |

Relations: `recipes` links products to ingredient types; `lot_inputs` links ingredient lots to production runs; `finished_lots` links runs to output lots; `shipments` links output lots to retailers through warehouses; `temperature_readings` links to shipments. `incident_reports` contains noisy text. The two `answer_key_*` files are *held-out answers* for testing lot matching and ingredient-to-finished-lot tracing. Do not include answer-key columns as model inputs.

The 2,400 incidents comprise 800 ingredient-lot quality reviews, 800 finished-lot quality reviews, and 800 cold-chain reviews. A temperature excursion means *review required*, never confirmed contamination. The text is generated from a few templates, so a high score on this set would not establish real-world performance. For a meaningful text-matching evaluation, create a separate manually reviewed set of real notices and split by source or time, not just random rows from these templates.

## Event boundary and limitations

The participant guidebook says pre-event research and data exploration are allowed, while actual project code must start during the 17 to 18 October hacking window. This generator and output are explicitly **practice/reference material made before the event**. Rebuild the submitted solution during the official window and verify with organisers whether any pre-event generated data may be used in the submission. The local `.gitignore` keeps the large downloaded and generated files out of an accidental commit.

The simulation has consistent references, stock capacities, shipment quantities, and dates, but it does not emulate a real operator's full traceability process. For example, it has no real retailer inventory depletion, consumer exposure data, lab-confirmed contamination labels, or reliable Malaysian recall coverage. The broad synthetic set supports UI and pipeline load testing; start the live demo with a small traceable scenario that can be explained in three minutes.
