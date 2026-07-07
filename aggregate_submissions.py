#!/usr/bin/env python3
"""
Aggregate submissions from multiple machines into a cross-corpus report.

  python3 aggregate_submissions.py submissions/*.json

For each machine: per-arm accuracy / median cost / median latency.
Pooled: per-question paired contrasts within each machine, pooled across
machines with cluster bootstrap (clusters = machines, then questions).
Writes combined.csv (one row per run, all machines) and prints the report.
"""
import json, random, sys
from collections import defaultdict

random.seed(7)
ARMS = ['mcp', 'skill', 'hybrid', 'files']

def med(xs): return sorted(xs)[len(xs)//2] if xs else 0.0

if len(sys.argv) < 2:
    sys.exit(__doc__)

subs = []
for path in sys.argv[1:]:
    s = json.load(open(path))
    s['_path'] = path
    subs.append(s)

# ---- per-machine tables ----
print(f'{len(subs)} submission(s)\n')
per_machine_qdiff = defaultdict(list)   # (arm_a, arm_b) -> list of per-question diffs (all machines)
for s in subs:
    graded = [r for r in s['runs'] if r.get('score') is not None]
    cfg = s.get('config', {})
    print(f"machine {s['machine_id']}  ({s.get('date','?')}, {cfg.get('n_questions','?')} questions, "
          f"reps={cfg.get('reps','?')}, model={cfg.get('model','?')}, judge={cfg.get('judge_model','?')})")
    print(f"  {'arm':8} {'n':>4} {'acc':>6} {'med$':>7} {'med s':>6} {'DNF':>4}")
    for arm in ARMS:
        sel = [r for r in graded if r['arm'] == arm]
        if not sel:
            continue
        print(f"  {arm:8} {len(sel):>4} {sum(r['score'] for r in sel)/len(sel):>5.0%} "
              f"{med([r['cost'] for r in sel]):>7.3f} {med([r['secs'] for r in sel]):>6.0f} "
              f"{sum(1 for r in sel if r.get('dnf')):>4}")
    print()
    # per-question means for paired contrasts
    qm = defaultdict(dict)
    for r in graded:
        qm[r['qid']].setdefault(r['arm'], []).append(r['score'])
    for q, arms in qm.items():
        means = {a: sum(v)/len(v) for a, v in arms.items()}
        for pair in (('mcp', 'files'), ('mcp', 'skill'), ('hybrid', 'files')):
            if pair[0] in means and pair[1] in means:
                per_machine_qdiff[pair].append((s['machine_id'], means[pair[0]] - means[pair[1]]))

# ---- pooled contrasts (two-level cluster bootstrap: machines, then questions) ----
print('pooled paired contrasts (accuracy):')
for pair, diffs in per_machine_qdiff.items():
    by_m = defaultdict(list)
    for m, d in diffs:
        by_m[m].append(d)
    machines = list(by_m)
    obs = sum(d for _, d in diffs) / len(diffs)
    boots = []
    for _ in range(10000):
        ms = [machines[random.randrange(len(machines))] for _ in machines]
        pool = [d for m in ms for d in
                [by_m[m][random.randrange(len(by_m[m]))] for _ in by_m[m]]]
        boots.append(sum(pool) / len(pool))
    boots.sort()
    lo, hi = boots[250], boots[9750]
    print(f"  {pair[0]} vs {pair[1]}: {obs:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]  "
          f"(n={len(diffs)} question-pairs, {len(machines)} machine(s))")

# ---- combined CSV ----
cols = ['machine_id', 'qid', 'category', 'difficulty', 'provenance', 'arm', 'rep',
        'score', 'dnf', 'cost', 'secs', 'turns']
with open('combined.csv', 'w') as f:
    f.write(','.join(cols) + '\n')
    for s in subs:
        for r in s['runs']:
            f.write(','.join(str(r.get(c, s['machine_id'] if c == 'machine_id' else ''))
                             for c in cols) + '\n')
print('\nwrote combined.csv')
