"""Label DJGPP runtime functions in WINGS.EXE by exact masked-byte matching of library objects.

Each COFF object inside the given `ar` archives (libc.a, libm.a, libemu.a, ...) has its .text
section matched against WINGS.EXE .text with relocated bytes wildcarded. A unique hit gives the
link address of the whole object; every text symbol in the object is then named at
link_addr + symbol_value. Relocations are then resolved against the EXE bytes to recover the
addresses of referenced external symbols (data and functions), which are cross-checked.

This is stricter than Ghidra FunctionID (whole-object, all non-reloc bytes identical).

usage: lib_match.py <exe> <lib.a> [<lib.a> ...] [--csv out.csv] [--report out.txt]
"""
import re
import struct
import sys
from collections import defaultdict

STUB = 0x800
TEXT_VA = 0x10A8


def load_exe(path):
    d = open(path, 'rb').read()
    tsize = struct.unpack_from('<I', d, STUB + 24)[0]
    text = d[STUB + 0xA8:STUB + 0xA8 + tsize]
    return text


def ar_members(path):
    d = open(path, 'rb').read()
    if path.endswith('.o'):
        yield path.replace('\\', '/').split('/')[-1], d
        return
    assert d[:8] == b'!<arch>\n', path
    off = 8
    longnames = b''
    while off + 60 <= len(d):
        hdr = d[off:off + 60]
        name = hdr[:16].decode('latin1').strip()
        size = int(hdr[48:58].decode().strip())
        body = d[off + 60:off + 60 + size]
        if name == '//':
            longnames = body
        elif name not in ('/', '__.SYMDEF', '__.SYMDEF/', ''):
            if name.startswith('/') and name[1:].isdigit():
                i = int(name[1:])
                name = longnames[i:longnames.index(b'/', i)].decode()
            yield name.rstrip('/'), body
        off += 60 + size + (size & 1)


def parse_coff(obj):
    magic, nsec, _ts, symptr, nsyms, opthdr, _fl = struct.unpack_from('<HHIIIHH', obj, 0)
    if magic != 0x14C:
        return None
    secs = []
    o = 20 + opthdr
    for i in range(nsec):
        name, _pa, va, size, raw, relp, _ln, nrel, _nln, flags = struct.unpack_from('<8sIIIIIIHHI', obj, o + 40 * i)
        secs.append(dict(name=name.rstrip(b'\0').decode(), va=va, size=size, raw=raw, relp=relp, nrel=nrel))
    strtab_off = symptr + 18 * nsyms
    syms = {}
    i = 0
    while i < nsyms:
        e = obj[symptr + 18 * i: symptr + 18 * i + 18]
        if e[:4] == b'\0\0\0\0':
            so = struct.unpack_from('<I', e, 4)[0]
            end = obj.index(b'\0', strtab_off + so)
            nm = obj[strtab_off + so:end].decode('latin1')
        else:
            nm = e[:8].rstrip(b'\0').decode('latin1')
        val, scn, typ, scl, naux = struct.unpack_from('<IhHBB', e, 8)
        syms[i] = dict(name=nm, value=val, sec=scn, type=typ, cls=scl)
        i += 1 + naux
    for s in secs:
        s['relocs'] = [struct.unpack_from('<IIH', obj, s['relp'] + 10 * k) for k in range(s['nrel'])]
    return secs, syms


def pattern_for(sec_bytes, relocs, sec_va):
    mask = bytearray(len(sec_bytes))
    for va, _sym, _typ in relocs:
        o = va - sec_va
        for k in range(4):
            if 0 <= o + k < len(mask):
                mask[o + k] = 1
    parts = []
    run = bytearray()
    for b, m in zip(sec_bytes, mask):
        if m:
            if run:
                parts.append(re.escape(bytes(run)))
                run = bytearray()
            parts.append(b'.')
        else:
            run.append(b)
    if run:
        parts.append(re.escape(bytes(run)))
    return re.compile(b''.join(parts), re.DOTALL), len(sec_bytes) - sum(mask)


def main():
    args = sys.argv[1:]
    csv_out = report_out = None
    if '--csv' in args:
        i = args.index('--csv'); csv_out = args[i + 1]; del args[i:i + 2]
    if '--report' in args:
        i = args.index('--report'); report_out = args[i + 1]; del args[i:i + 2]
    exe, libs = args[0], args[1:]
    text = load_exe(exe)
    names = {}            # va -> (name, lib, member, kind)
    ext_refs = defaultdict(set)  # symbol name -> set of resolved VAs
    rep = []
    stats = defaultdict(lambda: [0, 0, 0])  # lib -> [objects, matched, ambiguous]
    for lib in libs:
        libname = lib.replace('\\', '/').split('/')[-1]
        for mname, obj in ar_members(lib):
            c = parse_coff(obj)
            if not c:
                continue
            secs, syms = c
            ts = [s for s in secs if s['name'] == '.text']
            if not ts or ts[0]['size'] == 0:
                continue
            t = ts[0]
            stats[libname][0] += 1
            tb = obj[t['raw']:t['raw'] + t['size']]
            pat, fixed = pattern_for(tb, t['relocs'], t['va'])
            if fixed < 12:
                rep.append(f'SKIP  {libname}:{mname} (only {fixed} fixed bytes)')
                continue
            hits = [m.start() for m in pat.finditer(text)]
            if len(hits) != 1:
                if hits:
                    stats[libname][2] += 1
                rep.append(f'{"AMBIG" if hits else "MISS "} {libname}:{mname} hits={len(hits)}')
                continue
            stats[libname][1] += 1
            base = TEXT_VA + hits[0]
            tsec = secs.index(t) + 1
            for s in syms.values():
                if s['sec'] == tsec and s['cls'] in (2, 3) and not s['name'].startswith('.') \
                        and s['name'] not in ('gcc2_compiled.', '___gnu_compiled_c', '___gnu_compiled_cplusplus'):
                    nm = s['name'][1:] if s['name'].startswith('_') else s['name']
                    kind = 'func' if s['cls'] == 2 or (s['type'] & 0x30) == 0x20 else 'label'
                    names.setdefault(base + s['value'] - t['va'], (nm, libname, mname, kind))
            # resolve references to external symbols through relocations
            for rva, symi, typ in t['relocs']:
                s = syms.get(symi)
                if not s or s['sec'] != 0 or not s['name'].startswith('_'):
                    continue
                o = hits[0] + rva - t['va']
                v = struct.unpack_from('<I', text, o)[0]
                if typ == 20:  # DISP32: pc-relative
                    v = (TEXT_VA + o + 4 + v) & 0xFFFFFFFF
                elif typ != 6:
                    continue
                ext_refs[s['name'][1:]].add(v)
            rep.append(f'MATCH {libname}:{mname} @ {base:#x} size={t["size"]:#x}')
    # external references that resolve to one address are strong evidence
    known = {n[0]: va for va, n in names.items()}
    for nm, vas in sorted(ext_refs.items()):
        if len(vas) == 1:
            va = next(iter(vas))
            if nm in known and known[nm] != va:
                rep.append(f'CONFLICT ref {nm}: object says {known[nm]:#x}, reloc says {va:#x}')
            elif nm not in known:
                names.setdefault(va, (nm, 'reloc-ref', '', 'data' if va >= 0x55400 else 'func'))
    rep.insert(0, 'lib objects matched ambiguous')
    for lib, (n, m, a) in stats.items():
        rep.insert(1, f'{lib} {n} {m} {a}')
    txt = '\n'.join(rep)
    if report_out:
        open(report_out, 'w').write(txt + '\n')
    else:
        print(txt)
    if csv_out:
        with open(csv_out, 'w', newline='\n') as f:
            f.write('va,name,kind,confidence,notes\n')
            for va in sorted(names):
                nm, lib, mem, kind = names[va]
                f.write(f'{va:#010x},{nm},{kind},C,"runtime: {lib}:{mem} exact masked-byte match"\n')
    print(f'{len(names)} names; ' + '; '.join(f'{l}: {m}/{n} objects' for l, (n, m, a) in stats.items()),
          file=sys.stderr)


if __name__ == '__main__':
    main()
