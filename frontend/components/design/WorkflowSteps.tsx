type WorkflowStepsProps = {
  current?: number;
  steps: readonly string[];
};

export function WorkflowSteps({ current, steps }: WorkflowStepsProps) {
  return (
    <ol className="grid gap-2 sm:grid-cols-3" aria-label="Tracefront workflow">
      {steps.map((step, index) => {
        const active = current === index;
        return (
          <li
            key={step}
            aria-current={active ? "step" : undefined}
            className={`flex min-h-12 items-center gap-3 rounded-xl border px-4 py-3 text-sm font-medium ${
              active
                ? "border-rose-300 bg-rose-50 text-rose-950 dark:border-rose-700 dark:bg-rose-950 dark:text-rose-100"
                : "border-slate-200 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
            }`}
          >
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                active ? "bg-rose-600 text-white" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200"
              }`}
            >
              {index + 1}
            </span>
            {step}
          </li>
        );
      })}
    </ol>
  );
}
