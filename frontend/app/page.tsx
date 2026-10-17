"use client";

import { useRef, useState } from "react";

const reports = [
  {
    id: "RPT-1042",
    supplier: "Northfield Produce",
    report: "Temperature log",
    summary: "Cold-chain deviation flagged",
    received: "17 Oct 2026, 10:42",
    status: "Needs review",
    statusClass: "bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-200",
  },
  {
    id: "RPT-1041",
    supplier: "Riverbend Dairy",
    report: "Quality inspection",
    summary: "Inspection notes under review",
    received: "17 Oct 2026, 09:18",
    status: "In review",
    statusClass: "bg-sky-100 text-sky-900 dark:bg-sky-950 dark:text-sky-200",
  },
  {
    id: "RPT-1040",
    supplier: "Garden Lane Foods",
    report: "Lab report",
    summary: "Batch references indexed",
    received: "16 Oct 2026, 16:05",
    status: "Reviewed",
    statusClass: "bg-emerald-100 text-emerald-900 dark:bg-emerald-950 dark:text-emerald-200",
  },
];

const allowedExtensions = ["pdf", "csv", "txt"];
const maxFileSize = 10 * 1024 * 1024;

export default function Home() {
  const fileInput = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);

  function selectReport(file?: File) {
    setFileError(null);
    setSelectedFile(null);
    if (!file) return;

    const extension = file.name.split(".").pop()?.toLowerCase();
    if (!extension || !allowedExtensions.includes(extension)) {
      setFileError("Choose a PDF, CSV, or TXT report.");
    } else if (file.size > maxFileSize) {
      setFileError("Choose a report smaller than 10 MB.");
    } else {
      setSelectedFile(file.name);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
      <header className="mb-8">
        <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-rose-700 dark:text-rose-300">
          Tracefront / Reports
        </p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Supplier analysis
        </h1>
        <p className="mt-2 max-w-prose text-sm text-slate-700 dark:text-slate-300">
          Review incoming supplier reports and keep recent decisions in view.
        </p>
      </header>

      <section
        aria-labelledby="recent-reports-heading"
        className="min-h-96 overflow-hidden rounded-xl border border-rose-200 bg-white dark:border-slate-700 dark:bg-slate-900"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rose-100 bg-rose-50 px-5 py-5 dark:border-slate-700 dark:bg-slate-800 sm:px-6">
          <div>
            <h2 id="recent-reports-heading" className="text-lg font-semibold">
              Recent supplier reports
            </h2>
            <p className="mt-1 text-sm text-slate-700 dark:text-slate-300">
              Analysis records appear here when the service is connected.
            </p>
          </div>
          <span className="rounded-full border border-rose-200 bg-white px-3 py-1 text-xs font-semibold text-rose-800 dark:border-rose-700 dark:bg-slate-900 dark:text-rose-200">
            Sample records
          </span>
        </div>

        <div className="divide-y divide-slate-200 dark:divide-slate-700">
          {reports.map((item) => (
            <article
              key={item.id}
              className="grid gap-3 px-5 py-5 sm:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-center sm:gap-4 sm:px-6"
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-slate-900 dark:text-slate-100">
                  {item.supplier}
                </p>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                  {item.id}
                </p>
              </div>
              <div>
                <p className="text-sm font-medium text-slate-900 dark:text-slate-100">
                  {item.report}
                </p>
                <p className="mt-1 text-xs text-slate-600 dark:text-slate-400">
                  {item.summary}
                </p>
              </div>
              <p className="text-sm text-slate-700 dark:text-slate-300">
                {item.received}
              </p>
              <span
                className={`w-fit rounded-full px-3 py-1 text-xs font-semibold ${item.statusClass}`}
              >
                {item.status}
              </span>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="upload-heading" className="mt-8 max-w-sm">
        <h2 id="upload-heading" className="mb-3 text-sm font-semibold text-slate-700 dark:text-slate-300">
          New supplier report
        </h2>
        <input
          ref={fileInput}
          type="file"
          accept=".pdf,.csv,.txt"
          className="sr-only"
          tabIndex={-1}
          aria-hidden="true"
          onChange={(event) => {
            selectReport(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          className="flex min-h-36 w-full flex-col items-start justify-center rounded-xl border border-rose-300 bg-rose-100 px-6 py-5 text-left transition-colors hover:bg-rose-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700 dark:border-rose-800 dark:bg-rose-950 dark:hover:bg-rose-900 dark:focus-visible:outline-rose-300"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            className="mb-3 h-6 w-6 text-rose-800 dark:text-rose-200"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4 16.5v2.25A1.25 1.25 0 005.25 20h13.5A1.25 1.25 0 0020 18.75V16.5" />
          </svg>
          <span className="font-semibold text-slate-900 dark:text-slate-100">
            Upload supplier report
          </span>
          <span className="mt-1 text-sm text-slate-700 dark:text-slate-300">
            Select a PDF, CSV, or TXT file, up to 10 MB.
          </span>
        </button>
        <p className="mt-3 text-xs text-slate-600 dark:text-slate-400">
          Preview only. Files stay on your device until report upload is connected.
        </p>
        {fileError && (
          <p role="alert" className="mt-3 text-sm text-red-700 dark:text-red-300">
            {fileError}
          </p>
        )}
        {selectedFile && (
          <p role="status" className="mt-3 text-sm text-slate-700 dark:text-slate-300">
            Selected: {selectedFile}. Analysis upload is not connected yet.
          </p>
        )}
      </section>
    </main>
  );
}
