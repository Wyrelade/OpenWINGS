"""Replay a trace through tools/ship_model.py using the recorded key flags; report first mismatch.
usage: model_vs_trace.py <trace.json>"""
import json, sys
sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import ship_model as M
FIELDS = ['x', 'y', 'xsub', 'ysub', 'vx', 'vy', 'angle10', 'angle_deg', 'p5_acc']
t = json.load(open(sys.argv[1]))
g = {'gravity': t['globals']['g_gravity'], 'air_pct': t['globals']['opt_air_res_pct'],
     'drag_f': t['globals']['g_air_drag_f']}
ticks = t['ticks']
p = dict(ticks[0]['player'])
ok = 0
for r in ticks[1:]:
    q = r['player']
    if q['material'] != 0 or q['on_own_base'] or q['on_any_base'] or p['material'] != 0:
        print(f'stop at frame {r["frame"]}: material={q["material"]} base={q["on_own_base"]},{q["on_any_base"]}')
        break
    keys = {'thrust': q['key_thrust'], 'left': q['key_left'], 'right': q['key_right']}
    p['on_base'] = p['on_own_base'] or p['on_any_base']
    n = M.step(p, keys, t['dir72'], g)
    bad = [f for f in FIELDS if n[f] != q[f]]
    if bad:
        print(f'MISMATCH frame {r["frame"]}: ' + ', '.join(f'{f} model={n[f]} trace={q[f]}' for f in bad))
        break
    ok += 1
    p = dict(q)
print(f'{ok} consecutive ticks match')
