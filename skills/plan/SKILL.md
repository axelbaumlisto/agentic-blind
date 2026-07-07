---
name: plan
description: |
  Create, list, load, and execute implementation plans. Use when user says /plan,
  "create a plan", "make a plan", "plan for", wants to break down a complex task,
  or references an existing plan. Also use when starting multi-step implementation work.
---

# Plan Management Skill

Create, store, list, and execute structured implementation plans.

Plans are markdown files stored in `~/.pi/plans/` (global) or `.pi/plans/` (project-local).

---

## Commands

### Create a plan: `/plan <description>`

1. **Analyze** the task/requirements
2. **Research** the codebase — read relevant files, understand structure
3. **Write** the plan as structured markdown (see format below)
4. **Save** to `~/.pi/plans/<slug>.md` or `.pi/plans/<slug>.md` if inside a git repo
5. **Report** plan summary with task count

### List plans: `/plan list`

List all plans from both `~/.pi/plans/` and `.pi/plans/`:
```bash
ls -lt ~/.pi/plans/*.md .pi/plans/*.md 2>/dev/null
```
Show: filename, first heading, task count, date.

### Load a plan: `/plan load <name>`

Read the plan file and display summary. Prepare to execute.

### Execute a plan: `/plan run <name>`

Load plan and execute tasks sequentially:
1. Read plan file
2. For each task: mark in-progress → execute → verify → mark done
3. After each task: commit if there are changes
4. After all tasks: run full verification

### Show current: `/plan status`

Show which plan is active, which tasks are done/remaining.

---

## Plan Format

```markdown
# <Plan Title>

## Context
<What problem we're solving, why, current state>

## Approach
<High-level strategy, key decisions>

## Tasks

### Task 1: <title>
**Files:** `path/to/file.rs`, `path/to/test.rs`
**Depends:** Task N (optional — gates /ado parallel execution)
**Acceptance:** <criteria> (optional — /ado review gate)
**Verify:** `cargo test` (optional — /ado runs before each commit)
**Steps:**
1. <specific step>
2. <specific step>
3. <verify step>

### Task 2: <title>
...

## Verification
<How to verify the whole plan is complete>
- [ ] All tests pass
- [ ] Lint clean
- [ ] Manual check: ...
```

## Rules

- **Each task = one logical change** (5-15 min of work)
- **Each task is independently testable** — can verify it works before moving on
- **Tasks list files they touch** — no surprises
- **Steps are concrete** — not "implement the feature" but "add field X to struct Y in file Z"
- **TDD when possible** — write test first, then implementation
- **Frequent commits** — commit after each completed task
- **No task depends on unwritten code from a later task** — tasks are ordered by dependency
- **State Depends: explicitly** when a dependency is not visible through files (build, migrations, external state) — /ado executes this format and parallelizes independent tasks

## Naming

Generate slug from plan title:
- `refactor-auth-module.md`
- `add-websocket-support.md`
- `fix-peer-registry-dedup.md`

## When creating plans

1. **Read the codebase first** — don't plan in the abstract
2. **Identify all files** that will be created or modified
3. **Check for existing tests** — plan should extend them
4. **Consider edge cases** — note them in tasks
5. **Include verification** — each task and final plan-level checks
6. **Break large plans into phases** — if >10 tasks, group into phases
7. **Harden high-stakes plans** with /aplan before executing

## When executing plans

1. **Read the full plan** before starting
2. **Raise concerns** if plan seems wrong — don't blindly execute
3. **Update plan** if reality diverges — add notes, mark tasks modified
4. **Don't skip verification steps** — they exist for a reason
5. **Commit after each task** with descriptive message referencing the plan
