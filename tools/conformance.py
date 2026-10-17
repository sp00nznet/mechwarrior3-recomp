#!/usr/bin/env python3
"""MechWarrior 3 conformance harness (REPO_RULES section 9).

Two fixed corpora, one pass/fail count each, compared against the committed
baseline in conformance.json; a regression fails the run:

* **Milestones**: what the host prints at each stage of boot, in boot order.
  The first two need no window (a dry run maps Mech3.exe and binds its
  imports). The rest need --run, which opens the game's window, so they are
  scored only with --run, on a machine with a display (REPO_RULES section 13:
  under offstage at the console, never over RDP).
* **Lift health**: from the generated tree. Lift errors, bodies with no
  terminator, RECOMP_ITAIL targets that cannot resolve at run time, and
  UNIMPLEMENTED instructions.

The game is not in the repo. Without game/Mech3.exe and the built host this
skips with a message and exits 0, so it can sit in CI without the corpus.

    py -3 tools/conformance.py              # dry run, compare, print the table
    py -3 tools/conformance.py --run        # ...plus a 30 s run of the game (needs a display)
    py -3 tools/conformance.py --update     # ...and accept the result as the baseline
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, 'src', 'recomp', 'gen')
BASELINE = os.path.join(ROOT, 'conformance.json')

# (name, what the host prints when it is reached, needs --run). Boot order.
MILESTONES = [
    ('Mech3.exe mapped at 0x00400000', r'mapped Mech3\.exe: 0x00400000', False),
    ('every import bound', r'imports bound, 0 unresolved', False),
    ('entered the CRT startup', r'entering 0x', True),
    ('alive at 30 s, no fault', r'\[watchdog\] 30 s:', True),
]


def boot(host, run):
    args = [host, '--game', os.path.join(ROOT, 'game')] + (['--run', '--watchdog', '30'] if run else [])
    try:
        p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, errors='replace', timeout=120)
        out, code = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        out, code = (e.stdout or '') + (e.stderr or ''), 'timeout'
        out = out if isinstance(out, str) else out.decode(errors='replace')
    # A fault prints its report and stops: no later milestone can match.
    tail = [l for l in out.splitlines() if l.startswith(('===', '[watchdog]', '[exit]', '  in lifted'))]
    if '=== fault' in out:
        out = out[:out.index('=== fault')]
    passed = [name for name, pat, _ in MILESTONES if re.search(pat, out)]
    return passed, code, tail[:4]


def lift_health():
    stats = json.load(open(os.path.join(ROOT, 'work', 'lift_stats.json')))
    disp = set(re.findall(r'\{ 0x([0-9A-F]{8})u,', open(os.path.join(GEN, 'recomp_dispatch.c')).read()))
    unresolved = unimplemented = 0
    for fn in glob.glob(os.path.join(GEN, 'recomp_0*.c')):
        text = open(fn, encoding='utf-8', errors='replace').read()
        unresolved += sum(1 for t in re.findall(r'RECOMP_ITAIL\(0x([0-9A-F]{8})u\)', text) if t not in disp)
        unimplemented += text.count('UNIMPLEMENTED:')
    return {'lifted': stats['lifted'], 'errors': stats['errors'],
            'no_terminator': stats['no_terminator'], 'unresolved_itail': unresolved,
            'unimplemented': unimplemented}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--host', default=os.path.join(ROOT, 'build', 'mw3.exe'))
    ap.add_argument('--run', action='store_true', help='also run the game for 30 s (opens a window)')
    ap.add_argument('--update', action='store_true', help='accept this run as the baseline')
    args = ap.parse_args()
    if not (os.path.isfile(args.host) and os.path.isfile(os.path.join(ROOT, 'game', 'Mech3.exe'))
            and os.path.isfile(os.path.join(ROOT, 'work', 'lift_stats.json'))):
        print('conformance: skipped -- needs game/Mech3.exe (your copy of MechWarrior 3), the lift '
              'and build/mw3.exe (README, Getting Started)')
        return 0

    scored = [m for m in MILESTONES if args.run or not m[2]]
    passed, code, tail = boot(os.path.abspath(args.host), args.run)
    health = lift_health()
    now = {'milestones': len(passed), 'of': len(MILESTONES), 'run': args.run, **health}
    base = json.load(open(BASELINE)) if os.path.exists(BASELINE) else None

    print('milestones: %d/%d  (exit %s)%s' % (len(passed), len(MILESTONES), code,
                                             '' if args.run else '  -- dry run; --run scores the rest'))
    for name, _, _ in scored:
        print('  [%s] %s' % ('x' if name in passed else ' ', name))
    for l in tail:
        print('  ' + l)
    print('lift: %(lifted)d functions, %(errors)d errors, %(no_terminator)d with no terminator, '
          '%(unresolved_itail)d unresolvable ITAIL targets, %(unimplemented)d UNIMPLEMENTED '
          'instructions' % health)

    worse = []
    if base:
        # A dry run is compared only on the milestones it can reach.
        want = base['milestones'] if args.run or not base.get('run') else \
            sum(1 for m in MILESTONES if not m[2])
        if len(passed) < want:
            worse.append('milestones %d -> %d' % (want, len(passed)))
        for k in ('errors', 'no_terminator', 'unresolved_itail', 'unimplemented'):
            if now[k] > base.get(k, now[k]):
                worse.append('%s %d -> %d' % (k, base[k], now[k]))
    if args.update or not base:
        json.dump(now, open(BASELINE, 'w'), indent=1)
        print('baseline written to conformance.json')
    if worse:
        print('REGRESSION: ' + '; '.join(worse))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
