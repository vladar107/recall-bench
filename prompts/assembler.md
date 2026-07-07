You are the editor assembling the final question bank for a retrieval
benchmark. Below are candidate questions from two curators who explored the
same corpus through different access paths. Your job:

1. DEDUPLICATE: where two candidates cover the same underlying event/session,
   keep exactly one — prefer the one with the deeper/more complete reference;
   when references CONFLICT, keep the candidate whose evidence is more
   specific and note the conflict in a "flags" field.
2. ENFORCE RULES: drop candidates that violate self-containment (references
   "this repo" etc.), embed session ids/paths in the question text, quote
   verbatim transcript strings, ask for unstable or subjective answers, or
   fall outside the {FROM}..{TO} window.
3. BALANCE: select the final {N_FINAL} questions with as close to equal
   category counts as possible ({TARGET_PER_CAT} per category), both
   provenances represented, and days spread across the window.

Return ONLY a JSON array of the selected question objects, unchanged except:
renumber ids Q01..Q{N_FINAL}, add "provenance":"both" (curators held both
access paths), and add "flags":[] (list any concerns per question).

CANDIDATES:
{CANDIDATES_JSON}
