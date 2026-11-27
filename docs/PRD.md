# Peak — SAT Prep for Addison: PRD & Architecture

Nov 27, 2026 · @Matt Turner · Standalone app

## 1. Decision

Build **Peak**, named for reaching her top performance. It is a standalone **SAT-only** app with its own repo (`thematthewturner/peak`), database, files and deploys, running as a separate Compose project on the existing `belay-app` Droplet at `peak.mturner.work`. Its job is narrow. **Find the SAT points Addison is still losing, assign the smallest fix that works, and prove the fix holds on a fresh question under test conditions.**

The promise to Addison: *"Know exactly which points you're losing. Fix them once. Prove it on a question you've never seen."*

Headline bets:

1. **SAT only, hyper-focused.** One exam, one taxonomy, one runner, one score trend. The target is a 1400 superscore for Palmetto Fellows, with a first official sitting on June 5, 2027.
2. **A real, private corpus.** All the official SAT practice material Matt can download goes into a private, verified item bank. Generated content has to pass the same checks: deterministic math templates and gated R&W items. Official items are the calibration anchor. Bluebook forms stay locked as clean benchmarks.
3. **Tailored to her specific errors.** Seed the error model with what we already know from Honors Algebra 2. She skips plug-back checks, drops a routine when the format changes, has a few recurring wrong powers, slips on signs, and stalls on one problem. Her slowdowns come from stacking several rules at once. Each becomes a named cue the runner enforces.
4. **Math first, R&W protected.** Her October 2026 PSAT was R&W 620, Math 500, and Math is half the SAT score. Math gets about 60% of the time; R&W keeps weekly reps on Craft & Structure.
5. **Copy Belay, don't couple to it.** A one-time copy of Belay's hardened modules gives Peak a head start. The two apps share only the host and one edge proxy, with no runtime calls between them.
6. **Scratch-paper diagnosis.** For a missed math item, she photographs her scratch work. The ported Belay reading pipeline marks the first wrong step. Her losses are execution errors, so this is the highest-leverage feature Belay brings.

## 2. Starting point and stakes

The working target is a **1400 superscore** (about R&W 710 / Math 690), from a current **1120** (R&W 620 / Math 500, PSAT, October 2026). That is +90 R&W and +190 Math. The runway is about 27 months to the last Palmetto-eligible sitting.

**Why 1400.** Wando class rank puts the top-6% Palmetto path out of reach. The rank-free path needs SAT 1400 plus a 4.00 SC UGP. She is at 4.575, so the test score is the binding constraint. CHE superscores the SAT, so section-by-section gains across sittings count. [CHE Palmetto workshop](https://che.sc.gov/sites/che/files/Documents/Counselors%20Page/PFS%20Early%20Award%20Workshop%202024UPDDATE.pdf) · [CHE 2027 info packet](https://che.sc.gov/sites/che/files/Documents/Counselors%20Page/PFS_Info_Packet_Student_2027.pdf)

**What it is worth (SC schools only).** Palmetto pays $6,700 in year 1 and $7,500 in years 2–4, or $29,200 total. LIFE pays $5,000 a year, or $20,000. The gap is **$9,200 over four years**, and it holds with STEM enhancements on both. USC adds at least $3,500 for Palmetto Fellows. The app costs are small next to this: a 20-point shift in P(1400) is worth about $1,840 in expectation, before counting honors-college and merit effects. [CHE award amounts](https://che.sc.gov/node/72) · [USC](https://cms.sc.edu/about/offices_and_divisions/undergraduate_admissions/tuition_scholarships/sc_residents/index.php)

### Diagnostic profile Peak starts from

| Signal | Value | Product implication |
| --- | --- | --- |
| PSAT Oct 2026 | 1120 = R&W 620 / Math 500 | Start the plan at a 60/40 Math/R&W time split. Rebalance weekly from fresh data. |
| Weak PSAT bands | Advanced Math, PSDA, Geometry/Trig, Craft & Structure | These seed the first repair queue. Confirm them on a Bluebook baseline. |
| Strong band | Information & Ideas | Maintenance only, as hard-item reps. |
| Algebra 2 error log (Oct 2026) | No plug-back checks; format-shift abandonment; wrong powers (9 = 3³ recurring); sign slips; one-problem time sink | Pre-seeded micro-skills and cues (§5.2). The runner enforces the checks. |
| Fluency vs knowledge | Accurate in isolation, slows when several rules stack | Train stamina with timed modules and Hard Module 2 sims, not more content review. |
| Current coursework | Honors Algebra 2 now; Precalc next year (CP vs Honors undecided) | Align Advanced Math drills to the current Algebra 2 unit to double-dip. |

### Scenario model (planning assumptions, not predictions)

| Scenario | Assumption | Mar 2028 superscore | 1400 reached |
| --- | --- | --- | --- |
| Bear | Fewer than 1.5 sessions a week. Math gains come mostly from coursework. | \~1230 (660 / 570) | Unlikely by senior spring; LIFE stays the plan |
| Base | Three 25-minute sessions a week, repair loop working, Bluebook every 3 weeks | \~1320 (690 / 630) | Fall of senior year, through a Math superscore |
| Bull | Base, plus Math errors convert quickly as they did in Algebra 2 (48% to 98% in one session) | \~1410 (720 / 690) | Spring of junior year |

The swing variable is Math execution, not R&W content. Section gains and scores in this table are speculative. Replace them with her first two clean Bluebook results.

### Calendar anchors

- **Dec 2026:** Bluebook preview, then one unseen full test as the clean baseline.
- **Jun 5, 2027:** sophomore SAT (confirmed). It gives a real score report and a first superscore section. Register before College Board's deadline. [College Board](https://satsuite.collegeboard.org/dates/june-5-2027-sat-test-date)
- **Oct 2027:** PSAT/NMSQT (junior). National Merit is not a goal, since her index of 172 is far below typical SC cutoffs. Use it as a free official checkpoint.
- **Spring 2028:** primary SAT window.
- **Aug–Oct 2028:** senior retakes for any section still short.
- **Spring 2029:** last Palmetto-eligible sitting. CHE's 2026 materials say March and its 2027 packet says April, so confirm the cutoff with the Wando counselor.

## 3. Product principles

1. **Studying doesn't wait for software.** Phase 0 starts on official tools by link. The private corpus takes over as it is ingested.
2. **Clean benchmarks are sacred.** An unseen, uninterrupted, single-sitting Bluebook form is the only score trend shown as truth. Retakes, pauses and exposed forms go in separate series.
3. **Repetition is not transfer.** An issue closes only on fresh, unaided, first-exposure items from a different item family, at least one of them 7 or more days after the repair.
4. **Smallest intervention that works.** Match the intervention to the cause: a cue, a rule card, a worked example, a timed rep or a lesson. "Careless" is never a terminal label.
5. **Addison owns it.** Peak is student-led. Matt gets a one-minute weekly digest, not a live feed.
6. **School comes first.** When a school test is within 3 days, Peak drops to 5-minute maintenance.
7. **No guilt mechanics.** No streaks and no growing backlog. A tired week shortens sessions without wiping history.
8. **Carry over Belay's invariants.** Ownership checks on every route, additive-only migrations, allowlisted logs, every model call through `parse_with_receipt` and the monthly budget, and no answer reveal before an attempt is recorded.

### How the two research docs are reconciled

The two inputs (the engineering research and the Max-Score Blueprint) disagree in several places. Each row records the call made here.

| Topic | Engineering research | Max-Score Blueprint | Decision in this PRD |
| --- | --- | --- | --- |
| Item source | Import roughly 3,000 Question Bank items into the database and render them in-app | Store pointers and metadata only; render only original or licensed items | Build both: a private official corpus from Matt's own downloads, plus a verified generated corpus (§8). Material that overlaps Bluebook stays benchmark-locked. |
| Hosting | Local SQLite or Postgres | One local SQLite file | Peak's own Compose project and Postgres on the shared Belay Droplet. It is one canonical database across her MacBook and iPhone, with Belay's hardened ops copied in. The Blueprint itself requires one canonical database. |
| Scheduler | FSRS for everything | Transparent heuristic plus a verification ladder | Three engines, one job each: a verification ladder for mistakes, FSRS for atomic rule cards only, and a priority heuristic for choosing drills (§5.4). |
| Closing a mistake | Correct twice on separate days with fresh variants | Two unaided first exposures from distinct families across 2 days, one at 7+ days in an unlabeled mixed set | The Blueprint's stricter rule. |
| Error labels | Auto-classify (careless, gap, pacing, lucky guess) | Cold retry first; "careless" never closes a ticket | The auto-classifier proposes; Addison confirms a cause and a cue in 2 taps. "Careless" must map to a named execution micro-skill. |
| Score estimates | Tutor-estimated routing cutoffs and error budgets | No drill-to-SAT conversion | No in-app scaled score. Error budgets appear only as coaching heuristics labeled as tutor estimates. |
| Test runner | Replicate all 9 Bluebook tools | Use Bluebook for the interface; in-app timed sets come later | Phase 2 builds the habit-forming subset: timer, eliminator, mark-for-review navigation, strict numeric entry, Desmos, reference sheet, highlight. Adaptive full tests stay in Bluebook. |
| Session dose | 20–30 minutes of FSRS a day plus micro-sets | Three 25-minute sessions a week | Three 25-minute core sessions a week, plus optional 5-minute phone sessions on other days. |
| Vendor statistics (Lumist 42% drop, Acely 94%, "80% of gains from review") | Used as design constants | Treated as marketing evidence | Hypotheses only. Peak measures its own versions. |

Correction to the Blueprint: it calls the 620/480 PSAT split stale. The October 2026 PSAT (620 / 500) is current, so the starting allocation can use it now.

## 4. Users and jobs

| User | Job to be done | Surface | Success looks like |
| --- | --- | --- | --- |
| **Addison** (primary) | "Tell me exactly what to do in the time I have, show me why I missed it, and let me prove I've fixed it." | MacBook for core sessions and timed work. iPhone for 5-minute rule reps, logging Bluebook misses and photographing scratch work. | Opens Today and is working within 10 seconds. Rates sessions useful at least 4/5. Chooses to come back. |
| **Matt** (parent/operator) | "Know whether this is working, and when to step in, without becoming the tutor." | Weekly digest in Peak's parent view. Admin pages for corpus review and settings. | Reads the digest in under a minute. Under 15 minutes a week of parent effort after setup. |
| **Tutor** (optional) | "Arrive at a session knowing her top two loss patterns." | A one-page PDF export Matt shares by hand, modeled on Belay's tutor handoff. | Tutor sessions target open repair tickets, not general review. |

The explanation voice follows Matt's standing instruction: write as a really smart 10th-grade girl would explain it to a friend. That means short, concrete and a little funny, never condescending, and never a lecture.

## 5. Learning methods

Every miss becomes a **repair ticket** that moves through five steps. Each step is grounded in a method with real evidence behind it: retrieval practice, spacing, interleaving, faded worked examples, specific feedback, and the hypercorrection effect.

### 5.1 The loop

1. **Attempt.** Before any feedback, record the answer or skip, confidence (Sure / Unsure / Guess, one keypress), elapsed time, flags, answer changes and Desmos use. External items record what is known; unknown values stay null.
2. **Diagnose.** Retry the missed item cold and untimed before revealing the solution. Wrong untimed points to content, setup or reasoning. Right untimed after a timed miss points to fluency, pacing or execution. For math, she can photograph her scratch work and the scratch-work pipeline (ported from Belay) marks the first wrong step. She confirms one cause and one cue in two taps.
3. **Repair.** Apply the smallest intervention for that cause (table in 5.5).
4. **Verify.** Run the verification ladder (5.4a). Only fresh, unaided, first-exposure evidence counts.
5. **Maintain.** Confirmed skills reappear in mixed sets. A fresh miss reopens the ticket with the reason attached.

### 5.2 Error taxonomy, pre-seeded for Addison

Causes are fixed and small. Micro-skills are open-ended and carry a one-line cue that appears in the runner when the pattern is likely.

| Cause | Example micro-skills (seeded from her Algebra 2 log) | Cue shown in the runner |
| --- | --- | --- |
| Content gap | Hidden powers (1 = b⁰, √ = ½); growth vs decay from base, not coefficient | Rule card plus a worked example |
| Setup / method | Abandons a known routine when the layout changes; picks Desmos when algebra is faster | "Same math, new costume. What's the routine?" |
| Requested quantity | Answers x when asked for 6x, radius when asked for diameter, one root when asked for the sum | "Re-read the last line before you enter." |
| Execution | Skips plug-back; sign slips when factoring; wrong powers (9 = 3³ recurring) | "Plug it back in" check line on equation items |
| Entry (numeric response) | Mixed numbers, too many characters, a dropped negative | Strict-entry validation with a reason |
| Evidence / distractor (R&W) | Recycled language, absolutes, scope shift, true but off-goal (rhetorical synthesis) | "Point to the line that proves it." |
| Pacing | Spends 3+ minutes on one item | A 90-second nudge to flag and move |
| Tool misuse | Typed `=` instead of `~` in a regression; misread a zoomed graph | Desmos syntax card |

Auto-classification proposes a cause from correctness × confidence × difficulty × time × cold-retry result. The rule is deterministic and its reasons are visible. Addison's confirmation wins.

### 5.3 Confidence and hypercorrection

| Confidence + outcome | Reading | Action |
| --- | --- | --- |
| Sure + wrong | Entrenched misconception (hypercorrection opportunity) | Show the surprise feedback right away. A ticket is required. Re-verify at 2–3 days and again at about 7 days, because confident errors can return once the correction fades. |
| Guess + right | Lucky guess | Show the full explanation anyway. No mastery credit. Enter the skill into the queue. |
| Unsure or Guess + wrong | Knowledge gap | If the misses cluster in one skill or come with long times, route to untimed SkillBuilder before any timed work. |
| Sure + right + on pace | Fluent | Counts as evidence and extends FSRS intervals. |
| Sure + right + slow (over p90 for the skill) | Correct but expensive | Fluency ticket: timed reps on a faster method. |

### 5.4 Three schedulers, one job each

**a) Verification ladder (repair tickets).** A transparent state machine:

`OPEN → REPAIRING → RETRY_DUE (next day) → TRANSFER_DUE (7+ days, unlabeled mixed set) → CONFIRMED → MAINTAIN`, with a relapse moving it to `REOPENED`.

CONFIRMED needs two correct, unaided, first exposures from **distinct item families** on two different days, one of them in a mixed set 7 or more days after the repair. If time caused the original miss, one of them must also be under target pacing. A same-family variant or a recalled answer cannot close a ticket. When no fresh item exists, show "needs a new item" and do not count a repeat.

**b) FSRS for atomic rule cards only.** Use `py-fsrs` with `desired_retention = 0.90`. Card types: formulas missing from the reference sheet (discriminant, vertex form, sum and product of roots, circle standard form, arc and sector, complementary sin/cos), the five grammar clusters, transition families, Desmos syntax, and her personal cue cards from confirmed tickets. Math cards render a fresh template variant on every review, and the prompt never names the method.

The rating comes from behavior, not self-report:

- Again: wrong, or needed a hint.
- Hard: right on a guess, or slower than p90.
- Good: right, Sure, on pace.
- Easy: right, Sure, under p50.

Run the optimizer monthly once there are about 1,000 reviews. Defaults are fine before then.

**c) Drill priority (what to practice next).** For each skill *s* in the official taxonomy:

```latex
\text{priority}_s = w_{\text{domain}} \times \hat{m}_s \times (1 + 0.5\,r_s) \times f(\text{days to test}), \qquad \hat{m}_s = \frac{\text{misses}_s + k\,\bar{m}_{\text{section}}}{\text{attempts}_s + k}
```

- w = the official domain share (about 0.35 for Algebra and Advanced Math, 0.15 for PSDA and Geometry/Trig; 0.20–0.28 for R&W domains).
- m̂ = the first-attempt miss rate, smoothed toward the section average with k = 8.
- r = open or reopened tickets in the last 30 days.
- f = a factor that shifts weight toward timed and robustness work inside 6 weeks of a test.

About 15% of slots go to under-measured skills for exploration. Hard items unlock only after 75% or better on the last 12 fresh Medium items. Matt and Addison can override any of this from the UI. Priority orders work; it is not a point value.

### 5.5 Repair playbook (cause → smallest intervention)

| Cause | Intervention | Evidence that closes it |
| --- | --- | --- |
| Content gap | One worked example, then a faded example where she supplies the missing step, then an unseen item. Add a rule card to FSRS. | The ladder in 5.4a |
| Setup / method | Contrast two plausible approaches side by side, then one transfer item | Ladder, unlabeled |
| Requested quantity / execution | Add a runner cue and a check line; 5 mixed items where the trap is live | Ladder, with no cue on the transfer item |
| Evidence / distractor | Name the distractor's flaw, point to the proving line, then 3 fresh items of the same skill | Ladder |
| Pacing | Train the skip trigger, or switch to a faster reliable method (algebra vs Desmos decision card) | Timed transfer at target pace |
| Persists after 2 repair cycles | Escalate: Khan Academy lesson, a tutor-handoff item, or Schoolhouse.world | Same ladder |

### 5.6 Session composer (Today)

She picks 5, 15, 25 or 40 minutes. Every block shows its reason (for example, "Due: sign slips, 7-day check").

| Block | Share of a 25-minute session | Content |
| --- | --- | --- |
| Due verifications | Up to 30% | Retry and transfer items from the ladder |
| Rule cards | Up to 5 minutes | Due FSRS cards, interleaved across domains |
| Focused skill | About 45% | The top-priority skill: worked example → faded → unseen |
| Mixed finish | About 20% | 4–6 unlabeled, interleaved items, including one from the weaker section |

A 5-minute session is rule cards only. The composer caps the backlog: overdue items past 2× a session are re-ranked, not stacked.

### 5.7 Stamina progression

She moves stage by stage, per section. Promotion needs 80% fresh accuracy at the stage below over at least 2 sessions.

1. Untimed SkillBuilder
2. Per-item caps: 45 s for R&W conventions, 60 s for standard Math, 90 s for dense reading and hard Math
3. Timed micro-sets of 10–15 items
4. A full single module: 27 R&W items in 32 minutes, or 22 Math items in 35 minutes
5. A Hard Module 2 simulation, with the hardest items first, to train composure
6. A full Bluebook test

This targets her documented gap, which is throughput when several rules stack, not knowledge.

## 6. Features

P0 delivers the coaching loop on a verified official SAT corpus. P1 adds depth: templates, generated R&W items, the timed runner and scratch-work diagnosis. P2 adds refinements that only pay off once there is data.

### P0: the coaching loop on official content (Phase 1)

| ID | Feature | Minimum behavior | Acceptance |
| --- | --- | --- | --- |
| F1 | **Today** | A 5/15/25/40-minute session built by the composer (§5.6), with a reason on every block. Before the corpus is ready, it assigns official practice by link. | Working within 10 seconds of opening. Shortening a session never deletes due work. |
| F2 | **Official corpus ingestion** | Matt uploads Question Bank exports and SAT/PSAT practice tests in `/admin/corpus`. The pipeline extracts, verifies, locks and publishes them (§8.3). A review queue shows the source page beside the extraction. | Extraction errors under 1% on audit. Benchmark items are never served in drills. Re-uploading a file is a no-op. |
| F3 | **Item player (learning mode)** | Multiple choice plus numeric entry under College Board rules: 5 characters for positive answers, 6 for negative; no mixed numbers, commas, $ or %. Confidence capture before submit. Official rationale afterward. Trap tags. | Invalid entries are rejected with the official reason. No key or rationale is sent before an attempt exists. |
| F4 | **Benchmarks and form ledger** | Separate series for PSAT, clean Bluebook, exposed Bluebook and official SAT. Screenshot intake of My Practice review screens and score reports. | A retaken, paused or assisted result cannot enter the clean trend. |
| F5 | **Miss and guess review** | Queues wrong, skipped, right-but-guessed and slow-right attempts. A cold-retry prompt, then 2 taps for cause and cue. | Under 30 seconds per miss. "Careless" needs a micro-skill. |
| F6 | **Repair and verification queue** | The ladder from §5.4a: state, next evidence, due date and reopen reason on every ticket. | A retry or double submission never advances a ticket twice. A same-family item cannot close one. |
| F7 | **Rule cards on iPhone** | FSRS deck (§5.4b): formulas, grammar clusters, transition families, Desmos syntax and her cue cards. | Ratings come from behavior. A 5-minute session works one-handed. |
| F8 | **Progress and parent digest** | Clean Bluebook trend, newly confirmed skills, the next action, and a countdown to June 5, 2027. The weekly digest adds corpus health and the generated items waiting for Matt's review. | Matt reads it in under a minute. |
| F9 | **School-test calendar and throttle** | She enters school test dates. Within 3 days of one, sessions drop to 5-minute maintenance. | No due ticket is dropped; dates slide. |
| F10 | **Export and backup** | CSV and JSON export. Peak's own nightly encrypted backups and restore drill. | A restore preserves provenance, exposure, ticket states and due dates. |

### P1: depth (Phases 2–3)

| ID | Feature | Minimum behavior | Acceptance |
| --- | --- | --- | --- |
| F11 | **Scratch-work diagnosis** | The ported Belay pipeline marks the first wrong step in a photo of her math work. | Only after her attempt is recorded. Feedback cites a line or abstains. |
| F12 | **Math templates** | About 25 families calibrated to official exemplars, aimed at her weakest Advanced Math, PSDA and Geometry/Trig cells. | Every instance passes verification. A 200-instance audit finds zero key errors. |
| F13 | **Dual solution tabs** | An Algebra path and a Desmos path with a "faster here" tag. | Both paths are verified to reach the key. |
| F14 | **Timed runner** | Bluebook-style tools: hideable timer with a 5-minute alert, eliminator, mark for review and question menu, reference sheet, highlights, Desmos. Module trainers and a Hard Module 2 simulator. | Survives a dropped connection. Timing is accurate to the second. **Ships by May 15, 2027.** |
| F15 | **Generated R&W corpus** | The draft → check → Matt reviews → calibrate pipeline (§8.4), aimed at Craft & Structure and other thin cells. | Within 10 points of official-item accuracy in the same cell, or the cell is pulled. |

### P2: once there is data (Phase 4)

- **F16** Monthly FSRS optimizer and a pacing dashboard (p50/p90 time by skill, answer-change direction, flags revisited).
- **F17** One-page tutor handoff PDF and an item-bounded coaching chat that gives no answers in timed mode.
- **F18** Optional read-only Belay feed for school test dates and her current unit.

## 7. Section playbooks built into the product

The test's structure is official. Each module has two unscored pretest items. The Module 1 result sets the Module 2 route, and scoring uses item characteristics, not raw counts. Peak encodes tactics as cues, rule cards and drill modes, not as reading material. [Test structure](https://satsuite.collegeboard.org/sat/whats-on-the-test/structure)

|  | Reading and Writing | Math |
| --- | --- | --- |
| Per module | 27 items in 32 minutes (about 71 s each) | 22 items in 35 minutes (about 95 s each) |
| Domains (share of scored items) | Craft & Structure 28%, Information & Ideas 26%, Conventions 26%, Expression of Ideas 20% | Algebra 35%, Advanced Math 35%, PSDA 15%, Geometry & Trig 15% |
| Format | Multiple choice with one short passage each | About 75% multiple choice, about 25% numeric entry |

### Math

- **Desmos decision cards** (FSRS card type plus the dual-solution tab):
  - Use Desmos for systems and intersections, radical equations (graph both sides), almost-factorable quadratics, equivalent-expression checks, and regressions written with `~`.
  - Use algebra for proportional "no solution / infinite solutions" problems, tangency with b² − 4ac = 0, sum and product of roots, and one-step linear items.
- **Formulas missing from the reference sheet** are seeded as rule cards: slope, distance, midpoint, discriminant, quadratic formula, vertex form, −b/a and c/a, circle standard form, exponential growth and decay, SOHCAHTOA, sin θ = cos(90° − θ), arc length, and sector area.
- **Live trap checks** on items: the requested quantity (6x vs x), extraneous roots (plug back), dividing by x (loses x = 0), and units or percent-of vs percent-change. Her plug-back habit is the first cue to fade, and only once tickets confirm it.
- **Content filter:** exclude complex numbers and long multi-question passages from any imported legacy material. Numeric entry accepts negatives.
- **Coursework alignment:** when her current school unit (from the calendar) is Algebra 2 exponentials or functions, drill priority boosts the matching Advanced Math skills by 1.25×.

### Reading and Writing

- **Conventions, as five rule clusters:**
  1. Clause boundaries: period = semicolon = comma + FANBOYS, and a colon only after an independent clause.
  2. Matching punctuation around nonessential elements.
  3. Subject–verb agreement across intervening phrases.
  4. Apostrophes vs possessive pronouns.
  5. Tense consistency and dangling modifiers.
- Choose the shortest complete option only as a tiebreaker.
- **Transitions:** cover the choices, name the logical family first (contrast, cause, continuation, sequence, emphasis), then compare.
- **Rhetorical synthesis:** read the stated goal before the notes. Reject answers that are true but off-goal.
- **Reading items:** predict the word in Words in Context before looking at choices. Label sentence functions with an action verb in Text Structure. Summarize each author in 5 words for Cross-Text. Point to the proving line for evidence and inference. The distractor checklist covers recycled language, absolutes, scope shift and reversal.
- **Her profile:** keep Information & Ideas sharp with hard reps only. Put R&W repair time into Craft & Structure.

### Timing and test-day execution

- **Module 1 precision.** It sets the route, so train accuracy before speed there.
- **Two-pass rule.** Flag and move if an R&W item passes about 90 seconds, or a Math item has no setup within 45–60 seconds. Enter a best guess before moving and never leave a blank. The runner nudges at those thresholds, which also covers her one-problem time sink.
- **Final 60 seconds.** Sweep any blanks with a fixed letter.
- **Hard Module 2 composure.** A hard opening is a good sign: it means she routed up. The simulator front-loads the hardest items so the hard start is familiar.

Tutor-estimated error budgets and routing cutoffs (for example, about 0–2 Math misses for 780+) are not published by College Board. They may appear as coaching context, labeled as estimates, and never as a score conversion.

## 8. Content corpus

Peak builds a **private corpus of every official SAT item it can get**. A **generated corpus** extends it, calibrated against the official items and admitted only through the same checks. Official items are the ground truth for style, difficulty and keys. Bluebook forms stay locked as benchmarks.

### 8.1 Why both halves are needed

These are planning estimates.

- **Demand.** She sees about 45–60 fresh items a week, or roughly 3,000–4,000 exposures through spring 2028. About 60% are Math, and most are Medium or Hard.
- **Supply.** The official Question Bank is reported to hold about 3,000 current SAT items. Spread over 87 skill × difficulty cells, that averages about 35 per cell.
- **The binding constraint** is Hard items in her weak cells: Advanced Math, PSDA, Geometry/Trig and Craft & Structure. Focused repair burns through one of those cells in roughly 3–5 weeks. Generated items supply the depth there.

### 8.2 What goes in (everything private)

| Source | Use | Counts toward confirming a fix? |
| --- | --- | --- |
| Question Bank exports, **all** domains and difficulties, with "exclude active questions" on | Drills | Yes, first exposure tracked by Question ID |
| Paper (non-adaptive) SAT and PSAT practice tests | Benchmark-locked: post-test review and exposure tracking only | No |
| Her Bluebook My Practice review screens and official score reports | Review of her own misses | No |
| Purchased prep books (optional: Meltzer, College Panda), scanned | Escalation drills | Yes, within that source |
| Generated math templates | Unlimited fresh variants | Yes, but a family can't close its own ticket |
| Generated R&W items | Fill thin cells | Only after Matt's review and calibration |

Khan Academy stays a link-out and is not ingested. Peak never scrapes a website; everything enters as a file Matt downloaded or scanned.

### 8.3 Ingestion pipeline

Question Bank exports split on Question ID anchors. Practice tests split on section, module and question number.

1. **Upload and fingerprint.** A SHA-256 hash makes duplicate uploads a no-op. Files go to private storage, never Git.
2. **Render and segment.** Page images plus the text layer.
3. **Extract.** Claude vision plus the text layer returns structured JSON: passage, stem, choices, figure crops, key, rationale and metadata. For Question Bank exports, the export filter supplies the metadata.
4. **Verify.**
   - Schema check.
   - The official key is present.
   - A blind solve by `MODEL_CHECK_ID`; a disagreement goes to review.
   - SymPy checks math keys when the stem parses.
   - The re-rendered text matches the source text layer at 99% or better.
   - A figure exists wherever the source page had one.
5. **Dedupe and lock.** Dedupe by Question ID. Any item from a benchmark form is locked. Her past exposure is imported from her logs.
6. **Publish** with `status = verified` and `rights = private_official`. Failures go to a review queue with the source page beside the extraction.

**Quality gate:** a 50-item human audit per 1,000 items, with extraction errors under 1%.

**Cost:** about 3,000–3,500 items. That is an estimated one-time $50–200 at current Sonnet/Opus-class rates, and about half that through the Batch API. Confirm on the pricing page first. A separate `INGEST_COST_LIMIT` caps it.

### 8.4 Generated corpus

- **Math templates.** Each family declares its skill, trap type, Desmos suitability, parameter constraints and a verifier. Output is formatted the SAT way: 4 choices or numeric entry. Parameters are tuned to match official exemplars. Difficulty labels are recalibrated after her first 30 attempts on a family.
- **R&W items.**
  - Claude drafts each item to the official skill specification, using official items only as structural exemplars.
  - **Similarity guard:** n-gram overlap with any official passage must stay under a threshold.
  - Every wrong choice maps to a named trap.
  - A blind solve by a second model must match the key, and the second model is asked whether any other choice is defensible.
  - Passages run 25–150 words.
- **Matt reviews.** He approves every item in `/admin/corpus` until 200 have been reviewed with under 2% errors. After that he samples 1 in 5. The weekly digest shows the queue.
- **Calibration rule.** If her accuracy on generated items in a cell is more than 10 points off her accuracy on official items in the same cell, after 30+ attempts, that cell's generated items are pulled and recalibrated.

### 8.5 Rights and guardrails

College Board content, and any purchased books, belong to their publishers. Peak is built for **private, single-household study use of material Matt downloaded or bought**:

- auth-gated, with no public URLs and no sharing
- never committed to Git or redistributed
- manual downloads and scans only, with no scraping
- purgeable by source in one command

This keeps the exposure narrow. It does not make it a licensed use; each publisher's terms govern, and I'm not a lawyer. The repo ships with zero official content. [College Board permissions](https://privacy.collegeboard.org/copyright-trademark/request-instructions)

### 8.6 What AI does and doesn't do

| Task | Model | Guardrail |
| --- | --- | --- |
| Official item extraction | `MODEL_ID` (vision), Batch API | Official key, blind solve by `MODEL_CHECK_ID`, human audit sample |
| Screenshot and score-report intake | `MODEL_ID` (vision) | She confirms every row. Uncertain fields stay blank. |
| Scratch-work reading and first wrong step | Ported Belay read → confirm → feedback jobs | Transcription never sees the key. Feedback abstains when the image is unclear. |
| Generated R&W items and template drafting | `MODEL_ID` drafts, `MODEL_CHECK_ID` checks | Similarity guard, trap mapping, blind solve, Matt's review, calibration. Done at authoring time, never live. |
| Weekly digest narrative | Summarizes computed stats | Every number comes from SQL. |
| **Never** | — | Generate a scored item during a session. Decide math correctness (that's deterministic). Compute scaled scores. Reveal answers in timed mode. |

**Budget.** `PEAK_COST_LIMIT_MONTH` is checked before every provider call, with Peak's own Anthropic key so its spend stays separate from Belay's. Ongoing use should run to single-digit dollars a month.

## 9. Architecture

Peak runs as **its own Compose project on the `belay-app` Droplet**, with its own repo, containers, Postgres, files, secrets, backups and deploys. The apps share only the host and a small edge proxy that owns ports 80 and 443. The stack is the same proven pattern as Belay: Next.js, FastAPI, a Python worker, Postgres and Caddy. Belay's hardened modules are copied in once, and there are no runtime calls between the apps.

&#91;embedded content: Peak architecture · a separate Compose project beside Belay on one Droplet, behind one edge proxy\]

Each app's database and worker stay on its own private network. Only the `web` and `api` containers join the shared `edge` network. Model calls leave only from Peak's worker, through its own key and budget.

### 9.1 Sharing the Droplet safely

| Concern | Decision |
| --- | --- |
| **Capacity** | Belay's container limits already total about 1.8 GB (proxy 128 MB, web 256, api 512, worker 640, Postgres 256). Peak adds about 1.9 GB (web 256, api 512, worker 768 for PDF rendering, Postgres 384). The Droplet's size was never confirmed (shown as a $12/month estimate). **Resize to 2 vCPU / 4 GB / 80 GB (about $24 a month) before P1**, with 2 GB swap. Move to 8 GB only if memory pressure shows during ingestion. Take a snapshot before resizing, because the resize needs a short power-off. |
| **Ports 80/443** | Only one process can own them. Move Caddy out of Belay's Compose into a tiny `edge` project (`/opt/edge`) on an external Docker network named `edge`. Its Caddyfile routes `belay.mturner.work` to Belay and `peak.mturner.work` to Peak. This is one small Belay infra PR (P0) and the only change Belay needs. |
| **Isolation** | Compose project name `peak`; its own internal network; its own Postgres container. A single shared Postgres server would save about 250 MB, but it couples upgrades and restores. Data lives in `/srv/peak/data/{postgres,files}`, releases in `/opt/peak`, secrets in `/etc/peak/peak.env`. Peak has its own Anthropic key and database credentials. |
| **Deploys** | A separate GitHub workflow, image tags and a `deploy.sh` scoped by project name. A Belay deploy never restarts Peak, and vice versa. |
| **Contention** | Ingestion runs at worker concurrency 1, preferably overnight, at a lower process priority. Alerts fire at 75% disk and on sustained memory pressure. |
| **Backups** | Peak's own nightly encrypted backup timer, staggered one hour after Belay's, to a separate Spaces prefix, with its own restore drill. Weekly DigitalOcean Droplet backups add a second layer. |
| **Accepted risk** | A host failure, a full disk or a patch reboot takes down both apps. That is acceptable for a family tool with tested restores. |
| **DNS** | `peak` A record → `134.209.209.174` in Cloudflare. Caddy issues the certificate; use Full (strict) if proxied. |

**Copied from Belay (one time, then owned):** `auth.py`, `provider_usage.py` and `provider_keys.py`, job lease and recovery from `worker.py`, `upload_admission.py`, `images.py`, `logs.py`, the read, confirm and feedback jobs for scratch work, the `infra/*` scripts and the CI workflows. **Not copied:** Belay's domain code, database and accounts.

### 9.2 Backend modules (`services/backend/peak/`)

| Module | Owns | Must not |
| --- | --- | --- |
| `exam.py` | SAT sections, module timing, item formats, tools and entry rules, held as data | Compute scaled scores (Bluebook only) |
| `taxonomy.py` | Official domain → skill tree, domain weights, her micro-skills and cues | Invent skills outside the official specs without a micro-skill parent |
| `corpus/ingest.py` | Upload, fingerprint, render, segment, extract, verify, lock, publish | Publish unverified items, or drill benchmark forms |
| `corpus/generate.py` | R&W drafting, similarity guard, blind check, Matt's review queue | Release without approval |
| `templates/` + `verify.py` | Math families, SymPy plus numeric verification, calibration | Release on an unknown or timed-out verification |
| `items.py` / `entry.py` | Item and version store, assets, student-safe projection / numeric-entry rules mirrored in TypeScript | Send a key before an attempt exists |
| `attempts.py` | Append-only attempts, idempotency, first exposure by Question ID, family and version | Mutate an attempt |
| `diagnose.py` / `tickets.py` | Cause proposal / verification ladder and evidence rules | Count same-family or assisted evidence |
| `srs.py` | `py-fsrs`, behavior-to-rating mapping, monthly optimizer | Let the student self-rate |
| `priority.py` / `composer.py` | Drill priority, session assembly, school-test throttle | Build an unbounded backlog |
| `benchmarks.py` | Form ledger, clean and exposed series | Put a dirty result in the clean trend |
| `scratch/` | Ported paper-reading pipeline | Show the key to transcription |
| `api.py` | `/api/*` routers with role and ownership guards | Skip the household check |

### 9.3 Data model (Postgres, additive Alembic migrations)

| Table | Key fields | Notes |
| --- | --- | --- |
| `skills` | id, section, domain, skill, micro\_skill, parent\_id, domain\_weight, cue | Official specs plus her micro-skills |
| `source_documents` | sha256 (unique), kind (qbank\_export, practice\_test, bluebook\_screens, book\_scan, scratch), rights, export\_filter\_json, status | One row per uploaded file |
| `items` / `item_assets` / `item_checks` | origin (official, template, generated), source\_ref (Question ID), skill\_id, family\_id, difficulty, format, benchmark\_locked, status, content, key, rationale / figure crops / each verification check with model and receipt IDs | Official text is stored only under `rights = private_official` |
| `templates` | skill, renderer, constraints, trap type, desmos\_ok, verifier report, calibration | Generator code lives in Git |
| `forms` / `benchmarks` | label, status (unseen, reserved, used, exposed) / section and total scores, M2 tiers, conditions, clean (derived), domain bands | The form ledger |
| `sessions` / `attempts` / `events` | purpose, mode / item, version, params, first exposure, answer, correctness, confidence, time, flags, Desmos use, idempotency key / (session, seq) telemetry | Attempts and events are append-only |
| `tickets` / `ticket_evidence` | skill, cause, cue, state, intervention, next due, timing\_required / which attempts counted and why |  |
| `cards` / `card_reviews` / `plans` / `school_tests` | FSRS state / ratings / targets, cadence, test dates / her school calendar |  |

### 9.4 API, web and runner

- **API.** `GET /api/today`, sessions with idempotent event batches, attempts with review and scratch, the student-safe item render, tickets, cards, benchmarks, progress, digest and export. Corpus upload, review and approval are parent-only.
- **Web routes.** `/` (Today), `/run/[session]`, `/review/[attempt]`, `/tickets`, `/benchmarks`, `/cards` (phone-first), `/progress`. For Matt: `/admin/corpus` (upload, audit, approve) and `/admin/digest`.
- **Runner.** Bluebook-style module timing, tools and keyboard shortcuts. Desmos is configured to College Board's SAT setup: images, folders and notes off, log mode for regressions on. Telemetry is buffered in IndexedDB, flushed every 5 seconds and on `visibilitychange`, and deduplicated on the server. [College Board Desmos configuration](https://desmos.com/assessment-pdfs/CollegeBoard_Desmos_Calculator_AP_SAT.pdf) · [Desmos API](https://www.desmos.com/api)
- **Rendering.** KaTeX for math. Official figures are served only as private, authenticated images.

### 9.5 Jobs, operations and security

- **Worker job kinds.**
  - Ingest: `ingest_render`, `ingest_extract`, `ingest_verify`, `ingest_publish`.
  - Generation: `gen_rw_draft`, `gen_rw_check`, `template_calibrate`.
  - Scratch work: `scratch_read`, `scratch_feedback`.
  - Housekeeping: `stats_refresh`, `digest_weekly`, `fsrs_optimize_monthly`.
- All model calls go through `parse_with_receipt`, `PEAK_COST_LIMIT_MONTH` and `INGEST_COST_LIMIT`. Logs carry allowlisted fields only, with no item text, answers or file names.
- Readiness reports DB, worker heartbeat, job age, ingest backlog, and disk and memory headroom.
- Dependencies: `fsrs` (py-fsrs), `sympy`, `pymupdf`, `katex`. No Redis and no new vendors.

## 10. Metrics and launch gates

The one number that matters is the **clean Bluebook trajectory**. Everything else is a leading indicator or a guardrail, and the dashboard says which.

| Tier | Metric | Definition | Target |
| --- | --- | --- | --- |
| North star | Clean Bluebook trajectory | Section and total scores on unseen, single-sitting Bluebook forms. Show the last 2–3 with dates and spread. | Total +40 per 6 weeks in the base phase |
| Leading | Fresh mixed accuracy | Correct ÷ all assigned (skips count as wrong), first exposure, unaided, by skill and difficulty | Medium ≥ 85%, Hard ≥ 60% in weak domains before upgrading timed work |
| Leading | Delayed transfer rate | Fresh mixed checks passed at 7+ days ÷ eligible checks. Overdue and no-fresh-item counts shown separately. | ≥ 75% |
| Leading | Repeat loss | Misses per comparable set, by cause and micro-skill | Plug-back and requested-quantity misses trend to near zero |
| Leading | Risk despite correct | Guessed-right ÷ attempted, and Sure-wrong ÷ Sure | Sure-wrong under 5% |
| Leading | Timed Module 1 accuracy | Accuracy on full-length timed single modules | R&W ≥ 85%, Math ≥ 80% before Hard Module 2 work |
| Guardrail | Engagement | Sessions a week, minutes, her usefulness rating, overrun rate | 3 a week, rating ≥ 4/5, overrun under 20% |
| Guardrail | Trust | Intake edit rate, disputed explanations, template key errors | Under 10%, under 2%, zero |
| Guardrail | Cost and effort | Model spend; Matt's minutes a week | Under the cap; under 15 minutes |

**Gates**

- **Phase 1 exit:** she uses Peak 3 times a week for 3 straight weeks without prompting. At least 80% of baseline Bluebook misses are triaged into tickets. Intake edit rate is under 10%, and the corpus audit finds under 1% extraction errors.
- **Phase 2 exit:** every template passes its verifier, with zero key errors in a 200-instance audit. The numeric-entry validator matches College Board rules on a golden set. Generated items land within 10 points of her accuracy on official items in the same cell.
- **Phase 3 exit:** runner telemetry loss is under 0.5% of events. A timed module matches Bluebook's timing to the second.
- **Stall rule:** if two clean benchmarks 6+ weeks apart move less than about 40 points, which is within normal cross-form noise, diagnose before adding volume. Check whether the bottleneck is new material, difficulty, speed, the intervention, or form noise. Change one thing and test it on comparable fresh items.

## 11. Build sequence

The work packages use Belay's `docs/ROADMAP.md` format so a coding agent can pick them up. Each is one PR, run in order, with the full verification suite before each push. **The June 5, 2027 SAT is a hard deadline:** the timed runner (P14) must ship by May 15.

**Phase 0 (owner actions, December 2026, no code).**

- **Host.** Check the Droplet's current size, snapshot it, then resize it to 2 vCPU / 4 GB / 80 GB.
- **Accounts.** Add the `peak` DNS record. Create the `thematthewturner/peak` repo, a Spaces prefix and a separate Anthropic key.
- **Baseline.** Enter the October 2026 PSAT. She takes the Bluebook test preview, then one unseen full Bluebook test in a clean single sitting.
- **Register** for the June 5, 2027 SAT before College Board's deadline.
- **Gather everything (D2).** Question Bank exports for all domains and difficulties, plus the SAT and PSAT paper practice tests.
- Until P5 ships, she practices in the official Question Bank directly.

| Phase | WP | Scope | Size | Depends on |
| --- | --- | --- | --- | --- |
| 1 | P0 | **Belay PR:** move Caddy into the `edge` project, add the external `edge` network and route both hostnames | S | resize |
| 1 | P1 | Bootstrap the Peak repo from Belay's hardened modules. Compose project `peak` joins `edge`. Own CI, deploy and backup timer. | M | P0 |
| 1 | P2 | SAT exam definition, taxonomy, core schema, CLI accounts | M | P1 |
| 1 | P3 | Source upload, fingerprinting, render and segment | M | P2 |
| 1 | P4 | Extraction, verification checks, benchmark lock, review and audit UI | L | P3 |
| 1 | P5 | Item store, student-safe render, item player, numeric-entry validator | M | P4 |
| 1 | P6 | Attempts, benchmarks and form ledger, screenshot intake | M | P5 |
| 1 | P7 | Miss and guess review, `diagnose.py`, ticket ladder and evidence rules | M | P6 |
| 1 | P8 | Priority scheduler, session composer, Today, school-test throttle | M | P7 |
| 1 | P9 | FSRS rule cards and phone UI | M | P2 |
| 1 | P10 | Progress view, weekly digest, export | S | P8 |
| 2 | P11 | Port the scratch-work read, confirm and feedback pipeline | M | P6 |
| 2 | P12 | Template framework, verifier, calibration, first 10 math families | L | P5 |
| 2 | P13 | Dual-solution tabs, and FSRS math cards rendering fresh variants | M | P9, P12 |
| 3 | P14 | **Timed runner**: Bluebook tools, Desmos, module trainers, Hard Module 2 simulator, IndexedDB telemetry | L | P5 |
| 3 | P15 | Generated R&W pipeline: draft, similarity guard, blind check, Matt's review queue, calibration | L | P4 |
| 3 | P16 | 15 more math families | M | P12 |
| 4 | P17 | FSRS optimizer and pacing dashboard | M | P13, P14 |
| 4 | P18 | Tutor handoff PDF and item-bounded coaching chat | M | P13 |
| 4 | P19 | Optional read-only Belay feed for school tests and current unit | S | P8 |

**Target dates:**

- Phase 0: December 2026.
- Phase 1: early February 2027.
- Phase 2: March 2027.
- Phase 3: runner by May 15, 2027, ahead of the June 5 SAT.
- Phase 4: summer 2027, before the junior-year push.

## 12. Risks and the strongest alternatives

### Steel-man: buy instead of build

**The case.** The official stack is free and very good: Bluebook, the Question Bank, and Khan Academy linked from My Practice. Add Acely or PrepPros (about $49–149 a month) or a UWorld QBank (about $249–449, per Matt's research; prices unverified). That gets mature content and analytics tomorrow, with zero build risk. The biggest hidden cost of building is that Peak becomes Matt's project instead of Addison's study habit.

**Why build anyway.** No product combines her Algebra 2 error profile, scratch-paper step diagnosis, school-test awareness and one private, verified SAT corpus. Belay's hardened modules can be copied in, so Phase 1 is mostly schema, ingestion and screens.

**Hedge.** Phase 0 starts real studying now using only official tools. Kill criterion: if by March 2027 she isn't choosing Peak 3 times a week, stop building and buy a commercial bank.

### Steel-man: give Peak its own Droplet

**The case.** Full isolation. A Belay deploy, a full disk or a memory spike can never touch Peak.

**Why share.** One host to patch, monitor and back up, at the same monthly cost, since the shared host needs a resize anyway. Separate Compose projects, networks, databases and deploys keep the logical isolation.

**Guard.** Memory limits per container, overnight ingestion, alerts, and tested per-app restores. If contention shows up twice in a month, move Peak to its own Droplet. That takes an afternoon, because its data paths and deploys are already separate.

### Risks

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| Logging friction kills use | Medium | High | Two-tap reviews, screenshot intake, phone batch grid; weekly usefulness rating |
| Hard official items run out in weak cells | High by junior spring | Medium | Bluebook reserves, templates, reviewed generated items, paid bank as a trigger (D6) |
| Phase 3 crunch before June 5 | Medium | High | The runner (P14) can start right after P5, in parallel with Phase 2 |
| Matt's review queue becomes a bottleneck | Medium | Medium | Batch review in the weekly digest; sampling at 1 in 5 after 200 clean reviews |
| Shared-host contention or outage | Low–Medium | Medium | Resize, container limits, overnight ingestion, alerts, Droplet backups plus app backups |
| A bad AI explanation or key teaches the wrong thing | Medium | High | No live item generation, checker model, Matt's review, "you graded this wrong" dispute flow |
| Junior-year overload and burnout | Medium | High | Hard caps, no streaks, school-test throttle, taper weeks around AP exams |
| Score noise read as progress or regress | High | Medium | Clean-series rules, the 40-point stall rule, trends over the last 2–3 results |
| Rights or terms problem with official content or Desmos | Low–Medium | Medium | Private and auth-gated, manual downloads only, purge by source (§8.5); confirm Desmos terms (D4) |

## 13. Decisions

### Decided November 27, 2026

| ID | Decision | What it means for the build |
| --- | --- | --- |
| D1 | **SAT only, hyper-focused** | One exam definition, one taxonomy, one runner, one score trend. The ACT is out of scope. |
| D2 | **Private storage of every official SAT item we can get** | Full Question Bank, all SAT and PSAT practice tests, her own reports, and optional book scans, under the §8.5 guardrails |
| D3 | **Sit the June 5, 2027 SAT** | Register in Phase 0. The timed runner ships by May 15, 2027. |
| D8 | **Name: Peak** | Repo `thematthewturner/peak`, host `peak.mturner.work`, package `peak` |
| D9 | **Same Droplet as Belay** | A separate Compose project, the edge-proxy split (P0) and a resize to 4 GB |
| D10 | **Matt reviews generated R&W items** | He approves every item until 200 are reviewed with under 2% errors, then samples 1 in 5. The queue appears in the weekly digest. |

### Still open

| ID | Decision | Recommendation | Needed by |
| --- | --- | --- | --- |
| D4 | Desmos API key and terms for private use | Request a key and confirm the terms. If they don't allow it, link out to desmos.com/testing instead. | Before P14 |
| D5 | Does Addison co-design? | Yes. She tests every Phase 1 screen and has veto power on friction. | Before P5 |
| D6 | Paid content trigger | Buy a UWorld QBank only if official plus generated supply fails calibration in a weak cell | Junior fall 2027 |
| D7 | Testing accommodations | If any are relevant, start the College Board request through the Wando counselor early | 3+ months before June 5, 2027 |
| D11 | Droplet resize | Confirm the current size, snapshot, then resize to 2 vCPU / 4 GB / 80 GB. Go to 8 GB only on measured pressure. | Before P0 |

### Sources

- Matt's research inputs: *Engineering a Local Digital SAT Prep App* and *Digital SAT Max-Score App Blueprint* (Nov 27, 2026)
- Belay repository, as the pattern source: `README.md`, `docs/PRD.md`, `docs/STATUS.md`, `docs/ROADMAP.md`, `infra/compose.yaml` ([thematthewturner/belay](https://github.com/thematthewturner/belay))
- [SC CHE Palmetto Fellows 2027 info packet](https://che.sc.gov/sites/che/files/Documents/Counselors%20Page/PFS_Info_Packet_Student_2027.pdf) · [CHE award amounts](https://che.sc.gov/node/72)
- [College Board: Bluebook new features, fall 2026](https://bluebook.collegeboard.org/test-admin/new-updated-features) · [Question Bank](https://satsuite.collegeboard.org/practice/student-question-bank) · [June 5, 2027 SAT](https://satsuite.collegeboard.org/dates/june-5-2027-sat-test-date)
- [Desmos API](https://www.desmos.com/api) · [FSRS optimizer (PyPI)](https://pypi.org/project/FSRS-Optimizer/)
