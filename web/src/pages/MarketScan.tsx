import { useMutation } from "@tanstack/react-query";
import { ExternalLink, Plus, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";

import { TokenReport } from "@/components/TokenReport";
import { Button, Chip, EmptyState, Field, Notice, PageHeader, Panel, PanelHeader, Segmented, Select, TextInput } from "@/components/ui";
import { useProfile } from "@/hooks/useProfile";
import { api } from "@/lib/api";
import { spring } from "@/lib/motion";

export default function MarketScan() {
  const { name: profileName, profile } = useProfile();
  const [offerings, setOfferings] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [industry, setIndustry] = useState("");
  const [summary, setSummary] = useState("");
  const [max, setMax] = useState(8);
  const scan = useMutation({
    mutationFn: (list: string[]) =>
      api.marketResearch({ offerings: list, industry: industry || undefined, requirement_summary: summary || undefined, max_companies: max, profile: profileName }),
  });
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!scan.isPending) return;
    const started = Date.now();
    setElapsed(0);
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(id);
  }, [scan.isPending]);

  // A typed offering counts even if Enter was never pressed.
  const run = () => {
    const pending = draft.trim();
    const list = pending && !offerings.includes(pending) ? [...offerings, pending] : offerings;
    if (!list.length) return;
    setOfferings(list);
    setDraft("");
    scan.mutate(list);
  };
  const suggestions = [...(profile?.market_research.default_offerings ?? []), ...(profile?.offerings.map((o) => o.name) ?? [])]
    .filter((s, i, all) => all.indexOf(s) === i && !offerings.includes(s));

  const add = (value: string) => {
    const v = value.trim();
    if (v && !offerings.includes(v)) setOfferings((o) => [...o, v]);
    setDraft("");
  };

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-8 sm:px-8">
      <PageHeader title="Market scan" description="Find vendors that offer what the buyer asked for: likely competitors, partners, or subcontractors." />
      <Panel className="p-5">
        <div className="flex flex-col gap-5">
          <Field label="Offerings to look for" htmlFor="offering" hint="Type one and press Enter to add another. Two or more also finds vendors that bundle them.">
            <div className="flex min-h-11 flex-wrap items-center gap-1.5 rounded-control border border-line-strong bg-panel px-2 py-1.5 focus-within:border-ion focus-within:shadow-[0_0_0_3px_var(--color-ion-soft)]">
              <AnimatePresence initial={false}>
                {offerings.map((o) => (
                  <motion.span
                    key={o}
                    layout
                    initial={{ opacity: 0, scale: 0.85 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.85 }}
                    transition={spring.land}
                    className="inline-flex h-7 items-center gap-1 rounded-full bg-ion-soft pl-3 pr-1 text-small text-ink"
                  >
                    {o}
                    <button type="button" aria-label={`Remove ${o}`} onClick={() => setOfferings((x) => x.filter((y) => y !== o))} className="flex size-5 items-center justify-center rounded-full hover:bg-wash-strong">
                      <X className="size-3" />
                    </button>
                  </motion.span>
                ))}
              </AnimatePresence>
              <input
                id="offering"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={() => draft.trim() && add(draft)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === ",") { e.preventDefault(); add(draft); }
                  if (e.key === "Backspace" && !draft && offerings.length) setOfferings((o) => o.slice(0, -1));
                }}
                placeholder={offerings.length ? "" : "e.g. field service management software"}
                className="h-7 min-w-40 flex-1 bg-transparent px-1 text-body text-ink outline-none placeholder:text-ink-3"
              />
            </div>
          </Field>
          {suggestions.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {suggestions.map((s) => <Chip key={s} onClick={() => add(s)}><Plus className="size-3.5" />{s}</Chip>)}
            </div>
          )}
          <div className="grid gap-4 md:grid-cols-[1fr_1fr_auto]">
            <Field label="Industry" htmlFor="industry">
              <Select id="industry" value={industry} onChange={(e) => setIndustry(e.target.value)}>
                <option value="">Any industry</option>
                {profile?.industries.map((i) => <option key={i}>{i}</option>)}
              </Select>
            </Field>
            <Field label="Use case" htmlFor="summary" hint="Optional, sharpens the search">
              <TextInput id="summary" value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="e.g. hospital patient scheduling" />
            </Field>
            <Field label="Companies">
              <Segmented label="Companies" value={max} onChange={setMax} options={[{ value: 5, label: "5" }, { value: 8, label: "8" }, { value: 12, label: "12" }]} />
            </Field>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <Button variant="primary" size="lg" loading={scan.isPending} disabled={!offerings.length && !draft.trim()} onClick={run}>
              {scan.isPending ? "Scanning" : "Scan the market"}
            </Button>
            {scan.isPending && (
              <p className="text-small text-ink-2" role="status">
                Searching the web and reading each company's site: <span className="tabular text-ink">{elapsed}s</span>. This usually takes 30 to 90 seconds.
              </p>
            )}
          </div>
        </div>
      </Panel>

      <div className="mt-6 flex flex-col gap-6">
        {scan.isError && <Notice tone="bad" title="The scan did not finish">{(scan.error as Error).message}</Notice>}
        {scan.data && (
          <>
            {scan.data.warnings?.map((w) => (
              <Notice key={w} title="Heads up">
                {w.startsWith("Degraded mode") ? "Without a Groq key the scan cannot check that each company actually sells this, or read prices and leaders from their sites. Results are search matches only." : w}
              </Notice>
            ))}
            <Panel>
              <PanelHeader title="Vendors" description={`${scan.data.rows.length} companies for ${scan.data.offerings.join(", ")}`} />
              {scan.data.rows.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[760px] text-small">
                    <thead>
                      <tr className="text-left text-ink-3">
                        {["Company", "What they do", "Price", "Rating", "Leader", "Years", ""].map((h) => <th key={h} className="px-5 py-2.5 font-normal">{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {scan.data.rows.map((r) => (
                        <tr key={r.Domain} className="border-t border-line text-ink-2">
                          <td className="px-5 py-3"><span className="font-semibold text-ink">{r.Company}</span><span className="block text-caption text-ink-3">{r.Domain}</span></td>
                          <td className="max-w-[28rem] px-5 py-3"><span className="line-clamp-2">{r.About}</span><span className="block text-caption text-ink-3">Matches {r["Matched solutions"]}</span></td>
                          <td className="tabular px-5">{r.Price}</td>
                          <td className="tabular px-5">{r.Review}</td>
                          <td className="px-5">{r.Contact}</td>
                          <td className="tabular px-5">{r["Age (years)"]}</td>
                          <td className="px-5">
                            <a href={`https://${r.Domain}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ion-strong hover:underline">
                              Site <ExternalLink className="size-3" />
                            </a>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyState icon={<X className="size-5" />} title="No vendors found" description="Try broader offerings or remove the industry filter. Free web search is rate-limited, so retrying in a minute can help." />
              )}
            </Panel>
            <Panel>
              <PanelHeader title="Token usage" />
              <TokenReport usage={scan.data.token_usage} />
            </Panel>
          </>
        )}
      </div>
    </div>
  );
}
