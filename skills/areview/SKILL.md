---
name: areview
description: "Multi-role agentic review & revise orchestrator. Takes a TASK and/or a FILE, spins up parallel fresh-context subagents in different expert roles (critic, researcher, editor). Agents search the web, verify claims, and either write findings (critic mode) or apply changes (editor mode). Runs BLIND by default (sanitized artifact, no access to prior reviews) for objectivity against groupthink, with a convergence stop rule. Triggers: /areview, areview, blind review, multi-role review, critique and revise, agentic review."
---

# AREVIEW — agentic multi-role review & revise

## Purpose

Review **and optionally revise** any artifact (plan, doc, code, config) using
parallel fresh-context subagents acting in distinct expert **roles**. Unlike
`aplan` (read-only plan review), `areview`:

- Accepts **a task, a file, or both**
- Assigns agents **different roles** (critic / researcher / editor)
- Agents **search the internet** to verify claims against current best practice
- Agents can **write changes** (editor role) or **only critique** (critic role)
- **Runs BLIND by default** (fresh context + sanitized artifact, no access to
  prior reviews) for objectivity against groupthink, with an explicit
  **convergence stop rule**

> **Blind is the default for objectivity.** Only drop blind mode when you
> deliberately want agents to build on a known prior review (rare). Blind
> rounds produce distinct findings each pass and even *revert* wrong
> recommendations from earlier rounds; anchored rounds mostly confirm each
> other.

## When to use

- Stress-testing a plan/spec/doc before execution
- Fact-checking claims against live sources (web search)
- Iterative hardening: critique → revise → re-critique until convergence
- Any task where one orchestrator should stay in control while specialist
  agents contribute findings or edits

## Inputs

| Input | Required | Notes |
|-------|----------|-------|
| `file` | optional | Path to artifact under review (plan/doc/code). Pass absolute path to each agent. |
| `task` | optional | What to review/achieve. At least one of file/task required. |
| `roles` | optional | Which roles to spawn (default: critic ×3). |
| `mode` | optional | `critic` (write findings only) or `editor` (apply changes). Default critic. |
| `blind` | optional | **Default ON.** Sanitize artifact + forbid reading prior reviews. Disable only to deliberately anchor on a known review. |
| `rounds` | optional | Max blind rounds (default 3, hard max ~5). |

## Roles (mix & match)

- **critic** — find errors, weak assumptions, logical/math holes. Write a
  findings report. NO edits. Must cite sources (URLs) and give GO/NO-GO + a
  maturity score (1-10).
- **researcher** — search the web to verify/refute the artifact's factual
  claims (APIs, deadlines, best practices, benchmarks). Report with URLs.
- **editor** — apply concrete changes to the file (only in `mode: editor`).
  Must explain each edit. Runs AFTER critics in a chain, never in parallel
  with other editors on the same file.
- **domain specialists** (optional) — measurement/bidding, safety, ops,
  migration, UX, security, etc. Define ad-hoc per task.

## Workflow

### A. Critic round (default, parallel)
1. Parent prepares inputs (file path + context).
2. Parent launches 2-4 critics/researchers in **parallel, fresh context**.
3. Each agent reads ONLY the artifact + named data files, **uses its own web
   search / tools as it sees fit** (they are experts — don't prescribe a
   specific search command), writes a findings report to its `output` path.
4. Parent synthesizes findings and applies fixes itself (or via editor round).

### B. Editor round (mode: editor, chained)
1. Parent passes synthesized findings to a single **editor** agent.
2. Editor applies edits to **the annotated ORIGINAL file**, explains each change.
3. Re-run a critic round to verify (loop).

> 🔴 **Editor ↔ blind reconcile (critical):** the sanitized copy is for
> **critics/researchers only**. The **editor always edits the real annotated
> original**, never the `/tmp/*-clean.md` copy — otherwise edits land in /tmp
> (lost) or, if copied back, wipe the provenance/changelog the sanitizer
> stripped. Blind applies to *reading for critique*, not to *writing fixes*.

### C. Blind iterative hardening (recommended for high-stakes artifacts)
Repeat critic rounds until **convergence**. Each round is **fresh context** so
agents never see prior reviews — this prevents groupthink and lets later rounds
*correct* earlier mistakes.

Per-round loop (strict order):
1. **(Re)sanitize** the CURRENT artifact → clean copy; run leak-verify until 0.
   (Re-sanitize every round: the parent's last edits added fresh provenance.)
2. Launch fresh blind critics on the clean copy.
3. Synthesize; apply **minimal literal** fixes to the annotated original.
4. Check the stop rule. If not converged, go to 1.

> The single biggest failure mode is skipping step 1's re-sanitize after edits,
> or stripping only obvious `review/revision` words. Both yield false
> convergence. Always run leak-verify to 0 on the resolution-vocabulary regex.

## Naming & paths

- `output` = **absolute path** per agent (Constraints require absolute paths).
- Convention: `<repo>/research/<area>/<TAG>_review_<N>.md` if the project has a
  `research/` dir; otherwise `/tmp/<TAG>_review_<N>.md`. Create the dir first.
- `TAG` = round label (BLIND / CLEAN / ROUND2 ...). `N` = agent index in round.
- Parent picks concrete values; nothing in the file is a literal placeholder.

## 🔒 BLIND DISCIPLINE (critical — learned the hard way)

Fresh context alone is NOT enough. **The artifact itself leaks prior reviews.**
If the file contains annotations like "fixed by review #4", "REVISION 3",
agents see them and steer away from those areas — defeating the blind purpose.

### ⚠️ The subtle trap (learned the hard way — cost ~3 extra rounds)

The obvious leaks ("review #N", "blind run", "REVISION") are easy to strip. But
**provenance hides in words that never mention review at all.** A line like:
- "dispute resolved by direct API query"
- "ALIGNED with step 1" / "consistent with Task 11"
- "VERIFIED" / "confirmed" / "agreed" / "settled"
- "(intentional buffer)" / "deliberately deferred"

...silently tells a fresh agent **"this zone is already decided, don't dig"** —
producing **false convergence**. In one campaign, an artifact looked "converged"
across 5 rounds; a run on a copy stripped only of `review/revision/round`
**still** missed a logical error, because internal "resolved/aligned/verified"
markers kept agents anchored. The error surfaced only after stripping THOSE too.

**Rule:** strip ALL of these classes before a blind round:
1. Explicit review trail: `review #N`, `REVISION N`, `round N`, `blind/anchored`
2. Resolution markers: `resolved`, `verified`, `confirmed`, `agreed`,
   `dispute settled`, `aligned/consistent with step/task N`
3. Intent justifications that defend a past choice: `(intentional ...)`,
   `(deliberate buffer)`, `corrected to`, `NOT X — actually Y`
4. Changelog/provenance headers and "Sources: *_review_*.md" lines

Replace with the **plain claim** (keep the fact, drop the defense). E.g.
"ALIGNED with step 1: ≥14 days" → "≥14 days". "VERIFIED via API: both
budget-bound" → "both budget-bound".

Pass the sanitized copy to critics. Keep the annotated original for the editor.

```bash
# sanitizer template — ADAPT patterns + ADD your domain's resolution words
python3 - << 'PY'
import re
src = 'plan.md'; out = '/tmp/plan-clean.md'
s = open(src).read()
pats = [
  r'\s*\((?:fixed|found|caught) by[^)]*\)',
  r'\bREVISION \d+\b', r'\bround #?\d+\b', r'\(review #?\d+\)',
  r'\b(?:слепой|блайнд|anchored)\b[^.\n]*',
  # resolution / provenance markers (the subtle trap):
  r'\s*—?\s*(?:СОГЛАСОВАНО|aligned|consistent) (?:со?|with) [^.\n]*',
  r'\b(?:ВЕРИФИЦИРОВАНО?|VERIFIED|confirmed|разрешён|resolved|Спор ревью[^.\n]*)\b',
  r'\(исправлено[^)]*\)', r'\(нашли[^)]*\)', r'\(areview[^)]*\)',
]
for p in pats:
    s = re.sub(p, '', s, flags=re.I)
open(out,'w').write(s)
# leak-verify: ANY residue of review/resolution vocabulary = NOT clean
leak_re = r'review|revision|ревь|ревиз|слеп|согласован|верифиц|verified|resolved|aligned|areview'
leaks = [l for l in s.splitlines() if re.search(leak_re, l, re.I)]
print('LEAKS:', len(leaks))
for l in leaks: print('  >', l)
assert not leaks, 'NOT clean — add patterns until LEAKS:0 before running blind'
PY
```

> **Provenance can also live OUTSIDE the artifact.** If the plan cites a source
> file (e.g. `GADS_STATS.md`) that itself carries stale "recommends Task 2-3"
> conclusions from a since-reverted strategy, agents may "restore" the reverted
> decision. Either pass a sanitized source too, or flag stale source-conclusions
> as historical.

## 🛑 CONVERGENCE STOP RULE

Stop blind rounds when BOTH hold:
- **(a)** the round surfaced **no NEW strategic finding** (binary check — more
  robust than comparing 1-10 scores, which different fresh agents calibrate
  differently), AND
- **(b)** findings shifted from "what's wrong / suboptimal" (strategy) to
  "typos / checklist-out-of-sync" (mechanics).

Maturity scores are a secondary signal only (treat ±1 as noise — independent
fresh critics disagree by that much). ~5 rounds is a reasonable hard maximum.
Once a round produces only mechanical sync fixes, returns are exhausted — stop
and execute.

### ⚠️ Parent edits can INJECT new bugs — each round may correct the last

Observed repeatedly: the parent applies a round's fix, and the **next** blind
round flags that the parent **mis-stated the fix** (e.g. justified removing a
conversion by "its value distorts tCPA" — wrong, since tCPA bids on count, not
value). This is the method working as intended: blind rounds correct the
parent's own freshly-introduced errors. Implication:
- **After applying fixes, the artifact changed → re-sanitize before next round.**
- Don't treat "round N+1 found something in what round N edited" as failure to
  converge — it's the safety net catching your edit. Real convergence = a round
  finds nothing new in the **current** text, not that rounds stopped disagreeing.
- Keep parent edits **minimal and literal** to the finding; don't add reasoning
  the critic didn't give (that reasoning is unreviewed and often where new bugs
  enter).

### ⚠️ Distinguish "converged" from "frame exhausted"

A late round may report "no strategic errors" yet still surface **new strategic
findings that are reframings, not bugs** (e.g. "is the whole campaign even
incremental?" vs the plan's frame "optimize this campaign's bids"). These are
NOT stop-rule violations — they signal the plan has converged **within its
frame**, and remaining questions need an **experiment/execution** (geo-holdout,
A/B), not more text review. When findings become "change the frame" rather than
"fix the text", **stop reviewing and start executing** — file the reframings as
explicit deferred (P2) items so they aren't lost.

**Why blind helps (evidence, not law):** in one observed 5-run campaign-plan
hardening, anchored reviews mostly confirmed each other while blind rounds
produced distinct findings each pass and even *reverted* a wrong recommendation
from a prior round. Caveat (n=1, one domain): blind costs repeated work and can
oscillate (round N+1 undoes round N) — the parent holding the annotated original
and synthesizing across rounds is what prevents the pendulum. Use blind as the
default for **high-stakes** artifacts, not a universal law.

## Invocation pattern (subagent tool)

```
subagent({
  context: "fresh",
  concurrency: 3,
  tasks: [
    { agent: "delegate", output: "/abs/research/area/BLIND_review_1.md",
      task: "Role: senior <domain> critic. FIRST time seeing this. Goal: find
             SUBSTANTIVE errors. Be honest — if good, say so, don't invent
             problems. DATA (only these): <sanitized file>, <data file>. Do NOT
             read other review files. SEARCH WEB (cd skills/exa-search &&
             bash search.sh \"q\" 5 / bash content.sh \"url\" 3000) to verify
             claims. WRITE audit (md): 1.Errors+URLs 2.Missing 3.Doubtful
             assumptions 4.VERDICT GO/NO-GO/CONDITIONAL + maturity /10." },
    { agent: "delegate", output: "research/.../TAG_review_2.md",
      task: "Role: <second angle>. ... (different lens, same discipline)" },
    { agent: "delegate", output: "research/.../TAG_review_3.md",
      task: "Role: measurement/math checker. Verify ALL arithmetic + logic. ..." }
  ]
})
```

For an **editor** round, use a chain instead of parallel:
```
subagent({ context: "fresh", chain: [
  { agent: "delegate", task: "Critic: produce findings on {file} → {chain_dir}/findings.md" },
  { agent: "delegate", task: "Editor: apply fixes from {chain_dir}/findings.md to {file}, explain each" }
]})
```

## Constraints

- Critics/researchers must **not modify the artifact or any project/source
  files** — they only write their own findings report (passed via `output`).
  (Say "do not modify project/source files", not "no file writes", so the
  agent still writes its `output` artifact.)
- Only **editor** role writes, and only when `mode: editor`; never two editors
  on the same file in parallel.
- Reviews must not expose raw secrets, credentials, or private domains.
- Always pass **absolute paths**.
- For blind **critic** rounds: pass the **sanitized copy**, forbid reading other
  reviews. The **editor** round uses the **original** (see Editor reconcile).
- 🔴 **Blind gate:** do NOT start a blind critic round until the sanitized copy
  exists AND its leak-verify output is empty. No clean copy = not blind.
- **Secret hygiene:** never pass credential/secret files (e.g. `.credentials.md`,
  `.env`, token files) in an agent's data set. Exclude them from the file list.
- **Cost:** each round = 2-4 fresh agents (+ web search). 1-2 rounds suffice for
  most artifacts; reserve 3-5 blind rounds for high-stakes ones. Don't auto-loop.
- Ignore stale "needs attention" subagent signals — parallel runs complete
  (X/N succeeded) despite nudges.

## Output convention

- Findings: `research/<area>/<TAG>_review_<N>.md` (TAG = BLIND/CLEAN/ROUND etc.)
- Parent synthesizes + applies, then logs a one-line summary of what shifted
  this round (strategy finding vs mechanical sync) to track convergence.
