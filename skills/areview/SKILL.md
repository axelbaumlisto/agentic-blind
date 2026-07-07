---
name: areview
description: "Multi-role agentic review & revise orchestrator. Takes a TASK and/or a FILE (plan, doc, code, diff), spins up parallel fresh-context subagents in expert roles (critic, researcher, editor; code: integration/conformance/edge-case). Agents verify claims (web search) and either write findings (critic mode) or apply changes (editor mode). Runs BLIND by default (sanitized artifact, no prior reviews) with a convergence stop rule. Triggers: /areview, areview, blind review, multi-role review, critique and revise, agentic review, code review."
---

# AREVIEW — agentic multi-role review & revise

Review **and optionally revise** any artifact (plan, doc, code, diff) via
parallel fresh-context subagents in distinct expert roles. Blind by default:
fresh context + sanitized artifact + no access to prior reviews — anchored
reviews mostly confirm each other; blind rounds find distinct issues and can
revert earlier wrong recommendations. Drop blind only to deliberately build
on a known review (rare).

**Skill dir** = directory containing this SKILL.md (default install:
`~/.pi/agent/skills/areview/`). `sanitize.py`, `leak_words.txt`,
`test_fixture.md` live there.

## Inputs

| Input | Required | Notes |
|-------|----------|-------|
| `file` | optional | Artifact path (plan/doc/code/diff). Absolute paths to agents. |
| `task` | optional | What to review/achieve. ≥1 of file/task required. |
| `roles` | optional | Default: critic ×3. |
| `mode` | optional | `critic` (findings only, default) or `editor` (apply changes). |
| `blind` | optional | Default ON. |
| `rounds` | optional | Max blind rounds (default 3, hard max ~5). |

## Roles

Prose artifacts:
- **critic** — substantive errors, weak assumptions, logic/math holes.
  Findings report only, NO edits. Cite sources (URLs), verdict
  GO/NO-GO/CONDITIONAL + maturity /10.
- **researcher** — web-verify factual claims (APIs, deadlines, benchmarks).
- **editor** — applies changes (only `mode: editor`), explains each edit.
  Runs AFTER critics in a chain; never two editors on one file in parallel.

Code artifacts (diff + plan + acceptance as input):
- **integration critic** — seams between changes, duplication, dead code,
  API consistency across the diff.
- **conformance critic** — does the whole delivered change match what the
  plan/spec promised.
- **edge-case/security critic** — races, boundaries, injections, error paths.

Domain specialists (safety, ops, migration, UX...) — define ad-hoc.
Model diversity: give critics different models (`model:` per task) when
available — fresh context removes context bias, not model blind spots.

## Workflow

**A. Critic round (default):** parent sanitizes artifact → launches 2-4
critics/researchers in parallel, fresh context → each reads ONLY the
artifact + named data files, uses its own web-search tools as it sees fit,
writes findings to its `output` path → parent synthesizes and applies
minimal literal fixes to the annotated original.

**B. Editor round (`mode: editor`, chained):** parent passes synthesized
findings to one editor; editor edits **the annotated ORIGINAL**, never the
sanitized `/tmp/*-clean.md` copy (edits would be lost or wipe provenance the
sanitizer stripped). Blind applies to *reading for critique*, not *writing
fixes*. Re-run a critic round to verify.

**C. Blind iterative hardening (high-stakes artifacts):** repeat per-round,
strict order:
1. **(Re)sanitize the CURRENT artifact** → clean copy, leak-verify to 0.
   Re-sanitize every round — the parent's last edits added fresh provenance.
2. Launch fresh blind critics on the clean copy.
3. Synthesize; apply **minimal literal** fixes to the annotated original —
   don't add reasoning the critic didn't give (unreviewed reasoning is where
   new bugs enter).
4. Check stop rule; if not converged, go to 1.

## 🔒 Blind discipline

Fresh context alone is not blind: **the artifact itself leaks prior
reviews**, and subtle resolution vocabulary ("resolved", "VERIFIED",
"aligned with step 1", "(intentional buffer)") silently tells fresh agents
"this zone is decided, don't dig" — producing false convergence even when
obvious "review #N" markers are stripped. Strip all 4 classes:

1. Explicit review trail: `review #N`, `REVISION N`, `round N`, blind/anchored
2. Resolution markers: resolved, verified, confirmed, agreed, aligned/consistent with step N
3. Intent justifications defending a past choice: `(intentional ...)`, `corrected to`
   — but on a **first-round** artifact these are legitimate author rationale;
   strip class 3 from round 2 onward.
4. Changelog/provenance headers, `Sources: *_review_*.md` lines

Replace with the plain claim (keep the fact, drop the defense):
"ALIGNED with step 1: ≥14 days" → "≥14 days".

```bash
python3 <skill_dir>/sanitize.py plan.md /tmp/plan-clean.md \
  [--extra-words domain.txt] [--allow allow.txt] [--report-only]
```

leak_words.txt loads by default; `--extra-words` adds domain vocabulary;
`--allow` holds false-positive regexes (stems: «согласованность»,
"unresolved", "left-aligned"). On LEAKS>0 no out file is written + exit 1 —
**normal on first run**; iterate patterns/allowlist to 0, don't weaken the
vocabulary. Provenance can also live in cited source files — pass sanitized
sources too, or flag their stale conclusions as historical.

### Code-mode carve-out (blind gate)

- **Prose artifacts:** no clean copy with leak-verify 0 = not blind. Hard gate.
- **Code mode (diff input):** run leak-verify (grep against leak_words.txt)
  on the diff AND on the plan copy — code comments, test names, CHANGELOG in
  a diff do carry provenance. Fires → sanitize before handing to critics;
  clean → pass as is. Blind here = fresh context + leak-checked inputs +
  forbidden reads: git log, review files, ROUNDS.md (always provenance).
  This ban is prompt discipline, not construction — critics have bash;
  treat as residual risk.

## 🛑 Convergence stop rule

Stop blind rounds when BOTH hold:
- **(a)** round surfaced no NEW strategic finding (binary check — more robust
  than comparing maturity scores; independent critics differ by ±1), AND
- **(b)** findings shifted from strategy ("what's wrong") to mechanics
  (typos, checklist sync).

Notes:
- Parent edits can inject new bugs; round N+1 flagging round N's edit is the
  safety net working, not non-convergence. Convergence = nothing new in the
  **current** text.
- A late round may surface **reframings** ("is the whole approach right?")
  rather than bugs — that's frame exhaustion, not non-convergence: file them
  as deferred P2 items, stop reviewing, start executing.
- Log each round to `research/<area>/ROUNDS.md` (fallback
  `/tmp/<TAG>_ROUNDS.md`): one line —
  `round N: strategic|mechanical, verdicts, what changed`. Stop rule is
  checked against this file, not parent memory. Critics must not read it.

## Naming & paths

- `output` = absolute path per agent.
- Findings: `<repo>/research/<area>/<TAG>_review_<N>.md` if `research/`
  exists, else `/tmp/<TAG>_review_<N>.md`. TAG = round label
  (BLIND/CLEAN/ROUND2...), N = agent index. Create dirs first.

## Invocation pattern

```
subagent({
  context: "fresh",
  concurrency: 3,
  tasks: [
    { agent: "delegate", output: "/abs/research/area/BLIND_review_1.md",
      task: "Role: senior <domain> critic. FIRST time seeing this. Find
             SUBSTANTIVE errors — if it's good, say so, don't invent problems.
             DATA (only these): <sanitized file>, <data file>. Do NOT read
             other review files. Use web search tools available to you to
             verify claims. WRITE audit (md): 1.Errors+URLs 2.Missing
             3.Doubtful assumptions 4.VERDICT GO/NO-GO/CONDITIONAL + maturity /10." },
    { agent: "delegate", output: ".../BLIND_review_2.md", model: "<other model>",
      task: "Role: <second angle>. ... (different lens, same discipline)" },
    { agent: "delegate", output: ".../BLIND_review_3.md",
      task: "Role: math/logic checker. Verify ALL arithmetic + logic. ..." }
  ]
})
```

Editor round — chain, not parallel:
```
subagent({ context: "fresh", chain: [
  { agent: "delegate", task: "Critic: findings on {file} → {chain_dir}/findings.md" },
  { agent: "delegate", task: "Editor: apply fixes from {chain_dir}/findings.md to {file}, explain each" }
]})
```

## Constraints

- Critics/researchers must **not modify project/source files** — they only
  write their own `output` report (phrase it that way, not "no file writes").
- Only editor writes, only in `mode: editor`, never two editors in parallel
  on one file.
- Always absolute paths. No secrets/credential files in any agent's data set;
  reviews must not expose secrets or private domains.
- Blind gate: see Code-mode carve-out above for prose vs code rules.
- Cost: each round = 2-4 fresh agents + web search. 1-2 rounds suffice for
  most artifacts; reserve 3-5 blind rounds for high-stakes. Don't auto-loop.
- Ignore stale "needs attention" subagent signals — parallel runs complete
  despite nudges.

## Output convention

Findings per Naming & paths; after each round parent logs one line to
ROUNDS.md (strategy vs mechanics) to track convergence.
