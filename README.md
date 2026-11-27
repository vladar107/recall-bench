# recall-bench

**How should a coding agent search its own history — a purpose-built index, or
grep over raw transcripts?** This benchmark measures it *on your machine, with
your real history*, and takes ~2 hours of unattended runtime.

It accompanies the preprint *"MCP, Skill, or Grep? A Controlled Comparison
of Memory Access for Coding Agents"* (Ramazaev, 2026). The original
study (one corpus, 492 runs) found an indexed interface **2.8× faster, 2.3×
cheaper, and +9 pp more accurate** than raw-file search — with the accuracy
gap concentrated in synthesis workloads. One corpus proves little.
**Replications on other people's corpora are what this repo is for.**

## What it does

Four agent configurations answer the same questions about your coding-agent
history, fully tool-isolated:

| Arm | Data access | Interface | Isolation |
|---|---|---|---|
| `mcp` | claudescope index | 6 MCP tools | file tools disallowed |
| `skill` | claudescope index | CLI taught by an agent skill | `Bash(claudescope:*)` prefix rule |
| `hybrid` | both | MCP tools + file tools | — |
| `files` | raw transcripts | grep / jq / file reads | MCP absent; index state banned |

The pipeline is fully automated: it **generates a question bank from your own
corpus** (two curator agents, each holding BOTH access paths and alternating
which one leads discovery), **verifies every reference answer independently
through both paths** — raw files AND the index — and drops any question that
only one path can confirm, so no question structurally favors either arm. It
then runs every question × arm × repetition as a **cold, isolated
`claude -p` process**, grades answers **blind** with a different, stronger
model, and packages metrics for sharing. (Protocol `v2`; the original study
used a slightly weaker dual-provenance curation and is kept in
`submissions/pilot-m0.json` as reference only — pooled statistics use v2
submissions exclusively.)

**Models (defaults, pinned — versions matter for comparability):**
research arms `claude-sonnet-5`; curation, assembly and blind judging
`claude-opus-4-8`. Accuracy is judged by the LLM judge **by design** (blind,
fixed rubric, judge model ≠ contestant model, ±15% tolerance on aggregate
numbers); there is no human grading step.

## Requirements

- **Claude Code** CLI, logged in (`claude --version` works)
- **claudescope ≥ 0.11.0**: `npm i -g @vladar107/claudescope` (or brew / nix)
- **A real corpus**: ≥ ~30 Claude Code sessions **or** ≥ ~30 MB of
  transcripts in the last 3 weeks (a few marathon sessions count too)
- macOS or Linux, `zsh`, `python3` (stdlib only)
- **Budget**: defaults (40 questions × 4 arms × 3 reps + curation + judging)
  ≈ **$50–70** API usage. Lite run (`--questions 20 --reps 1`) ≈ $15–30.

## Privacy — read this first

- Everything runs **locally**; no data leaves your machine during the benchmark.
- The generated `bank.json` contains excerpts of your history — **it stays
  with you**.
- The only file you share is `submissions/<machine-id>.json`: run metrics
  (scores, cost, latency, turns, tool mix) and question **metadata** (category,
  difficulty, date, provenance) — no question text, no answers, no transcript
  content.
  `--include-questions` opts in to sharing question text; only use it after
  reviewing every question.
- The benchmark's own runs create Claude Code session transcripts under
  `~/.claude/projects/`; when you're done, `python3 bench.py clean --yes`
  deletes them and reindexes claudescope (dry-run without `--yes`).

## Run it

```bash
git clone https://github.com/vladar107/recall-bench.git && cd recall-bench
python3 bench.py all
```

Stage by stage (each stage is idempotent — rerun after any failure and it
resumes where it stopped):

```bash
python3 bench.py preflight    # tools, daemon, MCP handshake, corpus volume
python3 bench.py curate       # question bank from YOUR corpus → bank.json
python3 bench.py verify       # cross-provenance reference verification
python3 bench.py run          # the measured runs (cold, tool-isolated)
python3 bench.py judge        # blind grading
python3 bench.py report       # scoreboard + results.json
python3 bench.py package      # submissions/<machine-id>.json (metrics only)
python3 bench.py clean --yes  # afterwards: remove the benchmark's own transcripts
```

**Checkpoint after `verify`: skim `bank.json`.** Delete any question that
looks wrong, ambiguous, or too private, then continue with `run`.

Useful flags: `--questions 40` · `--reps 3` · `--arms mcp,files,hybrid,skill`
· `--model claude-sonnet-5` · `--judge-model claude-opus-4-8` ·
`--concurrency 5` · `--window-days 21`. Keep the default models if you want
your numbers pooled with other submissions.

## Send your results

`package` writes exactly one shareable file: `submissions/<machine-id>.json`.
Skim it, then either:

- **open a PR** on this repo adding that one file, or
- **email it** to **vladar107@gmail.com**.

That's all — nothing else is needed.

Every submission is credited in the paper's replication section (or kept
anonymous on request — the machine id is already a salted hash).

## How the data is aggregated

Submissions are pooled with [`aggregate_submissions.py`](aggregate_submissions.py):

```bash
python3 aggregate_submissions.py submissions/*.json
```

It prints per-machine scoreboards, then pooled paired accuracy contrasts
(MCP vs files, MCP vs skill, hybrid vs files) with a two-level cluster
bootstrap — resampling machines first, then questions within each machine —
so no single corpus dominates and confidence intervals reflect between-machine
variation. Submissions from pre-v2 protocols (including the original study,
[`submissions/pilot-m0.json`](submissions/pilot-m0.json)) are displayed
per-machine but excluded from the pooled statistics. It also writes
`combined.csv` (one row per run across all machines) for your own analysis.

## Runs on other models

The pooled study uses Claude Sonnet 5 as the agent and Claude Opus 4.8 as the
judge. Runs with a different agent or judge live in their own folder under
`submissions/` and are **not** pooled with it: the `submissions/*.json` glob
above does not pick them up.

[`submissions/opus-5-5/bfc6f8fbddfa.json`](submissions/opus-5-5/bfc6f8fbddfa.json)
— agent `claude-opus-5-5`, judge `claude-fable-5-2`, 32 verified
questions, 3 reps, 96 runs per arm, no DNF. Means of per-question means:

| arm    | accuracy | time   | cost    | turns |
|--------|---------:|-------:|--------:|------:|
| files  | 96.4%    | 24.4 s | $0.179  | 5.8   |
| mcp    | 99.0%    | 13.3 s | $0.162  | 5.1   |
| skill  | 98.4%    | 16.4 s | $0.199  | 6.1   |
| hybrid | 97.9%    | 30.9 s | $0.175  | 5.8   |

MCP is about 1.8× faster than raw files, as in the pooled study (2.35×). The
cost advantage shrinks from 45% to 9%, because this agent needs about 6 turns
on raw files where Sonnet 5 needed about 10. Accuracy is again not
distinguishable: MCP − files is +2.6 pp, 95% CI [−1.0, +7.8] (bootstrap over
questions).

[`submissions/opus-5-5/76e5ed2a991d.json`](submissions/opus-5-5/76e5ed2a991d.json)
— same agent and judge on a second machine, with curation and verification
also on `claude-opus-5-5`: 37 verified questions, 3 reps, 111 runs per arm,
no DNF. This is the machine behind the pooled `submissions/76e5ed2a991d.json`
Sonnet 5 run, on a newer 21-day window and a new question bank.

| arm    | accuracy | time   | cost    | turns |
|--------|---------:|-------:|--------:|------:|
| files  | 96.8%    | 24.5 s | $0.194  | 6.0   |
| mcp    | 100.0%   | 11.9 s | $0.150  | 5.2   |
| skill  | 100.0%   | 15.4 s | $0.213  | 6.7   |
| hybrid | 99.1%    | 37.2 s | $0.188  | 5.4   |

MCP is 2.1× faster and 23% cheaper than raw files. MCP − files accuracy is
+3.2 pp, 95% CI [0.0, +9.0] (bootstrap over questions), again not clearly
distinguishable.

Read each table as a comparison between arms within that run only. Agent,
judge, machine and question set all differ from the pooled study, so
differences between these tables and it cannot be attributed to the model.
Both runs sit at the ceiling: three questions per run were ever answered
imperfectly.

## Repo layout

```
bench.py                  the orchestrator (all stages)
run_one.sh                one cold, tool-isolated benchmark run
judge_one.sh              one blind grading call
arms/                     per-arm system prompts
prompts/                  curator / assembler / verifier prompts
runhome/                  neutral cwd for runs (contains the claudescope skill)
aggregate_submissions.py  cross-machine pooling & stats
submissions/              collected submissions, one <machine-id>.json each
```

## Method notes

Hard tool allowlists (`--allowedTools`, `--strict-mcp-config`, a
`Bash(claudescope:*)` permission prefix for the skill arm), a 40-turn cap,
contamination rule excluding the benchmark's own transcripts, and post-hoc
isolation audit from the runs' own transcripts. Full method: see the paper.

## License

MIT. The benchmark tests [claudescope](https://github.com/vladar107/claudescope),
which is maintained by the same author — replications by others are the
antidote to that conflict of interest.
