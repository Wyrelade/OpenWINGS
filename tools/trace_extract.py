"""Extract hook records from a DOSBox-X guest RAM file (`memory file=`) into a trace JSON.

Scans every 512-byte slot for the "WREC" magic and every 4 KB page for "WHDR" (see
tools/make_trace_exe.py for layouts). Records are keyed by frame_counter; duplicates must be
identical or extraction fails.

usage: trace_extract.py <guestmem.bin> <out.json> [--meta key=value ...]
"""
import json
import struct
import sys
import zlib

sys.path.insert(0, __file__.replace("\\", "/").rsplit("/", 1)[0])
from player_layout import PLAYER_FIELDS  # noqa: E402


HDR_LEN_V3 = 0xDC4 + 528
HDR_LEN = HDR_LEN_V3 + 16
WIN = 17
LEV_DIR = __file__.replace("\\", "/").rsplit("/", 2)[0] + '/re/work/wings/LEV'


def identify_level(w, h, sig_a, sig_b):
    """Return 'NAME.LEV:score' for the level whose rows 240 / 300 best match the in-RAM signature."""
    import glob
    import os
    from lev_parse import parse
    best = None
    # the harness parks the other levels in re/work/LEV_hidden so the game can only pick LEGO
    for f in sorted(glob.glob(LEV_DIR + '/*.LEV') + glob.glob(LEV_DIR + '/../../LEV_hidden/*.LEV')):
        lv = parse(f)
        if (lv['w'], lv['h']) != (w, h):
            continue
        px = lv['pixels']
        a = px[240 * w:240 * w + 400]
        b = px[300 * w + 200:300 * w + 328]
        score = sum(x == y for x, y in zip(a + b, sig_a + sig_b)) / 528
        if best is None or score > best[1]:
            best = (os.path.basename(f), score)
    return f'{best[0]}:{best[1]:.3f}' if best else None


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
            if hdr is not None and hdr != h[:HDR_LEN]:
                raise SystemExit('two different headers found')
            hdr = h[:HDR_LEN]
        elif m in (b'WREC', b'WRC3', b'WRC4'):
            fr = struct.unpack_from('<I', d, off + 4)[0]
            n = 1 if m == b'WREC' else 2
            body = d[off:off + 8 + 0x128 * n + 0x80 + (WIN * WIN if m == b'WRC4' else 0)]
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
    lw, lh = struct.unpack_from('<ii', hdr, o); o += 8
    sig_a, sig_b = hdr[o:o + 400], hdr[o + 400:o + 528]; o += 528
    opts = hdr[o:o + 8]; o += 8
    strength, repair = struct.unpack_from('<ii', hdr, o)
    v4 = any(b[:4] == b'WRC4' for b in recs.values())
    level_match = identify_level(lw, lh, sig_a, sig_b) if any(sig_a + sig_b) else None
    ship_params = dict(zip(['p0_strength', 'p1_mass', 'p2_turn', 'p3_thrust', 'p4_maxspeed',
                            'p5_rate', 'p6'],
                           struct.unpack_from('<ififiii', ship, 8)))
    frames = sorted(recs)
    gaps = [f for a, f in zip(frames, frames[1:]) if f != a + 1]
    out = {
        'meta': meta,
        'globals': {'g_gravity': grav, 'g_air_drag_f': drag_f, 'opt_gravity_pct': gpct,
                    'opt_air_res_pct': apct, 'level_w': lw, 'level_h': lh,
                    'level_match': level_match},
        'options': ({'raw_9ab64': opts.hex(), 'flowing_water': opts[0x9AB69 - 0x9AB64],
                     'waves': opts[0], 'ship_strength_pct': strength,
                     'g_repair': repair} if v4 else None),
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
        rec = {'frame': fr, 'player': decode_player(p), 'raw': p.hex()}
        if b[:4] in (b'WRC3', b'WRC4'):
            p1 = b[8 + 0x128:8 + 0x250]
            rec['player1'] = decode_player(p1)
        if b[:4] == b'WRC4':
            # only a CRC32 of the level window is kept: traces are committed, level pixels are not
            rec['window_crc'] = zlib.crc32(b[8 + 0x250 + 0x80:8 + 0x250 + 0x80 + WIN * WIN])
        out['ticks'].append(rec)
    json.dump(out, open(outp, 'w'), indent=None, separators=(',', ':'))
    print(f'{len(frames)} ticks (frames {frames[0] if frames else "-"}..{frames[-1] if frames else "-"}), '
          f'{len(gaps)} gaps -> {outp}')


if __name__ == '__main__':
    main()
