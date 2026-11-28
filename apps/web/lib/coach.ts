// Coaching content. Strategies follow the PRD section playbooks and the SAT score guide; evidence notes cite
// the guide's grades. Tips fade once she's proven a skill (expertise reversal: help that helps a novice
// slows down someone who already has it).

export type Tip = { how: string; trap: string };

export const SKILL_TIP: Record<string, Tip> = {
  "craft_and_structure.words-in-context": { how: "Cover the choices. Predict your own word from the sentence, then find its match.", trap: "A choice that's a real meaning of the word, just not in this sentence." },
  "craft_and_structure.text-structure-and-purpose": { how: "Name what the sentence does with one verb: introduces, contrasts, illustrates, qualifies.", trap: "A choice that describes the content instead of its job." },
  "craft_and_structure.cross-text-connections": { how: "Sum up each author in five words, then ask how Author 2 would answer Author 1.", trap: "Treating the texts as agreeing because they share a topic." },
  "information_and_ideas.central-ideas-and-details": { how: "Say the main idea before reading choices. It covers the whole text, not one sentence.", trap: "A true detail that's too narrow to be the main idea." },
  "information_and_ideas.command-of-evidence": { how: "Point to the exact line, or the exact number in the graph, that proves it.", trap: "Data that's accurate but doesn't support the specific claim." },
  "information_and_ideas.inferences": { how: "The answer must be true from the text alone. If you need an extra assumption, it's wrong.", trap: "A reasonable idea the text never actually supports." },
  "standard_english_conventions.boundaries": { how: "Find the two clauses. Period = semicolon = comma plus FANBOYS. A colon needs a full sentence before it.", trap: "A lone comma joining two full sentences." },
  "standard_english_conventions.form-structure-and-sense": { how: "Find the true subject, skipping the phrase in between, then match the verb.", trap: "A verb that agrees with the nearest noun instead of the subject." },
  "expression_of_ideas.rhetorical-synthesis": { how: "Read the goal in the question first. Pick the choice that does exactly that goal.", trap: "A true statement from the notes that misses the stated goal." },
  "expression_of_ideas.transitions": { how: "Before the choices, name the relationship: contrast, cause, continuation, sequence or example.", trap: "A word from the right family for a different relationship." },
  "algebra.linear-equations-in-one-variable": { how: "Distribute carefully, collect terms, solve, then plug it back in.", trap: "A sign slip when distributing a negative: $-2(x - 4) = -2x + 8$." },
  "algebra.linear-functions": { how: "Slope is the rate, $y$-intercept is the starting value. Translate the story into $y = mx + b$.", trap: "Swapping the rate and the starting value." },
  "algebra.linear-equations-in-two-variables": { how: "Pick convenient values ($x = 0$ or $y = 0$) to test points and intercepts fast.", trap: "Answering for $x$ when the question asks about $y$." },
  "algebra.systems-of-two-linear-equations-in-two-variables": { how: "Graph both in Desmos and read the intersection, or eliminate one variable.", trap: "No solution means same slope, different intercept. Infinitely many means identical lines." },
  "algebra.linear-inequalities-in-one-or-two-variables": { how: "Treat it like an equation, but flip the sign when you multiply or divide by a negative.", trap: "Forgetting to flip the inequality." },
  "advanced_math.equivalent-expressions": { how: "Expand or factor, or test a value like $x = 2$ in both expressions.", trap: "Wrong powers: $9 = 3^2$, not $3^3$." },
  "advanced_math.nonlinear-equations-in-one-variable-and-systems-": { how: "Graph both sides in Desmos and read where they meet. Check every answer in the original.", trap: "An extraneous root from squaring both sides." },
  "advanced_math.nonlinear-functions": { how: "Growth or decay comes from the base, not the coefficient. Vertex form $a(x - h)^2 + k$ gives the vertex $(h, k)$.", trap: "Reading the sign of $h$ backwards." },
  "problem_solving_data_analysis.ratios-rates-proportional-relationships-and-unit": { how: "Write units on every number and let them cancel.", trap: "Converting once instead of for every unit that changes." },
  "problem_solving_data_analysis.percentages": { how: "Percent change $= \\dfrac{\\text{new} - \\text{old}}{\\text{old}}$. Multiplying by $1.2$ is a 20% increase.", trap: "Dividing by the new value instead of the original." },
  "problem_solving_data_analysis.one-variable-data-distributions-and-measures-of-": { how: "Mean moves toward outliers; median doesn't. Spread is about distance from center.", trap: "Assuming mean and median change together." },
  "problem_solving_data_analysis.two-variable-data-models-and-scatterplots": { how: "Read the axes and units first. In Desmos, regressions use `~`, not `=`.", trap: "Interpreting the slope with the wrong units." },
  "problem_solving_data_analysis.probability-and-conditional-probability": { how: "Find the right row or column total first. 'Given' shrinks the denominator.", trap: "Using the grand total for a conditional probability." },
  "problem_solving_data_analysis.inference-from-sample-statistics-and-margin-of-e": { how: "Conclusions only reach the population the sample was drawn from, within the margin of error.", trap: "Claiming more certainty than the margin allows." },
  "problem_solving_data_analysis.evaluating-statistical-claims": { how: "Random assignment shows cause. Random sampling lets you generalize. You need the right one for the claim.", trap: "Calling an observational study proof of cause." },
  "geometry_trigonometry.area-and-volume": { how: "Write the formula first, then substitute. Check which measurement the question wants.", trap: "Using diameter where the formula wants radius." },
  "geometry_trigonometry.lines-angles-and-triangles": { how: "Mark every angle you can find. Parallel lines and triangle sums (180°) do most of the work.", trap: "Assuming a figure is drawn to scale." },
  "geometry_trigonometry.right-triangles-and-trigonometry": { how: "SOHCAHTOA, and $\\sin\\theta = \\cos(90^\\circ - \\theta)$. Look for 3-4-5 and 5-12-13 triangles.", trap: "Mixing up opposite and adjacent." },
  "geometry_trigonometry.circles": { how: "Complete the square to get $(x - h)^2 + (y - k)^2 = r^2$. Arc and sector are fractions of $360^\\circ$.", trap: "Reporting $r^2$ as the radius." },
};

// The question Peak asks before attaching a cause (design guide: ask, don't label).
export const ASK: Record<string, string> = {
  sign_slips: "Did a sign flip trip you up?",
  skips_plug_back: "Would plugging it back in have caught it?",
  wrong_powers: "Was it a power or exponent slip?",
  requested_quantity: "Did you answer a different question than the one asked?",
  format_shift_abandonment: "Did the question look different from ones you know?",
  desmos_vs_algebra: "Would the other method have been faster?",
  numeric_entry_format: "Was it how you typed the answer?",
  distractor_traps: "Did a tempting wrong answer pull you in?",
  one_problem_time_sink: "Did this one eat too much time?",
  desmos_syntax: "Did Desmos do something unexpected?",
  hidden_powers: "Was there a rule here you didn't know yet?",
  growth_vs_decay: "Was there a rule here you didn't know yet?",
};

// The guide's six miss categories, mapped onto Peak's causes ("Careless" must still name a pattern).
export const CATEGORY: [string, string, string, string][] = [
  ["content_gap", "Content gap", "Didn't know the rule or method yet", "a rule you didn't know yet"],
  ["requested_quantity", "Misread", "Answered something other than what was asked", "a misread"],
  ["execution", "Careless slip", "Knew it, slipped on a step", "a careless slip"],
  ["pacing", "Time", "Ran long or rushed", "a time problem"],
  ["evidence_distractor", "Trap answer", "A tempting wrong choice pulled you in", "a trap answer"],
  ["setup_method", "Strategy", "Picked a slower or wrong approach", "a strategy problem"],
];

// Short "why this works" notes, from the score guide's evidence table.
export const WHY: Record<string, string> = {
  warmup: "Spaced re-attempts are where fixes stick. Spaced retrieval beat cramming by a wide margin in the research (score guide 4.3, grade A).",
  cards: "Saying a rule from memory before you check it beats rereading it (4.1, grade A).",
  learn: "For a new math skill, studying solved examples first works better than struggling cold. Once you've got it, they slow you down, so they go away (4.4).",
  mixed: "Mixing question types feels harder. That's the point: it trains you to spot which tool a question needs (4.2, grade A).",
  confidence: "Sure-but-wrong answers are the most valuable ones to catch. They're the mistakes that feel right (4.6).",
  rule: "Writing your own one-line rule is a light way to explain it to yourself, without slowing you down (4.4).",
  pace: "On test day, Reading and Writing gives ~71 seconds a question and Math ~95. Flag a time sink and come back (section 3).",
};

export function tipFor(skillId: string | null | undefined): Tip | null {
  return (skillId && SKILL_TIP[skillId]) || null;
}

/** Faded scaffolding: show the strategy until she's right on at least 4 of her last 5 (min 5 answers). */
export function tipFaded(stat: { attempts: number; recent_accuracy: number | null } | undefined): boolean {
  return !!stat && stat.attempts >= 5 && (stat.recent_accuracy ?? 0) >= 0.8;
}

export function paceSeconds(section: string | undefined): number {
  return section === "rw" ? 71 : 95;
}
