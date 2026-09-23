"""Disassemble WINGS.EXE .text around a VA or find instruction patterns.
usage: exe_dis.py at <va_hex> [count]   |  exe_dis.py find <regex-on-'mnemonic op_str'> [ctx]
       exe_dis.py xref <va_hex>   (instructions whose operands contain the value)"""
import struct, sys, re
from capstone import Cs, CS_ARCH_X86, CS_MODE_32
d = open('original/wings140/WINGS.EXE', 'rb').read()
STUB = 0x800
tsize, dsize = struct.unpack_from('<II', d, STUB + 24)
tbase, dbase = 0x10a8, 0x55400
text = d[STUB + 0xa8:STUB + 0xa8 + tsize]
md = Cs(CS_ARCH_X86, CS_MODE_32); md.skipdata = True
insns = list(md.disasm(text, tbase))
idx = {i.address: n for n, i in enumerate(insns)}
def show(n0, n1):
    for i in insns[max(0, n0):n1]:
        print(f'  {i.address:06x}: {i.mnemonic} {i.op_str}')
cmd = sys.argv[1]
if cmd == 'at':
    va = int(sys.argv[2], 16); c = int(sys.argv[3]) if len(sys.argv) > 3 else 40
    n = min(idx, key=lambda a: abs(a - va)); show(idx[n], idx[n] + c)
elif cmd == 'find':
    rx = re.compile(sys.argv[2]); ctx = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    for n, i in enumerate(insns):
        if rx.search(f'{i.mnemonic} {i.op_str}'):
            print(f'--- {i.address:06x}'); show(n - ctx, n + 3)
elif cmd == 'xref':
    v = sys.argv[2].lower()
    for i in insns:
        if v in i.op_str: print(f'  {i.address:06x}: {i.mnemonic} {i.op_str}')
