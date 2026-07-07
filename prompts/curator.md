You are curating benchmark questions for a retrieval experiment over THIS
machine's AI-coding-agent transcript history. Discovery constraint: {PROVENANCE_RULE}

Draft {N_CANDIDATES} candidate benchmark questions with verified reference
answers: {N_PER_CAT} in each category:
1. needle — find a specific error/message/fact ("where did I hit X? what was the fix?")
2. session-read — locate a session and report a specific detail from it
3. aggregate — counts/costs/totals scoped to a sub-range INSIDE the window below (never all-time)
4. multi-session — a fact whose full answer spans 2+ different Claude Code sessions
5. decision-recall — "what was decided about X / why was Y chosen?"

HARD CONSTRAINTS:
- Facts must be answerable from Claude Code sessions only (~/.claude/projects).
- The underlying events must fall between {FROM} and {TO}, spread across that
  window (roughly a third per week; include at least 2 from the final 3 days).
- Self-contained: name the project/topic explicitly; the answerer has no
  context beyond the question. No "this repo".
- Paraphrased: never quote exact transcript strings verbatim; never embed
  session ids or file paths in the QUESTION (exact strings gift-wrap search).
- Stable: the answer must not change as new sessions are added.
- Checkable: the reference answer is short and objective. No opinion questions.
- Verify every reference against the data BEFORE including it.
- Difficulty honesty: label easy/medium/hard truthfully.
- OFF-LIMITS as material: sessions produced by this benchmark itself (anything
  whose working directory is the benchmark kit folder, or that discusses a
  "history-retrieval benchmark" / question banks).

Return ONLY a JSON array (no prose, no code fences), {N_CANDIDATES} objects:
[{"id":"{ID_PREFIX}01","category":"needle","question":"…","reference":"…",
  "evidence":"<session id(s)/file path(s) proving it>","difficulty":"easy|medium|hard",
  "project":"<project>","day":"YYYY-MM-DD"}, …]
