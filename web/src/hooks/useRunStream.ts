import { useCallback, useRef, useState } from "react";

import { ApiError } from "@/lib/api";
import { streamPost } from "@/lib/sse";
import type { TraceEntry } from "@/lib/types";

export type StepStatus = "pending" | "running" | "done" | "failed";

export interface RunStep {
  tool: string;
  status: StepStatus;
  summary?: string;
  tokens?: number;
}

export interface LiveSection {
  key: string;
  title: string;
  status: "queued" | "writing" | "done" | "failed";
  preview?: string;
  tokens?: number;
  wordCount?: number;
  cacheHit?: boolean;
  mode?: string;
  error?: string;
}

export interface RunState<T> {
  phase: "idle" | "running" | "done" | "error";
  steps: RunStep[];
  sections: LiveSection[];
  decisions: TraceEntry[];
  tokens: number;
  result?: T;
  error?: ApiError;
  startedAt?: number;
}

const initial = <T,>(): RunState<T> => ({ phase: "idle", steps: [], sections: [], decisions: [], tokens: 0 });

function startNext(steps: RunStep[]): RunStep[] {
  const next = steps.findIndex((s) => s.status === "pending");
  if (next < 0 || steps.some((s) => s.status === "running")) return steps;
  return steps.map((s, i) => (i === next ? { ...s, status: "running" } : s));
}

/** Drives a streamed workflow and turns its events into plan steps and arriving sections. */
export function useRunStream<T>() {
  const [state, setState] = useState<RunState<T>>(initial);
  const abort = useRef<AbortController | null>(null);

  const reset = useCallback(() => {
    abort.current?.abort();
    setState(initial());
  }, []);

  const start = useCallback(async (path: string, body: unknown): Promise<T | undefined> => {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;
    setState({ ...initial<T>(), phase: "running", startedAt: Date.now() });
    let final: T | undefined;
    try {
      await streamPost(
        path,
        body,
        ({ event, data }) => {
          if (event === "result") final = data as T;
          setState((prev) => {
            if (event === "trace") {
              const entry = data.entry as TraceEntry;
              if (entry.type === "make_plan" || entry.type === "replan") {
                const done = new Set(prev.steps.filter((s) => s.status === "done").map((s) => s.tool));
                const steps = (entry.plan ?? [])
                  .filter((t) => t !== "done")
                  .map<RunStep>((tool) => ({ tool, status: done.has(tool) ? "done" : "pending" }));
                return { ...prev, steps: startNext(steps), decisions: [...prev.decisions, entry] };
              }
              if (entry.type === "tool_call" && entry.tool) {
                const steps = prev.steps.map((s) =>
                  s.tool === entry.tool
                    ? { ...s, status: (entry.ok ? "done" : "failed") as StepStatus, summary: entry.summary, tokens: entry.usage?.total_tokens }
                    : s,
                );
                return { ...prev, steps: startNext(steps), tokens: prev.tokens + (entry.usage?.total_tokens ?? 0) };
              }
              return { ...prev, decisions: [...prev.decisions, entry] };
            }
            if (event === "sections_planned") {
              const planned = (data.sections as { section_key: string; title: string }[]) ?? [];
              return { ...prev, sections: planned.map((s) => ({ key: s.section_key, title: s.title, status: "queued" })) };
            }
            if (event === "section_started") {
              return {
                ...prev,
                sections: prev.sections.map((s) => (s.key === data.section_key ? { ...s, status: "writing" } : s)),
              };
            }
            if (event === "section_done") {
              return {
                ...prev,
                sections: prev.sections.map((s) =>
                  s.key === data.section_key
                    ? {
                        ...s,
                        status: data.ok ? "done" : "failed",
                        preview: data.preview as string | undefined,
                        tokens: data.tokens as number | undefined,
                        wordCount: data.word_count as number | undefined,
                        cacheHit: Boolean(data.cache_hit),
                        mode: data.generation_mode as string | undefined,
                        error: data.error as string | undefined,
                      }
                    : s,
                ),
              };
            }
            if (event === "result") {
              return {
                ...prev,
                phase: "done",
                result: data as T,
                steps: prev.steps.map((s) => (s.status === "running" ? { ...s, status: "done" } : s)),
              };
            }
            if (event === "error") {
              const err = new ApiError(
                String(data.message ?? "The run failed."),
                Number(data.status ?? 500),
                String(data.code ?? "error"),
                (data.retry_after as number | null) ?? null,
              );
              return { ...prev, phase: "error", error: err };
            }
            return prev;
          });
        },
        controller.signal,
      );
    } catch (err) {
      if ((err as Error).name === "AbortError") return undefined;
      const apiErr = err instanceof ApiError ? err : new ApiError(String((err as Error).message), 0);
      setState((prev) => ({ ...prev, phase: "error", error: apiErr }));
      return undefined;
    }
    return final;
  }, []);

  return { state, start, reset };
}
