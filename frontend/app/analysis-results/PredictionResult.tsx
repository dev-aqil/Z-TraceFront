"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { displayValue, readStoredRun } from "@/lib/api";
import type { Contribution, PathogenResult, StoredRun, Tally } from "@/lib/api";

const REVEAL_DELAY_MS = 1400;
const BAND_STYLE = { high: "bg-rose-600 text-white", medium: "bg-amber-100 text-amber-900", low: "bg-slate-200 text-slate-800" };

function percent(p: number) {
  return `${(p * 100).toFixed(p < 0.01 ? 2 : 1)}%`;
}

function shown(value: string | number | null | undefined) {
  if (value == null || value === "") return "not recorded";
  const n = Number(value);
  return Number.isFinite(n) && !Number.isInteger(n) ? n.toFixed(3) : String(value);
}

function times(ratio: number) {
  return ratio >= 10 ? ratio.toFixed(0) : ratio >= 0.1 ? ratio.toFixed(1) : "<0.1";
}

// A one-hot explanation can be about a category the sample is NOT in; say so instead of misstating its value.
function reason(c: Contribution, labels: Record<string, string>) {
  const label = labels[c.source_feature] ?? c.source_feature;
  const category = c.feature.startsWith(`${c.source_feature}_`) ? c.feature.slice(c.source_feature.length + 1) : null;
  if (category === "infrequent_sklearn") return { label, value: "rare-category group" };
  if (category !== null && category.toLowerCase() !== (c.input_value ?? "").toLowerCase()) return { label, value: `not “${displayValue(c.source_feature, category)}”` };
  return { label, value: shown(c.input_value == null ? c.input_value : displayValue(c.source_feature, c.input_value)) };
}

function verdict(r: PathogenResult) {
  const flagged = r.prediction.risk_band === "high";
  const positive = r.actual === "positive";
  if (flagged && positive) return "Flagged high, and it tested positive.";
  if (flagged) return "Flagged high, but it tested negative. Most flagged samples test negative: the model ranks where to sample next, it does not detect contamination.";
  return positive ? "Missed: it tested positive but was not flagged high." : "Not flagged high, and it tested negative.";
}

function PathogenCard({ result, labels, tally, revealed }: { result: PathogenResult; labels: Record<string, string>; tally?: Tally; revealed: boolean }) {
  const p = result.prediction;
  const probability = p.probability_positive;
  const scale = Math.max(probability, p.threshold) * 1.6;
  const reasons = (p.explanation ?? []).slice(0, 3);
  const largest = Math.max(...reasons.map((r) => Math.abs(r.contribution)), 1e-9);
  const positive = result.actual === "positive";
  const headingId = `pathogen-${result.model}`;

  return (
    <section aria-labelledby={headingId} className="flex flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 id={headingId} className="text-xl font-semibold tracking-tight">{result.pathogen}</h2>
      <p className="mt-0.5 font-mono text-[11px] text-slate-500">{p.model_version}</p>

      <p className="mt-4 text-sm font-medium text-slate-600">Probability this lab sample tests positive</p>
      <div className="mt-1 flex flex-wrap items-end gap-3">
        <span className="text-5xl font-light tabular-nums tracking-tight">{percent(probability)}</span>
        <span className={`mb-1.5 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide ${BAND_STYLE[p.risk_band]}`}>{p.risk_band} risk</span>
      </div>
      {/* Pathogens differ in how often they test positive, so raw percentages don't compare across cards; the
          distance to each model's own high-risk line does, and it always agrees with the badge. */}
      <p className="mt-1 text-sm text-slate-700"><strong className="font-semibold">{times(probability / p.threshold)}×</strong> this model&apos;s high-risk line</p>
      <div className="relative mt-4 h-2.5 rounded-full bg-slate-200" aria-hidden="true">
        <div className="h-full rounded-full bg-rose-600" style={{ width: `${Math.min(100, (probability / scale) * 100)}%` }} />
        <div className="absolute -top-1.5 h-5 w-0.5 bg-slate-900" style={{ left: `${(p.threshold / scale) * 100}%` }} />
      </div>
      <p className="mt-2 text-xs leading-5 text-slate-600">The black line is the {percent(p.threshold)} threshold for “high”, chosen on validation data.</p>

      <h3 className="mt-5 text-sm font-semibold">What moved the score</h3>
      {reasons.length ? (
        <ul className="mt-2 space-y-3">
          {reasons.map((c) => {
            const { label, value } = reason(c, labels);
            const up = c.contribution > 0;
            return (
              <li key={c.feature} className="text-sm">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="min-w-0"><strong className="font-semibold">{label}</strong>: <span className="break-words text-slate-700">{value}</span></span>
                  <span className={`shrink-0 text-xs font-semibold ${up ? "text-rose-700" : "text-emerald-700"}`}>{up ? "▲ raised" : "▼ lowered"}</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-slate-100" aria-hidden="true">
                  <div className={`h-full rounded-full ${up ? "bg-rose-400" : "bg-emerald-400"}`} style={{ width: `${(Math.abs(c.contribution) / largest) * 100}%` }} />
                </div>
              </li>
            );
          })}
        </ul>
      ) : <p className="mt-2 text-sm text-slate-600">No explanation is available for this model.</p>}
      {p.explanation_units && <p className="mt-3 text-xs leading-5 text-slate-500">Contributions in {p.explanation_units}, before calibration. They describe the model&apos;s behaviour, not causes of contamination.</p>}

      <div className="mt-5 border-t border-slate-100 pt-4">
        <h3 className="text-sm font-medium text-slate-600">Actual lab result</h3>
        {result.actual ? (
          revealed ? (
            <div role="status">
              <p className={`mt-1 text-3xl font-semibold tracking-tight ${positive ? "text-rose-700" : "text-emerald-700"}`}>{positive ? "Positive" : "Negative"}</p>
              <p className="mt-1 text-sm leading-6 text-slate-700">{verdict(result)}</p>
            </div>
          ) : <p role="status" className="mt-1 text-sm text-slate-500">Revealing the lab result…</p>
        ) : <p className="mt-1 text-sm leading-6 text-slate-700">No lab result applies: the details were edited or randomly mixed, so this is not a real sample.</p>}
        {(revealed || !result.actual) && tally && tally.samples > 0 && (
          <p className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-700">
            <strong className="font-semibold">This session, {tally.samples} real {tally.samples === 1 ? "sample" : "samples"}:</strong> {tally.positives} tested positive and {tally.flaggedPositives} of those were flagged high; {tally.flagged} flagged high in total.
          </p>
        )}
      </div>
    </section>
  );
}

export default function PredictionResult() {
  const [stored, setStored] = useState<StoredRun | null | undefined>(undefined);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => setStored(readStoredRun()), []);

  useEffect(() => {
    if (!stored?.result.sample_id) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return setRevealed(true);
    const timer = setTimeout(() => setRevealed(true), REVEAL_DELAY_MS);
    return () => clearTimeout(timer);
  }, [stored]);

  if (stored === undefined) return null;
  if (!stored) {
    return (
      <main className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-white px-6 text-center text-[#0d293b]">
        <h1 className="text-2xl font-semibold tracking-tight">No model run to show</h1>
        <p className="max-w-md text-sm leading-6 text-slate-600">Spin a sample on the start page, then run the analysis.</p>
        <Link href="/#spin" className="rounded-lg bg-rose-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700">Spin a sample</Link>
      </main>
    );
  }

  const { result, labels, tallies } = stored;
  const several = result.results.length > 1;
  const inputs: [string, string | number | null][] = [
    ["sample_date", result.sample.sample_date],
    ["product_category", result.sample.product_category],
    ["establishment_id", result.sample.establishment_id],
    ...Object.entries(result.sample.metadata),
  ];

  return (
    <main className="min-h-dvh bg-[#f7f9fb] text-[#0d293b]">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-12 max-w-5xl items-center justify-between px-6">
          <Link href="/" aria-label="TraceFront home" className="rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-rose-600">
            <span className="relative block h-10 w-36 overflow-hidden">
              <Image src="/tracefront-logo-black.png" alt="TraceFront" width={2091} height={752} priority className="absolute left-0 top-1/2 h-12 w-auto max-w-none -translate-y-1/2" />
            </span>
          </Link>
          <Link href="/#spin" className="inline-flex h-8 items-center rounded-full border border-slate-300 bg-white px-3 text-xs font-medium text-slate-900 shadow-sm hover:border-slate-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600">Spin another</Link>
        </div>
      </header>

      <div className="mx-auto max-w-5xl px-6 py-8">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-rose-700">Model results</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">{result.name}</h1>
        <p className="mt-1 text-sm text-slate-600">
          {several ? `${result.results.length} pathogen models ran on this sample. Each is scored on its own; they are not combined into one score.` : "One pathogen model applies to this product."}
          {result.sample_id && <span className="font-mono text-xs text-slate-500"> · FSIS sample {result.sample_id}</span>}
        </p>

        <div className={`mt-6 grid gap-4 ${several ? "lg:grid-cols-2" : "max-w-2xl"}`}>
          {result.results.map((r) => <PathogenCard key={r.model} result={r} labels={labels} tally={tallies.byModel[r.model]} revealed={revealed} />)}
        </div>

        <section aria-labelledby="inputs-heading" className="mt-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 id="inputs-heading" className="text-sm font-semibold">Sample details used by {several ? "every model" : "the model"}</h2>
          <dl className="mt-3 grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
            {inputs.map(([name, value]) => (
              <div key={name} className="flex min-w-0 gap-3">
                <dt className="w-36 shrink-0 text-slate-500">{labels[name] ?? name}</dt>
                <dd className="min-w-0 break-words font-mono text-xs leading-5 text-slate-900">{shown(typeof value === "string" ? displayValue(name, value) : value)}</dd>
              </div>
            ))}
          </dl>
        </section>

        <p className="mt-6 text-xs leading-5 text-slate-500">{result.results[0]?.prediction.disclaimer}</p>
        {result.sample_id && <p className="mt-2 text-xs leading-5 text-slate-500">Validation-period sample ({result.window.start} to before {result.window.end}): never used for training, but used to choose the models, calibration and thresholds, so results here run slightly optimistic.</p>}
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href="/#spin" className="rounded-lg bg-rose-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700">Spin another sample</Link>
          <Link href="/" className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-medium hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600">Upload a file instead</Link>
        </div>
      </div>
    </main>
  );
}
