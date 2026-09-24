"""Python front end for recon/tests/ship_sim.c: fly the reconstructed ship (with terrain collision)
over a user-supplied level, to design capture scripts offline.

  sim = Recon('FOREST.LEV')            # finds the level in re/work or original/
  path = sim.run(x, y, script_bytes)   # list of dicts, one per tick (after the tick)

Default ship / rules: taken from the header of re/traces/lego_noinput_dosbox_mingw32.json
(default ship, gravity 100%, air resistance 100%)."""
import json
import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from lev_parse import parse  # noqa: E402

BUILD = os.path.join(ROOT, 'build', 'recon')
LEV_DIRS = ['re/work/wings/LEV', 're/work/LEV_hidden', 'original/wings140/LEV', 'original/wingslev']
KEYS = ['x', 'y', 'xsub', 'ysub', 'vx', 'vy', 'angle10', 'hp', 'on_own_base', 'on_any_base', 'material']


def find_level(name):
    for d in LEV_DIRS:
        p = os.path.join(ROOT, d, name)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(name)


def build():
    os.makedirs(BUILD, exist_ok=True)
    exe = os.path.join(BUILD, 'ship_sim' + ('.exe' if os.name == 'nt' else ''))
    src = ['recon/tests/ship_sim.c', 'recon/core/ship.c', 'recon/core/terrain.c',
           'recon/core/material.c', 'recon/core/x87.c']
    newest = max(os.path.getmtime(os.path.join(ROOT, s)) for s in src)
    if not os.path.exists(exe) or os.path.getmtime(exe) < newest:
        subprocess.run([sys.executable, '-m', 'ziglang', 'cc', '-std=c99', '-O2', '-o', exe, *src],
                       cwd=ROOT, check=True)
    return exe


def fbits(v):
    return struct.unpack('<I', struct.pack('<f', v))[0]


class Recon:
    def __init__(self, level, team=0):
        lv = parse(find_level(level))
        self.w, self.h, self.pix = lv['w'], lv['h'], lv['pixels']
        self.bin = os.path.join(BUILD, f'sim_{level}.bin')
        os.makedirs(BUILD, exist_ok=True)
        open(self.bin, 'wb').write(self.pix)
        t = json.load(open(os.path.join(ROOT, 're', 'traces', 'lego_noinput_dosbox_mingw32.json')))
        g, st = t['globals'], t['ship_type']
        self.params = (f"{self.w} {self.h} {g['g_gravity']} {g['opt_air_res_pct']} "
                       f"{fbits(g['g_air_drag_f']):x} {fbits(st['p3_thrust']):x} {st['p2_turn']} "
                       f"{st['p4_maxspeed']} {st['p5_rate']} {120 * st['p0_strength'] // 100} {team}")
        self.dir72 = ' '.join(f'{c} {s}' for c, s in t['dir72'])
        self.exe = build()

    def pixel(self, x, y):
        return self.pix[y * self.w + x] if 0 <= x < self.w and 0 <= y < self.h else 0

    def run(self, x, y, script):
        inp = f"{self.params} {x} {y} {len(script)}\n{self.dir72}\n" + ' '.join(map(str, script)) + '\n'
        out = subprocess.run([self.exe, self.bin], input=inp, capture_output=True, text=True,
                             check=True).stdout.split('\n')
        return [dict(zip(KEYS, map(int, line.split()))) for line in out if line.strip()]
