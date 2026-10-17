"use client";

import { useMemo, useRef, useState } from "react";
import type { Graph, GraphNode } from "@/lib/api";

type NetworkNode = GraphNode & { x: number; y: number; width: number; height: number };
export type ReviewAlert = { shipmentId: string; type: string; reason: string };

const COLUMNS: Record<GraphNode["kind"], { x: number; width: number; height: number }> = {
  root: { x: 18, width: 185, height: 72 },
  route: { x: 275, width: 170, height: 42 },
  batch: { x: 520, width: 185, height: 40 },
  recipient: { x: 765, width: 230, height: 38 },
};
const ROW = 43; // spacing between receiving sites
const GROUP_GAP = 12; // extra space after each batch, and again after each route
const WIDTH = 1070;
const MIN_HEIGHT = 430;

// Entrance: card 260ms, distributor 420ms, routes 540ms, batches 700ms, sites from 870ms, alert 1550ms.
const GRAPH_TIMING = {
  startMs: { root: 420, route: 540, batch: 700, recipient: 870 },
  staggerMs: 28,
  lineLeadMs: 60,
  alertMs: 1550,
} as const;

// Tidy tree: sites stack top to bottom and each parent centres on its children. A node with two parents sits under the first.
function layout(graph: Graph) {
  const parent = new Map<string, string>();
  const children = new Map<string, string[]>();
  for (const [from, to] of graph.edges) {
    if (!parent.has(to)) parent.set(to, from);
    children.set(from, [...(children.get(from) ?? []), to]);
  }
  const source = new Map(graph.nodes.map((node) => [node.id, node]));
  const placed = new Map<string, NetworkNode>();
  let cursor = 17;
  const place = (id: string): number => {
    const node = source.get(id)!;
    const size = COLUMNS[node.kind];
    const kids = (children.get(id) ?? []).filter((kid) => parent.get(kid) === id && source.has(kid));
    let center = cursor + size.height / 2;
    if (kids.length) {
      const centers = kids.map(place);
      center = (centers[0] + centers[centers.length - 1]) / 2;
      if (node.kind === "batch" || node.kind === "route") cursor += GROUP_GAP;
    } else {
      cursor += ROW;
    }
    placed.set(id, { ...node, ...size, y: center - size.height / 2 });
    return center;
  };
  graph.nodes.filter((node) => !parent.has(node.id)).forEach((node) => place(node.id));

  let route = 0;
  const nodes = graph.nodes.flatMap((node) => {
    const p = placed.get(node.id);
    return !p ? [] : [p.kind === "route" ? { ...p, label: `${++route}. ${p.label}` } : p];
  });
  const byId = new Map(nodes.map((node) => [node.id, node]));

  const highlighted = new Set<string>();
  for (const node of nodes) {
    if (node.kind !== "recipient" || !node.flagged) continue;
    for (let id = node.id; parent.has(id) && !highlighted.has(`${parent.get(id)}>${id}`); id = parent.get(id)!) {
      highlighted.add(`${parent.get(id)}>${id}`);
    }
  }

  const delay = new Map<string, number>();
  const layerCounts: Record<GraphNode["kind"], number> = { root: 0, route: 0, batch: 0, recipient: 0 };
  for (const node of nodes) delay.set(node.id, GRAPH_TIMING.startMs[node.kind] + layerCounts[node.kind]++ * GRAPH_TIMING.staggerMs);

  const edges = graph.edges.filter(([from, to]) => byId.has(from) && byId.has(to));
  return { nodes, byId, edges, highlighted, delay, height: Math.max(MIN_HEIGHT, cursor + 10) };
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

function WarningMarker({ label, alert, top }: { label: string; alert: ReviewAlert; top: number }) {
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
    <div className="distribution-warning-enter absolute z-10" style={{ left: 1015, top, animationDelay: `${GRAPH_TIMING.alertMs}ms` }} onAnimationStart={(event) => { if (event.target === event.currentTarget) triggerPing(); }} onMouseEnter={reveal} onMouseLeave={() => setHovered(false)} onFocus={reveal} onBlur={() => setHovered(false)} onKeyDown={(event) => { if (event.key === "Escape") { setPinned(false); setHovered(false); } }}>
      <button type="button" aria-label={label} aria-expanded={open} aria-controls="review-signal" onClick={() => { triggerPing(); setSeen(true); setPinned((value) => !value); }} className="relative flex h-10 w-10 items-center justify-center rounded-lg transition-transform hover:scale-105 active:scale-95 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-500">
        <svg aria-hidden="true" viewBox="0 0 52 48" className="h-full w-full drop-shadow-[0_0_10px_rgba(245,158,11,0.6)]">
          <path d="M26 3 50 45H2L26 3Z" fill="#f59e0b" stroke="white" strokeWidth="2.5" />
          <path d="M26 17v13" stroke="#111827" strokeWidth="3" strokeLinecap="round" />
          <circle cx="26" cy="36" r="2" fill="#111827" />
        </svg>
        {!seen && <span aria-hidden="true" className="absolute -right-0.5 -top-0.5 h-3.5 w-3.5 rounded-full border-2 border-white bg-rose-600 shadow-sm" />}
      </button>
      <div id="review-signal" role="note" aria-hidden={!open} className={`distribution-warning-popover absolute right-0 top-[38px] w-[350px] rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-950 shadow-xl ${open ? "distribution-warning-popover--open" : ""}`}>
        <strong className="block font-bold">{alert.shipmentId}: {alert.type} signal</strong>
        <span>{alert.reason} Confirm the shipment and product status with the receiving site.</span>
      </div>
    </div>
  );
}

export default function DistributionTree({ graph, alert }: { graph: Graph; alert: ReviewAlert | null }) {
  const { nodes, byId, edges, highlighted, delay, height } = useMemo(() => layout(graph), [graph]);
  const target = alert ? byId.get(`shipment:${alert.shipmentId}`) : undefined;
  const count = (kind: GraphNode["kind"]) => nodes.filter((node) => node.kind === kind).length;
  const marked = nodes.filter((node) => node.kind === "recipient" && node.flagged).map((node) => node.detail ? `${node.detail} to ${node.label}` : node.label);

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-[#f8fafc] [scrollbar-color:#cbd5e1_#f8fafc]">
      <div className="relative mx-auto w-[1070px]" style={{ height }}>
        <p className="sr-only">Distribution tree: {count("root")} distributor(s) supply {count("route")} route groups, {count("batch")} batches and {count("recipient")} receiving sites. {marked.length ? `Marked for review: ${marked.join("; ")}.` : "No shipment is marked for review."}</p>
        <svg aria-hidden="true" viewBox={`0 0 ${WIDTH} ${height}`} className="pointer-events-none absolute inset-0 h-full w-full" fill="none">
          {edges.map(([sourceId, destinationId]) => {
            const lit = highlighted.has(`${sourceId}>${destinationId}`);
            return <path key={`${sourceId}-${destinationId}`} className="distribution-graph-item" style={{ animationDelay: `${delay.get(destinationId)! - GRAPH_TIMING.lineLeadMs}ms` }} d={edgePath(byId.get(sourceId)!, byId.get(destinationId)!)} stroke={lit ? "#f59e0b" : "#94a3b8"} strokeWidth={lit ? 2.5 : 2} strokeLinecap="round" />;
          })}
        </svg>
        {nodes.map((node) => (
          <div key={node.id} title={node.detail ? `${node.label} · ${node.detail}` : node.label} className={`distribution-graph-item distribution-tree-node distribution-tree-node--${node.kind} ${node.flagged ? "distribution-tree-node--flagged" : ""}`} style={{ left: node.x, top: node.y, width: node.width, height: node.height, animationDelay: `${delay.get(node.id)}ms` }}>
            <span className="min-w-0 truncate">{node.label}</span>
            {node.kind === "root" && <span className="mt-1 block text-[11px] font-medium opacity-80">{node.detail}</span>}
          </div>
        ))}
        {alert && target && <WarningMarker top={target.y - 1} alert={alert} label={`Review ${alert.type.toLowerCase()} signal on shipment ${alert.shipmentId} to ${target.label}`} />}
      </div>
    </div>
  );
}
