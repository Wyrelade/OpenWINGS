# Main loop and timing

- `match_main` 0x34B2C: setup, then `do { ... } while(true)` frame loop [C].
- Per frame: `frame_counter++` (0x9D744); key snapshot `g_keytable_frame = g_keytable_live` (256 B);
  per-player input fetch (local keys / serial remote with 2- or 4-frame delay buffer); per-player ship
  update (inlined); per-player render into ≤4 viewports; world updates (~90 subsystem calls, unnamed);
  optional FPS overlay; `flip()` 0x109E0; busy-wait `while(!tick_flag)`; `tick_flag=0` [C].
- PIT installed with `timer_install(g_framerate)` at 0x34868; ISR 0x220E0 sets tick_flag, tick_count++ [C].
- One simulation step per displayed frame, no delta-time [C] -> fixed 50 Hz step by default.
- Frame counter starts at 1 in the first traced tick [C trace].
- Viewport: player render uses `x-78..x+78`, `y-45..y+44` => **157x90** [C disasm + screenshot, 1-player
  game shows a single centered 157x90 view].
- RNG: `seed_rng` 0x1AF34 = `srandom(time(0))`; serial setup re-seeds with an exchanged short seed
  (0x1E388, 0x1E5EB) [C] => lockstep determinism; `random_n` uses libc `random()` 0x4B0FC (not `rand`).

## Trace harness notes
- DJGPP stdio writes (fopen/fwrite/fflush) from inside the match loop produced a runaway, zero-filled
  file of >1 GB/s (tested twice, FSEXT table zeroed — still runaway). Root cause [?]
  (possibly DOSBox-X local-drive behaviour with DOS write CX=0 loops). Workaround: hook writes to RAM,
  DOSBox-X `memory file=` exposes guest RAM to the host, `tools/trace_extract.py` scans it.
