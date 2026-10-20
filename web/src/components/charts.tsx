import clsx from "clsx";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";

import { spring } from "@/lib/motion";

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

function niceMax(value: number): number {
  if (value <= 0) return 1;
  const exp = Math.pow(10, Math.floor(Math.log10(value)));
  const f = value / exp;
  const nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
  return nice * exp;
}

/** Single-series columns: one baseline, thin bars, per-bar hover/focus readout. */
export function ColumnChart({ data, format, height = 180, label }: {
  data: { label: string; value: number }[];
  format: (n: number) => string;
  height?: number;
  label: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const max = useMemo(() => niceMax(Math.max(0, ...data.map((d) => d.value))), [data]);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);
  const padLeft = 44;
  const padBottom = 22;
  const plotH = height - padBottom - 8;
  const bandPct = data.length ? 100 / data.length : 100;

  return (
    <figure className="relative" aria-label={label}>
      <div className="relative" style={{ height }}>
        {/* gridlines and y ticks */}
        {ticks.map((t) => {
          const y = 8 + plotH - (t / max) * plotH;
          return (
            <div key={t} className="absolute left-0 right-0 flex items-center" style={{ top: y }}>
              <span className="tabular w-10 -translate-y-1/2 pr-2 text-right text-caption text-ink-3">{format(t)}</span>
              <span className="h-px flex-1 -translate-y-1/2 bg-line" />
            </div>
          );
        })}
        {/* bars */}
        <div className="absolute bottom-[22px] right-0 top-2 flex" style={{ left: padLeft }}>
          {data.map((d, i) => {
            const h = max ? (d.value / max) * plotH : 0;
            return (
              <button
                key={d.label}
                type="button"
                className="group relative flex h-full flex-1 items-end justify-center outline-none"
                style={{ maxWidth: `${bandPct}%` }}
                onPointerEnter={() => setActive(i)}
                onPointerLeave={() => setActive(null)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
                aria-label={`${d.label}: ${format(d.value)}`}
              >
                <motion.span
                  className={clsx("block w-full max-w-6 rounded-t-[4px] bg-viz-1 transition-[filter]", active === i && "brightness-125")}
                  initial={{ height: 0 }}
                  animate={{ height: Math.max(d.value > 0 ? 2 : 0, h) }}
                  transition={spring.smooth}
                />
                {active === i && (
                  <motion.span
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={spring.snappy}
                    className="pointer-events-none absolute z-10 whitespace-nowrap rounded-control border border-line bg-overlay px-2.5 py-1.5 text-left shadow-float"
                    style={{ bottom: Math.min(h + 8, plotH - 30) }}
                  >
                    <span className="tabular block text-small font-semibold text-ink">{format(d.value)}</span>
                    <span className="block text-caption text-ink-3">{d.label}</span>
                  </motion.span>
                )}
              </button>
            );
          })}
        </div>
        {/* x labels */}
        <div className="absolute bottom-0 right-0 flex" style={{ left: padLeft }}>
          {data.map((d, i) => (
            <span
              key={d.label}
              className="flex-1 truncate text-center text-caption text-ink-3"
              style={{ visibility: data.length > 10 && i % Math.ceil(data.length / 8) !== 0 ? "hidden" : "visible" }}
            >
              {d.label}
            </span>
          ))}
        </div>
      </div>
    </figure>
  );
}

export interface StackSeries {
  key: string;
  label: string;
  color: string;
}

export interface StackColumn {
  id: string;
  label: string;
  sub?: string;
  values: Record<string, number>;
  /** Items folded into one series (e.g. "Other"), listed under it in the readout. */
  breakdown?: Record<string, { label: string; value: number }[]>;
  /** An extra line in the readout, e.g. the cost. */
  note?: string;
  disabled?: boolean;
}

/**
 * Stacked columns, one per item. Series stack bottom → top in the order given, separated by 2px
 * surface gaps, with a 4px rounded cap. Hovering or focusing a column shows every series in it;
 * the tallest and the last column carry their total on the cap. The legend is always shown.
 */
export function StackedColumnChart({ columns, series, format, height = 280, label, onSelect, selectHint }: {
  columns: StackColumn[];
  series: StackSeries[];
  format: (n: number) => string;
  height?: number;
  label: string;
  onSelect?: (id: string) => void;
  selectHint?: string;
}) {
  const [active, setActive] = useState<number | null>(null);
  const [plotRef, plotWidth] = useWidth<HTMLDivElement>();
  const totals = columns.map((c) => series.reduce((sum, s) => sum + (c.values[s.key] ?? 0), 0));
  const max = niceMax(Math.max(0, ...totals));
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);
  const padLeft = 44;
  const capH = 20; // room above the tallest column for its total
  const axisH = 38; // two-line labels under the columns
  const plotH = height - capH - axisH;
  const px = (v: number) => (max ? (v / max) * plotH : 0);
  const band = columns.length ? plotWidth / columns.length : 0;
  const tallest = totals.indexOf(Math.max(...totals));
  const capped = new Set(band >= 44 ? [tallest, columns.length - 1] : []);
  const labelEvery = band >= 64 ? 1 : Math.ceil(64 / Math.max(band, 1));
  const legendTotals = series.map((s) => columns.reduce((sum, c) => sum + (c.values[s.key] ?? 0), 0));

  return (
    <figure aria-label={label} className="flex flex-col gap-4">
      <div className="relative" style={{ height }}>
        {/* gridlines and y ticks */}
        {ticks.map((t) => (
          <div key={t} className="absolute left-0 right-0 flex items-center" style={{ top: capH + plotH - px(t) }}>
            <span className="tabular w-10 -translate-y-1/2 pr-2 text-right text-caption text-ink-3">{format(t)}</span>
            <span className="h-px flex-1 -translate-y-1/2 bg-line" />
          </div>
        ))}
        {/* columns: the whole band is the hit target, not just the painted bar */}
        <div ref={plotRef} className="absolute right-0 flex" style={{ left: padLeft, top: capH, height: plotH }}>
          {columns.map((c, i) => {
            const shown = series.filter((s) => (c.values[s.key] ?? 0) > 0);
            const barH = px(totals[i]);
            // The 2px gaps come out of the segments, so the cap still lands on the column's value.
            const fill = Math.max(0, barH - 2 * Math.max(0, shown.length - 1));
            const isActive = active === i;
            // Beside the column, on the side with more room, so the hovered column stays visible.
            const beside = i >= columns.length / 2 ? { right: "calc(50% + 18px)" } : { left: "calc(50% + 18px)" };
            const clickable = Boolean(onSelect) && !c.disabled;
            return (
              <button
                key={c.id}
                type="button"
                className={clsx("relative flex h-full flex-1 items-end justify-center outline-none", clickable ? "cursor-pointer" : "cursor-default")}
                onPointerEnter={() => setActive(i)}
                onPointerLeave={() => setActive(null)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
                onClick={() => clickable && onSelect?.(c.id)}
                aria-label={`${c.label}${c.sub ? `, ${c.sub}` : ""}: ${format(totals[i])} in total. ${shown.map((s) => `${s.label} ${format(c.values[s.key])}`).join(", ")}`}
              >
                <span className="flex w-full max-w-6 flex-col-reverse gap-[2px]">
                  {shown.map((s, j) => (
                    <motion.span
                      key={s.key}
                      className={clsx("block w-full transition-[filter]", j === shown.length - 1 && "rounded-t-[4px]", isActive && "brightness-125")}
                      style={{ background: s.color }}
                      initial={{ height: 0 }}
                      animate={{ height: Math.max(1, totals[i] ? (c.values[s.key] / totals[i]) * fill : 0) }}
                      transition={spring.smooth}
                    />
                  ))}
                </span>
                {capped.has(i) && !isActive && (
                  <span className="tabular pointer-events-none absolute whitespace-nowrap text-caption text-ink-2" style={{ bottom: barH + 4 }}>
                    {format(totals[i])}
                  </span>
                )}
                {isActive && (
                  <motion.span
                    initial={{ opacity: 0, y: 4 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={spring.snappy}
                    className="pointer-events-none absolute top-0 z-10 w-max min-w-44 max-w-72 rounded-control border border-line bg-overlay px-3 py-2 text-left shadow-float"
                    style={beside}
                  >
                    <span className="tabular block text-small font-semibold text-ink">{format(totals[i])} tokens</span>
                    <span className="block truncate text-caption text-ink-3">{c.label}{c.sub ? ` · ${c.sub}` : ""}</span>
                    {c.note && <span className="block text-caption text-ink-3">{c.note}</span>}
                    <span className="mt-2 flex flex-col gap-1">
                      {[...shown].reverse().map((s) => (
                        <span key={s.key} className="flex flex-col">
                          <span className="flex items-center gap-2 text-caption">
                            <span className="h-0.5 w-2.5 shrink-0 rounded-full" style={{ background: s.color }} aria-hidden />
                            <span className="tabular font-semibold text-ink">{format(c.values[s.key])}</span>
                            <span className="truncate text-ink-2">{s.label}</span>
                          </span>
                          {c.breakdown?.[s.key]?.map((b) => (
                            <span key={b.label} className="ml-[18px] flex gap-2 text-caption text-ink-3">
                              <span className="tabular">{format(b.value)}</span>
                              <span className="truncate">{b.label}</span>
                            </span>
                          ))}
                        </span>
                      ))}
                    </span>
                    {clickable && selectHint && <span className="mt-2 block text-caption text-ink-3">{selectHint}</span>}
                  </motion.span>
                )}
              </button>
            );
          })}
        </div>
        {/* column labels; the newest column always keeps its label */}
        <div className="absolute bottom-0 right-0 flex" style={{ left: padLeft, height: axisH }}>
          {columns.map((c, i) => (
            <span
              key={c.id}
              className="flex min-w-0 flex-1 flex-col items-center pt-2"
              style={{ visibility: (columns.length - 1 - i) % labelEvery === 0 ? "visible" : "hidden" }}
            >
              <span className="max-w-full truncate px-1 text-caption text-ink-2" title={c.label}>{c.label}</span>
              {c.sub && <span className="max-w-full truncate px-1 text-[11px] leading-4 text-ink-3">{c.sub}</span>}
            </span>
          ))}
        </div>
      </div>
      <ul className="flex flex-wrap gap-x-5 gap-y-1.5" aria-label="Legend">
        {series.map((s, k) => (
          <li key={s.key} className="flex items-center gap-2 text-small text-ink-2">
            <span className="size-2.5 rounded-[2px]" style={{ background: s.color }} aria-hidden />
            <span>{s.label}</span>
            <span className="tabular text-ink-3">{format(legendTotals[k])}</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** Parts of one total, separated by 2px surface gaps. Legend carries the values. */
export function CompositionBar({ segments, format, label }: {
  segments: { label: string; value: number; color: string }[];
  format: (n: number) => string;
  label: string;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const [active, setActive] = useState<number | null>(null);
  return (
    <figure aria-label={label} className="flex flex-col gap-3">
      <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-[4px]">
        {total === 0 ? (
          <span className="h-full w-full bg-viz-track" />
        ) : (
          segments.map((s, i) =>
            s.value > 0 ? (
              <motion.button
                key={s.label}
                type="button"
                aria-label={`${s.label}: ${format(s.value)}`}
                onPointerEnter={() => setActive(i)}
                onPointerLeave={() => setActive(null)}
                onFocus={() => setActive(i)}
                onBlur={() => setActive(null)}
                className={clsx("h-full min-w-[3px] basis-0 outline-none transition-[filter]", active === i && "brightness-125")}
                style={{ background: s.color }}
                initial={{ flexGrow: 0 }}
                animate={{ flexGrow: s.value }}
                transition={spring.smooth}
              />
            ) : null,
          )
        )}
      </div>
      <ul className="flex flex-wrap gap-x-5 gap-y-1.5">
        {segments.map((s, i) => (
          <li key={s.label} className={clsx("flex items-center gap-2 text-small", active === i ? "text-ink" : "text-ink-2")}>
            <span className="size-2.5 rounded-[2px]" style={{ background: s.color }} aria-hidden />
            <span>{s.label}</span>
            <span className="tabular font-semibold text-ink">{format(s.value)}</span>
            {total > 0 && <span className="tabular text-ink-3">{Math.round((s.value / total) * 100)}%</span>}
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** Ranked list with a bar per row. Works as a table: every value is printed. */
export function BarList({ rows, format, empty = "Nothing recorded yet." }: {
  rows: { label: string; value: number; sub?: string }[];
  format: (n: number) => string;
  empty?: string;
}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (!rows.length) return <p className="py-2 text-small text-ink-3">{empty}</p>;
  return (
    <ul className="flex flex-col gap-2.5">
      {rows.map((r) => (
        <li key={r.label} className="grid grid-cols-[minmax(0,10rem)_1fr_auto] items-center gap-3">
          <span className="truncate text-small text-ink-2" title={r.label}>{r.label}</span>
          <span className="h-2 overflow-hidden rounded-[4px] bg-viz-track">
            <motion.span
              className="block h-full rounded-[4px] bg-viz-1"
              initial={{ width: 0 }}
              animate={{ width: `${(r.value / max) * 100}%` }}
              transition={spring.smooth}
            />
          </span>
          <span className="tabular text-right text-small text-ink">
            {format(r.value)}
            {r.sub && <span className="ml-2 text-ink-3">{r.sub}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}
