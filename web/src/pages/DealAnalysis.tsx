import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { MessagesSquare } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { useSearchParams } from "react-router-dom";

import { DropZone } from "@/components/DropZone";
import { Counter, StageMeter } from "@/components/figures";
import { PlanTrack } from "@/components/RunProgress";
import { TokenReport } from "@/components/TokenReport";
import { Button, Field, Notice, PageHeader, Panel, PanelHeader, Segmented, StatusTag, TextArea, type Tone } from "@/components/ui";
import { useProfile } from "@/hooks/useProfile";
import { useRunStream } from "@/hooks/useRunStream";
import { api, ApiError } from "@/lib/api";
import { fmtInt } from "@/lib/format";
import { spring } from "@/lib/motion";
import type { Gap, IntentResult } from "@/lib/types";

const severityTone: Record<string, Tone> = { Low: "neutral", Medium: "warn", High: "bad", Critical: "bad" };

function GapList({ gaps, empty }: { gaps: Gap[]; empty: string }) {
  if (!gaps.length) return <p className="text-small text-ink-3">{empty}</p>;
  return (
    <ul className="flex flex-col gap-3">
      {gaps.map((g, i) => (
        <li key={i} className="rounded-control border border-line p-3.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-small font-semibold text-ink">{g.gap_type}</span>
            <StatusTag tone={severityTone[g.severity] ?? "warn"}>{g.severity}</StatusTag>
          </div>
          <p className="mt-1.5 text-small text-ink-2">{g.description}</p>
          <p className="mt-1.5 text-small text-ink"><span className="text-ink-3">Next: </span>{g.recommendation}</p>
        </li>
      ))}
    </ul>
  );
}

function Block({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-small text-ink-3">{label}</span>
      <div className="text-body text-ink">{children}</div>
    </div>
  );
}

function ScoreHeadline({ label, score, stage, estimate }: { label: string; score: number; stage?: string; estimate?: boolean }) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-3">
        <span className="text-small text-ink-2">{label}</span>
        {estimate && <StatusTag tone="warn">Keyword estimate, low confidence</StatusTag>}
      </div>
      <div className="flex items-baseline gap-3">
        <Counter value={score} className="text-hero font-semibold tracking-tight text-ink" />
        <span className="text-lead text-ink-3">/ 100</span>
        {stage && <span className="ml-1 text-lead font-semibold text-ion-strong">{stage}</span>}
      </div>
    </div>
  );
}

function Actions({ items }: { items: string[] }) {
  const [done, setDone] = useState<Record<number, boolean>>({});
  if (!items.length) return <p className="text-small text-ink-3">No next actions suggested.</p>;
  return (
    <ul className="flex flex-col">
      {items.map((a, i) => (
        <li key={i} className="border-b border-line last:border-0">
          <label className="flex cursor-pointer items-start gap-3 py-2.5">
            <input type="checkbox" checked={Boolean(done[i])} onChange={() => setDone((d) => ({ ...d, [i]: !d[i] }))} className="mt-1 size-4 accent-[var(--color-ion)]" />
            <span className={clsx("text-small transition-colors", done[i] ? "text-ink-3 line-through" : "text-ink")}>{a}</span>
          </label>
        </li>
      ))}
    </ul>
  );
}

function Results({ r }: { r: IntentResult }) {
  const { profile } = useProfile();
  const [tab, setTab] = useState<"overview" | "buyer" | "fit">("overview");
  const co = r.client_overview;
  const br = r.buyer_readiness;
  const pf = r.product_fit;
  const coverage = br.stakeholder_coverage;
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-display font-semibold text-ink">{co.opportunity_name || "Opportunity"}</h2>
          <p className="mt-1 flex flex-wrap gap-x-4 text-body text-ink-2">
            {co.client_name && <span>{co.client_name}</span>}
            {co.existing_relationship && co.existing_relationship !== "Unknown" && <span className="text-ink-3">{co.existing_relationship}</span>}
            {co.primary_contact && <span className="text-ink-3">{co.primary_contact}</span>}
          </p>
        </div>
        <Segmented
          label="View"
          value={tab}
          onChange={setTab}
          options={[{ value: "overview", label: "Overview" }, { value: "buyer", label: "Buyer" }, { value: "fit", label: "Product fit" }]}
        />
      </div>
      {r.warnings.map((w) => <Notice key={w} title="Heads up">{w}</Notice>)}

      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={tab} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={spring.smooth} className="flex flex-col gap-6">
          {tab === "overview" && (
            <>
              <div className="grid gap-6 lg:grid-cols-2">
                <Panel className="flex flex-col gap-4 p-5">
                  <ScoreHeadline label="Buyer readiness" score={br.buyer_readiness_score ?? 0} stage={br.readiness_stage} estimate={br.mode === "heuristic"} />
                  <StageMeter score={br.buyer_readiness_score ?? 0} stages={profile?.buyer_intelligence.readiness_stages ?? []} stage={br.readiness_stage} />
                </Panel>
                <Panel className="flex flex-col gap-4 p-5">
                  <ScoreHeadline label="Product fit" score={pf.product_fit_score ?? 0} stage={pf.fit_stage} estimate={pf.mode === "heuristic"} />
                  <StageMeter score={pf.product_fit_score ?? 0} stages={profile?.product_fit.fit_stages ?? []} stage={pf.fit_stage} />
                </Panel>
              </div>
              <Panel>
                <PanelHeader title="The problem, in the buyer's terms" />
                <div className="grid gap-5 p-5 md:grid-cols-2">
                  <Block label="Problem">{co.problem_statement || "Not stated"}</Block>
                  <Block label="What success looks like">{co.success_definition || "Not stated"}</Block>
                  <Block label="Who is affected">{co.stakeholder_impact || "Not stated"}</Block>
                  <Block label="Why now">{co.urgency_statement || "Not stated"}</Block>
                </div>
              </Panel>
              <Panel>
                <PanelHeader title="Next actions" description="Tick them off as you go; this list stays on this screen." />
                <div className="px-5 py-1">
                  <Actions items={[...(br.recommended_next_actions ?? []), ...(pf.recommended_next_actions ?? [])].slice(0, 8)} />
                </div>
              </Panel>
            </>
          )}

          {tab === "buyer" && (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <Panel>
                <PanelHeader title="Intent" />
                <div className="flex flex-col gap-4 p-5">
                  <p className="text-body text-ink">{br.intent_classification?.summary || "No summary."}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {(br.intent_classification?.detected_intents ?? []).map((i) => (
                      <StatusTag key={i} tone={i === br.intent_classification?.primary_intent ? "ion" : "neutral"}>{i}</StatusTag>
                    ))}
                  </div>
                  {(br.reasoning ?? []).length > 0 && (
                    <ul className="flex list-disc flex-col gap-1.5 pl-5 text-small text-ink-2">{br.reasoning!.map((x) => <li key={x}>{x}</li>)}</ul>
                  )}
                </div>
              </Panel>
              <Panel>
                <PanelHeader title="Buying gaps" />
                <div className="p-5"><GapList gaps={br.buyer_gaps ?? []} empty="No blockers found in the conversation." /></div>
              </Panel>
              <Panel className="lg:col-span-2">
                <PanelHeader title="Stakeholders" description={coverage?.engagement_summary} />
                <div className="overflow-x-auto px-5 py-3">
                  {coverage?.stakeholders.length ? (
                    <table className="w-full min-w-[560px] text-small">
                      <thead><tr className="text-left text-ink-3"><th className="py-1.5 font-normal">Person</th><th className="font-normal">Role</th><th className="font-normal">Category</th><th className="font-normal">Influence</th><th className="font-normal">Engagement</th></tr></thead>
                      <tbody>
                        {coverage.stakeholders.map((s, i) => (
                          <tr key={i} className="border-t border-line text-ink-2">
                            <td className="py-2 text-ink">{s.name}</td><td>{s.role}</td><td>{s.category}</td><td>{s.influence_level}</td><td>{s.engagement_quality}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : <p className="text-small text-ink-3">No named stakeholders in the conversation.</p>}
                </div>
                {coverage && coverage.missing_roles.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 border-t border-line px-5 py-3">
                    <span className="mr-1 text-small text-ink-3">Not yet engaged:</span>
                    {coverage.missing_roles.map((m) => <StatusTag key={m} tone="warn">{m}</StatusTag>)}
                  </div>
                )}
              </Panel>
            </div>
          )}

          {tab === "fit" && (
            <div className="grid gap-6 lg:grid-cols-2">
              <Panel className="lg:col-span-2">
                <PanelHeader title="Matched capabilities" description={pf.fit_summary} />
                <div className="overflow-x-auto px-5 py-3">
                  {pf.matched_capabilities?.length ? (
                    <table className="w-full min-w-[560px] text-small">
                      <thead><tr className="text-left text-ink-3"><th className="py-1.5 font-normal">Buyer need</th><th className="font-normal">Our capability</th><th className="font-normal">Area</th><th className="font-normal">Strength</th></tr></thead>
                      <tbody>
                        {pf.matched_capabilities.map((m, i) => (
                          <tr key={i} className="border-t border-line text-ink-2">
                            <td className="py-2 text-ink">{m.buyer_need}</td><td>{m.matched_capability}</td><td>{m.capability_area}</td>
                            <td><StatusTag tone={m.fit_strength === "Strong" ? "good" : m.fit_strength === "Weak" ? "bad" : "warn"}>{m.fit_strength}</StatusTag></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  ) : <p className="text-small text-ink-3">No capability matches identified.</p>}
                </div>
              </Panel>
              <Panel>
                <PanelHeader title="Fit gaps" />
                <div className="p-5"><GapList gaps={pf.product_gaps ?? []} empty="No fit gaps identified." /></div>
              </Panel>
              <Panel>
                <PanelHeader title="Positioning" />
                <div className="flex flex-col gap-4 p-5 text-small">
                  {pf.competitive_positioning?.competitors_mentioned?.length ? (
                    <Block label="Competitors mentioned">{pf.competitive_positioning.competitors_mentioned.join(", ")}</Block>
                  ) : null}
                  {pf.integration_fit?.summary && <Block label={`Integration fit (${pf.integration_fit.score}/100)`}>{pf.integration_fit.summary}</Block>}
                  {(pf.recommended_positioning ?? []).length > 0 && (
                    <Block label="Lead with"><ul className="flex list-disc flex-col gap-1 pl-5 text-small text-ink-2">{pf.recommended_positioning!.map((x) => <li key={x}>{x}</li>)}</ul></Block>
                  )}
                </div>
              </Panel>
            </div>
          )}
        </motion.div>
      </AnimatePresence>

      <Panel>
        <PanelHeader title="Token usage" />
        <TokenReport usage={r.token_usage} />
      </Panel>
    </div>
  );
}

export default function DealAnalysis() {
  const { name: profileName } = useProfile();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const storedId = params.get("run");
  const stored = useQuery({ queryKey: ["run", storedId], queryFn: () => api.run<IntentResult>(storedId!), enabled: Boolean(storedId) });
  const { state, start, reset } = useRunStream<IntentResult>();
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState<string | undefined>();
  const [reading, setReading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (state.result) {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      setParams({ run: state.result.workflow_id }, { replace: true });
    }
  }, [state.result, queryClient, setParams]);

  const readFile = async (files: File[]) => {
    const file = files[0];
    setReading(true);
    setError(null);
    try {
      if (/\.(pdf|docx)$/i.test(file.name)) setText((await api.extractText(file, profileName)).text);
      else setText(await file.text());
      setFileName(file.name);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not read that file.");
    } finally {
      setReading(false);
    }
  };

  const result = state.result ?? (storedId ? stored.data?.result : undefined);
  const showInput = state.phase === "idle" && !result;

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 sm:px-8">
      <PageHeader
        title="Deal analysis"
        description="Drop a call transcript, email thread, or meeting notes. Get the buyer's problem, how ready they are to buy, and how well you fit."
        actions={!showInput && (
          <Button variant="secondary" icon={<MessagesSquare className="size-4" />} onClick={() => { reset(); setText(""); setParams({}); }}>
            Analyze another
          </Button>
        )}
      />
      {showInput && (
        <div className="grid gap-6 lg:grid-cols-2">
          <DropZone title="Drop a conversation" hint="Transcript, email, or notes: .txt, .md, .eml, .pdf, .docx" onFiles={readFile} busy={reading} accept=".txt,.md,.eml,.log,.pdf,.docx" />
          <div className="flex flex-col gap-3">
            <Field label="Or paste it" htmlFor="transcript" hint={fileName ? `From ${fileName}, ${fmtInt(text.length)} characters` : undefined}>
              <TextArea id="transcript" rows={9} value={text} onChange={(e) => setText(e.target.value)} placeholder="[00:01] Buyer: We're evaluating vendors for…" />
            </Field>
            {error && <Notice tone="bad" title="That file could not be read">{error}</Notice>}
            <Button
              variant="primary"
              size="lg"
              disabled={text.trim().length < 40}
              onClick={() => start("/intent-detection-runs/stream", { transcript_text: text, file_name: fileName, profile: profileName })}
            >
              Analyze conversation
            </Button>
          </div>
        </div>
      )}
      {(state.phase === "running" || state.phase === "error") && (
        <Panel className="p-5">
          <PlanTrack state={state} />
          {state.error && <div className="mt-4"><Notice tone="bad" title="The analysis did not finish">{state.error.message}</Notice></div>}
        </Panel>
      )}
      {storedId && stored.isLoading && !state.result && <Panel className="h-64 p-5"><p className="text-small text-ink-3">Loading the analysis</p></Panel>}
      {result && <Results r={result} />}
    </div>
  );
}
