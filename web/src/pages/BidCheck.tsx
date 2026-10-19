import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ScanSearch } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { BarList } from "@/components/charts";
import { DropZone } from "@/components/DropZone";
import { HeroScore, Meter } from "@/components/figures";
import { RequirementList } from "@/components/RequirementList";
import { PlanTrack } from "@/components/RunProgress";
import { TokenReport } from "@/components/TokenReport";
import { Button, Field, Notice, PageHeader, Panel, PanelHeader, StatusTag, TextArea } from "@/components/ui";
import { useProfile } from "@/hooks/useProfile";
import { useRunStream } from "@/hooks/useRunStream";
import { api, ApiError } from "@/lib/api";
import { fmtInt } from "@/lib/format";
import type { DocumentMatchResult } from "@/lib/types";

function DocInput({ id, label, value, onChange, profile }: { id: string; label: string; value: string; onChange: (v: string) => void; profile: string }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const read = async (files: File[]) => {
    setBusy(true);
    setError(null);
    try {
      onChange((await api.extractText(files[0], profile)).text);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not read that file.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col gap-3">
      {!value && <DropZone compact title={`Upload the ${label.toLowerCase()}`} hint="PDF, Word, Markdown, or text" onFiles={read} busy={busy} />}
      <Field label={label} htmlFor={id} hint={value ? `${fmtInt(value.trim().split(/\s+/).length)} words` : "Or paste the text"} error={error}>
        <TextArea id={id} rows={value ? 14 : 5} value={value} onChange={(e) => onChange(e.target.value)} />
      </Field>
    </div>
  );
}

export default function BidCheck() {
  const { name: profileName } = useProfile();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const storedId = params.get("run");
  const stored = useQuery({ queryKey: ["run", storedId], queryFn: () => api.run<DocumentMatchResult>(storedId!), enabled: Boolean(storedId) });
  const { state, start, reset } = useRunStream<DocumentMatchResult>();
  const [rfp, setRfp] = useState("");
  const [response, setResponse] = useState("");

  useEffect(() => {
    if (state.result) {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      setParams({ run: state.result.workflow_id }, { replace: true });
    }
  }, [state.result, queryClient, setParams]);

  const result = state.result ?? (storedId ? stored.data?.result : undefined);
  const showInput = state.phase === "idle" && !result;
  const scores = result?.scores;

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 sm:px-8">
      <PageHeader
        title="Bid check"
        description="Score a response you already wrote against the RFP before it goes out: what is missing, and how an evaluator would grade it."
        actions={!showInput && (
          <Button variant="secondary" icon={<ScanSearch className="size-4" />} onClick={() => { reset(); setParams({}); }}>Check another</Button>
        )}
      />
      {showInput && (
        <div className="flex flex-col gap-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <DocInput id="rfp" label="RFP" value={rfp} onChange={setRfp} profile={profileName} />
            <DocInput id="response" label="Our response" value={response} onChange={setResponse} profile={profileName} />
          </div>
          <div>
            <Button
              variant="primary"
              size="lg"
              disabled={rfp.trim().length < 40 || response.trim().length < 40}
              onClick={() => start("/document-match-runs/stream", { request_text: rfp, document_text: response, profile: profileName })}
            >
              Check the response
            </Button>
          </div>
        </div>
      )}
      {(state.phase === "running" || state.phase === "error") && (
        <Panel className="p-5">
          <PlanTrack state={state} />
          {state.error && <div className="mt-4"><Notice tone="bad" title="The check did not finish">{state.error.message}</Notice></div>}
        </Panel>
      )}
      {result && scores && (
        <div className="grid gap-6 lg:grid-cols-[340px_minmax(0,1fr)]">
          <div className="flex flex-col gap-6">
            <Panel className="flex flex-col gap-5 p-5">
              <HeroScore value={scores.composite_score} label="Response score" />
              <div className="flex flex-col gap-3.5">
                <Meter label="Requirement coverage" value={scores.requirement_coverage_score} />
                <Meter label="Evaluator rubric" value={scores.quality_score} />
                <Meter label="Offering fit" value={scores.solution_fit_score} />
                <Meter label="Precedent similarity" value={scores.historical_similarity_score} />
              </div>
            </Panel>
            {result.warnings.map((w) => <Notice key={w} title="Heads up">{w}</Notice>)}
          </div>
          <div className="flex min-w-0 flex-col gap-6">
            <Panel>
              <PanelHeader
                title="Requirements"
                action={scores.missing_requirements.length ? <StatusTag tone="warn">{scores.missing_requirements.length} not addressed</StatusTag> : <StatusTag tone="good">All addressed</StatusTag>}
              />
              <div className="px-5 py-2"><RequirementList details={scores.coverage_details} /></div>
            </Panel>
            {scores.rubric && (
              <Panel>
                <PanelHeader title="Evaluator rubric" description="Each criterion scored out of 10" />
                <div className="flex flex-col gap-6 p-5">
                  <BarList rows={scores.rubric.criteria.map((c) => ({ label: c.criterion, value: c.score }))} format={(n) => n.toFixed(1)} />
                  <div className="grid gap-5 md:grid-cols-3">
                    {([["Strengths", scores.rubric.strengths], ["Weaknesses", scores.rubric.weaknesses], ["Fix before sending", scores.rubric.recommendations]] as const).map(([label, items]) => (
                      <div key={label}>
                        <p className="text-small font-semibold text-ink">{label}</p>
                        <ul className="mt-2 flex list-disc flex-col gap-1.5 pl-5 text-small text-ink-2">{items.map((x) => <li key={x}>{x}</li>)}</ul>
                      </div>
                    ))}
                  </div>
                </div>
              </Panel>
            )}
            <Panel>
              <PanelHeader title="Token usage" />
              <TokenReport usage={result.token_usage} />
            </Panel>
          </div>
        </div>
      )}
    </div>
  );
}
