"""Extract Wings 1.40 resources to PNG/WAV/JSON for inspection.

Formats implemented here were verified by exact byte-accounting (parser consumes the
whole file with no leftover). Field *meanings* of header values are hypotheses.
Usage: python tools/wings_extract.py <wings140_dir> <out_dir>
"""
import struct, os, sys, json, glob, wave
from PIL import Image

def rle(d, o, n):
    out = bytearray()
    while len(out) < n:
        b = d[o]; o += 1
        if b >= 0xC0:
            out += bytes([d[o]]) * (b & 0x3F); o += 1
        else:
            out.append(b)
    return bytes(out[:n]), o

def vga_pal(p6):
    return bytes(min(255, c * 255 // 63) for c in p6)

def read_pcx(path):
    """Standard ZSoft PCX v5, 8bpp, 1 plane; 256-colour 8-bit palette at EOF (0x0C marker)."""
    d = open(path, 'rb').read()
    assert d[0] == 0x0A and d[2] == 1 and d[3] == 8
    x0, y0, x1, y1 = struct.unpack_from('<4H', d, 4)
    bpl = struct.unpack_from('<H', d, 66)[0]
    w, h = x1 - x0 + 1, y1 - y0 + 1
    raw, o = rle(d, 128, bpl * h)
    pix = b''.join(raw[y * bpl:y * bpl + w] for y in range(h))
    pal = d[-768:] if d[-769] == 0x0C else None
    return w, h, pix, pal, len(d) - 769 - o

def ship(path):
    d = open(path, 'rb').read()
    assert d[:4] == b'WSHP'
    ver, nl = struct.unpack_from('<II', d, 4); o = 12
    name = d[o:o + nl].decode('latin1'); o += nl
    vals = struct.unpack_from('<IfIfIII', d, o); o += 28
    frames = []
    while o < len(d):
        w, h, sz = struct.unpack_from('<HHI', d, o); o += 8
        px, o2 = rle(d, o, w * h); assert o2 - o == sz; o = o2
        frames.append((w, h, px))
    return name, ver, vals, frames

def font(path):
    """VGAFONT1.PIC: sequence of glyphs: u16 w, u16 h, w*h raw bytes."""
    d = open(path, 'rb').read(); o = 0; g = []
    while o < len(d):
        w, h = struct.unpack_from('<HH', d, o); o += 4
        g.append((w, h, d[o:o + w * h])); o += w * h
    return g

def sounds(path):
    d = open(path, 'rb').read()
    n = struct.unpack_from('<H', d, 0)[0]; o = 2; out = []
    for i in range(n):
        L = struct.unpack_from('<I', d, o)[0]; o += 4
        out.append(d[o:o + L]); o += L
    assert o == len(d)
    return out

def main(src, dst):
    os.makedirs(dst, exist_ok=True)
    meta = {}
    game_pal = None
    for f in ['WINGS.PIC', 'WINGS2.PIC', 'W_PICT.PIC', 'W_PICT2.PIC', 'W_WEAP.PIC', 'COLORS.PCX']:
        w, h, pix, pal, slack = read_pcx(os.path.join(src, f))
        im = Image.frombytes('P', (w, h), pix)
        if pal: im.putpalette(pal)
        im.save(os.path.join(dst, f.replace('.', '_') + '.png'))
        meta[f] = dict(w=w, h=h, has_pal=bool(pal), rle_slack=slack)
        if f == 'COLORS.PCX': game_pal = pal
    # ships
    os.makedirs(os.path.join(dst, 'ships'), exist_ok=True)
    meta['ships'] = {}
    for f in sorted(glob.glob(os.path.join(src, 'SHIPS', '*.SHP'))):
        name, ver, vals, frames = ship(f)
        fw, fh = frames[0][0], frames[0][1]
        sheet = Image.new('P', (fw * 12, fh * ((len(frames) + 11) // 12)))
        for i, (w, h, px) in enumerate(frames):
            sheet.paste(Image.frombytes('P', (w, h), px), ((i % 12) * fw, (i // 12) * fh))
        sheet.putpalette(game_pal)
        sheet = sheet.resize((sheet.width * 4, sheet.height * 4), Image.NEAREST)
        sheet.save(os.path.join(dst, 'ships', os.path.basename(f) + '.png'))
        meta['ships'][os.path.basename(f)] = dict(name=name, version=ver, header=vals, frames=len(frames))
    # font
    g = font(os.path.join(src, 'VGAFONT1.PIC'))
    meta['VGAFONT1.PIC'] = dict(glyphs=len(g), sizes=sorted({(w, h) for w, h, _ in g}))
    # sounds (sample rate unknown -> 11025 assumed for preview only)
    os.makedirs(os.path.join(dst, 'sounds'), exist_ok=True)
    snd = sounds(os.path.join(src, 'WINGS.SND'))
    for i, s in enumerate(snd):
        with wave.open(os.path.join(dst, 'sounds', f'snd{i:02d}.wav'), 'wb') as wv:
            wv.setnchannels(1); wv.setsampwidth(1); wv.setframerate(11025)
            wv.writeframes(bytes((b + 128) & 0xFF for b in s))  # signed -> unsigned
    meta['WINGS.SND'] = dict(samples=len(snd), lengths=[len(s) for s in snd])
    # weapons
    d = open(os.path.join(src, 'WEAPONS.DAT'), 'rb').read()
    meta['WEAPONS.DAT'] = [dict(id=i, name=d[i*52:i*52+20].split(b'\0')[0].decode(),
                                fields=list(struct.unpack_from('<8i', d, i*52+20)))
                           for i in range(len(d) // 52)]
    json.dump(meta, open(os.path.join(dst, 'catalogue.json'), 'w'), indent=1)
    print(json.dumps({k: (v if k not in ('WEAPONS.DAT', 'ships') else '...') for k, v in meta.items()}, indent=1)[:3000])

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
