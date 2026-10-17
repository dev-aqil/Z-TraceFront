import Link from "next/link";

type StageCardProps = {
  number: number;
  title: string;
  description: string;
  inputs: readonly string[];
  outcome: string;
  previewHref?: string;
};

export function StageCard({ number, title, description, inputs, outcome, previewHref }: StageCardProps) {
  return (
    <article className="flex h-full flex-col rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-700 dark:bg-slate-900 sm:p-6">
      <div className="mb-5 flex items-center justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-widest text-rose-700 dark:text-rose-300">
          Screen {number}
        </span>
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
          Design draft
        </span>
      </div>
      <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
      <p className="mt-2 text-sm leading-6 text-slate-700 dark:text-slate-300">{description}</p>
      <h3 className="mt-6 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">What it uses</h3>
      <ul className="mt-2 space-y-2 text-sm text-slate-700 dark:text-slate-300">
        {inputs.map((input) => (
          <li key={input} className="flex gap-2">
            <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-rose-500" />
            <span>{input}</span>
          </li>
        ))}
      </ul>
      <div className="mt-auto pt-6">
        <div className="rounded-xl bg-slate-50 p-3 text-sm text-slate-800 dark:bg-slate-800 dark:text-slate-100">
          <span className="font-semibold">Outcome:</span> {outcome}
        </div>
        {previewHref && (
          <Link
            href={previewHref}
            className="mt-4 inline-flex min-h-10 items-center rounded-lg px-1 text-sm font-semibold text-rose-700 underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 dark:text-rose-300"
          >
            Open current preview
          </Link>
        )}
      </div>
    </article>
  );
}
