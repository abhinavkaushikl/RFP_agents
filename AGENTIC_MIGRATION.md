# Agentic Migration

This document records what changed when the platform moved from a hard-coded
sequential pipeline to an end-to-end agentic runtime.

## Why

Previously, the orchestrator decided the entire workflow in code: which agent
to call, in what order, with what arguments, and when to stop. The five
endpoints each had their own bespoke `run_*_workflow` method with a fixed
sequence baked in. That worked, but it wasn't agentic — the LLM was a
text-generation backend, not a decision-maker.

The goal of this change: every routing, planning, and termination decision
is made by the supervisor LLM at runtime. Existing agents remain the
underlying capabilities; they're just exposed as **tools** the supervisor can
choose from.

## Architecture: Plan-Execute with replanning

The supervisor produces an upfront plan, the runner executes each step in
order, and the supervisor is consulted again if a step fails.

```
                    ┌────────────────────────┐
   payload ──────▶  │  pick_intent (LLM)    │  ──▶  intent
                    └────────────────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │   make_plan (LLM)      │  ──▶  [step1, step2, …, done]
                    └────────────────────────┘
                                │
                    ┌───────────┴────────────┐
                    ▼                        ▼
             pop step from plan    ┌─ on tool failure ─┐
                    │              │                   │
                    ▼              ▼                   ▼
             execute tool     decide_next (LLM)    abort/budget
                    │         replan / continue        │
                    ▼              │                   │
             store result    ◀─────┘                   │
                    │                                  │
                    └──────────────────────────────────┘
                                │
                                ▼
                    ┌────────────────────────┐
                    │  decide_done (LLM)     │  ──▶  final summary
                    └────────────────────────┘
```

Why Plan-Execute and not pure ReAct: local Mistral 7B is unreliable at
multi-hop tool selection. ReAct-style (one LLM call per hop) compounds error
rates fast. Plan-Execute makes ~3 LLM decisions per workflow (intent + plan
+ done) regardless of how many tools run, which keeps the system practical
on a slow local model.

## What changed

### New files (the agentic runtime)

| File | Role |
|------|------|
| `src/app/agentic/__init__.py` | Public exports: `WorkflowState`, `build_tool_registry`, `run_agentic` |
| `src/app/agentic/state.py` | `WorkflowState` dataclass — single mutable container threaded through every phase. Holds `intent`, `plan`, `results`, `trace`, budget counters, and helpers like `get_result(tool_name, key)` |
| `src/app/agentic/tools.py` | Wraps each existing agent as a `Tool(name, description, args_schema, fn)`. Tool fns auto-fill missing args from `state.results` so supervisor plans can be sparse. Also defines the compound `generate_proposal_sections` tool (see "Pragmatic compromise" below) |
| `src/app/agentic/supervisor.py` | The four LLM decision functions: `pick_intent`, `make_plan`, `decide_next`, `decide_done`. Each runs through `_llm_json_call`, which retries once on JSON parse failure and falls back to a heuristic if Mistral can't produce valid JSON |
| `src/app/agentic/runner.py` | The execute loop. ~70 LOC. Calls supervisor for intent + plan, pops steps, dispatches via tool registry, asks supervisor what to do on failure, asks supervisor to confirm done at the end |

### Modified files

#### `src/app/orchestration/orchestrator.py` — fully replaced

Before: ~190 lines of hard-coded sequences (`run_proposal_workflow` did
`structure → planner → solution_comparison → loop(retrieve → generate → validate)
→ scoring`; each other workflow had its own bespoke chain).

After: ~110 lines. The class holds an `agent_registry`, a `tool_registry`,
and an `LLMService`. Every public method (`run_proposal_workflow`,
`run_revision_workflow`, `run_document_match_workflow`,
`run_market_research_workflow`, `run_intent_detection_workflow`) is now a
thin shim that:

1. Calls `run_agentic(payload, intent_hint=…, agents=…, tools=…, llm=…)`
   — the same single entry point for every endpoint.
2. Reshapes the resulting `WorkflowState` into the response dict the
   matching router expects.

The intent hint is a soft bias for the supervisor, not a guarantee — the
supervisor can override it (e.g., if the user hits `/workflow-runs` but
their payload obviously matches `intent_detection`, the LLM picks
`intent_detection`).

### Unchanged

- `src/app/agents/*.py` — every existing agent (`RequestStructuringAgent`,
  `RetrievalAgent`, `GenerationAgent`, `RevisionAgent`, `ValidationAgent`,
  `ScoringAgent`, `SolutionComparisonAgent`, `MarketResearchAgent`,
  `IntentDetectionAgent`, `PlannerAgent`) is untouched. They're now exposed
  through the tool registry instead of called directly.
- `src/app/services/*` — no changes.
- `src/app/api/routers/*` — no changes. The agentic shift is invisible to the
  HTTP layer beyond a new `agent_trace` field appearing in responses.
- `src/app/schemas/api.py` — response models unchanged; `agent_trace` is
  additive and tolerated by Pydantic.
- UI pages — no changes.

## How the supervisor "decides"

Every supervisor function in `supervisor.py` follows the same pattern:

1. **Build a tight prompt** with current state context and the JSON schema
   it must produce.
2. **Call `_llm_json_call`** which:
   - Runs `LLMService.generate(temperature=0.0, max_tokens=…)`.
   - Parses the response with a tolerant JSON extractor (handles ` ```json `
     fences, finds the outermost `{…}` or `[…]`).
   - On parse failure, **re-prompts once** with the malformed output and
     "Return ONLY the JSON object."
3. **Validate the parsed structure**:
   - `pick_intent`: must be one of the five known intents.
   - `make_plan`: drops unknown tool names, caps at 10 steps, ensures the
     plan ends with `done`.
   - `decide_next`: must be `replan` / `continue` / `abort`.
   - `decide_done`: must contain a boolean `done` field.
4. **Heuristic fallback** if validation fails:
   - `pick_intent`: scan payload keys (`transcript_text` → `intent_detection`,
     `offerings` only → `market_research`, etc.).
   - `make_plan`: hard-coded plan template per intent.
   - `decide_next`: continue (skip the failed step).
   - `decide_done`: assume done.

The fallbacks are **safety nets, not the deterministic flow**. When the
local LLM produces valid JSON (the common case), every decision is
agentic. When it doesn't, the system stays alive instead of returning 500.

## Tools the supervisor can pick

Defined in `src/app/agentic/tools.py`:

| Tool | Underlying agent | Notes |
|------|------------------|-------|
| `structure_request` | `RequestStructuringAgent` | Run first for proposal-related intents |
| `compare_solutions` | `SolutionComparisonAgent` | Reads from `structure_request` output |
| `retrieve_evidence` | `RetrievalAgent` | pgvector RAG for one section |
| `generate_section` | `GenerationAgent` | Mistral draft for one section |
| `validate_section` | `ValidationAgent` | Requirement coverage check |
| `generate_proposal_sections` | (compound) | Loops retrieve+generate+validate per section |
| `revise_section` | `RevisionAgent` | Mistral revision pass |
| `score_proposal` | `ScoringAgent` | Auto-pulls draft text from prior sections |
| `market_research` | `MarketResearchAgent` | DDG + scrape + Mistral extraction |
| `detect_intent_fields` | `IntentDetectionAgent` | Transcript field extraction |
| `done` | (terminator) | Always last in any plan |

### Pragmatic compromise: the compound tool

`generate_proposal_sections` runs `retrieve → generate → validate` for every
section *internally* in one supervisor step. Without it, a 5-section
proposal would be ~20 supervisor decisions, which on local Mistral is
unworkably slow and unreliable.

This is the one place the system is less than fully fine-grained agentic.
The supervisor still owns the high-level decisions (which intent, which
plan, replan-or-not, done-or-not) — it just doesn't pick each section's
sub-steps individually. Splitting this back out is a future optimization
once we move to a more capable model (Qwen 2.5 14B / Qwen 3).

## Observability

Every state transition is appended to `state.trace`. Trace entry types:

- `pick_intent` — `{intent, hint}`
- `make_plan` — `{plan: [tool names]}`
- `tool_call` — `{tool, ok, summary, error}`
- `tool_error` — for unknown tool names
- `decide_next` — `{action, reason}`
- `replan` — `{plan: [tool names]}`
- `decide_done` — `{done, summary}`
- `done` — `{reason}`
- `budget_exhausted`

The full trace is returned on every endpoint response under `agent_trace`,
so the Streamlit UI (or any client) can render an "agent thinking" view
without extra plumbing.

## Limits and budgets

- `state.budget = 12` — max tool calls per workflow. After this the runner
  bails to `decide_done`.
- `state.max_replans = 2` — max times the supervisor can ask for a fresh
  plan after a failure.
- `LLMServiceError` is caught inside tool wrappers and inside
  `_llm_json_call`, so neither tool failures nor supervisor LLM failures
  raise out of `run_agentic`.

## Verification

After the migration, every existing endpoint still returns the same
top-level shape (with `agent_trace` added):

| Endpoint | Intent picked | Tools typically run |
|----------|--------------|---------------------|
| `POST /api/workflow-runs` | `proposal_generation` | `structure_request → compare_solutions → generate_proposal_sections → score_proposal` |
| `POST /api/generated-sections/{id}/revise` | `revision` | `retrieve_evidence → revise_section` |
| `POST /api/document-match-runs` | `document_match` | `structure_request → retrieve_evidence → compare_solutions → score_proposal` |
| `POST /api/market-research-runs` | `market_research` | `market_research` |
| `POST /api/intent-detection-runs` | `intent_detection` | `detect_intent_fields` |

To confirm a particular workflow is genuinely agentic and not silently
falling back to the heuristic plan, look at the `agent_trace` field in the
response — the `make_plan` entry shows whether the LLM produced the plan
(matches what was executed) or the heuristic fired (matches the templates
in `_fallback_plan`).

## Migration to Qwen later

The agentic layer assumes nothing about the LLM beyond the `LLMService`
interface (`generate(prompt, system, temperature, max_tokens) → str`).
Switching to Qwen 2.5 / Qwen 3 is a config change in `app.core.config`
(`llm_model`) plus a fresh `ollama pull`. The supervisor prompts may need
light retuning since Qwen prefers slightly more direct phrasing, but no
structural change is required.

If different roles want different models (e.g., Qwen 14B for the supervisor
and Mistral 7B for section drafting), `LLMService` would be split into a
`SupervisorLLM` and `GenerationLLM`. That's not done yet — it can wait
until the model swap is on the table.
