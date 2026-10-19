import * as Dialog from "@radix-ui/react-dialog";
import { useQuery } from "@tanstack/react-query";
import { Command } from "cmdk";
import { CornerDownLeft, FileText, Layers, Monitor, Moon, Sun } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useNavigate } from "react-router-dom";

import { useProfile } from "@/hooks/useProfile";
import { useTheme } from "@/hooks/useTheme";
import { api } from "@/lib/api";
import { fmtRelative } from "@/lib/format";
import { spring } from "@/lib/motion";
import { NAV } from "./AppShell";

const item =
  "flex h-10 cursor-pointer items-center gap-3 rounded-control px-3 text-body text-ink-2 aria-selected:bg-wash-strong aria-selected:text-ink";

export function CommandPalette({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate();
  const { profiles, setName, name } = useProfile();
  const { preference, setPreference } = useTheme();
  const runs = useQuery({ queryKey: ["runs", "palette"], queryFn: () => api.runs(8, "proposal_generation"), enabled: open });
  const go = (to: string) => {
    onOpenChange(false);
    navigate(to);
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild forceMount>
              <motion.div className="fixed inset-0 z-50 bg-black/45" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.15 }} />
            </Dialog.Overlay>
            <Dialog.Content asChild forceMount aria-describedby={undefined}>
              <motion.div
                initial={{ opacity: 0, scale: 0.96, y: -8 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.98, transition: { duration: 0.12 } }}
                transition={spring.snappy}
                className="fixed inset-x-0 top-[14vh] z-50 mx-auto w-[min(600px,calc(100vw-2rem))] overflow-hidden rounded-sheet border border-line bg-overlay/95 shadow-float backdrop-blur-xl"
              >
                <Dialog.Title className="sr-only">Search and jump</Dialog.Title>
                <Command loop>
                  <Command.Input
                    autoFocus
                    placeholder="Search pages, proposals, and actions"
                    className="h-13 w-full border-b border-line bg-transparent px-4 text-lead text-ink outline-none placeholder:text-ink-3"
                  />
                  <Command.List className="max-h-[52vh] overflow-y-auto p-2">
                    <Command.Empty className="px-3 py-6 text-small text-ink-3">No matches. Try a client name or a page.</Command.Empty>
                    <Command.Group heading="Go to" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-caption [&_[cmdk-group-heading]]:text-ink-3">
                      {NAV.flatMap((g) => g.items).map((nav) => (
                        <Command.Item key={nav.to} value={`go ${nav.label}`} onSelect={() => go(nav.to)} className={item}>
                          <span className="text-ink-3">{nav.icon}</span>
                          {nav.label}
                          <CornerDownLeft className="ml-auto size-3.5 text-ink-3 opacity-0 [[aria-selected=true]_&]:opacity-100" />
                        </Command.Item>
                      ))}
                      <Command.Item value="go usage tokens cost" onSelect={() => go("/usage")} className={item}>
                        <span className="w-[18px]" />Usage
                      </Command.Item>
                      <Command.Item value="go settings api key" onSelect={() => go("/settings")} className={item}>
                        <span className="w-[18px]" />Settings
                      </Command.Item>
                    </Command.Group>
                    {(runs.data?.runs.length ?? 0) > 0 && (
                      <Command.Group heading="Recent proposals" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-caption [&_[cmdk-group-heading]]:text-ink-3">
                        {runs.data!.runs.map((run) => (
                          <Command.Item
                            key={run.workflow_id}
                            value={`proposal ${run.client_name} ${run.title} ${run.workflow_id}`}
                            onSelect={() => go(`/proposals/${run.workflow_id}`)}
                            className={item}
                          >
                            <FileText className="size-[18px] text-ink-3" />
                            <span className="truncate">{run.title || "Untitled proposal"}</span>
                            <span className="truncate text-small text-ink-3">{run.client_name}</span>
                            <span className="ml-auto shrink-0 text-caption text-ink-3">{fmtRelative(run.created_at)}</span>
                          </Command.Item>
                        ))}
                      </Command.Group>
                    )}
                    <Command.Group heading="Appearance" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-caption [&_[cmdk-group-heading]]:text-ink-3">
                      {([["light", "Light theme", Sun], ["dark", "Dark theme", Moon], ["system", "Match system theme", Monitor]] as const).map(([value, label, Icon]) => (
                        <Command.Item
                          key={value}
                          value={`theme appearance ${label}`}
                          onSelect={() => {
                            onOpenChange(false);
                            setPreference(value);
                          }}
                          className={item}
                        >
                          <Icon className="size-[18px] text-ink-3" />
                          {label}
                          {preference === value && <span className="ml-auto text-caption text-ion">Active</span>}
                        </Command.Item>
                      ))}
                    </Command.Group>
                    {profiles.length > 1 && (
                      <Command.Group heading="Switch profile" className="[&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-caption [&_[cmdk-group-heading]]:text-ink-3">
                        {profiles.map((p) => (
                          <Command.Item
                            key={p.name}
                            value={`profile ${p.display_name}`}
                            onSelect={() => {
                              setName(p.name);
                              onOpenChange(false);
                            }}
                            className={item}
                          >
                            <Layers className="size-[18px] text-ink-3" />
                            {p.display_name}
                            {p.name === name && <span className="ml-auto text-caption text-ion">Active</span>}
                          </Command.Item>
                        ))}
                      </Command.Group>
                    )}
                  </Command.List>
                </Command>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
}
