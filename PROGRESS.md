# OpenWINGS Progress Tracker

**1 system = spec doc -> `recon/` implementation -> differential test vs original traces.**
A function counts as *named* once it has a symbol in `re/symbols.csv` with evidence; it counts as
*verified* only when its behaviour is reproduced by `recon/` code and passes a trace diff test.

> The `named:` / `verified:` line below is the single source of truth for progress. After changing it,
> run `python tools/update_readme_progress.py` to regenerate the README badge and table, and commit
> both files together.

**Game functions identified: 975 · named: 25 · verified: 1**  ·  updated 2026-09-24

Runtime (not counted above, labelled automatically by `tools/lib_match.py`): crt0 + libemu + 160 DJGPP
libc objects = 290 symbols. libgcc / libg++ 2.7.2.1 still unlabelled (archives unavailable).

## Phase P1 — RE baseline

| done | step | note |
|---|---|---|
| [x] | EXE format identified | DJGPP v2 go32 COFF, gcc 2.7.2.1, C++, stripped |
| [x] | Ghidra project | headless import at correct VAs, `re/ghidra/scripts/ApplySymbols.java`, `ExportAll.java` |
| [x] | runtime labelled | exact masked-byte object matching, 290 names (`re/runtime_symbols.csv`) |
| [x] | anchors named | timer, VGA, flip, RNG, key tables, player array |
| [~] | main loop call tree | `match_main` 0x34B2C annotated; ~90 world-update callees unnamed |
| [ ] | `.data` layout map | pools and array sizes |

## Phase P2 — Ground truth

| done | step | note |
|---|---|---|
| [x] | DOSBox-X harness | MinGW32 build (80-bit FPU), `-S0`, menus via `autotype` |
| [x] | per-tick dump | patched copy -> RAM records -> DOSBox-X `memory file` -> JSON |
| [x] | first trace | `re/traces/lego_noinput_dosbox_mingw32.json` |
| [x] | input injection | SCRIPT.BIN -> key table; 5 scripted traces (noinput/thrust/rotate/mixed/dive) |
| [x] | level identity check | level pixel rows in the trace header; only LEGO.LEV left in the work-copy LEV dir |
| [ ] | RNG seed forcing | |

## Systems

| done | system | spec | recon | diff test |
|---|---|---|---|---|
| [x] | timing / 50 Hz fixed step | loop-timing.md | - | disasm |
| [x] | input sampling | input.md | - | disasm |
| [x] | ship physics, air subset (thrust, speed limit, rotate, gravity, drag, clamp) | physics.md | `recon/core/ship.c`, `x87.c` | 1021 / 1299 ticks (thrust / mixed) [C] |
| [ ] | ship push decay (force kind 3) | physics.md | ported | no trace yet |
| [ ] | terrain collision & landing (**next: RE-2**) | | | |
| [ ] | weapons 0-34 | | | |
| [ ] | explosions / terrain carving | | | |
| [ ] | water CA | | | |
| [ ] | weather, civilians, troopers | | | |
| [ ] | AI | | | |
| [ ] | rules / modes | | | |

## Session log

### 2026-09-23 — RE-1 start
Ghidra + runtime labelling, ship update found inlined in `match_main`, `player_t`/`ship_type_t`
recovered, physics constants and Options scaling, input path, RNG seeding, 157x90 viewport and
50 Hz fixed step confirmed, trace harness built. Hurdles: in-match DJGPP stdio writes run away
(worked around via guest RAM file); MSVC DOSBox-X lacks 80-bit FPU (use MinGW32 build).

### 2026-09-24 — RE-1 done
The old "1-player damage" blocker was the game loading other 400x400 levels. The harness now checks a level-pixel
signature and keeps only LEGO.LEV in the work-copy LEV dir. Clean traces: noinput, thrust, rotate, mixed, dive.
`recon/core/ship.c` + `x87.c` (portable C99, exact 64-bit-mantissa rounding without long double) match the original
free-running for 1021 (thrust) and 1299 (mixed) consecutive ticks up to landing; all 13 v%200 drag ticks confirm
x87 extended precision. Verified: `ship_speed`. decomp.dev report workflow added. Next: RE-2 terrain collision/landing.
