"use client";

import { useEffect, useRef, useState } from "react";
import { getCatalog, predictSample, spinSample, startSampleRun } from "@/lib/api";
import type { Catalog, FamilyInfo, SampleRecord, SampleRun } from "@/lib/api";

type Values = Record<string, string | null>;
type Landed = { kind: "sample"; run: SampleRun } | { kind: "random" };
type Reel = { text: string; stopped: boolean };

const TOP_LEVEL = ["sample_date", "product_category", "establishment_id"];
const REEL_TICK_MS = 70;
const FIRST_STOP_MS = 700;
const STOP_GAP_MS = 260;

function valuesOf(sample: SampleRecord): Values {
  const values: Values = { sample_date: sample.sample_date, product_category: sample.product_category, establishment_id: sample.establishment_id };
  for (const [name, value] of Object.entries(sample.metadata)) values[name] = value == null ? null : String(value);
  return values;
}

function sampleOf(family: FamilyInfo, values: Values): SampleRecord {
  const metadata: SampleRecord["metadata"] = {};
  for (const field of family.fields) if (!TOP_LEVEL.includes(field.name)) metadata[field.name] = values[field.name] ?? null;
  return { sample_date: values.sample_date ?? "", product_category: values.product_category ?? null, establishment_id: values.establishment_id ?? null, metadata };
}

const pick = <T,>(items: T[]) => items[Math.floor(Math.random() * items.length)];

export default function SpinPanel({ onRun }: { onRun: () => void }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [error, setError] = useState("");
  const [family, setFamily] = useState<FamilyInfo | null>(null);
  const [values, setValues] = useState<Values>({});
  const [reels, setReels] = useState<Record<string, Reel>>({});
  const [spinning, setSpinning] = useState(false);
  const [landed, setLanded] = useState<Landed | null>(null);
  const [edited, setEdited] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval>>();

  useEffect(() => {
    getCatalog().then((c) => {
      if (c.families.length) setCatalog(c);
      else setError(`No model is loaded in the ML service: ${Object.values(c.unavailable).join("; ")}`);
    }, (e: Error) => setError(`${e.message} Start the ML service on port 8100 to spin samples.`));
    return () => clearInterval(timerRef.current);
  }, []);

  // Slot-machine reels: each spins through its real value list, then stops on the drawn value, left to right.
  function spinTo(next: FamilyInfo, final: Values, outcome: Landed) {
    if (!catalog) return;
    clearInterval(timerRef.current);
    const names = ["product", ...next.fields.map((field) => field.name)];
    const finalText = (name: string) => (name === "product" ? next.name : final[name] ?? "(not recorded)");
    const optionsFor = (name: string) => (name === "product" ? catalog.families.map((f) => f.name) : next.fields.find((f) => f.name === name)!.options);
    setFamily(next);
    setValues(final);
    setEdited(false);
    setLanded(null);
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setReels(Object.fromEntries(names.map((name) => [name, { text: finalText(name), stopped: true }])));
      setSpinning(false);
      setLanded(outcome);
      return;
    }
    setSpinning(true);
    const start = performance.now();
    timerRef.current = setInterval(() => {
      const elapsed = performance.now() - start;
      const frame: Record<string, Reel> = {};
      names.forEach((name, i) => {
        const stopped = elapsed >= FIRST_STOP_MS + i * STOP_GAP_MS;
        frame[name] = { text: stopped ? finalText(name) : String(pick(optionsFor(name)) ?? ""), stopped };
      });
      setReels(frame);
      if (Object.values(frame).every((reel) => reel.stopped)) {
        clearInterval(timerRef.current);
        setSpinning(false);
        setLanded(outcome);
      }
    }, REEL_TICK_MS);
  }

  async function spinRealSample() {
    if (!catalog || spinning) return;
    setError("");
    setSpinning(true);
    try {
      const run = await spinSample();
      const next = catalog.families.find((f) => f.key === run.family);
      if (!next) throw new Error(`The ML service returned an unknown product family ${run.family}.`);
      spinTo(next, valuesOf(run.sample), { kind: "sample", run });
    } catch (e) {
      setSpinning(false);
      setError((e as Error).message);
    }
  }

  function spinRandomMix() {
    if (!catalog || spinning) return;
    setError("");
    const next = pick(catalog.families);
    spinTo(next, Object.fromEntries(next.fields.map((field) => [field.name, pick(field.options) ?? null])), { kind: "random" });
  }

  function run() {
    if (!catalog || !family || !landed || spinning) return;
    const real = landed.kind === "sample" && !edited;
    startSampleRun(real ? Promise.resolve(landed.run) : predictSample(family.key, sampleOf(family, values)), catalog.labels);
    onRun();
  }

  const pathogens = family?.models.map((m) => m.pathogen).join(" and ");
  const plural = (family?.models.length ?? 0) > 1;
  const runs = `Runs the ${pathogens} model${plural ? "s" : ""}.`;
  const status = !landed ? null
    : landed.kind === "random" ? `Random mix: not a real sample, so there are no lab results to compare. ${runs}`
    : edited ? `What-if: edited from a real sample, so its lab results no longer apply. ${runs}`
    : `Real FSIS sample from the validation period (${landed.run.window.start} to before ${landed.run.window.end}), never used for training. It was tested for ${pathogens}; ${plural ? "each model is" : "the model is"} scored and the lab result${plural ? "s" : ""} revealed after the analysis.`;

  return (
    <section id="spin" aria-labelledby="spin-title" className="mt-4 rounded-xl border border-slate-200 bg-white px-5 py-4 lg:shrink-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="spin-title" className="text-base font-semibold text-slate-900">Or spin a sample for the pathogen models</h2>
          <p className="mt-0.5 text-sm text-slate-600">Draws one FSIS lab sample&apos;s details; every pathogen model for its product then runs on it.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={spinRealSample} disabled={!catalog || spinning} className="min-h-10 rounded-lg bg-[#0d293b] px-5 py-2 text-sm font-semibold text-white hover:bg-[#16405a] disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600">{spinning ? "Spinning…" : "Spin real sample"}</button>
          <button type="button" onClick={spinRandomMix} disabled={!catalog || spinning} className="min-h-10 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600">Random mix</button>
          <button type="button" onClick={run} disabled={!landed || spinning} className="min-h-10 rounded-lg bg-rose-600 px-5 py-2 text-sm font-semibold text-white hover:bg-rose-700 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700">Run analysis</button>
        </div>
      </div>

      {!catalog && !error && <p role="status" className="mt-3 text-sm text-slate-500">Loading models… the first load takes about 10 seconds.</p>}
      {error && <p role="alert" className="mt-3 text-sm font-medium text-red-700">{error}</p>}

      {family && (
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7" aria-live="polite" aria-busy={spinning}>
          <div className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Product</p>
            <p className={`mt-1 truncate text-sm font-semibold ${reels.product?.stopped === false ? "text-slate-400" : "text-slate-900"}`}>{reels.product?.text ?? family.name}</p>
          </div>
          {family.fields.map((field) => {
            const reel = reels[field.name];
            const id = `reel-${field.name}`;
            return (
              <div key={field.name} className="min-w-0 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <label htmlFor={id} className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">{field.label}</label>
                {landed ? (
                  <select id={id} value={values[field.name] ?? ""} onChange={(event) => { setValues({ ...values, [field.name]: event.target.value || null }); setEdited(true); }} className="mt-1 w-full truncate rounded border border-slate-300 bg-white px-1.5 py-1 font-mono text-xs text-slate-900 focus:border-rose-500 focus:outline-none focus:ring-2 focus:ring-rose-100">
                    <option value="">(not recorded)</option>
                    {field.options.map((option) => <option key={option} value={option}>{option}</option>)}
                  </select>
                ) : (
                  <p id={id} className={`mt-1 truncate font-mono text-xs ${reel?.stopped ? "text-slate-900" : "text-slate-400"}`}>{reel?.text ?? "—"}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
      {status && <p className="mt-2 text-xs leading-5 text-slate-600">{status}</p>}
    </section>
  );
}
