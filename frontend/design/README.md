# Tracefront design workspace

The existing Next.js app serves the first upload screen at `/` and the design map at `/design`. The earlier supplier-report dashboard remains at `/reports`. React components shared by future screens live in `../components/design/`. The two original HTML mockups are archived in `reference/` as design inputs, not runtime pages. The approved image mockup for page one is in `mockups/page-01-upload.png`.

## Screen mapping

| New screen | Mockup material to carry forward | Product decision |
| --- | --- | --- |
| 1. Upload | File well and one centered upload action | The button opens the step-two demo overlay. Drag-and-drop checks a local file extension; no server upload is connected yet. |
| 2. Confirm | Dark overlay, floating dialog, and Windows-style demo picker | The current dialog demonstrates a sample file already selected. Real column detection and validation are future work. |
| 3. Analyze | Circular correlation motif | The step-two confirmation fades into `/ml-process`, which shows the circle as an illustration. Actual ingestion, inference, retrieval, and graph tracing remain separate services to build. |
| 4. Distribution | Recipient and route cards | Show known destinations and buyers for the selected batch. |
| 5. Anomalies | Anomaly cards and network view | Show evidence and the affected batch-specific downstream graph. |
| 6. Response | Contact and notification panel | Keep an early precautionary warning separate from the update based on an official lab result; require human approval. |

Each numbered page remains a separate screen, matching the team's preferred segmented journey.

## Candidate component boundaries

- `WorkflowSteps` and `StageCard` provide shared navigation and design language now.
- The root upload page currently owns local file selection and extension checks. Column mapping and server upload are future work.
- `AnalysisProgress` will present actual backend job state alongside the circular animation.
- `AnomalyList` and `SupplyChainGraph` will share batch IDs and a selected anomaly.
- `NotificationReview` will prepare separate early and post-lab messages, with explicit approval and delivery status.

## Data and claims to settle before implementation

- The supplier file needs batch IDs, shipment IDs, product/ingredient IDs, origin, destination, buyer, timestamps, temperature readings, and quantities. Validate or map real incoming columns before displaying a record count.
- Historical openFDA recall records can provide reference patterns. They cannot prove that a particular uploaded shipment was contaminated; the supplier file and official lab result provide different evidence.
- Avoid the mockups' fixed correlation coefficients, 142 kitchens, four alerts, and simulated delivery confirmations unless a clearly labeled demo fixture backs them.
- Copy, English terminology, and stage ownership are deliberately open for team review before the six mockup pages are converted.
- Keep page fades short, optional under reduced motion, and separate from the longer explanatory network animation.

No dataset is uploaded, model is run, or notification is sent by the current design preview. The Windows-style picker is simulated and clearly labeled as a demo. The fade to `/ml-process` leads to the existing illustrative animation.
