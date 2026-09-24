/* See x87.h.  128-bit intermediates are built from two uint64_t limbs. */
#include "x87.h"
#include <string.h>

typedef struct { uint64_t hi, lo; } u128;

static u128 u128_make(uint64_t hi, uint64_t lo) { u128 r; r.hi = hi; r.lo = lo; return r; }

static int bitlen64(uint64_t v)
{
    int n = 0;
    while (v) { n++; v >>= 1; }
    return n;
}

static int bitlen128(u128 v) { return v.hi ? 64 + bitlen64(v.hi) : bitlen64(v.lo); }

static u128 shr128(u128 v, int n)
{
    if (n <= 0) return v;
    if (n >= 128) return u128_make(0, 0);
    if (n >= 64) return u128_make(0, v.hi >> (n - 64));
    return u128_make(v.hi >> n, (v.lo >> n) | (v.hi << (64 - n)));
}

static u128 shl128(u128 v, int n)
{
    if (n <= 0) return v;
    if (n >= 128) return u128_make(0, 0);
    if (n >= 64) return u128_make(v.lo << (n - 64), 0);
    return u128_make((v.hi << n) | (v.lo >> (64 - n)), v.lo << n);
}

/* non-zero if any of the low n bits of v are set */
static int lowbits128(u128 v, int n)
{
    if (n <= 0) return 0;
    if (n >= 128) return v.hi || v.lo;
    if (n >= 64) return v.lo || (n > 64 && (v.hi << (128 - n)));
    return (v.lo << (64 - n)) != 0;
}

static int bit128(u128 v, int i) { return i >= 64 ? (int)((v.hi >> (i - 64)) & 1) : (int)((v.lo >> i) & 1); }

static u128 add128(u128 a, u128 b)
{
    u128 r;
    r.lo = a.lo + b.lo;
    r.hi = a.hi + b.hi + (r.lo < a.lo);
    return r;
}

static u128 sub128(u128 a, u128 b)
{
    u128 r;
    r.lo = a.lo - b.lo;
    r.hi = a.hi - b.hi - (a.lo < b.lo);
    return r;
}

static int cmp128(u128 a, u128 b)
{
    if (a.hi != b.hi) return a.hi < b.hi ? -1 : 1;
    if (a.lo != b.lo) return a.lo < b.lo ? -1 : 1;
    return 0;
}

static u128 mul64(uint64_t a, uint64_t b)
{
    uint64_t a0 = a & 0xFFFFFFFFu, a1 = a >> 32, b0 = b & 0xFFFFFFFFu, b1 = b >> 32;
    uint64_t p00 = a0 * b0, p01 = a0 * b1, p10 = a1 * b0, p11 = a1 * b1;
    uint64_t mid = (p00 >> 32) + (p01 & 0xFFFFFFFFu) + (p10 & 0xFFFFFFFFu);
    u128 r;
    r.lo = (p00 & 0xFFFFFFFFu) | (mid << 32);
    r.hi = p11 + (p01 >> 32) + (p10 >> 32) + (mid >> 32);
    return r;
}

static x87_t zero(int neg) { x87_t z; z.neg = neg; z.m = 0; z.e = 0; return z; }

/* Round the exact value (-1)^neg * (M + sticky*tiny) * 2^E to `bits` significant bits
 * (round to nearest, ties to even) and normalise to a 64-bit mantissa.  `sticky` stands for
 * non-zero bits below M; callers keep at least bits+2 bits in M whenever sticky can be set. */
static x87_t round_to(u128 M, int E, int sticky, int bits, int neg)
{
    x87_t r;
    uint64_t q;
    int L = bitlen128(M), sh;
    if (L == 0) return zero(neg);
    if (L > bits) {
        int drop = L - bits;
        int guard = bit128(M, drop - 1);
        int rest = lowbits128(M, drop - 1) || sticky;
        q = shr128(M, drop).lo;
        if (guard && (rest || (q & 1))) {
            q++;
            if (bits == 64 ? q == 0 : q == ((uint64_t)1 << bits)) {
                q = (uint64_t)1 << (bits - 1);
                drop++;
            }
        }
        E += drop;
    } else {
        q = M.lo;
    }
    sh = 64 - bitlen64(q);
    r.neg = neg;
    r.m = q << sh;
    r.e = E - sh;
    return r;
}

x87_t x87_from_int(int64_t v)
{
    uint64_t u = v < 0 ? (uint64_t)0 - (uint64_t)v : (uint64_t)v;
    return round_to(u128_make(0, u), 0, 0, 64, v < 0);
}

x87_t x87_from_double(double d)
{
    uint64_t b, frac;
    int ex, neg;
    memcpy(&b, &d, sizeof b);
    neg = (int)(b >> 63);
    ex = (int)((b >> 52) & 0x7FF);
    frac = b & (((uint64_t)1 << 52) - 1);
    if (ex == 0) /* zero or subnormal */
        return round_to(u128_make(0, frac), -1074, 0, 64, neg);
    return round_to(u128_make(0, frac | ((uint64_t)1 << 52)), ex - 1075, 0, 64, neg);
}

x87_t x87_mul(x87_t a, x87_t b)
{
    if (!a.m || !b.m) return zero(a.neg ^ b.neg);
    return round_to(mul64(a.m, b.m), a.e + b.e, 0, 64, a.neg ^ b.neg);
}

x87_t x87_div_int(x87_t a, int32_t d)
{
    uint32_t dig[4], qd[4];
    uint64_t r = 0, ud = d < 0 ? (uint64_t)0 - (uint64_t)(int64_t)d : (uint64_t)d;
    int i, neg = a.neg ^ (d < 0);
    if (!a.m) return zero(neg);
    /* (a.m << 64) / |d|, schoolbook over 32-bit digits (|d| < 2^32 so r fits) */
    dig[0] = (uint32_t)(a.m >> 32); dig[1] = (uint32_t)a.m; dig[2] = 0; dig[3] = 0;
    for (i = 0; i < 4; i++) {
        uint64_t cur = (r << 32) | dig[i];
        qd[i] = (uint32_t)(cur / ud);
        r = cur % ud;
    }
    return round_to(u128_make(((uint64_t)qd[0] << 32) | qd[1], ((uint64_t)qd[2] << 32) | qd[3]),
                    a.e - 64, r != 0, 64, neg);
}

x87_t x87_add(x87_t a, x87_t b)
{
    u128 A, B;
    int d, sticky;
    if (!a.m) return b;
    if (!b.m) return a;
    if (a.e < b.e) { x87_t t = a; a = b; b = t; }
    d = a.e - b.e;
    A = u128_make(a.m >> 1, a.m << 63);          /* a.m * 2^63, top bit at 126 */
    B = u128_make(b.m >> 1, b.m << 63);
    sticky = lowbits128(B, d);
    B = shr128(B, d);
    return round_to(add128(A, B), a.e - 63, sticky, 64, a.neg);
}

x87_t x87_sqrt(x87_t a)
{
    u128 R, res, bit, t;
    int sh, e2;
    uint64_t q;
    x87_t r;
    if (!a.m) return a;
    /* R = m * 2^sh with 127 or 128 bits and (e - sh) even: sqrt(R) lies in [2^63, 2^64) */
    sh = ((a.e - 63) % 2 == 0) ? 63 : 64;
    R = shl128(u128_make(0, a.m), sh);
    e2 = (a.e - sh) / 2;
    /* bitwise integer square root; R ends as the remainder R - res^2 */
    res = u128_make(0, 0);
    bit = u128_make((uint64_t)1 << 62, 0);         /* 2^126 */
    while (cmp128(bit, R) > 0) bit = shr128(bit, 2);
    while (bit.hi || bit.lo) {
        t = add128(res, bit);
        if (cmp128(R, t) >= 0) {
            R = sub128(R, t);
            res = add128(shr128(res, 1), bit);
        } else {
            res = shr128(res, 1);
        }
        bit = shr128(bit, 2);
    }
    q = res.lo;
    /* round to nearest: up iff sqrt > q + 1/2  <=>  R - q^2 > q (a tie is impossible) */
    if (cmp128(R, u128_make(0, q)) > 0) {
        q++;
        if (q == 0) { q = (uint64_t)1 << 63; e2++; }
    }
    r.neg = 0;
    r.m = q;
    r.e = e2;
    return r;
}

x87_t x87_round_double(x87_t a)
{
    return round_to(u128_make(0, a.m), a.e, 0, 53, a.neg);
}

int64_t x87_trunc(x87_t a)
{
    uint64_t q;
    if (!a.m) return 0;
    if (a.e >= 0) q = a.e >= 63 ? 0 : a.m << a.e;       /* out of range: not used */
    else q = -a.e >= 64 ? 0 : a.m >> -a.e;
    return a.neg ? -(int64_t)q : (int64_t)q;
}

int64_t x87_floor(x87_t a)
{
    int64_t t = x87_trunc(a);
    if (a.neg && a.e < 0) {
        int n = -a.e;
        int frac = n >= 64 ? 1 : (a.m & ((((uint64_t)1) << n) - 1)) != 0;
        if (frac) t -= 1;
    }
    return t;
}

int32_t x87_mul_trunc(double c, int32_t v)
{
    return (int32_t)x87_trunc(x87_mul(x87_from_double(c), x87_from_int(v)));
}
