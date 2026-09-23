"""Generate SCRIPT.BIN input scripts for trace capture (LEGO.LEV, teleport to the 90x90 open box).

Script byte i = key flags applied on frame i+1 (see tools/make_trace_exe.py):
  bit0 thrust, bit1 fire2, bit2 left, bit3 right, bit4 fire1.
Scripts are designed offline with tools/ship_model.py so the ship stays inside the open box
(x 240..329, y 183..272 on LEGO) for as long as the script intends.

  noinput  : nothing pressed (gravity + drag fall)
  thrust   : only the thrust key (hover controller, nose stays up)
  rotate   : only the turn keys (spins while falling)
  mixed    : thrust + turn controller flying a circle, with coast and spin-only phases

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


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    t = json.load(open(os.path.join(os.path.dirname(__file__), '..', 're', 'traces',
                                    'lego_noinput_dosbox_mingw32.json')))
    dir72 = t['dir72']
    for kind, n in (('noinput', 300), ('thrust', 900), ('rotate', 300), ('mixed', 1200)):
        s = gen(kind, n, dir72)
        path = simulate(s, dir72)
        air = next((i for i, p in enumerate(path) if not inside(p)), len(path))
        open(os.path.join(out, f'{kind}.bin'), 'wb').write(bytes(s))
        print(f'{kind}: {len(s)} bytes, model stays in box for {air} ticks, '
              f'thrust {sum(1 for b in s if b & T)}, turn {sum(1 for b in s if b & (L | R))}')


if __name__ == '__main__':
    main()
