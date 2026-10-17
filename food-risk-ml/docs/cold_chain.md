# Cold-chain monitoring (rules, real time)

`src/coldchain/rules.py` applies published temperature rules to a live stream of sensor readings. Each reading takes constant time to process, and every alert says which rule fired and quotes its source.

**This is not a trained model and has no accuracy figure.** No dataset links sensor readings to measured outcomes (Person A M8: `BLOCKED_PENDING_SENSOR_DATA`), so nothing is learned and nothing is scored. Learning from invented outcomes would break the project's no-invented-data rule. The demo feed is **simulated** and every output says so (`"simulated": true`).

## Rules (`configs/cold_chain_rules.toml`)

| Profile | Limit | Source |
|---|---|---|
| `poultry_chilled` | ≤ 4 °C | Regulation (EC) No 853/2004, Annex III, Section II, Chapter V |
| `red_meat_chilled` | ≤ 7 °C, kept during storage and transport | Regulation (EC) No 853/2004, Annex III, Section I, Chapter VII |
| `offal_chilled` | ≤ 3 °C, kept during storage and transport | same |
| `tcs_food_us` | ≤ 5 °C (41 °F) | FDA Food Code 2022, 3-501.16 |
| `frozen` | ≤ −18 °C, with no tolerance applied | Council Directive 89/108/EEC, Article 2. Article 5 allows brief upward fluctuations; that limit was not verified, so none is applied. |

**Danger zone (every profile):** USDA FSIS guidance says bacteria grow most rapidly between 40 °F (4.4 °C) and 140 °F (60 °C). Perishable food should not be out of refrigeration for more than **2 hours**, or **1 hour above 90 °F (32.2 °C)**.

## Statuses and alerts

| Status | Meaning |
|---|---|
| `ok` | at or below the product limit |
| `excursion` | above the product limit now. A `EXCURSION` alert is raised once per excursion. |
| `critical` | cumulative time in the danger zone has reached the USDA limit. It stays critical: cooling down again does not undo time already spent warm. |

- **`DATA_GAP`:** readings more than 15 minutes apart. The gap is **not** counted as in range or out of range; it is reported.
- **Time accounting:** sample-and-hold. The interval after a reading is charged at that reading's temperature.
- **Calibration:** every stream has an `offset_c` added to each raw reading. Real sensors read off; set it from the sensor's calibration certificate.

## Run

```
python -m src.cli cold-chain --scenario compressor_failure --profile poultry_chilled --benchmark 100000
python -m src.cli cold-chain --readings my_readings.csv --profile red_meat_chilled --offset -0.3
```

- **CSV format:** `stream_id,time,temp_c`, with ISO times in ascending order per stream. Out-of-order or non-finite readings are rejected.
- **Simulated scenarios:** `normal`, `door_open` (20 min at about 6.5 °C during unloading), `compressor_failure` (warms toward 28 °C from minute 60) and `sensor_dropout` (40 min with no readings).

**Throughput, single thread, 2026-10-17:**
- x86 laptop: about 136,000 readings/s, 7 µs per reading
- **LinuxONE (IBM Z, s390x): 269,141 readings/s, 3.7 µs per reading** (`reports/linuxone_evidence/step4/46_cold_chain.log`)
