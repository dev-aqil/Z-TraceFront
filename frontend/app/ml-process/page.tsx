"use client";

import { useEffect, useRef, useState } from "react";

const CONNECT_START = 1800;
const CONNECT_END = 4800;
const DOTS_FULL = 6300;
const DOTS_DECLINE_START = 8200;
const DOTS_END = 11200;
const RELEASE_START = 11600;
const RELEASE_END = 13000;
const CLOSE_START = 13300;
const CLOSE_END = 16100;
const DURATION = 19100;
const NODE_COUNT = 96;
const INITIAL_EDGE_COUNT = 156;
const EDGE_COUNT = 312;
const STAGES = [
  { at: 0, title: "Signals appear", detail: "Individual records spread into view." },
  { at: CONNECT_START, title: "Relationships form", detail: "Connections draw across the network for three seconds." },
  { at: CONNECT_END, title: "Evidence moves", detail: "Links refresh while signals travel rapidly through them." },
  { at: DOTS_DECLINE_START, title: "Signals settle", detail: "Traveling dots thin out over three seconds." },
  { at: RELEASE_START, title: "Connections release", detail: "Each line retracts into its two dash endpoints." },
  { at: CLOSE_START, title: "Circle closes", detail: "Dashes gather at the first signal." },
  { at: CLOSE_END, title: "Focus on signal", detail: "The camera slowly moves in on the final dash." },
];

type Point = { x: number; y: number };
type Edge = { from: number; to: number; bend: number };

const edges: Edge[] = Array.from({ length: EDGE_COUNT }, (_, index) => {
  const from = (index * 37 + 11) % NODE_COUNT;
  const distance = 13 + ((index * 29 + 17) % 69);
  return { from, to: (from + distance) % NODE_COUNT, bend: ((index * 19) % 7) - 3 };
});

const clamp = (value: number) => Math.max(0, Math.min(1, value));
const ease = (value: number) => 1 - Math.pow(1 - clamp(value), 3);
const smooth = (value: number) => {
  const t = clamp(value);
  return t * t * (3 - 2 * t);
};

function curvePoint(start: Point, control: Point, end: Point, amount: number): Point {
  const t = clamp(amount);
  const inverse = 1 - t;
  return {
    x: inverse * inverse * start.x + 2 * inverse * t * control.x + t * t * end.x,
    y: inverse * inverse * start.y + 2 * inverse * t * control.y + t * t * end.y,
  };
}

function edgeRange(index: number, time: number): { from: number; to: number } {
  if (time < CONNECT_END) {
    if (index >= INITIAL_EDGE_COUNT) return { from: 0, to: 0 };
    return { from: 0, to: clamp(((time - CONNECT_START) / (CONNECT_END - CONNECT_START)) * INITIAL_EDGE_COUNT - index) };
  }

  // Initial links start fully formed. A second set begins hidden, then both
  // sets continuously enter, hold, and retract on staggered cycles.
  const offset = index < INITIAL_EDGE_COUNT
    ? 0.18 + (((index * 53) % INITIAL_EDGE_COUNT) / INITIAL_EDGE_COUNT) * 0.43
    : 0.86 + ((((index - INITIAL_EDGE_COUNT) * 37) % INITIAL_EDGE_COUNT) / INITIAL_EDGE_COUNT) * 0.13;
  const phase = (offset + (Math.min(time, DOTS_DECLINE_START) - CONNECT_END) / 2600) % 1;
  let range: { from: number; to: number };
  if (phase < 0.17) range = { from: 0, to: ease(phase / 0.17) };
  else if (phase < 0.65) range = { from: 0, to: 1 };
  else if (phase < 0.85) {
    const retreat = ease((phase - 0.65) / 0.2) * 0.5;
    range = { from: retreat, to: 1 - retreat };
  } else range = { from: 0, to: 0 };

  if (time < DOTS_DECLINE_START) return range;
  const settle = ease((time - DOTS_DECLINE_START) / 500);
  if (range.to - range.from >= 0.5) {
    return { from: range.from * (1 - settle), to: range.to + (1 - range.to) * settle };
  }
  const midpoint = (range.from + range.to) / 2;
  return {
    from: range.from + (midpoint - range.from) * settle,
    to: range.to + (midpoint - range.to) * settle,
  };
}

function stageFor(time: number) {
  if (time >= STAGES[6].at) return 6;
  if (time >= STAGES[5].at) return 5;
  if (time >= STAGES[4].at) return 4;
  if (time >= STAGES[3].at) return 3;
  if (time >= STAGES[2].at) return 2;
  if (time >= STAGES[1].at) return 1;
  return 0;
}

function draw(canvas: HTMLCanvasElement, time: number) {
  const context = canvas.getContext("2d");
  if (!context) return;

  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width || !height) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const pixelWidth = Math.round(width * dpr);
  const pixelHeight = Math.round(height * dpr);
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth;
    canvas.height = pixelHeight;
  }
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, width, height);

  const center = { x: width / 2, y: height / 2 };
  const maximumRadius = Math.min(width, height) * 0.382;
  const expand = ease(time / 1800);
  const disconnect = smooth((time - RELEASE_START) / (RELEASE_END - RELEASE_START));
  const gather = smooth((time - CLOSE_START) / (CLOSE_END - CLOSE_START));
  const zoomProgress = smooth((time - CLOSE_END) / (DURATION - CLOSE_END));
  const radius = maximumRadius * expand;
  const zoom = 1 + 9 * zoomProgress;
  // Keep the final dash moving directly toward screen center as the camera zooms.
  const zoomFocus = {
    x: center.x,
    y: center.y - maximumRadius + (maximumRadius * (1 - zoomProgress)) / zoom,
  };
  context.save();
  context.translate(center.x, center.y);
  context.scale(zoom, zoom);
  context.translate(-zoomFocus.x, -zoomFocus.y);
  const nodePoint = (index: number): Point => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / NODE_COUNT;
    return {
      x: center.x + Math.cos(angle) * radius,
      y: center.y + Math.sin(angle) * radius,
    };
  };
  const controlPoint = (start: Point, end: Point, bend: number): Point => ({
    x: center.x + ((start.x + end.x) / 2 - center.x) * 0.2 + bend * 2.5,
    y: center.y + ((start.y + end.y) / 2 - center.y) * 0.2 - bend * 2.5,
  });

  // A faint guide circle gives the moving dashes a stable visual destination.
  if (time < RELEASE_START) {
    context.beginPath();
    context.arc(center.x, center.y, maximumRadius, 0, Math.PI * 2);
    context.strokeStyle = "rgba(148, 163, 184, 0.12)";
    context.lineWidth = 1;
    context.stroke();
  }

  const visibleEdges: Array<{ start: Point; control: Point; end: Point; from: number; to: number } | undefined> = [];
  context.lineWidth = Math.max(0.7, width / 900);
  for (let index = 0; index < EDGE_COUNT && disconnect < 1; index += 1) {
    const range = edgeRange(index, time);
    if (range.to - range.from < 0.01) continue;
    const edge = edges[index];
    const start = nodePoint(edge.from);
    const end = nodePoint(edge.to);
    const control = controlPoint(start, end, edge.bend);
    const strokeSegment = (from: number, to: number) => {
      if (to - from < 0.005) return;
      const steps = Math.max(1, Math.ceil((to - from) * 14));
      const first = curvePoint(start, control, end, from);
      context.beginPath();
      context.moveTo(first.x, first.y);
      for (let step = 1; step <= steps; step += 1) {
        const point = curvePoint(start, control, end, from + ((to - from) * step) / steps);
        context.lineTo(point.x, point.y);
      }
      context.strokeStyle = `rgba(100, 116, 139, ${0.17 * (1 - ease((disconnect - 0.75) / 0.25))})`;
      context.stroke();
    };

    if (disconnect > 0) {
      const midpoint = (range.from + range.to) / 2;
      strokeSegment(range.from, range.from + (midpoint - range.from) * (1 - disconnect));
      strokeSegment(range.to - (range.to - midpoint) * (1 - disconnect), range.to);
    } else {
      strokeSegment(range.from, range.to);
    }
    visibleEdges[index] = { start, control, end, from: range.from, to: range.to };
  }

  const flow = clamp((time - CONNECT_END) / (DOTS_FULL - CONNECT_END));
  const decline = clamp((time - DOTS_DECLINE_START) / (DOTS_END - DOTS_DECLINE_START));
  const particleCount = Math.floor((18 + flow * 200) * (1 - decline) * (1 - decline));
  const flowTime = Math.max(0, time - CONNECT_END);
  const rampTime = Math.min(flowTime, DOTS_FULL - CONNECT_END);
  const travel = 0.00022 * flowTime
    + (0.0021 * rampTime * rampTime * rampTime) / (3 * (DOTS_FULL - CONNECT_END) ** 2)
    + 0.0021 * Math.max(0, flowTime - (DOTS_FULL - CONNECT_END));
  if (flow > 0 && particleCount > 0) {
    for (let index = 0; index < particleCount; index += 1) {
      const edge = visibleEdges[(index * 47) % EDGE_COUNT];
      if (!edge || edge.to - edge.from < 0.15) continue;
      const offset = ((index * 43) % 101) / 101;
      const position = edge.from + ((offset + travel) % 1) * (edge.to - edge.from);
      const point = curvePoint(edge.start, edge.control, edge.end, position);
      context.beginPath();
      context.arc(point.x, point.y, 1.25 + flow * 0.9, 0, Math.PI * 2);
      context.fillStyle = `rgba(225, 29, 72, ${0.32 + flow * 0.52})`;
      context.fill();
    }
  }

  // Compress the arc toward dash zero at the top of the original circle.
  // Drawing it last keeps the destination visible while the other dashes overlap.
  for (let index = NODE_COUNT - 1; index >= 0; index -= 1) {
    const angle = -Math.PI / 2 + ((index * Math.PI * 2) / NODE_COUNT) * (1 - gather);
    const point = {
      x: center.x + Math.cos(angle) * radius,
      y: center.y + Math.sin(angle) * radius,
    };
    const pulse = particleCount > 0 ? Math.max(0, Math.sin(time * 0.006 + index * 0.91)) : 0;
    const fade = index === 0 ? 1 : 1 - ease((gather - 0.55) / 0.45);
    context.save();
    context.translate(point.x, point.y);
    context.rotate(angle + Math.PI / 2);
    context.fillStyle = index === 0 && gather > 0
      ? "rgba(225, 29, 72, 1)"
      : `rgba(51, 65, 85, ${(0.56 + pulse * 0.35) * fade})`;
    context.fillRect(-1.2, -3.6, 2.4, 7.2);
    context.restore();
  }
  context.restore();
}

export default function MlProcess() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const elapsedRef = useRef(0);
  const [playing, setPlaying] = useState(true);
  const [replayKey, setReplayKey] = useState(0);
  const [stage, setStage] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setReducedMotion(preference.matches);
    updatePreference();
    preference.addEventListener("change", updatePreference);
    return () => preference.removeEventListener("change", updatePreference);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const observer = new ResizeObserver(() => draw(canvas, reducedMotion ? DURATION : elapsedRef.current));
    observer.observe(canvas);
    draw(canvas, reducedMotion ? DURATION : elapsedRef.current);
    return () => observer.disconnect();
  }, [reducedMotion]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || reducedMotion || !playing) return;
    let frameId = 0;
    let previousTime: number | null = null;

    const tick = (now: number) => {
      if (previousTime !== null && !document.hidden) {
        elapsedRef.current = Math.min(DURATION, elapsedRef.current + Math.min(now - previousTime, 100));
      }
      previousTime = now;
      draw(canvas, elapsedRef.current);
      const nextStage = stageFor(elapsedRef.current);
      setStage((current) => (current === nextStage ? current : nextStage));
      if (elapsedRef.current < DURATION) {
        frameId = requestAnimationFrame(tick);
      } else {
        setPlaying(false);
      }
    };

    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [playing, reducedMotion, replayKey]);

  function replay() {
    elapsedRef.current = 0;
    setStage(0);
    setReplayKey((value) => value + 1);
    setPlaying(true);
    if (canvasRef.current) draw(canvasRef.current, reducedMotion ? DURATION : 0);
  }

  const currentStage = reducedMotion ? STAGES[6] : STAGES[stage];

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12 lg:px-8">
      <header className="mb-7 flex flex-wrap items-start justify-between gap-5">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-rose-700 dark:text-rose-300">
            Tracefront / Concept preview
          </p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">From signals to a decision</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-700 dark:text-slate-300">
            A visual story for how evidence from many records can come together for human review.
          </p>
        </div>
        <a href="/" className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600 dark:border-slate-700 dark:hover:bg-slate-800">
          Back to dashboard
        </a>
      </header>

      <section aria-label="Machine learning concept animation" className="overflow-hidden rounded-2xl border border-rose-200 bg-white shadow-sm dark:border-slate-700">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rose-100 bg-rose-50 px-5 py-4 dark:border-slate-700 dark:bg-slate-800 sm:px-7">
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest text-rose-700 dark:text-rose-300">Illustrative animation</p>
            <h2 className="mt-1 text-lg font-semibold text-slate-900 dark:text-white" aria-live="polite">{currentStage.title}</h2>
            <p className="text-sm text-slate-600 dark:text-slate-300">{currentStage.detail}</p>
          </div>
          <div className="flex gap-2">
            {reducedMotion && <span className="self-center text-xs text-slate-600 dark:text-slate-300">Static view for reduced motion</span>}
            {!reducedMotion && elapsedRef.current < DURATION && (
              <button type="button" onClick={() => setPlaying((value) => !value)} className="min-h-10 rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-900 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600">
                {playing ? "Pause" : "Play"}
              </button>
            )}
            {!reducedMotion && (
              <button type="button" onClick={replay} className="min-h-10 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white hover:bg-rose-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-rose-600">
                Replay
              </button>
            )}
          </div>
        </div>
        <div className="relative mx-auto max-w-[680px] p-3 sm:p-6">
          <canvas ref={canvasRef} aria-hidden="true" className="block aspect-square w-full rounded-xl bg-white" />
        </div>
      </section>

      <ol className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Animation stages">
        {STAGES.map((item, index) => (
          <li key={item.title} className={`rounded-xl border px-4 py-3 text-sm ${index === (reducedMotion ? 6 : stage) ? "border-rose-300 bg-rose-50 text-rose-950 dark:border-rose-700 dark:bg-rose-950 dark:text-rose-100" : "border-slate-200 bg-white text-slate-600 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"}`}>
            <span className="mr-2 font-semibold">0{index + 1}</span>{item.title}
          </li>
        ))}
      </ol>
      <p className="mt-5 text-xs leading-5 text-slate-600 dark:text-slate-400">
        Concept visualization only. The moving lines and particles do not represent a trained model or a live supplier analysis.
      </p>
    </main>
  );
}
