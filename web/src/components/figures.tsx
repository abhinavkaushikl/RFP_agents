import clsx from "clsx";
import { motion, useMotionValueEvent, useSpring } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { spring } from "@/lib/motion";

/**
 * A number that springs from its previous value to a new one (live token counts, period switches).
 * It shows the real value immediately on first render, so nothing counts up on page load.
 */
export function Counter({ value, format = (n) => Math.round(n).toLocaleString(), className }: {
  value: number;
  format?: (n: number) => string;
  className?: string;
}) {
  const motionValue = useSpring(value, spring.counter);
  const [display, setDisplay] = useState(() => format(value));
  const formatRef = useRef(format);
  formatRef.current = format;
  useMotionValueEvent(motionValue, "change", (v) => setDisplay(formatRef.current(v)));
  useEffect(() => {
    motionValue.set(value);
  }, [motionValue, value]);
  return <span className={className}>{display}</span>;
}

function severity(ratio: number, invert = false): string {
  const r = invert ? 1 - ratio : ratio;
  if (r >= 0.7) return "var(--color-viz-1)";
  if (r >= 0.45) return "var(--color-warn)";
  return "var(--color-bad)";
}

/** A single ratio against a limit. The fill carries severity; the track is the same hue, lighter. */
export function Meter({ value, label, detail, compact }: {
  value: number | null | undefined;
  label: string;
  detail?: string;
  compact?: boolean;
}) {
  const measured = value != null;
  const ratio = measured ? Math.max(0, Math.min(1, value)) : 0;
  return (
    <div className={clsx("flex flex-col", compact ? "gap-1" : "gap-1.5")}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-small text-ink-2">{label}</span>
        <span className="tabular text-small font-semibold text-ink">{measured ? Math.round(ratio * 100) : "Not measured"}</span>
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-viz-track"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={measured ? Math.round(ratio * 100) : undefined}
      >
        {measured && (
          <motion.div
            className="h-full rounded-full"
            style={{ background: severity(ratio) }}
            initial={{ width: 0 }}
            animate={{ width: `${ratio * 100}%` }}
            transition={spring.smooth}
          />
        )}
      </div>
      {detail && <span className="text-caption text-ink-3">{detail}</span>}
    </div>
  );
}

/** The one headline number on a view. */
export function HeroScore({ value, label, caption }: { value: number | null | undefined; label: string; caption?: string }) {
  const measured = value != null;
  return (
    <div className="flex flex-col gap-2">
      <span className="text-small text-ink-2">{label}</span>
      <div className="flex items-baseline gap-2">
        {measured ? (
          <Counter value={Math.round((value ?? 0) * 100)} className="text-hero font-semibold tracking-tight text-ink" />
        ) : (
          <span className="text-display font-semibold text-ink-3">Not scored</span>
        )}
        {measured && <span className="text-lead text-ink-3">/ 100</span>}
      </div>
      {measured && (
        <div className="h-1.5 overflow-hidden rounded-full bg-viz-track">
          <motion.div
            className="h-full rounded-full"
            style={{ background: severity(value ?? 0) }}
            initial={{ width: 0 }}
            animate={{ width: `${Math.max(0, Math.min(1, value ?? 0)) * 100}%` }}
            transition={spring.smooth}
          />
        </div>
      )}
      {caption && <span className="text-caption text-ink-3">{caption}</span>}
    </div>
  );
}

/** Score on a 0-100 scale with stage bands, e.g. buyer readiness. */
export function StageMeter({ score, stages, stage }: { score: number; stages: { name: string; max_score: number }[]; stage?: string }) {
  const sorted = [...stages].sort((a, b) => a.max_score - b.max_score);
  return (
    <div className="flex flex-col gap-2">
      <div className="relative h-2 overflow-hidden rounded-full bg-viz-track">
        <motion.div
          className="h-full rounded-full bg-viz-1"
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(0, Math.min(100, score))}%` }}
          transition={spring.smooth}
        />
        {sorted.slice(0, -1).map((s) => (
          <span key={s.name} className="absolute top-0 h-full w-0.5 bg-panel" style={{ left: `${s.max_score}%` }} aria-hidden />
        ))}
      </div>
      {/* each label sits over its own band: column widths are the band widths */}
      <div
        className="grid text-caption text-ink-3"
        style={{ gridTemplateColumns: sorted.map((s, i) => `${Math.max(1, s.max_score - (i ? sorted[i - 1].max_score : 0))}fr`).join(" ") }}
      >
        {sorted.map((s) => (
          <span key={s.name} title={s.name} className={clsx("truncate pr-1", s.name === stage && "font-semibold text-ink")}>{s.name}</span>
        ))}
      </div>
    </div>
  );
}
