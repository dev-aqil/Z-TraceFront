# Live Food Recaller for the Supply Chain

## Project status

- **Selected idea:** Adam's food-safety and supply-chain traceability proposal.
- **Proposed competition track:** Real-Time AI for Critical Decisions.
- **Status:** Concept selected. Dataset availability, licences, model approach, and implementation scope still need validation.

## Original problem statement

Food contamination may only be identified after a product has reached the market. When a laboratory or food-safety investigation confirms contamination, regulators such as Malaysia's Ministry of Health (KKM) need to know which batches are still in the supply chain and which retailers may still have them, so affected products can be isolated or recalled and consumers can be warned.

## Intended users

- Consumers
- Food manufacturers
- Retail and supermarket chains
- Distributors
- Warehouses
- Food-safety regulators, such as KKM

## Proposed workflow

1. **Cold-chain warning:** Simulate temperature readings from a refrigerated truck carrying a temperature-sensitive food product. If readings exceed a product-specific threshold for a relevant duration, flag the shipment for review and recommend that the supplier hold or test it.
2. **Batch traceability:** When a contamination report or foodborne-illness investigation identifies a suspect batch, trace that batch through distributors and retailers to locate products that may still be available.
3. **Ingredient-to-product tracing:** If a contaminated ingredient was transformed into other products, trace those products too. For example, a contaminated lettuce lot used in ready-to-eat salad may affect multiple finished-product batches.

The proposal is to track and act at the **food-batch level**.

## Proposed AI components

### Food-safety risk detection

Candidate input features:

- Temperature readings and excursion duration
- Storage duration
- Transport duration
- Supplier history
- Previous recall information
- Shipment conditions
- Product type

Candidate models named in the proposal include XGBoost, Gradient Boosting, and Random Forest. The model and training approach have not yet been selected or validated.

### Recall-scope decision support

The system would recommend which batches and downstream locations require attention, aiming to identify affected products without unnecessarily including unrelated batches. The recommendation should explain which lot links and risk signals led to the result.

The proposed AI should support investigation and prioritisation. A qualified food-safety authority or responsible organisation would make the final decision to release, hold, or recall products.

## Proposed data sources

- **OpenFDA Food Enforcement Reports API:** Proposed source for historical food recall examples. It has not yet been confirmed as suitable for the Malaysia-focused use case.
- **Synthetic supply-chain data:** Proposed source for batch movements, ingredient transformations, retailer inventory, and simulated cold-chain sensor events.

### Dataset validation notes

- OpenFDA documents publicly releasable U.S. food recall records, with records dating from 2004 onward and weekly updates. Its fields include recall reasons, product descriptions, code information, and distribution patterns. See the [OpenFDA Food Enforcement API](https://open.fda.gov/apis/food/enforcement/) and its [searchable fields](https://open.fda.gov/apis/food/enforcement/searchable-fields/).
- OpenFDA is a U.S. FDA recall source. It should not be presented as KKM data or as a live Malaysian traceability system. Its public recall records do not provide this project's simulated sensor stream or a complete retailer-by-retailer batch graph. This is a scope implication of the available endpoint and fields, not a claim that no other data source exists.
- The team's synthetic data should be clearly labelled as simulated. It can demonstrate the workflow, but cannot by itself validate real-world contamination prediction performance.
- Before submission, record dataset sources, licences or terms, coverage, limitations, and any synthetic-data assumptions.

## Proposed LinuxONE role

The proposal is to host the meaningful backend AI components on IBM LinuxONE Community Cloud, including:

- API and event processing
- Risk inference
- Batch-relationship graph traversal
- Recall-scope recommendations
- Database access and audit records

The demo should show a real request reaching a service on LinuxONE and returning a risk or traceability result. The final technology choices remain open.

## Initial technology suggestions

These are suggestions from the original proposal, not final decisions:

- **Frontend:** Next.js or React, Tailwind CSS, Cytoscape.js, and Chart.js
- **Backend:** Python with FastAPI
- **AI/ML:** XGBoost, Snap ML, or scikit-learn
- **Graph processing:** NetworkX
- **Database:** PostgreSQL
- **Data:** OpenFDA plus a synthetic supply-chain simulator

## Key assumptions and risks to validate

1. A temperature excursion is a risk signal, not proof that food is contaminated. Thresholds must be appropriate to the product and the intended decision. The prototype should flag a shipment for review, hold, or testing rather than assert contamination based on temperature alone.
2. Public historical recall records may not include enough batch-level and retailer-level detail to reconstruct a complete supply chain. The demonstrable batch graph may need to be synthetic.
3. A supervised model requires suitable labelled examples. Do not claim predictive accuracy unless the team has a defensible labelled dataset and a meaningful evaluation method.
4. “Recall optimisation” needs a safe boundary: the system can explain and prioritise a proposed scope, while authorised food-safety decision-makers retain final authority.
5. Keep the event prototype narrow, for example one ready-to-eat salad product, a few ingredient and finished-product lots, a small set of distributors and retailers, one simulated temperature excursion, and one confirmed contamination event.

## Suggested demo narrative

Show a simulated cold-chain excursion triggering a review flag. Then enter a confirmed contamination report for an ingredient lot. The LinuxONE-hosted backend traces that lot through product transformations and shipment records, returns the potentially affected finished-product batches and retailers, and explains why each is included. Unrelated batches remain outside the proposed scope when the recorded links show they were not exposed.
