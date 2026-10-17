# TraceFront demo script

A three-minute live demo: what to click, what the screen shows, and what to say. Setup and recovery details are in [demo-runbook.md](demo-runbook.md).

**The story in one line:** a warm chicken shipment looks like the cause of a Salmonella positive, but a second positive in a salad with no chicken points to a shared lettuce lot. The officer extends the hold and the decision is recorded.

## Before you present

Start about five minutes early, from the repository root in PowerShell.

| Terminal | Command | Keep it open? |
|---|---|---|
| A | `.\backend\demo-tunnel.ps1` | Yes, for the whole demo |
| B | `.\backend\.venv\Scripts\python -B backend/preflight.py` | No. It must end with "all five pathogen models and explanations". |
| C | `cd frontend`, then `npm run dev` | Yes. It must say `Local: http://localhost:3000`. |

Then:

1. Run only one frontend. If `next start` or another `npm run dev` already holds port 3000, Next.js moves to 3001, and the server refuses requests from 3001.
2. Click through the whole flow once, without pressing **Approve**. Dev mode compiles each page on its first visit, which takes a few seconds; this warm-up keeps that delay out of the live demo.
3. On `/trace`, check that RM-402 reads "Marinated chicken". If it doesn't, click **Load synthetic scenario** once.
4. Close other tabs and set the browser zoom so the trace network fits the screen width.

## The script

### 0:00–0:20 · Set the scene

- **Show:** http://localhost:3000
- **Say:** "A food-safety officer receives a supplier's shipment file after a chilled chicken truck ran warm. TraceFront finds what went wrong, follows the stock to every site, and records who decided to hold it."

### 0:20–0:50 · Detect

- **Click:** **Browse files**, then **Open** on `supplier_shipments.csv`, then **Preview analysis**. Let the animation finish, then scroll to the findings.
- **Show:**
  - The summary: 3 findings (1 high, 1 medium, 1 low).
  - The checks row: temperature 6/8 shipments, humidity 1/8, arrival delay 1/8, quantity 1/8, destination 8/8.
  - Finding 01 opened: SHIP-017, lot RM-402, peak 12.1 °C against the 4 °C limit for chilled poultry, 120 minutes in the danger zone.
- **Say:**
  - "We always say what we couldn't check. Two shipments had no temperature data, so zero findings is never a clearance."
  - "Every finding cites its rule and its source record: the EU poultry limit and the USDA two-hour rule. It isn't a black box."

### 0:50–1:05 · Spread

- **Click:** **Next**.
- **Show:** the distribution network, with the flagged shipments marked.
- **Optional:** open **Early warning** to show the drafted heads-up. Say "nothing is sent; this comes before the formal decision".
- **Click:** **Trace related lots**.

### 1:05–1:50 · Trace (the twist)

- **Show:**
  - The banner carries finding 01 into the investigation.
  - RM-402 went into **CW-42 chicken wrap**, then to Warehouse KL and stores KL-03 and KL-04.
  - The lab evidence: CW-42 is Salmonella positive.
- **Say:** "Case closed? The warm chicken explains the wrap…"
- **Show:** the amber panel. **CS-91, a Caesar salad with no chicken**, is also positive.
- **Say:** "…but it doesn't explain the salad."
- **Click:** **Investigate all 2 positive products together**.
- **Show:** **L-102 lettuce** ranks first, shared by 2 of 2 products. RM-402 drops to 1 of 2.
- **Say:** "The excursion was real, but the only thing both positives share is the lettuce. That's an investigation lead, not proof, so we act on the stock, not on blame."

### 1:50–2:30 · Decide

- **Show:** the **Containment decision** panel.
  - **Targeted hold:** 2 lots, 5 shipments.
  - **Extended hold (recommended):** 5 lots, 9 shipments, 7 sites. 3 shipments are still moving and can be stopped; 6 are delivered and need a hold at the site. It includes **VW-17 veggie wrap**, made with the same lettuce, which hasn't tested positive yet.
- **Click:** type an officer name and a reason, then **Approve extended hold**.
- **Show:**
  - The decision history: who, when, why, and the link back to the upload.
  - The held shipments are marked "Hold approved · simulated".
  - Refresh the page: the decision is still there.
- **Say:** "The system recommends; a person decides; the record survives."

### 2:30–3:00 · Close

- **Say:** "All of this runs on IBM LinuxONE: the API, PostgreSQL, and five XGBoost pathogen models, served on s390x."
- **State the limits plainly:**
  - The lab results and lot links are a simulated scenario.
  - The hold is recorded, not executed. Nothing is sent to a site.
  - Shipment rows are movements, not current inventory.
  - The models score FSIS laboratory samples, not uploaded shipments.

## Questions you may get

**What does the ML do?**
On the home page, **Spin a sample** runs a real FSIS sample through every pathogen model for that product, with per-feature explanations. The models rank which samples to test next; they don't decide holds.

**How good is it?**
Lead with poultry *Campylobacter*:
- Test PR-AUC is 0.433 on LinuxONE (0.434 on x86), against a 19.8% positive rate; ROC-AUC is 0.752.
- At its threshold it flags 49% of samples and catches 77% of positives.

Source: `food-risk-ml/docs/model_card_campylobacter.md`.

**Does it really run on IBM Z?**
Yes. The evidence is in `food-risk-ml/reports/linuxone_evidence/`:
- The hardware log shows s390x, big-endian, IBM machine type 9175.
- The Campylobacter model was retrained there in 33 s.
- Its `/predict` call answered in 0.098 s.

**Why not just recall everything?**
The two hold options make the trade-off visible: 5 shipments for the targeted hold against 9 for the extended one. A broad recall pulls stock that no evidence links to the incident.

**Is the temperature rule made up?**
No. The rules cite their sources: Regulation (EC) No 853/2004 for chilled poultry, and the USDA danger zone of 4.4–60 °C with a 2-hour limit.

## If something breaks

| What you see | What to do |
|---|---|
| "Cannot reach the backend API at http://localhost:8000…" | The tunnel dropped. Re-run Terminal A, then refresh. |
| "Cannot reach the service at http://localhost:18000" | You're on an old production build. Stop it and use `npm run dev` on port 3000. |
| Dev server says `Local: http://localhost:3001` | Something else holds 3000. Stop it, then restart `npm run dev`. |
| Trace says "Lot RM-402 has no stored ingredient links yet" | Click **Load synthetic scenario**. It keeps RM-402 selected. |
| The animation sits at 100% | Keep the browser tab in front; the animation pauses in background tabs. |
| Anything else | Switch to the backup video. |

## Rehearsal rules

- Decisions can't be edited or deleted, so every rehearsal approval stays in the history for that selection. Rehearse up to **Approve** and stop there, or plan a cleanup before the final run.
- Record one clean run as a backup video.
- Rehearse three times in a row without manual fixes before the real presentation.
