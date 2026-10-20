#!/usr/bin/env bash
# Stop hook: while an interactive audit is in progress, Claude may not declare
# itself done until every planned job produced output that covers its rules.
# Exit 2 = refuse the stop; stderr tells Claude what is still missing.
input=$(cat)
[[ -f "$CLAUDE_PROJECT_DIR/.audit/IN_PROGRESS" ]] || exit 0
# Don't loop forever: if we already blocked once this turn, let it stop.
[[ "$(jq -r '.stop_hook_active' <<<"$input")" == "true" ]] && exit 0
cd "$CLAUDE_PROJECT_DIR"
if ! out=$(python3 scripts/audit/audit.py coverage 2>&1); then
  echo "Audit not complete. $out  Run the missing jobs listed in .audit/retry.txt, then verify and report." >&2
  exit 2
fi
[[ -f .audit/report.md ]] || { echo "Coverage complete but no report yet: run verify, the finding-verifier pass, and report." >&2; exit 2; }
rm -f .audit/IN_PROGRESS
exit 0
