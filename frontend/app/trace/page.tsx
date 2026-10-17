"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getFindings, getTraceBatches, recordDecision, seedTraceDemo, traceLots, withAnalysis } from "@/lib/api";
import type { Decision, HoldScope, TraceBatch, TraceDocument } from "@/lib/api";
import type { DemoFinding } from "../analysis-results/demo-findings";

const code = (batch: TraceBatch) => batch.lot_code ?? `Batch ${batch.batch_id}`;
const SCOPES: Record<HoldScope, [title: string, description: string]> = {
  targeted: ["Targeted hold", "The lots under investigation and anything made from them."],
  extended: ["Extended hold", "Everything in this trace, including shared ingredients and other products made from them."],
};

// Shipments covered by the latest decision for this selection, if it approved a hold.
const heldBy = (trace: TraceDocument) => new Set(trace.decisions[0]?.decision === "approved" ? trace.decisions[0].shipment_ids : []);

function DecisionPanel({ trace, label, analysisId, onRecorded }: { trace: TraceDocument; label: (id: number) => string; analysisId: string | null; onRecorded: (d: Decision) => void }) {
  const { recommended, basis, note, options } = trace.containment;
  // With no upstream lots both options hold the same stock; offer one choice rather than two identical ones.
  const same = options.targeted.shipment_ids.join() === options.extended.shipment_ids.join() && options.targeted.batch_ids.join() === options.extended.batch_ids.join();
  const scopes: HoldScope[] = same ? ["targeted"] : ["targeted", "extended"];
  const [scope, setScope] = useState<HoldScope>(recommended);
  const [officer, setOfficer] = useState("");
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const codeOf = (id: number) => trace.shipments.find((s) => s.shipment_id === id)?.shipment_code ?? String(id);

  async function decide(decision: Decision["decision"]) {
    if (!officer.trim() || !reason.trim()) return setError("Enter the officer name and a reason before recording a decision.");
    setSaving(true); setError("");
    try {
      onRecorded(await recordDecision({ batch_ids: trace.selected_batch_ids, scope, decision, officer: officer.trim(), reason: reason.trim(), analysis_id: analysisId }));
      setReason("");
    } catch (e) { setError((e as Error).message); }
    finally { setSaving(false); }
  }

  return <section aria-labelledby="decision-heading" className="mt-5 rounded-2xl border border-slate-900 bg-white p-5">
    <div className="flex flex-wrap items-baseline justify-between gap-2"><h2 id="decision-heading" className="text-lg font-semibold">Containment decision</h2><p className="text-xs font-semibold text-amber-800">{note}</p></div>
    <p className="mt-2 text-sm leading-6 text-slate-700"><strong>Recommended: {SCOPES[recommended][0].toLowerCase()}.</strong> {basis}</p>
    <form onSubmit={(e) => { e.preventDefault(); decide(((e.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null)?.value === "rejected" ? "rejected" : "approved"); }}>
      <fieldset className={`mt-4 grid gap-3 ${same ? "" : "sm:grid-cols-2"}`}><legend className="sr-only">Hold scope</legend>
        {scopes.map((key) => {
          const ships = trace.shipments.filter((s) => options[key].shipment_ids.includes(s.shipment_id));
          const moving = ships.filter((s) => s.status === "pending" || s.status === "in_transit").length;
          return <label key={key} className={`cursor-pointer rounded-xl border p-4 ${scope === key ? "border-rose-500 bg-rose-50" : "border-slate-200 hover:border-slate-400"}`}>
            <span className="flex items-center gap-2"><input type="radio" name="scope" checked={scope === key} onChange={() => setScope(key)} className="accent-rose-600" /><strong className="text-sm">{SCOPES[key][0]}</strong>{key === recommended && <span className="rounded-full bg-slate-900 px-2 py-0.5 text-[10px] font-semibold text-white">Recommended</span>}</span>
            <span className="mt-1 block text-xs text-slate-600">{SCOPES[key][1]}</span>
            <span className="mt-3 block text-xs"><strong>{options[key].batch_ids.length}</strong> lots · <strong>{ships.length}</strong> shipments · <strong>{new Set(ships.map((s) => s.to_org_id)).size}</strong> receiving sites</span>
            <span className="mt-1 block text-[11px] text-slate-500">{moving} pending or in transit can be stopped · {ships.length - moving} delivered need a hold at the site</span>
            <span className="mt-2 block text-[11px] text-slate-500">{options[key].batch_ids.map(label).join(", ")}</span>
          </label>;
        })}
        {same && <p className="text-[11px] text-slate-500">No upstream ingredient is recorded for this selection, so an extended hold would cover the same stock.</p>}
      </fieldset>
      <div className="mt-4 grid gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <label className="text-xs font-semibold">Officer<input value={officer} onChange={(e) => setOfficer(e.target.value)} required maxLength={100} autoComplete="name" className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
        <label className="text-xs font-semibold">Reason<textarea value={reason} onChange={(e) => setReason(e.target.value)} required maxLength={500} rows={2} className="mt-1 block w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal" /></label>
      </div>
      {error && <p role="alert" className="mt-3 text-sm text-rose-800">{error}</p>}
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="submit" value="approved" disabled={saving} className="rounded-xl bg-rose-600 px-5 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 disabled:opacity-50">Approve {SCOPES[scope][0].toLowerCase()}</button>
        <button type="submit" value="rejected" disabled={saving} className="rounded-xl border border-slate-300 px-5 py-2.5 text-sm font-semibold hover:border-slate-900 disabled:opacity-50">Reject recommendation</button>
      </div>
    </form>
    <h3 className="mt-6 text-sm font-semibold">Decision history</h3>
    {!trace.decisions.length ? <p className="mt-2 text-xs text-slate-500">No decision has been recorded for this selection.</p> : <ol className="mt-2 space-y-2">{trace.decisions.map((d) => <li key={d.decision_id} className="rounded-xl border border-slate-200 px-4 py-3 text-xs">
      <p><strong className={d.decision === "approved" ? "text-rose-700" : "text-slate-700"}>{d.decision === "approved" ? "Approved" : "Rejected"} {SCOPES[d.scope][0].toLowerCase()}</strong> · {d.officer} · {new Date(d.decided_at).toLocaleString()}</p>
      <p className="mt-1 text-slate-600">{d.reason}</p>
      <p className="mt-1 text-[11px] text-slate-500">{d.shipment_ids.length} shipments: {d.shipment_ids.map(codeOf).join(", ") || "none recorded"}</p>
      {d.analysis_id && <Link href={`${withAnalysis("/analysis-results", d.analysis_id)}#findings`} className="mt-1 inline-block text-[11px] font-semibold text-slate-700 underline decoration-slate-300 underline-offset-2 hover:text-rose-700">Started from upload {d.analysis_id}</Link>}
    </li>)}</ol>}
  </section>;
}

function LotNetwork({ trace }: { trace: TraceDocument }) {
  const held = heldBy(trace);
  const selected = new Set(trace.selected_batch_ids);
  const upstream = new Set(trace.upstream);
  const columns = [trace.batches.filter((b) => upstream.has(b.batch_id)),
    trace.batches.filter((b) => !upstream.has(b.batch_id)),
    trace.shipments];
  const height = Math.max(280, ...columns.map((rows) => 70 + rows.length * 66));
  const positions = new Map<number, { x: number; y: number }>();
  columns.slice(0, 2).forEach((rows, col) => rows.forEach((row, i) => {
    if ("batch_id" in row) positions.set(row.batch_id, { x: 24 + col * 340, y: 58 + i * 66 });
  }));
  const curve = (x: number, y: number, x2: number, y2: number) => `M${x},${y} C${x + 48},${y} ${x2 - 48},${y2} ${x2},${y2}`;
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-[#f8fafc]">
      <div className="relative mx-auto w-[1040px]" style={{ height }}>
        {["Ingredient lots", "Products under review", "Recorded movements"].map((label, i) => <p key={label} className="absolute top-5 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500" style={{ left: 24 + i * 340 }}>{label}</p>)}
        <svg aria-hidden="true" className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 1040 ${height}`} preserveAspectRatio="none">
          {trace.edges.map(([a, b]) => {
            const from = positions.get(a), to = positions.get(b);
            if (!from || !to) return null;
            return <path key={`${a}-${b}`} d={curve(from.x + 270, from.y + 24, to.x, to.y + 24)} fill="none" stroke={selected.has(b) ? "#e11d48" : "#cbd5e1"} strokeWidth="1.5" />;
          })}
          {trace.shipments.map((ship, i) => {
            const from = positions.get(ship.batch_id);
            return from && <path key={`ship-${ship.shipment_id}`} d={curve(from.x + 270, from.y + 24, 704, 82 + i * 66)} fill="none" stroke="#cbd5e1" strokeWidth="1" />;
          })}
        </svg>
        {trace.batches.map((batch) => {
          const p = positions.get(batch.batch_id)!;
          return <div key={batch.batch_id} style={{ left: p.x, top: p.y }} className={`absolute w-[270px] rounded-xl border px-3 py-2 ${selected.has(batch.batch_id) ? "border-rose-400 bg-rose-50" : upstream.has(batch.batch_id) ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white"}`}>
            <p className="truncate text-xs font-semibold"><span className="mr-2 font-mono">{code(batch)}</span>{batch.product_name}</p>
            <p className="mt-0.5 truncate text-[10px] text-slate-600">{batch.organization_name}{selected.has(batch.batch_id) ? " · selected" : ""}</p>
          </div>;
        })}
        {trace.shipments.map((ship, i) => <div key={ship.shipment_id} style={{ left: 704, top: 58 + i * 66 }} className={`absolute w-[310px] rounded-xl border px-3 py-2 ${held.has(ship.shipment_id) ? "border-rose-400 bg-rose-50" : "border-sky-200 bg-sky-50"}`}>
          <p className="truncate text-xs font-semibold">{ship.to_name} <span className="font-normal text-slate-500">· {ship.shipment_code}</span></p>
          <p className="mt-0.5 truncate text-[10px] text-slate-600">From {ship.from_name} · {held.has(ship.shipment_id) ? "hold approved (simulated)" : ship.status.replace(/_/g, " ")}</p>
        </div>)}
      </div>
    </div>
  );
}

export default function TracePage() {
  const [batches, setBatches] = useState<TraceBatch[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [trace, setTrace] = useState<TraceDocument | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [back, setBack] = useState("/");
  const [analysisId, setAnalysisId] = useState<string | null>(null);
  const [origin, setOrigin] = useState<DemoFinding | null>(null); // the upload finding that opened this investigation

  useEffect(() => {
    let live = true;
    const query = new URLSearchParams(window.location.search);
    const analysis = query.get("analysis");
    const lot = query.get("lot");
    if (analysis) {
      setAnalysisId(analysis);
      setBack(`/distribution?analysis=${encodeURIComponent(analysis)}`);
      // The banner is context only; if the findings cannot load, the trace still works without it.
      getFindings(analysis).then((findings) => { if (live) setOrigin(findings.find((f) => f.batchId === lot) ?? findings[0] ?? null); }, () => {});
    }
    getTraceBatches().then((rows) => {
      if (!live) return;
      setBatches(rows);
      const ids = query.getAll("batch").map(Number).filter((id) => rows.some((b) => b.batch_id === id));
      const matches = lot ? rows.filter((b) => b.lot_code === lot) : [];
      if (ids.length) setSelected(ids);
      else if (matches.length === 1) {
        setSelected([matches[0].batch_id]);
        if (analysis && matches[0].synthetic) setNotice(`Lot ${lot} from your upload matches a stored lot. Its ingredient links, later movements and lab results come from the simulated scenario.`);
      }
      else if (lot) setNotice(matches.length ? `Lot ${lot} belongs to more than one producer. Select the producer below.` : `Lot ${lot} has no stored ingredient links yet. Load the synthetic scenario to connect it, or select a known batch.`);
      setLoading(false);
    }, (e: Error) => { if (live) { setError(e.message); setLoading(false); } });
    return () => { live = false; };
  }, []);

  useEffect(() => {
    if (!selected.length) { setTrace(null); return; }
    let live = true;
    setTrace(null);
    setError("");
    const url = new URL(window.location.href);
    url.searchParams.delete("batch");
    selected.forEach((id) => url.searchParams.append("batch", String(id)));
    window.history.replaceState(null, "", url);
    traceLots(selected).then((data) => { if (live) setTrace(data); }, (e: Error) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [selected]);

  async function loadDemo() {
    setSeeding(true); setError("");
    try {
      const result = await seedTraceDemo();
      const rows = await getTraceBatches();
      setBatches(rows);
      setNotice("Synthetic scenario loaded: lot links, movements and lab results are simulated. Existing records were preserved.");
      // Arriving from an upload, stay on its lot instead of jumping to the scenario's default selection.
      const lot = new URLSearchParams(window.location.search).get("lot");
      const matches = lot ? rows.filter((b) => b.lot_code === lot) : [];
      setSelected(matches.length === 1 ? [matches[0].batch_id] : result.selected_batch_ids);
    } catch (e) { setError((e as Error).message); }
    finally { setSeeding(false); }
  }

  function toggle(id: number) {
    if (selected.length === 1 && selected[0] === id) {
      const url = new URL(window.location.href);
      url.searchParams.delete("batch");
      url.searchParams.delete("lot");
      window.history.replaceState(null, "", url);
    }
    setSelected((ids) => ids.includes(id) ? ids.filter((value) => value !== id) : ids.length < 20 ? [...ids, id] : ids);
  }
  const byId = new Map(batches.map((batch) => [batch.batch_id, batch]));
  const label = (id: number) => byId.has(id) ? code(byId.get(id)!) : String(id);
  const positives = trace ? [...new Set([...trace.lab_results, ...trace.positive_elsewhere].filter((lab) => lab.result === "positive").map((lab) => lab.batch_id))].sort((a, b) => a - b) : [];

  return <main className="min-h-dvh bg-[#f7f9fb] text-[#0d293b]">
    <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex h-14 max-w-screen-2xl items-center justify-between px-5 sm:px-8">
      <Link href="/" aria-label="TraceFront home"><Image src="/tracefront-logo-black.png" alt="TraceFront" width={140} height={50} className="h-11 w-auto" /></Link>
      <Link href={back} className="rounded-full border border-slate-300 px-4 py-2 text-xs font-semibold hover:border-slate-900">← Back</Link>
    </div></header>
    <div className="mx-auto max-w-screen-2xl px-5 py-7 sm:px-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><p className="text-[10px] font-bold uppercase tracking-[0.22em] text-rose-700">TraceFront / Investigation</p><h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">Follow the lot. Find the connections.</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Select products under investigation to trace their ingredients and find related stock across factories and receiving sites.</p></div>
        <button onClick={loadDemo} disabled={seeding || loading} className="rounded-xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">{seeding ? "Loading scenario…" : "Load synthetic scenario"}</button>
      </div>
      {origin && <div className="mt-5 rounded-xl border border-rose-200 bg-white px-4 py-3 text-sm leading-6">
        <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-rose-700">Started from upload finding {origin.id}</p>
        <p className="mt-1"><strong>{origin.title}</strong> · lot <span className="font-mono">{origin.batchId}</span> · <span className="font-mono">{origin.shipmentId}</span></p>
        <p className="text-slate-600">{origin.reason}</p>
      </div>}
      {notice && <p role="status" className="mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">{notice}</p>}
      {error && <p role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}
      <section aria-labelledby="select-heading" className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-2"><h2 id="select-heading" className="text-sm font-semibold">Products under investigation</h2><span className="text-xs text-slate-500">{selected.length} selected · selection does not confirm contamination</span></div>
        {loading ? <p role="status" className="mt-4 text-sm text-slate-500">Loading stored batches…</p> : !batches.length ? <p className="mt-4 text-sm text-slate-600">No batches have been recorded. Load the synthetic scenario to explore a complete trace.</p> : <div className="mt-4 flex max-h-52 flex-wrap gap-2 overflow-y-auto">
          {batches.map((batch) => <label key={batch.batch_id} className={`flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-xs ${selected.includes(batch.batch_id) ? "border-rose-400 bg-rose-50" : "border-slate-200 hover:border-slate-400"}`}>
            <input type="checkbox" checked={selected.includes(batch.batch_id)} onChange={() => toggle(batch.batch_id)} className="accent-rose-600" /><span><strong>{code(batch)}</strong> · {batch.product_name}<span className="mt-0.5 block text-[10px] text-slate-500">{batch.organization_name}{batch.synthetic ? " · simulated" : ""}</span></span>
          </label>)}
        </div>}
      </section>
      {!!selected.length && !trace && !error && <p role="status" className="mt-8 text-sm text-slate-500">Following ingredient and shipment records…</p>}
      {trace && <>
        <div className="mt-6 grid gap-3 sm:grid-cols-3">
          {[[trace.upstream.length, "upstream ingredient lots"], [trace.related.length, "other connected products"], [new Set(trace.shipments.map((s) => s.to_org_id)).size, "receiving locations in this trace"]].map(([number, text]) => <div key={text} className="rounded-2xl border border-slate-200 bg-white px-5 py-4"><strong className="text-3xl font-light tabular-nums">{number}</strong><p className="mt-1 text-xs text-slate-500">{text}</p></div>)}
        </div>
        {!!trace.positive_elsewhere.length && <section aria-labelledby="elsewhere-heading" className="mt-5 rounded-2xl border border-amber-300 bg-amber-50 p-5">
          <h2 id="elsewhere-heading" className="text-sm font-semibold text-amber-950">Positive results this selection does not explain</h2>
          <ul className="mt-2 space-y-1 text-xs text-amber-950">{trace.positive_elsewhere.map((lab) => <li key={lab.lab_result_id}><strong>{code(lab.batch)}</strong> · {lab.batch.product_name} · {lab.batch.organization_name} · {lab.contaminant ?? "Unspecified test"} {lab.result} · {lab.tested_at.replace("T", " ")}</li>)}</ul>
          <p className="mt-2 text-xs leading-5 text-amber-900">No stored lot link connects these to the current selection. Investigating every positive product together shows whether they share an ingredient.</p>
          <button onClick={() => setSelected(positives)} className="mt-3 rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700">Investigate all {positives.length} positive products together</button>
        </section>}
        <section aria-label="Stored ingredient and shipment network" className="mt-5 rounded-2xl border border-slate-200 bg-white p-4"><LotNetwork trace={trace} /><p className="mt-3 text-xs leading-5 text-slate-500">Amber: upstream ingredient · Rose: selected product · White: connected product · Blue: recorded shipment destination. Lines reflect stored lot links and movements.</p></section>
        <div className="mt-5 grid items-start gap-5 lg:grid-cols-[minmax(300px,0.8fr)_minmax(0,1.2fr)]">
          <section className="rounded-2xl border border-slate-200 bg-white p-5"><h2 className="text-lg font-semibold">Ingredients to investigate</h2><p className="mt-1 text-xs leading-5 text-slate-500">Ranked by how many selected products share the ingredient, then closeness in the lot chain.</p>
            {!trace.source_ranking.length && <p className="mt-4 text-sm text-slate-600">No upstream ingredient links are recorded for this selection.</p>}
            <ol className="mt-4 space-y-2">{trace.source_ranking.map((r, i) => <li key={r.batch_id} className={`rounded-xl border p-3 ${r.flagged_product_count > 1 ? "border-amber-300 bg-amber-50" : "border-slate-200"}`}>
              <div className="flex items-center justify-between gap-2"><strong className="text-sm">{i + 1}. {label(r.batch_id)}</strong><span className="rounded-full bg-white px-2 py-1 text-[10px] font-semibold">{r.flagged_product_count} / {trace.selected_batch_ids.length} products</span></div><p className="mt-1 text-xs text-slate-600">{byId.get(r.batch_id)?.product_name} · {byId.get(r.batch_id)?.organization_name}</p><p className="mt-2 text-[11px] text-slate-500">Linked to {r.matched_batch_ids.map(label).join(", ")}</p>
            </li>)}</ol><p className="mt-4 border-t border-slate-100 pt-3 text-xs leading-5 text-slate-500">{trace.interpretation}</p>
          </section>
          <section className="min-w-0 rounded-2xl border border-slate-200 bg-white p-5"><h2 className="text-lg font-semibold">Where the connected stock moved</h2><p className="mt-1 text-xs text-slate-500">Shipment quantities describe movements; they are not current inventory totals.</p>
            <div className="mt-4 overflow-x-auto"><table className="w-full text-left text-xs"><thead className="border-b border-slate-200 text-[10px] uppercase tracking-wide text-slate-500"><tr>{["Lot / shipment", "Movement", "Quantity", "Status"].map((s) => <th key={s} className="px-2 py-3 font-semibold">{s}</th>)}</tr></thead><tbody>{trace.shipments.map((s) => <tr key={s.shipment_id} className="border-b border-slate-100"><td className="whitespace-nowrap px-2 py-3"><strong>{label(s.batch_id)}</strong><span className="mt-1 block text-[10px] text-slate-500">{s.shipment_code}</span></td><td className="min-w-[150px] px-2 py-3">{s.from_name}<span className="mt-1 block text-slate-500">→ {s.to_name}</span></td><td className="whitespace-nowrap px-2 py-3">{s.quantity.toLocaleString()} {s.quantity_unit ?? "(unit not recorded)"}</td><td className="whitespace-nowrap px-2 py-3">{s.status.replace(/_/g, " ")}{heldBy(trace).has(s.shipment_id) && <span className="mt-1 block w-fit rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold text-rose-800">Hold approved · simulated</span>}</td></tr>)}</tbody></table>{!trace.shipments.length && <p className="py-4 text-sm text-slate-500">No shipment locations have been recorded.</p>}</div>
          </section>
        </div>
        {!!trace.lab_results.length && <section className="mt-5 rounded-2xl border border-slate-200 bg-white p-5"><h2 className="text-sm font-semibold">Recorded laboratory evidence</h2><ul className="mt-3 space-y-2 text-xs">{trace.lab_results.map((lab) => <li key={lab.lab_result_id}><strong>{label(lab.batch_id)}</strong> · {lab.contaminant ?? "Unspecified test"} · <span className={lab.result === "positive" ? "font-semibold text-rose-700" : "text-slate-600"}>{lab.result}</span> · {lab.tested_at.replace("T", " ")}</li>)}</ul></section>}
        <DecisionPanel key={trace.selected_batch_ids.join(",")} trace={trace} label={label} analysisId={analysisId} onRecorded={(d) => setTrace((t) => t && { ...t, decisions: [d, ...t.decisions] })} />
      </>}
    </div>
  </main>;
}
