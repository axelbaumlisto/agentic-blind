# agentic-blind

Agentic skills for [pi](https://github.com/badlogic/pi-mono) implementing a
plan → blind-harden → gated-execute pipeline with adversarial agent
boundaries.

**Blind critics solve the bias problem.** When reviewer agents see prior
reviews — or even subtle resolution markers left in the artifact ("resolved",
"verified", "aligned with step 1") — they anchor on past conclusions,
confirm each other, and steer away from "already decided" zones, producing
false convergence. Each blind round here runs fresh-context critics on a
sanitized copy with all provenance stripped: no groupthink, no anchoring,
no self-confirmation. Blind rounds find distinct issues each pass and can
even revert wrong recommendations from earlier rounds — anchored reviews
mostly just agree with themselves.

```
/plan  →  /aplan (blind plan review)  →  /ado (gated execution)  →  areview (code audit)
```

## Skills

| Skill | Purpose |
|---|---|
| **plan** | Create structured implementation plans (`Files:`/`Depends:`/`Acceptance:`/`Verify:` per task) |
| **aplan** | Plan review preset: 2-4 parallel read-only critics (architecture, safety, ops, migration) |
| **areview** | Multi-role blind review & revise: fresh-context critics on a **sanitized** artifact, convergence stop rule, code-mode roles (integration/conformance/edge-case) |
| **ado** | Plan executor: worker→reviewer gates per step, git checkpoints, parallel independent steps, optional final areview over the full diff |

## Key ideas

- **Blind review**: fresh context alone is not blind — the artifact itself
  leaks prior reviews through resolution vocabulary ("resolved", "VERIFIED",
  "aligned with step 1"). `areview/sanitize.py` strips 4 leak classes and
  hard-gates on leak-verify = 0 (with an allowlist for false-positive stems).
- **Adversarial boundary**: the checker is never in the checked party's
  context. Reviewer is a NEW fresh agent every round; the worker keeps
  context (resume) on pointwise fixes, and is respawned fresh — after a tree
  revert — when the reviewer says the approach is wrong (REJECT-REDO).
- **Reviewer classifies** REJECT-FIX vs REJECT-REDO — it is the only party
  not invested in the step succeeding.
- **Git checkpoints**: mandatory clean baseline, verify-before-commit, one
  commit per approved step, revert = `reset --hard + clean -fd`.
- **Parallelism without worktrees**: isolation lives in the plan (disjoint
  `Files:` + scope-guard), one shared tree. Default sequential; doubt ⇒
  serialize.
- **Convergence stop rule**: stop when a round finds no NEW strategic issue
  and findings shift from strategy to mechanics. Reframings ≠ non-convergence.
- **Async agents**: worker and critic subagents are launched with
  `async: true` and drained via `subagent_wait` (poll with `action: "status"`).
  The fan-out never blocks the turn and one slow agent can't stall the batch;
  `ado` still keeps **one writer per shared tree** — the worker finishes and is
  drained before the fresh reviewer starts. Stale "needs attention" nudges are
  inspected, not obeyed — async runs complete regardless.

## Install

Copy skill directories into `~/.pi/agent/skills/` (user scope) or
`.pi/skills/` (project scope):

```bash
cp -r skills/* ~/.pi/agent/skills/
```

## Sanitizer

```bash
python3 skills/areview/sanitize.py plan.md /tmp/plan-clean.md \
  [--extra-words domain.txt] [--allow allow.txt] [--report-only]
```

On LEAKS > 0 no output file is written (exit 1) — normal on the first run;
iterate patterns/allowlist to 0. Test fixture included:

```bash
python3 skills/areview/sanitize.py skills/areview/test_fixture.md /tmp/x.md --report-only
```

## License

MIT
