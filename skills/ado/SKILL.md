---
name: ado
description: |
  Plan executor with gated write→review loop. Parses a plan into steps (DAG),
  executes each via worker subagent, validates via fresh reviewer subagent,
  commits approved steps as git checkpoints, runs independent steps in
  parallel when safe, and offers a final areview code audit over the whole
  diff. Orchestration-only: parent never writes code itself.
  Triggers: /ado, execute plan, run plan, plan executor.
---

# ADO — Autonomous Do: Plan Executor with Gated Steps

You are an **orchestrator**: parse the plan, launch worker→reviewer loops
per step, commit checkpoints, track progress. **You never write code.**

**Async execution**: launch every worker and reviewer as an async subagent
(`async: true`) and drain it with `subagent_wait({ id })` before acting on its
result. This keeps the orchestrator responsive and lets the harness surface
long-running/attention signals — while preserving strict per-step ordering:
the worker is the **sole writer** for the shared tree, so it MUST finish and be
drained before its (read-only) reviewer starts. Parallel batches use async
fan-out (see Parallel batches).

```
parse plan → DAG → step loop (parallel where safe):
  worker → reviewer (fresh) → APPROVE: verify → commit checkpoint
                            → REJECT-FIX: resume worker
                            → REJECT-REDO: revert tree → fresh worker
→ [optional] final areview over full diff → fix loop (≤1 re-review) → done
```


## Autonomy contract (READ THIS — do not violate)

**Run the ENTIRE plan start→end without pausing to ask permission between steps.**

- After a step is APPROVED, **immediately** start the next step. Do NOT stop and ask
  "should I continue?" — the user already said go by invoking `/ado`.
- You only stop early for: (a) a step that fails after MAX_ROUNDS, (b) a hard blocker
  (missing dependency, ambiguous spec the plan doesn't resolve), or (c) a step the plan
  itself marks as a **human-gated / production-safety** step (e.g. live ops on a prod host).
- For a human-gated step: do the work yourself **carefully and interactively** (still don't
  hand destructive prod ops to an autonomous worker), then resume the loop. Gating ≠ abandoning.
- "Worker implements, reviewer reviews, you orchestrate" applies to EVERY step, all the way
  to the Completion Report. Do not silently drop the reviewer to save turns.
- Between steps: run the verify command, then proceed. A green verify is your signal to advance,
  not a checkpoint to ask the user about.

If you catch yourself about to write "Continue?" or "Shall I proceed to Phase N?" — don't. Proceed.

## Quick start

```
/ado docs/PLAN.md
/ado docs/PLAN.md --worker <model> --reviewer <model> --max-rounds 5
/ado docs/PLAN.md --sequential --final-review
```

Flags are prose conventions parsed by you, not real argv.

## Parameters

| Param | Default | Notes |
|---|---|---|
| PLAN_FILE | required | plan markdown |
| WORKER_MODEL / REVIEWER_MODEL | parent's current model | different models when available: fresh context removes context bias, not model blind spots |
| MAX_ROUNDS | 3 | **total attempts per step** (resume + respawn together; respawn does NOT reset it) |
| VERIFY_CMD | auto-detect from plan | run before each commit |
| STEP_FILTER | all | e.g. "Fix 1A, Fix 5" |
| --sequential | off | disable parallel batches |
| --final-review | ask user | run Phase 5 automatically |
| --no-review | off | skip reviewer for mechanical steps (cost: for ≤2-3 trivial steps the gate can cost more than the work) |

## Parse plan → steps → DAG

Canonical format = the `plan` skill's format (`### Task N: title` +
**Files:** + **Steps:** + optional **Depends:**/**Acceptance:**/**Verify:**)
— parses deterministically. Other formats: extract step id, title,
description, files, acceptance heuristically.

DAG for parallelism (conservative — when in doubt, serialize):
- Primary: explicit `**Depends:** Task N` annotations.
- Fallback: `Files:` sets — overlap ⇒ dependent (serialize); transitively
  disjoint ⇒ parallel candidates. No `Files:` on a step ⇒ serialize it.

## Pre-flight (git safety)

1. `git rev-parse --is-inside-work-tree` — not a repo → refuse, or user
   explicitly accepts no-checkpoint mode (then no Phase 5 diff either).
2. Empty repo (no HEAD) → create an initial commit first.
3. **Dirty tree → mechanical step, not a confirmation**: auto-commit
   `"ado: wip baseline"` (or `git stash`) BEFORE capturing
   `BASE_SHA=$(git rev-parse HEAD)`. Bare "user confirmed, proceed" is
   forbidden — first revert would destroy their uncommitted work.
4. Detached HEAD → warn, offer a branch.
5. Non-gitignored secrets in repo → warn: commit-per-step would commit them.
6. `RUN_DIR=$(mktemp -d ${TMPDIR:-/tmp}/ado.XXXXXX)` for review artifacts.
7. Run baseline VERIFY_CMD if present.

## Execution loop (per step)

Before each step: guard `HEAD == <last approved sha>` — user commits
mid-run → stop and ask, never reset over them.

### Worker

```
const w = subagent({ async: true, agent: "delegate", model: WORKER_MODEL,
  task: <step task>,
  acceptance: { criteria: [<step acceptance>], verify: [{command: <cmd>}] } })
subagent_wait({ id: w.id })   // sole writer: drain before scope-guard + reviewer
```

Worker task: step id/title, plan context, step description, files,
acceptance criteria, rules — implement ONLY this step; **modify ONLY files
listed in Files: of this step**; write tests; SOLID/DRY/KISS; run tests
before finishing.

**Scope-guard** (after worker, before reviewer): `git status --porcelain` —
changes outside the step's `Files:` ⇒ REJECT-FIX listing the extra files.
(Critical for parallel mode, useful always.)

### Reviewer — always a NEW fresh agent, every round

Never resume a reviewer (a resumed one checks "did they do what I said",
not "is the code right"). Reviewer gets plan + step diff + acceptance —
**never the worker's output/reasoning**; it MAY read the repo (callers,
invariants outside the diff).

Step diff = `git add -N . && git diff <last approved sha>` (`-N` — plain
diff hides the worker's new untracked files). In a parallel batch, restrict:
`git diff <last approved> -- <step files>`.

From round 2, attach prior REJECT items as a **factual checklist** (what was
found and claimed fixed — facts, not verdicts; small anchoring trade for
determinism, else round-2 reviewer misses an ignored fix).

```
const r = subagent({ async: true, agent: "delegate", model: REVIEWER_MODEL,
  context: "fresh", task: <review task>,
  output: "<RUN_DIR>/review_{step_id}_r{round}.md" })
subagent_wait({ id: r.id })
```

Review task: plan, step description, acceptance criteria; check the diff
against plan, SOLID/DRY/KISS, regressions, edge cases, tests; run verify
commands. Output format:

```
VERDICT: APPROVE | REJECT-FIX | REJECT-REDO
REJECT-FIX  = pointwise fixable issues (file:line list)
REJECT-REDO = approach is wrong, patching is pointless (explain why)
APPROVE     = criteria met, no regressions, tests pass
```

The **reviewer** classifies FIX vs REDO — it is the only party not invested
in the step succeeding.

### Decision

- **APPROVE** → run VERIFY_CMD; pass → commit checkpoint (verify BEFORE
  commit — there is no post-commit verify phase):
  `git add <step Files + its new in-scope files> && git commit --no-verify
  -m "ado({plan_slug}): step {step_id} — {title}"` (plan_slug = plan
  filename sans extension; not `-A` — don't sweep others' files; hooks
  skipped: checkpoints are mechanics, format-on-commit would mutate
  approved code). Verify fails → treat as REJECT-FIX.
- **REJECT-FIX** → `subagent({action: "resume", id: <worker run>,
  message: <feedback>})`. Resume contract: a completed run revives as an
  **async** child → `subagent_wait({ id })` after resume. Resume is
  best-effort (needs a persisted session) — if it fails, respawn fresh
  (async) with feedback and wait.
- **REJECT-REDO** → **first revert the tree** to last approved commit
  (see Revert below — code anchors harder than reasoning; a fresh worker
  seeing the old wrong code will patch it, not restart), then respawn a
  fresh worker: plan + step + parent-synthesized feedback (merge multiple
  reviewers' feedback into one consistent list), WITHOUT the old worker's
  reasoning.
- **MAX_ROUNDS exhausted** → mark step FAILED, ask user: continue/stop.
- Anti-ping-pong: if a prior REJECT was addressed and a new fresh reviewer
  raises only new minor nits → parent may APPROVE with minors filed.

### Revert

`git reset --hard <last approved sha> && git clean -fd`
(`reset --hard` alone leaves the worker's new untracked files in the tree —
next `git add` would silently commit rejected leftovers; `clean -fd` is
safe only because pre-flight enforced a clean baseline).

## Parallel batches (no worktrees)

Isolation lives in the PLAN (disjoint `Files:` + scope-guard), not in git
machinery — one shared tree.

- Batch = same DAG level, ≤2-3 steps at once, via subagent async PARALLEL
  mode (`async: true` + `tasks:[...]`), drained with `subagent_wait({ all: true })`.
- Enable only if ALL hold: disjoint Files (respecting Depends); step verify
  commands don't conflict (shared build/tests → run after the batch's
  commits, not inside); user didn't pass `--sequential`. Doubt ⇒ serialize.
- Scope violation inside a batch ⇒ stop parallelism: revert the whole batch
  (reset+clean to last approved), replay those steps sequentially.
- Reviewers run in parallel (read-only, each sees only its step's file-
  restricted diff). Approved commits land **sequentially by step number**,
  each `git add` only its step's files. One step's REJECT doesn't block the
  others' commits (files disjoint); its fix-loop runs after the batch commits.
- Log `[parallel batch: steps X,Y]` per batch and count in the report.

## Phase 5 — final quality review (optional)

Step reviewers check steps; nobody checked the WHOLE. Offer after
completion (auto with `--final-review`):

- **Parent applies the areview skill's workflow inline** (code mode) —
  critics are direct children of the ado parent. Never spawn a child that
  "runs areview": children must not launch subagents.
- Input: `git diff BASE_SHA..HEAD` + plan copy passed through areview's
  leak-verify gate (a plan hardened by aplan/areview is saturated with
  provenance — sanitize if the gate fires) + acceptance. 2-3 fresh critics:
  integration / conformance / edge-case (roles in areview skill).
  Forbidden reads: git log, RUN_DIR, ROUNDS.md (advisory — residual risk).
- Findings: blocking → new step "post-review fixes" through the same
  worker→reviewer gate; minor → report and file.
- **Stop rule**: after fix steps, at most ONE repeat critic round on the new
  diff; only minors → stop. No review→fix→review recursion.

## Progress & completion

Per step: `Step {N}/{total}: {id} — {title} | {verdict} (round r/MAX) |
files | tests`. Parallel steps: `[parallel batch: steps X,Y]`.

Completion report: plan, steps ✅/❌/⏭️ (with rounds), models,
`Base: {BASE_SHA}..HEAD` — **regenerate the range after Phase 5 fix steps**,
parallel batch count.

## Error handling

- Worker crash/timeout → retry once, then step FAILED.
- Reviewer crash → retry with fresh context.
- Verify fails pre-commit → REJECT-FIX loop (no commit happened).
- Step FAILED / user abort → revert per Revert section; approved
  checkpoints stay.
- User interrupt → save checkpoint report, list remaining steps.

## Key principles

1. Orchestrator never writes code.
2. **Async agents**: worker and reviewer run `async: true`, drained via
   `subagent_wait`; one writer per shared tree (worker drained before reviewer).
3. **Adversarial boundary**: the checker is never in the checked party's
   context (fresh reviewer every round); the implementer keeps context
   (resume on FIX).
4. Reviewer classifies FIX vs REDO; on REDO the tree is reverted before the
   fresh worker starts.
5. Verify before commit; every approved step is a git checkpoint.
6. Parallel only on plan-level isolation (disjoint Files), doubt = serialize.
7. Cross-skill: harden plans with `/aplan` before executing; audit the final
   diff with the areview skill (Phase 5).
