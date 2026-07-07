#!/usr/bin/env python3
"""
agent-memory-bench — portable replication harness.

Stages (each idempotent/resumable; `all` runs the full pipeline):

  python3 bench.py preflight
  python3 bench.py curate    [--questions 20] [--curator-model opus]
  python3 bench.py verify    [--verifier-model sonnet]
  python3 bench.py run       [--arms mcp,files,hybrid,skill] [--reps 3] [--model sonnet] [--concurrency 5]
  python3 bench.py judge     [--judge-model opus]
  python3 bench.py report
  python3 bench.py package   [--include-questions]
  python3 bench.py clean --yes   (after you're done: delete the benchmark's own
                                  session transcripts from ~/.claude/projects and
                                  reindex claudescope; dry-run without --yes)
  python3 bench.py all

Everything runs and stays local. `package` writes submission.json containing
per-run METRICS and question METADATA only — no transcript content, no
question text, no answers — unless you opt in with --include-questions.
"""
import argparse, datetime, hashlib, json, os, platform, random, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict

K = os.path.dirname(os.path.abspath(__file__))
OUT = f'{K}/out'
ARMS_ALL = ['mcp', 'files', 'hybrid', 'skill']
CATS = ['needle', 'session-read', 'aggregate', 'multi-session', 'decision-recall']
VERSION = '1.0.0'

def sh(cmd, timeout=1800):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, '', 'timeout')

def headless(prompt, model, arm=None, max_turns=40):
    """One cold `claude -p` run; returns parsed JSON output or None."""
    args = ['claude', '--print', '--output-format', 'json', '--model', model,
            '--max-turns', str(max_turns), '--strict-mcp-config']
    disallow = ['Write', 'Edit', 'NotebookEdit', 'Task', 'Agent', 'WebFetch', 'WebSearch',
                'TodoWrite', 'EnterPlanMode', 'ExitPlanMode', 'Workflow', 'ReportFindings',
                'ScheduleWakeup', 'ShareOnboardingGuide']
    if arm == 'mcp':
        args += ['--mcp-config', f'{K}/mcp-claudescope.json', '--allowedTools',
                 *[f'mcp__claudescope__{t}' for t in ('search_transcripts', 'list_sessions',
                   'get_session', 'list_projects', 'get_analytics', 'get_memory')]]
        disallow += ['Bash', 'Grep', 'Glob', 'Read', 'Skill']
    elif arm == 'files':
        args += ['--mcp-config', f'{K}/mcp-empty.json',
                 '--allowedTools', 'Bash', 'Grep', 'Glob', 'Read']
        disallow += ['Skill']
    elif arm == 'hybrid':
        args += ['--mcp-config', f'{K}/mcp-claudescope.json', '--allowedTools',
                 'Bash', 'Grep', 'Glob', 'Read',
                 *[f'mcp__claudescope__{t}' for t in ('search_transcripts', 'list_sessions',
                   'get_session', 'list_projects', 'get_analytics', 'get_memory')]]
        disallow += ['Skill']
    elif arm == 'none':
        args += ['--mcp-config', f'{K}/mcp-empty.json', '--allowedTools', 'Read']
        disallow += ['Bash', 'Grep', 'Glob', 'Skill']
    args += ['--disallowedTools', *disallow, '--', prompt]
    r = subprocess.run(args, capture_output=True, text=True, cwd=f'{K}/runhome', timeout=3600)
    try:
        return json.loads(r.stdout)
    except Exception:
        print(f'  ! headless run produced no JSON (rc={r.returncode}): {r.stderr[:200]}', file=sys.stderr)
        return None

def extract_json_array(text):
    m = re.search(r'\[.*\]', text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

# ---------------------------------------------------------------- preflight
def stage_preflight(a):
    ok = True
    def check(name, cond, hint=''):
        nonlocal ok
        print(f"  [{'ok' if cond else 'FAIL'}] {name}" + ('' if cond else f' — {hint}'))
        ok = ok and cond
    check('claude CLI', shutil.which('claude') is not None, 'install Claude Code')
    check('claudescope CLI', shutil.which('claudescope') is not None,
          'npm i -g @vladar107/claudescope (or brew/nix)')
    check('python3 + zsh', shutil.which('zsh') is not None, 'zsh required by run_one.sh')
    if shutil.which('claudescope'):
        r = sh(['claudescope', 'status'])
        healthy = 'running' in (r.stdout + r.stderr).lower()
        if not healthy:
            print('  … starting claudescope daemon')
            sh(['claudescope', 'start'], timeout=300)
            r = sh(['claudescope', 'status'])
            healthy = 'running' in (r.stdout + r.stderr).lower()
        check('claudescope daemon', healthy, 'claudescope start')
    proj = os.path.expanduser('~/.claude/projects')
    frm, to = window(a)
    recent, size, days = 0, 0, set()
    if os.path.isdir(proj):
        cutoff = datetime.datetime.strptime(frm, '%Y-%m-%d').timestamp()
        for root, _, files in os.walk(proj):
            for f in files:
                if not f.endswith('.jsonl'):
                    continue
                fp = os.path.join(root, f)
                mt = os.path.getmtime(fp)
                if mt >= cutoff:
                    recent += 1
                    size += os.path.getsize(fp)
                    days.add(datetime.date.fromtimestamp(mt))
    mb = size / 1e6
    # Either many sessions OR a lot of material: a few marathon sessions are
    # as question-rich as dozens of small ones.
    check(f'corpus volume in {frm}..{to}: ~{recent} sessions / {mb:.0f} MB '
          f'(need ≥ 30 sessions OR ≥ 30 MB)',
          recent >= 30 or mb >= 30, 'benchmark needs a few weeks of real usage')
    if len(days) < 7:
        print(f'  [warn] activity spans only {len(days)} distinct day(s) — question '
              'curation prefers events spread across the window; expect a smaller bank')
    # The harness injects its own MCP config, so user registration is NOT
    # required — what matters is that `claudescope mcp` speaks MCP. Handshake:
    init = ('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":'
            '"2025-03-26","capabilities":{},"clientInfo":{"name":"preflight","version":"0"}}}')
    r = subprocess.run(['claudescope', 'mcp'], input=init + '\n', capture_output=True,
                       text=True, timeout=60) if shutil.which('claudescope') else None
    check('claudescope MCP handshake', bool(r) and '"result"' in r.stdout,
          'claudescope mcp did not answer an MCP initialize')
    print('PREFLIGHT', 'PASSED' if ok else 'FAILED')
    return ok

def window(a):
    to = datetime.date.today()
    frm = to - datetime.timedelta(days=a.window_days)
    return frm.isoformat(), to.isoformat()

# ------------------------------------------------------------------ curate
def stage_curate(a):
    os.makedirs(OUT, exist_ok=True)
    frm, to = window(a)
    per_cat = max(1, round(a.questions * 1.4 / 5 / 2))  # 40% buffer, 2 curators
    n_cand = per_cat * 5
    tmpl = open(f'{K}/prompts/curator.md').read()
    # Two curators, EACH with both access paths (fairness rule in the prompt:
    # every candidate must be confirmed through both raw files and the index).
    for prefix in ('A', 'B'):
        out = f'{OUT}/candidates_{prefix}.json'
        if os.path.exists(out):
            print(f'  skip curate:{prefix} (exists)'); continue
        print(f'  curator {prefix} ({n_cand} candidates, model={a.curator_model}) …')
        prompt = (tmpl.replace('{N_CANDIDATES}', str(n_cand))
                  .replace('{N_PER_CAT}', str(per_cat)).replace('{FROM}', frm)
                  .replace('{TO}', to).replace('{ID_PREFIX}', prefix))
        d = headless(prompt, a.curator_model, arm='hybrid', max_turns=100)
        cand = extract_json_array(d.get('result', '')) if d else None
        if not cand:
            print(f'  ! curator {prefix} failed — rerun `curate`'); sys.exit(1)
        json.dump(cand, open(out, 'w'), indent=1)
        print(f'  curator {prefix}: {len(cand)} candidates (${d.get("total_cost_usd", 0):.2f})')
    # assemble
    bank_path = f'{K}/bank.json'
    if os.path.exists(bank_path):
        print('  skip assemble (bank.json exists)'); return
    cands = (json.load(open(f'{OUT}/candidates_A.json')) +
             json.load(open(f'{OUT}/candidates_B.json')))
    tmpl = open(f'{K}/prompts/assembler.md').read()
    prompt = (tmpl.replace('{N_FINAL}', str(a.questions))
              .replace('{TARGET_PER_CAT}', str(a.questions // 5))
              .replace('{FROM}', frm).replace('{TO}', to)
              .replace('{CANDIDATES_JSON}', json.dumps(cands, ensure_ascii=False)))
    d = headless(prompt, a.curator_model, arm='none', max_turns=8)
    bank = extract_json_array(d.get('result', '')) if d else None
    if not bank:
        print('  ! assembler failed — rerun `curate`'); sys.exit(1)
    json.dump(bank, open(bank_path, 'w'), indent=1)
    print(f'  bank assembled: {len(bank)} questions → bank.json '
          f'({dict(Counter(q["category"] for q in bank))})')

# ------------------------------------------------------------------ verify
def stage_verify(a):
    bank = json.load(open(f'{K}/bank.json'))
    tmpl = open(f'{K}/prompts/verifier.md').read()
    verdicts = {}
    vp = f'{OUT}/verification.json'
    if os.path.exists(vp):
        verdicts = json.load(open(vp))
    def one(q):
        # EQUAL-OPPORTUNITY verification: the reference must be independently
        # confirmable through BOTH access paths, else the question is unfair
        # to one arm and is dropped.
        verdicts = []
        for arm in ('files', 'mcp'):
            prompt = (tmpl.replace('{QUESTION}', q['question'])
                      .replace('{REFERENCE}', q['reference']).replace('{EVIDENCE}', q.get('evidence', '')))
            d = headless(prompt, a.verifier_model, arm=arm)
            r = (d or {}).get('result', '')
            m = re.search(r'VERDICT:\s*(\w+)', r)
            verdicts.append((arm, m.group(1) if m else 'UNVERIFIABLE', r[:120]))
        combined = 'CONFIRMED' if all(v == 'CONFIRMED' for _, v, _ in verdicts) else \
                   '/'.join(f'{a_}:{v}' for a_, v, _ in verdicts)
        return q['id'], combined, ' | '.join(n for _, _, n in verdicts)
    todo = [q for q in bank if q['id'] not in verdicts]
    print(f'  verifying {len(todo)} references (model={a.verifier_model}) …')
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        for fut in as_completed([ex.submit(one, q) for q in todo]):
            qid, verdict, note = fut.result()
            verdicts[qid] = {'verdict': verdict, 'note': note}
            print(f'  {qid}: {verdict}')
            json.dump(verdicts, open(vp, 'w'), indent=1)
    kept = [q for q in bank if verdicts.get(q['id'], {}).get('verdict') == 'CONFIRMED']
    dropped = [q['id'] for q in bank if q['id'] not in {k['id'] for k in kept}]
    json.dump(kept, open(f'{K}/bank.json', 'w'), indent=1)
    print(f'  bank after verification: {len(kept)} kept, dropped {dropped or "none"}')

# --------------------------------------------------------------------- run
def stage_run(a):
    bank = {q['id']: q for q in json.load(open(f'{K}/bank.json'))}
    arms = a.arms.split(',')
    cells = [(qid, arm, rep) for rep in range(1, a.reps + 1)
             for qid in bank for arm in arms
             if not os.path.exists(f'{OUT}/{qid}_{arm}_r{rep}.json')
             or os.path.getsize(f'{OUT}/{qid}_{arm}_r{rep}.json') == 0]
    print(f'  {len(cells)} cells to run (model={a.model}, concurrency={a.concurrency})')
    env = dict(os.environ, BENCH_MODEL=a.model)
    def one(cell):
        qid, arm, rep = cell
        r = subprocess.run(['zsh', f'{K}/run_one.sh', qid, arm, str(rep), bank[qid]['question']],
                           capture_output=True, text=True, env=env, timeout=3600)
        return f'{qid}_{arm}_r{rep}: {(r.stdout or r.stderr).strip()[:80]}'
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        for fut in as_completed([ex.submit(one, c) for c in cells]):
            print(' ', fut.result(), flush=True)

# ------------------------------------------------------------------- judge
def stage_judge(a):
    bank = json.load(open(f'{K}/bank.json'))
    arms = a.arms.split(',')
    cells = [(q['id'], arm, rep) for rep in range(1, a.reps + 1) for q in bank for arm in arms]
    env = dict(os.environ, BENCH_JUDGE_MODEL=a.judge_model)
    def one(cell):
        qid, arm, rep = cell
        r = subprocess.run(['zsh', f'{K}/judge_one.sh', qid, arm, str(rep)],
                           capture_output=True, text=True, env=env, timeout=1200)
        return f'{qid}_{arm}_r{rep}: {(r.stdout or r.stderr).strip()[:60]}'
    with ThreadPoolExecutor(max_workers=min(4, a.concurrency)) as ex:
        for fut in as_completed([ex.submit(one, c) for c in cells]):
            print(' ', fut.result(), flush=True)

# ------------------------------------------------------------------ report
def collect_rows(a):
    bank = {q['id']: q for q in json.load(open(f'{K}/bank.json'))}
    rows = []
    for qid, q in bank.items():
        for arm in ARMS_ALL:
            for rep in range(1, a.reps + 1):
                p = f'{OUT}/{qid}_{arm}_r{rep}.json'
                if not os.path.exists(p) or os.path.getsize(p) == 0:
                    continue
                try:
                    d = json.load(open(p))
                except Exception:
                    continue
                score, reason = None, ''
                jp = f'{OUT}/judge_{qid}_{arm}_r{rep}.json'
                if os.path.exists(jp):
                    try:
                        jr = json.load(open(jp)).get('result', '')
                        m = re.search(r'SCORE:\s*([\d.]+)', jr)
                        score = float(m.group(1)) if m else None
                    except Exception:
                        pass
                dnf = d.get('subtype') == 'error_max_turns' or not d.get('result')
                if dnf and score is None:
                    score = 0.0
                u = d.get('usage', {})
                rows.append({'qid': qid, 'arm': arm, 'rep': rep,
                             'category': q.get('category'), 'difficulty': q.get('difficulty'),
                             'provenance': q.get('provenance'), 'day': q.get('day'),
                             'score': score, 'dnf': dnf,
                             'cost': d.get('total_cost_usd', 0),
                             'secs': d.get('duration_ms', 0) / 1000,
                             'turns': d.get('num_turns', 0),
                             'out_tokens': u.get('output_tokens', 0)})
    return rows

def stage_report(a):
    rows = collect_rows(a)
    json.dump(rows, open(f'{K}/results.json', 'w'), indent=1)
    graded = [r for r in rows if r['score'] is not None]
    med = lambda xs: sorted(xs)[len(xs)//2] if xs else 0
    print(f'  rows: {len(rows)} ({len(graded)} graded)')
    print(f"  {'arm':8} {'n':>4} {'acc':>6} {'med$':>7} {'med s':>6} {'DNF':>4}")
    for arm in ARMS_ALL:
        s = [r for r in graded if r['arm'] == arm]
        if not s: continue
        print(f"  {arm:8} {len(s):>4} {sum(r['score'] for r in s)/len(s):>5.0%} "
              f"{med([r['cost'] for r in s]):>7.3f} {med([r['secs'] for r in s]):>6.0f} "
              f"{sum(1 for r in s if r['dnf']):>4}")

# ----------------------------------------------------------------- package
def stage_package(a):
    rows = collect_rows(a)
    bank = json.load(open(f'{K}/bank.json'))
    machine = hashlib.sha256((platform.node() + os.path.expanduser('~')).encode()).hexdigest()[:12]
    qmeta = [{k: q.get(k) for k in
              (['id', 'category', 'difficulty', 'provenance', 'day'] +
               (['question', 'reference'] if a.include_questions else []))} for q in bank]
    claude_v = sh(['claude', '--version'], timeout=60).stdout.strip()
    scope_v = sh(['claudescope', '--version'], timeout=60).stdout.strip() or \
              (sh(['claudescope', 'status'], timeout=60).stdout.split() or [''])[0]
    sub = {'harness_version': VERSION,
           'machine_id': machine,
           'date': datetime.date.today().isoformat(),
           'platform': platform.system(),
           'tool_versions': {'claude_cli': claude_v, 'claudescope': scope_v},
           'config': {'protocol': 'v2-hybrid-curation-dual-verify',
                      'reps': a.reps, 'arms': a.arms.split(','), 'model': a.model,
                      'judge_model': a.judge_model, 'n_questions': len(bank),
                      'window_days': a.window_days},
           'questions': qmeta,
           'runs': rows}
    json.dump(sub, open(f'{K}/submission.json', 'w'), indent=1)
    print(f'  wrote submission.json (machine {machine}, {len(rows)} runs, '
          f'question text {"INCLUDED" if a.include_questions else "excluded"})')
    print('  review it, then share submission.json with the study author.')

# ------------------------------------------------------------------- clean
def stage_clean(a):
    """Delete the transcript buckets created by this benchmark's own headless
    runs (curators, verifiers, measured runs, judges all execute with
    cwd=<kit>/runhome), then ask claudescope to reindex so they drop out of
    the index. Touches ONLY directories matching this kit's runhome slug."""
    runhome = os.path.realpath(f'{K}/runhome')
    slug = '-' + re.sub(r'[^A-Za-z0-9]+', '-', runhome).strip('-')
    proj = os.path.expanduser('~/.claude/projects')
    targets = []
    if os.path.isdir(proj):
        for d in os.listdir(proj):
            if d == slug or d.endswith(slug[-60:]):
                targets.append(os.path.join(proj, d))
    if not targets:
        print('  nothing to clean (no benchmark transcript buckets found)')
        return
    n = sum(len(files) for t in targets for _, _, files in os.walk(t))
    for t in targets:
        print(f'  {"deleting" if a.yes else "would delete"}: {t} ({n} files)')
    if not a.yes:
        print('  dry run — re-run as `bench.py clean --yes` to delete')
        return
    for t in targets:
        shutil.rmtree(t)
    # nudge claudescope to drop the deleted sessions from its index
    dj = os.path.expanduser('~/.claudescope/daemon.json')
    try:
        port = json.load(open(dj)).get('port', 4317)
        import urllib.request
        req = urllib.request.Request(f'http://127.0.0.1:{port}/api/reindex', method='POST')
        urllib.request.urlopen(req, timeout=120).read()
        print('  deleted + claudescope reindexed')
    except Exception:
        print('  deleted; claudescope will drop them on its next start/reindex')

# -------------------------------------------------------------------- main
STAGES = {'preflight': stage_preflight, 'curate': stage_curate, 'verify': stage_verify,
          'run': stage_run, 'judge': stage_judge, 'report': stage_report,
          'package': stage_package, 'clean': stage_clean}

p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
p.add_argument('stage', choices=list(STAGES) + ['all'])
p.add_argument('--questions', type=int, default=40)
p.add_argument('--reps', type=int, default=3)
p.add_argument('--arms', default='mcp,files,hybrid,skill')
p.add_argument('--model', default='claude-sonnet-5')
p.add_argument('--curator-model', default='claude-opus-4-8')
p.add_argument('--verifier-model', default='claude-sonnet-5')
p.add_argument('--judge-model', default='claude-opus-4-8')
p.add_argument('--concurrency', type=int, default=5)
p.add_argument('--window-days', type=int, default=21)
p.add_argument('--include-questions', action='store_true')
p.add_argument('--yes', action='store_true', help='confirm deletion for the clean stage')
a = p.parse_args()

if a.stage == 'all':
    if not stage_preflight(a):
        sys.exit(1)
    for s in ('curate', 'verify', 'run', 'judge', 'report', 'package'):
        print(f'== {s} ==')
        STAGES[s](a)
else:
    print(f'== {a.stage} ==')
    r = STAGES[a.stage](a)
    if a.stage == 'preflight' and not r:
        sys.exit(1)
