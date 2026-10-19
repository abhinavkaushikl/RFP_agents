import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";

export type Connection = "ready" | "degraded" | "offline" | "checking";

/** Polls /health/ready so the toolbar can show whether drafting will use the real models. */
export function useReadiness() {
  const query = useQuery({ queryKey: ["ready"], queryFn: api.ready, refetchInterval: 30_000, retry: 0 });
  let state: Connection = "checking";
  if (query.isError) state = "offline";
  else if (query.data) {
    const { database, llm } = query.data.checks;
    state = database.ok && llm.configured ? "ready" : database.ok ? "degraded" : "offline";
  }
  return { ...query, state };
}
