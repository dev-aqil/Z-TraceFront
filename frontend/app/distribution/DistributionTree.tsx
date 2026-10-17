"use client";

import { useRef, useState } from "react";

type NetworkNode = {
  id: string;
  label: string;
  detail?: string;
  kind: "root" | "route" | "batch" | "recipient";
  x: number;
  y: number;
  width: number;
  height: number;
  flagged?: boolean;
};

const nodes: NetworkNode[] = [
  { id: "root", label: "FOOD PROCESSING", detail: "Main distributor", kind: "root", x: 18, y: 180, width: 185, height: 72 },

  { id: "protein", label: "1. Protein cold-chain", kind: "route", x: 275, y: 35, width: 170, height: 42 },
  { id: "marinades", label: "2. Broth & marinades", kind: "route", x: 275, y: 125, width: 170, height: 42 },
  { id: "produce", label: "3. Pre-cut produce", kind: "route", x: 275, y: 235, width: 170, height: 42 },
  { id: "dry", label: "4. Dry goods", kind: "route", x: 275, y: 345, width: 170, height: 42 },

  { id: "rm402", label: "RM-402 · Marinated chicken", kind: "batch", x: 520, y: 35, width: 185, height: 42, flagged: true },
  { id: "sauce", label: "Central kitchen supply", kind: "batch", x: 520, y: 115, width: 185, height: 38 },
  { id: "grill", label: "Restaurant supply", kind: "batch", x: 520, y: 158, width: 185, height: 38 },
  { id: "canteen", label: "Industrial canteen", kind: "batch", x: 520, y: 225, width: 185, height: 38 },
  { id: "cloud", label: "Cloud kitchen", kind: "batch", x: 520, y: 268, width: 185, height: 38 },
  { id: "bakery", label: "Bakery supply", kind: "batch", x: 520, y: 335, width: 185, height: 38 },
  { id: "hotel", label: "Hospitality kitchen", kind: "batch", x: 520, y: 378, width: 185, height: 38 },

  { id: "qsr", label: "Central Kitchen, QSR Group A", detail: "SHIP-017", kind: "recipient", x: 765, y: 17, width: 230, height: 38, flagged: true },
  { id: "ramen", label: "Ramen Production Kitchen", detail: "SHIP-018", kind: "recipient", x: 765, y: 60, width: 230, height: 38 },
  { id: "central", label: "Central Kitchen B", kind: "recipient", x: 765, y: 115, width: 230, height: 38 },
  { id: "restaurant", label: "Restaurant & Grill", kind: "recipient", x: 765, y: 158, width: 230, height: 38 },
  { id: "canteen-dest", label: "Industrial Canteen", kind: "recipient", x: 765, y: 225, width: 230, height: 38 },
  { id: "cloud-dest", label: "Cloud Kitchen North", kind: "recipient", x: 765, y: 268, width: 230, height: 38 },
  { id: "bakery-dest", label: "Bakery Production B2B", kind: "recipient", x: 765, y: 335, width: 230, height: 38 },
  { id: "hotel-dest", label: "Banquet & Hotel Kitchen", kind: "recipient", x: 765, y: 378, width: 230, height: 38 },
];

const edges: [string, string][] = [
  ["root", "protein"], ["root", "marinades"], ["root", "produce"], ["root", "dry"],
  ["protein", "rm402"], ["rm402", "qsr"], ["rm402", "ramen"],
  ["marinades", "sauce"], ["marinades", "grill"], ["sauce", "central"], ["grill", "restaurant"],
  ["produce", "canteen"], ["produce", "cloud"], ["canteen", "canteen-dest"], ["cloud", "cloud-dest"],
  ["dry", "bakery"], ["dry", "hotel"], ["bakery", "bakery-dest"], ["hotel", "hotel-dest"],
];

const byId = new Map(nodes.map((node) => [node.id, node]));

// Entrance: card 260ms, distributor 420ms, routes 540ms, batches 700ms, sites finish 1446ms, alert 1550ms.
const GRAPH_TIMING = {
  startMs: { root: 420, route: 540, batch: 700, recipient: 870 },
  staggerMs: 28,
  lineLeadMs: 60,
  alertMs: 1550,
} as const;

const graphNodeDelay = new Map<string, number>();
const layerCounts: Record<NetworkNode["kind"], number> = { root: 0, route: 0, batch: 0, recipient: 0 };
for (const node of nodes) {
  graphNodeDelay.set(node.id, GRAPH_TIMING.startMs[node.kind] + layerCounts[node.kind] * GRAPH_TIMING.staggerMs);
  layerCounts[node.kind] += 1;
}

function edgePath(source: NetworkNode, destination: NetworkNode) {
  const x1 = source.x + source.width;
  const y1 = source.y + source.height / 2;
  const x2 = destination.x;
  const y2 = destination.y + destination.height / 2;
  const handle = Math.min(80, (x2 - x1) * 0.55);
  return `M ${x1} ${y1} C ${x1 + handle} ${y1}, ${x2 - handle} ${y2}, ${x2} ${y2}`;
}

async function playWarningPing(): Promise<boolean> {
  if (!window.AudioContext) return false;
  let context: AudioContext | undefined;
  try {
    context = new AudioContext();
    if (context.state === "suspended") {
      await Promise.race([
        context.resume(),
        new Promise<void>((resolve) => window.setTimeout(resolve, 120)),
      ]);
    }
    if (context.state !== "running") {
      void context.close();
      return false;
    }

    const oscillator = context.createOscillator();
    const gain = context.createGain();
    const start = context.currentTime;
    oscillator.type = "sine";
    oscillator.frequency.setValueAtTime(1047, start);
    oscillator.frequency.exponentialRampToValueAtTime(784, start + 0.24);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(0.08, start + 0.012);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.28);
    oscillator.connect(gain).connect(context.destination);
    oscillator.onended = () => { void context?.close(); };
    oscillator.start(start);
    oscillator.stop(start + 0.3);
    return true;
  } catch {
    if (context && context.state !== "closed") void context.close();
    return false;
  }
}

function WarningMarker({ label }: { label: string }) {
  const [hovered, setHovered] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [seen, setSeen] = useState(false);
  const pingPlayed = useRef(false);
  const pingPending = useRef(false);
  const open = hovered || pinned;

  function triggerPing() {
    if (pingPlayed.current || pingPending.current) return;
    pingPending.current = true;
    void playWarningPing().then((played) => {
      pingPlayed.current = played;
      pingPending.current = false;
    });
  }

  function reveal() {
    setHovered(true);
    setSeen(true);
  }

  return (
    <div className="distribution-warning-enter absolute z-10" style={{ left: 1015, top: 16, animationDelay: `${GRAPH_TIMING.alertMs}ms` }} onAnimationStart={(event) => { if (event.target === event.currentTarget) triggerPing(); }} onMouseEnter={reveal} onMouseLeave={() => setHovered(false)} onFocus={reveal} onBlur={() => setHovered(false)} onKeyDown={(event) => { if (event.key === "Escape") { setPinned(false); setHovered(false); } }}>
      <button type="button" aria-label={label} aria-expanded={open} aria-controls="review-signal" onClick={() => { triggerPing(); setSeen(true); setPinned((value) => !value); }} className="relative flex h-10 w-10 items-center justify-center rounded-lg transition-transform hover:scale-105 active:scale-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500">
        <svg aria-hidden="true" viewBox="0 0 52 48" className="h-full w-full drop-shadow-[0_0_10px_rgba(245,158,11,0.6)]">
          <path d="M26 3 50 45H2L26 3Z" fill="#f59e0b" stroke="white" strokeWidth="2.5" />
          <path d="M26 17v13" stroke="#111827" strokeWidth="3" strokeLinecap="round" />
          <circle cx="26" cy="36" r="2" fill="#111827" />
        </svg>
        {!seen && <span aria-hidden="true" className="absolute -right-0.5 -top-0.5 h-3.5 w-3.5 rounded-full border-2 border-white bg-rose-600 shadow-sm" />}
      </button>
      <div id="review-signal" role="note" aria-hidden={!open} className={`distribution-warning-popover absolute right-0 top-[38px] w-[350px] rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950 shadow-xl ${open ? "distribution-warning-popover--open" : ""}`}>
        <strong className="block font-bold">SHIP-017: Temperature signal</strong>
        <span>Recorded at 8.4°C against a 7°C review limit. Confirm the shipment and product status with the receiving kitchen.</span>
      </div>
    </div>
  );
}

export default function DistributionTree() {
  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-[#f8fafc] [scrollbar-color:#cbd5e1_#f8fafc]">
      <div className="relative mx-auto h-[430px] w-[1070px]">
        <p className="sr-only">Distribution tree: the food processing distributor supplies four route groups. Batch RM-402 goes to Central Kitchen, QSR Group A and Ramen Production Kitchen. SHIP-017 to Central Kitchen is marked for review.</p>
        <svg aria-hidden="true" viewBox="0 0 1070 430" className="pointer-events-none absolute inset-0 h-full w-full" fill="none">
          {edges.map(([sourceId, destinationId]) => {
            const source = byId.get(sourceId)!;
            const destination = byId.get(destinationId)!;
            const highlighted = ["root:protein", "protein:rm402", "rm402:qsr"].includes(`${sourceId}:${destinationId}`);
            return <path key={`${sourceId}-${destinationId}`} className="distribution-graph-item" style={{ animationDelay: `${graphNodeDelay.get(destinationId)! - GRAPH_TIMING.lineLeadMs}ms` }} d={edgePath(source, destination)} stroke={highlighted ? "#f59e0b" : "#94a3b8"} strokeWidth={highlighted ? 2.5 : 2} strokeLinecap="round" />;
          })}
        </svg>
        {nodes.map((node) => (
          <div key={node.id} title={node.detail ? `${node.label} · ${node.detail}` : node.label} className={`distribution-graph-item distribution-tree-node distribution-tree-node--${node.kind} ${node.flagged ? "distribution-tree-node--flagged" : ""}`} style={{ left: node.x, top: node.y, width: node.width, height: node.height, animationDelay: `${graphNodeDelay.get(node.id)}ms` }}>
            <span className="min-w-0 truncate">{node.label}</span>
            {node.kind === "root" && <span className="mt-1 block text-[11px] font-medium opacity-80">{node.detail}</span>}
          </div>
        ))}
        <WarningMarker label="Review temperature signal on shipment SHIP-017 to Central Kitchen, QSR Group A" />
      </div>
    </div>
  );
}
