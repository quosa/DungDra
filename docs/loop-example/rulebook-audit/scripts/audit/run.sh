#!/usr/bin/env bash
# Outer loop for the rulebook audit. Run from the target repo root.
#
#   scripts/audit/run.sh docs/RULEBOOK.md            # full run
#   PARALLEL=8 BUDGET_PER_JOB=1.50 scripts/audit/run.sh docs/RULEBOOK.md
#   scripts/audit/run.sh docs/RULEBOOK.md --approve   # accept extracted rules.json
#
# Claude Code is the inner loop (the agent reading code). This script is the
# outer loop: it decides WHAT each agent sees, runs them in parallel, checks
# their output mechanically, retries holes, and produces a stable report.
set -euo pipefail

RULEBOOK=${1:?usage: run.sh <rulebook.md> [--approve]}
HERE="$(cd "$(dirname "$0")" && pwd)"
SCHEMAS="$HERE/../../schemas"
PARALLEL=${PARALLEL:-4}
BUDGET_PER_JOB=${BUDGET_PER_JOB:-1.00}
SHARD_DEPTH=${SHARD_DEPTH:-2}
A=.audit
mkdir -p "$A/raw" "$A/logs"
PY="python3 $HERE/audit.py"

# One headless Claude Code call = one agent, one schema, fresh context.
# Reads the same .claude/agents/<name>.md used in interactive mode: the
# frontmatter gives tools + model, the body becomes the system prompt.
# (--tools rather than --agent: an agent's tools allowlist also hides the
#  structured-output tool, so the schema silently stops being enforced.)
agent() {  # agent <name> <schema-file> <out-file> <prompt>
  local name=$1 schema=$2 out=$3 prompt=$4 def=".claude/agents/$1.md" log
  log="$A/logs/$(basename "$out")"
  local tools model body
  tools=$(awk '/^---/{n++; next} n==1 && /^tools:/{sub(/^tools:[ ]*/,""); gsub(/,/," "); print}' "$def")
  model=$(awk '/^---/{n++; next} n==1 && /^model:/{print $2}' "$def")
  body=$(awk '/^---/{n++; next} n>=2' "$def")
  # shellcheck disable=SC2086
  claude -p "$prompt" \
    --append-system-prompt "$body" \
    --tools $tools \
    --model "${model:-sonnet}" \
    --output-format json \
    --json-schema "$(cat "$schema")" \
    --max-budget-usd "$BUDGET_PER_JOB" \
    > "$log.log" 2> "$log.err" || true
  # Prefer schema-enforced output; fall back to a JSON block in the text result.
  jq -e '.structured_output // (.result | capture("(?s)(?<j>\\{.*\\})").j | fromjson)' "$log.log" \
    > "$out" 2>/dev/null || rm -f "$out"
  jq -r '.total_cost_usd // 0' "$log.log" >> "$A/costs.txt" 2>/dev/null || true
}
export -f agent; export A BUDGET_PER_JOB

# ── 1. Rule extraction, with a human gate ──────────────────────────────────
# The rulebook is the spec for everything downstream, and mechanical rules
# carry shell commands. A person approves rules.json once; the hash pins it.
RB_HASH=$(sha256sum "$RULEBOOK" | cut -c1-16)
if [[ ! -f $A/rules.json || "$(cat $A/rules.rulebook-hash 2>/dev/null)" != "$RB_HASH" ]]; then
  echo "» extracting rules from $RULEBOOK"
  agent rule-extractor "$SCHEMAS/rules.schema.json" "$A/rules.json" \
    "Rulebook: $RULEBOOK. Repository root: $(pwd). Extract the rules."
  [[ -f $A/rules.json ]] || { echo "extraction failed, see $A/logs/rules.json.log"; exit 1; }
  $PY check-rules --rulebook "$RULEBOOK" || true   # warnings shown before approval
  echo "$RB_HASH" > $A/rules.rulebook-hash
  rm -f $A/rules.approved
fi
if [[ "${2:-}" == "--approve" ]]; then sha256sum $A/rules.json > $A/rules.approved; fi
if ! sha256sum -c --quiet $A/rules.approved 2>/dev/null; then
  echo "» review $A/rules.json (ids, scopes, mechanical 'check' commands), then rerun with --approve"
  exit 3
fi

rm -f "$A"/raw/*.json "$A/costs.txt" "$A/retry.txt" "$A/final.json"

# ── 2. Rulebook-only analysis: conflicts, gaps, ambiguity ─────────────────
echo "» analysing rulebook"
agent rulebook-analyst "$SCHEMAS/findings.schema.json" "$A/raw/_rulebook.json" \
  "Rulebook: $RULEBOOK. Normalized rules: $A/rules.json. Report conflicts, gaps and ambiguities." &

# ── 3. Mechanical rules: no model, just run the approved checks ───────────
echo "» running mechanical checks"
jq -c '.rules[] | select(.kind=="mechanical" and .check)' $A/rules.json | while read -r r; do
  id=$(jq -r .id <<<"$r"); cmd=$(jq -r .check <<<"$r")
  if ! out=$(bash -c "$cmd" 2>&1); then
    jq -n --arg id "$id" --arg ev "${out:0:2000}" --arg q "$(jq -r .text <<<"$r")" \
      '{rule_ids:[$id],kind:"violation",severity:"medium",evidence:$ev,rule_quote:$q,
        explanation:"Mechanical check failed",confidence:1,_mechanical:true}'
  fi
done | jq -s '{checked:[], findings:.}' > $A/raw/_mechanical.json

# ── 4. Fan out semantic audit: shard × rule-batch, read-only agents ───────
$PY plan --depth "$SHARD_DEPTH"
run_job() {
  local j=$1 job shard rules
  job=$(jq -r .job <<<"$j"); shard=$(jq -r .shard <<<"$j")
  rules=$(jq -c --argjson ids "$(jq -c .rule_ids <<<"$j")" '[.rules[]|select(.id as $i|$ids|index($i))]' $A/rules.json)
  agent rule-auditor "$SCHEMAS/findings.schema.json" "$A/raw/$job.json" \
    "Shard: $shard (only look inside this path). Rules to check: $rules"
  echo "  ✓ $job"
}
export -f run_job; export SCHEMAS
jq -c . $A/jobs.jsonl | xargs -d '\n' -P "$PARALLEL" -I{} bash -c 'run_job "$1"' _ {}

# Coverage gate: any job that failed or skipped a rule gets one retry.
if ! $PY coverage; then
  echo "» retrying incomplete jobs"
  grep -Ff $A/retry.txt $A/jobs.jsonl | jq -c . | xargs -d '\n' -P "$PARALLEL" -I{} bash -c 'run_job "$1"' _ {}
  $PY coverage || echo "» some jobs still incomplete; reported as coverage holes"
fi
wait  # rulebook analyst

# ── 5. Evidence gate (mechanical): quotes must exist where cited ──────────
$PY verify --rulebook "$RULEBOOK"

# ── 6. Adversarial verification (semantic): fresh agent tries to refute ──
echo "» adversarial verification"
n=$(jq length $A/verified.json)
for ((i=0; i<n; i+=15)); do
  jq ".[$i:$((i+15))]" $A/verified.json > $A/logs/batch_$i.json
  agent finding-verifier "$SCHEMAS/findings.schema.json" "$A/raw/_verify_$i.out" \
    "Rulebook: $RULEBOOK. Findings to challenge: $(cat $A/logs/batch_$i.json)"
  # If the verifier dropped or invented findings, fall back to the unchallenged batch.
  if [[ -f $A/raw/_verify_$i.out ]] && \
     [[ $(jq '.findings|length' $A/raw/_verify_$i.out) == $(jq length $A/logs/batch_$i.json) ]]; then
    jq '.findings' $A/raw/_verify_$i.out
  else
    jq '.' $A/logs/batch_$i.json
  fi
done | jq -s 'add // []' > $A/final.json
rm -f $A/raw/_verify_*.out

# ── 7. Report: dedupe, suppress, diff against baseline ────────────────────
echo "» spend: \$$(awk '{s+=$1} END {printf "%.2f", s}' $A/costs.txt)"
$PY report --fail-on-new-high "${@:3}"
