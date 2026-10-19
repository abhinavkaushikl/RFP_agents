const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
const whole = new Intl.NumberFormat("en-US");

export const fmtInt = (n: number | null | undefined) => whole.format(Math.round(n ?? 0));
export const fmtCompact = (n: number | null | undefined) => compact.format(n ?? 0);
export const fmtPct = (ratio: number | null | undefined, digits = 0) =>
  ratio == null ? "Not measured" : `${(ratio * 100).toFixed(digits)}%`;

export function fmtCost(usd: number | null | undefined): string {
  const v = usd ?? 0;
  if (v === 0) return "$0";
  if (v < 0.01) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(2)}`;
}

export function fmtScore(value: number | null | undefined): string {
  return value == null ? "Not measured" : Math.round(value * 100).toString();
}

export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const diff = (Date.now() - then) / 1000;
  if (diff < 45) return "just now";
  if (diff < 3600) return `${Math.round(diff / 60)} min ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)} h ago`;
  if (diff < 7 * 86400) return `${Math.round(diff / 86400)} d ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function titleCase(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Plain-language names for the supervisor's tools, as shown to sales users. */
export const STEP_LABELS: Record<string, string> = {
  structure_request: "Read the RFP",
  compare_solutions: "Match offerings",
  retrieve_evidence: "Find precedent",
  generate_proposal_sections: "Draft sections",
  generate_section: "Draft section",
  validate_section: "Check coverage",
  revise_section: "Revise",
  score_proposal: "Score",
  market_research: "Search vendors",
  detect_intent_fields: "Opportunity basics",
  frame_business_problem: "Frame the problem",
  analyze_buyer_intelligence: "Buyer readiness",
  analyze_product_fit: "Product fit",
};

export const stepLabel = (tool: string) => STEP_LABELS[tool] ?? titleCase(tool);
