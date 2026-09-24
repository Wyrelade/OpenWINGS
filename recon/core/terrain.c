/* Wings 1.40 terrain collision, landing and damage.  Step numbers refer to docs/systems/terrain.md. */
#include "terrain.h"
#include "material.h"
#include "x87.h"

const double TERRAIN_WATER_DRAG = 0.952;
const double TERRAIN_SPECIAL_DRAG = 0.65;

uint8_t level_get_pixel(const level_t *l, int32_t x, int32_t y)
{
    if (x < 0 || y < 0 || x >= l->w || y >= l->h)
        return 0;
    return l->pix[y * l->pitch + x];
}

void level_set_pixel(level_t *l, int32_t x, int32_t y, uint8_t c)
{
    if (x < 0 || y < 0 || x >= l->w || y >= l->h)
        return;
    l->pix[y * l->pitch + x] = c;
}

int base_owner(uint8_t c)
{
    int r = 4;
    if ((uint8_t)(c - 40) <= 1) r = 0;
    if ((uint8_t)(c - 42) <= 1) r = 1;
    if ((uint8_t)(c - 44) <= 1) r = 2;
    if ((uint8_t)(c - 46) <= 1) r = 3;
    if ((uint8_t)(c - 38) <= 1) r = 5;
    return r;
}

int water_current(uint8_t c)
{
    int r = 0;
    if (c == 49) r = 1;
    if (c == 50) r = 2;
    if (c == 51) r = 3;
    return r;
}

void player_on_base(ship_t *s)
{
    if (s->material == MAT_WATER) {
        if (s->angle_deg != 180) {
            s->xsub = 0; s->ysub = 0;
            s->vx = 0; s->vy = 0;
        }
        s->angle_deg = 180;
    } else {
        s->angle_deg = s->push_vy < 0 ? 180 : 0;
    }
    s->angle10 = s->angle_deg * 10;
}

/* the pixel the ship would occupy after integrating the current velocity */
static uint8_t probe(const ship_t *s, const level_t *l)
{
    return level_get_pixel(l, s->x + (s->xsub + s->vx) / 1000, s->y + (s->ysub + s->vy) / 1000);
}

static void splash(const ship_t *s, int32_t speed, terrain_events_t *ev)
{
    (void)s;
    ev->splash++;
    ev->splash_speed = speed;
}

static void on_base(ship_t *s, terrain_events_t *ev)
{
    player_on_base(s);
    ev->on_base_calls++;
}

void player_terrain_collide(ship_t *s, level_t *l, int32_t repair, terrain_events_t *ev)
{
    uint8_t c0 = probe(s, l), c;
    int cls = material_class(c0), k, owner;

    /* 1 */
    s->on_own_base = 0;
    s->on_any_base = 0;
    /* 2. air: leaving water, background fire */
    if (cls == MAT_AIR) {
        if (s->hp > 0 && s->material == MAT_WATER)
            splash(s, ship_speed(s->vx, s->vy), ev);
        if (c0 == 54 && s->hp > 0 && s->shield == 0) {
            s->damage_acc++;
            ev->fire++;
        }
    }
    /* 3. water: current, drag, then re-classify with the new velocity */
    if (cls == MAT_WATER) {
        if (s->material != MAT_WATER)
            splash(s, ship_speed(s->vx, s->vy), ev);
        k = water_current(probe(s, l));
        if (k == 0) s->vy -= 40;
        if (k == 1) s->vy += 120;
        if (k == 2) { s->vy -= 12; s->vx -= 90; }
        if (k == 3) { s->vy -= 12; s->vx += 90; }
        s->vx = x87_mul_trunc(TERRAIN_WATER_DRAG, s->vx);
        s->vy = x87_mul_trunc(TERRAIN_WATER_DRAG, s->vy);
        s->carried = 0;
        cls = material_class(probe(s, l));
    }
    /* 4. snow and the other class-8 colours */
    if (cls == MAT_SPECIAL) {
        if (c0 == 53 && s->material != MAT_SPECIAL)
            splash(s, ship_speed(s->vx, s->vy) / 2, ev);
        s->vx = x87_mul_trunc(TERRAIN_SPECIAL_DRAG, s->vx);
        s->vy = x87_mul_trunc(TERRAIN_SPECIAL_DRAG, s->vy);
        if ((uint32_t)(s->vy - 1) <= 23)
            s->vy = 0;
        s->carried = 0;
    }
    /* 5. hit: halve, damage by the remaining speed, then find a free axis */
    if (cls == MAT_SOLID || cls == MAT_INDESTR || cls == MAT_SOFT || cls == MAT_BURNING) {
        int32_t sv;
        s->vx /= 2;
        s->vy /= 2;
        if (cls != MAT_SOFT && s->hp > 0) {
            int32_t d = ship_speed(s->vx, s->vy);
            if (d > 1) {
                ev->hit_sound++;
                ev->hit_volume = (int8_t)(uint8_t)(d * 64 / 6);
            }
            s->damage_acc += d;
            if (s->carried == 1 && s->last_attacker == 100)
                s->last_attacker = s->u_120;
        }
        s->carried = 0;
        sv = s->vx;
        s->vx = 0;
        k = material_class(probe(s, l));
        if (k != MAT_AIR && k != MAT_WATER) {
            s->vx = sv;
            s->vy = 0;
            k = material_class(probe(s, l));
            if (k != MAT_AIR && k != MAT_WATER)
                s->vx = 0;
        }
    }
    /* 6. landing on a base */
    if (cls == MAT_BASE || cls == MAT_BASE_INDESTR) {
        owner = base_owner(probe(s, l));
        s->vx = 0;
        s->vy = 0;
        s->carried = 0;
        if (owner == 5) {
            s->on_any_base = 1;
            on_base(s, ev);
        }
        if (owner == 4 || owner == s->team) {
            on_base(s, ev);
            s->on_own_base = 1;
        }
    }
    /* 7. remember the medium the ship moves into */
    s->material = material_class(probe(s, l));
    /* 8. resting on a destructible base: the pixel below the current position */
    c = level_get_pixel(l, s->x, s->y + 1);
    if (material_class(c) == MAT_BASE) {
        on_base(s, ev);
        owner = base_owner(c);
        if (owner == 5)
            s->on_any_base = 1;
        if (owner == 4 || owner == s->team)
            s->on_own_base = 1;
        if (material_class(level_get_pixel(l, s->x, s->y - 1)) == MAT_BASE) {
            level_set_pixel(l, s->x, s->y - 1, 0);
            ev->pixels_cleared++;
        }
    }
    /* 9. repair on an own base: +repair hp every 10th tick */
    if (s->on_own_base == 1) {
        if (s->base_repair_ctr++ == 9) {
            s->base_repair_ctr = 0;
            if (s->hp > 0 && s->hp_max > s->hp) {
                s->hp += repair;
                if (s->hp > s->hp_max)
                    s->hp = s->hp_max;
            }
        }
    }
}

void player_apply_damage(ship_t *s, int32_t self, int32_t lookup, terrain_events_t *ev)
{
    int32_t d = s->damage_acc, att = s->last_attacker;
    s->damage_acc = 0;
    if (att == 100) {
        att = lookup;
        if (att == -1 && (s->push_timer > 0 || s->carried == 1))
            att = s->u_120;
        if (att == -1 || att == self)
            att = 100;
    }
    if (s->attacker_age <= 999)
        s->attacker_age++;
    if (s->attacker_age > 40)
        s->last_attacker = 100;
    if (s->shield == 1)
        d -= 15;
    if (d > 0) {
        s->flash_color = 0x1F;
        if (s->flash_timer < d) s->flash_timer = d;
        if (s->flash_timer <= 1) s->flash_timer = 2;
        if (s->carried == 1) s->u_c8 -= d >> 2;
        s->hp -= d;
        if (s->hp <= 0) {
            ev->died++;
            ev->kill_credit = att;
        }
    }
}
