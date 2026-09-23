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
7. Gravity: if `push_timer == 0`: `vy += g_gravity`; else `v += push_v` and push_v decays toward (0,12) [C].
8. Air drag [C]: `opt_air_res_pct == 100` -> `c = 0.995` (double const 0x34B1C);
   `== 0` -> none; else `c = (float)(1 - pct*0.005/100)` (0x9AB78).
   `vx = trunc(c*vx); vy = trunc(c*vy)`.
9. `player_apply_forces` (explosion/force list 0x76A20; `v += trunc(f*dir/mass)`).
10. `player_terrain_collide` — **single pixel** test at the next position (material classes, water,
    base landing, soft/solid bounce); RE-2.
11. `player_apply_damage`.
12. Clamp next pixel to `[2, W-3] x [2, H-3]` (zeroes that velocity component).
13. Integrate: `xsub += vx; x += xsub/1000; xsub %= 1000` (C truncating division, so sub-pixel may be negative) [C, trace].

## Constants and Options
- Gravity: `g_gravity = opt_gravity_pct*12/100` (int div), default 12 milli-px/tick^2 [C].
- Drag default 0.995 -> terminal velocity ~2.4 px/tick.
- HP: `hp_max = (opt_ship_strength_pct*120/100) * p0/100` (default 120) [C].
- Ship params p0..p6 copied at spawn (`player_spawn_init` 0x909C) into +0xE8..+0xFC [C].

## Float semantics
- Every float->int is `fistp` under a control word with high byte 0x0C (RC=truncate; PC=single,
  but PC is irrelevant for fistp). Multiplies run under the default CW (DJGPP `_npxsetup`, expected 0x037F = 64-bit mantissa) [H for CW value].
- `c*v` with double 0.995 is NOT exact in 53-bit double: when `v*0.995` is an integer (v multiple of 200)
  real x87 extended gives k-1e-15 -> trunc k-1, while a 53-bit double product rounds to k.
  => reconstruction must emulate 64-bit-mantissa rounding for this multiply (helper `x87_mul_trunc`).
- DOSBox-X MSVC x64 builds emulate the FPU with 64-bit `long double`=double -> not bit-exact to real x87.
  Traces are captured with the **MinGW32 build** (x86 FPU core / 80-bit long double). Verification of the
  precision assumption is pending (compare trace vs both rounding models at v%200==0 ticks).

## Trace check (manual, lego_noinput_dosbox_mingw32.json)
Frame 1: vy = trunc(0.995*(0+12)) = 11; frame 2: trunc(0.995*23) = 22 — matches [C].

## Fixed step
No delta-time anywhere in the ship block: all updates are per-tick constants [C disasm].
Game speed therefore scales with the Framerate option (PIT Hz); canonical 50 Hz.
