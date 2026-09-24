/* Offline flight simulator on recon/core (ship.c + terrain.c), used to design capture scripts
 * (tools/make_scripts.py via tools/recon_sim.py).  Not a test by itself.
 *
 * stdin:  W H gravity air_pct drag_f_bits(hex) thrust_bits(hex) turn_rate max_speed p5_rate
 *         hp_max team x y n
 *         144 ints dir72
 *         n key bytes (bit0 thrust, bit2 left, bit3 right)
 * argv[1]: level file (W*H raw palette indices)
 * stdout: one line per tick: x y xsub ysub vx vy angle10 hp on_own_base on_any_base material */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../core/ship.h"
#include "../core/terrain.h"

int main(int argc, char **argv)
{
    long W, H, grav, air, turn, maxs, p5, hpmax, team, x, y, n, i, b;
    unsigned long drag_bits, thrust_bits;
    unsigned int u;
    int32_t dir72[72][2];
    unsigned char *lev;
    FILE *f;
    ship_t s;
    ship_world_t w;
    level_t L;

    if (argc < 2) return 2;
    if (scanf("%ld %ld %ld %ld %lx %lx %ld %ld %ld %ld %ld %ld %ld %ld", &W, &H, &grav, &air,
              &drag_bits, &thrust_bits, &turn, &maxs, &p5, &hpmax, &team, &x, &y, &n) != 14) return 2;
    for (i = 0; i < 72; i++) {
        long c, sn;
        if (scanf("%ld %ld", &c, &sn) != 2) return 2;
        dir72[i][0] = (int32_t)c; dir72[i][1] = (int32_t)sn;
    }
    lev = malloc((size_t)(W * H));
    f = fopen(argv[1], "rb");
    if (!f || fread(lev, 1, (size_t)(W * H), f) != (size_t)(W * H)) return 2;
    fclose(f);
    memset(&s, 0, sizeof s);
    s.x = x; s.y = y; s.hp = s.hp_max = hpmax; s.team = team; s.last_attacker = 100;
    s.u_120 = 100; s.p5_rate = p5; s.turn_rate = turn; s.max_speed = maxs;
    u = (unsigned int)thrust_bits; memcpy(&s.thrust, &u, sizeof u);
    u = (unsigned int)drag_bits; memcpy(&w.drag_f, &u, sizeof u);
    w.gravity = grav; w.air_pct = air; w.level_w = W; w.level_h = H;
    w.dir72 = (const int32_t (*)[2])dir72;
    L.pix = lev; L.pitch = W; L.w = W; L.h = H;
    for (i = 0; i < n; i++) {
        ship_keys_t k;
        ship_events_t ev;
        terrain_events_t tev;
        if (scanf("%ld", &b) != 1) return 2;
        k.thrust = (int)(b & 1); k.left = (int)((b >> 2) & 1); k.right = (int)((b >> 3) & 1);
        memset(&tev, 0, sizeof tev);
        ship_step_pre(&s, &k, &w, &ev);
        player_terrain_collide(&s, &L, 1, &tev);
        player_apply_damage(&s, 0, -1, &tev);
        ship_step_post(&s, &k, &w, &ev);
        printf("%ld %ld %ld %ld %ld %ld %ld %ld %d %d %ld\n", (long)s.x, (long)s.y, (long)s.xsub,
               (long)s.ysub, (long)s.vx, (long)s.vy, (long)s.angle10, (long)s.hp, s.on_own_base,
               s.on_any_base, (long)s.material);
    }
    free(lev);
    return 0;
}
