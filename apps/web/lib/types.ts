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
};
export type Card = { id: string; kind: string; front: string; back: string };
export type Series = Record<string, { id: string; taken_on: string; rw: number | null; math: number | null; total: number | null }[]>;
