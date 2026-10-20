# rulebook-audit

A Claude Code loop that checks a repository against a rulebook. It finds
**implementation discrepancies** (code that breaks a rule) and **rulebook
defects** (rules that conflict, leave gaps, or can be read two ways).

It uses no MCP servers, only skills, subagents, hooks and CLI.

```
.claude/
  agents/         rule-extractor · rulebook-analyst · rule-auditor · finding-verifier
  skills/         rulebook-audit/SKILL.md   (interactive entry point)
  hooks/          guard-writes.sh (PreToolUse) · stop-gate.sh (Stop)
  settings.json   permissions + hook wiring
scripts/audit/
  run.sh          outer loop (headless claude -p, parallel fan-out)
  audit.py        deterministic gates: plan · check-rules · coverage · verify · report
schemas/          JSON Schemas enforced with --json-schema
example/          seeded test rulebook and the report it produced
```

## Run

```bash
cp -r .claude scripts schemas /path/to/repo/     # merge .claude/ if one exists
cd /path/to/repo
scripts/audit/run.sh docs/RULEBOOK.md             # stops after extraction for review
scripts/audit/run.sh docs/RULEBOOK.md --approve   # full run → .audit/report.md
```

Settings: `PARALLEL` (default 4), `BUDGET_PER_JOB` in USD (default 1.00),
`SHARD_DEPTH` (default 2, so `services/<name>` is one shard).
The run exits 2 when there are new high-severity findings, so you can use it as a CI gate.
Mark the repo as trusted once, by opening Claude Code in it interactively, so
the project settings and hooks load in headless runs.

## Pipeline

```
RULEBOOK.md
   │ rule-extractor (Read, Glob)          → rules.json   ─┐ check-rules: text verbatim, ids unique
   │                                                      └ HUMAN APPROVAL (hash-pinned)
   ├─ rulebook-analyst (Read; no code)     → conflicts / gaps / ambiguities
   ├─ mechanical rules                     → run approved `check` commands, no model
   └─ plan: shard × rule-batch jobs
        │ rule-auditor ×N (Read, Grep, Glob; parallel; fresh context each)
        │ coverage gate: every assigned rule id in `checked`, else retry once
   verify (script): evidence must be a verbatim quote at the cited lines
   finding-verifier (fresh context): tries to refute each finding
   report (script): dedupe by fingerprint, suppressions, diff vs baseline
```

## Where the reliability comes from

| Failure mode | What stops it | Enforced by |
|---|---|---|
| Hallucinated violation | Quote must exist at file:line | `audit.py verify` |
| Plausible but wrong finding | Fresh agent tries to refute it | `finding-verifier` |
| Rules silently skipped | `checked` must list every assigned id | `audit.py coverage` + retry, Stop hook |
| Context overload on a big repo | One shard and ≤6 rules per agent | `audit.py plan` |
| Paraphrased or invented rules | Rule text must be verbatim; human approves | `check-rules` + approval hash |
| Auditor "fixes" code | No Write tool; PreToolUse hook blocks writes outside `.audit/` | agent `tools:` + hook |
| Unparseable output | JSON Schema enforced, text fallback | `--json-schema` |
| Noise between runs | Line-shift-stable fingerprints, baseline, suppressions | `audit.py report` |
| Runaway cost | Per-job cap, total spend printed | `--max-budget-usd` |

## Test run (example/)

Rulebook with 7 rules and 2 files seeded with problems. All seeded issues were
found, including the LOG-1 vs LOG-2 conflict (you can't log all headers without
logging the Authorization token) and the gap in DEP-1 (it requires "approved
libraries" but no list exists). The whole run cost about $0.30.
