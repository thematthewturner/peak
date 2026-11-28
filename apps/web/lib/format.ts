// Shared wording and dates. Copy follows the PRD voice: short, concrete, never a lecture.
export const SAT_DAY = new Date(2027, 5, 5);

export function daysToSat(now = new Date()): number {
  const t = new Date(now);
  t.setHours(0, 0, 0, 0);
  return Math.max(0, Math.round((SAT_DAY.getTime() - t.getTime()) / 86_400_000));
}

export function greeting(now = new Date()): string {
  const h = now.getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}

export const DOMAIN: Record<string, string> = {
  algebra: "Algebra",
  advanced_math: "Advanced Math",
  problem_solving_data_analysis: "Problem-Solving & Data",
  geometry_trigonometry: "Geometry & Trig",
  craft_and_structure: "Craft & Structure",
  information_and_ideas: "Information & Ideas",
  standard_english_conventions: "Conventions",
  expression_of_ideas: "Expression of Ideas",
};

export const CAUSE: Record<string, string> = {
  execution: "Execution",
  setup_method: "Setup",
  content_gap: "Content gap",
  requested_quantity: "Answered a different question",
  evidence_distractor: "Distractor",
  pacing: "Pacing",
  entry: "Entry format",
  tool_misuse: "Desmos or tools",
};

// Causes that must name a pattern: "careless" is never a final answer.
export const NEEDS_PATTERN = new Set(["execution", "requested_quantity", "pacing"]);

export function shortDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso.length <= 10 ? iso + "T00:00:00" : iso);
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

export function capitalize(s: string): string {
  return s ? s[0].toUpperCase() + s.slice(1) : s;
}
