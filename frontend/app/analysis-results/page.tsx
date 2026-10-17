"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { getFindingsReport, useAnalysis, withAnalysis } from "@/lib/api";
import { demoFindings } from "./demo-findings";
import PredictionResult from "./PredictionResult";

const DEMO_REPORT = { findings: demoFindings, checks: null };

type RevealStage = "dash" | "zero" | "count" | "results";

const SCROLL_GESTURE_GAP_MS = 180;

const bubbleOffsets = [
  { x: -24, y: -16 },
  { x: 18, y: 12 },
  { x: -12, y: 20 },
  { x: 25, y: 16 },
  { x: -20, y: -11 },
  { x: 13, y: 11 },
];

const compactBubbleOffsets = [
  { x: -6, y: -132 },
  { x: 11, y: -12 },
  { x: -2, y: 62 },
  { x: 12, y: -115 },
  { x: -8, y: 7 },
  { x: 3, y: 73 },
];

function FindingIcon({ type }: { type: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-6 w-6 shrink-0 text-rose-600">
      {type === "Temperature" && <><path d="M10 14.6V5a2 2 0 0 1 4 0v9.6a4 4 0 1 1-4 0Z" /><path d="M12 10v8" /></>}
      {type === "Delivery" && <><path d="M3 6h11v10H3zM14 9h4l3 3v4h-7" /><circle cx="7" cy="18" r="2" /><circle cx="18" cy="18" r="2" /></>}
      {type === "Humidity" && <><path d="M12 3c-3 4-6 7.3-6 11a6 6 0 0 0 12 0c0-3.7-3-7-6-11Z" /><path d="M9 15a3 3 0 0 0 3 3" /></>}
      {type === "Quantity" && <><path d="m4 8 8-4 8 4-8 4-8-4ZM4 8v9l8 4 8-4V8M12 12v9" /></>}
      {type === "Sensor coverage" && <><circle cx="12" cy="12" r="2" /><path d="M8.5 8.5a5 5 0 0 0 0 7M15.5 8.5a5 5 0 0 1 0 7M5.5 5.5a9 9 0 0 0 0 13M18.5 5.5a9 9 0 0 1 0 13" /></>}
      {type === "Destination" && <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10" r="2.5" /></>}
    </svg>
  );
}

// ?prediction=1 shows a spin-a-sample model run; otherwise the shipment findings of ?analysis=<id> (or the demo).
export default function AnalysisResultsPage() {
  const [mode, setMode] = useState<"findings" | "prediction" | null>(null);
  useEffect(() => setMode(new URLSearchParams(window.location.search).has("prediction") ? "prediction" : "findings"), []);
  return mode === "prediction" ? <PredictionResult /> : mode === "findings" ? <FindingsResults /> : null;
}

function FindingsResults() {
  const router = useRouter();
  const leavingRef = useRef(false);
  const [leaving, setLeaving] = useState(false);
  const [stage, setStage] = useState<RevealStage>("dash");
  const [count, setCount] = useState(0);
  const [atBottom, setAtBottom] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [viewport, setViewport] = useState({ width: 1280, height: 800 });
  const { id: analysisId, data: report, error: loadError } = useAnalysis(getFindingsReport, DEMO_REPORT);
  const loaded = report?.findings ?? null;
  const findings = loaded ?? [];
  // A check with no data is "not checked", never "passed": zero findings must not read as a clearance.
  const unchecked = report?.checks?.filter((check) => check.shipments_checked === 0) ?? [];
  const noneRan = !!report?.checks && unchecked.length === report.checks.length;
  const total = findings.length;
  const severityCounts = (["High", "Medium", "Low", "Unknown"] as const)
    .map((level) => [level, findings.filter((finding) => finding.severity === level).length] as const)
    .filter(([, n]) => n > 0)
    .map(([level, n]) => `${n} ${level.toLowerCase()}`)
    .join(" · ");

  useEffect(() => {
    const updateViewport = () => setViewport({ width: window.innerWidth, height: window.innerHeight });
    updateViewport();
    window.addEventListener("resize", updateViewport);
    return () => window.removeEventListener("resize", updateViewport);
  }, []);

  useEffect(() => {
    if (!loaded) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setCount(loaded.length);
      setStage("results");
      return;
    }

    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const elapsed = now - start;
      if (elapsed >= 2900) {
        setCount(loaded.length);
        setStage("results");
        return;
      }
      if (elapsed >= 1400) {
        setStage("count");
        setCount(Math.min(loaded.length, Math.floor(((elapsed - 1400) / 1200) * (loaded.length + 1))));
      } else if (elapsed >= 400) {
        setStage("zero");
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [loaded]);

  useEffect(() => {
    if (stage !== "results") return;

    let frame = 0;
    const update = () => {
      const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      const progress = reducedMotion
        ? Number(window.scrollY > 0)
        : Math.min(1, window.scrollY / Math.max(320, window.innerHeight - 192));
      setScrollProgress(progress);
    };
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
    };
  }, [stage]);

  const counting = stage === "count" || stage === "results";
  const progress = scrollProgress;
  const compact = viewport.width < 700;
  const offset = progress * Math.max(0, viewport.height / 2 - (compact ? 42 : 60));
  const headerVisible = stage === "results" && progress > 0.05;
  const headerInteractive = progress > 0.75;

  const goToDistribution = useCallback(() => {
    if (leavingRef.current || stage !== "results") return;
    leavingRef.current = true;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      router.push(withAnalysis("/distribution", analysisId));
      return;
    }
    setLeaving(true);
  }, [analysisId, router, stage]);

  useEffect(() => {
    if (stage !== "results") return;
    if (window.location.hash !== "#findings") return;
    const frame = requestAnimationFrame(() => document.getElementById("findings")?.scrollIntoView());
    return () => cancelAnimationFrame(frame);
  }, [stage]);

  useEffect(() => {
    if (stage !== "results") return;
    const items = document.querySelectorAll<HTMLElement>("#findings [data-analysis-reveal]");
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) {
      items.forEach((item) => item.classList.add("analysis-content-visible"));
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("analysis-content-visible");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.08, rootMargin: "0px 0px -40px 0px" });
    items.forEach((item) => observer.observe(item));
    return () => observer.disconnect();
  }, [stage]);

  useEffect(() => {
    if (stage !== "results") return;
    let touchStartY = 0;
    let touchStartedAtBottom = false;
    let lastWheelAt = 0;
    const isAtBottom = () => window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 8;
    const onScroll = () => setAtBottom(isAtBottom());
    const onWheel = (event: WheelEvent) => {
      const now = performance.now();
      const newScroll = now - lastWheelAt > SCROLL_GESTURE_GAP_MS;
      lastWheelAt = now;
      if (event.deltaY <= 0 || leavingRef.current) return;
      if (!isAtBottom()) return;
      event.preventDefault();
      if (newScroll) goToDistribution();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (!isAtBottom() || !["ArrowDown", "PageDown", "End", " "].includes(event.key)) return;
      if (event.target instanceof HTMLElement && event.target.closest("button, a, summary, input, textarea, select")) return;
      event.preventDefault();
      goToDistribution();
    };
    const onTouchStart = (event: TouchEvent) => {
      touchStartY = event.touches[0]?.clientY ?? 0;
      touchStartedAtBottom = isAtBottom();
    };
    const onTouchEnd = (event: TouchEvent) => {
      const touchEndY = event.changedTouches[0]?.clientY ?? touchStartY;
      if (touchStartY - touchEndY <= 40 || !isAtBottom()) return;
      if (touchStartedAtBottom) goToDistribution();
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchend", onTouchEnd, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("touchstart", onTouchStart);
      window.removeEventListener("touchend", onTouchEnd);
    };
  }, [goToDistribution, stage]);

  function tilePosition(index: number) {
    const spread = compact
      ? Math.min(128, Math.max(100, viewport.width * 0.29))
      : Math.min(250, Math.max(190, viewport.width * 0.24));
    const bubble = compact ? compactBubbleOffsets[index] : bubbleOffsets[index];
    const x = (index < 3 ? -spread : spread) + bubble.x;
    const y = compact ? bubble.y : ((index % 3) - 1) * 118 + bubble.y;
    return { transform: `translate(-50%, -50%) translate3d(${x}px, ${y}px, 0)` };
  }

  if (loadError) {
    return (
      <main className="flex min-h-dvh flex-col items-center justify-center gap-4 bg-white px-6 text-center text-[#0d293b]">
        <h1 className="text-2xl font-semibold tracking-tight">Findings could not be loaded</h1>
        <p role="alert" className="max-w-md text-sm leading-6 text-slate-600">{loadError}</p>
        <Link href="/" className="rounded-lg bg-rose-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-700">Upload a file</Link>
      </main>
    );
  }

  return (
    <main className={`min-h-dvh bg-white text-[#0d293b] ${leaving ? "analysis-exit-up" : ""}`} onAnimationEnd={(event) => {
      if (leaving && event.target === event.currentTarget) router.push(withAnalysis("/distribution", analysisId));
    }}>
      {headerVisible && (
        <header aria-hidden={!headerInteractive} className="fixed inset-x-0 top-0 z-20 h-12 border-b border-slate-200 bg-white/95 backdrop-blur-sm" style={{ opacity: progress, pointerEvents: headerInteractive ? "auto" : "none" }}>
          <div className="mx-auto flex h-12 max-w-7xl items-center justify-between px-6">
            <Link href="/" tabIndex={headerInteractive ? 0 : -1} aria-label="TraceFront home" className="rounded-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-rose-600">
              <span className="relative block h-10 w-36 overflow-hidden">
                <Image src="/tracefront-logo-black.png" alt="TraceFront" width={2091} height={752} priority className="absolute left-0 top-1/2 h-12 w-auto max-w-none -translate-y-1/2" />
              </span>
            </Link>
            <button type="button" onClick={goToDistribution} className="inline-flex h-10 items-center gap-2 rounded-full border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-900 shadow-sm transition-colors hover:border-slate-900 hover:bg-slate-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600" aria-label="Next: distribution network">
              Next <span aria-hidden="true">→</span>
            </button>
          </div>
        </header>
      )}

      <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-30">
          <div className={`findings-zero ${stage === "dash" ? "findings-zero--dash" : "findings-zero--outline"} ${counting ? "findings-zero--hide" : ""}`} />
          <span className={`findings-count ${counting ? "findings-count--visible" : ""}`} style={{ opacity: counting ? Math.max(0, 1 - progress / 0.6) : 0, transform: `translate(-50%, -50%) translateY(-${offset}px) scale(${1 - progress * 0.6})` }}>{count}</span>
          <span className={`findings-label ${count === total && counting ? "findings-label--visible" : ""}`} style={{ opacity: count === total && counting ? Math.max(0, 1 - progress / 0.6) : 0, transform: `translate(-50%, -50%) translateY(${110 - offset - progress * 66}px)` }}>Anomalies Found</span>
      </div>

      <nav aria-label="Anomaly icons" aria-hidden={stage !== "results" || progress > 0.35} className="pointer-events-none fixed inset-0 z-30" style={{ opacity: Math.max(0, 1 - progress / 0.35) }}>
        {findings.slice(0, bubbleOffsets.length).map((finding, index) => (
          <a key={finding.id} href={`#finding-${finding.id}`} aria-label={finding.type} tabIndex={stage === "results" && progress <= 0.35 ? 0 : -1} className={`absolute left-1/2 top-1/2 ${stage === "results" && progress <= 0.35 ? "pointer-events-auto" : ""}`} style={tilePosition(index)}>
            <span className={`finding-tile ${count > index ? "finding-tile--visible" : ""}`}>
              <FindingIcon type={finding.type} />
            </span>
          </a>
        ))}
      </nav>

      <section className="relative h-dvh min-h-[560px] bg-white" aria-label="Analysis result">
        {stage === "results" && <p role="status" className="sr-only">{total} {total === 1 ? "anomaly" : "anomalies"} found. Scroll to review the findings.</p>}
      </section>

      {stage === "results" && progress < 0.25 && (
        <button type="button" onClick={() => document.getElementById("findings")?.scrollIntoView({ behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" })} className="fixed bottom-8 left-1/2 z-20 flex min-h-14 -translate-x-1/2 flex-col items-center justify-center gap-1 rounded-xl px-6 text-sm font-semibold text-slate-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600" style={{ opacity: 1 - progress / 0.25 }}>
          <span>Scroll to continue</span>
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5 text-rose-600"><path d="M12 4v15m-6-6 6 6 6-6" /></svg>
        </button>
      )}

      {stage === "results" && (
        <section id="findings" aria-labelledby="findings-heading" className="min-h-dvh scroll-mt-12 bg-[#f7f9fb]">
          <div className="mx-auto max-w-6xl px-6 pb-16 pt-5">
            <div data-analysis-reveal className="analysis-content-reveal mb-8 flex flex-wrap items-center justify-between gap-4">
              <h1 id="findings-heading" className="text-3xl font-semibold tracking-tight">Findings to review</h1>
              {severityCounts && <p className="ml-auto whitespace-nowrap rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm">{severityCounts}</p>}
            </div>
            <div className="space-y-3">
              {report?.checks && <div data-analysis-reveal aria-label="Checks run on this file" className="analysis-content-reveal flex flex-wrap gap-2 pb-2">
                {report.checks.map((check) => <span key={check.check} className={`rounded-full border px-3 py-1 text-xs ${check.shipments_checked ? "border-slate-200 bg-white text-slate-700" : "border-amber-300 bg-amber-50 text-amber-900"}`}>
                  {check.label}: {check.shipments_checked ? `${check.shipments_checked}/${check.shipments_total} shipments checked` : `not checked (needs ${check.fields.join(" + ")})`}
                </span>)}
              </div>}
              {total === 0 && <p data-analysis-reveal className={`analysis-content-reveal rounded-xl border px-5 py-8 text-center text-sm ${unchecked.length ? "border-amber-300 bg-amber-50 text-amber-900" : "border-slate-200 bg-white text-slate-600"}`}>
                {noneRan ? "No checks could run: the file has no temperature, humidity, arrival, quantity or destination data. This is not a safety clearance."
                  : unchecked.length ? `No anomalies in the checks that ran. ${unchecked.length} of ${report!.checks!.length} checks had no data, so this is not a full clearance.`
                  : "No anomalies were found in the checks that ran on this file."}
              </p>}
              {findings.map((finding) => (
                <details key={finding.id} id={`finding-${finding.id}`} data-analysis-reveal className="analysis-content-reveal finding-card group scroll-mt-14 rounded-xl border border-slate-200 bg-white">
                  <summary className="finding-summary flex min-h-28 cursor-pointer items-center gap-5 px-5 py-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600">
                    <span className="w-14 shrink-0 self-center font-mono text-5xl font-light leading-none tracking-tighter text-slate-400">{finding.id}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <h2 className="text-base font-semibold leading-5 text-[#0d293b]">{finding.title}</h2>
                        <span className="inline-flex rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs font-medium text-slate-600">{finding.type}</span>
                      </div>
                      <p className="mt-1 text-sm leading-5 text-slate-600">{finding.reason}</p>
                    </div>
                    <div className="hidden shrink-0 text-right md:block">
                      <p className="font-mono text-sm font-semibold text-slate-800">{finding.batchId}</p>
                      <p className="mt-1 font-mono text-xs text-slate-500">{finding.shipmentId}</p>
                    </div>
                    <svg aria-hidden="true" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5 shrink-0 text-slate-500 transition-transform duration-200 group-open:rotate-180"><path d="m5 7.5 5 5 5-5" strokeLinecap="round" strokeLinejoin="round" /></svg>
                  </summary>
                  <div className="grid gap-4 border-t border-slate-100 bg-slate-50 px-5 py-5 text-sm sm:grid-cols-3 sm:pl-24">
                    <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Observed</p><p className="mt-1 font-medium text-slate-900">{finding.observed}</p></div>
                    <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Review limit</p><p className="mt-1 font-medium text-slate-900">{finding.reviewLimit}</p></div>
                    <div><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Source record</p><p className="mt-1 font-mono text-slate-900">{finding.sourceRecord}</p></div>
                  </div>
                </details>
              ))}
            </div>
            <div data-analysis-reveal className="analysis-content-reveal mt-8 flex justify-center border-t border-slate-200 pt-6">
              <button type="button" onClick={goToDistribution} disabled={!atBottom} className={`flex min-h-14 flex-col items-center justify-center gap-1 rounded-xl px-6 text-sm font-semibold text-slate-700 transition-all duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 ${atBottom ? "translate-y-0 opacity-100" : "pointer-events-none translate-y-2 opacity-0"}`}>
                <span>Scroll to continue</span>
                <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5 text-rose-600"><path d="M12 4v15m-6-6 6 6 6-6" /></svg>
              </button>
            </div>
          </div>
        </section>
      )}
    </main>
  );
}
