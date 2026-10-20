import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { Copy, Database, Download, FileDown, Sparkles } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { HeroScore, Meter } from "@/components/figures";
import { Markdown } from "@/components/Markdown";
import { RequirementList } from "@/components/RequirementList";
import { Sheet } from "@/components/Sheet";
import { useToast } from "@/components/Toast";
import { TokenReport } from "@/components/TokenReport";
import { Button, Chip, Field, Notice, Panel, PanelHeader, Skeleton, StatusTag, TextArea } from "@/components/ui";
import { useProfile } from "@/hooks/useProfile";
import { api, ApiError } from "@/lib/api";
import { fmtInt, fmtRelative } from "@/lib/format";
import { spring } from "@/lib/motion";
import type { ProposalResult, Section, StoredRun } from "@/lib/types";

const QUICK_EDITS = ["Make it shorter", "More executive tone", "Lead with business outcomes", "Simplify the language", "Add concrete next steps"];

function sectionMeta(s: Section): string {
  if (s.cache_hit) return "From cache";
  if (s.generation_mode === "fallback" || s.generation_mode === "template") return "Outline only";
  const tokens = s.usage?.total_tokens;
  return [`${fmtInt(s.word_count)} words`, tokens ? `${fmtInt(tokens)} tokens` : null, s.revision_number && s.revision_number > 1 ? `revision ${s.revision_number}` : null]
    .filter(Boolean)
    .join(", ");
}

function ReviseSheet({ section, run, open, onOpenChange }: {
  section: Section | null;
  run: StoredRun<ProposalResult>;
  open: boolean;
  onOpenChange: (v: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [instruction, setInstruction] = useState("");
  useEffect(() => setInstruction(""), [section?.section_key]);
  const history = useQuery({
    queryKey: ["revisions", section?.section_id],
    queryFn: () => api.revisions(section!.section_id!),
    enabled: open && Boolean(section?.section_id),
  });

  const mutation = useMutation({
    mutationFn: () =>
      api.revise(section!.section_id ?? run.workflow_id, {
        instruction,
        section_key: section!.section_key,
        base_text: section!.draft_text,
        requirements: run.result.request?.requirements,
        profile: run.profile,
      }),
    onSuccess: (res) => {
      queryClient.setQueryData<StoredRun<ProposalResult>>(["run", run.workflow_id], (prev) =>
        prev && {
          ...prev,
          result: {
            ...prev.result,
            sections: prev.result.sections.map((s) =>
              s.section_key === section!.section_key
                ? { ...s, draft_text: res.revision.draft_text, word_count: res.revision.draft_text.split(/\s+/).length, revision_number: res.revision.revision_number ?? (s.revision_number ?? 1) + 1, cache_hit: false }
                : s,
            ),
          },
        },
      );
      queryClient.invalidateQueries({ queryKey: ["revisions", section?.section_id] });
      toast({
        tone: "good",
        title: res.revision.revision_number ? `Revision ${res.revision.revision_number} saved` : "Section revised",
        detail: res.revision.revision_summary,
      });
      onOpenChange(false);
    },
    onError: (err) => toast({ tone: "bad", title: "Revision failed", detail: err instanceof ApiError ? err.message : undefined }),
  });

  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title={section ? `Revise ${section.title}` : "Revise"}
      description="Describe the change. Requirements already addressed are kept."
      footer={
        <div className="flex items-center justify-end gap-2">
          <Button variant="ghost" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button variant="primary" icon={<Sparkles className="size-4" />} loading={mutation.isPending} disabled={!instruction.trim()} onClick={() => mutation.mutate()}>
            Revise section
          </Button>
        </div>
      }
    >
      <div className="flex flex-col gap-5">
        <Field label="What should change?" htmlFor="instruction">
          <TextArea id="instruction" rows={5} autoFocus value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="e.g. Shorten to 150 words and mention our 24x7 support model." />
        </Field>
        <div className="flex flex-wrap gap-2">
          {QUICK_EDITS.map((q) => (
            <Chip key={q} active={instruction === q} onClick={() => setInstruction(q)}>{q}</Chip>
          ))}
        </div>
        {section?.section_id && (history.data?.revisions.length ?? 0) > 1 && (
          <div>
            <p className="mb-2 text-small font-semibold text-ink-2">History</p>
            <ol className="flex flex-col gap-2">
              {history.data!.revisions.slice().reverse().map((r) => (
                <li key={r.revision_id} className="rounded-control border border-line px-3 py-2 text-small">
                  <p className="text-ink">Revision {r.revision_number}{r.instruction ? `: ${r.instruction}` : " (first draft)"}</p>
                  <p className="text-caption text-ink-3">{fmtRelative(r.created_at)}</p>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </Sheet>
  );
}

export default function Workspace() {
  const { id = "" } = useParams();
  const toast = useToast();
  const { profile } = useProfile();
  const query = useQuery({ queryKey: ["run", id], queryFn: () => api.run<ProposalResult>(id) });
  const [active, setActive] = useState<string | null>(null);
  const [revising, setRevising] = useState<Section | null>(null);
  const refs = useRef<Record<string, HTMLElement | null>>({});
  const run = query.data;
  const result = run?.result;
  const sections = useMemo(() => (result?.sections ?? []).filter((s) => s.draft_text || s.error), [result]);
  const titles = useMemo(() => Object.fromEntries(sections.map((s) => [s.section_key, s.title])), [sections]);

  useEffect(() => {
    if (!sections.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.getAttribute("data-key"));
      },
      { rootMargin: "-80px 0px -60% 0px" },
    );
    Object.values(refs.current).forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
  }, [sections]);

  if (query.isLoading) {
    return (
      <div className="mx-auto flex max-w-[1400px] flex-col gap-4 px-8 py-8">
        <Skeleton className="h-9 w-80" />
        <Skeleton className="h-5 w-56" />
        <Skeleton className="mt-6 h-[50vh] w-full" />
      </div>
    );
  }
  if (query.isError || !run || !result) {
    return (
      <div className="mx-auto max-w-[720px] px-8 py-12">
        <Notice tone="bad" title="This proposal could not be opened">
          {(query.error as Error)?.message ?? "It may have been created without database persistence."}{" "}
          <Link to="/proposals" className="text-ion-strong underline">Back to proposals</Link>
        </Notice>
      </div>
    );
  }

  const scores = result.scores ?? ({} as ProposalResult["scores"]);
  const exportable = result.persisted !== false;
  const request = result.request;
  const exportAs = async (format: "pdf" | "md") => {
    try {
      await api.download(run.workflow_id, format);
    } catch (err) {
      toast({ tone: "bad", title: "Export failed", detail: err instanceof ApiError ? err.message : undefined });
    }
  };
  const copy = async (s: Section) => {
    try {
      await navigator.clipboard.writeText(s.draft_text);
      toast({ tone: "good", title: `${s.title} copied` });
    } catch {
      toast({ tone: "bad", title: "Copy is blocked in this browser" });
    }
  };
  const jump = (key: string) => {
    setActive(key);
    refs.current[key]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="fade-in mx-auto grid max-w-[1440px] gap-8 px-4 py-8 sm:px-8 xl:grid-cols-[200px_minmax(0,1fr)_340px]">
      {/* Outline */}
      <nav className="hidden xl:block" aria-label="Sections">
        <div className="sticky top-6 flex flex-col gap-0.5">
          <p className="px-2.5 pb-2 text-caption text-ink-3">Sections</p>
          {sections.map((s) => (
            <button
              key={s.section_key}
              type="button"
              onClick={() => jump(s.section_key)}
              className={clsx("relative flex items-center gap-2 rounded-control px-2.5 py-1.5 text-left text-small", active === s.section_key ? "text-ink" : "text-ink-3 hover:text-ink-2")}
            >
              {active === s.section_key && <motion.span layoutId="outline-active" transition={spring.snappy} className="absolute inset-0 rounded-control bg-raised" />}
              <span className="relative truncate">{s.title}</span>
              {s.error && <span className="relative ml-auto size-1.5 shrink-0 rounded-full bg-bad" aria-label="failed" />}
            </button>
          ))}
        </div>
      </nav>

      {/* Document */}
      <article className="min-w-0">
        <header className="mb-8 flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-display font-semibold text-ink">{request?.title || "Proposal"}</h1>
            <p className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1 text-body text-ink-2">
              {request?.client_name && <span>{request.client_name}</span>}
              {request?.industry && request.industry !== "Unspecified" && <span className="text-ink-3">{request.industry}</span>}
              <span className="text-ink-3">{fmtRelative(run.created_at)}</span>
            </p>
          </div>
          <div className="flex gap-2" title={exportable ? undefined : "Export needs the run saved in the database"}>
            <Button size="sm" icon={<Download className="size-4" />} onClick={() => exportAs("pdf")} disabled={!exportable}>
              PDF
            </Button>
            <Button size="sm" variant="ghost" icon={<FileDown className="size-4" />} onClick={() => exportAs("md")} disabled={!exportable}>
              Markdown
            </Button>
          </div>
        </header>

        <div className="mb-6 flex flex-col gap-3">
          {result.warnings?.map((w) => <Notice key={w} title="Heads up">{w}</Notice>)}
          {result.status !== "completed" && <Notice title={`This run is ${result.status}`}>Some steps did not finish. Sections that failed are marked below.</Notice>}
        </div>

        <div className="flex flex-col gap-14">
          {sections.map((s) => (
            <section key={s.section_key} data-key={s.section_key} ref={(el) => { refs.current[s.section_key] = el; }} className="scroll-mt-6">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
                <div className="min-w-0">
                  <h2 className="text-title font-semibold text-ink">{s.title}</h2>
                  <p className="mt-0.5 flex items-center gap-1.5 text-small text-ink-3">
                    {s.cache_hit && <Database className="size-3.5 text-viz-2" aria-hidden />}
                    {s.error ? "Failed" : sectionMeta(s)}
                  </p>
                </div>
                {!s.error && (
                  <div className="flex gap-1.5">
                    <Button size="sm" variant="ghost" icon={<Copy className="size-3.5" />} onClick={() => copy(s)}>Copy</Button>
                    <Button size="sm" variant="secondary" icon={<Sparkles className="size-3.5" />} onClick={() => setRevising(s)}>Revise</Button>
                  </div>
                )}
              </div>
              {s.error ? (
                <Notice tone="bad" title="This section was not drafted">{s.error}</Notice>
              ) : (
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div
                    key={`${s.section_key}-${s.revision_number ?? 1}`}
                    initial={{ opacity: 0, filter: "blur(4px)" }}
                    animate={{ opacity: 1, filter: "blur(0px)" }}
                    exit={{ opacity: 0 }}
                    transition={spring.smooth}
                  >
                    <Markdown>{s.draft_text}</Markdown>
                  </motion.div>
                </AnimatePresence>
              )}
            </section>
          ))}
        </div>
      </article>

      {/* Inspector */}
      <aside className="flex flex-col gap-5 xl:sticky xl:top-6 xl:max-h-[calc(100dvh-7rem)] xl:self-start xl:overflow-y-auto xl:pb-6">
        <Panel className="flex flex-col gap-5 p-5">
          <HeroScore value={scores.composite_score} label="Response score" caption="Weighted by the profile's scoring settings" />
          <div className="flex flex-col gap-3.5">
            <Meter label="Requirement coverage" value={scores.requirement_coverage_score} />
            <Meter label="Evaluator rubric" value={scores.quality_score} />
            <Meter label="Offering fit" value={scores.solution_fit_score} />
            <Meter label="Completeness" value={scores.completeness_score} />
            <Meter label="Precedent similarity" value={scores.historical_similarity_score} />
          </div>
          {scores.rubric?.weaknesses?.length ? (
            <div className="border-t border-line pt-4">
              <p className="text-small font-semibold text-ink">What an evaluator would push on</p>
              <ul className="mt-2 flex flex-col gap-1.5 text-small text-ink-2">
                {scores.rubric.weaknesses.slice(0, 4).map((w) => <li key={w}>{w}</li>)}
              </ul>
            </div>
          ) : null}
        </Panel>

        <Panel>
          <PanelHeader
            title="Requirements"
            description={request?.requirements?.length ? `${request.requirements.length} extracted from the RFP` : undefined}
            action={scores.missing_requirements?.length ? <StatusTag tone="warn">{scores.missing_requirements.length} open</StatusTag> : request?.requirements?.length ? <StatusTag tone="good">All addressed</StatusTag> : undefined}
          />
          <div className="px-5 py-2">
            <RequirementList details={scores.coverage_details ?? []} limit={10} />
          </div>
        </Panel>

        {request && (
          <Panel>
            <PanelHeader title="Brief" />
            <dl className="flex flex-col gap-3 px-5 py-4 text-small">
              {request.timeline && (<div><dt className="text-ink-3">Timeline</dt><dd className="text-ink">{request.timeline}</dd></div>)}
              {request.budget && (<div><dt className="text-ink-3">Budget</dt><dd className="text-ink">{request.budget}</dd></div>)}
              {request.compliance_requirements?.length > 0 && (
                <div><dt className="text-ink-3">Compliance</dt><dd className="mt-1 flex flex-wrap gap-1.5">{request.compliance_requirements.map((c) => <StatusTag key={c} tone="ion">{c}</StatusTag>)}</dd></div>
              )}
              {result.solution_comparison?.matching_offerings?.length > 0 && (
                <div><dt className="text-ink-3">{result.solution_comparison.catalog_configured ? "Matched offerings" : "Capabilities needed"}</dt><dd className="text-ink">{result.solution_comparison.matching_offerings.join(", ")}</dd></div>
              )}
              {request.ambiguity_flags?.length > 0 && (
                <div><dt className="text-ink-3">Clarify with the buyer</dt><dd><ul className="mt-1 flex flex-col gap-1 text-ink-2">{request.ambiguity_flags.map((f) => <li key={f}>{f}</li>)}</ul></dd></div>
              )}
            </dl>
          </Panel>
        )}

        {result.token_usage?.totals && (
          <Panel>
            <PanelHeader title="Token usage" description="This run, by section, agent, and model" />
            <TokenReport usage={result.token_usage} sectionTitles={{ ...Object.fromEntries((profile?.sections ?? []).map((s) => [s.key, s.title])), ...titles }} showCalls={false} />
          </Panel>
        )}
      </aside>

      <ReviseSheet section={revising} run={run} open={revising !== null} onOpenChange={(v) => !v && setRevising(null)} />
    </div>
  );
}
