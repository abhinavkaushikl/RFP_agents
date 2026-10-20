import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { BarList, ColumnChart, StackedColumnChart, type StackColumn, type StackSeries } from "@/components/charts";
import { TokenReport } from "@/components/TokenReport";
import { EmptyState, Field, Notice, PageHeader, Panel, PanelHeader, Segmented, Skeleton, TextInput } from "@/components/ui";
import { useProfile } from "@/hooks/useProfile";
import { api } from "@/lib/api";
import { fmtCompact, fmtCost, fmtInt, titleCase } from "@/lib/format";
import type { Profile, RunUsage } from "@/lib/types";

const KIND: Record<string, string> = {
  proposal_generation: "Proposals",
  intent_detection: "Deal analyses",
  document_match: "Bid checks",
  market_research: "Market scans",
  revision: "Revisions",
};

function lastDays(days: number): string[] {
  const out: string[] = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setUTCDate(d.getUTCDate() - i);
    out.push(d.toISOString().slice(0, 10));
  }
  return out;
}

const RUNS_SHOWN = 12;
const NAMED_SECTIONS = 6; // series slots; any further sections fold into "Other sections"
const OTHER = "__other_sections";
const BASE = "__planning";

const fmtWhen = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

/**
 * Columns (oldest → newest) and series for the per-run chart. A section's colour comes from its
 * position in the profile (default sections first), never from the data on screen, so changing
 * the period never repaints a section.
 */
function runStacks(runs: RunUsage[], profile: Profile | undefined, titles: Record<string, string>) {
  const order = [...new Set([...(profile?.default_sections ?? []), ...(profile?.sections ?? []).map((s) => s.key)])];
  const slot = (key: string) => {
    const i = order.indexOf(key);
    return i >= 0 && i < NAMED_SECTIONS ? i : -1;
  };
  const name = (key: string) => titles[key] ?? titleCase(key);
  const present = new Set<string>();
  let anyOther = false;
  let anyBase = false;

  const columns: (StackColumn & { cost: number })[] = [...runs].reverse().map((run) => {
    const values: Record<string, number> = {};
    const folded: { label: string; value: number }[] = [];
    for (const s of run.sections) {
      if (slot(s.section_key) >= 0) {
        values[s.section_key] = (values[s.section_key] ?? 0) + s.total_tokens;
        present.add(s.section_key);
      } else {
        folded.push({ label: name(s.section_key), value: s.total_tokens });
      }
    }
    if (folded.length) {
      values[OTHER] = folded.reduce((sum, f) => sum + f.value, 0);
      anyOther = true;
    }
    if (run.other_tokens > 0) {
      values[BASE] = run.other_tokens;
      anyBase = true;
    }
    return {
      id: run.workflow_id,
      label: run.client_name || run.title || "Untitled run",
      sub: fmtWhen(run.started_at),
      values,
      breakdown: folded.length ? { [OTHER]: folded } : undefined,
      note: `${fmtCost(run.cost_usd)} estimated`,
      disabled: !run.saved,
      cost: run.cost_usd,
    };
  });

  const series: StackSeries[] = [
    ...[...present].sort((a, b) => slot(a) - slot(b)).map((key) => ({ key, label: name(key), color: `var(--color-series-${slot(key) + 1})` })),
    ...(anyOther ? [{ key: OTHER, label: "Other sections", color: "var(--color-series-other)" }] : []),
    ...(anyBase ? [{ key: BASE, label: "Planning & checks", color: "var(--color-series-base)" }] : []),
  ];
  return { columns, series };
}

export default function Usage() {
  const { profile } = useProfile();
  const navigate = useNavigate();
  const [days, setDays] = useState(7);
  const [table, setTable] = useState(false);
  const [runTable, setRunTable] = useState(false);
  const [lookup, setLookup] = useState("");
  const summary = useQuery({ queryKey: ["usage", days], queryFn: () => api.usageSummary(days), placeholderData: keepPreviousData });
  const runUsage = useQuery({
    queryKey: ["usage", "run", lookup.trim()],
    queryFn: () => api.workflowUsage(lookup.trim()),
    enabled: /^[0-9a-f-]{36}$/i.test(lookup.trim()),
    retry: 0,
  });

  const daily = useMemo(() => {
    const byDay = new Map((summary.data?.by_day ?? []).map((d) => [d.day, d.total_tokens]));
    return lastDays(days).map((day) => ({
      label: new Date(`${day}T00:00:00Z`).toLocaleDateString(undefined, { month: "short", day: "numeric", timeZone: "UTC" }),
      value: byDay.get(day) ?? 0,
    }));
  }, [summary.data, days]);
  const titles = Object.fromEntries((profile?.sections ?? []).map((s) => [s.key, s.title]));
  const data = summary.data;
  const runsUsage = useQuery({
    queryKey: ["usage", "runs", days],
    queryFn: () => api.usageRuns(days, RUNS_SHOWN),
    placeholderData: keepPreviousData,
  });
  const perRun = useMemo(
    () => runStacks(runsUsage.data?.runs ?? [], profile, titles),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- titles is derived from profile
    [runsUsage.data, profile],
  );

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 sm:px-8">
      <PageHeader title="Usage" description="Model tokens and cost across the team, including what prompt caching and the section cache saved." />
      <div className="mb-5 flex items-center gap-3">
        <Segmented label="Period" value={days} onChange={setDays} options={[{ value: 1, label: "Today" }, { value: 7, label: "7 days" }, { value: 30, label: "30 days" }, { value: 90, label: "90 days" }]} />
      </div>

      {summary.isLoading ? (
        <Skeleton className="h-80" />
      ) : summary.isError ? (
        <Notice tone="bad" title="Usage could not be loaded">{(summary.error as Error).message}</Notice>
      ) : !data?.totals.calls ? (
        <Panel><EmptyState icon={<BarChart3 className="size-5" />} title="No model calls in this period" description="Draft a proposal or analyze a conversation and the tokens show up here." /></Panel>
      ) : (
        <div className={summary.isFetching ? "flex flex-col gap-6 opacity-70 transition-opacity" : "flex flex-col gap-6 transition-opacity"}>
          <Panel>
            <PanelHeader
              title="Tokens per day"
              action={<button type="button" onClick={() => setTable((t) => !t)} className="text-small text-ion-strong hover:underline">{table ? "Show chart" : "Show table"}</button>}
            />
            <div className="p-5">
              {table ? (
                <table className="w-full text-small">
                  <thead><tr className="text-left text-ink-3"><th className="py-1.5 font-normal">Day</th><th className="text-right font-normal">Tokens</th></tr></thead>
                  <tbody className="tabular">
                    {daily.map((d) => <tr key={d.label} className="border-t border-line"><td className="py-1.5 text-ink-2">{d.label}</td><td className="text-right text-ink">{fmtInt(d.value)}</td></tr>)}
                  </tbody>
                </table>
              ) : (
                <ColumnChart data={daily} format={fmtCompact} label="Tokens per day" />
              )}
            </div>
          </Panel>
          <Panel>
            <PanelHeader
              title="Tokens per run, by section"
              description={`The latest ${RUNS_SHOWN} proposal runs in this period. Planning & checks covers calls not tied to one section: reading the RFP, planning, and scoring.`}
              action={<button type="button" onClick={() => setRunTable((t) => !t)} className="text-small text-ion-strong hover:underline">{runTable ? "Show chart" : "Show table"}</button>}
            />
            <div className={runsUsage.isFetching ? "p-5 opacity-70 transition-opacity" : "p-5 transition-opacity"}>
              {runsUsage.isLoading ? (
                <Skeleton className="h-72" />
              ) : runsUsage.isError ? (
                <Notice tone="bad" title="Runs could not be loaded">{(runsUsage.error as Error).message}</Notice>
              ) : !perRun.columns.length ? (
                <p className="py-2 text-small text-ink-3">No proposal runs in this period.</p>
              ) : runTable ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-small">
                    <thead>
                      <tr className="text-left text-ink-3">
                        <th className="py-1.5 pr-4 font-normal">Run</th>
                        {perRun.series.map((s) => <th key={s.key} className="px-2 text-right font-normal">{s.label}</th>)}
                        <th className="px-2 text-right font-normal">Total</th>
                        <th className="pl-2 text-right font-normal">Cost</th>
                      </tr>
                    </thead>
                    <tbody className="tabular">
                      {[...perRun.columns].reverse().map((c) => (
                        <tr key={c.id} className="border-t border-line align-top">
                          <td className="py-1.5 pr-4">
                            <span className="block text-ink-2">{c.label}</span>
                            <span className="block text-caption text-ink-3">{c.sub}</span>
                          </td>
                          {perRun.series.map((s) => (
                            <td key={s.key} className="px-2 py-1.5 text-right text-ink">
                              {c.values[s.key] ? fmtInt(c.values[s.key]) : "–"}
                              {c.breakdown?.[s.key]?.map((b) => (
                                <span key={b.label} className="block text-caption text-ink-3">{b.label} {fmtInt(b.value)}</span>
                              ))}
                            </td>
                          ))}
                          <td className="px-2 py-1.5 text-right font-semibold text-ink">{fmtInt(Object.values(c.values).reduce((a, b) => a + b, 0))}</td>
                          <td className="py-1.5 pl-2 text-right text-ink-2">{fmtCost(c.cost)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <StackedColumnChart
                  columns={perRun.columns}
                  series={perRun.series}
                  format={fmtCompact}
                  label="Tokens per run, by section"
                  onSelect={(id) => navigate(`/proposals/${id}`)}
                  selectHint="Click to open the proposal"
                />
              )}
            </div>
          </Panel>
          <Panel>
            <PanelHeader title={`All runs, ${data.workflows ?? 0} in this period`} />
            <TokenReport usage={data} sectionTitles={titles} showCalls={false} />
          </Panel>
          <Panel>
            <PanelHeader title="By kind of work" />
            <div className="p-5">
              <BarList
                rows={(data.by_workflow_type ?? []).map((r) => ({ label: KIND[r.workflow_type ?? ""] ?? titleCase(r.workflow_type ?? "other"), value: r.total_tokens, sub: fmtCost(r.cost_usd) }))}
                format={fmtCompact}
              />
            </div>
          </Panel>
        </div>
      )}

      <Panel className="mt-6">
        <PanelHeader title="Look up one run" description="Paste a run id to see every model call it made." />
        <div className="flex flex-col gap-4 p-5">
          <Field label="Run id" htmlFor="run-id">
            <TextInput id="run-id" value={lookup} onChange={(e) => setLookup(e.target.value)} placeholder="e.g. 3f2c9a1e-…" className="font-mono" />
          </Field>
          {runUsage.isError && <Notice title="No usage for that run">{(runUsage.error as Error).message}</Notice>}
        </div>
        {runUsage.data && <TokenReport usage={runUsage.data} sectionTitles={titles} />}
      </Panel>
    </div>
  );
}
