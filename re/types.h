/* Recovered Wings 1.40 data structures.  Tags: [C] confirmed (disasm + trace), [H] hypothesis, [?] unknown.
 * All offsets are byte offsets; all ints are 32-bit little endian (gcc 2.7.2.1 / DJGPP, i386).
 * Python mirror for trace decoding: tools/player_layout.py (keep in sync). */
#ifndef WINGS_TYPES_H
#define WINGS_TYPES_H
#include <stdint.h>

/* 12-byte RLE sprite header as loaded by FUN_0001bbf8 (layout inside [?]). */
typedef struct { uint8_t raw[12]; } sprite_t;

/* ship_type_t (900 = 0x384 bytes), array pointer at g_ship_types 0x9B434.
 * Loaded by ship_type_t::load() 0x8F04 from SHIPS/<name>.SHP.  [C] layout from loader. */
typedef struct {
    int32_t  name_len;        /* +0x00 [C] */
    char    *name;            /* +0x04 [H] new char[name_len+1] */
    int32_t  p0_strength;     /* +0x08 [C] HP scale %: hp_max = (opt_strength*120/100)*p0/100 */
    float    p1_mass;         /* +0x0C [C] divides force impulses (player_apply_forces) */
    int32_t  p2_turn;         /* +0x10 [C] turn rate, 1/10 degree per tick (default 50 = 5 deg) */
    float    p3_thrust;       /* +0x14 [C] thrust factor: dv = trunc(p3 * dir72[k]) milli-px/tick */
    int32_t  p4_max_speed;    /* +0x18 [C] |vx|,|vy| box above which thrust may not raise speed */
    int32_t  p5_rate;         /* +0x1C [C] added to player.p5_acc each tick, FUN_00026440 per 100 [H: exhaust/smoke] */
    int32_t  p6;              /* +0x20 [C] read directly from ship type (FUN_0000dac0 on force kind 1) [?] */
    sprite_t frames[72];      /* +0x24 [C] frame = angle_deg/5 -> 72 rotations of 5 deg */
} ship_type_t;

/* player_t (0x128 bytes), array g_players[8] at 0x9B444.  Ship update is inlined in match_main. */
typedef struct {
    int32_t x, y;             /* +0x00 [C] pixel position */
    int32_t xsub, ysub;       /* +0x08 [C] sub-pixel 1/1000 px, C remainder (can be negative) */
    int32_t vx, vy;           /* +0x10 [C] velocity, 1/1000 px per tick */
    int32_t ship_type;        /* +0x18 [C] index into g_ship_types */
    int32_t u_1c;             /* +0x1C [?] 0 => ship stats shown in menu */
    int32_t team;             /* +0x20 [C] 0..3 */
    int32_t angle_deg;        /* +0x24 [C] = angle10/10; 0 = nose up, increases clockwise */
    int32_t angle10;          /* +0x28 [C] 0..3599 */
    int32_t hp_max;           /* +0x2C [C] */
    int32_t hp;               /* +0x30 [C] */
    int32_t u_34;             /* +0x34 [?] set 1 at spawn */
    int32_t weapon2;          /* +0x38 [C] secondary weapon 1..34, -1 none */
    int32_t weapon2_start;    /* +0x3C [H] */
    uint8_t weapon_avail[0x38]; /* +0x40 [C] weapon_avail[w] != 0 -> selectable (player_cycle_weapon) */
    int32_t fire_ready;       /* +0x78 [H] */
    int32_t turn_released;    /* +0x7C [C] both turn keys up (edge detection for weapon cycling on base) */
    uint8_t flash_color;      /* +0x80 [C] 0x1F while hit-flash */
    uint8_t flash_color_restore; /* +0x81 [C] */
    uint8_t _pad82[2];
    int32_t flash_timer;      /* +0x84 [C] */
    uint8_t keybind[5];       /* +0x88 [C] scancodes: thrust, fire2, left, right, fire1 (KEYS.DAT order) */
    uint8_t _pad8d[3];
    int32_t key_thrust;       /* +0x90 [C] */
    int32_t key_fire2;        /* +0x94 [C] (default Down) */
    int32_t key_left;         /* +0x98 [C] angle10 -= turn_rate */
    int32_t key_right;        /* +0x9C [C] angle10 += turn_rate */
    int32_t key_fire1;        /* +0xA0 [C] (default RShift) */
    int32_t base_repair_ctr;  /* +0xA4 [C] every 10 ticks on own base: hp += g_repair (0x9EAE8) */
    uint8_t on_own_base;      /* +0xA8 [C] */
    uint8_t on_any_base;      /* +0xA9 [C] */
    uint8_t _padaa[2];
    int32_t material;         /* +0xAC [?] written by player_terrain_collide; stays 0 on landing ticks in traces */
    uint8_t exhaust_toggle;   /* +0xB0 [C] ^=1 each tick; exhaust spawned on toggle==1 while thrusting */
    uint8_t _padb1[0x13];
    int8_t  weapon_cycle_dir; /* +0xC4 [C] */
    uint8_t autofire_ctr;     /* +0xC5 [C] */
    uint8_t carried;          /* +0xC6 [H] grabbed/netted flag (cleared by collisions) */
    uint8_t _padc7;
    int32_t u_c8, u_cc, u_d0; /* +0xC8.. [?] mission counters? */
    int32_t push_timer;       /* +0xD4 [C] >0: gravity replaced by push_v (force kind 3) */
    int32_t push_vx, push_vy; /* +0xD8 [C] decays toward (0, 12) */
    int32_t u_e0, u_e4;       /* [?] */
    int32_t strength_pct;     /* +0xE8 [C] copy of p0 */
    float   mass;             /* +0xEC [C] copy of p1 */
    int32_t turn_rate;        /* +0xF0 [C] copy of p2 */
    float   thrust;           /* +0xF4 [C] copy of p3 */
    int32_t max_speed;        /* +0xF8 [C] copy of p4 */
    int32_t p5_rate;          /* +0xFC [C] copy of p5 */
    int32_t p5_acc;           /* +0x100 [C] */
    int32_t score;            /* +0x104 [C] deathmatch kills */
    int32_t u_108;            /* +0x108 [?] reduces damage by 15 when 1 (shield?) */
    int32_t confuse_timer;    /* +0x10C [C] */
    int32_t confuse_kind;     /* +0x110 [C] 0 swap L/R, 1 swap L/thrust, 2 swap thrust/R, 3 random thrust drop, 4 force fire2 */
    int32_t damage_acc;       /* +0x114 [C] applied+cleared in player_apply_damage */
    int32_t last_attacker;    /* +0x118 [C] 100 = none */
    int32_t attacker_age;     /* +0x11C [C] resets attacker after 40 ticks */
    int32_t u_120, u_124;     /* [?] */
} player_t;

#endif
