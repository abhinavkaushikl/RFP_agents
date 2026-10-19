# RFP Proposal Platform

A multi-agent platform that drafts, revises, and scores RFP responses for **any industry**. A
supervisor model plans each run and calls specialized agents: request structuring, offering
match, retrieval over your past proposals, section writing, validation, scoring, and sales
conversation analysis.

- **Models:** Groq. `openai/gpt-oss-120b` handles writing and deep analysis; `openai/gpt-oss-20b`
  handles routing, planning, and light extraction such as intent detection.
- **Domain-agnostic:** industries, offerings, proposal sections, sales categories, and scoring
  weights live in YAML *domain profiles*, not in code.
- **Cost controls:** Groq prompt caching (static-first prompts), a Redis section cache, per-model
  rate limiting, and a token and cost report on every response.
- **Storage:** Postgres + pgvector for the knowledge base, runs, section revisions, and usage events.

## Architecture

```
Web app (React) ──HTTP/SSE──▶ FastAPI ──▶ Orchestrator ──▶ run_agentic()
                                                     │
                       supervisor (fast model): pick_intent → make_plan → decide_next → decide_done
                                                     │
                       tools → agents ──▶ LLMService ──▶ Groq
                                 │            ├─ routing: agent → tier → model
                                 │            ├─ Redis response/section cache
                                 │            ├─ RPM/TPM limiter (Redis, adaptive to Groq headers)
                                 │            └─ usage records → token report + llm_usage_events
                                 └──▶ pgvector retrieval, coverage analyzer (MiniLM embeddings)
```

| Agent | Model tier | Does |
|---|---|---|
| supervisor | fast | Intent (locked to the endpoint by default), plan, recovery, completion |
| intent_detection, problem_framing | fast | Opportunity basics and problem framing from a conversation |
| market_research | fast | Company facts from scraped pages |
| request_structuring | frontier | RFP → requirements (with priority and category), criteria, timeline, budget, compliance |
| solution_comparison | frontier | Requirements → your offering catalog (or inferred capabilities) |
| generation, revision | frontier | Section drafting and revision |
| scoring | frontier | Rubric against the evaluation criteria, plus measured components |
| buyer_intelligence, product_fit | frontier | Sales readiness and product fit from a conversation |
| retrieval, validation | none | pgvector search and semantic requirement coverage |

Move an agent between tiers with `RFP_LLM_ROUTE_OVERRIDES='{"product_fit": "fast"}'`.

## Quick start (local)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[ui,dev]"
cp .env.example .env            # set RFP_GROQ_API_KEY (a key from your Groq organization)

createdb proposal_platform      # Postgres 14+ with the pgvector extension available
alembic upgrade head
redis-server &                   # optional but recommended: shared cache and rate limits

python scripts/smoke_groq.py     # checks both models and prompt caching (a few hundred tokens)
PYTHONPATH=src python scripts/load_proposals.py --input data/samples/rfp_records.sample.jsonl --source samples

uvicorn main:app --app-dir src --reload      # API on :8000, docs at /docs

cd web && npm install && npm run dev         # web app on :5173 (proxies /api to :8000)
# or build it once and let the API serve it on :8000:
cd web && npm run build
```

Or run everything with Docker: `cp .env.example .env`, add the key, then `docker compose up --build` and open
http://localhost:8000.

## Web app

`web/` is a React + TypeScript app (Vite, Tailwind, Motion) built for sales and bid teams. FastAPI serves the
production build from `web/dist`, so there is one URL and no CORS setup.

| Screen | For |
|---|---|
| Home | Drop an RFP to start; recent work; the week's usage |
| New proposal | Four-step composer (RFP, client, sections you drag to order, guidance), then a live run: the supervisor's plan and each section landing as its agent finishes, streamed from `POST /api/workflow-runs/stream` |
| Proposal | Outline, the document in a reading face, and an inspector with the score, requirement coverage, the brief, and token usage; revise any section in a side sheet; export PDF or Markdown |
| Deal analysis | Transcript or email in; problem framing, buyer readiness, product fit, next actions out |
| Bid check | Score a response you already wrote against the RFP |
| Market scan | Vendors offering what the buyer asked for |
| Knowledge base | Upload past proposals (PDF, Word, Markdown) and search what the agents will reuse |
| Usage | Tokens, cost, prompt-cache rate, and cache savings by day, section, agent, and model |
| Settings | Appearance, API key, domain profile, model routing, system status |

- **Appearance:** dark by default, plus light and match-system (toolbar, Settings, or ⌘K). The choice is saved
  per browser and applied before first paint; `?theme=light` in a URL sets it too. Switching grows the new theme
  out of the toggle where the browser supports view transitions.
- **Motion:** spring physics on everything you touch: navigation, segmented controls, drag-to-reorder sections,
  sheets you can flick away, toasts you can swipe. Reduced-motion settings are respected.
- **Access:** when the API requires keys, paste one in Settings; it is sent as `X-API-Key`.

The previous Streamlit UI in `ui/` still works (`pip install -e ".[ui]"`, `streamlit run ui/app.py`) and runs in
Docker with `docker compose --profile legacy up`.

## Making it yours: domain profiles

`configs/domain_profiles/default.yaml` is industry-neutral. Create a profile for your company with
`extends: default` and override only what differs. See `example_company.yaml`.

| Key | Used for |
|---|---|
| `organization` | Name, description, differentiators used in every writing prompt |
| `offerings` | Catalog that requirements are matched against; product-fit analysis uses it too |
| `sections` | Section keys, titles, word ranges, guidance, sub-headings, and **aliases** (so "Pricing", "Fees", and `pricing_notes` share one section) |
| `default_sections` | Sections drafted when a request doesn't name any |
| `industries` | Canonical names plus aliases; retrieval filters match aliases too |
| `buyer_intelligence`, `product_fit` | Readiness and fit stages with score bands, gap types, stakeholder categories, capability areas |
| `scoring` | Composite weights and default evaluation criteria |
| `lexicons` | Competitors and compliance frameworks to watch for |

Choose a profile per request (`"profile": "example_company"`), in the UI sidebar, or for the whole
deployment with `RFP_DEFAULT_PROFILE`. Profile edits take effect without a restart and invalidate
cached outputs automatically, because the profile version is part of every prompt.

## Cost and capacity controls

**Groq prompt caching.** Groq caches prompt prefixes automatically on gpt-oss models and bills cached
input at half price. Prompts are laid out static-first:

- **Sections:** `[system: writing rules] [RFP context: identical for every section] [section brief + precedent]`
- **Transcript analysis:** all four agents send the same system message and transcript, with their
  own task last.
- **Supervisor:** the tool catalog and reference plans live in the system message.

The first section of a proposal is generated alone and the rest in parallel, so the shared context
is already cached when they run. `cached_prompt_tokens` and `prompt_cache_rate` appear in every
report.

**Section and response cache (Redis).** A model output is stored under a hash of everything that
determines it (model, messages, parameters, prompt version). Re-running an unchanged proposal
costs zero tokens. Per request, `cache_policy` is `use` (default), `refresh` (regenerate and
overwrite), or `off`. TTLs: `RFP_CACHE_SECTION_TTL_S` (7 days) and `RFP_CACHE_LLM_TTL_S` (1 day).
Without Redis, a per-process LRU is used.

**Rate limiting.**
- *Outbound:* a per-model requests/min and tokens/min limiter (`RFP_LLM_RATE_LIMITS`), shared across
  API workers through Redis. Calls wait up to `RFP_LLM_RATE_LIMIT_MAX_WAIT_S` instead of failing.
  The limiter reads Groq's `x-ratelimit-*` headers and `retry-after`, and pauses a model before the
  provider rejects it. Defaults match Groq's lowest published tier, so raise them to your
  organization's limits.
- *Inbound:* `RFP_API_RATE_LIMIT_PER_MINUTE` per API key or client IP, returning 429 with
  `Retry-After`. If a run is interrupted by a rate limit, retrying is cheap because finished
  sections are cached.

**Token consumption report.** Every workflow response includes `token_usage` (illustrative values):

```json
{
  "totals":     {"model_calls": 9, "cache_hits": 2, "prompt_tokens": 18240, "cached_prompt_tokens": 9216,
                 "completion_tokens": 5120, "reasoning_tokens": 1430, "total_tokens": 23360,
                 "cost_usd": 0.0061, "saved_tokens": 4800, "prompt_cache_rate": 0.505},
  "by_section": [{"section_key": "executive_summary", "total_tokens": 4100, "cost_usd": 0.0011}],
  "by_agent":   [...], "by_model": [...], "by_tool": [...],
  "calls":      [{"agent": "generation", "section_key": "...", "model": "...", "latency_ms": 2100}]
}
```

Each `tool_call` entry in `agent_trace` also carries the tokens and cost that step used. Usage is
stored in `llm_usage_events`; query it with `GET /api/usage/workflows/{id}` and
`GET /api/usage/summary?days=7`, or open the **Token Usage** page in the UI. Costs use Groq list
prices from `RFP_LLM_PRICING` (October 2026); update them if your contract differs.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/workflow-runs` | Draft a proposal: `request_text`, `client_name`, `target_sections`, `profile`, `cache_policy` |
| GET | `/api/workflow-runs/{id}` | A stored run |
| POST | `/api/generated-sections/{id}/revise` | Revise a stored section (`instruction`; `base_text` optional) |
| GET | `/api/generated-sections/{id}/revisions` | Revision history |
| POST | `/api/document-match-runs` | Score an existing proposal against an RFP |
| POST | `/api/intent-detection-runs` | Analyze a sales conversation |
| POST | `/api/market-research-runs` | Find vendors for offerings |
| POST | `/api/historical-proposals/ingest` | Add past proposals as JSON records |
| POST | `/api/historical-proposals/upload` | Add past proposals as PDF, DOCX, Markdown, or text files |
| POST | `/api/documents/extract-text` | Extract text from an uploaded file |
| POST | `/api/retrieval/search` | Semantic search over the knowledge base |
| GET | `/api/usage/workflows/{id}`, `/api/usage/summary` | Token and cost reports |
| GET | `/api/profiles`, `/api/profiles/{name}` | Profiles and model routing (used by the UI) |
| GET | `/api/health`, `/api/health/ready` | Liveness; readiness of database, Redis, Groq configuration, and profile |

Set `RFP_API_KEYS` to require an `X-API-Key` header. Errors share one shape:
`{"error": {"code", "message", "request_id"}}`. A missing Groq key returns 503 `llm_not_configured`,
and exhausted rate limits return 429 with `Retry-After`.

## Ingestion formats

JSON records need only section text; everything else is optional:

```json
{"id": "p-2025-014", "title": "Citizen Services Portal", "client_name": "City of Riverton",
 "industry": "public sector", "solution_type": "digital_platforms",
 "proposal_sections": {"Executive Summary": "...", "Pricing": "..."}}
```

`proposal_sections` (or `sections`) may be an object or a list of `{"title", "content"}`. Section names
and industries are canonicalized through the profile. Re-ingesting the same `id` from the same
source is skipped. Uploaded documents are split on Markdown or Word headings, numbered headings,
and lines that match a profile section title or alias.

## Production checklist

- Create the Groq key in your organization, set `RFP_GROQ_API_KEY`, and run `scripts/smoke_groq.py`.
- Set `RFP_LLM_RATE_LIMITS` to your organization's limits from the Groq console.
- Run Redis and set `RFP_REDIS_REQUIRED=true`, so cache and limits are shared across workers.
- Set `RFP_API_KEYS`, `RFP_CORS_ORIGINS`, `RFP_ENVIRONMENT=production`, and `RFP_LOG_JSON=true`.
- Keep `RFP_LLM_ALLOW_DEGRADED=false`, so failures surface instead of silently returning heuristic output.
- Put the web app behind your SSO or reverse proxy, and set `RFP_API_KEYS` so the API itself is never open.
- Point readiness probes at `/api/health/ready`.

## Tests

```bash
pytest                                     # unit + end-to-end with a fake Groq client and fake Redis
RFP_TEST_DATABASE_URL=postgresql+psycopg://localhost:5432/rfp_test pytest -m postgres   # real pgvector
```

`tests/test_domain_profile.py::test_no_dataset_terms_in_generic_code` fails if terms from the
original telecom/AIOps dataset reappear in the app, UI, or profiles.

## Migrating from the AIOps version

- Run `alembic upgrade head`. Migration `0002` adds `llm_usage_events` and result columns on
  `workflow_runs`. It also deletes the embedding chunks of the junk `source_dataset` section that the
  old importer created.
- Existing proposals keep working. Legacy section keys such as `architecture_diagram`,
  `tone_specific_summary`, and `roi_summary` are aliases in the default profile, so retrieval still
  finds them.
- Ollama, Celery, and LangChain are no longer used. The local LoRA fine-tuning pipeline in
  `src/rfp_mistral` is optional: install with `pip install -e ".[training]"`. Its importer now works
  with any corpus (`python -m rfp_mistral.data.import_proposals --input <files>`).
