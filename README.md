# agent-memory-bench

**How should a coding agent search its own history — a purpose-built index, or
grep over raw transcripts?** This benchmark measures it *on your machine, with
your real history*, and takes ~2 hours of unattended runtime.

It accompanies the preprint *"Grep or Index? A Controlled Comparison of
Retrieval Interfaces for Coding-Agent Memory"* (Ramazaev, 2026). The original
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
corpus** (two curator agents with opposite discovery paths), **cross-verifies
every reference answer** through the opposite access path (unconfirmed
questions are dropped), runs every question × arm × repetition as a **cold,
isolated `claude -p` process**, grades answers **blind** with a different,
stronger model, and packages metrics for sharing.

**Models (defaults, pinned — versions matter for comparability):**
research arms `claude-sonnet-5`; curation, assembly and blind judging
`claude-opus-4-8`. Accuracy is judged by the LLM judge **by design** (blind,
fixed rubric, judge model ≠ contestant model, ±15% tolerance on aggregate
numbers); there is no human grading step.

## Requirements

- **Claude Code** CLI, logged in (`claude --version` works)
- **claudescope ≥ 0.11.0**: `npm i -g @vladar107/claudescope` (or brew / nix)
- **A real corpus**: ≥ ~30 Claude Code sessions in the last 3 weeks
- macOS or Linux, `zsh`, `python3` (stdlib only)
- **Budget**: defaults (20 questions × 4 arms × 3 reps + curation + judging)
  ≈ **$80–120** API usage. Lite run (`--reps 1`) ≈ $35–50.

## Privacy — read this first

- Everything runs **locally**; no data leaves your machine during the benchmark.
- The generated `bank.json` contains excerpts of your history — **it stays
  with you**.
- The only file you share is `submission.json`: run metrics (scores, cost,
  latency, turns, tool mix) and question **metadata** (category, difficulty,
  date, provenance) — no question text, no answers, no transcript content.
  `--include-questions` opts in to sharing question text; only use it after
  reviewing every question.
- The benchmark's own runs create Claude Code session transcripts under
  `~/.claude/projects/` (two `runhome` project folders); delete them
  afterwards if you wish — claudescope drops them from its index on the next
  reindex.

## Run it

```bash
git clone <this repo> && cd agent-memory-bench
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
python3 bench.py package      # submission.json (metrics only)
```

**Checkpoint after `verify`: skim `bank.json`.** Delete any question that
looks wrong, ambiguous, or too private, then continue with `run`.

Useful flags: `--questions 20` · `--reps 3` · `--arms mcp,files,hybrid,skill`
· `--model claude-sonnet-5` · `--judge-model claude-opus-4-8` ·
`--concurrency 5` · `--window-days 21`. Keep the default models if you want
your numbers pooled with other submissions.

## Send your results

1. Open `submission.json` and confirm you're comfortable with its contents
   (it is small and human-readable).
2. Email it to **vladar107@gmail.com** or open an issue/PR on this repo
   attaching the file.

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
variation. It also writes `combined.csv` (one row per run across all machines)
for your own analysis. The original study's data is included as
[`submissions/pilot-m0.json`](submissions/pilot-m0.json).

## Repo layout

```
bench.py                  the orchestrator (all stages)
run_one.sh                one cold, tool-isolated benchmark run
judge_one.sh              one blind grading call
arms/                     per-arm system prompts
prompts/                  curator / assembler / verifier prompts
runhome/                  neutral cwd for runs (contains the claudescope skill)
aggregate_submissions.py  cross-machine pooling & stats
submissions/              collected submission.json files
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
