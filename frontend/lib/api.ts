// Client for the backend analysis endpoints (backend/app/analysis.py) and the ML service's spin routes
// (food-risk-ml/src/api/spin.py). Pages without ?analysis=<id> show demo data.
import { useEffect, useState } from "react";
import type { DemoFinding } from "@/app/analysis-results/demo-findings";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ML_URL = process.env.NEXT_PUBLIC_ML_URL ?? "http://localhost:8100";

type Evidence = { source_record_id: string; field: string; observed_value: number | string; threshold_value?: number | null; unit?: string | null };
type ApiFinding = { finding_id: string; batch_id: string; shipment_id: string | null; anomaly_type: string; severity: string; summary: string; evidence: Evidence[] };
export type GraphNode = { id: string; kind: "root" | "route" | "batch" | "recipient"; label: string; detail?: string | null; flagged?: boolean };
export type Graph = { nodes: GraphNode[]; edges: [string, string][] };

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new Error(`Cannot reach the service at ${new URL(url).origin}.`);
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(typeof body?.detail === "string" ? body.detail : `Request failed (${response.status}).`);
  return body as T;
}

// Work starts on the upload page and the ML process animation waits for it, then goes to the href it resolves to.
// Client-side navigation keeps this module, and the promise, alive between pages.
let pending: Promise<string> | null = null;

function setPending(work: Promise<string>) {
  pending = work;
  pending.catch(() => {}); // handled when the animation finishes; avoids an unhandled-rejection warning meanwhile
}

export function startUpload(file: File | Promise<File>) {
  setPending(Promise.resolve(file).then((f) => {
    const form = new FormData();
    form.append("file", f);
    return request<{ analysis_id: string }>(`${API_URL}/api/analyses`, { method: "POST", body: form });
  }).then((r) => withAnalysis("/analysis-results", r.analysis_id)));
}

export function finishAnalysis(go: (href: string) => void) {
  if (!pending) return go("/analysis-results");
  pending.then(go, (e: Error) => go(`/?error=${encodeURIComponent(e.message)}`));
}

// A product family (raw poultry, raw beef, ready-to-eat) and every pathogen model that applies to it.
export type ReelField = { name: string; label: string; options: string[] };
export type FamilyInfo = { key: string; name: string; models: { key: string; pathogen: string }[]; fields: ReelField[] };
export type Catalog = { families: FamilyInfo[]; labels: Record<string, string>; unavailable: Record<string, string> };
export type SampleRecord = { sample_date: string; product_category: string | null; establishment_id: string | null; metadata: Record<string, string | number | null> };
export type Contribution = { feature: string; source_feature: string; input_value: string | null; contribution: number };
export type PathogenResult = {
  model: string;
  pathogen: string;
  actual: "positive" | "negative" | null; // null for edited or random samples: no lab result applies
  prediction: {
    model_version: string;
    probability_positive: number;
    risk_band: "high" | "medium" | "low";
    threshold: number;
    explanation: Contribution[] | null;
    explanation_units: string | null;
    disclaimer: string;
  };
};
export type SampleRun = {
  family: string;
  name: string;
  sample_id: string | null;
  sample: SampleRecord;
  window: { start: string; end: string };
  results: PathogenResult[]; // one per model for the product, never combined into one score
};
export type Tally = { samples: number; positives: number; flagged: number; flaggedPositives: number };
export type Tallies = { byModel: Record<string, Tally>; ids: string[] };
export type StoredRun = { result: SampleRun; labels: Record<string, string>; tallies: Tallies };

const json = { method: "POST", headers: { "Content-Type": "application/json" } };
// Display form of a sample field. The models need the raw value (the beef models lower-case their text), so this is
// for showing only: states in capitals, text fields capitalised, the "__unknown__" placeholder as "not recorded".
export function displayValue(field: string, value: string) {
  if (value === "__unknown__") return "not recorded";
  if (field.endsWith("establishment_state")) return value.toUpperCase();
  return field.startsWith("meta_cat_") ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

export const getCatalog = () =>request<Catalog>(`${ML_URL}/models`);
export const spinSample = () => request<SampleRun>(`${ML_URL}/models/spin`, { ...json, body: "{}" });
export const predictSample = (family: string, sample: SampleRecord) =>
  request<SampleRun>(`${ML_URL}/models/predict?family=${encodeURIComponent(family)}`, { ...json, body: JSON.stringify(sample) });

const RUN_KEY = "tracefront:sample-run";
const TALLY_KEY = "tracefront:spin-tallies";
let lastRun: StoredRun | null = null; // fallback when session storage is blocked

function readJson<T>(key: string): T | null {
  try {
    const value = sessionStorage.getItem(key);
    return value ? (JSON.parse(value) as T) : null;
  } catch {
    return null;
  }
}

function writeJson(key: string, value: unknown) {
  try {
    sessionStorage.setItem(key, JSON.stringify(value));
  } catch {
    // storage blocked or full: the result still shows from memory during client-side navigation
  }
}

// Real, unedited samples count once each toward a per-pathogen session tally, so judging a model never rests on one spin.
export function startSampleRun(run: Promise<SampleRun>, labels: Record<string, string>) {
  setPending(run.then((result) => {
    let tallies = readJson<Tallies>(TALLY_KEY) ?? { byModel: {}, ids: [] };
    if (result.sample_id && !tallies.ids.includes(result.sample_id)) {
      const byModel = { ...tallies.byModel };
      for (const r of result.results) {
        if (!r.actual) continue;
        const t = byModel[r.model] ?? { samples: 0, positives: 0, flagged: 0, flaggedPositives: 0 };
        const positive = r.actual === "positive";
        const flagged = r.prediction.risk_band === "high";
        byModel[r.model] = {
          samples: t.samples + 1,
          positives: t.positives + Number(positive),
          flagged: t.flagged + Number(flagged),
          flaggedPositives: t.flaggedPositives + Number(positive && flagged),
        };
      }
      tallies = { byModel, ids: [...tallies.ids, result.sample_id] };
      writeJson(TALLY_KEY, tallies);
    }
    lastRun = { result, labels, tallies };
    writeJson(RUN_KEY, lastRun);
    return "/analysis-results?prediction=1";
  }));
}

export function readStoredRun() {
  return lastRun ?? readJson<StoredRun>(RUN_KEY);
}

export function withAnalysis(path: string, id: string | null) {
  return id ? `${path}?analysis=${encodeURIComponent(id)}` : path;
}

const TYPES: Record<string, [type: string, title: string]> = {
  temperature_excursion: ["Temperature", "Cold-chain temperature out of range"],
  shipment_delay: ["Delivery", "Shipment arrived later than planned"],
  humidity_excursion: ["Humidity", "Humidity exceeded the review limit"],
  quantity_mismatch: ["Quantity", "Received quantity did not match dispatch"],
  sensor_gap: ["Sensor coverage", "Temperature log has a gap"],
  destination_mismatch: ["Destination", "Destination codes need reconciliation"],
};
const SEVERITY: Record<string, DemoFinding["severity"]> = { high: "High", medium: "Medium", low: "Low" };

function withUnit(value: number | string, unit?: string | null) {
  if (unit === "C") return `${value}°C`;
  if (unit === "%") return `${value}%`;
  return unit ? `${value} ${unit}` : String(value);
}

function toUiFinding(f: ApiFinding, index: number): DemoFinding {
  const [type, title] = TYPES[f.anomaly_type] ?? ["Other", "Finding to review"];
  const [main, other] = f.evidence;
  return {
    id: String(index + 1).padStart(2, "0"),
    type,
    severity: SEVERITY[f.severity] ?? "Unknown",
    title,
    batchId: f.batch_id,
    shipmentId: f.shipment_id ?? "Batch-level",
    reason: f.summary,
    observed: withUnit(main.observed_value, main.unit),
    reviewLimit: main.threshold_value != null ? `${withUnit(main.threshold_value, main.unit)} maximum`
      : other ? `${other.observed_value} (${other.field.replace(/_/g, " ")})` : "—",
    sourceRecord: main.source_record_id,
  };
}

export async function getFindings(id: string) {
  const doc = await request<{ findings: ApiFinding[] }>(`${API_URL}/api/analyses/${encodeURIComponent(id)}/findings`);
  return doc.findings.map(toUiFinding);
}

export function getDistribution(id: string) {
  return request<Graph>(`${API_URL}/api/analyses/${encodeURIComponent(id)}/distribution`);
}

// Loads data for ?analysis=<id>, or returns the demo fixture when the page was opened without one.
export function useAnalysis<T>(load: (id: string) => Promise<T>, demo: T) {
  const [state, setState] = useState<{ id: string | null; data: T | null; error: string }>({ id: null, data: null, error: "" });
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("analysis");
    if (!id) return setState({ id: null, data: demo, error: "" });
    let live = true;
    load(id).then(
      (data) => { if (live) setState({ id, data, error: "" }); },
      (e: Error) => { if (live) setState({ id, data: null, error: e.message }); },
    );
    return () => { live = false; };
  }, [load, demo]);
  return state;
}
