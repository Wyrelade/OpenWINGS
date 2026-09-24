# Ship physics (Wings 1.40)

Source: `match_main` 0x34B2C, per-player block ~0x3531C–0x35F00 (inlined, not a separate function).
Tags: [C] confirmed by disassembly (and trace where noted), [H] hypothesis, [?] unknown.

## Units
- Position: `x,y` int pixels + `xsub,ysub` in 1/1000 px [C].
- Velocity: `vx,vy` int, 1/1000 px per tick [C]. +y is down.
- Angle: `angle10` in 1/10 degree (0..3599), `angle_deg = angle10/10`; 0 = nose up, clockwise positive [C].
- Direction table `g_dir72[k] = {cos, sin}` for `k = angle_deg/5`, built at startup (0x340A8):
  `deg = 90 + 5k` (float accumulate), `rad = deg * 0.01745` (**not** pi/180),
  `tab = (int)floor(cos/sin(rad)*1000 + 0.5)` [C disasm; values captured in traces].
  Second table `g_dir360` (360 entries, start 270, `rad = deg*0.017453`) used by weapons/forces.

Reconstruction: `recon/core/ship.c` (`ship_step_pre` = steps 1-8, `ship_step_post` = 12-13),
`recon/core/terrain.c` (steps 10-11), `recon/core/x87.c` (exact x87 arithmetic), diff test
`recon/tests/run_ship_diff.py` (since RE-2: every tick of 13 traces incl. landings, see terrain.md).

## Per-tick order for one player (alive, not carried)
1. `player_apply_confusion` (control scramble status) [C].
2. Thrust if `key_thrust` [C]:
   - `before = (|vx|>max || |vy|>max) ? ship_speed(p) : 10000`
   - `vy -= trunc(thrust * dir72[k].sin)`; `vx -= trunc(thrust * dir72[k].cos)`
   - if `ship_speed(p) > before`: undo both (add back the same truncated values).
   - `ship_speed = trunc(floor(20 * sqrt((vx/2000f)^2 + (vy/2000f)^2)))` (1/100 px/tick).
3. Fire keys (weapons, out of RE-1 scope).
4. Rotation when not on a base: `key_right: angle10 += turn_rate`, `key_left: angle10 -= turn_rate`,
   wrap to 0..3599, `angle_deg = angle10/10`. On a base the turn keys cycle secondary weapon on release [C].
5. `p5_acc += p5_rate; n = p5_acc/100; FUN_00026440() n times; p5_acc -= 100n` [C] (effect [H]).
6. Hit-flash timer.
7. Gravity (0x35B29) [C disasm]: if `push_timer == 0`: `vy += g_gravity`. Else: `if (push_timer > 1) push_timer--;`
   `v += push_v`; then only when `push_timer == 1`: `push_vx` steps 1 toward 0, `push_vy` steps 1 toward 12,
   and `push_timer = 0` once `push_v == (0, 12)`. (Push path not yet trace-tested.)
8. Air drag [C]: `opt_air_res_pct == 100` -> `c = 0.995` (double const 0x34B1C);
   `== 0` -> none; else `c = (float)(1 - pct*0.005/100)` (0x9AB78).
   `vx = trunc(c*vx); vy = trunc(c*vy)`.
9. `player_apply_forces` (only when `hp > 0`; explosion/force list 0x76A20; `v += trunc(f*dir/mass)`,
   `damage_acc += f.damage`; a force from another player sets `last_attacker = source, attacker_age = 0`
   (0x36AAE)) [C disasm]. Not reconstructed yet.
10. `player_terrain_collide` — **single pixel** test at the next position (material classes, water,
    base landing, soft/solid bounce): docs/systems/terrain.md, `recon/core/terrain.c` [C, trace].
11. `player_apply_damage`: docs/systems/terrain.md, `recon/core/terrain.c` [C, trace].
12. Clamp (0x35CEE) [C disasm]: for x then y, if `pos + (sub + v)/1000 < 2` -> `pos = 2, v = 0, carried = 0`;
    then if `> W-3` (resp. `H-3`) -> `pos = W-3, v = 0, carried = 0`. Sub-pixel is kept.
13. Integrate: `xsub += vx; x += xsub/1000; xsub %= 1000` (C truncating division, so sub-pixel may be negative) [C, trace].
14. `exhaust_toggle ^= 1`; exhaust particle (FUN_0000dd9c) when `toggle == 1 && key_thrust && hp > 0 && !carried`;
    smoke (FUN_0000eb9c) when `hp*100/hp_max < 17 && hp > 0 && random_n(2) == 0` (consumes RNG) [C disasm].

## Constants and Options
- Gravity: `g_gravity = opt_gravity_pct*12/100` (int div), default 12 milli-px/tick^2 [C].
- Drag default 0.995 -> terminal velocity ~2.4 px/tick.
- HP: `hp_max = (opt_ship_strength_pct*120/100) * p0/100` (default 120) [C].
- Ship params p0..p6 copied at spawn (`player_spawn_init` 0x909C) into +0xE8..+0xFC [C].

## Float semantics
- Every float->int is `fistp` under a control word with high byte 0x0C (RC=truncate; PC=single,
  but PC is irrelevant for fistp). Multiplies run under the default CW with **64-bit mantissa precision [C, trace]**:
  all 13 v%200 drag ticks in the traces (below) need it.
- `c*v` with double 0.995 is NOT exact in 53-bit double: when `v*0.995` is an integer (v multiple of 200)
  real x87 extended gives k-1e-15 -> trunc k-1, while a 53-bit double product rounds to k.
  => reconstruction must emulate 64-bit-mantissa rounding for this multiply (helper `x87_mul_trunc`).
- DOSBox-X MSVC x64 builds emulate the FPU with 64-bit `long double`=double -> not bit-exact to real x87.
  Traces are captured with the **MinGW32 build** (x86 FPU core / 80-bit long double).
- `ship_speed` (0x903C) disasm order: `fld 2000.0f; fidivr vx; fidivr vy; fmul st0` (both); `faddp`;
  `fstp qword` (-> double); `fsqrt` (libm sqrt 0x491F4 is `fld qword; fsqrt`); `fmul 20.0`; `fstp qword`;
  `floor`; `fistp` (trunc). Reproduced op-by-op in `recon/core/x87.c` (portable C99, no long double).
- Thrust: `trunc(thrust_f32 * dir)` is exact in a double (24-bit x 11-bit), so a plain C cast is exact.

## Verification (2026-09-24) [C]
RE-1 (air only): `python recon/tests/run_ship_diff.py` free-ran from the first record with the recorded key
flags, no resync, and stopped at the first tick whose collision pixel is not air. Since RE-2 the same traces run
to their end, ground contact included (all ticks match) — see docs/systems/terrain.md.

| trace | consecutive matching ticks | stop |
|---|---|---|
| noinput | 126 | landing (pixel 136) |
| rotate | 126 | landing |
| thrust | **1021** | landing |
| mixed | **1299** | landing |
| dive | 85 (ship_speed limit undoes thrust on the last 15) | landing |

Fields compared every tick: x, y, xsub, ysub, vx, vy, angle10, angle_deg, p5_acc.
Drag ticks with a non-zero v multiple of 200 (13 in total, e.g. mixed frame 30: v=200 -> trace 198,
x87 198, 53-bit double 199; thrust frame 39: v=400 -> 397 / 397 / 398): the 64-bit-mantissa model matched
all 13, the double model would have diverged on all 13. `x87_check` additionally matches the rational
model (`tools/ship_model.py`) on 3310 inputs incl. exact sqrt boundaries (60k,80k), (100k,0).

## Trace check (manual, lego_noinput_dosbox_mingw32.json)
Frame 1: vy = trunc(0.995*(0+12)) = 11; frame 2: trunc(0.995*23) = 22 — matches [C].

## Fixed step
No delta-time anywhere in the ship block: all updates are per-tick constants [C disasm].
Game speed therefore scales with the Framerate option (PIT Hz); canonical 50 Hz.
