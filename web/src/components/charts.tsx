import clsx from "clsx";
import { motion } from "motion/react";
import { useMemo, useState } from "react";

import { spring } from "@/lib/motion";

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
