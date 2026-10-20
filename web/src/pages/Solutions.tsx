import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Package, Pencil, Plus, Search, Trash2, Users } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState, type FormEvent } from "react";

import { Sheet } from "@/components/Sheet";
import { useToast } from "@/components/Toast";
import { Button, EmptyState, Field, IconButton, Notice, PageHeader, Panel, Select, Skeleton, StatusTag, Switch, TextArea, TextInput, type Tone } from "@/components/ui";
import { useAuth } from "@/hooks/useAuth";
import { api, ApiError } from "@/lib/api";
import { fmtRelative } from "@/lib/format";
import { spring } from "@/lib/motion";
import type { Solution, SolutionInput, SolutionStatus } from "@/lib/types";

const STATUS: Record<SolutionStatus, { label: string; tone: Tone }> = {
  active: { label: "Active", tone: "good" },
  planned: { label: "Planned", tone: "ion" },
  retired: { label: "Retired", tone: "neutral" },
};

const EMPTY: SolutionInput = { name: "", category: "", status: "active", description: "", capabilities: [], url: "" };

const toInput = (s: Solution): SolutionInput => ({
  name: s.name, category: s.category ?? "", status: s.status, description: s.description, capabilities: s.capabilities, url: s.url ?? "",
});

function SolutionForm({ solution, onClose }: { solution: Solution | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [form, setForm] = useState<SolutionInput>(solution ? toInput(solution) : EMPTY);
  const [capabilities, setCapabilities] = useState((solution?.capabilities ?? []).join("\n"));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      const body: SolutionInput = {
        ...form,
        category: form.category?.trim() || null,
        url: form.url?.trim() || null,
        capabilities: capabilities.split("\n").map((c) => c.trim()).filter(Boolean),
      };
      return solution ? api.updateSolution(solution.id, body) : api.createSolution(body);
    },
    onSuccess: (saved) => {
      void queryClient.invalidateQueries({ queryKey: ["solutions"] });
      toast({ tone: "good", title: solution ? "Solution updated" : "Solution added", detail: saved.name });
      onClose();
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not save. Try again."),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    save.mutate();
  };
  const set = <K extends keyof SolutionInput>(key: K, value: SolutionInput[K]) => setForm((f) => ({ ...f, [key]: value }));

  return (
    <form id="solution-form" onSubmit={submit} className="flex flex-col gap-4 px-5 py-4">
      <Field label="Name" htmlFor="sol-name">
        <TextInput id="sol-name" required autoFocus maxLength={160} value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="e.g. Acme CRM" />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Category" htmlFor="sol-cat" hint="Optional">
          <TextInput id="sol-cat" maxLength={80} value={form.category ?? ""} onChange={(e) => set("category", e.target.value)} placeholder="e.g. Sales software" />
        </Field>
        <Field label="Status" htmlFor="sol-status">
          <Select id="sol-status" value={form.status} onChange={(e) => set("status", e.target.value as SolutionStatus)}>
            <option value="active">Active</option>
            <option value="planned">Planned</option>
            <option value="retired">Retired</option>
          </Select>
        </Field>
      </div>
      <Field label="Description" htmlFor="sol-desc" hint="What it is and who it is for.">
        <TextArea id="sol-desc" maxLength={4000} value={form.description} onChange={(e) => set("description", e.target.value)} className="min-h-28" />
      </Field>
      <Field label="Capabilities" htmlFor="sol-caps" hint="One per line, up to 30.">
        <TextArea id="sol-caps" value={capabilities} onChange={(e) => setCapabilities(e.target.value)} className="min-h-24" placeholder={"Pipeline tracking\nOutlook sync"} />
      </Field>
      <Field label="Link" htmlFor="sol-url" hint="Optional. Product page, case study or repository.">
        <TextInput id="sol-url" type="url" maxLength={500} value={form.url ?? ""} onChange={(e) => set("url", e.target.value)} placeholder="https://" />
      </Field>
      {error && <Notice tone="bad" title="Could not save">{error}</Notice>}
    </form>
  );
}

function SolutionCard({ solution, showOwner, onEdit, onDelete }: { solution: Solution; showOwner: boolean; onEdit: () => void; onDelete: () => void }) {
  const status = STATUS[solution.status];
  return (
    <motion.li layout="position" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={spring.smooth} className="group flex flex-col gap-3 rounded-panel border border-line bg-panel p-5">
      <div className="flex items-start gap-3">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-control bg-raised text-ink-2"><Package className="size-[18px]" aria-hidden /></span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-body font-semibold text-ink">{solution.name}</h3>
          <p className="truncate text-small text-ink-3">
            {[solution.category, showOwner && solution.owner_email ? `Owner: ${solution.owner_email}` : null].filter(Boolean).join(" · ") || "No category"}
          </p>
        </div>
        <StatusTag tone={status.tone}>{status.label}</StatusTag>
      </div>
      {solution.description && <p className="line-clamp-3 text-small leading-relaxed text-ink-2">{solution.description}</p>}
      {solution.capabilities.length > 0 && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Capabilities">
          {solution.capabilities.slice(0, 6).map((c) => (
            <li key={c} className="rounded-full border border-line bg-fill px-2.5 py-0.5 text-caption text-ink-2">{c}</li>
          ))}
          {solution.capabilities.length > 6 && <li className="px-1 py-0.5 text-caption text-ink-3">+{solution.capabilities.length - 6} more</li>}
        </ul>
      )}
      <div className="mt-auto flex items-center justify-between gap-2 pt-1">
        <span className="text-caption text-ink-3">Updated {fmtRelative(solution.updated_at)}</span>
        <span className="flex items-center gap-0.5">
          {solution.url && (
            <a href={solution.url} target="_blank" rel="noreferrer noopener" aria-label={`Open ${solution.name} link`} className="grid size-8 place-items-center rounded-control text-ink-3 transition-colors hover:bg-wash hover:text-ink">
              <ExternalLink className="size-4" />
            </a>
          )}
          {solution.mine && <IconButton label={`Edit ${solution.name}`} onClick={onEdit}><Pencil className="size-4" /></IconButton>}
          <IconButton label={`Delete ${solution.name}`} onClick={onDelete}><Trash2 className="size-4" /></IconButton>
        </span>
      </div>
    </motion.li>
  );
}

export default function Solutions() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const queryClient = useQueryClient();
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [everyone, setEveryone] = useState(false);
  const [editing, setEditing] = useState<Solution | "new" | null>(null);
  const [deleting, setDeleting] = useState<Solution | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setQ(search.trim()), 250);
    return () => clearTimeout(timer);
  }, [search]);

  const list = useQuery({
    queryKey: ["solutions", q, isAdmin && everyone],
    queryFn: () => api.solutions({ q: q || undefined, everyone: isAdmin && everyone }),
    placeholderData: keepPreviousData,
  });
  const remove = useMutation({
    mutationFn: (s: Solution) => api.deleteSolution(s.id),
    onSuccess: (_, s) => {
      void queryClient.invalidateQueries({ queryKey: ["solutions"] });
      toast({ tone: "good", title: "Solution deleted", detail: s.name });
      setDeleting(null);
    },
    onError: (err) => toast({ tone: "bad", title: "Could not delete", detail: err instanceof ApiError ? err.message : undefined }),
  });

  const solutions = list.data?.solutions ?? [];
  const showOwner = isAdmin && everyone;

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 sm:px-8">
      <PageHeader
        title="Existing solutions"
        description={showOwner ? "Everyone's solutions. You can see and remove them, but only owners can edit their own." : "Solutions you already have. Only you can see this list."}
        actions={<Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setEditing("new")}>Add solution</Button>}
      />

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative w-full max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" aria-hidden />
          <TextInput aria-label="Search solutions" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by name, category or description" className="pl-9" />
        </div>
        {isAdmin && (
          <div className="flex items-center gap-2 text-small text-ink-2">
            <Users className="size-4 text-ink-3" aria-hidden />
            <Switch checked={everyone} onChange={setEveryone} label="Show everyone's" />
          </div>
        )}
      </div>

      {list.isLoading ? (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2].map((i) => <li key={i}><Skeleton className="h-44" /></li>)}</ul>
      ) : list.isError ? (
        <Notice tone="bad" title="Solutions could not be loaded">{(list.error as Error).message}</Notice>
      ) : solutions.length === 0 ? (
        <Panel>
          {q ? (
            <EmptyState icon={<Search className="size-5" />} title="No matches" description={`Nothing matches “${q}”.`} />
          ) : (
            <EmptyState
              icon={<Package className="size-5" />}
              title="No solutions yet"
              description="Add the products, services and past projects you already have. They stay private to your account."
              action={<Button variant="primary" icon={<Plus className="size-4" />} onClick={() => setEditing("new")}>Add your first solution</Button>}
            />
          )}
        </Panel>
      ) : (
        <ul className={list.isFetching ? "grid gap-4 opacity-70 transition-opacity sm:grid-cols-2 lg:grid-cols-3" : "grid gap-4 transition-opacity sm:grid-cols-2 lg:grid-cols-3"}>
          <AnimatePresence initial={false}>
            {solutions.map((s) => (
              <SolutionCard key={s.id} solution={s} showOwner={showOwner} onEdit={() => setEditing(s)} onDelete={() => setDeleting(s)} />
            ))}
          </AnimatePresence>
        </ul>
      )}

      <Sheet
        open={editing !== null}
        onOpenChange={(open) => !open && setEditing(null)}
        title={editing === "new" ? "Add a solution" : "Edit solution"}
        description="Only you can see this."
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
            <Button variant="primary" type="submit" form="solution-form">{editing === "new" ? "Add solution" : "Save changes"}</Button>
          </div>
        }
      >
        {editing !== null && <SolutionForm key={editing === "new" ? "new" : editing.id} solution={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
      </Sheet>

      <Sheet
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title="Delete this solution?"
        description={deleting ? `“${deleting.name}” will be removed for good.` : undefined}
        footer={
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setDeleting(null)}>Keep it</Button>
            <Button variant="primary" loading={remove.isPending} onClick={() => deleting && remove.mutate(deleting)}>Delete</Button>
          </div>
        }
      >
        {deleting?.owner_email && !deleting.mine && <p className="px-5 py-4 text-small text-ink-2">This belongs to {deleting.owner_email}. They won't be able to get it back.</p>}
      </Sheet>
    </div>
  );
}
