#!/bin/zsh
# judge_one.sh <qid> <arm> <rep> — blind-grade one answer with Opus.
# Reads out/<qid>_<arm>_r<rep>.json + bank.json; writes out/judge_<qid>_<arm>_r<rep>.json
set -u
B="${0:A:h}"
QID="$1"; ARM="$2"; REP="$3"
export BENCH_DIR="$B"
OUT="$B/out/judge_${QID}_${ARM}_r${REP}.json"
[[ -s "$OUT" ]] && { echo "skip $OUT"; exit 0; }

PROMPT=$(python3 - "$QID" "$ARM" "$REP" <<'EOF'
import json, sys, os
B = os.path.dirname(os.path.abspath(sys.argv[0])) if False else os.environ.get('BENCH_DIR')
qid, arm, rep = sys.argv[1], sys.argv[2], sys.argv[3]
bank = {q['id']: q for q in json.load(open(f'{B}/bank.json'))}
run = json.load(open(f'{B}/out/{qid}_{arm}_r{rep}.json'))
q = bank[qid]
cand = run.get('result', '(no answer)')
tol = ''
if q['category'] == 'aggregate':
    tol = ("\nTOLERANCE: this is an aggregate/counting question. Numbers within ~15% of the reference "
           "(or matching after reasonable rounding) count as matching; a correct entity/day with a "
           "moderately-off number scores 0.5, not 0. Different-but-defensible counting criteria "
           "(e.g. deduplication differences) with transparent methodology also merit 0.5.")
print(f"""You grade one candidate answer against a reference answer for a question about
a user's AI-coding-agent history. You do not know which system produced it.

Scoring rubric:
- 1.0: factually matches the reference on every element the question asks for (rounding ok; extra correct detail ok).
- 0.5: partially correct — core claim right but a requested element missing/wrong, or correct but too vague.
- 0.0: wrong, contradicts the reference, unsupported guess, or no answer.
Judge ONLY against the reference. Do not reward confidence, length, or effort.{tol}

QUESTION: {q['question']}

REFERENCE ANSWER: {q['reference']}

CANDIDATE ANSWER: {cand}

Reply with EXACTLY this format and nothing else:
SCORE: <1 | 0.5 | 0>
REASON: <one sentence>""")
EOF
)
cd "$B/runhome"
BENCH_DIR="$B" claude --print --output-format json --model "${BENCH_JUDGE_MODEL:-claude-opus-4-8}" --max-turns 1 \
  --strict-mcp-config --mcp-config "$B/mcp-empty.json" \
  --disallowedTools "Bash" "Grep" "Glob" "Read" "Write" "Edit" "Task" "Agent" "WebFetch" "WebSearch" "Workflow" "Skill" "ToolSearch" \
  -- "$PROMPT" > "$OUT" 2> "$B/out/judge_${QID}_${ARM}_r${REP}.err"
echo "judged ${QID}_${ARM}_r${REP} rc=$?"
