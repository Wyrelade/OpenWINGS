/* material_class (0x3987C): palette index -> material class.  Ported from disassembly. */
#ifndef RECON_MATERIAL_H
#define RECON_MATERIAL_H
#include <stdint.h>

enum {
    MAT_AIR = 0,        /* 0, 54 (background fire), 64..79 (drawn background) */
    MAT_SOLID = 1,      /* everything not listed (128..255 ground, 52 bubbles, 55..63, ...) */
    MAT_BASE = 2,       /* 32..47 except 38..39 */
    MAT_WATER = 3,      /* 48..51 */
    MAT_INDESTR = 4,    /* 80..95 */
    MAT_BASE_INDESTR = 5, /* 38..39 */
    MAT_SOFT = 6,       /* 96..111 */
    MAT_BURNING = 7,    /* 112..127 */
    MAT_SPECIAL = 8     /* 6, 17..20, 53 [?] */
};

int material_class(uint8_t c);

#endif
