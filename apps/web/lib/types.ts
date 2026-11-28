export type Me = { id: string; username: string; role: "student" | "parent"; csrf: string; demo: boolean };
export type Block = { kind: string; minutes: number; count: number; reason: string };
export type TodayPlan = {
  minutes: number;
  throttled: boolean;
  days_to_target: number;
  deferred_verifications: number;
  blocks: Block[];
  focus_candidates: { skill_id: string; priority: number; reason: string }[];
};
export type Item = {
  seen_before?: boolean;
  id: string;
  format: "mc" | "numeric";
  skill_id: string | null;
  difficulty: string | null;
  passage: string | null;
  stem: string | null;
  choices: Record<string, string> | null;
  figures: string[];
};
export type AttemptResult = {
  created: boolean;
  attempt_id: string;
  correct: boolean | null;
  revealed: boolean;
  needs_cold_retry?: boolean;
  key?: string[];
  rationale?: string | null;
};
export type Diagnosis = {
  kind: string;
  cause: string | null;
  ticket_required: boolean;
  mastery_credit: boolean;
  reverify_days: number[];
  reasons: string[];
};
export type MicroSkill = { key: string; cause: string; label: string; cue: string };
export type Ticket = {
  id: string;
  skill_id: string;
  cause: string;
  micro_skill: string | null;
  cue: string | null;
  state: string;
  next_due: string | null;
  reopen_reason: string | null;
  rule?: string | null;
};
export type Card = { id: string; kind: string; front: string; back: string };
export type Series = Record<string, { id: string; taken_on: string; rw: number | null; math: number | null; total: number | null }[]>;
export type Taxonomy = { causes: string[]; micro_skills: MicroSkill[] };
export type SkillMap = Record<string, { name: string; domain: string; section: string }>;
export type AttemptRow = { id: string; item_id: string; correct: boolean | null; confidence: string | null; elapsed_ms: number | null; created: string };
export type Step = {
  kind: "question" | "reattempt" | "worked" | "cards";
  item_id?: string; skill_id?: string; domain: string; block: string; reason: string;
  flags?: Record<string, unknown>; ticket_id?: string; rule?: string | null; count?: number;
};
export type BlockInfo = { key: string; title: string; why: string; count: number };
export type GuidedPlan = {
  id: string; section: string; minutes: number; throttled: boolean; focus_skill: string | null; focus_reason: string;
  only_skill: string | null; blocks: BlockInfo[]; steps: Step[]; done_items?: string[]; ended?: string | null;
};
export type Preview = Omit<GuidedPlan, "id" | "steps"> & { questions: number };
export type Solved = Item & { key: string[]; rationale: string | null };
export type Stats = {
  domains: Record<string, { section: string; attempts: number; correct: number }>;
  skills: Record<string, { attempts: number; correct: number; last: string | null; recent_accuracy: number | null }>;
  calibration: { sure: number; sure_right: number; sure_wrong: number };
  week_sessions: number; week_target: number; latest_total: number | null;
};
export type Summary = {
  answered: number; correct: number; sure_wrong: number; guessed_right: number;
  fixes: { id: string; cause: string; micro_skill: string | null; rule: string | null }[]; next_due: string | null;
};
