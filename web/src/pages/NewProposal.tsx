import { useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { ArrowLeft, GripVertical, Plus, X } from "lucide-react";
import { AnimatePresence, motion, Reorder, useDragControls } from "motion/react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { DropZone } from "@/components/DropZone";
import { LiveSections, PlanTrack } from "@/components/RunProgress";
import { useToast } from "@/components/Toast";
import { Button, Chip, Field, Notice, Panel, Select, Switch, TextArea, TextInput } from "@/components/ui";
import { sectionTitle, useProfile } from "@/hooks/useProfile";
import { useReadiness } from "@/hooks/useReadiness";
import { useRunStream } from "@/hooks/useRunStream";
import { api, ApiError } from "@/lib/api";
import { fmtInt } from "@/lib/format";
import { spring } from "@/lib/motion";
import type { ProposalResult } from "@/lib/types";

const INFER = "";

function Step({ n, title, description, children }: { n: number; title: string; description?: string; children: ReactNode }) {
  return (
    <section className="grid gap-4 border-b border-line py-7 first:pt-0 last:border-0 md:grid-cols-[40px_1fr]">
      <span className="tabular flex size-7 items-center justify-center rounded-full border border-line-strong text-small text-ink-2">{n}</span>
      <div className="flex min-w-0 flex-col gap-4">
        <div>
          <h2 className="text-lead font-semibold text-ink">{title}</h2>
          {description && <p className="mt-0.5 text-small text-ink-3">{description}</p>}
        </div>
        {children}
      </div>
    </section>
  );
}

function SectionRow({ id, title, onRemove }: { id: string; title: string; onRemove: () => void }) {
  const controls = useDragControls();
  return (
    <Reorder.Item
      value={id}
      dragListener={false}
      dragControls={controls}
      transition={spring.smooth}
      whileDrag={{ scale: 1.02, boxShadow: "0 12px 30px -10px rgb(0 0 0 / 0.6)" }}
      className="flex h-11 items-center gap-2 rounded-control border border-line bg-raised pl-1.5 pr-1"
    >
      <button
        type="button"
        aria-label={`Drag to reorder ${title}`}
        onPointerDown={(e) => controls.start(e)}
        className="flex h-8 w-7 cursor-grab touch-none items-center justify-center rounded-[6px] text-ink-3 hover:text-ink-2 active:cursor-grabbing"
      >
        <GripVertical className="size-4" />
      </button>
      <span className="min-w-0 flex-1 truncate text-body text-ink">{title}</span>
      <button type="button" onClick={onRemove} aria-label={`Remove ${title}`} className="flex size-8 items-center justify-center rounded-[6px] text-ink-3 hover:bg-wash-strong hover:text-ink">
        <X className="size-4" />
      </button>
    </Reorder.Item>
  );
}

export default function NewProposal() {
  const navigate = useNavigate();
  const location = useLocation() as { state?: { text?: string; fileName?: string } };
  const queryClient = useQueryClient();
  const toast = useToast();
  const { name: profileName, profile } = useProfile();
  const readiness = useReadiness();
  const { state: run, start, reset } = useRunStream<ProposalResult>();

  const [rfp, setRfp] = useState(location.state?.text ?? "");
  const [fileName, setFileName] = useState(location.state?.fileName ?? "");
  const [reading, setReading] = useState(false);
  const [client, setClient] = useState("");
  const [title, setTitle] = useState("");
  const [industry, setIndustry] = useState(INFER);
  const [offering, setOffering] = useState(INFER);
  const [sections, setSections] = useState<string[]>([]);
  const [themes, setThemes] = useState("");
  const [instruction, setInstruction] = useState("");
  const [reuse, setReuse] = useState(true);
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    if (profile && sections.length === 0) setSections(profile.default_sections);
  }, [profile?.name]); // re-seed only when the profile changes

  const words = useMemo(() => (rfp.trim() ? rfp.trim().split(/\s+/).length : 0), [rfp]);
  const available = (profile?.sections ?? []).filter((s) => !sections.includes(s.key));
  const errors = {
    rfp: words < 25 ? "Paste the RFP or upload the file (at least a few sentences)." : null,
    client: client.trim() ? null : "Enter the client organization.",
    sections: sections.length ? null : "Choose at least one section.",
  };
  const valid = !errors.rfp && !errors.client && !errors.sections;

  const readFile = async (files: File[]) => {
    setReading(true);
    try {
      const doc = await api.extractText(files[0], profileName);
      setRfp(doc.text);
      setFileName(doc.file_name);
    } catch (err) {
      toast({ tone: "bad", title: "That file could not be read", detail: err instanceof ApiError ? err.message : undefined });
    } finally {
      setReading(false);
    }
  };

  const draft = async () => {
    setTouched(true);
    if (!valid) return;
    const instructionText = [instruction.trim(), themes.trim() && `Win themes to emphasize: ${themes.trim()}`].filter(Boolean).join(". ");
    const result = await start("/workflow-runs/stream", {
      request_text: rfp.trim(),
      title: title.trim() || `${client.trim()} proposal`,
      client_name: client.trim(),
      industry: industry || undefined,
      solution_type: offering || undefined,
      user_instruction: instructionText || undefined,
      target_sections: sections,
      profile: profileName,
      cache_policy: reuse ? "use" : "refresh",
    });
    if (result) {
      queryClient.setQueryData(["run", result.workflow_id], {
        workflow_id: result.workflow_id,
        workflow_type: "proposal_generation",
        status: result.status,
        profile: profileName,
        created_at: new Date().toISOString(),
        completed_at: new Date().toISOString(),
        result,
      });
      queryClient.invalidateQueries({ queryKey: ["runs"] });
      toast({
        tone: result.status === "completed" ? "good" : "info",
        title: result.status === "completed" ? "Proposal drafted" : `Proposal ${result.status}`,
        detail: `${result.sections.filter((s) => !s.error).length} sections, ${fmtInt(result.token_usage.totals.total_tokens)} tokens`,
      });
      setTimeout(() => navigate(`/proposals/${result.workflow_id}`), 900);
    }
  };

  const composing = run.phase === "idle" || run.phase === "error";

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 sm:px-8">
      <AnimatePresence mode="wait" initial={false}>
        {composing ? (
          <motion.div
            key="compose"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.985, transition: { duration: 0.16 } }}
            transition={spring.smooth}
            className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_300px]"
          >
            <div className="min-w-0">
              <h1 className="text-display font-semibold text-ink">New proposal</h1>
              <p className="mt-1.5 text-lead text-ink-2">Four steps. Only the RFP and the client are required.</p>
              {run.phase === "error" && run.error && (
                <div className="mt-6">
                  <Notice tone="bad" title="The draft did not finish">
                    {run.error.message}
                    {run.error.retryAfter ? ` Try again in ${Math.ceil(run.error.retryAfter)} seconds; finished sections are cached.` : ""}
                  </Notice>
                </div>
              )}
              <div className="mt-8">
                <Step n={1} title="The RFP" description="Paste it, or upload the document and the text is extracted for you.">
                  {!rfp && <DropZone compact title="Upload the RFP" hint="PDF, Word, Markdown, or text" onFiles={readFile} busy={reading} />}
                  <Field label="RFP text" htmlFor="rfp" error={touched ? errors.rfp : null} hint={fileName ? `From ${fileName}, ${fmtInt(words)} words` : `${fmtInt(words)} words`}>
                    <TextArea id="rfp" value={rfp} onChange={(e) => setRfp(e.target.value)} rows={rfp ? 14 : 6} placeholder="Scope, requirements, evaluation criteria, timeline, budget…" />
                  </Field>
                </Step>

                <Step n={2} title="Client" description="Contact details stay out of the requirements.">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label="Client organization" htmlFor="client" error={touched ? errors.client : null}>
                      <TextInput id="client" value={client} onChange={(e) => setClient(e.target.value)} placeholder="e.g. Contoso Health" />
                    </Field>
                    <Field label="Proposal title" htmlFor="title" hint="Optional">
                      <TextInput id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Patient portal modernization" />
                    </Field>
                    <Field label="Industry" htmlFor="industry">
                      <Select id="industry" value={industry} onChange={(e) => setIndustry(e.target.value)}>
                        <option value={INFER}>Let the agents decide</option>
                        {profile?.industries.map((i) => <option key={i} value={i}>{i}</option>)}
                      </Select>
                    </Field>
                    <Field label="Offering" htmlFor="offering" hint={profile && !profile.offerings.length ? "This profile has no catalog yet" : undefined}>
                      <Select id="offering" value={offering} onChange={(e) => setOffering(e.target.value)}>
                        <option value={INFER}>Let the agents decide</option>
                        {profile?.offerings.map((o) => <option key={o.code} value={o.code}>{o.name}</option>)}
                      </Select>
                    </Field>
                  </div>
                </Step>

                <Step n={3} title="Sections" description="Drag to set the order. They are drafted in parallel and assembled in this order.">
                  <Reorder.Group axis="y" values={sections} onReorder={setSections} className="flex flex-col gap-1.5">
                    {sections.map((key) => (
                      <SectionRow key={key} id={key} title={sectionTitle(profile, key)} onRemove={() => setSections((s) => s.filter((k) => k !== key))} />
                    ))}
                  </Reorder.Group>
                  {touched && errors.sections && <p className="text-small text-bad-text">{errors.sections}</p>}
                  {available.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {available.map((s) => (
                        <Chip key={s.key} onClick={() => setSections((prev) => [...prev, s.key])}>
                          <Plus className="size-3.5" />
                          {s.title}
                        </Chip>
                      ))}
                    </div>
                  )}
                </Step>

                <Step n={4} title="Guidance" description="Optional. Applies to every section.">
                  <Field label="Win themes" htmlFor="themes" hint="Comma-separated, e.g. speed to value, data security">
                    <TextInput id="themes" value={themes} onChange={(e) => setThemes(e.target.value)} />
                  </Field>
                  <Field label="Instructions for the writer" htmlFor="instruction">
                    <TextArea id="instruction" rows={3} value={instruction} onChange={(e) => setInstruction(e.target.value)} placeholder="e.g. Keep it executive-friendly and lead with ROI." />
                  </Field>
                  <Switch
                    checked={reuse}
                    onChange={setReuse}
                    label="Reuse sections that have not changed"
                    description="Identical inputs return the saved section instantly and cost no tokens."
                  />
                </Step>
              </div>
            </div>

            <aside className="lg:sticky lg:top-6 lg:self-start">
              <Panel className="p-5">
                <p className="text-body font-semibold text-ink">Ready to draft</p>
                <ul className="mt-4 flex flex-col gap-2.5 text-small">
                  {[
                    [words >= 25, words ? `${fmtInt(words)} words of RFP` : "RFP text"],
                    [Boolean(client.trim()), client.trim() || "Client organization"],
                    [sections.length > 0, `${sections.length} section${sections.length === 1 ? "" : "s"}`],
                  ].map(([ok, label]) => (
                    <li key={String(label)} className={clsx("flex items-center gap-2.5", ok ? "text-ink" : "text-ink-3")}>
                      <motion.span
                        animate={{ scale: ok ? 1 : 0.85, backgroundColor: ok ? "var(--color-ion)" : "var(--color-track-off)" }}
                        transition={spring.land}
                        className="size-2 rounded-full"
                      />
                      <span className="truncate">{label as string}</span>
                    </li>
                  ))}
                </ul>
                <Button variant="primary" size="lg" className="mt-5 w-full" onClick={draft} disabled={touched && !valid}>
                  Draft proposal
                </Button>
                <p className="mt-3 text-caption text-ink-3">
                  Written by {profile?.llm.frontier_model?.replace("openai/", "") ?? "the frontier model"}, planned by{" "}
                  {profile?.llm.fast_model?.replace("openai/", "") ?? "the fast model"}.
                </p>
              </Panel>
              {readiness.state === "degraded" && (
                <div className="mt-4">
                  <Notice title="No Groq key on the server">Sections will be outlines until RFP_GROQ_API_KEY is set.</Notice>
                </div>
              )}
            </aside>
          </motion.div>
        ) : (
          <motion.div
            key="run"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={spring.smooth}
            className="mx-auto flex max-w-[820px] flex-col gap-6"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <h1 className="truncate text-display font-semibold text-ink">{title.trim() || `${client.trim()} proposal`}</h1>
                <p className="mt-1 text-lead text-ink-2">{client.trim()}</p>
              </div>
              {run.phase === "running" ? (
                <Button variant="ghost" icon={<ArrowLeft className="size-4" />} onClick={reset} title="The draft keeps running and appears in Recent work">Back to edit</Button>
              ) : (
                run.result && <Button variant="primary" onClick={() => navigate(`/proposals/${run.result!.workflow_id}`)}>Open proposal</Button>
              )}
            </div>
            <Panel className="p-5">
              <PlanTrack state={run} />
            </Panel>
            {run.result?.warnings.map((w) => <Notice key={w} title="Heads up">{w}</Notice>)}
            <LiveSections sections={run.sections} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
