import { useQuery } from "@tanstack/react-query";
import { FileText, MessagesSquare, ScanSearch } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { DropZone } from "@/components/DropZone";
import { Button, EmptyState, Notice, Panel, PanelHeader, Skeleton } from "@/components/ui";
import { useProfile } from "@/hooks/useProfile";
import { useReadiness } from "@/hooks/useReadiness";
import { api, ApiError } from "@/lib/api";
import { fmtCompact, fmtCost, fmtRelative } from "@/lib/format";
import { spring } from "@/lib/motion";
import type { RunSummary } from "@/lib/types";

const RUN_LINKS: Record<string, (id: string) => string> = {
  proposal_generation: (id) => `/proposals/${id}`,
  intent_detection: (id) => `/deals?run=${id}`,
  document_match: (id) => `/bid-check?run=${id}`,
};
const RUN_KIND: Record<string, string> = {
  proposal_generation: "Proposal",
  intent_detection: "Deal analysis",
  document_match: "Bid check",
  market_research: "Market scan",
};

function ScoreCell({ value }: { value: number | null }) {
  if (value == null) return <span className="text-small text-ink-3">Not scored</span>;
  const pct = Math.round(value * 100);
  return (
    <span className="flex items-center gap-2">
      <span className="tabular w-7 text-right text-small font-semibold text-ink">{pct}</span>
      <span className="h-1 w-14 overflow-hidden rounded-full bg-viz-track">
        <span className="block h-full rounded-full bg-viz-1" style={{ width: `${pct}%` }} />
      </span>
    </span>
  );
}

export function RunRow({ run }: { run: RunSummary }) {
  const to = RUN_LINKS[run.workflow_type]?.(run.workflow_id);
  const content = (
    <>
      <span className="flex size-8 shrink-0 items-center justify-center rounded-control bg-raised text-ink-2">
        {run.workflow_type === "intent_detection" ? <MessagesSquare className="size-4" /> : run.workflow_type === "document_match" ? <ScanSearch className="size-4" /> : <FileText className="size-4" />}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-body font-semibold text-ink">{run.title || run.client_name || "Untitled"}</span>
        <span className="block truncate text-small text-ink-3">
          {[run.client_name && run.title ? run.client_name : null, RUN_KIND[run.workflow_type], run.section_count ? `${run.section_count} sections` : null]
            .filter(Boolean)
            .join(", ")}
        </span>
      </span>
      <span className="hidden sm:block">{run.workflow_type !== "intent_detection" && <ScoreCell value={run.composite_score} />}</span>
      <span className="w-20 shrink-0 text-right text-small text-ink-3">{fmtRelative(run.created_at)}</span>
    </>
  );
  const cls = "flex items-center gap-3 px-5 py-3 transition-colors hover:bg-fill";
  return to ? <Link to={to} className={cls}>{content}</Link> : <div className={cls}>{content}</div>;
}

export default function Home() {
  const navigate = useNavigate();
  const { name: profile, profile: detail } = useProfile();
  const readiness = useReadiness();
  const runs = useQuery({ queryKey: ["runs", "home"], queryFn: () => api.runs(8) });
  const week = useQuery({ queryKey: ["usage", 7], queryFn: () => api.usageSummary(7) });
  const [busy, setBusy] = useState(false);
  const orgName = detail?.organization.name;
  const hasOrg = Boolean(orgName && orgName.toLowerCase() !== "our organization");
  const [error, setError] = useState<string | null>(null);

  const onFile = async (files: File[]) => {
    setBusy(true);
    setError(null);
    try {
      const doc = await api.extractText(files[0], profile);
      navigate("/new", { state: { text: doc.text, fileName: doc.file_name } });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not read that file.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto grid max-w-[1240px] gap-8 px-4 py-8 sm:px-8 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="flex min-w-0 flex-col gap-8">
        <section>
          <motion.h1
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={spring.smooth}
            className="max-w-[22ch] text-[2.4rem] font-semibold leading-[1.1] tracking-[-0.02em] text-ink"
          >
            Turn an RFP into a first draft.
          </motion.h1>
          <p className="mt-3 max-w-[60ch] text-lead text-ink-2">
            The agents read the requirements, match them to {hasOrg ? `${orgName}'s` : "your"} offerings, reuse your best
            past proposals, and score the response before you send it.
          </p>
          <div className="mt-6">
            <DropZone
              title="Drop the RFP here"
              hint="PDF, Word, Markdown, or text. You can also paste it on the next screen."
              onFiles={onFile}
              busy={busy}
            >
              <div className="mt-1 flex flex-wrap justify-center gap-2" onClick={(e) => e.stopPropagation()}>
                <Button size="sm" variant="secondary" onClick={() => navigate("/new")}>Paste RFP text</Button>
                <Button size="sm" variant="ghost" onClick={() => navigate("/deals")}>Analyze a sales call</Button>
              </div>
            </DropZone>
            {error && <div className="mt-3"><Notice tone="bad" title="That file could not be read">{error}</Notice></div>}
          </div>
        </section>

        <Panel>
          <PanelHeader title="Recent work" action={<Link to="/proposals" className="text-small text-ion-strong hover:underline">See all</Link>} />
          {runs.isLoading ? (
            <div className="flex flex-col gap-3 p-5">
              {[0, 1, 2].map((i) => <Skeleton key={i} className="h-10" />)}
            </div>
          ) : runs.isError ? (
            <div className="p-5"><Notice tone="bad" title="Recent work is unavailable">{(runs.error as Error).message}</Notice></div>
          ) : runs.data?.runs.length ? (
            <div className="divide-y divide-line">
              {runs.data.runs.map((run) => <RunRow key={run.workflow_id} run={run} />)}
            </div>
          ) : (
            <EmptyState
              icon={<FileText className="size-5" />}
              title="No proposals yet"
              description="Drop an RFP above to draft your first one. Finished drafts, deal analyses, and bid checks show up here."
            />
          )}
        </Panel>
      </div>

      <aside className="flex flex-col gap-6">
        {readiness.state === "degraded" && (
          <Notice title="Drafts will be outlines only">
            The Groq key is not configured on the server. Add RFP_GROQ_API_KEY to enable the models.
          </Notice>
        )}
        <Panel>
          <PanelHeader title="Last 7 days" action={<Link to="/usage" className="text-small text-ion-strong hover:underline">Usage</Link>} />
          <dl className="grid grid-cols-2 gap-x-4 gap-y-4 p-5">
            {[
              ["Runs", week.data?.workflows ?? 0, (n: number) => String(n)],
              ["Tokens", week.data?.totals.total_tokens ?? 0, fmtCompact],
              ["Cost", week.data?.totals.cost_usd ?? 0, fmtCost],
              ["Saved by cache", week.data?.totals.saved_tokens ?? 0, fmtCompact],
            ].map(([label, value, fmt]) => (
              <div key={label as string}>
                <dt className="text-small text-ink-3">{label as string}</dt>
                <dd className="mt-0.5 text-title font-semibold text-ink">{(fmt as (n: number) => string)(value as number)}</dd>
              </div>
            ))}
          </dl>
        </Panel>
        <Panel>
          <PanelHeader title="Writing as" />
          <div className="flex flex-col gap-3 p-5 text-small">
            <div>
              <p className="text-ink-3">Organization</p>
              <p className="text-ink">{detail ? (hasOrg ? orgName : "Not set. Add your company to the domain profile.") : "Loading"}</p>
            </div>
            <div>
              <p className="text-ink-3">Offerings in the catalog</p>
              <p className="text-ink">{detail ? (detail.offerings.length ? detail.offerings.map((o) => o.name).join(", ") : "None yet: capabilities are inferred from each RFP") : "Loading"}</p>
            </div>
            <Link to="/settings" className="text-ion-strong hover:underline">Change profile</Link>
          </div>
        </Panel>
      </aside>
    </div>
  );
}
