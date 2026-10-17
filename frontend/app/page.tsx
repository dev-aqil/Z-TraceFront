"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { startUpload } from "@/lib/api";
import SpinPanel from "./SpinPanel";

const acceptedTypes = ["csv", "xlsx", "json"];
const exampleFileName = "supplier_shipments.csv";
const PICKER_CONFIRM_DELAY_MS = 750;

export default function UploadPage() {
  const router = useRouter();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const dialogActionRef = useRef<HTMLButtonElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pickerTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [exampleSelected, setExampleSelected] = useState(false);
  const [error, setError] = useState("");
  const [dragging, setDragging] = useState(false);
  const [dialogStage, setDialogStage] = useState<"intro" | "picker-blank" | "picker" | "picker-confirming" | "selected">("intro");
  const [transitioning, setTransitioning] = useState(false);
  const selectedFileLabel = exampleSelected ? `${exampleFileName} selected` : file ? `${file.name} selected` : null;

  useEffect(() => {
    if (dialogRef.current?.open && dialogStage !== "picker-confirming") dialogActionRef.current?.focus();
  }, [dialogStage]);

  useEffect(() => () => pickerTimersRef.current.forEach(clearTimeout), []);

  useEffect(() => {
    const uploadError = new URLSearchParams(window.location.search).get("error");
    if (uploadError) setError(`Analysis failed: ${uploadError}`);
  }, []);

  function clearPickerTimers() {
    pickerTimersRef.current.forEach(clearTimeout);
    pickerTimersRef.current = [];
  }

  function openFilePicker() {
    clearPickerTimers();
    pickerTimersRef.current = [
      setTimeout(() => setDialogStage("picker-blank"), 180),
      setTimeout(() => { setDialogStage("picker"); pickerTimersRef.current = []; }, 580),
    ];
  }

  function confirmExampleFile() {
    clearPickerTimers();
    setDialogStage("picker-confirming");
    pickerTimersRef.current = [setTimeout(() => {
      setExampleSelected(true);
      setFile(null);
      setError("");
      setDialogStage("selected");
      pickerTimersRef.current = [];
    }, PICKER_CONFIRM_DELAY_MS)];
  }

  function chooseFile(nextFile?: File) {
    setError("");
    setFile(null);
    setExampleSelected(false);
    if (!nextFile) {
      setDialogStage("intro");
      return;
    }

    const extension = nextFile.name.split(".").pop()?.toLowerCase();
    if (!extension || !acceptedTypes.includes(extension)) {
      setError("Choose a CSV, XLSX, or JSON file.");
      setDialogStage("intro");
      return;
    }

    setFile(nextFile);
    setDialogStage("selected");
  }

  function openUploadDialog() {
    setDialogStage(file || exampleSelected ? "selected" : "intro");
    dialogRef.current?.showModal();
  }

  function startAnalysis() {
    startUpload(file ?? fetch(`/${exampleFileName}`).then((response) => {
      if (!response.ok) throw new Error("The example file is missing.");
      return response.blob();
    }).then((blob) => new File([blob], exampleFileName, { type: "text/csv" })));
    dialogRef.current?.close();
    goToProcessing();
  }

  function goToProcessing() {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      router.push("/ml-process");
      return;
    }
    setTransitioning(true);
  }

  return (
    <main
      aria-busy={transitioning}
      onTransitionEnd={(event) => {
        if (transitioning && event.target === event.currentTarget && event.propertyName === "opacity") router.push("/ml-process");
      }}
      className={`min-h-screen bg-slate-50 text-slate-900 motion-safe:transition-opacity motion-safe:duration-300 motion-safe:ease-in lg:flex lg:h-dvh lg:flex-col ${transitioning ? "opacity-0" : "opacity-100"}`}
    >
      <header className="bg-[#0d293b] text-white lg:shrink-0">
        <div className="mx-auto flex max-w-7xl items-center px-4 py-2 sm:px-6 lg:px-8">
          <Link href="/" aria-label="TraceFront home" className="rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-rose-300">
            <Image src="/tracefront-logo.png" alt="TraceFront" width={224} height={84} priority className="h-10 w-auto sm:h-12" />
          </Link>
        </div>
      </header>

      <div className="mx-auto w-full max-w-7xl px-4 py-5 sm:px-6 sm:py-6 lg:min-h-0 lg:flex-1 lg:px-8 lg:py-2">
        <section aria-labelledby="upload-title" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6 lg:flex lg:h-full lg:flex-col lg:p-4">
          <h1 id="upload-title" className="text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">Upload supply chain data</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">Choose a supplier shipment file to review batch information.</p>

          <div
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              chooseFile(event.dataTransfer.files[0]);
            }}
            className={`mt-5 flex min-h-52 flex-col items-center justify-center rounded-xl border-2 border-dashed px-5 py-3 text-center sm:min-h-72 lg:min-h-0 lg:flex-1 ${dragging ? "border-rose-600 bg-rose-100" : "border-rose-300 bg-rose-50/60"}`}
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-white text-rose-600 shadow-sm sm:h-12 sm:w-12" aria-hidden="true">
              <svg viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="h-8 w-8">
                <path d="M15 36H12a8 8 0 0 1-1-15.9A13 13 0 0 1 36.2 18a9 9 0 0 1 .8 18h-4" />
                <path d="M24 39V23m0 0-6 6m6-6 6 6" />
              </svg>
            </div>
            <h2 className="mt-2 max-w-full break-all text-xl font-semibold text-slate-800 sm:text-2xl" aria-live="polite">{selectedFileLabel ?? "Drop your file here"}</h2>
            <p className="mt-1 text-sm text-slate-600">{selectedFileLabel ? "File ready to review." : "or browse for a file"}</p>
            <button type="button" onClick={openUploadDialog} className="mt-3 inline-flex min-h-11 items-center justify-center rounded-lg bg-rose-600 px-8 py-2 text-sm font-semibold text-white hover:bg-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700">
              {selectedFileLabel ? "Review file" : "Browse files"}
            </button>
            <p className="mt-2 text-xs font-medium tracking-wide text-slate-600">CSV&nbsp;&nbsp;·&nbsp;&nbsp;XLSX&nbsp;&nbsp;·&nbsp;&nbsp;JSON</p>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border border-slate-200 bg-slate-50 px-5 py-3 text-sm text-slate-700">
            <span className="font-semibold text-slate-900">Example upload fields</span>
            <span>Batch ID</span>
            <span>Shipment time</span>
            <span>Temperature</span>
            <span>Destination</span>
          </div>

          <SpinPanel onRun={goToProcessing} />
          <Link href="/trace" className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-slate-700 underline decoration-slate-300 underline-offset-4 hover:text-rose-700">Open lot investigation <span aria-hidden="true">→</span></Link>

          {error && <p role="alert" className="mt-4 text-sm font-medium text-red-700">{error}</p>}
        </section>
      </div>

      <dialog
        ref={dialogRef}
        aria-labelledby="upload-dialog-title"
        aria-busy={dialogStage === "picker-blank" || dialogStage === "picker-confirming"}
        onClose={() => { clearPickerTimers(); setDialogStage("intro"); }}
        className={`upload-data-dialog w-[min(760px,calc(100vw-2rem))] max-h-[calc(100dvh-2rem)] overflow-y-auto rounded-2xl border border-slate-200 bg-white p-0 text-slate-900 shadow-2xl ${dialogStage === "picker" || dialogStage === "picker-confirming" || dialogStage === "picker-blank" ? "max-w-3xl" : "max-w-xl"}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.json"
          tabIndex={-1}
          aria-hidden="true"
          className="hidden"
          onChange={(event) => {
            clearPickerTimers();
            chooseFile(event.target.files?.[0]);
            event.target.value = ""; // choosing the same file again still fires change
          }}
        />
        {dialogStage === "picker-blank" ? (
          <div className="h-[520px] rounded-2xl bg-white"><h2 id="upload-dialog-title" className="sr-only">Opening files</h2></div>
        ) : dialogStage === "picker" || dialogStage === "picker-confirming" ? (
          <div className="upload-picker-content overflow-hidden rounded-2xl bg-[#f6f8fb]">
            <div className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">Select a file</p>
                <h2 id="upload-dialog-title" className="text-base font-semibold">Open</h2>
              </div>
              <button type="button" onClick={() => dialogRef.current?.close()} aria-label="Close file selection" className="flex h-10 w-10 items-center justify-center rounded-lg text-xl text-slate-600 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-rose-600">×</button>
            </div>
            <div className="border-b border-slate-200 px-5 py-3">
              <div className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm text-slate-700">This PC <span className="mx-2 text-slate-400">›</span> Documents <span className="mx-2 text-slate-400">›</span> Shipment records</div>
            </div>
            <div className="flex min-h-64">
              <aside className="hidden w-44 shrink-0 border-r border-slate-200 bg-white px-4 py-5 text-sm text-slate-600 sm:block" aria-label="File locations">
                <p className="font-semibold text-slate-900">Quick access</p>
                <p className="mt-5">Desktop</p>
                <p className="mt-4 rounded-md bg-blue-50 px-2 py-1 font-medium text-blue-900">Documents</p>
                <p className="mt-4">Downloads</p>
              </aside>
              <div className="min-w-0 flex-1 px-5 py-5">
                <div className="grid grid-cols-[1fr_auto] gap-4 border-b border-slate-200 px-3 pb-3 text-xs font-medium text-slate-500 sm:grid-cols-[1fr_8rem]">
                  <span>Name</span><span>Type</span>
                </div>
                <div className="mt-2 grid grid-cols-[1fr_auto] items-center gap-4 rounded-lg border border-blue-300 bg-blue-100 px-3 py-3 text-sm text-blue-950 sm:grid-cols-[1fr_8rem]" aria-label="Selected file">
                  <span className="min-w-0 truncate font-semibold">📄 {exampleFileName}</span><span>CSV file</span>
                </div>
                <p className="mt-4 text-xs text-slate-600">Select the file, then choose Open.</p>
              </div>
            </div>
            <div className="border-t border-slate-200 bg-white p-5">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <span className="w-20 font-medium text-slate-700">File name</span>
                <input readOnly value={exampleFileName} aria-label="Selected file name" className="min-w-0 flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-slate-900" />
              </div>
              <div className="mt-4 flex flex-wrap justify-end gap-3">
                {/* The picker above is a mock that offers the example file; this opens the device's real file chooser. */}
                <button type="button" onClick={() => fileInputRef.current?.click()} className="mr-auto min-h-10 rounded-lg px-2 py-2 text-sm font-medium text-blue-700 underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-700">Choose a file from this device…</button>
                <button type="button" onClick={() => { clearPickerTimers(); setDialogStage(file || exampleSelected ? "selected" : "intro"); }} className="min-h-10 rounded-lg border border-slate-300 px-5 py-2 text-sm font-medium hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-rose-600">Cancel</button>
                <button
                  ref={dialogActionRef}
                  type="button"
                  onClick={confirmExampleFile}
                  disabled={dialogStage === "picker-confirming"}
                  className="min-h-10 rounded-lg bg-blue-600 px-7 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:cursor-wait disabled:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-700"
                >{dialogStage === "picker-confirming" ? "Opening…" : "Open"}</button>
              </div>
            </div>
          </div>
        ) : (
          <div className="p-6 sm:p-8">
            <div className="flex justify-end">
              <button type="button" onClick={() => dialogRef.current?.close()} aria-label="Close upload dialog" className="flex h-10 w-10 items-center justify-center rounded-lg text-xl text-slate-600 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-rose-600">×</button>
            </div>
            <div className="mt-7 flex h-16 w-16 items-center justify-center rounded-xl bg-rose-50 text-rose-600" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" className="h-9 w-9">
                <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
              </svg>
            </div>
            <h2 id="upload-dialog-title" className="mt-5 text-2xl font-semibold tracking-tight">{dialogStage === "selected" ? "File ready" : "Upload shipment file"}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">{dialogStage === "selected" ? "Review the selected file before continuing." : "Choose a CSV, XLSX, or JSON file to review."}</p>
            <div
              onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => { event.preventDefault(); setDragging(false); chooseFile(event.dataTransfer.files[0]); }}
              className={`mt-6 rounded-xl border-2 p-4 ${dialogStage === "selected" ? "border-slate-200 bg-slate-50" : dragging ? "border-rose-500 border-dashed bg-rose-50" : "border-slate-300 border-dashed bg-slate-50"}`}
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{dialogStage === "selected" ? "Selected file" : "Drop a file here"}</p>
              <p className="mt-1 break-all text-sm font-medium text-slate-900">{dialogStage === "selected" ? file?.name ?? exampleFileName : "or browse files from your device"}</p>
              <p className="mt-1 text-xs text-slate-600">CSV · XLSX · JSON</p>
            </div>
            {error && <p role="alert" className="mt-2 text-sm font-medium text-red-700">{error}</p>}
            <div className="mt-6 flex flex-wrap justify-end gap-3">
              <button type="button" onClick={() => dialogStage === "selected" ? openFilePicker() : dialogRef.current?.close()} className="min-h-11 rounded-lg border border-slate-300 px-5 py-2 text-sm font-medium hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600">{dialogStage === "selected" ? "Change file" : "Cancel"}</button>
              <button ref={dialogActionRef} type="button" onClick={() => dialogStage === "selected" ? startAnalysis() : openFilePicker()} className="min-h-11 rounded-lg bg-rose-600 px-6 py-2 text-sm font-semibold text-white hover:bg-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700">{dialogStage === "selected" ? "Preview analysis" : "Browse files"}</button>
            </div>
          </div>
        )}
      </dialog>
    </main>
  );
}
