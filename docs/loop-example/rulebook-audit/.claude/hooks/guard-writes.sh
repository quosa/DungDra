#!/usr/bin/env bash
# PreToolUse hook: an audit must never modify the thing it audits.
# Allows writes only under .audit/. Exit 2 = block, stderr is shown to Claude.
input=$(cat)
path=$(jq -r '.tool_input.file_path // .tool_input.notebook_path // empty' <<<"$input")
[[ -z "$path" ]] && exit 0
rel=$(realpath -m --relative-to="$CLAUDE_PROJECT_DIR" "$path")
if [[ "$rel" != .audit/* ]]; then
  echo "Blocked: rulebook audit is read-only outside .audit/ (tried to write $rel). Record the issue as a finding instead." >&2
  exit 2
fi
exit 0
