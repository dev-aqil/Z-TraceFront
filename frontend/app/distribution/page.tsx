"use client";

import Image from "next/image";
import Link from "next/link";
import { getDistribution, getFindings, useAnalysis, withAnalysis } from "@/lib/api";
import { demoFindings } from "../analysis-results/demo-findings";
import { demoGraph } from "./demo-graph";
import DistributionTree from "./DistributionTree";
import NotifyOverlay from "./NotifyOverlay";

const load = (id: string) => Promise.all([getDistribution(id), getFindings(id)]);
const demo: Awaited<ReturnType<typeof load>> = [demoGraph, demoFindings];

export default function DistributionPage() {
  const { id, data, error } = useAnalysis(load, demo);
  const graph = data?.[0] ?? null;
  const findings = data?.[1] ?? [];
  const siteFor = (shipmentId: string) => graph?.nodes.find((node) => node.id === `shipment:${shipmentId}`);
  // Findings arrive highest severity first, so the alert and notify draft point at the most urgent shipment.
  const focus = findings.find((finding) => siteFor(finding.shipmentId));
  const site = focus && siteFor(focus.shipmentId);
  const supplier = graph?.nodes.find((node) => node.kind === "root")?.label ?? "Supplier";
  const marked = graph?.nodes.filter((node) => node.kind === "recipient" && node.flagged).length ?? 0;

  return (
    <main className="distribution-page min-h-dvh overflow-hidden bg-[#f7f9fb] text-[#0d293b]">
      <header className="distribution-reveal border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-12 max-w-screen-2xl items-center justify-between gap-4 px-5 sm:px-8">
          <Link href="/" aria-label="TraceFront home" className="rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-rose-600">
            <span className="relative block h-10 w-36 overflow-hidden">
              <Image src="/tracefront-logo-black.png" alt="TraceFront" width={2091} height={752} priority className="absolute left-0 top-1/2 h-12 w-auto max-w-none -translate-y-1/2" />
            </span>
          </Link>
          <Link href={`${withAnalysis("/analysis-results", id)}#findings`} className="group inline-flex h-10 items-center rounded-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600"><span className="inline-flex h-8 items-center gap-1.5 rounded-full border border-slate-300 bg-white px-3 text-xs font-medium text-slate-900 shadow-sm transition-colors group-hover:border-slate-900 group-hover:bg-slate-50"><span aria-hidden="true">←</span> Findings</span></Link>
        </div>
      </header>

      <div className="mx-auto max-w-screen-2xl px-5 pb-6 pt-5 sm:px-8 sm:pt-6">
        <div className="distribution-reveal distribution-reveal--two flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Distribution Network</h1>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">Follow the flow from the distributor through route categories and product batches to each receiving site. The amber path leads to a shipment marked for review.</p>
          </div>
          <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white p-1 pr-3 text-xs font-semibold text-slate-700 shadow-sm"><span className="rounded-full bg-amber-700 px-2.5 py-1 text-white">{marked} {marked === 1 ? "shipment" : "shipments"}</span>marked for review</span>
        </div>

        <div className="distribution-reveal distribution-reveal--three mt-4 grid items-start gap-4 xl:grid-cols-[minmax(0,1fr)_16rem]">
          <section aria-label="Supplier distribution tree" className="min-w-0 rounded-[24px] border border-slate-200 bg-white p-4 shadow-[0_20px_60px_rgba(15,23,42,0.05)] sm:p-5">
            {graph
              ? <DistributionTree graph={graph} alert={focus ? { shipmentId: focus.shipmentId, type: focus.type, reason: focus.reason } : null} />
              : <p role={error ? "alert" : "status"} className="flex h-[430px] items-center justify-center text-sm text-slate-600">{error || "Loading distribution…"}</p>}
          </section>
          <aside className="flex flex-col gap-4" aria-label="Distribution actions and legend">
            {focus && site && <NotifyOverlay target={{ shipmentId: focus.shipmentId, batchId: focus.batchId, reason: focus.reason, supplier, recipient: site.label }} />}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm" aria-label="Network legend">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-700">Legend</h2>
              <ul className="mt-4 space-y-3 text-sm text-slate-700">
                <li className="flex items-center gap-3"><span aria-hidden="true" className="h-3 w-6 shrink-0 rounded-full border-2 border-amber-500 bg-amber-50" />Distributor</li>
                <li className="flex items-center gap-3"><span aria-hidden="true" className="h-3 w-6 shrink-0 rounded border border-green-300 bg-green-100" />Route category</li>
                <li className="flex items-center gap-3"><span aria-hidden="true" className="h-3 w-6 shrink-0 rounded border border-rose-300 bg-rose-50" />Product batch</li>
                <li className="flex items-center gap-3"><span aria-hidden="true" className="h-3 w-6 shrink-0 rounded border border-blue-300 bg-blue-50" />Receiving site</li>
                <li className="flex items-center gap-3"><span aria-hidden="true" className="h-0.5 w-6 shrink-0 bg-amber-500" />Review path</li>
                <li className="flex items-center gap-3"><span aria-hidden="true" className="flex w-6 shrink-0 justify-center text-sm leading-none text-amber-600">▲</span>Review alert</li>
              </ul>
            </div>
          </aside>
        </div>
      </div>
    </main>
  );
}
