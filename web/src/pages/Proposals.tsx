import { useQuery } from "@tanstack/react-query";
import { FileText, Search } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button, EmptyState, Notice, PageHeader, Panel, Segmented, Skeleton, TextInput } from "@/components/ui";
import { api } from "@/lib/api";
import { spring } from "@/lib/motion";
import { RunRow } from "./Home";

type Filter = "all" | "proposal_generation" | "intent_detection" | "document_match";

export default function Proposals() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const runs = useQuery({
    queryKey: ["runs", "list", filter],
    queryFn: () => api.runs(100, filter === "all" ? undefined : filter),
    placeholderData: (prev) => prev,
  });
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = (runs.data?.runs ?? []).filter((r) => r.workflow_type !== "market_research" && r.workflow_type !== "revision");
    return q ? list.filter((r) => `${r.title} ${r.client_name}`.toLowerCase().includes(q)) : list;
  }, [runs.data, query]);

  return (
    <div className="mx-auto max-w-[1100px] px-4 py-8 sm:px-8">
      <PageHeader
        title="Proposals"
        description="Every draft, deal analysis, and bid check your team has run."
        actions={<Button variant="primary" onClick={() => navigate("/new")}>New proposal</Button>}
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segmented
          label="Type"
          value={filter}
          onChange={setFilter}
          options={[
            { value: "all", label: "All" },
            { value: "proposal_generation", label: "Proposals" },
            { value: "intent_detection", label: "Deal analyses" },
            { value: "document_match", label: "Bid checks" },
          ]}
        />
        <div className="relative ml-auto w-full sm:w-72">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" />
          <TextInput value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter by client or title" className="pl-9" aria-label="Filter" />
        </div>
      </div>
      <Panel className={runs.isFetching && !runs.isLoading ? "opacity-70 transition-opacity" : "transition-opacity"}>
        {runs.isLoading ? (
          <div className="flex flex-col gap-3 p-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : runs.isError ? (
          <div className="p-5"><Notice tone="bad" title="The list could not be loaded">{(runs.error as Error).message}</Notice></div>
        ) : shown.length ? (
          <motion.div layout className="divide-y divide-line">
            <AnimatePresence initial={false}>
              {shown.map((run) => (
                <motion.div key={run.workflow_id} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={spring.smooth}>
                  <RunRow run={run} />
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>
        ) : (
          <EmptyState
            icon={<FileText className="size-5" />}
            title={query ? "No matches" : "Nothing here yet"}
            description={query ? "Try another client name or clear the filter." : "Runs appear here as soon as they finish."}
          />
        )}
      </Panel>
    </div>
  );
}
