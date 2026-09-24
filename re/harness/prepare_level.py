"""Prepare the work copy (re/work/wings) for a capture on one level.

- parks every level of re/work/wings/LEV in re/work/LEV_hidden and moves only <LEVEL> into LEV
  (the game otherwise picks random levels, see wingsdecompplan.md section 10);
- zeroes the level's event trailer (rain, snow, bombing, civilians, armed civilians) in the
  work copy, so no weather or civilians interfere;
- writes LEVELS.DAT = {1, "<LEVEL>"};
- switches Options/Detail "Flowing water" (0x9AB69, OPTIONS.DAT byte 19) and "Waves"
  (0x9AB64, byte 16) off, so the level pixels stay static (checked per tick by the v4 window).
Never touches original/.
usage: prepare_level.py LEVEL.LEV"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORK = os.path.join(ROOT, 're', 'work', 'wings')
LEV = os.path.join(WORK, 'LEV')
HIDDEN = os.path.join(ROOT, 're', 'work', 'LEV_hidden')


def main():
    name = sys.argv[1].upper()
    for f in os.listdir(LEV):
        if f.upper().endswith('.LEV') and f.upper() != name:
            os.replace(os.path.join(LEV, f), os.path.join(HIDDEN, f))
    dst = os.path.join(LEV, name)
    if not os.path.exists(dst):
        os.replace(os.path.join(HIDDEN, name), dst)
    d = bytearray(open(dst, 'rb').read())
    d[-10:] = bytes(10)
    open(dst, 'wb').write(d)
    open(os.path.join(WORK, 'LEVELS.DAT'), 'wb').write(struct.pack('<I', 1) + name.encode().ljust(12, b'\0'))
    o = bytearray(open(os.path.join(WORK, 'OPTIONS.DAT'), 'rb').read())
    o[16] = 0
    o[19] = 0
    open(os.path.join(WORK, 'OPTIONS.DAT'), 'wb').write(o)
    print(f'LEV = {sorted(os.listdir(LEV))}, events off, flowing water/waves off')


if __name__ == '__main__':
    main()
