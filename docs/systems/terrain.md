# Terrain collision and landing (Wings 1.40)

Source: `player_terrain_collide` 0x37D94..0x386D2 (called once per player per tick from the ship block
after `player_apply_forces` (only when `hp > 0`), before `player_apply_damage` 0x36F18, then the bounds clamp).
Tags: [C] disasm (+ trace where noted), [H] hypothesis, [?] unknown.
Reconstruction: `recon/core/terrain.c` (`player_terrain_collide`, `player_apply_damage`, `player_on_base`).

## Helpers [C disasm]
| VA | name | behaviour |
|---|---|---|
| 0x39FD8 | `level_get_pixel(x, y)` | `x<0 \|\| y<0 \|\| x>=W \|\| y>=H` -> 0 (air), else `pix[y*pitch + x]` |
| 0x3A01C | `level_set_pixel(x, y, c)` | same bounds test, writes the pixel; if byte 0x9AB9B == 1 also writes `mask[y*W+x] = c ? 0xFF : 0` (mask at 0x9B410 [?]) |
| 0x3987C | `material_class(c)` | see `recon/core/material.c` |
| 0x39A00 | `base_owner(c)` | 40–41 -> 0, 42–43 -> 1, 44–45 -> 2, 46–47 -> 3 (team), 38–39 -> 5, else 4 (neutral base 32–37) |
| 0x39A50 | `water_current(c)` | 49 -> 1 (down), 50 -> 2 (left), 51 -> 3 (right), else 0 (still water, 48) |
| 0x9388 | `player_on_base(p)` | see below |
| 0xE83C | `splash(x, y, speed)` | sound (sample +0x168, prio 1/2/3 by `speed*64/10`), then `speed/4` particles in the 40-slot pool 0x59AA0 (count 0x59F00); **each particle consumes 2 × `random_n(36)`**, none once the pool is full |
| 0x1FC80 | `sound_play(sample, prio, 0, vol)` | channel allocator, no RNG |

`probe` = `level_get_pixel(x + (xsub+vx)/1000, y + (ysub+vy)/1000)`: the single pixel the ship would occupy after
this tick's integration, using the **current** velocity (re-evaluated after each velocity change). No sprite mask.

## player_terrain_collide order [C disasm]
`c0 = probe; cls = material_class(c0)` (both kept in locals; `cls` is only re-read after the water branch).
1. `on_own_base = on_any_base = 0`.
2. `cls == 0` (air): if `hp > 0 && material == 3` -> `splash(x, y, ship_speed)` (leaving water).
   If `c0 == 54` (background fire) and `hp > 0` and `shield (u_108) == 0` -> `damage_acc += 1`.
3. `cls == 3` (water): if `material != 3` -> `splash(x, y, ship_speed)` (entering). `cur = water_current(probe)`:
   0 -> `vy -= 40`; 1 -> `vy += 120`; 2 -> `vy -= 12, vx -= 90`; 3 -> `vy -= 12, vx += 90`.
   Then `vx = trunc(0.952*vx); vy = trunc(0.952*vy)` (double 0x37D84, x87 fimul + fistp), `carried = 0`,
   and **`cls = material_class(probe)` again** with the new velocity; the steps below use this new class
   (the ship can leave the water sideways into ground or a base on the same tick).
4. `cls == 8` (colours 6, 17–20, 53): if `c0 == 53` (snow) and `material != 8` -> `splash(x, y, ship_speed/2)`.
   `vx = trunc(0.65*vx); vy = trunc(0.65*vy)` (double 0x37D8C); if `1 <= vy <= 24` then `vy = 0`; `carried = 0`.
5. `cls` in {1 solid, 4 indestructible, 6 soft, 7 burning} — **hit** [C, trace]:
   - `vx /= 2; vy /= 2` (C truncation toward zero).
   - if `cls != 6 && hp > 0`: `d = ship_speed(vx, vy)` (after halving); if `d > 1`: `sound_play(+0x798, 2, 0,
     (int8)(d*64/6))`; **`damage_acc += d` (also for d = 0, 1)**; if `carried == 1 && last_attacker == 100` ->
     `last_attacker = u_120`.  Soft ground (class 6) never damages.
   - `carried = 0`.
   - Axis test: `sv = vx; vx = 0`; if `probe` is air or water -> done (vx stays 0, vy kept).
     Else `vx = sv; vy = 0`; if `probe` is air or water -> done. Else `vx = 0` (both 0).
6. `cls` in {2 base, 5 indestructible base} (landing): `owner = base_owner(probe)`; `vx = vy = 0; carried = 0`.
   `owner == 5` -> `on_any_base = 1; player_on_base(p)`. Then (independently) `owner == 4 || owner == team` ->
   `player_on_base(p); on_own_base = 1`.
7. `material = material_class(probe)` — **the only writer of +0xAC** [C, xref]: class of the next pixel after all
   velocity changes, i.e. the medium the ship is moving into (usually 0 after a bounce, 3 while in water).
8. Resting check below the current pixel: `cb = level_get_pixel(x, y+1)`; if `material_class(cb) == 2`
   (destructible base only): `player_on_base(p)`; `owner = base_owner(cb)`; `owner == 5` -> `on_any_base = 1`
   (unreachable for class 2); `owner == 4 || owner == team` -> `on_own_base = 1`.
   Then if `material_class(level_get_pixel(x, y-1)) == 2` -> `level_set_pixel(x, y-1, 0)` (a base pixel above
   the ship is erased).  Step 8 runs only when the pixel below is class 2.
9. Repair: if `on_own_base == 1`: `old = base_repair_ctr++`; if `old == 9`: `base_repair_ctr = 0` and if
   `0 < hp < hp_max`: `hp = min(hp + g_repair, hp_max)`.  `g_repair` 0x9EAE8 = `max(1, opt_ship_strength_pct/100)`
   (set at match start 0x346C2; default 1) -> +1 hp every 10 ticks on an own base.

`on_any_base` is really "on an indestructible (38–39) base": it blocks rotation (turn keys cycle weapons) but
gives no repair; destructible neutral (32–37) and own-team bases set `on_own_base`. [C disasm]

## player_on_base 0x9388 [C disasm]
```
if (material == 3) {                 /* in water (class seen last tick) */
    if (angle_deg != 180) xsub = ysub = vx = vy = 0;
    angle_deg = 180;
} else
    angle_deg = push_vy < 0 ? 180 : 0;   /* push (force kind 3) upward -> upside down [H: Gravitor] */
angle10 = angle_deg * 10;
```
Landing snaps the ship upright (nose up) [C].

## player_apply_damage 0x36F18 [C disasm]
```
d = damage_acc; damage_acc = 0;
att = last_attacker;
if (att == 100) {
    att = attacker_lookup(self);            /* 0x386D4: grab/net pools 0x994A0 (40 B) / 0x99638 (92 B), -1 = none */
    if (att == -1 && (push_timer > 0 || carried == 1)) att = u_120;
    if (att == -1 || att == self) att = 100;
}                                           /* no self check when last_attacker != 100 */
if (attacker_age <= 999) attacker_age++;
if (attacker_age > 40) last_attacker = 100;
if (shield == 1) d -= 15;                   /* u_108 */
if (d > 0) {
    flash_color = 0x1F;
    if (flash_timer < d) flash_timer = d;
    if (flash_timer <= 1) flash_timer = 2;
    if (carried == 1) u_c8 -= d >> 2;
    hp -= d;
    if (hp <= 0) {
        player_die(x, y, self);             /* 0x37A58: explosion, respawn; uses random_n */
        if (deathmatch 0x9AC10 == 1) {
            kills_total 0x9EB38++;
            if (att != 100 && players[att].team != team) players[att].score++;
            else score--;
        }
    }
}
```
`att` is only a local (kill credit); `last_attacker` is written elsewhere (weapons).

## RNG consumers on this path
- `splash` 0xE83C: 2 × `random_n(36)` per particle, `speed/4` particles, only while the particle pool has room.
- `player_die` 0x37A58: `random_n` at 0x37C2D, 0x37C41, 0x37C9E (respawn search [H]).
- The collide solid/base/water logic itself and `player_apply_damage` (without death) consume no RNG.

## Trace evidence (ground = colour 136/139, class 1)
| trace frame | v into collide | after halve | ship_speed = damage | hp | axis test result |
|---|---|---|---|---|---|
| mixed 1301 | vy 1033 | 516 | 5 | 120 -> 115 | vx=0 probe is air -> vy kept (516) |
| mixed 1302 | vy 525 | 262 | 2 | 115 -> 113 | still solid -> vy = 0 |
| rotate 128 | vy 1075 | 537 | 5 | 120 -> 115 | still solid -> vy = 0 |
| dive 87 | vy 2075 | 1037 | 10 | 120 -> 110 | still solid -> vy = 0 |
`flash_timer` is set to the damage value on the same tick [C trace]. Resting on the ground: gravity 12 -> drag 11 ->
next pixel solid -> halve 5 -> ship_speed 0 -> damage 0, vy = 0 (rotate frames 131..).
