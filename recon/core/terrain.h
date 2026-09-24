/* Wings 1.40 terrain collision, landing and damage.  Spec: docs/systems/terrain.md.
 *
 * Tick order in match_main (0x35CDF): player_apply_forces (hp > 0 only, not reconstructed),
 * player_terrain_collide 0x37D94, player_apply_damage 0x36F18, then the bounds clamp in
 * ship_step_post().  Effects (splash particles, sounds, death) are reported as event counters. */
#ifndef RECON_TERRAIN_H
#define RECON_TERRAIN_H
#include <stdint.h>
#include "ship.h"

typedef struct {
    uint8_t *pix;           /* 0x99754: level pixels (palette indices) */
    int32_t pitch;          /* 0x9974C */
    int32_t w, h;           /* 0x9AE00 / 0x9AE04 */
} level_t;

typedef struct {
    int splash;             /* splash() 0xE83C calls (each may consume 2 * random_n(36) per particle) */
    int32_t splash_speed;   /* speed argument of the last splash */
    int hit_sound;          /* sound_play(+0x798, 2, 0, vol) on a damaging hit */
    int32_t hit_volume;     /* (int8)(d * 64 / 6) of the last hit sound */
    int fire;               /* background fire (colour 54) damage ticks */
    int on_base_calls;      /* player_on_base() calls */
    int pixels_cleared;     /* base pixels above a resting ship erased by level_set_pixel */
    int died;               /* hp dropped to <= 0: player_die() 0x37A58 would run (not reconstructed) */
    int32_t kill_credit;    /* attacker index credited on death (100 = none / suicide) */
    int drag;               /* water (0.952) or class-8 (0.65) drag applied this tick (diagnostics) */
    double drag_c;          /* its constant */
    int32_t drag_vx, drag_vy; /* velocity entering that drag */
} terrain_events_t;

uint8_t level_get_pixel(const level_t *l, int32_t x, int32_t y);          /* 0x39FD8 */
void    level_set_pixel(level_t *l, int32_t x, int32_t y, uint8_t c);     /* 0x3A01C (mask 0x9B410 not kept) */
int     base_owner(uint8_t c);      /* 0x39A00: team 0..3, 4 neutral, 5 indestructible */
int     water_current(uint8_t c);   /* 0x39A50: 0 still, 1 down, 2 left, 3 right */

void player_on_base(ship_t *s);     /* 0x9388: snap angle upright (or upside down) */

/* repair = g_repair 0x9EAE8 = max(1, opt_ship_strength_pct / 100) */
void player_terrain_collide(ship_t *s, level_t *l, int32_t repair, terrain_events_t *ev);

/* self = player index; lookup = result of attacker_lookup 0x386D4 (grab/net pools; -1 = none) */
void player_apply_damage(ship_t *s, int32_t self, int32_t lookup, terrain_events_t *ev);

extern const double TERRAIN_WATER_DRAG;   /* double 0.952 at 0x37D84 */
extern const double TERRAIN_SPECIAL_DRAG; /* double 0.65 at 0x37D8C */

#endif
