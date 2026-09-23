"""Reference model of the Wings 1.40 ship update (air-only subset) with exact x87 semantics.

Mirrors match_main's inlined per-player block (see docs/systems/physics.md). Used to design
trace scripts and as a second implementation to cross-check recon/core/ship.c.
Terrain collision, forces, damage, weapons, confusion are NOT modelled: callers must stop at the
first tick where the trace shows non-air material.

x87 model: multiplies/divides/sqrt round to a 64-bit mantissa (PC=extended, RN), stores to a
double round to 53 bits, fistp truncates (CW high byte 0x0C).
"""
import math
import struct
from fractions import Fraction

K_DRAG_DEFAULT = struct.unpack('<d', struct.pack('<d', 0.995))[0]


def rnd(x, bits):
    """Round a Fraction to `bits` significant bits, nearest-even (x87/IEEE)."""
    if x == 0:
        return Fraction(0)
    s = -1 if x < 0 else 1
    x = abs(x)
    e = x.numerator.bit_length() - x.denominator.bit_length()
    # scale so that m has exactly `bits` bits before the point
    while True:
        sh = bits - 1 - e
        m = x * (Fraction(2) ** sh)
        if m >= 2 ** bits:
            e += 1
            continue
        if m < 2 ** (bits - 1):
            e -= 1
            continue
        break
    q, r = divmod(m.numerator, m.denominator)
    r2 = 2 * r
    if r2 > m.denominator or (r2 == m.denominator and q & 1):
        q += 1
    return s * Fraction(q) / (Fraction(2) ** sh)


def ext(x):
    return rnd(Fraction(x), 64)


def dbl(x):
    return rnd(Fraction(x), 53)


def trunc(x):
    x = Fraction(x)
    return int(x.numerator / x.denominator) if False else (
        x.numerator // x.denominator if x >= 0 else -((-x.numerator) // x.denominator))


def f32(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]


def ext_sqrt(x):
    """Correctly rounded 64-bit-mantissa sqrt of a non-negative Fraction (fsqrt, RN)."""
    if x == 0:
        return Fraction(0)
    # compute floor(sqrt(x) * 2^k) with enough bits, then round
    k = 80
    n = x.numerator * (1 << (2 * k)) // x.denominator
    r = math.isqrt(n)
    exact = (r * r * x.denominator == x.numerator * (1 << (2 * k)))
    # r/2^k <= sqrt(x) < (r+1)/2^k ; add a sticky half-ulp below precision to break ties correctly
    val = Fraction(r, 1 << k) + (0 if exact else Fraction(1, 1 << (k + 1)))
    return rnd(val, 64)


def ship_speed(vx, vy):
    """FUN_0000903c: trunc(floor(20 * sqrt((vx/2000f)^2 + (vy/2000f)^2)))."""
    ax = ext(Fraction(vx) / 2000)
    ay = ext(Fraction(vy) / 2000)
    s = dbl(ext(ext(ay * ay) + ext(ax * ax)))
    r = dbl(ext(ext_sqrt(s) * 20))
    fl = math.floor(r)
    return int(fl)


def drag_mul(c, v):
    return trunc(ext(Fraction(c) * v))


def step(p, keys, dir72, g):
    """One tick. p: dict with x,y,xsub,ysub,vx,vy,angle10,angle_deg,p5_acc + params.
    keys: dict thrust,left,right. g: dict gravity, air_pct, drag_f."""
    p = dict(p)
    # 2. thrust
    if keys.get('thrust'):
        m = p['max_speed']
        if p['vx'] > m or p['vx'] < -m or p['vy'] > m or p['vy'] < -m:
            before = ship_speed(p['vx'], p['vy'])
        else:
            before = 10000
        k = p['angle_deg'] // 5
        c, s = dir72[k]
        th = Fraction(f32(p['thrust']))
        dy = trunc(th * s)          # exact: 24-bit x 10-bit product fits a 64-bit mantissa
        dx = trunc(th * c)
        p['vy'] -= dy
        p['vx'] -= dx
        if ship_speed(p['vx'], p['vy']) > before:
            p['vy'] += dy
            p['vx'] += dx
    # 4. rotation (not on a base)
    if not p.get('on_base'):
        for key, sgn in (('right', 1), ('left', -1)):
            if keys.get(key):
                a = p['angle10'] + sgn * p['turn_rate']
                if a > 3599:
                    a -= 3600
                if a < 0:
                    a += 3600
                p['angle10'] = a
                p['angle_deg'] = trunc(Fraction(a, 10))
    # 5. p5 accumulator
    p['p5_acc'] += p['p5_rate']
    n = trunc(Fraction(p['p5_acc'], 100))
    p['p5_acc'] -= 100 * n
    # 7. gravity (push_timer assumed 0)
    p['vy'] += g['gravity']
    # 8. drag
    if g['air_pct'] == 100:
        p['vx'] = drag_mul(K_DRAG_DEFAULT, p['vx'])
        p['vy'] = drag_mul(K_DRAG_DEFAULT, p['vy'])
    elif g['air_pct'] != 0:
        c = f32(g['drag_f'])
        p['vx'] = drag_mul(c, p['vx'])
        p['vy'] = drag_mul(c, p['vy'])
    # 12. clamps (level bounds) skipped for air-only use; 13. integrate
    for a, sub, v in (('x', 'xsub', 'vx'), ('y', 'ysub', 'vy')):
        t = p[sub] + p[v]
        q = trunc(Fraction(t, 1000))
        p[a] += q
        p[sub] = t - 1000 * q
    return p
