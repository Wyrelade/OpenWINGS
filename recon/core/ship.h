/* Wings 1.40 ship movement: the per-player block inlined in match_main (0x3531C-0x35F00).
 * Spec: docs/systems/physics.md.  Layout source: re/types.h (player_t).
 *
 * One tick = ship_step_pre() + [player_apply_forces: not reconstructed] + player_terrain_collide()
 * + player_apply_damage() (recon/core/terrain.c) + ship_step_post().  ship_step() is the air-only
 * subset (pre + post). */
#ifndef RECON_SHIP_H
#define RECON_SHIP_H
#include <stdint.h>

typedef struct {
    int32_t x, y;           /* player_t +0x00: pixel position */
    int32_t xsub, ysub;     /* +0x08: 1/1000 px, C remainder (may be negative) */
    int32_t vx, vy;         /* +0x10: 1/1000 px per tick, +y down */
    int32_t angle_deg;      /* +0x24: angle10 / 10, 0 = nose up, clockwise */
    int32_t angle10;        /* +0x28: 0..3599 */
    int32_t flash_timer;    /* +0x84 */
    uint8_t flash_color, flash_color_restore; /* +0x80 / +0x81 */
    uint8_t exhaust_toggle; /* +0xB0 */
    uint8_t carried;        /* +0xC6 */
    uint8_t on_own_base;    /* +0xA8: own-team or neutral destructible base (repair) */
    uint8_t on_any_base;    /* +0xA9: indestructible base 38..39 (no repair) */
    int32_t push_timer;     /* +0xD4 */
    int32_t push_vx, push_vy; /* +0xD8 / +0xDC */
    float   thrust;         /* +0xF4: ship p3 */
    int32_t turn_rate;      /* +0xF0: ship p2, 1/10 degree per tick */
    int32_t max_speed;      /* +0xF8: ship p4 */
    int32_t p5_rate;        /* +0xFC: ship p5 */
    int32_t p5_acc;         /* +0x100 */
    int32_t hp;             /* +0x30 */
    int32_t hp_max;         /* +0x2C */
    int32_t team;           /* +0x20 */
    int32_t material;       /* +0xAC: material class of the next pixel, set by player_terrain_collide */
    int32_t base_repair_ctr; /* +0xA4 */
    int32_t damage_acc;     /* +0x114: summed during the tick, applied by player_apply_damage */
    int32_t last_attacker;  /* +0x118: 100 = none */
    int32_t attacker_age;   /* +0x11C */
    int32_t shield;         /* +0x108 (u_108): 1 -> damage - 15, no fire damage */
    int32_t u_120;          /* +0x120: attacker credited when carried/pushed [?] */
    int32_t u_c8;           /* +0xC8: reduced by damage/4 while carried [?] */
} ship_t;

typedef struct {
    int thrust, left, right; /* player_t +0x90 / +0x98 / +0x9C after player_apply_confusion */
} ship_keys_t;

typedef struct {
    int32_t gravity;        /* g_gravity 0x9AB74 */
    float   drag_f;         /* g_air_drag_f 0x9AB78 (used when air_pct is not 0 or 100) */
    int32_t air_pct;        /* opt_air_res_pct 0x9AB80 */
    int32_t level_w, level_h; /* 0x9AE00 / 0x9AE04 */
    const int32_t (*dir72)[2]; /* g_dir72 0x9BD8C: {cos, sin} * 1000 per 5 degrees */
} ship_world_t;

typedef struct {
    int p5_events;          /* times FUN_00026440 would be called this tick */
    int exhaust;            /* 1 if FUN_0000dd9c (exhaust particle) would be called */
    int32_t pre_drag_vx, pre_drag_vy; /* velocity entering step 8 (diagnostics) */
} ship_events_t;

extern const double SHIP_DRAG_DEFAULT;  /* double 0.995 at 0x34B1C */

int32_t ship_speed(int32_t vx, int32_t vy);   /* FUN_0000903c, 1/100 px per tick */

void ship_step_pre(ship_t *s, const ship_keys_t *k, const ship_world_t *w, ship_events_t *ev);
void ship_step_post(ship_t *s, const ship_keys_t *k, const ship_world_t *w, ship_events_t *ev);
void ship_step(ship_t *s, const ship_keys_t *k, const ship_world_t *w, ship_events_t *ev);

/* pixel that player_terrain_collide tests: position after this tick's integration */
void ship_next_pixel(const ship_t *s, int32_t *nx, int32_t *ny);

#endif
