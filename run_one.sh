#!/bin/zsh
# run_one.sh <qid> <arm: mcp|files|hybrid> <rep> <question-text>
# One cold, isolated, tool-restricted headless run. Writes out/<qid>_<arm>_r<rep>.json
set -u
B="${0:A:h}"
QID="$1"; ARM="$2"; REP="$3"; QUESTION="$4"
OUT="$B/out/${QID}_${ARM}_r${REP}.json"
[[ -s "$OUT" ]] && { echo "skip $OUT (exists)"; exit 0; }

DISALLOW=("Write" "Edit" "NotebookEdit" "Task" "Agent" "WebFetch" "WebSearch"
          "TodoWrite" "EnterPlanMode" "ExitPlanMode" "Workflow" "Skill"
          "ReportFindings" "ScheduleWakeup" "ShareOnboardingGuide")

case "$ARM" in
  mcp)
    MCPCONF="$B/mcp-claudescope.json"
    ALLOW=("mcp__claudescope__search_transcripts" "mcp__claudescope__list_sessions" "mcp__claudescope__get_session" "mcp__claudescope__list_projects" "mcp__claudescope__get_analytics" "mcp__claudescope__get_memory")
    DISALLOW+=("Bash" "Grep" "Glob" "Read")
    ;;
  files)
    MCPCONF="$B/mcp-empty.json"
    ALLOW=("Bash" "Grep" "Glob" "Read")
    ;;
  skill)
    MCPCONF="$B/mcp-empty.json"
    ALLOW=("Skill" "Bash(claudescope:*)")
    DISALLOW=(${DISALLOW:#Skill})
    DISALLOW+=("Grep" "Glob" "Read")
    ;;
  hybrid)
    MCPCONF="$B/mcp-claudescope.json"
    ALLOW=("Bash" "Grep" "Glob" "Read" "mcp__claudescope__search_transcripts" "mcp__claudescope__list_sessions" "mcp__claudescope__get_session" "mcp__claudescope__list_projects" "mcp__claudescope__get_analytics" "mcp__claudescope__get_memory")
    ;;
  *) echo "unknown arm $ARM" >&2; exit 2 ;;
esac

cd "$B/runhome"
claude --print --output-format json --model "${BENCH_MODEL:-claude-sonnet-5}" --max-turns 40 \
  --append-system-prompt-file "$B/arms/${ARM}.md" \
  --strict-mcp-config --mcp-config "$MCPCONF" \
  --allowedTools "${ALLOW[@]}" \
  --disallowedTools "${DISALLOW[@]}" \
  -- "$QUESTION" > "$OUT" 2> "$B/out/${QID}_${ARM}_r${REP}.err"
RC=$?
echo "done ${QID}_${ARM}_r${REP} rc=$RC"
