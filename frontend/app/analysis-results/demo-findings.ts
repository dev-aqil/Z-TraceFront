// Illustrative UI fixture. Replace with validated findings from the ML API.
export type DemoFinding = {
  id: string;
  type: string;
  severity: "High" | "Medium" | "Low" | "Unknown";
  title: string;
  batchId: string;
  shipmentId: string;
  reason: string;
  observed: string;
  reviewLimit: string;
  sourceRecord: string;
};

export const demoFindings: DemoFinding[] = [
  { id: "01", type: "Temperature", severity: "High", title: "Cold-chain temperature exceeded limit", batchId: "RM-402", shipmentId: "SHIP-017", reason: "A shipment sensor recorded 8.4°C, above the 7°C review limit.", observed: "8.4°C", reviewLimit: "7°C maximum", sourceRecord: "sensor-reading-1842" },
  { id: "02", type: "Delivery", severity: "High", title: "Shipment arrived later than planned", batchId: "RM-415", shipmentId: "SHIP-024", reason: "Arrival was 95 minutes late, beyond the 30-minute review limit.", observed: "95 min late", reviewLimit: "30 min maximum", sourceRecord: "delivery-scan-2094" },
  { id: "03", type: "Humidity", severity: "Medium", title: "Packaging humidity exceeded range", batchId: "RM-411", shipmentId: "SHIP-029", reason: "A packaging sensor recorded 83% relative humidity against a 75% limit.", observed: "83% RH", reviewLimit: "75% RH maximum", sourceRecord: "humidity-reading-1128" },
  { id: "04", type: "Quantity", severity: "Medium", title: "Received quantity did not match dispatch", batchId: "RM-426", shipmentId: "SHIP-034", reason: "The receiving record shows 228 cases; the dispatch record lists 240.", observed: "12 cases short", reviewLimit: "240 dispatched", sourceRecord: "receiving-scan-0642" },
  { id: "05", type: "Sensor coverage", severity: "Medium", title: "Temperature log has a gap", batchId: "RM-431", shipmentId: "SHIP-039", reason: "No temperature reading was recorded for 76 minutes during transit.", observed: "76 min gap", reviewLimit: "30 min maximum", sourceRecord: "sensor-stream-039" },
  { id: "06", type: "Destination", severity: "Low", title: "Destination codes need reconciliation", batchId: "RM-436", shipmentId: "SHIP-042", reason: "The delivery scan lists KITCHEN-24; the shipment manifest lists KITCHEN-21.", observed: "2 codes differ", reviewLimit: "Codes should match", sourceRecord: "delivery-scan-2110" },
];
