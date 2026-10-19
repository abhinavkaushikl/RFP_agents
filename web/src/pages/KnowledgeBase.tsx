import { useMutation } from "@tanstack/react-query";
import clsx from "clsx";
import { CheckCircle2, ChevronRight, Search, XCircle } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";

import { DropZone } from "@/components/DropZone";
import { useToast } from "@/components/Toast";
import { Button, Field, Notice, PageHeader, Panel, PanelHeader, Select, StatusTag, TextArea, TextInput } from "@/components/ui";
import { useProfile } from "@/hooks/useProfile";
import { api } from "@/lib/api";
import { fmtInt, titleCase } from "@/lib/format";
import { spring } from "@/lib/motion";
import type { IngestResult } from "@/lib/types";

function IngestSummary({ result }: { result: IngestResult }) {
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={spring.smooth} className="flex flex-col gap-3 rounded-panel border border-line p-4">
      <p className="text-small text-ink">
        Added <span className="tabular font-semibold">{result.ingested_count}</span> proposals,{" "}
        <span className="tabular font-semibold">{result.section_count}</span> sections,{" "}
        <span className="tabular font-semibold">{fmtInt(result.chunk_count)}</span> searchable passages.
        {result.skipped_duplicates > 0 && ` Skipped ${result.skipped_duplicates} already in the library.`}
      </p>
      {result.files.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {result.files.map((f) => (
            <li key={f.file_name} className="flex items-start gap-2 text-small">
              {f.ok ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-good" /> : <XCircle className="mt-0.5 size-4 shrink-0 text-bad" />}
              <span className="min-w-0">
                <span className="text-ink">{f.file_name}</span>
                <span className="block text-caption text-ink-3">{f.ok ? (f.sections ?? []).map(titleCase).join(", ") : f.error}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      {result.skipped.map((s, i) => <p key={i} className="text-caption text-ink-3">Skipped {s.id ?? `record ${s.index}`}: {s.reason}</p>)}
    </motion.div>
  );
}

export default function KnowledgeBase() {
  const { name: profileName, profile } = useProfile();
  const toast = useToast();
  const [client, setClient] = useState("");
  const [industry, setIndustry] = useState("");
  const [jsonOpen, setJsonOpen] = useState(false);
  const [json, setJson] = useState("");
  const [query, setQuery] = useState("");
  const [section, setSection] = useState("");
  const [searchIndustry, setSearchIndustry] = useState("");

  const upload = useMutation({
    mutationFn: (files: File[]) => api.uploadProposals(files, { source_name: "web_upload", profile: profileName, client_name: client || undefined, industry: industry || undefined }),
    onSuccess: (r) => toast({ tone: "good", title: `Added ${r.ingested_count} proposals to the library` }),
  });
  const importJson = useMutation({
    mutationFn: () => {
      const data = JSON.parse(json);
      const records = Array.isArray(data) ? data : Array.isArray(data?.records) ? data.records : [data];
      return api.ingestRecords(records, "web_json", profileName);
    },
  });
  const search = useMutation({
    mutationFn: () => api.search({ query, section_type: section || undefined, industry: searchIndustry || undefined, top_k: 8, profile: profileName }),
  });

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 sm:px-8">
      <PageHeader title="Knowledge base" description="Past proposals the agents reuse as precedent. The better the library, the better every draft." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <Panel>
          <PanelHeader title="Add past proposals" description="Section headings are matched to this profile's sections." />
          <div className="flex flex-col gap-4 p-5">
            <DropZone multiple title="Drop proposal documents" hint="Several at once is fine: PDF, Word, Markdown, or text" onFiles={(f) => upload.mutate(f)} busy={upload.isPending} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Client" htmlFor="kb-client" hint="Optional, applies to this upload">
                <TextInput id="kb-client" value={client} onChange={(e) => setClient(e.target.value)} />
              </Field>
              <Field label="Industry" htmlFor="kb-industry">
                <Select id="kb-industry" value={industry} onChange={(e) => setIndustry(e.target.value)}>
                  <option value="">Not specified</option>
                  {profile?.industries.map((i) => <option key={i}>{i}</option>)}
                </Select>
              </Field>
            </div>
            {upload.isError && <Notice tone="bad" title="Upload failed">{(upload.error as Error).message}</Notice>}
            {upload.data && <IngestSummary result={upload.data} />}

            <button type="button" onClick={() => setJsonOpen((v) => !v)} aria-expanded={jsonOpen} className="flex items-center gap-2 self-start text-small text-ink-2 hover:text-ink">
              <motion.span animate={{ rotate: jsonOpen ? 90 : 0 }} transition={spring.snappy}><ChevronRight className="size-4" /></motion.span>
              Import JSON records instead
            </button>
            <AnimatePresence initial={false}>
              {jsonOpen && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={spring.smooth} className="overflow-hidden">
                  <div className="flex flex-col gap-3 pt-1">
                    <TextArea rows={8} value={json} onChange={(e) => setJson(e.target.value)} className="font-mono text-small" placeholder={'[{"id": "p-014", "client_name": "City of Riverton", "proposal_sections": {"Executive Summary": "…"}}]'} aria-label="JSON records" />
                    <Button variant="secondary" loading={importJson.isPending} disabled={!json.trim()} onClick={() => importJson.mutate()} className="self-start">Import records</Button>
                    {importJson.isError && <Notice tone="bad" title="Import failed">{importJson.error instanceof SyntaxError ? "That is not valid JSON." : (importJson.error as Error).message}</Notice>}
                    {importJson.data && <IngestSummary result={importJson.data} />}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Search the library" description="What the agents would retrieve for a given need." />
          <form className="flex flex-col gap-4 p-5" onSubmit={(e) => { e.preventDefault(); if (query.trim()) search.mutate(); }}>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" />
              <TextInput value={query} onChange={(e) => setQuery(e.target.value)} placeholder="e.g. phased rollout with staff training" className="pl-9" aria-label="Search query" />
            </div>
            <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
              <Select value={section} onChange={(e) => setSection(e.target.value)} aria-label="Section">
                <option value="">Any section</option>
                {profile?.sections.map((s) => <option key={s.key} value={s.key}>{s.title}</option>)}
              </Select>
              <Select value={searchIndustry} onChange={(e) => setSearchIndustry(e.target.value)} aria-label="Industry">
                <option value="">Any industry</option>
                {profile?.industries.map((i) => <option key={i}>{i}</option>)}
              </Select>
              <Button type="submit" variant="primary" loading={search.isPending} disabled={!query.trim()}>Search</Button>
            </div>
          </form>
          <div className="flex flex-col gap-3 px-5 pb-5">
            {search.isError && <Notice tone="bad" title="Search failed">{(search.error as Error).message}</Notice>}
            {search.data && !search.data.results.length && <p className="text-small text-ink-3">Nothing similar yet. Add past proposals on the left.</p>}
            <AnimatePresence initial={false}>
              {search.data?.results.map((hit, i) => (
                <motion.article
                  key={hit.id}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0, transition: { ...spring.smooth, delay: i * 0.03 } }}
                  exit={{ opacity: 0 }}
                  className="rounded-control border border-line p-4"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusTag tone="ion">{profile?.sections.find((s) => s.key === hit.section_key)?.title ?? titleCase(hit.section_key || "section")}</StatusTag>
                    {hit.industry && <span className="text-caption text-ink-3">{hit.industry}</span>}
                    <span className="ml-auto flex items-center gap-2 text-caption text-ink-3">
                      <span className="h-1 w-16 overflow-hidden rounded-full bg-viz-track"><span className="block h-full rounded-full bg-viz-1" style={{ width: `${Math.round(hit.score * 100)}%` }} /></span>
                      <span className={clsx("tabular", hit.score >= 0.6 && "text-ink")}>{Math.round(hit.score * 100)}% similar</span>
                    </span>
                  </div>
                  <p className="mt-2.5 line-clamp-5 font-serif text-small leading-relaxed text-ink-2">{hit.content}</p>
                </motion.article>
              ))}
            </AnimatePresence>
          </div>
        </Panel>
      </div>
    </div>
  );
}
