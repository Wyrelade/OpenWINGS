/* Differential test: replay a DOSBox-X trace of the original through recon/core (ship.c + terrain.c).
 *
 * The ship is simulated free-running from the trace's first record (no resync), using the key
 * flags the original recorded for each tick.  Per tick: ship_step_pre, player_terrain_collide,
 * player_apply_damage, ship_step_post.  player_apply_forces (weapon/explosion forces) is not
 * reconstructed: the run ends at the first force from another player (see below).
 * Also lists every tick where the velocity entering the drag step is a non-zero multiple of 200:
 * there a 53-bit double product gives a different answer than the x87's 64-bit mantissa.
 *
 * Fixture format (written by run_ship_diff.py from the re/traces JSON files):
 *   W H gravity air_pct drag_f_bits(hex) thrust_bits(hex) turn_rate max_speed p5_rate repair
 *   144 ints: dir72
 *   NF field names (must equal FIELD_NAMES below)
 *   N, then N lines of NF ints + CRC32 of the level window (17x17 level pixels around (x, y)
 *   after the tick, row-major, read by the v4 hook without bounds checks; "-" for older traces)
 * Level file: W*H raw palette indices (mutable copy: landing may erase base pixels).
 *
 * usage: ship_diff <fixture.txt> <level.bin> [min_ticks|all]
 *   exit 0 if >= min_ticks matched ("all" = every tick of the trace), or if every tick matched up to
 *   an external force (another player's weapon/explosion hit), where the checkable part ends */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../core/ship.h"
#include "../core/terrain.h"
#include "../core/material.h"
#include "../core/x87.h"

enum {
    F_FRAME, F_X, F_Y, F_XSUB, F_YSUB, F_VX, F_VY, F_ANGLE10, F_ANGLE_DEG, F_P5_ACC,
    F_HP, F_FLASH_TIMER, F_DAMAGE_ACC, F_ON_OWN_BASE, F_ON_ANY_BASE, F_MATERIAL,
    F_BASE_REPAIR_CTR, F_LAST_ATTACKER, F_ATTACKER_AGE, F_CARRIED, F_FLASH_COLOR,
    F_KEY_THRUST, F_KEY_LEFT, F_KEY_RIGHT, F_PUSH_TIMER, F_PUSH_VX, F_PUSH_VY, F_EXHAUST_TOGGLE,
    F_HP_MAX, F_TEAM, F_SHIELD, F_U_120, F_U_C8, F_FLASH_COLOR_RESTORE, NF
};
static const char *FIELD_NAMES[NF] = {
    "frame", "x", "y", "xsub", "ysub", "vx", "vy", "angle10", "angle_deg", "p5_acc",
    "hp", "flash_timer", "damage_acc", "on_own_base", "on_any_base", "material",
    "base_repair_ctr", "last_attacker", "attacker_age", "carried", "flash_color",
    "key_thrust", "key_left", "key_right", "push_timer", "push_vx", "push_vy", "exhaust_toggle",
    "hp_max", "team", "u_108", "u_120", "u_c8", "flash_color_restore"
};
/* fields compared every tick (F_FRAME+1 .. F_FLASH_COLOR) */
#define NCMP (F_FLASH_COLOR + 1)

#define WIN_R 8
#define WIN (2 * WIN_R + 1)
typedef struct { long v[NF]; int has_win; unsigned long win_crc; } rec_t;

static unsigned long crc32_bytes(const unsigned char *p, int n)
{
    unsigned long c = 0xFFFFFFFFUL;
    int k;
    while (n--) {
        c ^= *p++;
        for (k = 0; k < 8; k++)
            c = (c >> 1) ^ (0xEDB88320UL & (0UL - (c & 1)));
    }
    return c ^ 0xFFFFFFFFUL;
}

/* CRC32 of the 17x17 window of the recon level (with its own edits) exactly as the v4 hook reads
 * it (linear index, no bounds checks).  Returns 0 if part of the window lies outside the pixel
 * array (the hook then read unrelated memory and the tick cannot be checked). */
static int window_crc(const unsigned char *lev, long W, long H, const rec_t *q, unsigned long *crc)
{
    unsigned char buf[WIN * WIN];
    int r, c;
    for (r = 0; r < WIN; r++)
        for (c = 0; c < WIN; c++) {
            long idx = (q->v[F_Y] - WIN_R + r) * W + (q->v[F_X] - WIN_R + c);
            if (idx < 0 || idx >= W * H) return 0;
            buf[r * WIN + c] = lev[idx];
        }
    *crc = crc32_bytes(buf, WIN * WIN);
    return 1;
}

static float bits_to_float(unsigned long b)
{
    float f;
    unsigned int u = (unsigned int)b;
    memcpy(&f, &u, sizeof f);
    return f;
}

static void load_ship(ship_t *s, const rec_t *r, float thrust, long turn, long maxs, long p5)
{
    const long *v = r->v;
    memset(s, 0, sizeof *s);
    s->x = v[F_X]; s->y = v[F_Y]; s->xsub = v[F_XSUB]; s->ysub = v[F_YSUB];
    s->vx = v[F_VX]; s->vy = v[F_VY]; s->angle10 = v[F_ANGLE10]; s->angle_deg = v[F_ANGLE_DEG];
    s->p5_acc = v[F_P5_ACC]; s->flash_timer = v[F_FLASH_TIMER];
    s->flash_color = (uint8_t)v[F_FLASH_COLOR]; s->flash_color_restore = (uint8_t)v[F_FLASH_COLOR_RESTORE];
    s->push_timer = v[F_PUSH_TIMER]; s->push_vx = v[F_PUSH_VX]; s->push_vy = v[F_PUSH_VY];
    s->exhaust_toggle = (uint8_t)v[F_EXHAUST_TOGGLE]; s->carried = (uint8_t)v[F_CARRIED];
    s->on_own_base = (uint8_t)v[F_ON_OWN_BASE]; s->on_any_base = (uint8_t)v[F_ON_ANY_BASE];
    s->hp = v[F_HP]; s->hp_max = v[F_HP_MAX]; s->team = v[F_TEAM]; s->material = v[F_MATERIAL];
    s->base_repair_ctr = v[F_BASE_REPAIR_CTR]; s->damage_acc = v[F_DAMAGE_ACC];
    s->last_attacker = v[F_LAST_ATTACKER]; s->attacker_age = v[F_ATTACKER_AGE];
    s->shield = v[F_SHIELD]; s->u_120 = v[F_U_120]; s->u_c8 = v[F_U_C8];
    s->thrust = thrust; s->turn_rate = turn; s->max_speed = maxs; s->p5_rate = p5;
}

static void save_ship(const ship_t *s, long *v)
{
    v[F_X] = s->x; v[F_Y] = s->y; v[F_XSUB] = s->xsub; v[F_YSUB] = s->ysub;
    v[F_VX] = s->vx; v[F_VY] = s->vy; v[F_ANGLE10] = s->angle10; v[F_ANGLE_DEG] = s->angle_deg;
    v[F_P5_ACC] = s->p5_acc; v[F_HP] = s->hp; v[F_FLASH_TIMER] = s->flash_timer;
    v[F_DAMAGE_ACC] = s->damage_acc; v[F_ON_OWN_BASE] = s->on_own_base;
    v[F_ON_ANY_BASE] = s->on_any_base; v[F_MATERIAL] = s->material;
    v[F_BASE_REPAIR_CTR] = s->base_repair_ctr; v[F_LAST_ATTACKER] = s->last_attacker;
    v[F_ATTACKER_AGE] = s->attacker_age; v[F_CARRIED] = s->carried; v[F_FLASH_COLOR] = s->flash_color;
}

int main(int argc, char **argv)
{
    FILE *f;
    long W, H, grav, air, turn, maxs, p5, repair, n, i, j, matched = 0, rounding_ticks = 0;
    long double_would_fail = 0, min_ticks, first_contact = -1, contacts = 0;
    long splashes = 0, hits = 0, base_ticks = 0, water_ticks = 0, cleared = 0, fire = 0, win_ticks = 0;
    long tdrag = 0, tdrag_x87 = 0;
    unsigned long drag_bits, thrust_bits;
    int32_t dir72[72][2];
    rec_t *t;
    unsigned char *lev;
    ship_t s;
    ship_world_t w;
    level_t L;
    const char *stop = "end of trace";
    int external = 0;
    char name[64];

    if (argc < 3) { fprintf(stderr, "usage: ship_diff fixture level [min|all]\n"); return 2; }
    f = fopen(argv[1], "r");
    if (!f) { perror(argv[1]); return 2; }
    if (fscanf(f, "%ld %ld %ld %ld %lx %lx %ld %ld %ld %ld", &W, &H, &grav, &air, &drag_bits,
               &thrust_bits, &turn, &maxs, &p5, &repair) != 10) return 2;
    for (i = 0; i < 72; i++) {
        long c, sn;
        if (fscanf(f, "%ld %ld", &c, &sn) != 2) return 2;
        dir72[i][0] = (int32_t)c; dir72[i][1] = (int32_t)sn;
    }
    for (j = 0; j < NF; j++) {
        if (fscanf(f, "%63s", name) != 1 || strcmp(name, FIELD_NAMES[j]) != 0) {
            fprintf(stderr, "fixture field %ld: want %s\n", j, FIELD_NAMES[j]);
            return 2;
        }
    }
    if (fscanf(f, "%ld", &n) != 1 || n < 2) return 2;
    t = calloc((size_t)n, sizeof *t);
    for (i = 0; i < n; i++) {
        char tok[32];
        for (j = 0; j < NF; j++)
            if (fscanf(f, "%ld", &t[i].v[j]) != 1) return 2;
        if (fscanf(f, "%31s", tok) != 1) return 2;
        t[i].has_win = strcmp(tok, "-") != 0;
        t[i].win_crc = t[i].has_win ? strtoul(tok, NULL, 10) : 0;
    }
    fclose(f);
    min_ticks = argc > 3 ? (strcmp(argv[3], "all") == 0 ? n - 1 : atol(argv[3])) : n - 1;
    lev = malloc((size_t)(W * H));
    f = fopen(argv[2], "rb");
    if (!f || fread(lev, 1, (size_t)(W * H), f) != (size_t)(W * H)) { perror(argv[2]); return 2; }
    fclose(f);

    w.gravity = grav; w.air_pct = air; w.drag_f = bits_to_float(drag_bits);
    w.level_w = W; w.level_h = H; w.dir72 = (const int32_t (*)[2])dir72;
    L.pix = lev; L.pitch = W; L.w = W; L.h = H;
    load_ship(&s, &t[0], bits_to_float(thrust_bits), turn, maxs, p5);

    for (i = 1; i < n; i++) {
        const rec_t *q = &t[i];
        ship_keys_t k;
        ship_events_t ev;
        terrain_events_t tev;
        int32_t nx, ny;
        long vals[NF];
        int bad = 0;
        if (q->v[F_FRAME] != t[i - 1].v[F_FRAME] + 1) { stop = "frame gap"; break; }
        k.thrust = (int)q->v[F_KEY_THRUST]; k.left = (int)q->v[F_KEY_LEFT]; k.right = (int)q->v[F_KEY_RIGHT];
        memset(&tev, 0, sizeof tev);
        ship_step_pre(&s, &k, &w, &ev);
        ship_next_pixel(&s, &nx, &ny);
        if (material_class(level_get_pixel(&L, nx, ny)) != MAT_AIR) {
            contacts++;
            if (first_contact < 0) first_contact = q->v[F_FRAME];
        }
        player_terrain_collide(&s, &L, (int32_t)repair, &tev);
        player_apply_damage(&s, 0, -1, &tev);
        ship_step_post(&s, &k, &w, &ev);
        if (tev.drag) {
            tdrag++;
            tdrag_x87 += x87_mul_trunc(tev.drag_c, tev.drag_vx) != (int32_t)(tev.drag_c * tev.drag_vx)
                      || x87_mul_trunc(tev.drag_c, tev.drag_vy) != (int32_t)(tev.drag_c * tev.drag_vy);
        }
        splashes += tev.splash; hits += tev.hit_sound; cleared += tev.pixels_cleared; fire += tev.fire;
        base_ticks += s.on_own_base || s.on_any_base;
        water_ticks += s.material == MAT_WATER;
        if (tev.died) { stop = "ship died (player_die not reconstructed)"; break; }
        save_ship(&s, vals);
        /* player_apply_forces (0x36AAE) sets last_attacker = source, attacker_age = 0 for a force
         * from another player; player_apply_damage then makes the age 1.  Forces come from weapons
         * and explosions, which are not reconstructed: the checkable part of the trace ends here. */
        if (q->v[F_ATTACKER_AGE] == 1 && q->v[F_LAST_ATTACKER] != 100 && vals[F_ATTACKER_AGE] != 1) {
            static char buf[128];
            sprintf(buf, "external force from player %ld at frame %ld (player_apply_forces, weapons: not "
                    "reconstructed)", q->v[F_LAST_ATTACKER], q->v[F_FRAME]);
            stop = buf;
            external = 1;
            break;
        }
        for (j = 1; j < NCMP; j++) bad |= vals[j] != q->v[j];
        if (air == 100) {
            int32_t pv[2];
            pv[0] = ev.pre_drag_vx; pv[1] = ev.pre_drag_vy;
            for (j = 0; j < 2; j++) {
                if (pv[j] != 0 && pv[j] % 200 == 0) {
                    int32_t x87 = x87_mul_trunc(SHIP_DRAG_DEFAULT, pv[j]);
                    int32_t dbl = (int32_t)(SHIP_DRAG_DEFAULT * (double)pv[j]);
                    long got = q->v[j ? F_VY : F_VX];
                    rounding_ticks++;
                    /* only meaningful when nothing after the drag touched v this tick */
                    double_would_fail += dbl != got && x87 == got;
                }
            }
        }
        if (!bad && q->has_win) {
            unsigned long crc;
            if (window_crc(lev, W, H, q, &crc)) {
                win_ticks++;
                if (crc != q->win_crc) {
                    printf("LEVEL CHANGED frame %ld: level pixels around (%ld,%ld) differ from the recon level\n",
                           q->v[F_FRAME], q->v[F_X], q->v[F_Y]);
                    stop = "level pixels changed (not a recon edit)";
                    break;
                }
            }
        }
        if (bad) {
            printf("MISMATCH frame %ld:", q->v[F_FRAME]);
            for (j = 1; j < NCMP; j++)
                if (vals[j] != q->v[j]) printf(" %s recon=%ld trace=%ld", FIELD_NAMES[j], vals[j], q->v[j]);
            printf("\n");
            stop = "mismatch";
            break;
        }
        matched++;
    }
    printf("%ld/%ld ticks match (frames %ld..%ld); stop: %s\n", matched, n - 1, t[0].v[F_FRAME] + 1,
           t[0].v[F_FRAME] + matched, stop);
    printf("  first terrain contact frame %ld, contact ticks %ld, damaging hits %ld, splashes %ld, "
           "fire %ld, base ticks %ld, water ticks %ld, base pixels erased %ld, level window checked on "
           "%ld ticks\n", first_contact, contacts, hits, splashes, fire, base_ticks, water_ticks, cleared,
           win_ticks);
    printf("  water/snow drag ticks: %ld, where a 53-bit double product differs from x87: %ld\n",
           tdrag, tdrag_x87);
    printf("  v%%200 drag ticks: %ld, where a 53-bit double product would have diverged: %ld\n",
           rounding_ticks, double_would_fail);
    free(t);
    free(lev);
    /* a trace that ends in an external force passes if every tick before it matched */
    return matched >= min_ticks || (external && matched == i - 1) ? 0 : 1;
}
