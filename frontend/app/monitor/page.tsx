"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { clearReadings, getMe, getMonitor, seedTraceDemo, sendReading, signOut } from "@/lib/api";
import type { Me, MonitorAlert, MonitorLevel, Monitored } from "@/lib/api";
import TemperatureChart, { clock } from "./TemperatureChart";

const POLL_MS = 5000;
// SHIP-017 of public/supplier_shipments.csv: chilled chicken that warms in transit. SIMULATED readings, for demos only;
// the shipment belongs to the synthetic scenario, so its readings can be cleared afterwards.
const REPLAY_SHIPMENT = 910009;
const REPLAY_C = [2.8, 3.1, 3.6, 4.1, 5.8, 8.0, 9.6, 10.9, 11.4, 11.8, 12.1, 12.0, 11.7, 11.2, 10.6, 9.8, 9.1, 8.4, 8.0, 7.6];
const REPLAY_MS = 1500;

const LEVELS: Record<MonitorLevel, { label: string; color: string; glyph: string; note: string }> = {
  critical: { label: "Critical", color: "#d03b3b", glyph: "white", note: "Danger-zone time is used up. Cooling the load again does not undo it: treat it as unsafe." },
  excursion: { label: "Above limit", color: "#ec835a", glyph: "#0d293b", note: "The latest reading is above this shipment's limit." },
  recovered: { label: "Back in range", color: "#fab219", glyph: "#0d293b", note: "Within the limit again, but it was above it. Review the readings before the load is used." },
  ok: { label: "In range", color: "#0ca30c", glyph: "white", note: "Every reading so far is within the limit." },
};
const RULES: Record<MonitorAlert["rule"], string> = { EXCURSION: "Above limit", CRITICAL: "Critical", DATA_GAP: "Sensor gap" };
const MOVEMENT: Record<string, string> = { pending: "not yet departed", in_transit: "in transit", delivered: "delivered", held: "held" };

function LevelIcon({ level }: { level: MonitorLevel }) {
  const { color, glyph } = LEVELS[level];
  const mark = { stroke: glyph, strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, fill: "none" };
  return <svg aria-hidden viewBox="0 0 16 16" className="h-4 w-4 shrink-0">
    {level === "critical" && <><path d="M5 1h6l4 4v6l-4 4H5l-4-4V5z" fill={color} /><path d="M8 4.5v4M8 11.3v.2" {...mark} /></>}
    {level === "excursion" && <><path d="M8 1.2l7.2 13H.8z" fill={color} /><path d="M8 6v3.6M8 11.8v.1" {...mark} /></>}
    {level === "recovered" && <><circle cx={8} cy={8} r={7} fill={color} /><path d="M8 4.3v6.4M5.4 8.3L8 10.8l2.6-2.5" {...mark} /></>}
    {level === "ok" && <><circle cx={8} cy={8} r={7} fill={color} /><path d="M4.6 8.2l2.3 2.3 4.6-4.7" {...mark} /></>}
  </svg>;
}

const minutes = (n: number) => n < 60 ? `${Math.round(n)} min` : `${Math.floor(n / 60)} h ${Math.round(n % 60)} min`;

function Stat({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="rounded-xl border border-slate-200 px-3 py-2">
    <dt className="text-[11px] text-slate-500">{label}</dt>
    <dd className="text-base font-semibold tabular-nums">{value}</dd>
    <dd className="text-[11px] text-slate-500">{detail}</dd>
  </div>;
}

function ShipmentCard({ item }: { item: Monitored }) {
  const { shipment, lot, level } = item;
  const silent = item.silent_minutes !== null && item.silent_minutes > item.max_gap_minutes;
  const lotCode = lot.lot_code ?? `Batch ${lot.batch_id}`;
  return <article aria-labelledby={`ship-${shipment.shipment_id}`} className="rounded-2xl border border-slate-200 bg-white p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 id={`ship-${shipment.shipment_id}`} className="text-lg font-semibold">{shipment.shipment_code}</h2>
        <p className="mt-1 text-xs text-slate-600">Lot <span className="font-mono">{lotCode}</span> · {lot.product_name}{lot.synthetic && " · simulated scenario"}</p>
        <p className="text-xs text-slate-600">{shipment.from_name} → {shipment.to_name} · {MOVEMENT[shipment.status] ?? shipment.status}</p>
      </div>
      <p className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 px-3 py-1 text-xs font-semibold"><LevelIcon level={level} />{LEVELS[level].label}</p>
    </div>
    <p className="mt-2 text-xs text-slate-600">{LEVELS[level].note}</p>
    {silent && <p className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
      <strong>No reading for {minutes(item.silent_minutes!)}.</strong> The logger may be off or out of signal. Until readings resume, nothing is watching this load.
    </p>}
    <dl className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Stat label="Latest" value={`${item.latest.temperature.toFixed(1)} °C`} detail={clock(item.latest.at)} />
      <Stat label="Peak" value={`${item.peak.temperature.toFixed(1)} °C`} detail={clock(item.peak.at)} />
      <Stat label="Limit" value={`${item.limit_c} °C`} detail={item.profile_name} />
      <Stat label="In the danger zone" value={minutes(item.minutes_in_danger_zone)} detail="USDA limit: 2 h" />
    </dl>
    <TemperatureChart item={item} />
    <h3 className="mt-4 text-sm font-semibold">Alerts</h3>
    {!item.alerts.length ? <p className="mt-1 text-xs text-slate-500">None so far.</p>
      : <ol className="mt-2 space-y-2">{[...item.alerts].reverse().map((alert) => <li key={`${alert.rule}-${alert.time}`} className="rounded-xl border border-slate-200 px-3 py-2 text-xs">
        <p><strong>{RULES[alert.rule]}</strong> · {clock(alert.time)}</p>
        <p className="mt-0.5 text-slate-700">{alert.message}</p>
        <p className="mt-0.5 text-[11px] text-slate-500">{alert.source}</p>
      </li>)}</ol>}
    <Link href={`/trace?batch=${lot.batch_id}`} className="mt-4 inline-block text-xs font-semibold text-slate-700 underline decoration-slate-300 underline-offset-2 hover:text-rose-700">Trace lot {lotCode} and its other shipments →</Link>
  </article>;
}

export default function MonitorPage() {
  const [items, setItems] = useState<Monitored[] | null>(null);
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [updated, setUpdated] = useState<Date | null>(null);
  const [sent, setSent] = useState<number | null>(null); // replay progress; null when no replay is running
  const [clearing, setClearing] = useState(false);
  const stopped = useRef(false);
  const regulator = me?.role === "regulator"; // the server enforces this; here it only hides controls that would be refused

  const load = useCallback(() => getMonitor().then(
    (rows) => { setItems(rows); setUpdated(new Date()); setError(""); },
    (e: Error) => setError(`Live updates paused: ${e.message} Retrying every ${POLL_MS / 1000} seconds.`),
  ), []);

  useEffect(() => {
    getMe().then(setMe, () => {});
    load();
    const timer = setInterval(() => { if (!document.hidden) load(); }, POLL_MS);
    return () => { clearInterval(timer); stopped.current = true; };
  }, [load]);

  async function replay() {
    stopped.current = false;
    setError(""); setNotice(""); setSent(0);
    try {
      await seedTraceDemo(); // SHIP-017 is part of the synthetic scenario; loading it again changes nothing
      for (let i = 0; i < REPLAY_C.length && !stopped.current; i++) {
        // A reading already stored is answered with the stored one, so a replay can be run again safely.
        await sendReading(REPLAY_SHIPMENT, new Date(Date.UTC(2026, 9, 17, 6, i * 10)).toISOString(), REPLAY_C[i]);
        setSent(i + 1);
        await load();
        if (i < REPLAY_C.length - 1) await new Promise((resolve) => setTimeout(resolve, REPLAY_MS));
      }
    } catch (e) { setError((e as Error).message); }
    finally { setSent(null); }
  }

  async function clear() {
    stopped.current = true;
    setClearing(true); setError(""); setNotice("");
    try {
      const { deleted } = await clearReadings(REPLAY_SHIPMENT);
      setNotice(`Cleared ${deleted} simulated reading${deleted === 1 ? "" : "s"} from SHIP-017.`);
      await load();
    } catch (e) { setError((e as Error).message); }
    finally { setClearing(false); }
  }

  const counts = (Object.keys(LEVELS) as MonitorLevel[]).map((level) => [level, items?.filter((m) => m.level === level).length ?? 0] as const).filter(([, n]) => n);

  return <main className="min-h-dvh bg-[#f7f9fb] text-[#0d293b]">
    <header className="border-b border-slate-200 bg-white"><div className="mx-auto flex h-14 max-w-screen-2xl items-center justify-between px-5 sm:px-8">
      <Link href="/" aria-label="TraceFront home"><Image src="/tracefront-logo-black.png" alt="TraceFront" width={140} height={50} className="h-11 w-auto" /></Link>
      <div className="flex items-center gap-3 text-xs">
        {me && <><span className="hidden text-slate-600 sm:inline"><strong className="text-[#0d293b]">{me.name}</strong> · {me.organization_name ?? "Ministry of Health"}</span>
          <button onClick={() => signOut().finally(() => window.location.assign("/login"))} className="rounded-full border border-slate-300 px-4 py-2 font-semibold hover:border-slate-900">Sign out</button></>}
        <Link href="/trace" className="rounded-full border border-slate-300 px-4 py-2 font-semibold hover:border-slate-900">Trace lots</Link>
      </div>
    </div></header>
    <div className="mx-auto max-w-screen-2xl px-5 py-7 sm:px-8">
      <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Live shipments</h1>
      <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">Temperature readings from shipment loggers, checked against each shipment&apos;s limit as they arrive. {regulator ? "You see every shipment that has sent a reading." : "You see the shipments your organization sent or received."}</p>
      <p className="mt-1 text-xs text-slate-500">{updated ? `Updated ${updated.toLocaleTimeString()} · refreshes every ${POLL_MS / 1000} seconds` : "Loading…"}</p>

      {regulator && <section aria-labelledby="replay-heading" className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
        <h2 id="replay-heading" className="text-sm font-semibold">Simulated replay</h2>
        <p className="mt-1 max-w-3xl text-xs leading-5 text-slate-600">Sends the {REPLAY_C.length} SHIP-017 readings from the sample shipment file, one every {REPLAY_MS / 1000} seconds, the way a truck logger would. The readings are simulated and go to the synthetic scenario&apos;s shipment only, so they can be cleared afterwards.</p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          {sent === null
            ? <button onClick={replay} disabled={clearing} className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50">Replay SHIP-017</button>
            : <button onClick={() => { stopped.current = true; }} className="rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-slate-700">Stop replay</button>}
          <button onClick={clear} disabled={clearing || sent !== null} className="rounded-xl border border-slate-300 px-5 py-2.5 text-sm font-semibold hover:border-slate-900 disabled:opacity-50">{clearing ? "Clearing…" : "Clear simulated readings"}</button>
          {sent !== null && <span role="status" className="text-xs text-slate-600">{sent} of {REPLAY_C.length} sent</span>}
        </div>
      </section>}

      {notice && <p role="status" className="mt-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">{notice}</p>}
      {error && <p role="alert" className="mt-5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}

      {items === null ? (!error && <p className="mt-6 text-sm text-slate-500">Loading shipments…</p>)
        : !items.length ? <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5 text-sm leading-6">
          <h2 className="font-semibold">No shipment has sent a reading yet</h2>
          <p className="mt-1 text-slate-600">Loggers post readings to <code className="font-mono text-xs">/api/sensor-readings</code> with the shipment ID, the time and the temperature. {regulator && "To see how it works, replay the simulated shipment above."}</p>
        </section>
        : <>
          <p className="mt-6 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">{counts.map(([level, n]) => <span key={level} className="inline-flex items-center gap-1.5"><LevelIcon level={level} /><strong className="text-[#0d293b]">{n}</strong> {LEVELS[level].label.toLowerCase()}</span>)}</p>
          <div className="mt-3 grid gap-5 lg:grid-cols-2">{items.map((item) => <ShipmentCard key={item.shipment.shipment_id} item={item} />)}</div>
        </>}
    </div>
  </main>;
}
