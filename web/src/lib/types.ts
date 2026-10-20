export type CachePolicy = "use" | "refresh" | "off";

export interface UsageTotals {
  calls: number;
  model_calls: number;
  cache_hits: number;
  errors: number;
  prompt_tokens: number;
  cached_prompt_tokens: number;
  completion_tokens: number;
  reasoning_tokens: number;
  total_tokens: number;
  saved_tokens: number;
  cost_usd: number;
  saved_cost_usd: number;
  latency_ms: number;
  prompt_cache_rate: number;
}

export type UsageRow = UsageTotals & {
  agent?: string;
  tool?: string;
  section_key?: string;
  model?: string;
  tier?: string;
  day?: string;
  workflow_type?: string;
};

export interface UsageCall {
  agent: string;
  tool?: string | null;
  section_key?: string | null;
  model: string;
  tier: string;
  purpose: string;
  status: string;
  cache_hit: boolean;
  prompt_tokens: number;
  cached_prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  cost_usd: number;
  latency_ms: number;
  error?: string | null;
}

export interface TokenUsage {
  workflow_id?: string | null;
  totals: UsageTotals;
  by_agent: UsageRow[];
  by_tool: UsageRow[];
  by_section: UsageRow[];
  by_model: UsageRow[];
  calls?: UsageCall[];
  by_day?: UsageRow[];
  by_workflow_type?: UsageRow[];
  workflows?: number;
}

/** One run's tokens split by section; `other_tokens` are calls not tied to a section. */
export interface RunUsage {
  workflow_id: string;
  workflow_type: string | null;
  title: string;
  client_name: string;
  saved: boolean;
  started_at: string;
  total_tokens: number;
  cost_usd: number;
  sections: { section_key: string; total_tokens: number; cost_usd: number }[];
  other_tokens: number;
  other_cost_usd: number;
}

export interface RunsUsage {
  since: string;
  runs: RunUsage[];
}

export interface TraceEntry {
  type: string;
  tool?: string;
  ok?: boolean;
  summary?: string;
  error?: string | null;
  intent?: string;
  how?: string;
  plan?: string[];
  action?: string;
  reason?: string;
  done?: boolean;
  usage?: { total_tokens: number; cost_usd: number; cache_hits: number; saved_tokens: number; model_calls: number };
}

export interface CoverageDetail {
  requirement: string;
  covered: boolean;
  score: number;
  method: string;
  evidence: string;
}

export interface Section {
  section_key: string;
  title: string;
  draft_text: string;
  citations: string[];
  evidence_scores: number[];
  validation: {
    validation_score?: number | null;
    coverage_details?: CoverageDetail[];
    missing_items?: string[];
  };
  generation_mode: "llm" | "cache" | "fallback" | "template" | "failed";
  model?: string | null;
  cache_hit: boolean;
  word_count: number;
  usage?: { total_tokens?: number; cost_usd?: number; cached_prompt_tokens?: number } | null;
  error?: string | null;
  section_id?: string;
  revision_number?: number;
}

export interface RequirementDetail {
  id: string;
  text: string;
  category: string;
  priority: "must" | "should" | "could";
}

export interface StructuredRequest {
  title: string;
  client_name: string;
  industry: string;
  request_summary: string;
  requirements: string[];
  requirement_details: RequirementDetail[];
  evaluation_criteria: string[];
  timeline: string;
  budget: string;
  compliance_requirements: string[];
  vendors: string[];
  solution_type: string;
  ambiguity_flags: string[];
  extraction_mode: string;
}

export interface Rubric {
  overall_score: number;
  criteria: { criterion: string; score: number; comment: string }[];
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
}

export interface Scores {
  composite_score: number;
  requirement_coverage_score: number | null;
  historical_similarity_score: number | null;
  solution_fit_score: number | null;
  completeness_score: number | null;
  quality_score: number | null;
  weights_used: Record<string, number>;
  coverage_details: CoverageDetail[];
  missing_requirements: string[];
  rubric: Rubric | null;
}

export interface SolutionComparison {
  catalog_configured: boolean;
  matching_offerings: string[];
  gaps: string[];
  positioning_notes: string[];
  fit_explanation: string;
  solution_fit_score: number | null;
}

export interface RunBase {
  workflow_id: string;
  status: "completed" | "partial" | "incomplete" | "failed";
  intent?: string;
  profile?: string;
  summary?: string;
  warnings: string[];
  persisted?: boolean | null;
  token_usage: TokenUsage;
  agent_trace: TraceEntry[];
}

export interface ProposalResult extends RunBase {
  sections: Section[];
  scores: Scores;
  request: StructuredRequest;
  solution_comparison: SolutionComparison;
}

export interface DocumentMatchResult extends RunBase {
  scores: Scores;
  request: StructuredRequest;
  solution_comparison: SolutionComparison;
}

export interface Stage { name: string; max_score: number }

export interface Gap { gap_type: string; severity: "Low" | "Medium" | "High" | "Critical"; description: string; recommendation: string }

export interface Stakeholder {
  name: string;
  role: string;
  category: string;
  influence_level: string;
  engagement_quality: string;
  evidence: string;
}

export interface IntentResult extends RunBase {
  client_overview: {
    opportunity_name?: string;
    client_name?: string;
    existing_relationship?: string;
    date_opened?: string;
    primary_contact?: string;
    problem_statement?: string;
    success_definition?: string;
    stakeholder_impact?: string;
    urgency_statement?: string;
  };
  buyer_readiness: {
    mode?: string;
    buyer_readiness_score?: number;
    readiness_stage?: string;
    confidence?: number;
    reasoning?: string[];
    buyer_gaps?: Gap[];
    intent_classification?: { primary_intent: string; detected_intents: string[]; summary: string; confidence: number };
    stakeholder_coverage?: {
      stakeholders: Stakeholder[];
      identified_roles: string[];
      missing_roles: string[];
      coverage_score: number;
      engagement_summary: string;
    };
    conversation_highlights?: string[];
    recommended_next_actions?: string[];
  };
  product_fit: {
    mode?: string;
    product_fit_score?: number;
    fit_stage?: string;
    fit_summary?: string;
    matched_capabilities?: { buyer_need: string; matched_capability: string; capability_area: string; fit_strength: string; evidence: string }[];
    product_gaps?: Gap[];
    integration_fit?: { score: number; summary: string; required_integrations: string[]; risks: string[] };
    competitive_positioning?: { competitors_mentioned: string[]; differentiators: string[]; positioning_summary: string };
    risk_flags?: string[];
    recommended_positioning?: string[];
    recommended_next_actions?: string[];
  };
}

export interface MarketRow {
  Company: string;
  About: string;
  "Matched solutions": string;
  Price: string;
  Review: string;
  Contact: string;
  "Age (years)": number | string;
  Domain: string;
  Sources: string;
}

export interface MarketResult extends RunBase {
  rows: MarketRow[];
  offerings: string[];
  industry?: string | null;
}

export interface RevisionResult extends RunBase {
  section_id: string;
  revision: {
    section_key: string;
    draft_text: string;
    revision_summary: string;
    changed_topics: string[];
    revision_id?: string;
    revision_number?: number;
    generation_mode?: string;
  };
  validation: { validation_score?: number | null; coverage_details?: CoverageDetail[] };
}

export interface RunSummary {
  workflow_id: string;
  workflow_type: string;
  status: string;
  profile?: string;
  title: string;
  client_name: string;
  composite_score: number | null;
  section_count: number;
  total_tokens: number;
  cost_usd: number;
  created_at: string | null;
}

export interface StoredRun<T = ProposalResult> {
  workflow_id: string;
  workflow_type: string;
  status: string;
  profile?: string;
  created_at: string | null;
  completed_at: string | null;
  result: T;
}

export interface ProfileSection { key: string; title: string; words: [number, number]; headings: string[] }

export interface Offering { code: string; name: string; description: string; capabilities: string[] }

export interface Profile {
  name: string;
  version: string;
  display_name: string;
  description: string;
  organization: { name: string; description: string; differentiators: string[] };
  industries: string[];
  offerings: Offering[];
  sections: ProfileSection[];
  default_sections: string[];
  buyer_intelligence: { readiness_stages: Stage[]; intent_types: string[]; gap_types: string[]; stakeholder_categories: string[] };
  product_fit: { fit_stages: Stage[]; gap_types: string[]; capability_areas: string[] };
  market_research: { default_offerings: string[] };
  llm: {
    provider?: string;
    configured?: boolean;
    frontier_model?: string;
    fast_model?: string;
    routes?: Record<string, string>;
    cache_backend?: string;
    degraded_mode_allowed?: boolean;
  };
}

export interface ProfileListItem { name: string; display_name: string; description: string; version: string }

export interface Readiness {
  status: "ready" | "not_ready";
  checks: {
    database: { ok: boolean; migration?: string; error?: string };
    redis: { ok: boolean; backend: string; required: boolean };
    llm: { ok: boolean; configured: boolean; provider: string; organization_id?: string | null; frontier_model: string; fast_model: string };
    profile: { ok: boolean; name?: string; version?: string; error?: string };
  };
}

export interface SearchHit {
  id: string;
  content: string;
  section_key: string;
  solution_type: string;
  proposal_id: string;
  industry: string | null;
  score: number;
}

export interface IngestResult {
  ingested_count: number;
  section_count: number;
  chunk_count: number;
  skipped_duplicates: number;
  skipped: { index?: number; id?: string; reason: string }[];
  files: { file_name: string; ok: boolean; sections?: string[]; error?: string }[];
}

export type SolutionStatus = "active" | "planned" | "retired";

export interface Solution {
  id: string;
  name: string;
  category: string | null;
  status: SolutionStatus;
  description: string;
  capabilities: string[];
  url: string | null;
  created_at: string | null;
  updated_at: string | null;
  mine: boolean;
  /** Only sent to admins. */
  owner_email?: string;
}

export type SolutionInput = Pick<Solution, "name" | "category" | "status" | "description" | "capabilities" | "url">;
