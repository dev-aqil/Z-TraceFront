import Link from "next/link";

import { StageCard } from "@/components/design/StageCard";
import { WorkflowSteps } from "@/components/design/WorkflowSteps";

const steps = ["Upload", "Confirm", "Analyze", "Distribution", "Anomalies", "Response"] as const;

const stages = [
  {
    number: 1,
    title: "Upload a supplier dataset",
    description: "Choose a recent shipment file. This is the first dedicated screen in the flow.",
    inputs: ["Batch and product identifiers", "Transport temperature and timestamps", "Origins, destinations, and buyers"],
    outcome: "A file selected locally for the next review step.",
    previewHref: "/",
  },
  {
    number: 2,
    title: "Confirm the file",
    description: "Show the file name, format, and records that will be read before starting analysis.",
    inputs: ["Selected file", "Detected columns", "Validation messages"],
    outcome: "The operator confirms the dataset or chooses another file.",
  },
  {
    number: 3,
    title: "Run the analysis",
    description: "The circular network animation accompanies real pipeline status once the services are connected.",
    inputs: ["Validated shipment records", "Risk model output", "Batch links"],
    outcome: "Analysis progress and a result ready for review.",
    previewHref: "/ml-process",
  },
  {
    number: 4,
    title: "Inspect distribution",
    description: "Show where the selected batch went across known buyers and destinations.",
    inputs: ["Batch ID", "Shipment and delivery records", "Known downstream partners"],
    outcome: "A batch-specific distribution view.",
  },
  {
    number: 5,
    title: "Review anomalies",
    description: "Investigators inspect flagged shipments and the evidence behind each finding.",
    inputs: ["Temperature and time deviations", "Model score and explanation", "Affected batch records"],
    outcome: "A prioritized case with its traceable evidence.",
  },
  {
    number: 6,
    title: "Prepare a response",
    description: "Choose recipients and review a precautionary warning or a later lab-informed update.",
    inputs: ["Affected recipients", "Anomaly evidence", "Official lab result when available"],
    outcome: "A message ready for human approval and delivery.",
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
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Six focused screens, one traceable case.</h1>
          <p className="mt-3 text-sm leading-6 text-slate-700 dark:text-slate-300">
            Explore the six screens in the TraceFront workflow, from supplier data to contact review.
          </p>
        </div>
        <Link
          href="/"
          className="inline-flex min-h-10 items-center rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 dark:border-slate-700 dark:hover:bg-slate-800"
        >
          Open upload page
        </Link>
      </header>

      <WorkflowSteps steps={steps} />

      <section className="mt-6 grid gap-4 lg:grid-cols-3" aria-label="Planned screens">
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

    </main>
  );
}
