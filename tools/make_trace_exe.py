"""Build a tracing copy of WINGS.EXE (never touches original/).

Patch: the `call flip` at 0x367A3 in match_main's frame loop is redirected to a hook placed in the
dead function at 0xB92C (845 bytes, no direct or indirect references). Once per frame, after the
simulation tick and before flip(), the hook:
  1. on first call: malloc()s a 4 MB RAM buffer (page aligned) and fread()s SCRIPT.BIN
     (1 byte per frame) into a second buffer; writes a header page;
  2. appends a 512-byte record for this frame (8 records per 4 KB page, never straddling pages);
  3. writes the next frame's scripted key state into the live key table 0x5E3D4 using player 0's
     own key bindings (player+0x88..0x8C); script byte bit k -> key flag k (+0x90 + 4k);
  4. tail-jumps to flip() (0x109E0).

No DOS file writes are made: stdio writes from inside the match ran away (multi-GB zero-filled
TRACE.BIN; root cause not identified, see docs/systems/loop-timing.md). DOSBox-X maps guest RAM
from a host file (`memory file=`), and tools/trace_extract.py scans that file for the
self-describing pages (CWSDPMI paging means linear != physical, hence page-local records).

Header page ("WHDR"): char magic[4]="WHDR"; u32 zero; i32 g_gravity; f32 g_air_drag_f;
  i32 opt_gravity_pct; i32 opt_air_res_pct; i32 dir72[72][2]; i32 dir360[360][2];
  u8 ship_type_hdr[0x24] (of players[0].ship_type); i32 level_w; i32 level_h
Record (512 B): char magic[4]="WREC"; u32 frame_counter; u8 player0[0x128];
  u8 keytable_frame[128] (0x5E4D4..); padding

usage: make_trace_exe.py <src WINGS.EXE> <dst WINGS.EXE> [--teleport X Y]
  --teleport: at the end of frame 1 move player 0 to pixel (X,Y) with zero sub-pixel and
  velocity, so scripted flights start in open air (trace frame 1 = pre-teleport state).
"""
import struct
import sys
from keystone import Ks, KS_ARCH_X86, KS_MODE_32

STUB = 0x800
CAVE = 0xB92C
CAVE_SIZE = 845
CALL_SITE = 0x367A3
FLIP = 0x109E0
LIBC = dict(fopen=0x48FA8, fread=0x48E7C, fclose=0x49148, malloc=0x4B7A4)
FRAME_COUNTER = 0x9D744
PLAYERS = 0x9B444
KEYTAB = 0x5E3D4
KEYTAB_FRAME = 0x5E4D4
BUF_SIZE = 0x400000
REC = 512


def va2off(va):
    return va - 0x10A8 + STUB + 0xA8


def build(data_base, teleport=None):
    rbuf, wptr, sbuf, slen = data_base, data_base + 4, data_base + 8, data_base + 12
    s_script, s_rb = data_base + 16, data_base + 27
    L = LIBC

    def cp(src, n):
        return f"""
        mov esi, {src}
        mov ecx, {n:#x}
        rep movsb"""

    tele = ''
    if teleport:
        tx, ty = teleport
        tele = f"""
        mov dword ptr [{PLAYERS:#x}], {tx}
        mov dword ptr [{PLAYERS + 4:#x}], {ty}
        mov dword ptr [{PLAYERS + 8:#x}], 0
        mov dword ptr [{PLAYERS + 12:#x}], 0
        mov dword ptr [{PLAYERS + 16:#x}], 0
        mov dword ptr [{PLAYERS + 20:#x}], 0"""
    asm = f"""
        pushad
        cld
        mov eax, dword ptr [{rbuf:#x}]
        test eax, eax
        jnz have
        push {BUF_SIZE + 0x1000:#x}
        call {L['malloc']:#x}
        add esp, 4
        add eax, 0xfff
        and eax, 0xfffff000
        mov dword ptr [{rbuf:#x}], eax
        push 0x10000
        call {L['malloc']:#x}
        add esp, 4
        mov dword ptr [{sbuf:#x}], eax
        push {s_rb:#x}
        push {s_script:#x}
        call {L['fopen']:#x}
        add esp, 8
        test eax, eax
        jz noscript
        mov ebx, eax
        push ebx
        push 0x10000
        push 1
        push dword ptr [{sbuf:#x}]
        call {L['fread']:#x}
        add esp, 16
        mov dword ptr [{slen:#x}], eax
        push ebx
        call {L['fclose']:#x}
        add esp, 4
    noscript:
        mov edi, dword ptr [{rbuf:#x}]
        mov dword ptr [edi], 0x52444857
        mov dword ptr [edi + 4], 0
        add edi, 8
        {cp('0x9ab74', 16)}
        {cp('0x9bd8c', 0x240)}
        {cp('0x9bfcc', 0xb40)}
        mov esi, dword ptr [0x9b45c]
        imul esi, esi, 900
        add esi, dword ptr [0x9b434]
        mov ecx, 0x24
        rep movsb
        {cp('0x9ae00', 8)}
        mov edi, dword ptr [{rbuf:#x}]
        add edi, 0x1000
        mov dword ptr [{wptr:#x}], edi
        {tele}
    have:
        mov edi, dword ptr [{wptr:#x}]
        mov eax, dword ptr [{rbuf:#x}]
        add eax, {BUF_SIZE:#x}
        cmp edi, eax
        jae inputs
        mov dword ptr [edi], 0x43455257
        mov eax, dword ptr [{FRAME_COUNTER:#x}]
        mov dword ptr [edi + 4], eax
        add edi, 8
        {cp(hex(PLAYERS), 0x128)}
        {cp(hex(KEYTAB_FRAME), 0x80)}
        mov edi, dword ptr [{wptr:#x}]
        add edi, {REC:#x}
        mov dword ptr [{wptr:#x}], edi
    inputs:
        mov eax, dword ptr [{FRAME_COUNTER:#x}]
        xor ebx, ebx
        cmp eax, dword ptr [{slen:#x}]
        jae apply
        mov edx, dword ptr [{sbuf:#x}]
        movzx ebx, byte ptr [edx + eax]
    apply:
        xor ecx, ecx
    keyloop:
        movzx edx, byte ptr [ecx + {PLAYERS + 0x88:#x}]
        mov eax, ebx
        shr eax, cl
        and eax, 1
        mov byte ptr [edx + {KEYTAB:#x}], al
        inc ecx
        cmp ecx, 5
        jb keyloop
        popad
        jmp {FLIP:#x}
    """
    ks = Ks(KS_ARCH_X86, KS_MODE_32)
    code, _ = ks.asm(asm, CAVE)
    return bytes(code)


def main():
    src, dst = sys.argv[1], sys.argv[2]
    teleport = None
    if '--teleport' in sys.argv:
        i = sys.argv.index('--teleport')
        teleport = (int(sys.argv[i + 1]), int(sys.argv[i + 2]))
    d = bytearray(open(src, 'rb').read())
    code = build(CAVE + 0x200, teleport)
    data_base = (CAVE + len(code) + 3) & ~3
    code = build(data_base, teleport)
    assert (CAVE + len(code) + 3) & ~3 == data_base
    data = struct.pack('<IIII', 0, 0, 0, 0) + b'SCRIPT.BIN\0' + b'rb\0' + b'WHOOKv2'
    blob = code + b'\0' * (data_base - CAVE - len(code)) + data
    assert len(blob) <= CAVE_SIZE, len(blob)
    o = va2off(CAVE)
    d[o:o + CAVE_SIZE] = blob + b'\xCC' * (CAVE_SIZE - len(blob))
    c = va2off(CALL_SITE)
    assert d[c] == 0xE8 and struct.unpack_from('<i', d, c + 1)[0] + CALL_SITE + 5 == FLIP
    struct.pack_into('<i', d, c + 1, CAVE - (CALL_SITE + 5))
    open(dst, 'wb').write(d)
    print(f'hook {len(code)} B code + data @ {data_base:#x}; wrote {dst}')


if __name__ == '__main__':
    main()
