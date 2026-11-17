"use client";

import { useEffect, useState } from "react";
import { acknowledgeHold, getHolds, releaseHold } from "@/lib/api";
import type { Hold, Me } from "@/lib/api";

const when = (iso: string) => new Date(iso).toLocaleString();
const lotList = (hold: Hold) => hold.lots.map((lot) => `${lot.lot_code ?? `Batch ${lot.batch_id}`} ${lot.product_name}`).join(", ");

// Holds in force. A company also sees the holds that were lifted, so a site learns its stock is released.
// `reload` changes when the page records a decision; `onChanged` tells the page a hold changed here.
export default function HoldsPanel({ me, reload, onChanged }: { me: Me; reload: number; onChanged: () => void }) {
  const [holds, setHolds] = useState<Hold[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [lifting, setLifting] = useState<number | null>(null); // the hold whose lift form is open
  const [reason, setReason] = useState("");
  const regulator = me.role === "regulator";

  useEffect(() => {
    let live = true;
    getHolds().then((rows) => { if (live) setHolds(rows); }, (e: Error) => { if (live) setError(e.message); });
    return () => { live = false; };
  }, [reload]);

  async function act(work: Promise<Hold>) {
    setBusy(true); setError("");
    try {
      await work;
      setLifting(null); setReason("");
      onChanged(); // the page reloads its lots and bumps `reload`, which fetches the holds again
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }

  const shown = holds.filter((hold) => !hold.released || !regulator); // an officer finds lifted holds in the decision history
  if (!shown.length && !error) return null;

  return <section aria-labelledby="holds-heading" className="mt-6 rounded-2xl border border-rose-300 bg-white p-5">
    <h2 id="holds-heading" className="text-lg font-semibold">{regulator ? "Holds in force" : "Holds on your stock"}</h2>
    {!regulator && <p className="mt-1 text-xs leading-5 text-slate-600">The Ministry of Health has placed these lots on hold. Acknowledge each hold so the officer knows your site has seen it.</p>}
    {error && <p role="alert" className="mt-3 text-sm text-rose-800">{error}</p>}
    <ul className="mt-3 space-y-3">{shown.map((hold) => {
      const mine = hold.sites.find((site) => site.organization_id === me.organization_id);
      const waiting = hold.sites.filter((site) => !site.acknowledged_at);
      return <li key={hold.decision_id} className={`rounded-xl border px-4 py-3 text-xs leading-5 ${hold.released ? "border-slate-200 bg-slate-50" : "border-rose-200 bg-rose-50"}`}>
        <p><strong className={hold.released ? "text-slate-700" : "text-rose-800"}>{hold.released ? "Hold lifted" : "On hold"}</strong> · hold {hold.decision_id} · decided {when(hold.decided_at)} by {hold.officer}</p>
        <p className="mt-1 text-slate-700">{hold.reason}</p>
        <p className="mt-1 text-slate-700"><strong>{regulator ? "Lots" : "Your lots"}:</strong> {lotList(hold) || "none recorded"}</p>
        {hold.released && <p className="mt-1 text-slate-700">Lifted {when(hold.released.released_at)} by {hold.released.officer}: {hold.released.reason}</p>}

        {!regulator && !hold.released && (mine?.acknowledged_at
          ? <p className="mt-2 font-semibold text-slate-700">Acknowledged by {mine.acknowledged_by} on {when(mine.acknowledged_at)}.</p>
          : <button onClick={() => act(acknowledgeHold(hold.decision_id))} disabled={busy} className="mt-2 rounded-lg bg-rose-600 px-4 py-2 font-semibold text-white hover:bg-rose-700 disabled:opacity-50">Acknowledge this hold</button>)}

        {regulator && <>
          <p className="mt-2 font-semibold text-slate-700">{hold.sites.length - waiting.length} of {hold.sites.length} sites have acknowledged.</p>
          {!!waiting.length && <ul className="mt-1 space-y-0.5 text-slate-700">{waiting.map((site) => <li key={site.organization_id}>
            Waiting: <strong>{site.name}</strong> ({site.type}){[site.contact_name, site.contact_phone, site.contact_email].filter(Boolean).map((detail) => ` · ${detail}`).join("") || " · no contact recorded"}
          </li>)}</ul>}
          {lifting === hold.decision_id
            ? <form onSubmit={(e) => { e.preventDefault(); if (reason.trim()) act(releaseHold(hold.decision_id, reason.trim())); }} className="mt-3">
                <label className="block font-semibold">Reason for lifting the hold<textarea value={reason} onChange={(e) => setReason(e.target.value)} required maxLength={500} rows={2} autoFocus className="mt-1 block w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-normal" /></label>
                <div className="mt-2 flex gap-2">
                  <button type="submit" disabled={busy} className="rounded-lg bg-slate-900 px-4 py-2 font-semibold text-white hover:bg-slate-700 disabled:opacity-50">Lift hold</button>
                  <button type="button" onClick={() => { setLifting(null); setReason(""); }} className="rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold hover:border-slate-900">Cancel</button>
                </div>
              </form>
            : <button onClick={() => { setLifting(hold.decision_id); setReason(""); }} className="mt-3 rounded-lg border border-slate-300 bg-white px-4 py-2 font-semibold hover:border-slate-900">Lift this hold…</button>}
        </>}
      </li>;
    })}</ul>
  </section>;
}
