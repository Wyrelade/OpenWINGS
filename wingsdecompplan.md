# Wings (1996–1999) — Reverse-Engineering & Decompilation Plan

> Living document. Update the checklists in §9 as work lands.
> Evidence tags used throughout:
> - **[C] Confirmed** — verified by byte-exact parsing, disassembly, or the original documentation.
> - **[H] Hypothesis** — plausible, supported by some evidence, NOT yet verified. Must not be treated as fact in code.
> - **[?] Unknown** — no evidence yet.
>
> Addresses are **virtual addresses (VA)** in the WINGS.EXE COFF image unless stated otherwise.
> File offset = VA − 0x800 for `.text`; VA − 0x800 for `.data` too (`.data` VA 0x55400 ↔ file 0x54C00).

---

## 1. Project goal and scope

**Long-term goal:** reconstruct Wings v1.40 (Miika Virpioja, Finland; first released 1996, v1.40 dated 19.6.1999) into understandable, documented source code, so its gameplay can be ported faithfully to a modern runtime, and then used as the core of an online hop-in multiplayer arena (10–50 players per map).

**Two strictly separated tracks:**

| Track | Purpose | Rule |
|---|---|---|
| **A. Reconstruction** (`recon/`) | Reproduce Wings 1.40 behaviour exactly: physics, weapons, terrain, rules, AI, timing. | Every behaviour must trace back to disassembly or measured ground truth. No "improvements". |
| **B. Multiplayer** (`mp/`) | Modern server-authoritative arena built *around* the verified Track A simulation core. | May change presentation, networking, scale. May change gameplay only behind explicit, documented options. |

**In scope:** WINGS.EXE game logic, all resource formats, the level editor tools (MAKELEV, LEVCONV) as format references, KEYSETUP as a key-format reference, the 10 community levels in `wingslev.zip`.

**Out of scope (for now):** matching-decompilation (byte-identical rebuild with gcc 2.7.2.1) — possible later but not required; re-distributing the original assets (they stay user-supplied — see §10 legal note); the DJGPP runtime, CWSDPMI and libc internals (identify and label, do not reconstruct).

---

## 2. Inventory of supplied files

Project root contains two archives; both extracted (unchanged) to `original/`.

| Archive | SHA-256 | Contents |
|---|---|---|
| `wings140.zip` (3,154,125 B) | `afc81e3a…80503166` | Wings v1.40 full release, 79 entries (76 files + 3 dirs) |
| `wingslev.zip` (311,603 B) | `5a85ce57…ac366579` | 10 community levels, all dated 2001 (not by the original author) |

### 2.1 `wings140.zip` → `original/wings140/`

**Executables** (all DJGPP v2 `go32` COFF, see §3.1)

| File | Size | Date | Role |
|---|---|---|---|
| `WINGS.EXE` | 654,336 | 1999-06-17 | The game. SHA-256 `f70f16ca…4b1de8` |
| `MAKELEV.EXE` | 120,832 | 1997-01-16 | Level builder: PCX(+parallax PCX) → `.LEV`. **Format reference.** |
| `LEVCONV.EXE` | 123,904 | 1997-01-16 | AUTS level → Wings `.LEV` converter. Contains the AUTS level reader. |
| `KEYSETUP.EXE` | 50,688 | 1997-01-12 | Key rebinding tool, writes `KEYS.DAT`. Built with an older libc (Feb 1996, gcc 2.7.2). |
| `CWSDPMI.EXE` | 20,217 | 1996-08-18 | Charles Sandmann's DPMI host (third-party, not reversed). |

**Game data**

| File | Size | Format status | Notes |
|---|---|---|---|
| `WINGS.SND` | 679,767 | **[C]** decoded | u16 count (=42), then 42 × {u32 length, signed 8-bit mono PCM}. Sample rate **[?]** (11025 Hz assumed for preview). |
| `WEAPONS.DAT` | 1,820 | **[C]** layout / **[H]** semantics | 35 records × 52 B: char name[20] + int32 f[8]. |
| `SHIPS/*.SHP` (12 files) | 4.9–7.2 KB | **[C]** layout / **[H]** semantics | `WSHP` magic, version, name, 7 physics params, 72 × 15×15 RLE frames. |
| `LEV/*.LEV` (22 files) | 25–309 KB | **[C]** full layout | See §3.8. |
| `W_PICT.PIC`, `W_PICT2.PIC`, `W_WEAP.PIC`, `WINGS.PIC`, `WINGS2.PIC` | 5–28 KB | **[C]** | Plain ZSoft PCX v5, 320×200×8bpp, 256-colour palette at EOF. `.PIC` is just a renamed PCX. W_PICT = explosion/effect sprite atlas; W_WEAP = small projectile/entity sprite atlas (bullets, missiles, troopers/civilian-like figures, rings — exact mapping [?]); WINGS/WINGS2 = menu backgrounds. |
| `COLORS.PCX` | 19,885 | **[C]** | 400×400 PCX palette reference for level makers. |
| `VGAFONT1.PIC` | 17,408 | **[C]** | 256 glyphs × {u16 w=8, u16 h=8, 64 raw bytes}. Not PCX despite the name. |
| `KEYS.DAT` / `KEYS.DEF` | 40 / 40 | **[C]** layout | 40 raw scancodes (0x80-bit = extended key: 0xC8 Up, 0xD0 Down, 0xCB Left, 0xCD Right). Identical files = defaults. Slot order **[H]**: 5 actions × (3-player set + 4-player set). |
| `S2ASC.DAT` | 2,560 | **[C]** | 256 × 10-byte scancode→key-name strings (used by KEYSETUP/menus). |
| `OPTIONS.DAT` | 89 | **[H]** | Saved Options menus (framerate 50 = 0x32 visible). Needs field map from the save routine (string "options.dat" @ file 0x16D60). |
| `PLAYERS.DAT` | 104 | **[H]** | 26 × int32: player count + per-player human/computer/team/show-screen. |
| `SHIPS.DAT` | 128 | **[C]** layout | 8 × {u32, char[12] ship filename}; per-player ship choice. |
| `W_SELECT.DAT` | 351 | **[?]** | u32 + per-player weapon-availability byte matrix (values 0/1). Exact shape TBD. |
| `LEVELS.DAT` | 100 | **[C]** layout | u32 count (=8) + 8 × char[12] level names. References `W_SLIDE.LEV`, which is **not** in the package (stale save). |
| `WINGS.DAT` | 280 | **[?]** | High-entropy, looks encrypted/obfuscated. Opened at startup ("File not found: wings.dat" is fatal). Probably registration/integrity data; related strings `WINGS.REG`, `(reg.)`, `rekister.txt`. |
| `DIRS.CFG` | 14 | **[C]** | Two lines: level dir (`LEV`), music dir (`MUSIC`). |
| `MENU_M.CFG` | 81 | **[C]** | Menu music playlist (lists `JANUSKI.S3M`, which is **missing** from the package). |
| `COLORS.TXT`, `MAKELEV.TXT` | | **[C]** | Level palette semantics (English + Finnish). Key design document — see §3.8. |
| `WINGS.DOC` | 10,394 | **[C]** | Manual. Zip timestamp 2006 but content dated 19.6.1999. |
| `FILE_ID.DIZ` | 122 | | "1-8 player combat game. Requires 486/VGA. SoundBlaster, modem/serial game." |
| `MUSIC/*.S3M` (10), `MUSIC/*.MOD` (3) | 63–364 KB | **[C]** standard | Standard Scream Tracker 3 / ProTracker modules, played by an in-game player (§3.7). Third-party composers (credited in WINGS.DOC). |

### 2.2 `wingslev.zip` → `original/wingslev/`

10 community levels (2001): `TUNNELS`, `MARIO3`, `STRATO`, `TRAIN`, `TRIPLANE`, `AREENA4`, `VARASTO`, `WASTE`, `BASEWAR`, `TIILITALO`. **All parse with the identical `.LEV` format [C]** — the pack is purely additional content, no engine changes needed. Notable: `BASEWAR.LEV` is 1000×1000 (largest map; good stress test for 50-player arena), `AREENA4` is 642×480 and uses nearly no colour 0 (fully drawn background band 64–79).

### 2.3 Generated so far (not original files)

| Path | Purpose |
|---|---|
| `tools/lev_parse.py` | Verified `.LEV` parser + PNG export + material histogram |
| `tools/lev_probe.py` | First-pass probe (superseded by lev_parse) |
| `tools/wings_extract.py` | PCX/SHP/font/SND/WEAPONS extractor → `extracted/` |
| `tools/exe_scan.py` | Capstone linear sweep: INT sites, port I/O, call histogram |
| `tools/exe_dis.py` | Disassemble at VA / regex find / operand xref |
| `extracted/levels/*.png` | All 31 levels (+ parallax backgrounds) rendered |
| `extracted/ships/*.png`, `extracted/sounds/*.wav`, `extracted/*.png`, `extracted/catalogue.json` | Extracted assets |

---

## 3. Initial technical findings

### 3.1 Executable format, toolchain, CPU target

- **[C]** MZ stub = DJGPP `go32stub v2.00T` ("stub.h generated from stub.asm by djasm, Sat Oct 5 1996"), which loads an appended **COFF (i386, magic 0x14C)** at file offset 0x800.
- **[C]** COFF: 3 sections, **no symbol table** (`nsyms = 0`, stripped), no relocations, no debug info.
  | Section | VA | Size | File offset |
  |---|---|---|---|
  | `.text` | 0x010A8 | 344,920 | 0x008A8 |
  | `.data` | 0x55400 | 307,200 | 0x54C00 |
  | `.bss` | 0xA0400 | 18,432 | — |
  Entry = 0x10A8. Flat 32-bit protected mode (DPMI via CWSDPMI).
- **[C]** Compiler: **gcc 2.7.2.1**, runtime **DJGPP v2.01 libc built Oct 31 1996** + **libemu** (387 emulator, Sep 19 1996). Language **C++** (mangled-style class names in error strings: `ship_type_t::load()`, `sample_t::lock_memory()`, `mod_t::lock_memory()`, `channel_t::lock_memory()`; libg++ `Virtual memory exceeded in 'new'`).
- **[C]** No overlays, no packer/compression on the EXE. Read-only data (strings, float constants, jump tables) lives **inside `.text`** (gcc 2.7 behaviour) — linear disassembly will mis-decode those areas.
- **[C]** `.data` is ~92% zero: ~280 KB of statically-allocated game arrays (object pools, buffers). Its layout will reveal pool sizes (e.g. max projectiles, max particles).
- ~~**[H]** Game code occupies roughly VA 0x1100–0x3A000; DJGPP libc/libemu/libgpp from ~0x3A000 upward.~~ **Corrected [C]** (tools/lib_match.py, exact masked-byte match): `crt0` 0x10A8–0x1550, `libemu` 0x1550–0x737C, game (+ unlabelled libgcc/libg++ 2.7) 0x737C–0x475A0, DJGPP libc 0x475A0–0x55400. ≈1,350 `push ebp` function prologues in total. gcc 2.7 `-O2` style (frame pointers kept → easy function boundaries).
- **[C]** CPU target: 386+ with optional 387 (emulated if missing); doc says 386 minimum, 486/66 recommended.
- Useful fingerprints: DJGPP v2.01 libc is publicly archived; its object code can be compiled into Ghidra FunctionID / IDA FLIRT signatures to auto-label ~all runtime functions.

### 3.2 Interrupts, hardware and libraries (from disassembly)

- **[C]** All DOS/BIOS services go through DJGPP wrappers (`__dpmi_int`, DPMI `int 31h` functions 0x0000–0x0E01). Game code uses DPMI 0x0200–0x0205 (get/set real/protected-mode vectors) via `_go32_dpmi_*` helpers (VA 0x4A744 get / 0x4A758 set).
- **[C]** Hooked hardware interrupts:
  - **INT 8 / IRQ0 (PIT)** — install at VA 0x22124: `divisor = min(1193180.0 / hz, 65535)`, PIT ch.0 mode 3 (`out 43h, 36h`). ISR at VA 0x220E0: `tick_flag[0x769F0] = 1; tick_count[0x769F4]++; EOI`.
  - **INT 9 / IRQ1 (keyboard)** — custom handler installed around VA 0x10E8B (reads port 0x60; key-state table).
  - **Sound Blaster IRQ** — around VA 0x1D0DE (vector number from BLASTER env; DSP reset string `Error: reset_dsp()`, DMA ports 0x0A/0x0B/0x0C).
  - **Serial UART IRQ** — around VA 0x1D675/0x1DAC9 (COM port base stored at 0x5F104; 15 `in`/`out` via that variable).
- **[C]** No third-party game libraries (no Allegro, MIDAS, SEAL, MikMod strings). Sound driver (`sb_lib_*`), MOD/S3M player (`mod_t`), sample mixer (`channel_t`, `sample_t`), serial/modem layer and keyboard handler are **custom code** — i.e. all of it must be reversed (or replaced for the port).
- **[C]** No IPX/NetBIOS/TCP code. Networking = **serial null-modem & Hayes modem only** (`ATS0=1`, `ATS0=0`, `CONNECT`, `Dialling…`, `Waiting for call…`).

### 3.3 Graphics / rendering

- **[C]** VGA **mode 13h** (320×200×256): `set_mode` at VA 0x10570 (`__dpmi_int(0x10)` with AX=0x13); text mode restore at 0x1058C.
- **[C]** Double-buffered: a 64,000-byte system-RAM back buffer copied with `movedata()` to 0xA0000 after waiting for vertical retrace (port 0x3DA, bit 3) — VA 0x109A4.
- **[C]** Palette via ports 0x3C7/0x3C8/0x3C9 (6-bit DAC). Palette colours 0–47 fixed by the game; 48–255 come from each level (COLORS.TXT).
- **[C]** (was [H]; confirmed by match_main render call `x-78..x+78, y-45..y+44` and a 1-player screenshot) **Per-player viewport is 157×90 pixels**, 4 viewports on the 320×200 screen (2×2 split with borders/HUD). Evidence: minimum level size 157×90; parallax background size formula `bg = level/2 + (78, 45)` ≡ `(level − view)/2 + view` for view = 157×90 (i.e. background scrolls at half speed); doc says with >4 players you choose which ≤4 are "shown". **This tiny viewport is a core part of the game feel and must be preserved (or consciously changed) in the port.**
- **[C]** Sprites: ships are 15×15, 72 frames each (see §3.8); effects/weapons come from PCX atlases (`W_PICT`, `W_PICT2`, `W_WEAP`). ~~**[H]** 72 frames = 36 rotation angles (10°) × 2 visual variants~~ **[C]** 72 frames = 72 rotations of 5°: sprite index = `angle_deg/5` (match_main draw + terrain collide).
- **[C]** Options exposed: Framerate, Stars, Parallax, Flowing water, Flowing speed, Waves → water is a simulated pixel fluid (cellular automaton on the terrain bitmap), a significant CPU and sync concern.
- **[C]** F12 screenshot writes `screen.pcx` (PCX writer in EXE — a useful debug aid: can dump the back buffer).

### 3.4 Input

- **[C]** Custom INT 9 keyboard handler, scancode-based. Up to 8 players; bindings from `KEYS.DAT` (5 actions: thrust, turn left, turn right, fire primary, fire secondary; separate layouts for 1–3 and 4-player games per WINGS.DOC).
- **[C]** Global keys: ESC pause/quit, F1 pause, F2 FPS display (`Time: %d   FPS: %.2lf`), F10 quit from pause, F12 screenshot, `c` chat (in-game results screen, remote play).
- **[C]** At a base, turn-left/turn-right cycle secondary weapons (WINGS.DOC).
- **[C]** Input is sampled once per tick: `g_keytable_live` 0x5E3D4 → snapshot 0x5E4D4 at frame start → 5 flags per player via its bound scancodes (docs/systems/input.md).

### 3.5 Game loop and timing

- **[C]** Main in-game loop around VA 0x366C0–0x367B8. Per frame: game update/draw, `flip()` (VA 0x109E0), then **busy-wait until the PIT ISR sets `tick_flag`**, clear it, repeat. PIT frequency = the *Framerate* option (global 0x9D760, default **50**). Frame counter at 0x9D744 (FPS statistic reset every 200 frames).
- **[C]** (ship block disassembled: no delta-time, all per-tick constants) The simulation advances **exactly one fixed step per displayed frame** with no delta-time: raising "Framerate" speeds the whole game up (WINGS.DOC: "change the maximum speed of the game … default 50fps"), and a slow PC slows the game down rather than dropping frames. ⇒ **Canonical tick rate = 50 Hz**, fixed-step, which is ideal for deterministic reconstruction and server simulation. Must be verified by confirming no frame-time scaling in the ship update.
- **[C]** Floating point is used in game code (~1,100 FPU instructions below VA 0x3A000), dominated by `fild/fimul/fistp` with explicit `fldcw` truncation → **mixed int/float arithmetic with truncating float→int conversions**. `sin`/`cos` are called from only ~7 sites (VA 0x340DA–0x3420C init region, 0x392B7–0x395FB) ⇒ **[H]** trig lookup tables built at startup; per-tick physics uses tables.
- **[C]** RNG: game wrapper `random_n(n) = n > 0 ? random() % n : 0` at VA 0x1AF48, **174 call sites**. ~~`rand()` at 0x4B0FC~~ corrected: 0x4B0FC is libc **`random()`** (BSD additive feedback; `srandom` 0x4ADD4); libc `rand` is 0x4B188 and unused by random_n. **[C]** Seeding: `seed_rng` 0x1AF34 = `srandom(time(0))`; serial setup re-seeds with an exchanged short seed (0x1E388, 0x1E5EB) → lockstep-synchronised RNG.

### 3.6 Gameplay systems (what we know before reversing logic)

- **Players:** 1–8, human or computer (**AI bots exist [C]**: "Human / Computer" in Players menu), teams (Team 1–4, team bases colours 40–47).
- **Modes [C]:** Default last-man-standing (last survivor must land at a base to win the match); **Deathmatch** (respawn, killer +1, suicide −1, level change after N kills); **1-player mission** (rescue 10 troopers from enemy territory, return to base).
- **Rules options [C]:** Deathmatch, Kills/level, Starting weapon (default/random/…), Weapon-ready mark, Autofire, Gravity, Air resistance, Ship strength, Load times, plus per-level Rain, Snow, Bombing, Civilians (unarmed/aggressive).
- **Bases [C]:** land to repair, switch secondary weapon, and win. Base pixels (colours 32–47) are part of the destructible terrain; 38–39 indestructible; 40–47 team-private.
- **Weapons [C] names / [H] fields:** 35 entries in `WEAPONS.DAT`:
  `Autofire, Dumbfire, Troopers, Ion cannon, Multicannon, Shotgun, Splinterbomb, Bomb, Mine, Missile, Freezer, Poison, Harpoon, Nucleus, Grenade launcher, Dirtball, Digger, Hellfire, Torpedo, Base, Cannon, Landmines, Rockets, Bats, Teleport, Gravitor, Plastic explosive, Watercannon, Fireworks, Bouncer, Net, Shield, Electric blast, Poison gas, Nuke`.
  Field hypotheses: f1 = fire mode (0 single, 1 continuous/beam, 2 troopers); f2 = reload/charge in ticks (Autofire 8, Nuke 700); f3 = shots/burst or energy; f4/f5 = magazine reload & count (Grenade launcher 250/5, Rockets 400/6, Landmines 350/8, Poison gas 450/4); f6 = effect duration (Poison 1000, Net 1000, Nuke 400); f7 = speed/range/spread (Dumbfire 150, Missile 130, Bouncer 150). **All [H]** — the EXE also hard-codes a partly different weapon-name list at VA ~0x2518B (includes "Teleport", "Gravitor"), so WEAPONS.DAT may only hold tunables.
- **Ships [C] layout / [H] semantics:** 7 header values per ship, e.g. default: `(100, 1.0, 50, 0.06, 2000, 100, 1)`. ~~Hypothesis: (int strength/HP, float mass, int thrust, float turn-rate rad/tick, int fuel/energy, int armour/size, int gun count 1–2).~~ **[C] from ship_type_t::load + player_spawn_init + ship update:** p0 strength % (HP scale), p1 mass (divides force impulses), p2 turn rate in 1/10° per tick, p3 thrust factor (× dir table ×1000), p4 max-speed box (milli-px/tick), p5 per-tick accumulator rate (effect [H]), p6 [?]. See re/types.h, docs/systems/physics.md. Compare `TIE-F (70, 0.7, 60, 0.09, 2000, 90, 1)` vs `hammer (150, 1.7, 54, 0.04, 1600, 150, 2)`: consistent with light-fast vs heavy-slow.
- **Terrain [C]:** per-pixel destructible bitmap; material class = palette index range (§3.8). Burning, soft, explosive, indestructible, fire-damage, water (+ currents), snow, bubbles.
- **Environment [C]:** random rain, snow, air bombing, civilians (optionally armed) per level probabilities.
- **Pickups [?]:** no pickup strings found yet; weapons are chosen at bases. Troopers (rescuable/deployable) and civilians are the "entities" on the map.

### 3.7 Sound and music

- **[C]** Sound Blaster (2.0+) via BLASTER env; custom DMA/DSP driver; `-S0` disables sound.
- **[C]** Effects: 42 raw signed 8-bit PCM samples in `WINGS.SND`. Mixer with configurable effect channels, quality, volumes (`Sound quality`, `Effect channels`).
- **[C]** Music: in-house MOD/S3M player (`Not an S3M file.`, `: unknown format.`); also WAV loader present (`WAVEfmt `) and **CD audio** option (`CD-player`, `Track:`).
- Port plan: effects → modern mixer (sample→event mapping must be reversed); music → libopenmpt/libxmp (no need to reconstruct the tracker player unless exact timing matters).

### 3.8 Resource formats (confirmed)

**`.LEV` level — [C] byte-exact on all 31 levels** (`tools/lev_parse.py`):

```
0x000  u8  palette[256][3]     VGA 6-bit RGB (0..63); indices 0..47 overridden by the game
0x300  u16 width, u16 height   (min 157x90)
0x304  u32 rle_size
0x308  RLE level pixels        PCX-style: b>=0xC0 → run of (b&0x3F) × next byte, else literal
       u8  has_parallax
       if has_parallax: u16 bg_w (=w/2+78), u16 bg_h (=h/2+45), u32 rle_size, RLE bg pixels
       13-byte settings trailer:
         u8  stars (0/1)
         u16 unk_2            always 2 in all 31 files  [H: format version]
         u16 rain_pct         default 8
         u16 snow_pct         default 4
         u16 bombing_pct      default 2
         u16 civilians        default 40
         u16 armed_civ_pct    default 50
```
Trailer semantics **[C]** from MAKELEV prompt order + defaults ("Rain probability? (default 8%)", "Snow (4%)", "Bombing (2%)", "Civilians? (40)", "Armed civilians? (50%)") matching the default-valued trailer `01 0200 0800 0400 0200 2800 3200`.

**Map semantics = palette index [C]** (COLORS.TXT):

| Index | Meaning |
|---|---|
| 0 | empty / background (transparent; parallax or stars visible) |
| 1–31 | reserved (16 = water source) |
| 32–37 | base; 38–39 indestructible base; 40–41/42–43/44–45/46–47 team 1–4 bases |
| 48 | water; 49/50/51 water with current down/left/right; 52 bubbles |
| 53 | snow; 54 fire (background, damages) ; 55–56 explosive |
| 57–63 | reserved |
| 64–79 | background (non-solid, drawn) |
| 80–95 | indestructible |
| 96–111 | soft |
| 112–127 | burning (flammable) |
| 128–255 | normal destructible ground |

⇒ **There is no separate collision geometry, spawn list or entity table in a level.** Collision, bases (= spawn/landing/repair points), water, hazards are all implicit in the pixel colours. Spawns **[H]** are chosen at base pixels (team bases for team play). Civilians/troopers are spawned procedurally from the trailer counts.

**`.SHP` ship — [C] layout:**
```
char magic[4] = "WSHP"; u32 version (=1); u32 name_len; char name[name_len];
i32 p0; f32 p1; i32 p2; f32 p3; i32 p4; i32 p5; i32 p6;   (semantics [H], §3.6)
72 × { u16 w (=15), u16 h (=15), u32 rle_size, RLE pixels }
```
**`WINGS.SND` — [C]** u16 n; n × {u32 len; i8 pcm[len]}.
**`WEAPONS.DAT` — [C]** 35 × {char name[20]; i32 f[8]}.
**`.PIC` — [C]** ZSoft PCX v5 8bpp (except `VGAFONT1.PIC`: 256 × {u16 w, u16 h, u8 pix[w*h]}).
**Config `.DAT` files** — see §2.1 table; exact field maps pending (derive from their save routines).

### 3.9 Networking (original)

- **[C]** Serial (COM1–4, selectable speed) and Hayes modem (answer/dial/hang-up), chat terminal, *Send/Receive options* handshake, "Remote" player type, "Show screen" to pick which players are displayed locally.
- **[H]** Lockstep peer-to-peer: each machine simulates the full game and only local inputs are exchanged per tick (the options sync + identical start, and the doc's warning that sound IRQs "disturb transmissions" → any lost byte desyncs/crashes). This would mean the original simulation is **already deterministic given identical inputs + RNG seed** — a big win for us. Verify by reversing the serial packet format.

### 3.10 Other strings / fingerprints of value

- Registration system: `WINGS.REG`, `(reg.)` marker in the weapons menu, legacy `rekister.txt` cleanup prompt, encrypted `WINGS.DAT`. v1.40 is freeware; registration gates may still exist in code paths (some weapons?) — document, don't reimplement blindly.
- Debug overlay: `Mem: %ld  %ld`, `Time: %d   FPS: %.2lf`, `Error: time not restored`.
- Class names: `ship_type_t`, `sample_t`, `mod_t`, `channel_t` → the codebase uses `_t`-suffixed C++ classes; expect `player_t`, `level_t`, `weapon_t`/`bullet_t`, etc. (names for our reconstruction should follow this convention where evidence exists).

---

## 4. Probable original architecture  **[H]**

```
main()
 ├─ init: DPMI/lock memory, rekister.txt check, load wings.dat (reg), keys.dat, S2ASC,
 │        wings.snd, W_*.PIC atlases, vgafont1, ships/*.shp, weapons.dat, *.dat configs,
 │        dirs.cfg, menu_m.cfg, music list; install INT9 keyboard; SB init (BLASTER)
 ├─ menu system (mode 13h, WINGS.PIC/WINGS2.PIC bg): Start game / Players / Remote /
 │        Ships / Levels / Weapons / Options(Sound, Detail, Event, Rules, Music, CD) / Quit
 │        Remote → Serial | Modem → chat terminal, send/receive options
 └─ match(levels[1..8]):
      load level (.LEV) → terrain bitmap + parallax + palette(48..255)
      spawn players at bases, civilians/troopers
      install PIT timer @ framerate (50 Hz)
      loop:
        read input (local keys / AI / remote serial)
        update: ships (thrust, gravity, air resistance, rotation, collision with terrain pixels)
                weapons / projectiles / explosions (terrain carving, burning, chain explosives)
                water flow CA, rain/snow/bombing, civilians, troopers
                damage, deaths, respawn (deathmatch), bases (repair, weapon swap, win)
        render: per-viewport (≤4 × 157x90): parallax bg, terrain, sprites, HUD
        flip (vsync + movedata to A000:0000); mixer/music via SB IRQ
        wait for PIT tick flag
      results: "Team N won!", "Completed!", "Draw!", "Failed!", next level / menu
```

Probable C++ classes: `ship_type_t` (static ship def from .SHP), a per-player ship instance, bullets/projectiles pool, particle/explosion pool, level/terrain, `sample_t`/`channel_t` (mixer), `mod_t` (music), serial link, menu widgets.

---

## 5. Reverse-engineering / decompilation strategy

### 5.1 Principles
1. **Ground truth beats decompiler output.** Every reconstructed function gets a behavioural test against the original running in DOSBox-X (memory snapshots / traces), not just a code review.
2. **Label runtime first, then game.** Removing ~40–50% of the binary (libc, libemu, libgpp, stub) from consideration is the fastest win.
3. **Data-first.** Formats are mostly solved; struct layouts in `.data`/heap are the next lever (pool sizes, object records).
4. **Work outward from anchors:** known strings (`ship_type_t::load()`, `weapons.dat`, option names), known globals (tick flag 0x769F0, framerate 0x9D760, frame counter 0x9D744), hardware sites (VGA, PIT, keyboard, SB, UART).
5. **Keep a single source of truth for names:** a symbol/type database checked into the repo (`re/symbols.csv`, `re/types.h`) that is re-imported into Ghidra (and exported to any other tool).

### 5.2 Tools

| Tool | Use | Status |
|---|---|---|
| **Ghidra** (11.x) | Primary disassembler/decompiler. Load `WINGS.EXE` as raw x86-32 at image base using a small loader script (or strip the 2 KB stub and load the COFF — Ghidra's COFF loader handles i386 COFF). gcc calling convention `__cdecl`, `this` in first stack arg (gcc 2.7 thiscall = cdecl). | To install |
| DJGPP 2.01 `libc.a`, `libgpp`, `libemu` (from the DJGPP archive, `djlsr201`/`djdev201`) | Build **Ghidra FunctionID** (or IDA FLIRT) signatures to auto-label runtime. | To fetch |
| **DOSBox-X** (debugger build) | Run the original; breakpoints, memory dumps, CPU logs, `LOGS`/heavy logging; ground-truth capture. DOSBox-X debugger works with DPMI code via linear addresses. | To install |
| Python + capstone 5 (installed) + Pillow/numpy (installed) | Scripted scans, format parsers, trace diffing. | ✅ in use (`tools/`) |
| Rizin/Cutter or IDA Free | Second opinion on tricky functions (optional). | Optional |
| libopenmpt | Play/verify MOD/S3M outside the game. | Later |
| Custom **trace harness** | DOSBox-X memory snapshot per tick of player/projectile pools → JSON → diff against reimplementation. | To build (M3) |

### 5.3 Method per system
1. Find the entry anchor (string/global/hardware port).
2. Decompile in Ghidra; name function, locals, globals; define structs.
3. Write a **spec note** (`docs/systems/<system>.md`) with [C]/[H] tags and addresses.
4. Re-implement in `recon/` in portable C (or C++17) using **the same integer/float semantics** (truncation, 32-bit wrap, x87 80-bit intermediate where relevant).
5. Validate with a **differential test**: same inputs + seed → compare per-tick state with DOSBox-X captures. Only then mark [C].

### 5.4 Floating-point caution
The original mixes x87 float/double math with truncating conversions. x87 uses 80-bit intermediates; SSE2 on a modern CPU does not. For exact reproduction: (a) identify every float operation in the simulation path, (b) emulate the precision where it matters (use `long double` on x86 GCC/Clang, or soft-float emulation of the specific op sequences), or (c) prove the results are insensitive. For the MP server we will likely **convert the verified simulation to fixed-point** afterwards — but only once a float reference implementation matches the original bit-for-bit or within documented tolerance.

---

## 6. Proposed source-code / module structure

```
Wings Reborn/
├─ wingsdecompplan.md          ← this document
├─ wings140.zip, wingslev.zip  ← untouched originals (never modified)
├─ original/                   ← extracted originals (read-only by convention; git-ignored)
├─ extracted/                  ← generated assets (git-ignored, regenerable)
├─ tools/                      ← Python: parsers, extractors, disasm helpers, trace diffing
├─ re/                         ← reverse-engineering database
│  ├─ ghidra/                  ← Ghidra project (or exported .gzf) + scripts
│  ├─ symbols.csv              ← VA, name, kind, confidence [C]/[H], notes
│  ├─ types.h                  ← recovered structs/classes
│  └─ traces/                  ← DOSBox-X ground-truth captures
├─ docs/
│  ├─ formats/  lev.md shp.md snd.md weapons.md pic.md dat-configs.md
│  └─ systems/  loop-timing.md physics.md weapons.md terrain.md water.md ai.md
│               rules.md render.md input.md audio.md serial.md rng.md
├─ recon/                      ← Track A: faithful reimplementation (C/C++17, SDL2 frontend)
│  ├─ core/        (pure, deterministic, no I/O — the part MP reuses)
│  │   rng.c  tables.c(sin/cos)  terrain.c  water.c  ship.c  physics.c  weapons.c
│  │   projectiles.c  explosions.c  env.c(rain/snow/bombing)  civilians.c  troopers.c
│  │   ai.c  rules.c  match.c  state.h (single struct with all sim state)
│  ├─ io/          lev.c shp.c snd.c pcx.c font.c config.c keys.c
│  ├─ platform/    sdl_video.c(320x200 mode13 emu, 4 viewports) sdl_input.c sdl_audio.c
│  ├─ tests/       format round-trip, differential tests vs traces
│  └─ main.c
└─ mp/                         ← Track B: multiplayer (later; depends on recon/core only)
   ├─ server/   authoritative sim host (headless, links recon/core)
   ├─ protocol/ message schema, snapshot/delta codec, terrain-diff codec
   └─ client/   prediction/interpolation, renderer (can be Godot/C#, web, or SDL)
```

Rule: `recon/core` has **no** platform or network dependencies and exposes `sim_step(state*, inputs[])`. MP wraps it; it never forks it.

---

## 7. Level / resource format investigation plan

| # | Item | Status | Next action |
|---|---|---|---|
| F1 | `.LEV` container, RLE, parallax, trailer | ✅ [C] | Write `docs/formats/lev.md`; add writer + round-trip test (re-encode must equal original bytes — tests RLE encoder choices of MAKELEV). |
| F2 | Trailer `u16 = 2` field | [H] version | Find the `.LEV` reader in WINGS.EXE (xref `\*.lev`, VA ~0x10B02) and confirm. |
| F3 | How colours 0–47 are overridden; which palette entries animate (water, fire, bases per team colour) | [?] | Reverse level-load + palette code (ports 0x3C8/0x3C9). |
| F4 | Spawn selection | [?] | Reverse match start: how bases/pixels are found; per-team rules. |
| F5 | `.SHP` 7 params, 72-frame ordering | ✅ [C] p0–p5, p6 [?] | Reverse `ship_type_t::load()` (error string at VA ~0x86E8) and its users. |
| F6 | `WEAPONS.DAT` 8 fields; relation to hard-coded weapon table (VA ~0x2518B) | [H] | Reverse loader (string `weapons.dat` @ ~0x252C7) and weapon-fire dispatch. |
| F7 | `WINGS.SND` sample rate & sample→event map | [?] | Reverse SB DSP time-constant programming + `play_sample(id)` call sites. |
| F8 | `OPTIONS/PLAYERS/SHIPS/LEVELS/W_SELECT/SERIAL/MUSIC.DAT` | partial: PLAYERS.DAT [C] = {u32 ver=2, u32 n, i32 team[8], i32 kind[8], i32 show[8]}; LEVELS.DAT [C] = {u32 n, char name[n][12]} matched by strcmp to LEV dir list; SERIAL.DAT read at 0x17ECC | Reverse each save routine (fwrite of globals) → field maps. |
| F9 | `WINGS.DAT` / `WINGS.REG` | [?] | Reverse loader; determine if it gates content. Low priority. |
| F10 | AUTS level format | [?] | From LEVCONV.EXE (useful for importing AUTS maps; optional). |
| F11 | `W_PICT/W_PICT2/W_WEAP` atlas sub-rectangles | [?] | Find blit calls with constant src rects. |
| F12 | Community-pack compatibility | ✅ [C] | All 10 parse identically. |

---

## 8. Milestones and phased roadmap

| Phase | Milestone | Deliverable | Exit criteria |
|---|---|---|---|
| **P0** | Survey (this doc) | Inventory, format parsers, anchors | ✅ done |
| **P1** | RE baseline | Ghidra project; runtime auto-labelled via DJGPP 2.01 signatures; ≥90% of functions classified *game* vs *runtime*; main loop call tree | `re/symbols.csv` covers all runtime + top-level game functions |
| **P2** | Ground-truth harness | DOSBox-X running Wings with scripted input; per-tick dumps of player/projectile/global state; RNG seed control | Can record and replay a 30 s 2-player match deterministically |
| **P3** | Core data structures | Player/ship struct, projectile pool, explosion/particle pool, level/terrain object, global game-state layout | `re/types.h` with every field annotated [C]/[H] |
| **P4** | Movement & collision | Ship physics (thrust, rotation, gravity, air resistance, strength), terrain collision, landing on bases | `recon/core` ship sim matches traces tick-for-tick for ≥ 10 s flights |
| **P5** | Weapons & terrain destruction | All 35 weapons, projectile behaviours, explosions, carving, burning, explosives, damage model | Differential tests per weapon |
| **P6** | World simulation | Water CA + currents, rain/snow/bombing, civilians, troopers | Visual + state diff vs original |
| **P7** | Rules, AI, match flow | Modes (last-man, deathmatch, 1-player mission), bases, teams, bot AI, level rotation | Full match reproducible from recorded inputs |
| **P8** | Faithful playable port | `recon/` SDL build: 4-viewport local play, audio, menus (can be simplified) | Side-by-side playtest indistinguishable; input replays stay in sync with original |
| **P9** | MP prototype | Headless authoritative server + client with prediction/interp; 2–8 players | Playable over internet at 100 ms RTT |
| **P10** | MP scale | 10–50 players, interest management, terrain delta codec, late join, respawn rules, big maps | 50 bots + 10 humans stable, bandwidth budget met |

Parallelisable: P5/P6 sub-systems once P3 lands; asset/format docs anytime.

---

## 9. Progress / checklist system

Status keys: `[ ]` todo · `[~]` in progress · `[x]` done · `[C]`/`[H]` evidence level of result.
Rule: a system is **done** only when its differential test passes (P2 harness).

### 9.1 Survey & formats
- [x] Extract both archives to `original/` (zips untouched)
- [x] Identify EXE format & toolchain (DJGPP v2.01, gcc 2.7.2.1, C++, stripped COFF) [C]
- [x] `.LEV` parser verified on 31/31 levels [C]
- [x] `.SHP` layout parser (12/12) [C] — semantics [H]
- [x] `WINGS.SND` container (42 samples) [C] — rate [?]
- [x] `WEAPONS.DAT` layout (35 records) [C] — semantics [H]
- [x] PCX `.PIC` + `VGAFONT1.PIC` [C]
- [x] Render all levels/backgrounds, ships, atlases to `extracted/`
- [ ] `.LEV` writer + byte-identical round-trip
- [ ] Config `.DAT` field maps (OPTIONS, PLAYERS, SHIPS, LEVELS, W_SELECT, SERIAL, MUSIC)
- [ ] `WINGS.DAT`/registration understood
- [ ] Sound sample rate + id→event table
- [ ] Atlas sub-rects for W_PICT/W_PICT2/W_WEAP

### 9.2 RE baseline
- [x] Ghidra project created, COFF loaded, `.text`/`.data`/`.bss` mapped at correct VAs (Ghidra 12.1.4 headless, `re/ghidra/`)
- [~] Runtime labelled by exact masked-byte object matching (stricter than FunctionID): crt0, libemu 2/2, libc 160 objects, 290 names → `re/runtime_symbols.csv`. **libgcc/libg++ 2.7.2.1 not obtainable** (gcc2721b.zip / lgp271b.zip removed from the DJGPP archive, not on Wayback) → still unlabelled.
- [x] Known anchors named: `timer_isr` 0x220E0, `timer_install` 0x22124, `set_mode13` 0x10570, `set_textmode` 0x1058C, `vsync_flip` 0x109A4, `flip` 0x109E0, `random_n` 0x1AF48, libc `rand` 0x4B0FC, `tick_flag` 0x769F0, `tick_count` 0x769F4, `framerate` 0x9D760, `frame_counter` 0x9D744
- [~] Main in-game loop annotated (match_main 0x34B2C: input, inlined ship update, render, ~90 world calls still unnamed); ship-update call tree done
- [ ] `.data` layout map (pools, arrays, sizes)
- [ ] String-xref table for all game strings

### 9.3 Ground truth
- [x] DOSBox-X (MinGW32 build, 80-bit FPU) running Wings `-S0`, menu driven by `autotype`
- [x] Per-tick dump: patched copy (`tools/make_trace_exe.py`) → RAM records → DOSBox-X `memory file=` → `tools/trace_extract.py` JSON
- [ ] RNG seed forcing (patch `srand` arg or set state) for reproducible runs
- [~] Input injection: hook writes SCRIPT.BIN bytes into the key table per frame (built, not yet exercised)

### 9.4 Systems (each: spec doc → recon impl → differential test)
- [x] Timing / main loop (50 Hz fixed step confirmed by disasm) [C]
- [ ] RNG usage per system
- [ ] Trig tables
- [~] Ship physics (thrust/rotate/gravity/drag): spec written (docs/systems/physics.md), recon + diff test pending
- [ ] Terrain collision & landing
- [ ] Bases (repair, weapon switch, win condition)
- [ ] Damage / ship strength / death / respawn
- [ ] Weapons 0–34 (track individually)
- [ ] Explosions & terrain carving
- [ ] Burning / explosive / soft materials
- [ ] Water flow CA, currents, bubbles, waves
- [ ] Rain / snow / bombing events
- [ ] Civilians (unarmed / aggressive)
- [ ] Troopers (weapon + 1-player mission)
- [ ] Computer-player AI
- [ ] Game modes & scoring
- [ ] Rendering: viewports, parallax, stars, HUD
- [ ] Audio: effects mixer triggers, music playlist
- [ ] Serial/modem protocol (for determinism evidence)

### 9.5 Port & multiplayer
- [ ] `recon/` SDL build playable locally
- [ ] Input-replay parity with original
- [ ] Fixed-point conversion of `recon/core` (with parity tests)
- [ ] MP server prototype, protocol, client
- [ ] 50-player load test

---

## 10. Risks, unknowns and blockers

| Risk | Impact | Mitigation |
|---|---|---|
| Stripped binary, no symbols | Slow naming | Runtime signatures; string anchors; class names in errors; consistent symbol DB |
| rodata interleaved in `.text` | Bad linear disassembly, fake functions | Use Ghidra recursive descent; mark float/string tables as data |
| x87 80-bit float semantics | Tiny drift → desync vs original | Identify float ops in sim path; `long double`/soft-float reference; then fixed-point with parity tests |
| Fixed-step speed tied to framerate option | Behaviour at non-50 settings differs | Treat 50 Hz as canonical; record framerate in traces |
| Water CA + destructible terrain are large mutable state | Sync bandwidth, late join cost | Event-based terrain edits + deterministic CA or authoritative chunk deltas (§11) |
| Custom sound/music/serial code | Large, low-value RE effort | Reverse only triggers & protocol; replace playback with libopenmpt + modern mixer |
| Registration/obfuscated `WINGS.DAT` | Hidden gating of content | Reverse loader early enough to know whether anything is disabled |
| Missing referenced files (`JANUSKI.S3M`, `W_SLIDE.LEV`) | Minor; confirm game tolerates | Note only |
| DOSBox-X determinism (timer, SB IRQ) | Flaky traces | Run with `-S0`, fixed cycles, seed forcing |
| **Legal**: Wings is freeware but © Miika Virpioja; music by third parties | Distribution of assets/port | Keep original assets user-supplied (loader reads user's copy); reconstructed code is original work; try to contact the author for blessing/licence before public release |
| **DOSBox-X FPU precision** | MSVC x64 build uses 64-bit long double → drag `trunc(0.995*v)` differs from real x87 whenever v%200==0 | Traces from the MinGW32 build; recon implements exact 64-bit-mantissa rounding; verify on traces |
| **DJGPP stdio writes in-match run away** | Trace file grew >1 GB/s of zeros (root cause [?]) | No file writes from hooks; RAM records + DOSBox-X `memory file` |
| libgcc/libg++ 2.7.2.1 archives unavailable | Part of 0x3A000–0x475A0 unlabelled | Other mirrors / rebuild from gcc 2.7.2.1 source |
| Level-size globals 0x9AE00/0x9AE04 read 800×150 at frame 1 on LEGO (400×400) | Wrong clamp/bounds assumptions | Check writer at 0x345E7 [?] |
| Scope creep toward MP before reconstruction is verified | Loss of authenticity | Hard gate: MP work uses only [C]-marked systems |

Unknowns list: viewport size per player count; exact spawn logic; AI; pickups existence; sample rate; serial protocol; `.SHP`/`WEAPONS.DAT` semantics; how deathmatch respawn location is chosen; whether any global uses delta-time.

---

## 11. Multiplayer-port considerations

### 11.1 Architecture
- **Server-authoritative, fixed tick = 50 Hz** (the original's canonical step). Server runs the unmodified `recon/core` sim for one match instance per map.
- Clients send **inputs only** (5 buttons per tick: thrust, left, right, fire1, fire2 + weapon-select at base) with tick numbers; redundancy (last N inputs per packet) to hide loss.
- Server broadcasts **snapshots** (delta-compressed vs last acked) at 20–25 Hz, plus reliable **events** (terrain edits, deaths, pickups/rescues, score).

### 11.2 What must be deterministic / authoritative

| System | Authority | Client-side |
|---|---|---|
| Player ship state (pos, vel, angle, HP, fuel/energy, weapon, ammo/reload) | **Server authoritative** | **Predicted** for local player (same `ship_step()` code), reconciled on snapshot |
| Projectiles & explosions | **Server** | Local player's own shots predicted (spawn immediately, reconcile by projectile id); others interpolated |
| Hit detection & damage | **Server only** (with lag compensation for hitscan-like beams: Ion cannon/Electric blast/Hellfire) | Cosmetic effects only |
| Terrain destruction | **Server authoritative, transmitted as deterministic edit events** (`explode(x,y,r,type,seed)`, `carve`, `burn`) applied in the same order by clients; periodic **terrain checksum** per chunk; on mismatch server sends chunk RLE | Clients apply events with the same `core` code |
| Water CA, fire spread, burning | Either (a) server-authoritative chunk deltas, or (b) deterministic lockstep on clients with checksums. Prefer (b) only if P6 proves the CA is cheap and deterministic; else (a) | — |
| RNG | **Server only** (one `rand` stream per match, identical to original algorithm for authentic distributions); events carry any seeds clients need | Never consume RNG for gameplay on clients |
| Civilians, troopers, bombing, weather | Server; weather can be seeded cosmetic | Interpolated |
| Bots (original AI) | Server | — |
| Match rules, scores, respawn, level rotation | Server | UI only |

### 11.3 Tick rate, interpolation, prediction
- Sim 50 Hz; snapshot 20–25 Hz; remote entities rendered ~2 snapshot intervals in the past (interpolation), local ship predicted and replayed on correction. Ships are fast and small (15 px) in a 157×90 viewport — **prediction error of even 2–3 px is visible**, so reconciliation should smooth over a few frames rather than snap.
- Terrain collision in prediction uses the client's terrain copy; divergence only occurs on missed edit events → covered by reliable ordered edits + checksums.

### 11.4 Scale: 10–50 players
- Original design: max 8 players, 4 viewports, maps 150–1000 px wide. 50 players on a 400×400 map is not viable — need **larger maps** (BASEWAR 1000×1000 is the best existing candidate), map tiling/stitching, or enlarged community maps; plus base count scaling (spawn/landing contention).
- **Interest management:** per-client relevance by distance around their viewport (plus margin for fast projectiles/explosions); terrain edits are global but cheap (events), snapshots are per-client filtered.
- **Bandwidth budget** (estimate): ship state ~16–20 B quantised; 50 ships × 25 Hz × 20 B ≈ 25 KB/s worst case per client before interest filtering → filter to ~10–15 visible ships ≈ 6–8 KB/s. Projectiles: send spawn events + deterministic motion (most are ballistic) instead of per-tick positions.
- Server CPU: the original ran 8 players + water CA at 50 Hz on a 486; 50 players on a modern core is trivial *except* the water CA on big maps — profile early.

### 11.5 Late joining
- Joiner receives: level id + hash, **full current terrain** as RLE diff against the pristine level (typically small), water state (if authoritative), all entity states, scores, RNG is not sent (server-only). Then normal snapshot stream.

### 11.6 Respawning
- Original deathmatch respawns at a base (spawn logic TBD, §7 F4). For a hop-in arena: respawn with invulnerability timer, choose base far from enemies, allow weapon choice at spawn (original: weapon swap at bases). Keep original rules available as "classic" preset.

### 11.7 Gameplay adaptations (Track B only, all optional/flagged)
- Viewport: original 157×90 per player. Modern screens → either keep a 157×90-proportioned world view scaled up (authentic), or enlarge the view (changes balance: long-range weapons, dodging). Default: authentic scale, configurable.
- Win condition "last survivor lands at base" → replaced by timed/score rounds in drop-in mode.
- Friendly fire, team count >4 (original team bases only 4 colours).
- Anti-cheat: server authority covers most; clients never decide hits.

---

## 12. First concrete reverse-engineering task (recommended next step)

**Task RE-1: "Main loop → ship update" — build the RE baseline and recover the player-ship struct and its per-tick movement physics.**

Why this first: movement feel is the heart of Wings and the thing the multiplayer port must preserve most exactly; it's also the anchor from which every other system (weapons, collision, damage, AI) is reached, and it forces us to set up the two pieces of infrastructure every later task needs (named Ghidra database + ground-truth traces).

Steps:
1. **Ghidra setup** — load WINGS.EXE's COFF (offset 0x800) with `.text` @ 0x10A8, `.data` @ 0x55400, `.bss` @ 0xA0400; import `re/symbols.csv` with the anchors listed in §9.2.
2. **Runtime labelling** — obtain DJGPP v2.01 `djdev201.zip` (+ `gpp` libs matching gcc 2.7.2.1), build FunctionID signatures from `libc.a`/`libemu.a`/`libgpp.a`, apply; confirm `rand` @ 0x4B0FC, `movedata` @ 0x4A684, `__dpmi_int` @ 0x4A698.
3. **Walk the frame** — from the loop at 0x366C0, identify the per-tick update dispatcher and the per-player loop; find the function that reads the key-state table (fed by the INT 9 handler at ~0x10E8B) and applies thrust/rotation.
4. **Recover `ship_type_t`** from `ship_type_t::load()` (string @ file ~0x86E8) → map the 7 `.SHP` header fields to struct members and see which are read in the ship update (turn rate, thrust, mass, strength…).
5. **Recover the per-player ship instance struct** (position, velocity — expect float or fixed-point —, angle index 0–35/71, HP, fuel, weapon slots, reload timers).
6. **Document** in `docs/systems/physics.md` with every constant (gravity, air resistance and how the Options *Gravity* / *Air resistance* settings scale them) tagged [C]/[H].
7. **Verify** with a DOSBox-X memory trace: 1-player free flight on `LEGO.LEV` (empty-ish level), record ship struct each tick for thrust-only / rotate-only / gravity-only inputs; implement `ship_step()` in `recon/core/ship.c` and diff.

Acceptance: `ship_step()` reproduces the original's position/velocity/angle for ≥ 500 consecutive ticks (10 s) across the three input scripts, with any float tolerance explicitly justified.

### RE-1 status (2026-09-23, paused at user request)
Done: git repo (published as **OpenWINGS**); Ghidra 12.1.4 + JDK 21 + DOSBox-X (MSVC and MinGW32) installed portably in `D:\programs\re`; COFF import + `ApplySymbols.java`/`ExportAll.java`; runtime labelled (290 names); ship update located (inlined in `match_main`); `player_t`/`ship_type_t` recovered (`re/types.h`); gravity/drag/Options constants; input path; RNG seeding; 157×90 viewport and 50 Hz fixed step confirmed; trace harness working; first trace `re/traces/lego_noinput_dosbox_mingw32.json` (684 ticks, gravity-only fall, first ticks hand-checked).

Next steps to finish RE-1:
1. Capture thrust-only / rotate-only traces with SCRIPT.BIN (harness supports it).
2. Implement `recon/core/ship.c` `ship_step()` (physics.md steps 1–8, 12–13; forces/collision stubbed for air-only ticks) with an exact `x87_mul_trunc`; compiler: `python -m ziglang cc` (installed).
3. Diff test vs traces (air-only windows); test both rounding models on v%200==0 ticks.
4. Resolve the 0x9AE00 level-size anomaly; name remaining match_main callees (depth 3).
Then RE-2: terrain collision/landing (`player_terrain_collide` 0x37D94, single-pixel test, already read).

---

## Appendix A — Key addresses discovered so far

| VA | What | Evidence |
|---|---|---|
| 0x010A8 | COFF entry (`start`) | COFF header [C] |
| 0x10570 | `set_mode(0x13)` via `__dpmi_int(0x10)` | disasm [C] |
| 0x1058C | `set_mode(0x03)` | disasm [C] |
| 0x109A4 | wait vsync (0x3DA) + `movedata(backbuf → 0xA0000, 64000)` | disasm [C] |
| 0x109E0 | frame flip / present (called every frame in main loop) | disasm [H] |
| ~0x10E8B | INT 9 keyboard ISR install / restore | disasm [C] |
| 0x1AF48 | `random_n(n) = rand() % n` (174 callers) | disasm [C] |
| ~0x1D0DE | Sound Blaster IRQ install | disasm [H] |
| ~0x1D675 | Serial UART IRQ install | disasm [H] |
| 0x220E0 | PIT ISR: `tick_flag=1; tick_count++; EOI` | disasm [C] |
| 0x22124 | `timer_install(hz)`: divisor = 1193180/hz (double consts @ 0x22114) | disasm [C] |
| ~0x2518B | hard-coded weapon name strings | strings [C] |
| 0x34868 | call `timer_install(framerate)` at match start | disasm [C] |
| 0x366C0–0x367B8 | in-game frame loop; FPS calc; busy-wait on `tick_flag` | disasm [C] |
| 0x4A684 | libc `movedata` (jmp stub to 0x4CA20) | [H] |
| 0x4A698 | libc `__dpmi_int` | [H] |
| 0x4A744 / 0x4A758 | `_go32_dpmi_get/set_protected_mode_interrupt_vector` | [H] |
| 0x4B0FC | libc `random` (~~rand~~, corrected) | lib match [C] |
| 0x08F04 | `ship_type_t::load()` | disasm [C] |
| 0x0903C | `ship_speed(p)` = trunc(floor(20·sqrt((vx/2000)²+(vy/2000)²))) | disasm [C] |
| 0x0909C | `player_spawn_init(p,x,y,hp)` copies ship params | disasm [C] |
| 0x092D8 | `player_apply_confusion` | disasm [C] |
| 0x0947C | `player_cycle_weapon` | disasm [C] |
| 0x0B92C | dead function (845 B), used as trace-hook cave | xref scan [C] |
| 0x1AF34 | `seed_rng` = srandom(time(0)) | disasm [C] |
| 0x34B2C | `match_main` (frame loop + inlined ship update) | disasm [C] |
| 0x3691C / 0x36F18 / 0x37D94 | player_apply_forces / apply_damage / terrain_collide | disasm [C] |
| 0x3987C / 0x39FD8 | material_class / level_get_pixel | disasm [C] |
| 0x475A0 | start of DJGPP libc (crt1.o) | lib match [C] |
| 0x491F4 / 0x491FC | sqrt / floor | disasm [C] |
| 0x4B188 | libc `rand` (not used by random_n) | lib match [C] |
| 0x5E3D4 / 0x5E4D4 | key table live / per-frame snapshot | disasm [C] |
| 0x9AB74..0x9AB80 | g_gravity, g_air_drag_f, opt_gravity_pct, opt_air_res_pct | disasm [C] |
| 0x9B434 / 0x9B444 | g_ship_types* / g_players[8] (0x128 each) | disasm [C] |
| 0x9BD84 / 0x9BD88 | current player index / player count | disasm [C] |
| 0x9BD8C / 0x9BFCC | dir tables int[72][2], int[360][2] | disasm + trace [C] |
| 0x4BA8C / 0x4BAA8 | libm `cos` / `sin` | disasm [C] |
| 0x5F104 | serial/SB I/O base port variable | disasm [H] |
| 0x769F0 / 0x769F4 | `tick_flag` / `tick_count` | disasm [C] |
| 0x9D744 | frame counter | disasm [H] |
| 0x9D760 | framerate option (PIT Hz) | disasm [C] |

### RE-1 session 2 notes (2026-09-24, stopped at user request)
- `tools/ship_model.py`: exact reference model of the air-only ship tick (x87 64-bit-mantissa rounding via rationals). `tools/model_vs_trace.py` replays traces with recorded keys.
- **[C] free-fall physics**: model matches the original tick-for-tick for 95 ticks (spawn fall) and 126 ticks (teleported no-input fall, events off) until ground contact. Gravity + drag + integration + sub-pixel semantics confirmed by trace.
- Harness: `--teleport 284 227` (centre of LEGO's largest open 90x90 box), `tools/make_scripts.py` builds noinput/thrust/rotate/mixed scripts (model keeps them airborne 900–1200 ticks), `re/harness/capture.sh` retries when the wrong level loads.
- ~~0x9AE00 level-size anomaly~~ resolved: those runs loaded **RINTAMA (800x150)** instead of LEGO; the globals are correct. Level choice is not always the LEVELS.DAT entry [?].
- **Blocker for thrust/rotate/mixed traces**: in 1-player games the ship takes damage + an impulse within ~20–50 ticks even with rain/snow/bombing/civilians set to 0 in the work-copy LEGO.LEV. Suspect 1-player mission hazards. Next try: 2-player game (PLAYERS.DAT n=2, player 2 idle). Current `lego_thrust`/`lego_rotate` traces were captured with events ON and are only valid up to frames 31/47; `lego_mixed` is valid to frame 19.
- capture.sh bug fixed (stale output file was reported as ok).
- Next: 2-player captures → implement `recon/core/ship.c` from ship_model.py → C diff test.
