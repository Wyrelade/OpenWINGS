"""Static scan of WINGS.EXE (DJGPP v2 COFF) with capstone: interrupts, port I/O, calls.
Linear sweep only -> may mis-decode data embedded in .text (gcc 2.7 puts rodata there)."""
import struct, sys, collections
from capstone import Cs, CS_ARCH_X86, CS_MODE_32

path = sys.argv[1] if len(sys.argv) > 1 else 'original/wings140/WINGS.EXE'
d = open(path, 'rb').read()
STUB = 0x800
tsize = struct.unpack_from('<I', d, STUB + 20 + 4)[0]
tbase = 0x10a8; toff = STUB + 0xa8
text = d[toff:toff + tsize]
md = Cs(CS_ARCH_X86, CS_MODE_32); md.skipdata = True
ints = collections.Counter(); ports = collections.Counter(); calls = collections.Counter()
intsites = collections.defaultdict(list); prev = []
funcs = 0
for ins in md.disasm(text, tbase):
    m = ins.mnemonic
    if m == 'int':
        # record preceding "mov ah/ax/eax, imm" for DOS/BIOS function numbers
        fn = None
        for p in reversed(prev[-6:]):
            if p.mnemonic == 'mov' and p.op_str.split(',')[0] in ('ah', 'ax', 'eax', 'ax'):
                fn = p.op_str.split(',')[1].strip(); break
        ints[(ins.op_str, fn)] += 1; intsites[ins.op_str].append(hex(ins.address))
    elif m in ('in', 'out', 'insb', 'outsb', 'rep outsb', 'rep insb'):
        ops = ins.op_str
        port = None
        if 'dx' in ops:
            for p in reversed(prev[-8:]):
                if p.mnemonic == 'mov' and p.op_str.startswith(('dx,', 'edx,')):
                    port = p.op_str.split(',')[1].strip(); break
        else:
            port = ops.split(',')[0 if m == 'out' else 1].strip()
        ports[(m, port)] += 1
    elif m == 'call':
        calls[ins.op_str] += 1
    elif m == 'push' and ins.op_str == 'ebp':
        funcs += 1
    prev.append(ins)
    if len(prev) > 16: prev.pop(0)
print('text size', tsize, 'approx functions (push ebp):', funcs)
print('\nINT sites (vector, preceding ah/ax value):')
for k, v in sorted(ints.items(), key=lambda x: str(x)): print('  ', k, v)
print('\nPORT I/O (mnemonic, port):')
for k, v in sorted(ports.items(), key=lambda x: str(x)): print('  ', k, v)
print('\nTop call targets:')
for k, v in calls.most_common(40): print('  ', k, v)
