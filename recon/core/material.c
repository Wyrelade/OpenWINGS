#include "material.h"

/* Same test order as the original: later matches override earlier ones. */
int material_class(uint8_t c)
{
    int r = c != 0 ? MAT_SOLID : MAT_AIR;
    if ((uint8_t)(c - 64) <= 15) r = MAT_AIR;
    if (c == 54) r = MAT_AIR;
    if ((uint8_t)(c - 32) <= 15) r = MAT_BASE;
    if ((uint8_t)(c - 48) <= 3) r = MAT_WATER;
    if ((uint8_t)(c - 80) <= 15) r = MAT_INDESTR;
    if ((uint8_t)(c - 96) <= 15) r = MAT_SOFT;
    if ((uint8_t)(c - 112) <= 15) r = MAT_BURNING;
    if ((uint8_t)(c - 38) <= 1) r = MAT_BASE_INDESTR;
    if (c == 53) r = MAT_SPECIAL;
    if ((uint8_t)(c - 17) <= 3) r = MAT_SPECIAL;
    if (c == 6) r = MAT_SPECIAL;
    return r;
}
