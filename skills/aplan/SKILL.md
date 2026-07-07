---
name: aplan
description: "Multi-agent plan review preset: launches 2-4 read-only planner critics in parallel (architecture, safety, operations, migration) to research and stress-test a plan. Thin preset over the areview skill. Triggers: /aplan, plan review, review plan, stress test plan."
---

# APLAN — plan review preset over areview

aplan = the **areview** skill with a fixed preset:

- `mode: critic` (read-only — agents never modify the plan or source files)
- `roles`: **architecture** (design, data flow, queries/indexes),
  **safety** (data loss, rollback, interruption), **operations** (load,
  locks, downtime, monitoring), **migration** (step ordering, compatibility,
  feature flags) — pick 2-4 per plan; verify **Depends:/Files:**
  annotations too (a missed dependency between tasks = strategic finding,
  it gates /ado parallel execution).
- `blind`: ON for high-stakes plans. **Quick mode** for routine plans:
  one non-blind round, no sanitizer — keep it lightweight.

Workflow, sanitizer, convergence stop rule, naming, constraints — all from
the **areview** skill (load it by name; default install
`~/.pi/agent/skills/areview/SKILL.md`). No methodology lives here (DRY).

Output: areview's convention (`research/<area>/`, fallback `/tmp/`).
