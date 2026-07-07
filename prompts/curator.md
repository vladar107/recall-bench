You are curating benchmark questions for a retrieval experiment over THIS
machine's AI-coding-agent transcript history.

You have BOTH kinds of data access, and you must use BOTH while curating:
1. The claudescope MCP tools (search_transcripts, list_sessions, get_session,
   list_projects, get_analytics, get_memory).
2. Direct read access to the raw transcript files (~/.claude/projects/**/*.jsonl)
   via Bash/Grep/Glob/Read.

FAIRNESS RULE (the reason you have both): the finished questions will be
answered by agents that have only ONE of these access paths each. A question
is only fair if it can be answered through either path. Therefore, for every
candidate you include, you MUST confirm the reference answer through BOTH
paths: find/verify it in the raw files AND via the claudescope tools. Discard
candidates you cannot confirm both ways. Alternate which path you use for
initial discovery so neither dominates the bank (odd-numbered ids: discover
via raw files first; even-numbered ids: discover via claudescope first).

Draft {N_CANDIDATES} candidate questions with verified references:
{N_PER_CAT} in each category:
1. needle — find a specific error/message/fact ("where did I hit X? what was the fix?")
2. session-read — locate a session and report a specific detail from it
3. aggregate — counts/costs/totals scoped to a sub-range INSIDE the window below
   (never all-time; state the counting criterion in the reference)
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
- Difficulty honesty: label easy/medium/hard truthfully.
- OFF-LIMITS as material: sessions produced by this benchmark itself (anything
  whose working directory is the benchmark kit folder, or that discusses a
  "history-retrieval benchmark" / question banks).

Return ONLY a JSON array (no prose, no code fences), {N_CANDIDATES} objects:
[{"id":"{ID_PREFIX}01","category":"needle","question":"…","reference":"…",
  "evidence":"<session id(s) AND file path(s) proving it — both paths>",
  "difficulty":"easy|medium|hard","project":"<project>","day":"YYYY-MM-DD"}, …]
