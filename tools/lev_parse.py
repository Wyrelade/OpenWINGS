"""Wings .LEV parser (hypothesis-verified against all 31 supplied levels).

Layout (little-endian):
  0x000  768 B   VGA palette, 256 * RGB, 6-bit components (0..63)
  0x300  u16     level width
  0x302  u16     level height
  0x304  u32     size of RLE stream in bytes
  0x308  ...     PCX-style RLE: byte>=0xC0 -> run of (b&0x3F) copies of next byte, else literal
         u8      parallax flag (0/1)
  if parallax:
         u16 bg_w, u16 bg_h, u32 rle_size, RLE bg pixels   (bg_w = w/2+78, bg_h = h/2+45)
         then 13-byte settings trailer (same as below)
  else:
         13-byte settings trailer
Trailer field meanings are UNCONFIRMED (see wingsdecompplan.md).
"""
import struct, sys, glob, os

def unrle(d, o, n):
    out = bytearray()
    while len(out) < n:
        b = d[o]; o += 1
        if b >= 0xC0:
            out += bytes([d[o]]) * (b & 0x3F); o += 1
        else:
            out.append(b)
    assert len(out) == n, 'RLE run crosses end of image'
    return bytes(out), o

def parse(path):
    d = open(path, 'rb').read()
    lv = {'file': os.path.basename(path), 'palette': d[:768]}
    w, h, rs = struct.unpack_from('<HHI', d, 768)
    lv['w'], lv['h'] = w, h
    lv['pixels'], o = unrle(d, 776, w * h)
    assert o - 776 == rs
    lv['parallax'] = d[o]; o += 1
    if lv['parallax']:
        bw, bh, brs = struct.unpack_from('<HHI', d, o); o += 8
        lv['bg_w'], lv['bg_h'] = bw, bh
        lv['bg_pixels'], o2 = unrle(d, o, bw * bh)
        assert o2 - o == brs
        o = o2
    lv['trailer'] = d[o:]
    return lv

def to_png(lv, out, bg=False):
    from PIL import Image
    pal = bytes(min(255, c * 255 // 63) for c in lv['palette'])
    if bg:
        im = Image.frombytes('P', (lv['bg_w'], lv['bg_h']), lv['bg_pixels'])
    else:
        im = Image.frombytes('P', (lv['w'], lv['h']), lv['pixels'])
    im.putpalette(pal)
    im.save(out)

if __name__ == '__main__':
    outdir = None
    args = sys.argv[1:]
    if args and args[0] == '--png':
        outdir = args[1]; args = args[2:]; os.makedirs(outdir, exist_ok=True)
    for p in args:
        for f in sorted(glob.glob(p)):
            lv = parse(f)
            hist = [0] * 256
            for px in lv['pixels']: hist[px] += 1
            cls = {'bg0': hist[0], 'res1-31': sum(hist[1:32]), 'base32-47': sum(hist[32:48]),
                   'water48-52': sum(hist[48:53]), 'snow53': hist[53], 'fire54': hist[54],
                   'explosive55-56': sum(hist[55:57]), 'bg64-79': sum(hist[64:80]),
                   'indestr80-95': sum(hist[80:96]), 'soft96-111': sum(hist[96:112]),
                   'burn112-127': sum(hist[112:128]), 'normal128+': sum(hist[128:])}
            print(f"{lv['file']:14} {lv['w']}x{lv['h']} parallax={lv['parallax']} "
                  f"{('bg %dx%d' % (lv['bg_w'], lv['bg_h'])) if lv['parallax'] else '':12} "
                  f"trailer({len(lv['trailer'])})={lv['trailer'].hex()}")
            print('   ', {k: v for k, v in cls.items() if v})
            if outdir:
                base = os.path.join(outdir, os.path.splitext(lv['file'])[0].upper())
                to_png(lv, base + '.png')
                if lv['parallax']: to_png(lv, base + '_bg.png', bg=True)
