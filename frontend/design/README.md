# Tracefront design workspace

The existing Next.js app serves the design map at `/design`. React components shared by the future screens live in `../components/design/`. The two original HTML mockups are archived in `reference/` as design inputs, not runtime pages.

## Screen mapping

| New screen | Mockup material to carry forward | Product decision |
| --- | --- | --- |
| 1. Supplier upload | File well, dataset summary, confirmation | Accept a shipment dataset, validate its structure, and show exactly what was read. Do not claim that choosing a file has uploaded it. |
| 2. Analysis | Circular correlation motif | Reuse the current `/ml-process` animation as an explanation while actual ingestion, risk inference, document analysis, retrieval, and graph tracing run through separate services. The animation itself is illustrative. |
| 3. Review and response | Anomaly cards, distribution view, contact panel | Show anomaly evidence and a batch-specific downstream graph. Keep an early precautionary warning separate from the update based on an official lab result. Both require a human review step. |

The two mockups spread these concepts across six numbered pages. The new flow groups them into three screens so the supplier can move from upload to evidence to action without repeating panels.

## Candidate component boundaries

- `WorkflowSteps` and `StageCard` provide shared navigation and design language now.
- `SupplierUpload` will own file selection, format checks, column mapping, and upload status.
- `AnalysisProgress` will present actual backend job state alongside the circular animation.
- `AnomalyList` and `SupplyChainGraph` will share batch IDs and a selected anomaly.
- `NotificationReview` will prepare separate early and post-lab messages, with explicit approval and delivery status.

## Data and claims to settle before implementation

- The supplier file needs batch IDs, shipment IDs, product/ingredient IDs, origin, destination, buyer, timestamps, temperature readings, and quantities. Validate or map real incoming columns before displaying a record count.
- Historical openFDA recall records can provide reference patterns. They cannot prove that a particular uploaded shipment was contaminated; the supplier file and official lab result provide different evidence.
- Avoid the mockups' fixed correlation coefficients, 142 kitchens, four alerts, and simulated delivery confirmations unless a clearly labeled demo fixture backs them.
- Copy, English terminology, and stage ownership are deliberately open for team review before the six mockup pages are converted.
- Keep page fades short, optional under reduced motion, and separate from the longer explanatory network animation.

No dataset is uploaded, model is run, or notification is sent by the current design map.
