/* Differential test: replay a DOSBox-X trace of the original through recon/core/ship.c.
 *
 * The ship is simulated free-running from the trace's first record (no resync), using the key
 * flags the original recorded for each tick.  The run stops at the first tick whose collision
 * pixel is not air (player_terrain_collide is RE-2), or at the first field mismatch.
 * Also lists every tick where the velocity entering the drag step is a non-zero multiple of 200:
 * there a 53-bit double product gives a different answer than the x87's 64-bit mantissa.
 *
 * Fixture format (written by run_ship_diff.py from the re/traces JSON files):
 *   W H gravity air_pct drag_f_bits(hex) thrust_bits(hex) turn_rate max_speed p5_rate
 *   144 ints: dir72
 *   N, then N lines: frame x y xsub ysub vx vy angle10 angle_deg p5_acc key_thrust key_left
 *                    key_right on_base flash_timer push_timer push_vx push_vy exhaust_toggle
 *                    carried hp
 * Level file: W*H raw palette indices.
 *
 * usage: ship_diff <fixture.txt> <level.bin> [min_ticks]   exit 0 if >= min_ticks matched */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../core/ship.h"
#include "../core/material.h"
#include "../core/x87.h"

typedef struct {
    long frame, x, y, xsub, ysub, vx, vy, angle10, angle_deg, p5_acc;
    long key_thrust, key_left, key_right, on_base, flash_timer, push_timer, push_vx, push_vy;
    long exhaust_toggle, carried, hp;
} rec_t;

static float bits_to_float(unsigned long b)
{
    float f;
    unsigned int u = (unsigned int)b;
    memcpy(&f, &u, sizeof f);
    return f;
}

static void load_ship(ship_t *s, const rec_t *r, float thrust, long turn, long maxs, long p5)
{
    memset(s, 0, sizeof *s);
    s->x = r->x; s->y = r->y; s->xsub = r->xsub; s->ysub = r->ysub;
    s->vx = r->vx; s->vy = r->vy; s->angle10 = r->angle10; s->angle_deg = r->angle_deg;
    s->p5_acc = r->p5_acc; s->flash_timer = r->flash_timer; s->push_timer = r->push_timer;
    s->push_vx = r->push_vx; s->push_vy = r->push_vy; s->exhaust_toggle = (uint8_t)r->exhaust_toggle;
    s->carried = (uint8_t)r->carried; s->on_base = (uint8_t)r->on_base; s->hp = r->hp;
    s->thrust = thrust; s->turn_rate = turn; s->max_speed = maxs; s->p5_rate = p5;
}

int main(int argc, char **argv)
{
    FILE *f;
    long W, H, grav, air, turn, maxs, p5, n, i, j, matched = 0, rounding_ticks = 0;
    long double_would_fail = 0, min_ticks = argc > 3 ? atol(argv[3]) : 500;
    unsigned long drag_bits, thrust_bits;
    int32_t dir72[72][2];
    rec_t *t;
    unsigned char *lev;
    ship_t s;
    ship_world_t w;
    const char *stop = "end of trace";

    if (argc < 3) { fprintf(stderr, "usage: ship_diff fixture level [min]\n"); return 2; }
    f = fopen(argv[1], "r");
    if (!f) { perror(argv[1]); return 2; }
    if (fscanf(f, "%ld %ld %ld %ld %lx %lx %ld %ld %ld", &W, &H, &grav, &air, &drag_bits,
               &thrust_bits, &turn, &maxs, &p5) != 9) return 2;
    for (i = 0; i < 72; i++) {
        long c, sn;
        if (fscanf(f, "%ld %ld", &c, &sn) != 2) return 2;
        dir72[i][0] = (int32_t)c; dir72[i][1] = (int32_t)sn;
    }
    if (fscanf(f, "%ld", &n) != 1 || n < 2) return 2;
    t = calloc((size_t)n, sizeof *t);
    for (i = 0; i < n; i++) {
        rec_t *r = &t[i];
        if (fscanf(f, "%ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld %ld",
                   &r->frame, &r->x, &r->y, &r->xsub, &r->ysub, &r->vx, &r->vy, &r->angle10,
                   &r->angle_deg, &r->p5_acc, &r->key_thrust, &r->key_left, &r->key_right,
                   &r->on_base, &r->flash_timer, &r->push_timer, &r->push_vx, &r->push_vy,
                   &r->exhaust_toggle, &r->carried, &r->hp) != 21) return 2;
    }
    fclose(f);
    lev = malloc((size_t)(W * H));
    f = fopen(argv[2], "rb");
    if (!f || fread(lev, 1, (size_t)(W * H), f) != (size_t)(W * H)) { perror(argv[2]); return 2; }
    fclose(f);

    w.gravity = grav; w.air_pct = air; w.drag_f = bits_to_float(drag_bits);
    w.level_w = W; w.level_h = H; w.dir72 = (const int32_t (*)[2])dir72;
    load_ship(&s, &t[0], bits_to_float(thrust_bits), turn, maxs, p5);

    for (i = 1; i < n; i++) {
        const rec_t *q = &t[i];
        ship_keys_t k;
        ship_events_t ev;
        int32_t nx, ny, vals[9], want[9];
        static const char *names[9] = {"x", "y", "xsub", "ysub", "vx", "vy", "angle10",
                                       "angle_deg", "p5_acc"};
        int bad = 0;
        if (q->frame != t[i - 1].frame + 1) { stop = "frame gap"; break; }
        k.thrust = (int)q->key_thrust; k.left = (int)q->key_left; k.right = (int)q->key_right;
        ship_step_pre(&s, &k, &w, &ev);
        ship_next_pixel(&s, &nx, &ny);
        if (nx < 0 || ny < 0 || nx >= W || ny >= H || material_class(lev[ny * W + nx]) != MAT_AIR) {
            static char buf[96];
            sprintf(buf, "non-air collision pixel (%ld,%ld)=%d at frame %ld", (long)nx, (long)ny,
                    nx >= 0 && ny >= 0 && nx < W && ny < H ? lev[ny * W + nx] : -1, q->frame);
            stop = buf;
            break;
        }
        ship_step_post(&s, &k, &w, &ev);
        vals[0] = s.x; vals[1] = s.y; vals[2] = s.xsub; vals[3] = s.ysub; vals[4] = s.vx;
        vals[5] = s.vy; vals[6] = s.angle10; vals[7] = s.angle_deg; vals[8] = s.p5_acc;
        want[0] = q->x; want[1] = q->y; want[2] = q->xsub; want[3] = q->ysub; want[4] = q->vx;
        want[5] = q->vy; want[6] = q->angle10; want[7] = q->angle_deg; want[8] = q->p5_acc;
        for (j = 0; j < 9; j++) bad |= vals[j] != want[j];
        if (air == 100) {
            int32_t pv[2], got[2];
            pv[0] = ev.pre_drag_vx; pv[1] = ev.pre_drag_vy; got[0] = q->vx; got[1] = q->vy;
            for (j = 0; j < 2; j++) {
                if (pv[j] != 0 && pv[j] % 200 == 0) {
                    int32_t x87 = x87_mul_trunc(SHIP_DRAG_DEFAULT, pv[j]);
                    int32_t dbl = (int32_t)(SHIP_DRAG_DEFAULT * (double)pv[j]);
                    rounding_ticks++;
                    double_would_fail += dbl != got[j];
                    printf("  v%%200 frame %ld %s: v=%ld  x87=%ld  double53=%ld  trace=%ld\n",
                           q->frame, j ? "vy" : "vx", (long)pv[j], (long)x87, (long)dbl,
                           (long)got[j]);
                }
            }
        }
        if (bad) {
            printf("MISMATCH frame %ld:", q->frame);
            for (j = 0; j < 9; j++)
                if (vals[j] != want[j]) printf(" %s recon=%ld trace=%ld", names[j], (long)vals[j], (long)want[j]);
            printf("\n");
            stop = "mismatch";
            break;
        }
        matched++;
    }
    printf("%ld consecutive ticks match (frames %ld..%ld); stop: %s\n", matched, t[0].frame + 1,
           t[0].frame + matched, stop);
    printf("v%%200 drag ticks: %ld, where a 53-bit double product would have diverged: %ld\n",
           rounding_ticks, double_would_fail);
    free(t);
    free(lev);
    return matched >= min_ticks ? 0 : 1;
}
