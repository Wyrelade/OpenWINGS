"""Extract hook records from a DOSBox-X guest RAM file (`memory file=`) into a trace JSON.

Scans every 512-byte slot for the "WREC" magic and every 4 KB page for "WHDR" (see
tools/make_trace_exe.py for layouts). Records are keyed by frame_counter; duplicates must be
identical or extraction fails.

usage: trace_extract.py <guestmem.bin> <out.json> [--meta key=value ...]
"""
import json
import struct
import sys

sys.path.insert(0, __file__.replace("\\", "/").rsplit("/", 1)[0])
from player_layout import PLAYER_FIELDS  # noqa: E402


def decode_player(b):
    out = {}
    for name, off, fmt in PLAYER_FIELDS:
        v = struct.unpack_from('<' + fmt, b, off)[0]
        out[name] = v
    return out


def main():
    mem, outp = sys.argv[1], sys.argv[2]
    meta = dict(a.split('=', 1) for a in sys.argv[3:] if '=' in a)
    d = open(mem, 'rb').read()
    hdr = None
    recs = {}
    for off in range(0, len(d) - 512, 512):
        m = d[off:off + 4]
        if m == b'WHDR' and off % 4096 == 0 and d[off + 4:off + 8] == b'\0\0\0\0':
            h = d[off:off + 4096]
            if hdr is not None and hdr != h[:0xDC4]:
                raise SystemExit('two different headers found')
            hdr = h[:0xDC4]
        elif m == b'WREC':
            fr = struct.unpack_from('<I', d, off + 4)[0]
            body = d[off:off + 8 + 0x128 + 0x80]
            if fr in recs and recs[fr] != body:
                raise SystemExit(f'conflicting duplicate record for frame {fr}')
            recs[fr] = body
    if hdr is None:
        raise SystemExit('no WHDR page found')
    o = 8
    grav, drag_f, gpct, apct = struct.unpack_from('<ifii', hdr, o); o += 16
    dir72 = [list(struct.unpack_from('<ii', hdr, o + 8 * k)) for k in range(72)]; o += 0x240
    dir360 = [list(struct.unpack_from('<ii', hdr, o + 8 * k)) for k in range(360)]; o += 0xB40
    ship = hdr[o:o + 0x24]; o += 0x24
    lw, lh = struct.unpack_from('<ii', hdr, o)
    ship_params = dict(zip(['p0_strength', 'p1_mass', 'p2_turn', 'p3_thrust', 'p4_maxspeed',
                            'p5_rate', 'p6'],
                           struct.unpack_from('<ififiii', ship, 8)))
    frames = sorted(recs)
    gaps = [f for a, f in zip(frames, frames[1:]) if f != a + 1]
    out = {
        'meta': meta,
        'globals': {'g_gravity': grav, 'g_air_drag_f': drag_f, 'opt_gravity_pct': gpct,
                    'opt_air_res_pct': apct, 'level_w': lw, 'level_h': lh},
        'ship_type': ship_params,
        'dir72': dir72,
        'dir360': dir360,
        'first_frame': frames[0] if frames else None,
        'gaps': gaps,
        'ticks': [],
    }
    for fr in frames:
        b = recs[fr]
        p = b[8:8 + 0x128]
        out['ticks'].append({'frame': fr, 'player': decode_player(p), 'raw': p.hex()})
    json.dump(out, open(outp, 'w'), indent=None, separators=(',', ':'))
    print(f'{len(frames)} ticks (frames {frames[0] if frames else "-"}..{frames[-1] if frames else "-"}), '
          f'{len(gaps)} gaps -> {outp}')


if __name__ == '__main__':
    main()
