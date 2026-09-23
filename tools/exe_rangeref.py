"""List instructions with an immediate/displacement inside [lo, hi).
usage: exe_rangeref.py <lo_hex> <hi_hex>"""
import re, sys
sys.argv = [sys.argv[0], 'noop'] + sys.argv[1:]
lo, hi = int(sys.argv[2], 16), int(sys.argv[3], 16)
exec(open(__file__.replace('exe_rangeref.py', 'exe_dis.py')).read().split("cmd = sys.argv[1]")[0])
for i in insns:
    for m in re.finditer(r'0x[0-9a-f]+', i.op_str):
        v = int(m.group(), 16)
        if lo <= v < hi:
            print(f'  {i.address:06x}: {i.mnemonic} {i.op_str}'); break
