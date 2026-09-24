#!/usr/bin/env python3
"""Build and run the recon ship tests with `python -m ziglang cc`.

1. x87_check: recon/core/x87.c vs tools/ship_model.py on edge cases + random inputs
   (ship_speed incl. exact-integer boundaries, drag multiply incl. v % 200 == 0).
2. ship_diff: replay re/traces/lego_{noinput,thrust,rotate,mixed,dive}_dosbox_mingw32.json.
   thrust and mixed must match for >= 500 consecutive air ticks; noinput and rotate reach the
   ground after ~126 ticks and dive (ship_speed limit active on its last 15 air ticks) after 85,
   so those must match every air tick up to the landing.

Needs the user's copy of LEGO.LEV (re/work/wings/LEV/ or original/wings140/LEV/).
usage: python recon/tests/run_ship_diff.py
"""
import json
import os
import random
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import ship_model as M  # noqa: E402
from lev_parse import parse  # noqa: E402

BUILD = os.path.join(ROOT, 'build', 'recon')
CORE = ['recon/core/x87.c', 'recon/core/ship.c', 'recon/core/material.c']
CFLAGS = ['-std=c99', '-O2', '-Wall', '-Wextra', '-pedantic', '-Werror']
TRACES = ['noinput', 'thrust', 'rotate', 'mixed', 'dive']
MIN_TICKS = {'noinput': 120, 'rotate': 120, 'thrust': 500, 'mixed': 500, 'dive': 80}
FIELDS = ['frame', 'x', 'y', 'xsub', 'ysub', 'vx', 'vy', 'angle10', 'angle_deg', 'p5_acc',
          'key_thrust', 'key_left', 'key_right', 'on_base', 'flash_timer', 'push_timer',
          'push_vx', 'push_vy', 'exhaust_toggle', 'carried', 'hp']


def cc(src, out):
    exe = os.path.join(BUILD, out + ('.exe' if os.name == 'nt' else ''))
    cmd = [sys.executable, '-m', 'ziglang', 'cc', *CFLAGS, '-o', exe, src, *CORE]
    subprocess.run(cmd, cwd=ROOT, check=True)
    return exe


def fbits(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


def find_lego():
    for p in ('re/work/wings/LEV/LEGO.LEV', 'original/wings140/LEV/LEGO.LEV'):
        if os.path.exists(os.path.join(ROOT, p)):
            return os.path.join(ROOT, p)
    sys.exit('LEGO.LEV not found (user-supplied original data)')


def x87_check(exe):
    rnd = random.Random(1400)
    cases = [(0, 0), (1, 0), (-1, 0), (200, 0), (-200, 0), (2000, 0), (0, 2000), (1200, 1600),
             (-1200, 1600), (600, 800), (3000, 4000), (2001, 0), (1999, 0), (100, 0), (0, -100)]
    for k in range(1, 60):
        cases += [(100 * k, 0), (0, -100 * k), (60 * k, 80 * k), (200 * k, 1), (-200 * k, 7)]
    cases += [(rnd.randint(-6000, 6000), rnd.randint(-6000, 6000)) for _ in range(3000)]
    inp = ''.join(f'{a} {b}\n' for a, b in cases)
    out = subprocess.run([exe], input=inp, capture_output=True, text=True, check=True).stdout.split('\n')
    bad = 0
    for (a, b), line in zip(cases, out):
        got = list(map(int, line.split()))
        want = [M.ship_speed(a, b), M.drag_mul(M.K_DRAG_DEFAULT, a), M.drag_mul(M.f32(0.995), a)]
        if got != want:
            bad += 1
            if bad <= 10:
                print(f'  x87 mismatch vx={a} vy={b}: c={got} model={want}')
    print(f'x87_check: {len(cases) - bad}/{len(cases)} cases match the rational x87 model', flush=True)
    return bad == 0


def export(name, lev_bin):
    t = json.load(open(os.path.join(ROOT, 're', 'traces', f'lego_{name}_dosbox_mingw32.json')))
    g, st = t['globals'], t['ship_type']
    assert (g.get('level_match') or '').startswith('LEGO.LEV'), g
    lines = [f"{g['level_w']} {g['level_h']} {g['g_gravity']} {g['opt_air_res_pct']} "
             f"{fbits(g['g_air_drag_f']):x} {fbits(st['p3_thrust']):x} {st['p2_turn']} "
             f"{st['p4_maxspeed']} {st['p5_rate']}",
             ' '.join(f'{c} {s}' for c, s in t['dir72']), str(len(t['ticks']))]
    for r in t['ticks']:
        p = dict(r['player'], frame=r['frame'])
        p['on_base'] = 1 if (p['on_own_base'] or p['on_any_base']) else 0
        lines.append(' '.join(str(p[f]) for f in FIELDS))
    path = os.path.join(BUILD, f'{name}.txt')
    open(path, 'w').write('\n'.join(lines) + '\n')
    return path


def main():
    os.makedirs(BUILD, exist_ok=True)
    ok = x87_check(cc('recon/tests/x87_check.c', 'x87_check'))
    diff = cc('recon/tests/ship_diff.c', 'ship_diff')
    lv = parse(find_lego())
    lev_bin = os.path.join(BUILD, 'LEGO.bin')
    open(lev_bin, 'wb').write(lv['pixels'])
    for name in TRACES:
        print(f'== {name}', flush=True)
        r = subprocess.run([diff, export(name, lev_bin), lev_bin, str(MIN_TICKS[name])])
        ok &= r.returncode == 0
    print('PASS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
