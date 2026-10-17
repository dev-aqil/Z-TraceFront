# Tracefront

## Real-Time AI for Food Safety Decisions

### Datathon Track
**Real-Time AI for Critical Decisions**

---

## 1. Project Summary

**Tracefront** is a real-time AI decision-support platform for food safety incidents.

It monitors live supply-chain activity such as production, shipments, warehouse inventory, delivery status, storage temperature, product batches, and laboratory results.

Tracefront does not claim that AI can directly detect bacteria such as Salmonella. Instead, it:

1. Detects when a food batch becomes unusually risky.
2. Shows where that batch came from and where it is going.
3. Identifies other products connected to it.
4. Evaluates possible containment actions.
5. Recommends what food-safety teams should do next.
6. Continuously updates the recommendation as new information arrives.
7. Keeps a human officer in control of major actions.

The main question Tracefront tries to answer is:

> **What should we do right now to stop a possible food safety incident from spreading?**

---

## 2. Problem

Food contamination is difficult to manage because food can continue moving through factories, warehouses, delivery vehicles, and stores before contamination is confirmed.

It is unrealistic to laboratory-test every food product every day. A food-safety problem may only become known after laboratory testing, routine inspections, company quality checks, consumer illness reports, or outbreak investigations.

By the time contamination is confirmed, the affected food may already have moved through several stages of the supply chain.

Food-safety teams then need to answer urgent questions:

- Where did the affected food come from?
- Which ingredient or production batch may be responsible?
- What other products used the same ingredient?
- Which warehouses currently hold those products?
- Which trucks are carrying them?
- Which stores have already received them?
- Should a shipment be stopped?
- Should warehouse inventory be held?
- Should selected stores quarantine stock?
- Is a targeted recall enough, or is a broader recall required?

Acting too late can expose more consumers. Acting too aggressively can create unnecessary food waste, financial loss, and supply-chain disruption.

Tracefront helps teams make faster and more informed decisions while the incident is still developing.

---

## 3. Target Users

1. **Food Manufacturers and Processors**<br>
   Identify affected ingredients, production batches, and finished products.

2. **Food Safety and Quality Assurance Teams**<br>
   Monitor food-safety risk, investigate abnormalities, and review AI recommendations.

3. **Government Food Safety Authorities**<br>
   Support traceback, investigation, containment, and recall decisions.

4. **Distributors and Warehouses**<br>
   Identify affected stock or shipments and prevent them from moving further.

5. **Logistics Providers**<br>
   Identify trucks carrying potentially affected products and respond to hold or interception recommendations.

6. **Supermarket and Retail Chains**<br>
   Identify affected stores and quarantine or remove selected products.

7. **Consumers**<br>
   Indirect beneficiaries through faster containment and more accurate recalls.

---

## 4. Core MVP Flow

```text
LIVE SUPPLY CHAIN
        |
        v
Temperature / Shipment / Inventory Events
        |
        v
+---------------------------+
| AI / ML RISK ENGINE       |
|                           |
| How risky is this batch?  |
+---------------------------+
        |
        v
Risk Score + Explanation
        |
        v
Supply-Chain Graph
        |
        v
What is connected to this batch?
        |
        v
Decision Engine
        |
        v
What should we do now?
        |
        v
Human Approval
```

---

## 5. Before Contamination Is Confirmed

Tracefront continuously monitors operational data.

Example:

```text
Lettuce Batch L-102

10:00   3°C
10:10   4°C
10:20   8°C
10:30   11°C
10:40   12°C

Shipment delayed: 35 minutes
```

The AI does **not** say:

> Salmonella detected.

Instead, it says:

```text
FOOD SAFETY RISK

Batch: L-102
Risk: HIGH

Reasons:
- Long temperature excursion
- Shipment delay
- Product requires refrigeration

Recommended:
- Prioritize inspection/testing
- Temporarily hold warehouse stock
- Monitor related shipments
```

Tracefront detects **risk**, not confirmed biological contamination.

---

## 6. After Contamination Is Confirmed

Suppose a laboratory reports:

```text
SALMONELLA POSITIVE

Product:
Chicken Wrap

Batch:
CW-42
```

Tracefront checks which ingredients were used:

```text
Chicken Wrap CW-42
|
|-- Chicken C-81
|-- Lettuce L-102
|-- Sauce S-19
```

Later another product tests positive:

```text
Caesar Salad CS-91
|
|-- Lettuce L-102
|-- Cheese C-17
|-- Sauce S-71
```

Both contaminated products share **Lettuce L-102**.

Tracefront can rank L-102 as a high-priority investigation target, especially if the same batch already experienced an earlier temperature anomaly.

It should say:

> **Lettuce L-102 is the highest-priority source to investigate.**

It should not say:

> **AI has proven L-102 caused the contamination.**

---

## 7. Supply-Chain Graph

A supply-chain graph is simply a map of:

> **What came from where, what was used to produce what, and where it went next.**

Example:

```text
Lettuce Farm
     |
Lettuce L-102
     |
FreshBite Factory
   /           \
Chicken Wrap   Caesar Salad
     |              |
Warehouse KL    Warehouse JB
   /    \         /     \
Store 1 Store 2 Store 3 Store 4
```

Tracefront can move backward through the graph to answer:

> Where did the affected food come from?

It can move forward to answer:

> Where else could the affected food be going?

---

## 8. Main AI / ML Component

The main ML component should be the **Food Safety Risk Engine**.

### Goal

Estimate how risky each food batch is as new supply-chain events arrive.

### Example Inputs

- Current temperature
- Maximum temperature
- Time above expected temperature
- Number of abnormal temperature readings
- Delivery delay
- Shipment duration
- Product category
- Refrigerated or non-refrigerated
- Time since production
- Historical supplier incidents
- Historical recall patterns

### Example Output

```text
Batch L-102

Risk Score:
82 / 100

Risk Level:
HIGH

Main Reasons:
- Long temperature excursion
- Shipment delay
- Historical supplier risk
```

### Recommended MVP Models

- XGBoost
- Gradient Boosting
- Random Forest
- Snap ML if useful on LinuxONE

Do not use an LLM for the main risk model.

---

## 9. Optional Second AI Component

If the MVP is completed early, add **Source Ranking AI**.

After contamination is confirmed, the system ranks possible sources.

Example:

```text
LIKELY SOURCE RANKING

1. Lettuce L-102       91%
2. Factory Line 2      37%
3. Chicken C-81        16%
4. Sauce S-19           8%
```

The purpose is to help investigators decide:

> **What should we inspect or test next?**

---

## 10. Decision Engine

The decision engine does not need to be another ML model for the MVP.

It can use normal business logic, graph analysis, and simple optimization.

Example:

```text
Risk = 82%

Warehouse inventory:
8,200 units

Truck T17:
2,300 units
ETA 16 minutes

Stores already reached:
3
```

Possible options:

```text
OPTION A
Do nothing
Additional distribution: 8,200 units
```

```text
OPTION B
Hold warehouse
Additional distribution: 2,300 units
```

```text
OPTION C
Hold warehouse
+ Stop Truck T17
+ Flag affected stores
Additional distribution: 0 units
```

Tracefront can recommend the option that best reduces safety risk while avoiding unnecessary disruption.

---

## 11. Real-Time Critical Decision Features

To strongly match the **Real-Time AI for Critical Decisions** track, Tracefront should focus on decisions that must be made while the food is still moving.

### Live Containment Recommendation

```text
CRITICAL DECISION REQUIRED

Batch:
L-102

Risk:
HIGH

Next delivery:
16 minutes

Recommended:
- Hold warehouse inventory
- Stop Truck T17
- Flag Stores A, B, C
- Prioritize L-102 for testing
```

### Time-to-Next-Exposure

```text
TIME TO NEXT DELIVERY

00:16:42

Store KL-03 receives L-102
unless intervention occurs.
```

### Intervention Simulation

Compare:

```text
DO NOTHING
+8,200 units distributed
```

against:

```text
STOP SHIPMENT + HOLD WAREHOUSE
0 additional units distributed
```

### Continuously Updating Recommendation

```text
10:00
Risk = 42%
Recommendation = Monitor

10:05
Risk = 67%
Recommendation = Prioritize testing

10:10
Risk = 82%
Recommendation = Hold warehouse

10:12
Truck departed
Recommendation = Hold warehouse + Stop truck

10:20
Lab result positive
Recommendation = Targeted recall
```

---

## 12. Human-in-the-Loop

Tracefront should not automatically trigger major recalls.

```text
AI detects risk
      |
      v
AI evaluates situation
      |
      v
AI recommends action
      |
      v
Food Safety Officer
      |
      v
AUTHORIZE
```

---

## 13. Datasets

Tracefront needs a combination of real and synthetic datasets.

### A. Historical Food Recall Data

Use public historical recall records such as openFDA Food Enforcement data.

Purpose:

- Historical risk features
- Product risk patterns
- Previous contamination patterns

### B. Synthetic Supply-Chain Data

Generate:

- Suppliers
- Factories
- Ingredients
- Product batches
- Warehouses
- Trucks
- Stores

Example MVP size:

```text
10 suppliers
3 factories
5 warehouses
10 trucks
50 stores
500 batches
```

### C. Ingredient-to-Product Relationships

Example:

```text
Lettuce L-102
|
|-- Chicken Wrap CW-42
|-- Caesar Salad CS-91
|-- Veggie Wrap VW-17
```

### D. Real-Time Sensor Data

Simulate:

- Temperature
- Humidity
- Timestamp
- Shipment location

### E. Shipment and Inventory Data

Include:

- Shipment origin
- Destination
- Truck status
- ETA
- Quantity
- Warehouse stock
- Store deliveries

### F. Laboratory Results

Simulate positive and negative contamination events.

---

## 14. Simplified MVP ERD

### Organization

Represents supplier, factory, warehouse, or store.

```text
organization_id
name
type
```

### Batch

Represents an ingredient or finished product batch.

```text
batch_id
product_name
organization_id
produced_at
status
```

### BatchRelationship

Connects an ingredient batch to a finished-product batch.

```text
parent_batch_id
child_batch_id
quantity_used
```

### Shipment

Tracks movement of a batch.

```text
shipment_id
batch_id
from_org_id
to_org_id
quantity
status
departed_at
eta
```

### SensorReading

Stores live shipment sensor information.

```text
reading_id
shipment_id
timestamp
temperature
humidity
```

### LabResult

Stores contamination test results.

```text
lab_result_id
batch_id
tested_at
contaminant
result
```

---

## 15. LinuxONE Architecture

LinuxONE should be part of the core system.

```text
Supply Chain Simulator
        |
        v
Live Events
        |
        v
+----------------------------------+
|          IBM LinuxONE            |
|                                  |
| Event Ingestion                  |
|       |                          |
|       v                          |
| PostgreSQL                       |
|       |                          |
|       v                          |
| ML Risk Inference                |
|       |                          |
|       v                          |
| Supply-Chain Graph Analysis      |
|       |                          |
|       v                          |
| Decision Engine                  |
|       |                          |
|       v                          |
| Incident / Decision Audit Log    |
+----------------------------------+
        |
        v
Operations Dashboard
```

LinuxONE can host:

- Backend API
- Event processing
- PostgreSQL database
- ML inference
- Graph analysis
- Decision engine
- Incident logs
- Audit trail

---

## 16. Recommended MVP Tech Stack

### Frontend
- Next.js / React
- Tailwind CSS
- Cytoscape.js

### Backend
- Python
- FastAPI

### Database
- PostgreSQL

### AI / ML
- XGBoost
- Gradient Boosting
- Random Forest
- Snap ML if appropriate

### Graph Logic
- NetworkX

### Deployment
- IBM LinuxONE

### Data
- Public historical food recall data
- Synthetic supply-chain generator
- Synthetic real-time event generator

---

## 17. Demo Scenario

### Step 1: Normal Operations

```text
SYSTEM STATUS: NORMAL

Active batches: 500
Active shipments: 10
Stores: 50
```

### Step 2: Temperature Anomaly

```text
Lettuce L-102

Temperature:
3°C -> 4°C -> 8°C -> 11°C -> 12°C
```

AI updates:

```text
Risk:
18% -> 67%
```

### Step 3: Shipment Starts Moving

```text
Truck T17
Destination: Store KL-03
ETA: 16 minutes
```

Risk rises to 82%.

Tracefront recommends:

- Hold warehouse stock
- Stop Truck T17
- Flag already delivered inventory

### Step 4: Lab Confirmation

```text
Chicken Wrap CW-42
Salmonella: POSITIVE
```

Tracefront performs traceback.

### Step 5: Second Positive Product

```text
Caesar Salad CS-91
Salmonella: POSITIVE
```

Both products share Lettuce L-102.

### Step 6: Targeted Recall

Tracefront identifies affected products, warehouses, and stores, then compares a blanket recall with a targeted recall.

### Step 7: Human Authorization

```text
[VIEW EVIDENCE]

[SIMULATE]

[AUTHORIZE]
```

### Step 8: Decision Replay

```text
10:01  Temperature anomaly
10:05  Risk increased
10:07  Shipment detected
10:08  Hold recommended
10:09  Officer approved
10:20  Lab positive
10:21  Traceback completed
10:22  Targeted recall recommended
```

---

## 18. MVP Priorities

### Must Have

1. Synthetic supply-chain generator
2. Batch and shipment database
3. Real-time temperature events
4. ML risk score
5. Supply-chain graph
6. Trace backward and forward
7. Lab result event
8. Containment recommendation
9. Human approval screen
10. LinuxONE deployment

### Nice to Have

1. Source Ranking AI
2. Next-Best-Test recommendation
3. Recall optimization
4. Live countdown
5. Decision replay
6. Advanced explainability
7. Consumer adverse-event data

Do not build the Nice-to-Have features until the main end-to-end flow works.

---

## 19. Key Differentiator

Tracefront should not be presented as:

> An AI that detects contaminated food.

Instead:

> **Tracefront is a real-time AI decision-support system that detects emerging food-safety risk, understands how affected food is connected across the supply chain, and recommends the best containment action while the incident is still unfolding.**

The core intelligence can be explained in three questions:

```text
ML
|
v
Is something becoming dangerous?

GRAPH
|
v
What is connected to the risk?

DECISION ENGINE
|
v
What should we do now?
```

---

## 20. One-Line Pitch

> **Tracefront uses real-time AI on IBM LinuxONE to detect emerging food-safety risk, trace affected products across the supply chain, and help safety teams decide what to stop, hold, test, or recall before the incident spreads.**

---

## 21. Proposed Hybrid AI Revision (17 October 2026)

The team is considering a three-stage AI workflow. This proposal refines the earlier single-risk-model diagram and still needs implementation and evaluation.

1. *Predictive AI for structured data:* Use batch, shipment, inventory, temperature, and timing fields to estimate a review priority. Train and evaluate this model only against defensible labels. Until then, display a transparent rule-based priority and avoid presenting its number as a calibrated probability of contamination.
2. *Generative AI for unstructured evidence:* Read incident descriptions, inspection notes, lab reports, and supplier messages. Extract entities, dates, test outcomes, and uncertainty into a defined schema, with the source passage for each finding. It may offer an initial judgement for investigator review, but cannot turn an allegation or anomaly into a confirmed contamination event.
3. *RAG-supported final recommendation:* Retrieve approved food-safety procedures and policy documents relevant to the incident, then combine them with the structured evidence, predictive output, and deterministic batch graph. Return a structured recommendation with actions, affected lot IDs, evidence, cited procedure passages, uncertainty, and an explicit human-approval status. Retrieval-augmented generation supplies context; it does not independently verify a lab result or replace an authorised safety officer.

All model inference and the retrieval service are intended to run on the LinuxONE VM, alongside the graph and decision API. The VM's 3 vCPUs and 8 GB RAM make model size and response time practical constraints, so the team should test a small CPU-capable model before promising real-time latency. A single local language model may serve both generative stages with separate prompts and schemas if two model instances do not fit.

The project repository is now the private `dev-aqil/Z-TraceFront` repository. Teammates have collaborator Git access. Keep private SSH keys and the team's local public-key folder outside Git; use normal branches and pull requests to coordinate submission work.
