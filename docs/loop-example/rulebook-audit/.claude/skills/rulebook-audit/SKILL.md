---
name: rulebook-audit
description: Audit this repository against a rulebook (coding standards, architecture rules, security policy) for implementation discrepancies and for conflicts, gaps and ambiguities in the rulebook itself. Use when asked to check code against rules, standards, policies or an ADR set.
---

# Rulebook audit

Two ways to run this. Prefer the script for anything larger than one service.

## A. Batch (recommended): the outer loop does the orchestration

```bash
scripts/audit/run.sh <path-to-rulebook.md>
```

First run stops after rule extraction (exit 3). Show the user `.audit/rules.json`
summarised as a table (id, scope, kind, check command) and ask them to confirm
or correct it. Then rerun with `--approve`. When it finishes, summarise
`.audit/report.md`: rulebook defects first, then new high-severity violations,
then coverage holes. Never re-rank or drop findings in your summary.

## B. Interactive (small repos, or exploring one area)

Do the same stages yourself, with the same agents and the same gates:

1. `touch .audit/IN_PROGRESS` (enables the Stop-hook coverage gate).
2. Delegate to **rule-extractor** → write result to `.audit/rules.json`.
   Get user confirmation of the rules before continuing.
3. Delegate to **rulebook-analyst** → `.audit/raw/_rulebook.json`.
4. `python3 scripts/audit/audit.py plan` → `.audit/jobs.jsonl`.
5. For each job, delegate to **rule-auditor** with only that job's shard and
   rules; write its JSON to `.audit/raw/<job>.json`. Run independent jobs as
   parallel subagents.
6. `python3 scripts/audit/audit.py coverage`; rerun any listed job.
7. `python3 scripts/audit/audit.py verify --rulebook <path>`.
8. Delegate `.audit/verified.json` in batches of ≤15 to **finding-verifier**;
   concatenate results into `.audit/final.json`.
9. `python3 scripts/audit/audit.py report`.

## Invariants (do not work around these)

- You do not judge findings yourself. Auditors find, the verifier challenges,
  the scripts decide what survives. Your job is routing and summarising.
- Never edit source files. A hook enforces this.
- A finding without a verbatim quote is not a finding.
- Suppressing a finding means adding `{fingerprint, reason, by}` to
  `.audit/suppressions.json`, only when the user asks, with their reason.
- If a rule matches no files, report it; don't widen its scope to make it fit.
