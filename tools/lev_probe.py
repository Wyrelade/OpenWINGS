"""Probe Wings .LEV files: palette(768) + w,h(u16) + rlesize(u32) + RLE level + ... trailer."""
import struct, sys, glob, os

def unrle(d, o, n_out, n_in=None):
    out = bytearray(); start = o
    while len(out) < n_out:
        b = d[o]; o += 1
        if b >= 0xC0:
            out += bytes([d[o]]) * (b & 0x3F); o += 1
        else:
            out.append(b)
    return bytes(out[:n_out]), o, len(out) - n_out

def probe(path):
    d = open(path, 'rb').read()
    pal = d[:768]
    w, h, rs = struct.unpack_from('<HHI', d, 768)
    o = 776
    pix, end, over = unrle(d, o, w * h)
    info = dict(file=os.path.basename(path), size=len(d), w=w, h=h, rlesize=rs,
                rle_consumed=end - o, overshoot=over, rest=len(d) - end)
    return d, pal, w, h, pix, end, info

if __name__ == '__main__':
    for p in sys.argv[1:]:
        for f in sorted(glob.glob(p)):
            d, pal, w, h, pix, end, info = probe(f)
            print(info, d[end:end + 24].hex())
