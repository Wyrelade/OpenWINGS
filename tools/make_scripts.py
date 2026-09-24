"""Generate SCRIPT.BIN input scripts for trace capture (LEGO.LEV, teleport to the 90x90 open box).

Script byte i = key flags applied on frame i+1 (see tools/make_trace_exe.py):
  bit0 thrust, bit1 fire2, bit2 left, bit3 right, bit4 fire1.
Scripts are designed offline with tools/ship_model.py so the ship stays inside the open box
(x 240..329, y 183..272 on LEGO) for as long as the script intends.

  noinput  : nothing pressed (gravity + drag fall)
  thrust   : only the thrust key (hover controller, nose stays up)
  rotate   : only the turn keys (spins while falling)
  mixed    : thrust + turn controller flying a circle, with coast and spin-only phases
  dive     : turn nose-down, then full thrust: |v| passes max_speed (2000) before the ground, so
             the ship_speed limit (thrust undo) is exercised
(these five are captured on LEGO with teleport 284,227 and saved as lego_<kind>.bin)

RE-2 terrain scripts (designed with tools/recon_sim.py, i.e. recon/core incl. terrain collision):
  lego_base      : drop onto ground (damage), hop left onto the own team-0 base (40/41), repair
                   to full, lift off, spin in the air, land again (angle snaps upright)
  lego_enemybase : drop onto the team-1 base (42/43): stopped, but no base flags
  lego_neutral   : drop onto a neutral base (33-35): on_own_base, lift off, land again
  lego_water     : drop into the still-water pool (48): splash in/out, buoyancy, 0.952 drag,
                   turn upside down and thrust down, turn back and hit the ceiling
  forest_current : start inside FOREST's waterfall (49 down) -> currents 50/51, underwater hits
  forest_soft    : drop onto soft ground (96-111): halved, never damaged
  arena_indbase  : drop onto an indestructible base (38/39): on_any_base, rotation while resting
  waste_snow     : drop into snow (53, class 8) on the community level WASTE: 0.65 drag, sinks and
                   stops, thrusts out and lands in the snow again (copy original/wingslev/WASTE.lev
                   to re/work/LEV_hidden/WASTE.LEV first)
Script byte i is applied on frame i+1; the teleport happens at the end of frame 1, so the sim
starts from the teleport state with script[1:].
A manifest re/harness/scripts/captures.txt lists `name seconds level tx ty` for capture.sh.

usage: make_scripts.py <out_dir>
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ship_model as M  # noqa: E402

BOX = (240 + 6, 329 - 6, 183 + 6, 272 - 6)
CX, CY = 284, 227
T, L, R = 1, 4, 8


def start_state(dir72):
    return dict(x=CX, y=CY, xsub=0, ysub=0, vx=0, vy=0, angle10=0, angle_deg=0, p5_acc=0, p5_rate=100,
                max_speed=2000, thrust=0.06, turn_rate=50, on_base=False)


G = dict(gravity=12, air_pct=100, drag_f=0.995)


def signed_angle(p):
    a = p['angle10'] / 10
    return a - 360 if a > 180 else a


def hover_keys(p, yt, allow_turn, xt=CX):
    keys = 0
    a = signed_angle(p)
    if allow_turn:
        want = max(-35, min(35, -(0.5 * (p['x'] - xt) + 0.025 * p['vx'])))
        if want > a + 3:
            keys |= R
        elif want < a - 3:
            keys |= L
    if (p['y'] - yt) * 1.0 + p['vy'] * 0.035 > 0 and abs(a) < 70:
        keys |= T
    return keys


def simulate(script, dir72):
    p = start_state(dir72)
    path = [p]
    for b in script:
        p = M.step(p, {'thrust': b & T, 'left': b & L, 'right': b & R}, dir72, G)
        path.append(p)
    return path


def inside(p):
    return BOX[0] <= p['x'] <= BOX[1] and BOX[2] <= p['y'] <= BOX[3]


def gen(kind, n, dir72):
    import math
    script = [0] * 10
    p = simulate(script, dir72)[-1]
    mode_until, mode = 0, None
    for i in range(10, n):
        if kind == 'noinput':
            b = 0
        elif kind == 'rotate':
            b = R if (i // 40) % 2 == 0 else L
        elif kind == 'dive':
            b = R if p['angle10'] != 1800 else T
        elif kind == 'thrust':
            yt = CY + 20 * math.sin(i / 60)
            b = hover_keys(p, yt, False)
        else:  # mixed
            if i >= mode_until:
                mode = None
                if i % 150 == 60 and p['vy'] < -150 and abs(signed_angle(p)) < 10:
                    mode, mode_until = 'coast', i + 18
                elif i % 150 == 120 and abs(signed_angle(p)) < 10 and p['vy'] < 0:
                    mode, mode_until = 'spin', i + 14
            if mode == 'coast':
                b = 0
            elif mode == 'spin':
                b = R if i < mode_until - 7 else L
            else:
                xt = CX + 22 * math.cos(i / 45)
                yt = CY + 18 * math.sin(i / 45)
                b = hover_keys(p, yt, True, xt)
        script.append(b)
        p = M.step(p, {'thrust': b & T, 'left': b & L, 'right': b & R}, dir72, G)
    return script


T_, L_, R_ = T, L, R
TERRAIN = [
    # name, level, tx, ty, script
    ('lego_base', 'LEGO.LEV', 42, 40,
     [0] * 100 + [L_] * 4 + [T_] * 10 + [0] * 250 + [T_] * 25 + [0] * 150 + [L_] * 30 + [R_] * 30
     + [0] * 10 + [T_] * 8 + [0] * 120),
    ('lego_enemybase', 'LEGO.LEV', 320, 60, [0] * 150 + [T_] * 25 + [0] * 200),
    ('lego_neutral', 'LEGO.LEV', 236, 20, [0] * 150 + [T_] * 25 + [0] * 200),
    ('lego_water', 'LEGO.LEV', 90, 330,
     [0] * 250 + [R_] * 36 + [0] * 5 + [T_] * 20 + [0] * 60 + [L_] * 36 + [T_] * 60 + [0] * 200),
    ('forest_current', 'FOREST.LEV', 300, 170, [0] * 400 + [R_] * 20 + [T_] * 40 + [0] * 100),
    ('forest_soft', 'FOREST.LEV', 160, 130, [0] * 200 + [T_] * 20 + [0] * 150),
    ('arena_indbase', 'ARENA.LEV', 200, 300,
     [0] * 170 + [R_] * 30 + [0] * 20 + [T_] * 25 + [0] * 100 + [L_] * 20 + [0] * 80),
    ('waste_snow', 'WASTE.LEV', 569, 200,
     [0] * 150 + [T_] * 30 + [0] * 120 + [R_] * 10 + [T_] * 15 + [0] * 150),
]


def terrain_scripts(out):
    from recon_sim import Recon
    lines = []
    sims = {}
    for name, lev, tx, ty, script in TERRAIN:
        sim = sims.setdefault(lev, Recon(lev))
        path = sim.run(tx, ty, script[1:])
        hp = min(p['hp'] for p in path)
        feats = dict(own=sum(p['on_own_base'] for p in path), any=sum(p['on_any_base'] for p in path),
                     water=sum(p['material'] == 3 for p in path), min_hp=hp)
        open(os.path.join(out, f'{name}.bin'), 'wb').write(bytes(script))
        secs = len(script) // 50 + 30
        lines.append(f'{name} {secs} {lev} {tx} {ty}')
        print(f'{name}: {len(script)} bytes on {lev} from ({tx},{ty}); recon sim: {feats}')
    open(os.path.join(out, 'captures.txt'), 'w').write('\n'.join(lines) + '\n')


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    terrain_scripts(out)
    t = json.load(open(os.path.join(os.path.dirname(__file__), '..', 're', 'traces',
                                    'lego_noinput_dosbox_mingw32.json')))
    dir72 = t['dir72']
    for kind, n in (('noinput', 300), ('thrust', 900), ('rotate', 300), ('mixed', 1200), ('dive', 200)):
        s = gen(kind, n, dir72)
        path = simulate(s, dir72)
        air = next((i for i, p in enumerate(path) if not inside(p)), len(path))
        open(os.path.join(out, f'lego_{kind}.bin'), 'wb').write(bytes(s))
        lim = sum(1 for p, q, b in zip(path, path[1:], s) if b & T and max(abs(p['vx']), abs(p['vy'])) > 2000)
        print(f'{kind}: {len(s)} bytes, model stays in box for {air} ticks, limit checks {lim}, '
              f'thrust {sum(1 for b in s if b & T)}, turn {sum(1 for b in s if b & (L | R))}')


if __name__ == '__main__':
    main()
