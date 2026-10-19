import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { BarChart3 } from "lucide-react";
import { useMemo, useState } from "react";

import { BarList, ColumnChart } from "@/components/charts";
import { TokenReport } from "@/components/TokenReport";
import { EmptyState, Field, Notice, PageHeader, Panel, PanelHeader, Segmented, Skeleton, TextInput } from "@/components/ui";
import { useProfile } from "@/hooks/useProfile";
import { api } from "@/lib/api";
import { fmtCompact, fmtCost, fmtInt, titleCase } from "@/lib/format";

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

export default function Usage() {
  const { profile } = useProfile();
  const [days, setDays] = useState(7);
  const [table, setTable] = useState(false);
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
