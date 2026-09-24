/* Exact emulation of the few x87 operation sequences the Wings 1.40 simulation depends on.
 *
 * The original runs under DJGPP's default control word (precision = 64-bit mantissa, round to
 * nearest even) and converts to int with fistp under a control word whose high byte is 0x0C
 * (round toward zero).  A modern double (53-bit mantissa) gives different results in rare but
 * reachable cases, e.g. trunc(0.995 * v) for v a multiple of 200 (see docs/systems/physics.md).
 *
 * Portable C99: no long double, no __int128, no FPU mode changes.  Values are held as
 * sign * m * 2^e with a 64-bit mantissa and every operation rounds exactly like the x87. */
#ifndef RECON_X87_H
#define RECON_X87_H
#include <stdint.h>

typedef struct {
    int      neg;   /* 1 = negative */
    uint64_t m;     /* normalised: bit 63 set, or 0 for zero */
    int      e;     /* value = m * 2^e */
} x87_t;

x87_t   x87_from_int(int64_t v);
x87_t   x87_from_double(double d);          /* exact (IEEE-754 binary64 input) */
x87_t   x87_mul(x87_t a, x87_t b);          /* fmul, 64-bit mantissa, RN-even */
x87_t   x87_div_int(x87_t a, int32_t d);    /* fidiv / fidivr by a non-zero int32 */
x87_t   x87_add(x87_t a, x87_t b);          /* fadd of two values of the same sign */
x87_t   x87_sqrt(x87_t a);                  /* fsqrt of a non-negative value */
x87_t   x87_round_double(x87_t a);          /* fstp qword: round to 53-bit mantissa */
int64_t x87_trunc(x87_t a);                 /* fistp with RC = toward zero */
int64_t x87_floor(x87_t a);                 /* floor() then fistp */

/* trunc(c * v) computed by fld c ; fimul v ; fistp (RC = trunc). */
int32_t x87_mul_trunc(double c, int32_t v);

#endif
