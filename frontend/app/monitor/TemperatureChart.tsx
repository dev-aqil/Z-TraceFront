"use client";

import { useEffect, useRef, useState } from "react";
import type { Monitored } from "@/lib/api";

const H = 170, LEFT = 34, RIGHT = 12, TOP = 12, BOTTOM = 22;
const SERIES = "#2a78d6";

export const clock = (iso: string) => new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const niceStep = (raw: number) => [0.5, 1, 2, 5, 10, 20, 50].find((s) => s >= raw) ?? 100;

// One series, so no legend. The limit line carries its own label; the table under the chart holds every value.
export default function TemperatureChart({ item }: { item: Monitored }) {
  const { readings, limit_c, shipment } = item;
  const [active, setActive] = useState<number | null>(null);
  // Drawn at its real width, so labels stay 10px on a phone instead of shrinking with the whole picture.
  const [W, setW] = useState(560);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setW(Math.max(240, Math.round(entry.contentRect.width))));
    if (box.current) observer.observe(box.current);
    return () => observer.disconnect();
  }, []);
  const times = readings.map((r) => Date.parse(r.at));
  const t0 = times[0], t1 = Math.max(times[times.length - 1], t0 + 60_000);
  const temps = readings.map((r) => r.temperature);
  const lo = Math.floor(Math.min(...temps, limit_c) - 1), hi = Math.ceil(Math.max(...temps, limit_c) + 1);
  const x = (t: number) => LEFT + ((t - t0) / (t1 - t0)) * (W - LEFT - RIGHT);
  const y = (c: number) => TOP + ((hi - c) / (hi - lo)) * (H - TOP - BOTTOM);
  const step = niceStep((hi - lo) / 4);
  const ticks: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step) ticks.push(Number(v.toFixed(1)));
  const path = readings.map((r, i) => `${i ? "L" : "M"}${x(times[i]).toFixed(1)},${y(r.temperature).toFixed(1)}`).join("");
  const last = readings.length - 1;

  function nearest(clientX: number, box: DOMRect) {
    const t = t0 + ((((clientX - box.left) / box.width) * W - LEFT) / (W - LEFT - RIGHT)) * (t1 - t0);
    let best = 0;
    times.forEach((value, i) => { if (Math.abs(value - t) < Math.abs(times[best] - t)) best = i; });
    return best;
  }

  const shown = active !== null && active <= last ? active : null; // readings can shrink when a replay is cleared
  const point = shown === null ? null : { left: (x(times[shown]) / W) * 100, top: (y(temps[shown]) / H) * 100 };
  const summary = `Temperature of ${shipment.shipment_code} from ${clock(readings[0].at)} to ${clock(readings[last].at)}: latest ${temps[last]} °C, peak ${item.peak.temperature} °C, limit ${limit_c} °C.`;

  return <figure className="mt-4">
    <div ref={box} className="relative">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary} tabIndex={0}
        className="block h-auto w-full touch-none rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-slate-900"
        onPointerMove={(e) => setActive(nearest(e.clientX, e.currentTarget.getBoundingClientRect()))}
        onPointerLeave={() => setActive(null)}
        onFocus={() => setActive(last)} onBlur={() => setActive(null)}
        onKeyDown={(e) => {
          if (e.key === "ArrowLeft") { e.preventDefault(); setActive((i) => Math.max(0, (i ?? last) - 1)); }
          if (e.key === "ArrowRight") { e.preventDefault(); setActive((i) => Math.min(last, (i ?? last) + 1)); }
        }}>
        {ticks.map((v) => <g key={v}>
          <line x1={LEFT} x2={W - RIGHT} y1={y(v)} y2={y(v)} stroke="#e2e8f0" strokeWidth={1} />
          <text x={LEFT - 6} y={y(v) + 3} textAnchor="end" fontSize={10} fill="#64748b">{v}</text>
        </g>)}
        <line x1={LEFT} x2={W - RIGHT} y1={y(limit_c)} y2={y(limit_c)} stroke="#0d293b" strokeWidth={1} strokeDasharray="4 3" />
        <text x={W - RIGHT} y={y(limit_c) - 4} textAnchor="end" fontSize={10} fontWeight={600} fill="#0d293b">Limit {limit_c} °C</text>
        <text x={LEFT} y={H - 6} fontSize={10} fill="#64748b">{clock(readings[0].at)}</text>
        {last > 0 && <text x={W - RIGHT} y={H - 6} textAnchor="end" fontSize={10} fill="#64748b">{clock(readings[last].at)}</text>}
        <path d={path} fill="none" stroke={SERIES} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        <circle cx={x(times[last])} cy={y(temps[last])} r={3} fill={SERIES} />
        {shown !== null && <g>
          <line x1={x(times[shown])} x2={x(times[shown])} y1={TOP} y2={H - BOTTOM} stroke="#94a3b8" strokeWidth={1} />
          <circle cx={x(times[shown])} cy={y(temps[shown])} r={4} fill="white" stroke={SERIES} strokeWidth={2} />
        </g>}
      </svg>
      {point && shown !== null && <p aria-hidden className="pointer-events-none absolute -translate-x-1/2 -translate-y-full whitespace-nowrap rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold shadow-sm"
        style={{ left: `${Math.min(88, Math.max(12, point.left))}%`, top: `calc(${point.top}% - 8px)` }}>
        {clock(readings[shown].at)} · {temps[shown]} °C
      </p>}
    </div>
    <details className="mt-2 text-xs">
      <summary className="cursor-pointer font-semibold text-slate-700 hover:text-rose-700">Show readings as a table</summary>
      <div className="mt-2 max-h-48 overflow-y-auto rounded-lg border border-slate-200">
        <table className="w-full text-left">
          <thead className="sticky top-0 bg-slate-50 text-slate-600"><tr><th scope="col" className="px-3 py-1.5 font-semibold">Time</th><th scope="col" className="px-3 py-1.5 text-right font-semibold">°C</th></tr></thead>
          <tbody>{readings.map((r) => <tr key={r.at} className="border-t border-slate-100">
            <td className="px-3 py-1">{new Date(r.at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}</td>
            <td className={`px-3 py-1 text-right tabular-nums ${r.temperature > limit_c ? "font-semibold" : ""}`}>{r.temperature.toFixed(1)}{r.temperature > limit_c && " (above limit)"}</td>
          </tr>)}</tbody>
        </table>
      </div>
    </details>
  </figure>;
}
