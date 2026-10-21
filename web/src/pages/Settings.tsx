import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, XCircle } from "lucide-react";
import { useState } from "react";

import { useToast } from "@/components/Toast";
import { TwoStepPanel } from "@/components/TwoStepPanel";
import { Button, Field, PageHeader, Panel, PanelHeader, Segmented, StatusTag, TextInput } from "@/components/ui";
import { useProfile } from "@/hooks/useProfile";
import { useReadiness } from "@/hooks/useReadiness";
import { useTheme } from "@/hooks/useTheme";
import { getApiKey, setApiKey } from "@/lib/api";
import { titleCase } from "@/lib/format";

function Check({ ok, label, detail }: { ok: boolean | undefined; label: string; detail?: string }) {
  return (
    <li className="flex items-start gap-3 border-b border-line py-3 last:border-0">
      {ok === undefined ? <CircleDashed className="mt-0.5 size-4 text-ink-3" /> : ok ? <CheckCircle2 className="mt-0.5 size-4 text-good" /> : <XCircle className="mt-0.5 size-4 text-bad" />}
      <div>
        <p className="text-small text-ink">{label}</p>
        {detail && <p className="text-caption text-ink-3">{detail}</p>}
      </div>
    </li>
  );
}

export default function Settings() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const { profile, profiles, name, setName } = useProfile();
  const readiness = useReadiness();
  const { preference, setPreference } = useTheme();
  const [key, setKey] = useState(getApiKey());
  const checks = readiness.data?.checks;

  return (
    <div className="mx-auto max-w-[980px] px-4 py-8 sm:px-8">
      <PageHeader title="Settings" />
      <div className="flex flex-col gap-6">
        <Panel>
          <PanelHeader title="Appearance" description="Saved in this browser. Match system follows your computer's light or dark setting." />
          <div className="p-5">
            <Segmented
              label="Appearance"
              value={preference}
              onChange={(v) => setPreference(v)}
              options={[{ value: "dark", label: "Dark" }, { value: "light", label: "Light" }, { value: "system", label: "Match system" }]}
            />
          </div>
        </Panel>
        <TwoStepPanel />
        <Panel>
          <PanelHeader title="Access" description="Needed only when the server sets RFP_API_KEYS. Saved in this browser." />
          <form
            className="flex flex-wrap items-end gap-3 p-5"
            onSubmit={(e) => {
              e.preventDefault();
              setApiKey(key.trim());
              queryClient.invalidateQueries();
              toast({ tone: "good", title: key.trim() ? "API key saved" : "API key removed" });
            }}
          >
            <div className="min-w-64 flex-1">
              <Field label="API key" htmlFor="api-key">
                <TextInput id="api-key" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} placeholder="Paste the key your admin gave you" />
              </Field>
            </div>
            <Button type="submit" variant="primary">Save key</Button>
          </form>
        </Panel>

        <Panel>
          <PanelHeader title="Domain profile" description="Who the proposals are written for and what the agents know about your offerings. Edit the YAML in configs/domain_profiles." />
          <div className="flex flex-col gap-5 p-5">
            <div className="flex flex-wrap gap-2">
              {profiles.map((p) => (
                <Button key={p.name} size="sm" variant={p.name === name ? "primary" : "secondary"} onClick={() => setName(p.name)}>{p.display_name}</Button>
              ))}
            </div>
            {profile && (
              <dl className="grid gap-5 text-small md:grid-cols-2">
                <div>
                  <dt className="text-ink-3">Organization</dt>
                  <dd className="mt-0.5 text-ink">{profile.organization.name}</dd>
                  {profile.organization.description && <dd className="text-ink-2">{profile.organization.description}</dd>}
                </div>
                <div>
                  <dt className="text-ink-3">Default sections</dt>
                  <dd className="mt-0.5 text-ink">{profile.default_sections.map((k) => profile.sections.find((s) => s.key === k)?.title ?? k).join(", ")}</dd>
                </div>
                <div className="md:col-span-2">
                  <dt className="text-ink-3">Offering catalog</dt>
                  {profile.offerings.length ? (
                    <dd className="mt-1.5 grid gap-2 sm:grid-cols-2">
                      {profile.offerings.map((o) => (
                        <div key={o.code} className="rounded-control border border-line p-3">
                          <p className="font-semibold text-ink">{o.name}</p>
                          <p className="text-ink-3">{o.capabilities.join(", ")}</p>
                        </div>
                      ))}
                    </dd>
                  ) : (
                    <dd className="mt-0.5 text-ink-2">No catalog. Capabilities are inferred from each RFP; add `offerings` to the profile to match against yours.</dd>
                  )}
                </div>
              </dl>
            )}
          </div>
        </Panel>

        {profile?.llm.routes && (
          <Panel>
            <PanelHeader title="Models" description="Which model each agent uses. Change with RFP_LLM_ROUTE_OVERRIDES." />
            <div className="overflow-x-auto px-5 py-3">
              <table className="w-full min-w-[460px] text-small">
                <thead><tr className="text-left text-ink-3"><th className="py-1.5 font-normal">Agent</th><th className="font-normal">Tier</th><th className="font-normal">Model</th></tr></thead>
                <tbody>
                  {Object.entries(profile.llm.routes).map(([agent, tier]) => (
                    <tr key={agent} className="border-t border-line">
                      <td className="py-2 text-ink">{titleCase(agent)}</td>
                      <td><StatusTag tone={tier === "fast" ? "neutral" : "ion"}>{tier === "fast" ? "Fast" : "Frontier"}</StatusTag></td>
                      <td className="text-ink-2">{(tier === "fast" ? profile.llm.fast_model : profile.llm.frontier_model) ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
        )}

        <Panel>
          <PanelHeader title="System status" />
          <ul className="px-5 py-1">
            <Check ok={checks?.llm.configured} label="Groq API key" detail={checks ? (checks.llm.configured ? `Organization ${checks.llm.organization_id ?? "from the key"}` : "Missing on the server: drafts are outlines only") : undefined} />
            <Check ok={checks?.database.ok} label="Database" detail={checks?.database.ok ? `Migration ${checks.database.migration}` : checks?.database.error} />
            <Check ok={checks?.redis.ok} label="Shared cache and rate limits" detail={checks ? (checks.redis.ok ? "Redis" : "Redis offline, using in-process fallback") : undefined} />
            <Check ok={checks?.profile.ok} label="Default profile" detail={checks?.profile.name} />
          </ul>
        </Panel>
      </div>
    </div>
  );
}
