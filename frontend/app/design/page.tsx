import Link from "next/link";

import { StageCard } from "@/components/design/StageCard";
import { WorkflowSteps } from "@/components/design/WorkflowSteps";

const steps = ["Supplier data", "Analysis", "Review and response"] as const;

const stages = [
  {
    number: 1,
    title: "Upload the supplier record",
    description: "A supplier or factory owner selects a recent shipment dataset and checks what it contains before analysis.",
    inputs: ["Batch and product identifiers", "Transport temperature and timestamps", "Origins, destinations, and buyers"],
    outcome: "A validated file and a clear summary of the records to analyze.",
    previewHref: "/",
  },
  {
    number: 2,
    title: "Analyze the connected evidence",
    description: "The circular network animation explains the handoff from shipment records to the risk and traceability pipeline.",
    inputs: ["Uploaded shipment records", "Historical recall reference data", "Batch relationships and approved procedures"],
    outcome: "A review priority with linked evidence, when the services are connected.",
    previewHref: "/ml-process",
  },
  {
    number: 3,
    title: "Review anomalies and reach",
    description: "Investigators inspect each anomaly, trace where a batch went, and prepare the right message for the right stage.",
    inputs: ["Anomaly evidence and affected batch IDs", "Downstream recipients in the supply graph", "Official lab result when available"],
    outcome: "An early precautionary warning, followed by a lab-informed response after review.",
  },
] as const;

export default function DesignWorkspace() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
      <header className="mb-8 flex flex-wrap items-start justify-between gap-5">
        <div className="max-w-2xl">
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-rose-700 dark:text-rose-300">
            Tracefront / Design workspace
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">One record. One traceable response.</h1>
          <p className="mt-3 text-sm leading-6 text-slate-700 dark:text-slate-300">
            The two HTML mockups are being organized into a three-screen Next.js flow. This page is the shared design map, not a live analysis result.
          </p>
        </div>
        <Link
          href="/"
          className="inline-flex min-h-10 items-center rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 dark:border-slate-700 dark:hover:bg-slate-800"
        >
          Back to dashboard
        </Link>
      </header>

      <WorkflowSteps steps={steps} />

      <section className="mt-6 grid gap-4 lg:grid-cols-3" aria-label="Proposed screens">
        {stages.map((stage) => <StageCard key={stage.number} {...stage} />)}
      </section>

      <section className="mt-6 grid gap-4 md:grid-cols-2" aria-label="Response stages">
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 dark:border-amber-900 dark:bg-amber-950">
          <p className="text-xs font-semibold uppercase tracking-wider text-amber-800 dark:text-amber-200">Before lab confirmation</p>
          <h2 className="mt-2 text-lg font-semibold">Precautionary warning</h2>
          <p className="mt-2 text-sm leading-6 text-slate-700 dark:text-slate-300">Flag unusual temperature or shipment patterns, show who may have received the batch, and ask an authorized person to review the warning.</p>
        </div>
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 dark:border-emerald-900 dark:bg-emerald-950">
          <p className="text-xs font-semibold uppercase tracking-wider text-emerald-800 dark:text-emerald-200">After an official lab result</p>
          <h2 className="mt-2 text-lg font-semibold">Confirmed update</h2>
          <p className="mt-2 text-sm leading-6 text-slate-700 dark:text-slate-300">Attach the result, narrow the affected batch and recipients, then prepare a definitive update for human approval.</p>
        </div>
      </section>

      <p className="mt-6 text-xs leading-5 text-slate-600 dark:text-slate-400">
        Design preview only. File ingestion, trained inference, lab verification, and outbound notifications are not connected here.
      </p>
    </main>
  );
}
