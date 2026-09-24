/* Cross-check of recon/core/x87.c against tools/ship_model.py (exact rational x87 model).
 * stdin: lines "vx vy"; stdout: "ship_speed(vx,vy) trunc(0.995*vx) trunc(0.995f*vx)". */
#include <stdio.h>
#include "../core/ship.h"
#include "../core/x87.h"

int main(void)
{
    long vx, vy;
    const float f = 0.995f;
    while (scanf("%ld %ld", &vx, &vy) == 2)
        printf("%ld %ld %ld\n", (long)ship_speed((int32_t)vx, (int32_t)vy),
               (long)x87_mul_trunc(SHIP_DRAG_DEFAULT, (int32_t)vx),
               (long)x87_mul_trunc((double)f, (int32_t)vx));
    return 0;
}
