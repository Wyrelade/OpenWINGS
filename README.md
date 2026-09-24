# OpenWINGS

<!-- PROGRESS:BADGE -->
![named](https://img.shields.io/badge/named-40%2F975%20(4.10%25)-1f6feb)
![verified](https://img.shields.io/badge/verified-8%2F975%20(0.82%25)-2ea043)
<!-- /PROGRESS:BADGE -->
![platform](https://img.shields.io/badge/platform-DOS%20(DJGPP%20v2)-8957e5)
![license](https://img.shields.io/badge/license-MIT-blue)

An open-source, work-in-progress **behavioural decompilation** of **Wings** (v1.40), the 1–8 player
cave-flying combat game for DOS by **Miika Virpioja** (Finland, first released 1996, v1.40 dated
19.6.1999).

The goal is to recover the game's logic as readable, documented, portable C/C++ whose behaviour is
proven identical to the original by per-tick differential tests against the real executable running in
DOSBox-X. The verified simulation core is then meant to power a faithful modern port and, as a
separate track, an online drop-in multiplayer arena.

| Item | Value |
|---|---|
| Target | `WINGS.EXE` v1.40 (654,336 bytes) |
| Exe SHA-256 | `f70f16caa9672eda3d442e0b487cd673609ff48166edef3e95e49cb1204b1de8` |
| Format | DJGPP v2 `go32` stub + i386 COFF, stripped |
| Compiler | gcc 2.7.2.1 (C++), DJGPP v2.01 libc + libemu |
| Decompiler | Ghidra 12.1 (headless), plus custom Python tooling |
| Ground truth | DOSBox-X (MinGW32 build, 80-bit FPU), patched tracing copy of the EXE |
| License (project code) | MIT |

> **Bring your own copy of the game.** This repository contains no game executables, levels, sprites,
> sounds or music. Wings is © Miika Virpioja; the soundtrack belongs to its respective composers.
> Everything under `original/`, `extracted/` and `re/work/` is generated from *your own* copy
> (`wings140.zip`) and is gitignored.

## Status

Phase P1 (RE baseline) is largely done and the ground-truth harness works. Ship flight (RE-1) and
terrain collision, landing and damage (RE-2) are reconstructed: `recon/core/ship.c` + `terrain.c` reproduce
the original tick for tick on 13 traces over 4 levels — free flight, ground hits, resting, own/enemy/neutral/
indestructible bases with repair, still water, waterfall currents, soft ground and snow — including the x87
extended-precision rounding, which is emulated in portable C99. Run the diff test with
`python recon/tests/run_ship_diff.py`. The next milestone is RE-3: forces, primary weapons and projectiles.

<!-- PROGRESS:TABLE -->
| Metric | Functions | Count | Progress |
|---|---:|---:|---|
| **Named** (symbol + evidence) | 975 | 40 | `▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱` 4.10% |
| **Verified** (recon passes trace diff) | 975 | 8 | `▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱▱` 0.82% |
<!-- /PROGRESS:TABLE -->

Every finding is tagged **[C]** confirmed (disassembly plus trace), **[H]** hypothesis or **[?]**
unknown. Decompiler output is never trusted on its own.

### Highlights so far

- Fixed 50 Hz step, one simulation tick per frame, no delta-time (game speed = Framerate option).
- Positions are integer pixels plus 1/1000 sub-pixels; velocities are integer milli-pixels per tick.
- Gravity `12 * gravity% / 100`; air drag `v = trunc(0.995 * v)` per tick in x87 extended precision.
- Terrain collision tests a **single pixel**; material is the palette index of that pixel.
- Each player sees a **157×90** viewport.
- RNG is libc `random()`, seeded from `time(0)`, re-seeded from an exchanged seed in serial play
  (lockstep networking with a 2–4 frame input delay).

See [`wingsdecompplan.md`](wingsdecompplan.md) for the full plan, findings and address table, and
[`docs/systems/`](docs/systems) for per-system specs.

## Layout

| Path | What |
|---|---|
| `wingsdecompplan.md` | living RE plan: findings, checklist, risks, key addresses |
| `PROGRESS.md` | progress tracker (source of truth for the badges above) |
| `re/symbols.csv`, `re/runtime_symbols.csv` | symbol database (game / DJGPP runtime) |
| `re/types.h` | recovered structs (`player_t`, `ship_type_t`) |
| `re/ghidra/` | headless wrapper and Ghidra scripts (project binaries are gitignored) |
| `re/harness/`, `re/traces/` | DOSBox-X trace harness and captured ground-truth traces |
| `docs/systems/` | system specs: physics, loop timing, input |
| `tools/` | format parsers/extractors, disassembly helpers, runtime matcher, trace tools |
| `recon/` | faithful reimplementation (Track A): `core/` simulation, `tests/` trace diff tests |
| `mp/` | multiplayer (Track B, later; depends only on verified `recon/core`) |

## Quick start

Put your own `wings140.zip` in the repo root, then:

```
pip install capstone pillow numpy keystone-engine unicorn
unzip wings140.zip -d original/wings140          # originals stay untouched
python tools/wings_extract.py original/wings140 extracted   # assets -> PNG/WAV
python tools/lib_match.py original/wings140/WINGS.EXE <djgpp>/lib/crt0.o <djgpp>/lib/libc.a \
       <djgpp>/lib/libemu.a --csv re/runtime_symbols.csv   # DJGPP v2.01 djdev201.zip
re/ghidra/run_headless.sh <project_dir> wings -import re/work/WINGS.COFF ... \
       -postScript ApplySymbols.java re/symbols.csv
```

Capturing a trace (needs DOSBox-X MinGW32 build):

```
python tools/make_scripts.py re/harness/scripts        # scripts + captures.txt manifest
re/harness/capture.sh lego_base 44 LEGO.LEV 42 40      # name seconds level teleport-x teleport-y
```

## Contributing

1. Pick a system from `PROGRESS.md`, read its anchors in `wingsdecompplan.md` Appendix A.
2. Name functions and globals in `re/symbols.csv` with evidence tags; add structs to `re/types.h`.
3. Write or extend the spec in `docs/systems/`.
4. Reimplement in `recon/` and add a diff test against a trace. Only a passing diff test counts as verified.
5. Bump `PROGRESS.md`, run `python tools/update_readme_progress.py`, commit both.

## Credits

- **Wings** was created by **Miika Virpioja**. All credit for the original game, its design and its
  assets goes to him. This project is an unofficial fan effort, not affiliated with or endorsed by the
  author, and is intended to preserve and study the game.
- Music in the original release is by third-party tracker composers credited in `WINGS.DOC`.
- Community levels in `wingslev.zip` by their respective 2001 authors.
- Uses DJGPP (DJ Delorie et al.), CWSDPMI (Charles Sandmann), Ghidra (NSA), DOSBox-X, Capstone,
  Keystone and Unicorn as tools. None of their code is redistributed here.
- Workflow modelled on the Digimon World 2 decompilation project.

## License

The project's own code and documentation are released under the [MIT License](LICENSE). This license
does not cover Wings itself or any of its assets.
