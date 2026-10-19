import clsx from "clsx";
import { ChevronRight } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import { fmtCompact, fmtCost, fmtInt, titleCase } from "@/lib/format";
import { spring } from "@/lib/motion";
import type { TokenUsage, UsageRow } from "@/lib/types";
import { BarList, CompositionBar } from "./charts";
import { Counter } from "./figures";
import { Segmented } from "./ui";

export function StatTile({ label, value, detail, format = fmtInt }: {
  label: string;
  value: number;
  detail?: string;
  format?: (n: number) => string;
}) {
  return (
    <div className="flex flex-col gap-1 px-5 py-4">
      <span className="text-small text-ink-2">{label}</span>
      <Counter value={value} format={format} className="text-title font-semibold text-ink" />
      {detail && <span className="text-caption text-ink-3">{detail}</span>}
    </div>
  );
}

const rowsFor = (rows: UsageRow[], key: keyof UsageRow, labeler: (v: string) => string = (v) => v) =>
  rows.map((r) => ({
    label: labeler(String(r[key] ?? "")),
    value: r.total_tokens || r.saved_tokens,
    sub: r.cache_hits && !r.total_tokens ? "cached" : fmtCost(r.cost_usd),
  }));

/** Token consumption for one run or a period: totals, where the input came from, and where it went. */
export function TokenReport({ usage, sectionTitles = {}, showCalls = true }: {
  usage: TokenUsage;
  sectionTitles?: Record<string, string>;
  showCalls?: boolean;
}) {
  const t = usage.totals;
  const [view, setView] = useState<"section" | "agent" | "model">(usage.by_section.length ? "section" : "agent");
  const [callsOpen, setCallsOpen] = useState(false);
  const uncached = Math.max(0, t.prompt_tokens - t.cached_prompt_tokens);

  const breakdown =
    view === "section"
      ? rowsFor(usage.by_section, "section_key", (k) => sectionTitles[k] ?? titleCase(k))
      : view === "agent"
        ? rowsFor(usage.by_agent, "agent", titleCase)
        : rowsFor(usage.by_model, "model", (m) => m.replace(/^openai\//, ""));

  return (
    <div className="@container flex flex-col">
      <div className="grid grid-cols-2 divide-line border-b border-line @2xl:grid-cols-4 @2xl:divide-x">
        <StatTile label="Tokens" value={t.total_tokens} format={fmtInt} detail={`${fmtInt(t.model_calls)} model calls`} />
        <StatTile label="Estimated cost" value={t.cost_usd} format={fmtCost} detail="Groq list prices" />
        <StatTile
          label="Prompt cache"
          value={t.prompt_cache_rate * 100}
          format={(n) => `${Math.round(n)}%`}
          detail={`${fmtCompact(t.cached_prompt_tokens)} input tokens at half price`}
        />
        <StatTile
          label="Saved by section cache"
          value={t.saved_tokens}
          format={fmtInt}
          detail={t.cache_hits ? `${t.cache_hits} outputs reused, ${fmtCost(t.saved_cost_usd)}` : "No outputs reused yet"}
        />
      </div>

      <div className="flex flex-col gap-6 px-5 py-5">
        <CompositionBar
          label="Token composition"
          format={fmtCompact}
          segments={[
            { label: "New input", value: uncached, color: "var(--color-viz-1)" },
            { label: "Cached input", value: t.cached_prompt_tokens, color: "var(--color-viz-2)" },
            { label: "Output", value: t.completion_tokens, color: "var(--color-viz-3)" },
          ]}
        />
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-3">
            <span className="text-small font-semibold text-ink">Where the tokens went</span>
            <Segmented
              label="Breakdown"
              value={view}
              onChange={setView}
              options={[
                ...(usage.by_section.length ? [{ value: "section" as const, label: "Sections" }] : []),
                { value: "agent" as const, label: "Agents" },
                { value: "model" as const, label: "Models" },
              ]}
            />
          </div>
          <BarList rows={breakdown} format={fmtCompact} />
        </div>
      </div>

      {showCalls && (usage.calls?.length ?? 0) > 0 && (
        <div className="border-t border-line">
          <button
            type="button"
            onClick={() => setCallsOpen((v) => !v)}
            aria-expanded={callsOpen}
            className="flex w-full items-center gap-2 px-5 py-3 text-small text-ink-2 hover:text-ink"
          >
            <motion.span animate={{ rotate: callsOpen ? 90 : 0 }} transition={spring.snappy}>
              <ChevronRight className="size-4" />
            </motion.span>
            Every model call ({usage.calls!.length})
          </button>
          <AnimatePresence initial={false}>
            {callsOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={spring.smooth}
                className="overflow-hidden"
              >
                <div className="overflow-x-auto px-5 pb-4">
                  <table className="w-full min-w-[640px] text-small">
                    <thead>
                      <tr className="text-left text-ink-3">
                        {["Agent", "Section", "Model", "Input", "Cached", "Output", "Cost", "Time"].map((h) => (
                          <th key={h} className={clsx("py-1.5 pr-3 font-normal", ["Input", "Cached", "Output", "Cost", "Time"].includes(h) && "text-right")}>{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="tabular">
                      {usage.calls!.map((c, i) => (
                        <tr key={i} className="border-t border-line text-ink-2">
                          <td className="py-1.5 pr-3 text-ink">{titleCase(c.agent)}{c.status !== "ok" && <span className="ml-2 text-bad">{c.status}</span>}</td>
                          <td className="py-1.5 pr-3">{c.section_key ? sectionTitles[c.section_key] ?? titleCase(c.section_key) : ""}</td>
                          <td className="py-1.5 pr-3">{c.cache_hit ? "cache" : c.model.replace(/^openai\//, "")}</td>
                          <td className="py-1.5 pr-3 text-right">{fmtInt(c.prompt_tokens)}</td>
                          <td className="py-1.5 pr-3 text-right">{fmtInt(c.cached_prompt_tokens)}</td>
                          <td className="py-1.5 pr-3 text-right">{fmtInt(c.completion_tokens)}</td>
                          <td className="py-1.5 pr-3 text-right">{fmtCost(c.cost_usd)}</td>
                          <td className="py-1.5 text-right">{(c.latency_ms / 1000).toFixed(1)}s</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
