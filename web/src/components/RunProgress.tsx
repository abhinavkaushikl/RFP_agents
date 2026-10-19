import clsx from "clsx";
import { Check, CircleDashed, Database, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import type { LiveSection, RunState } from "@/hooks/useRunStream";
import { fmtInt, stepLabel } from "@/lib/format";
import { spring } from "@/lib/motion";
import { Counter } from "./figures";
import { Skeleton } from "./ui";

function Elapsed({ since, running }: { since?: number; running: boolean }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [running]);
  if (!since) return null;
  const secs = Math.max(0, Math.floor((now - since) / 1000));
  return <span className="tabular">{secs < 60 ? `${secs}s` : `${Math.floor(secs / 60)}m ${secs % 60}s`}</span>;
}

function Node({ status }: { status: "pending" | "running" | "done" | "failed" }) {
  return (
    <span className="relative flex size-[22px] shrink-0 items-center justify-center">
      {status === "running" && (
        <motion.span
          className="absolute inset-0 rounded-full border-2 border-ion"
          animate={{ scale: [1, 1.35], opacity: [0.7, 0] }}
          transition={{ duration: 1.3, repeat: Infinity, ease: "easeOut" }}
        />
      )}
      <motion.span
        layout
        className={clsx(
          "flex size-[22px] items-center justify-center rounded-full border-2",
          status === "done" && "border-ion bg-ion text-on-ion",
          status === "running" && "border-ion bg-canvas",
          status === "pending" && "border-line-strong bg-canvas",
          status === "failed" && "border-bad bg-bad/20 text-bad",
        )}
        animate={{ scale: status === "done" ? [0.7, 1] : 1 }}
        transition={spring.land}
      >
        {status === "done" && <Check className="size-3" strokeWidth={3} />}
        {status === "failed" && <X className="size-3" strokeWidth={3} />}
        {status === "running" && <span className="size-1.5 rounded-full bg-ion" />}
      </motion.span>
    </span>
  );
}

export function PlanTrack<T>({ state }: { state: RunState<T> }) {
  const steps = state.steps;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-baseline justify-between gap-4">
        <p className="text-small text-ink-2">
          {state.phase === "running" ? "The agents are working on it" : state.phase === "done" ? "Finished" : state.phase === "error" ? "Stopped" : ""}
        </p>
        <p className="flex gap-4 text-small text-ink-3">
          <Elapsed since={state.startedAt} running={state.phase === "running"} />
          <span>
            <Counter value={state.tokens} format={fmtInt} className="tabular text-ink-2" /> tokens
          </span>
        </p>
      </div>
      {steps.length === 0 ? (
        <div className="flex items-center gap-3">
          <Node status="running" />
          <span className="text-body text-ink-2">Planning the run</span>
        </div>
      ) : (
        <ol className="flex items-start">
          {steps.map((step, i) => (
            <li key={step.tool} className={clsx("flex min-w-0 flex-col gap-2", i < steps.length - 1 ? "flex-1" : "shrink-0")}>
              <div className="flex items-center">
                <Node status={step.status} />
                {i < steps.length - 1 && (
                  <span className="relative mx-2 h-0.5 flex-1 overflow-hidden rounded-full bg-line-strong">
                    <motion.span
                      className="absolute inset-y-0 left-0 rounded-full bg-ion"
                      initial={{ width: 0 }}
                      animate={{ width: step.status === "done" ? "100%" : step.status === "running" ? "35%" : "0%" }}
                      transition={spring.smooth}
                    />
                  </span>
                )}
              </div>
              <div className="pr-3">
                <p className={clsx("truncate text-small font-semibold", step.status === "pending" ? "text-ink-3" : "text-ink")}>{stepLabel(step.tool)}</p>
                {step.tokens ? <p className="tabular text-caption text-ink-3">{fmtInt(step.tokens)} tokens</p> : null}
              </div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function SectionCard({ section }: { section: LiveSection }) {
  return (
    <motion.li
      layout
      transition={spring.smooth}
      className={clsx(
        "overflow-hidden rounded-panel border bg-panel",
        section.status === "writing" ? "border-ion-line" : "border-line",
      )}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <span className="shrink-0">
          {section.status === "done" ? (
            <motion.span initial={{ scale: 0.6 }} animate={{ scale: 1 }} transition={spring.land} className="flex size-5 items-center justify-center rounded-full bg-ion text-on-ion">
              <Check className="size-3" strokeWidth={3} />
            </motion.span>
          ) : section.status === "failed" ? (
            <span className="flex size-5 items-center justify-center rounded-full bg-bad/20 text-bad"><X className="size-3" strokeWidth={3} /></span>
          ) : section.status === "writing" ? (
            <span className="flex size-5 items-center justify-center"><span className="size-2 animate-pulse rounded-full bg-ion" /></span>
          ) : (
            <CircleDashed className="size-5 text-ink-3" />
          )}
        </span>
        <p className={clsx("min-w-0 flex-1 truncate text-body font-semibold", section.status === "queued" ? "text-ink-3" : "text-ink")}>{section.title}</p>
        <span className="shrink-0 text-small text-ink-3">
          {section.status === "writing" && "Writing"}
          {section.status === "queued" && "Queued"}
          {section.status === "failed" && <span className="text-bad-text">Failed</span>}
          {section.status === "done" &&
            (section.cacheHit ? (
              <span className="inline-flex items-center gap-1.5"><Database className="size-3.5 text-viz-2" />From cache, 0 tokens</span>
            ) : section.mode === "fallback" || section.mode === "template" ? (
              "Outline only"
            ) : (
              <span className="tabular">{fmtInt(section.wordCount)} words, {fmtInt(section.tokens)} tokens</span>
            ))}
        </span>
      </div>
      <AnimatePresence mode="popLayout" initial={false}>
        {section.status === "writing" && (
          <motion.div key="writing" exit={{ opacity: 0 }} className="flex flex-col gap-2 px-4 pb-4 pl-12">
            <Skeleton className="h-3 w-[92%]" />
            <Skeleton className="h-3 w-[78%]" />
            <Skeleton className="h-3 w-[60%]" />
          </motion.div>
        )}
        {section.status === "done" && section.preview && (
          <motion.p
            key="done"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={spring.land}
            className="line-clamp-3 px-4 pb-4 pl-12 font-serif text-small leading-relaxed text-ink-2"
          >
            {section.preview.replace(/\*\*/g, "").replace(/^#+\s*/gm, "")}
          </motion.p>
        )}
        {section.status === "failed" && section.error && (
          <motion.p key="failed" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="px-4 pb-3 pl-12 text-small text-ink-3">
            {section.error}
          </motion.p>
        )}
      </AnimatePresence>
    </motion.li>
  );
}

export function LiveSections({ sections }: { sections: LiveSection[] }) {
  if (!sections.length) return null;
  const done = sections.filter((s) => s.status === "done").length;
  return (
    <div className="flex flex-col gap-3">
      <p className="text-small text-ink-2">
        <span className="tabular text-ink">{done}</span> of {sections.length} sections drafted
      </p>
      <motion.ol layout className="flex flex-col gap-2.5">
        {sections.map((s) => (
          <SectionCard key={s.key} section={s} />
        ))}
      </motion.ol>
    </div>
  );
}
