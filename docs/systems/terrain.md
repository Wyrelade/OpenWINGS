# Terrain collision (Wings 1.40) — RE-2 prep

Source: `player_terrain_collide` 0x37D94 (2367 bytes, called once per player per tick from the ship block
after `player_apply_forces`, before `player_apply_damage`). Callees: `level_get_pixel` 0x39FD8,
`material_class` 0x3987C, 0x39A50 (water current direction [H]), 0x39A00 (base owner [H]),
`player_on_base` 0x9388, `ship_speed` 0x903C, 0xE83C (splash effect [H]), 0x1FC80 (sound [H]), 0x3A01C [?].
Tags: [C] disasm (+ trace where noted), [H] hypothesis, [?] unknown. Status: first read, not yet reconstructed.

## Probe
`probe(p) = level_get_pixel(x + (xsub+vx)/1000, y + (ysub+vy)/1000)` — the pixel the ship would occupy after
this tick's integration (single pixel, no sprite mask) [C]. Out-of-level reads return 0 (air) [C].
`cls = material_class(probe)`. `+0xAC` (`material`, see below) is compared against 3 and 8 here, so it holds the
class seen on an earlier tick [H]; in all traces it stays 0 even on landing ticks [C trace].

## Order [C disasm]
1. `on_own_base = on_any_base = 0`.
2. `cls == 0` (air): if `hp > 0 && material == 3` -> splash `FUN_e83c(x, y, ship_speed)` (leaving water [H]).
   If `pixel == 54` (background fire) and `hp > 0` and `u_108 == 0` -> `damage_acc += 1`.
3. `cls == 3` (water): splash if `material != 3` (entering). Re-probe; `FUN_39a50(pixel)` gives the current:
   0 -> `vy -= 40`; 1 -> `vy += 120`; 2 -> `vy -= 12, vx -= 90`; 3 -> `vy -= 12, vx += 90` [C; mapping to
   colours 48–51 [H]]. Then `v = trunc(0.952 * v)` (double const 0x37D84, x87) and `carried = 0`. Re-probe.
4. `cls == 8` (colours 6, 17–20, 53): if `pixel == 53` (snow) and `material != 8` -> splash with
   `ship_speed/2`. `v = trunc(0.65 * v)` (double const 0x37D8C, x87); if `1 <= vy <= 24` then `vy = 0`; `carried = 0`.
5. `cls` in {1 solid, 4 indestructible, 6 soft, 7 burning} — **hit** [C, trace]:
   - `vx /= 2; vy /= 2` (C truncation toward zero).
   - if `cls != 6 && hp > 0`: `d = ship_speed(vx, vy)` (after halving); if `d > 1`: sound(2, 0, d/6) and
     `damage_acc += d`; if `carried && last_attacker == 100` -> `last_attacker = u_120`.
   - `carried = 0`.
   - Axis test: save `vx`, set `vx = 0`, re-probe; if still not air and not water: restore `vx`, set `vy = 0`,
     re-probe; if still not air and not water: `vx = 0`.
6. `cls` in {2 base, 5 indestructible base}: `v = 0`, `carried = 0`, `owner = FUN_39a00(pixel)`;
   `owner == 5` -> `on_any_base = 1`, `player_on_base(p)`; `owner == 4 || owner == team` ->
   `player_on_base(p)`, `on_own_base = 1` [C disasm; owner encoding [H]].
7. Remaining tail (0x384E9–0x386E0) not yet read.

## Trace evidence for step 5 (ground = colour 136/139, class 1)
| trace frame | v into collide | after halve | ship_speed = damage | hp | axis test result |
|---|---|---|---|---|---|
| mixed 1301 | vy 1033 | 516 | 5 | 120 -> 115 | vx=0 probe is air -> vy kept (516) |
| mixed 1302 | vy 525 | 262 | 2 | 115 -> 113 | still solid -> vy = 0 |
| rotate 128 | vy 1075 | 537 | 5 | 120 -> 115 | still solid -> vy = 0 |
| dive 87 | vy 2075 | 1037 | 10 | 120 -> 110 | still solid -> vy = 0 |
`flash_timer` is set to the damage value on the same tick [C trace] (player_apply_damage [H]).

## Open for RE-2
- Tail after 0x384E9; 0x39A00 / 0x39A50 / 0x3A01C semantics.
- `material` (+0xAC) writer; `u_108` (shield?) and `u_120`.
- `player_apply_damage` 0x36F18 (hp -= damage_acc, flash, death) — needed to diff landing ticks.
- Recon plan: `recon/core/terrain.c` `player_terrain_collide()` behind the existing `ship_step_pre` /
  `ship_step_post` split, then extend `ship_diff` past the first landing (all 5 traces land).
