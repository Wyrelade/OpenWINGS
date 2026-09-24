/* Wings 1.40 ship movement.  Step numbers refer to docs/systems/physics.md.
 * Float handling: every multiply that feeds a truncation goes through x87.c unless the product
 * is exact in a double (then the C cast truncates exactly like fistp with RC = toward zero). */
#include "ship.h"
#include "x87.h"

const double SHIP_DRAG_DEFAULT = 0.995;

int32_t ship_speed(int32_t vx, int32_t vy)
{
    /* fld 2000.0f; fidivr vx; fidivr vy; square both; add; fstp qword; sqrt; fmul 20.0;
     * fstp qword; floor; fistp (trunc) */
    x87_t ax = x87_div_int(x87_from_int(vx), 2000);
    x87_t ay = x87_div_int(x87_from_int(vy), 2000);
    x87_t sum = x87_round_double(x87_add(x87_mul(ax, ax), x87_mul(ay, ay)));
    x87_t r = x87_round_double(x87_mul(x87_sqrt(sum), x87_from_double(20.0)));
    return (int32_t)x87_floor(r);
}

static void thrust(ship_t *s, const ship_world_t *w)
{
    int32_t m = s->max_speed, before, dx, dy;
    const int32_t *d = w->dir72[s->angle_deg / 5];
    if (s->vx > m || s->vx < -m || s->vy > m || s->vy < -m)
        before = ship_speed(s->vx, s->vy);
    else
        before = 10000;
    /* float thrust (24-bit mantissa) * |dir| <= 1000: exact in a double */
    dy = (int32_t)((double)s->thrust * d[1]);
    dx = (int32_t)((double)s->thrust * d[0]);
    s->vy -= dy;
    s->vx -= dx;
    if (ship_speed(s->vx, s->vy) > before) {
        s->vy += dy;
        s->vx += dx;
    }
}

static void rotate(ship_t *s, int sign)
{
    int32_t a = s->angle10 + sign * s->turn_rate;
    if (a > 3599) a -= 3600;
    if (a < 0) a += 3600;
    s->angle10 = a;
    s->angle_deg = a / 10;
}

void ship_step_pre(ship_t *s, const ship_keys_t *k, const ship_world_t *w, ship_events_t *ev)
{
    int32_t n;
    ev->p5_events = 0;
    ev->exhaust = 0;
    /* 1. player_apply_confusion: caller passes the already-scrambled keys */
    /* 2. thrust */
    if (k->thrust)
        thrust(s, w);
    /* 3. fire keys: weapons, not reconstructed */
    /* 4. rotation; on a base the turn keys cycle the secondary weapon instead */
    if (!s->on_base) {
        if (k->right) rotate(s, 1);
        if (k->left) rotate(s, -1);
    }
    /* 5. p5 accumulator */
    s->p5_acc += s->p5_rate;
    n = s->p5_acc / 100;
    if (n > 0) ev->p5_events = n;
    s->p5_acc -= n * 100;
    /* 6. hit flash */
    if (s->flash_timer > 0) {
        if (s->flash_timer-- == 1)
            s->flash_color = s->flash_color_restore;
    }
    /* 7. gravity, or a push (force kind 3) that decays toward (0, 12) */
    if (s->push_timer == 0) {
        s->vy += w->gravity;
    } else {
        if (s->push_timer > 1) s->push_timer--;
        s->vx += s->push_vx;
        s->vy += s->push_vy;
        if (s->push_timer == 1) {
            if (s->push_vx > 0) s->push_vx--;
            if (s->push_vx < 0) s->push_vx++;
            if (s->push_vy > 12) s->push_vy--;
            if (s->push_vy < 12) s->push_vy++;
            if (s->push_vx == 0 && s->push_vy == 12) s->push_timer = 0;
        }
    }
    /* 8. air drag */
    ev->pre_drag_vx = s->vx;
    ev->pre_drag_vy = s->vy;
    if (w->air_pct == 100) {
        s->vx = x87_mul_trunc(SHIP_DRAG_DEFAULT, s->vx);
        s->vy = x87_mul_trunc(SHIP_DRAG_DEFAULT, s->vy);
    } else if (w->air_pct != 0) {
        s->vx = x87_mul_trunc((double)w->drag_f, s->vx);
        s->vy = x87_mul_trunc((double)w->drag_f, s->vy);
    }
    /* 9-11 (player_apply_forces, player_terrain_collide, player_apply_damage) happen between
     * ship_step_pre and ship_step_post */
}

void ship_step_post(ship_t *s, const ship_keys_t *k, const ship_world_t *w, ship_events_t *ev)
{
    /* 12. keep the next pixel inside [2, W-3] x [2, H-3] */
    if ((s->xsub + s->vx) / 1000 + s->x < 2) { s->x = 2; s->vx = 0; s->carried = 0; }
    if ((s->ysub + s->vy) / 1000 + s->y < 2) { s->y = 2; s->vy = 0; s->carried = 0; }
    if ((s->xsub + s->vx) / 1000 + s->x > w->level_w - 3) { s->x = w->level_w - 3; s->vx = 0; s->carried = 0; }
    if ((s->ysub + s->vy) / 1000 + s->y > w->level_h - 3) { s->y = w->level_h - 3; s->vy = 0; s->carried = 0; }
    /* 13. integrate (C division truncates toward zero, so sub-pixels may be negative) */
    s->xsub += s->vx;
    s->ysub += s->vy;
    s->x += s->xsub / 1000;
    s->y += s->ysub / 1000;
    s->xsub %= 1000;
    s->ysub %= 1000;
    /* exhaust particle every other tick while thrusting */
    s->exhaust_toggle ^= 1;
    if (s->exhaust_toggle == 1 && k->thrust && s->hp > 0 && !s->carried)
        ev->exhaust = 1;
}

void ship_step(ship_t *s, const ship_keys_t *k, const ship_world_t *w, ship_events_t *ev)
{
    ship_step_pre(s, k, w, ev);
    ship_step_post(s, k, w, ev);
}

void ship_next_pixel(const ship_t *s, int32_t *nx, int32_t *ny)
{
    *nx = s->x + (s->xsub + s->vx) / 1000;
    *ny = s->y + (s->ysub + s->vy) / 1000;
}
