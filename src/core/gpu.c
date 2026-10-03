/* GPU: packet-list walker and integer triangle rasterizer drawing into VRAM.
 * No floating point: every result is bit-exact on every host. */
#include "machine.h"
#include "font8x8.h"

#include <string.h>

/* VRAM is a byte array of little-endian 16-bit pixels. gpu_front hands it out
 * as uint16_t, which is only correct on a little-endian host (wasm32, arm64, x86). */
#if defined(__BYTE_ORDER__) && defined(__ORDER_LITTLE_ENDIAN__)
_Static_assert(__BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__, "Mei core requires a little-endian host");
#endif

#define FB_OFF(a)   ((a) - VRAM_BASE)
#define PAL_OFF     (PALETTE_ADDR - VRAM_BASE)
#define TEX_OFF     (TEXTURE_ADDR - VRAM_BASE)
#define TEX_MASK    0x7FFFFu        /* the 16 slots are 512 KB; 8-bit slot 15 wraps to slot 0 */
#define LIST_END    0xFFFFFFu

static inline uint16_t ld16(const uint8_t *p) { uint16_t v; memcpy(&v, p, 2); return v; }
static inline void st16(uint8_t *p, uint16_t v) { memcpy(p, &v, 2); }

static const int8_t dither_m[4][4] = {
    {-4, 0, -3, 1}, {2, -2, 3, -1}, {-3, 1, -4, 0}, {3, -1, 2, -2},
};

/* 5-bit -> 8-bit expansion: (c << 3) | (c >> 2) */
static const uint8_t expand5[32] = {
    0, 8, 16, 24, 33, 41, 49, 57, 66, 74, 82, 90, 99, 107, 115, 123,
    132, 140, 148, 156, 165, 173, 181, 189, 198, 206, 214, 222, 231, 239, 247, 255,
};

/* ---- buffers ---- */

void gpu_reset(Mei *m) {
    m->back = 0;
    m->gpu_ctrl = 0;
    m->gpu_status = 0;
}

uint32_t gpu_back_addr(const Mei *m) { return m->back ? FB_B_ADDR : FB_A_ADDR; }

const uint16_t *gpu_front(Mei *m) {
    return (const uint16_t *)(void *)(m->vram + FB_OFF(m->back ? FB_A_ADDR : FB_B_ADDR));
}

void gpu_vsync(Mei *m) {
    m->back ^= 1;
    m->gpu_status = 0;
}

/* The cost model's per-pixel table (the constants are in machine.h). */
uint32_t gpu_pixel_cycles(int kind) {
    uint32_t c = GPU_CYCLES_PX;
    if (kind & 2) c *= GPU_CYCLES_TEX_X;
    if (kind & 4) c *= GPU_CYCLES_SEMI_X;
    return c;
}

void gpu_clear(Mei *m, uint32_t colour) {
    m->gstat.clears++;
    m->gpu_cycles += GPU_CYCLES_CLEAR;
    uint8_t *fb = m->vram + FB_OFF(gpu_back_addr(m));
    uint16_t c = (uint16_t)(colour & (planes_on(m) ? 0xFFFF : 0x7FFF));   /* 16 bits: holes */
    for (int i = 0; i < MEI_W * MEI_H; i++) st16(fb + 2 * i, c);
}

/* ---- rasterizer ---- */

typedef struct {
    int32_t x, y;
    int32_t a[5];      /* r, g, b, u, v (each 0-255) */
} Vtx;

typedef struct {
    uint8_t *fb;
    const uint8_t *vram;
    int gouraud, textured, semi, mode, dither, four;
    int32_t flat[3];   /* polygon colour when not Gouraud */
    uint32_t slot;     /* byte offset of the texture slot within the texture area */
    uint32_t pal;      /* first palette colour index */
    uint16_t upper;    /* 0x8000: the packet draws into the PH layer (compositor on, colour bit 26) */
    const Mei *planes; /* compositor on and the packet blends: see planes_under() */
    PlnUnder *under;   /* this span's context (set per span when planes) */
} Raster;

static int64_t floor_div(int64_t n, int64_t d) {
    int64_t q = n / d;
    if ((n % d) != 0 && ((n < 0) != (d < 0))) q--;
    return q;
}

static int64_t ceil_div(int64_t n, int64_t d) { return -floor_div(-n, d); }

/* Attribute interpolation. Each attribute (r, g, b, u, v) at pixel p is
 * exactly floor(N(p) / area), where N(p) = sum_i a_i E_i(p) is linear in p.
 * Inside the triangle every E_i >= 0 and they sum to area, so the value is a
 * convex combination of the vertex values: it equals them at the vertices and
 * never leaves 0-255.
 *
 * Fast path: an F-bit fixed-point accumulator that is always rounded up
 * (ceil-rounded start and forward steps, floor-rounded backward steps), so
 * its error e satisfies 0 <= e < (steps + 1) ulps. A row walk takes at most
 * 1 + 239 + 638 + 319 < 1200 steps, so choosing 2^F >= 1200 * area keeps
 * e < 2^F / area. Since N / area is a multiple of 1 / area, adding less than
 * 1 / area never crosses an integer: acc >> F == floor(N / area) exactly.
 *
 * Slow path (huge or extreme triangles that would overflow the fast path):
 * an exact quotient/remainder DDA. Both give identical results. */
typedef struct { int32_t q, qs; int64_t r, rs; } Dda;

#if defined(__GNUC__) || defined(__clang__)
#define FORCE_INLINE inline __attribute__((always_inline))
#else
#define FORCE_INLINE inline
#endif

enum { F_GOURAUD = 1, F_TEXTURED = 2, F_SEMI = 4, F_DITHER = 8 };

static FORCE_INLINE int clamp255(int v) { return v < 0 ? 0 : v > 255 ? 255 : v; }
static FORCE_INLINE int clamp31(int v) { return v < 0 ? 0 : v > 31 ? 31 : v; }

/* The pixel pipeline for one pixel: texel + tint, dither, blend, write. */
static FORCE_INLINE void shade(const Raster *R, uint8_t *row, int x, const int8_t *dm,
                               int r, int g, int b, uint32_t u, uint32_t v, const int F) {
    if (F & F_TEXTURED) {
        const uint8_t *tex = R->vram + TEX_OFF;
        uint32_t idx;
        u &= 255; v &= 255;
        if (R->four) idx = (tex[R->slot + v * 128 + (u >> 1)] >> ((u & 1) * 4)) & 15;
        else idx = tex[(R->slot + v * 256 + u) & TEX_MASK];
        if (idx == 0) return;
        uint32_t t = ld16(R->vram + PAL_OFF + (R->pal + idx) * 2);
        r = expand5[t & 31] * r >> 7;
        g = expand5[(t >> 5) & 31] * g >> 7;
        b = expand5[(t >> 10) & 31] * b >> 7;
        if (r > 255) r = 255;
        if (g > 255) g = 255;
        if (b > 255) b = 255;
    }
    if (F & F_DITHER) {
        int o = dm[x & 3];
        r = clamp255(r + o) >> 3; g = clamp255(g + o) >> 3; b = clamp255(b + o) >> 3;
    } else {
        r >>= 3; g >>= 3; b >>= 3;
    }
    if (F & F_SEMI) {
        uint32_t bg = ld16(row + x * 2);
        /* rev 2: over a hole, or (upper) over a lower pixel, blend with the layers behind */
        if (R->under && (bg == PLN_HOLE || (R->upper && !(bg & 0x8000))))
            bg = planes_under(R->under, x, bg, R->upper != 0);
        int br = bg & 31, bgr = (bg >> 5) & 31, bb = (bg >> 10) & 31;
        switch (R->mode) {
        case 0: r = (br + r) >> 1; g = (bgr + g) >> 1; b = (bb + b) >> 1; break;
        case 1: r = clamp31(br + r); g = clamp31(bgr + g); b = clamp31(bb + b); break;
        case 2: r = clamp31(br - r); g = clamp31(bgr - g); b = clamp31(bb - b); break;
        default: r = clamp31(br + (r >> 2)); g = clamp31(bgr + (g >> 2)); b = clamp31(bb + (b >> 2)); break;
        }
    }
    uint16_t out = (uint16_t)(r | g << 5 | b << 10) | R->upper;
    if (out == PLN_HOLE) out = 0x8400;   /* upper black: never a hole (blue 1 of 31) */
    st16(row + x * 2, out);
}

/* Fast span: acc[k] holds attribute k in F-bit fixed point at x0, step[k] per pixel. */
static FORCE_INLINE void span_fixed(const Raster *R, uint8_t *row, int y, int x0, int x1,
                                    const int64_t *acc, const int64_t *step, int sh, const int F) {
    Raster L = *R;   /* local copy: framebuffer stores could otherwise alias *R */
    PlnUnder u;
    if ((F & F_SEMI) && L.planes) { u.m = L.planes; u.y = y; u.ready = 0; L.under = &u; }
    int64_t ar = acc[0], ag = acc[1], ab = acc[2], au = acc[3], av = acc[4];
    const int64_t sr = step[0], sg = step[1], sb = step[2], su = step[3], sv = step[4];
    const int8_t *dm = dither_m[y & 3];
    for (int x = x0; x <= x1; x++) {
        int r = L.flat[0], g = L.flat[1], b = L.flat[2];
        uint32_t u = 0, v = 0;
        if (F & F_GOURAUD) {
            r = (int)((uint64_t)ar >> sh); g = (int)((uint64_t)ag >> sh); b = (int)((uint64_t)ab >> sh);
            ar += sr; ag += sg; ab += sb;
        }
        if (F & F_TEXTURED) {
            u = (uint32_t)((uint64_t)au >> sh); v = (uint32_t)((uint64_t)av >> sh);
            au += su; av += sv;
        }
        shade(&L, row, x, dm, r, g, b, u, v, F);
    }
}

typedef void (*SpanFn)(const Raster *, uint8_t *, int, int, int, const int64_t *, const int64_t *, int);
#define SPAN_FN(F) static void span_##F(const Raster *R, uint8_t *row, int y, int x0, int x1, \
    const int64_t *acc, const int64_t *step, int sh) { span_fixed(R, row, y, x0, x1, acc, step, sh, F); }
SPAN_FN(0) SPAN_FN(1) SPAN_FN(2) SPAN_FN(3) SPAN_FN(4) SPAN_FN(5) SPAN_FN(6) SPAN_FN(7)
SPAN_FN(8) SPAN_FN(9) SPAN_FN(10) SPAN_FN(11) SPAN_FN(12) SPAN_FN(13) SPAN_FN(14) SPAN_FN(15)
static const SpanFn span_fns[16] = {
    span_0, span_1, span_2, span_3, span_4, span_5, span_6, span_7,
    span_8, span_9, span_10, span_11, span_12, span_13, span_14, span_15,
};

/* Slow exact span (flags at run time). */
static void span_exact(const Raster *R, uint8_t *row, int y, int x0, int x1, const Dda *d0, int64_t area, int F) {
    Dda d[5];
    memcpy(d, d0, sizeof d);
    const int8_t *dm = dither_m[y & 3];
    Raster L = *R;
    PlnUnder u;
    if ((F & F_SEMI) && L.planes) { u.m = L.planes; u.y = y; u.ready = 0; L.under = &u; }
    R = &L;
    for (int x = x0; x <= x1; x++) {
        int r = (F & F_GOURAUD) ? d[0].q : R->flat[0];
        int g = (F & F_GOURAUD) ? d[1].q : R->flat[1];
        int b = (F & F_GOURAUD) ? d[2].q : R->flat[2];
        shade(R, row, x, dm, r, g, b, (uint32_t)d[3].q, (uint32_t)d[4].q, F);
        for (int k = 0; k < 5; k++) {
            d[k].q += d[k].qs;
            d[k].r += d[k].rs;
            if (d[k].r >= area) { d[k].r -= area; d[k].q++; }
        }
    }
}

/* Returns the number of pixels written (for the frame statistics). */
static uint32_t draw_tri(const Raster *R, const Vtx *v0, const Vtx *v1, const Vtx *v2) {
    uint32_t filled = 0;
    int64_t area = (int64_t)(v1->x - v0->x) * (v2->y - v0->y) - (int64_t)(v1->y - v0->y) * (v2->x - v0->x);
    if (area == 0) return 0;
    if (area < 0) { const Vtx *t = v1; v1 = v2; v2 = t; area = -area; }

    int32_t minx = v0->x, maxx = v0->x, miny = v0->y, maxy = v0->y;
    const Vtx *V[3] = {v0, v1, v2};
    for (int i = 1; i < 3; i++) {
        if (V[i]->x < minx) minx = V[i]->x;
        if (V[i]->x > maxx) maxx = V[i]->x;
        if (V[i]->y < miny) miny = V[i]->y;
        if (V[i]->y > maxy) maxy = V[i]->y;
    }
    if (minx < 0) minx = 0;
    if (miny < 0) miny = 0;
    if (maxx > MEI_W - 1) maxx = MEI_W - 1;
    if (maxy > MEI_H - 1) maxy = MEI_H - 1;
    if (minx > maxx || miny > maxy) return 0;

    /* Edge i is opposite vertex i: E_i(p) = A x + B y + C, the weight of vertex i.
     * With area > 0, p is inside when every E_i + bias_i >= 0; bias is 0 on top
     * and left edges and -1 elsewhere (top-left fill rule). */
    int64_t A[3], B[3], C[3], bias[3];
    for (int i = 0; i < 3; i++) {
        const Vtx *a = V[(i + 1) % 3], *b = V[(i + 2) % 3];
        A[i] = (int64_t)a->y - b->y;
        B[i] = (int64_t)b->x - a->x;
        C[i] = -(A[i] * a->x + B[i] * a->y);
        bias[i] = (A[i] > 0 || (A[i] == 0 && B[i] > 0)) ? 0 : -1;
    }

    /* Span limits per row: edge i allows x >= -floor(M/D) when A > 0, or
     * x <= floor(M/D) when A < 0, with M = B y + C + bias and D = |A|.
     * floor(M/D) is stepped exactly down the rows (quotient + remainder). */
    int64_t eq[3] = {0}, er[3] = {0}, eqs[3] = {0}, ers[3] = {0}, D[3] = {0};
    for (int i = 0; i < 3; i++) {
        if (A[i] == 0) continue;
        D[i] = A[i] < 0 ? -A[i] : A[i];
        int64_t M = B[i] * miny + C[i] + bias[i];
        eq[i] = floor_div(M, D[i]);
        er[i] = M - eq[i] * D[i];
        eqs[i] = floor_div(B[i], D[i]);
        ers[i] = B[i] - eqs[i] * D[i];
    }

    /* Attributes: N_k(p) = sum_i a_ik E_i(p) = NA x + NB y + NC. */
    int flags = (R->gouraud ? F_GOURAUD : 0) | (R->textured ? F_TEXTURED : 0) |
                (R->semi ? F_SEMI : 0) | (R->dither ? F_DITHER : 0);
    int lo = R->gouraud ? 0 : 3, hi = R->textured ? 5 : 3;
    int64_t NA[5] = {0}, NB[5] = {0}, NC[5] = {0}, gmax = 0;
    for (int k = lo; k < hi; k++) {
        for (int i = 0; i < 3; i++) {
            NA[k] += V[i]->a[k] * A[i];
            NB[k] += V[i]->a[k] * B[i];
            NC[k] += V[i]->a[k] * C[i];
        }
        int64_t ga = (NA[k] < 0 ? -NA[k] : NA[k]) / area + 1, gb = (NB[k] < 0 ? -NB[k] : NB[k]) / area + 1;
        if (ga > gmax) gmax = ga;
        if (gb > gmax) gmax = gb;
    }
    int sh = 0;
    while (((int64_t)1 << sh) < 1200 * area) sh++;
    /* Fast path needs rem << sh, |gradient| << sh and the accumulator to stay below 2^62. */
    int fast = area < ((int64_t)1 << 26) && gmax < ((int64_t)1 << (52 - sh));

    int64_t sx_up[5] = {0}, sx_dn[5] = {0}, sy_up[5] = {0}, acc[5] = {0};
    Dda d[5] = {{0, 0, 0, 0}};
    for (int k = lo; k < hi; k++) {
        int64_t q = floor_div(NA[k], area), rm = NA[k] - q * area;
        if (fast) {
            sx_dn[k] = q * ((int64_t)1 << sh) + (rm << sh) / area;
            sx_up[k] = q * ((int64_t)1 << sh) + ceil_div(rm << sh, area);
            int64_t qy = floor_div(NB[k], area), ry = NB[k] - qy * area;
            sy_up[k] = qy * ((int64_t)1 << sh) + ceil_div(ry << sh, area);
        } else {
            d[k].qs = (int32_t)q;
            d[k].rs = rm;
        }
    }

    SpanFn fn = span_fns[flags];
    int32_t px = 0, py = INT32_MIN;   /* where acc[] was last evaluated */
    for (int32_t y = miny; y <= maxy; y++) {
        int32_t xl = minx, xr = maxx;
        int empty = 0;
        for (int i = 0; i < 3; i++) {
            if (A[i] > 0) { if (-eq[i] > xl) xl = (int32_t)(-eq[i] > xr ? xr + 1 : -eq[i]); }
            else if (A[i] < 0) { if (eq[i] < xr) xr = (int32_t)(eq[i] < xl ? xl - 1 : eq[i]); }
            else if (B[i] * y + C[i] + bias[i] < 0) empty = 1;
            if (A[i]) { eq[i] += eqs[i]; er[i] += ers[i]; if (er[i] >= D[i]) { er[i] -= D[i]; eq[i]++; } }
        }
        if (empty || xl > xr) continue;
        uint8_t *row = R->fb + (size_t)y * MEI_W * 2;
        filled += (uint32_t)(xr - xl + 1);

        if (!fast) {
            for (int k = lo; k < hi; k++) {
                int64_t n = NA[k] * xl + NB[k] * y + NC[k], q = floor_div(n, area);
                d[k].q = (int32_t)q;
                d[k].r = n - q * area;
            }
            span_exact(R, row, y, xl, xr, d, area, flags);
            continue;
        }
        if (y == py + 1) {   /* walk from the previous row start, rounding up */
            int32_t dx = xl - px;
            for (int k = lo; k < hi; k++) acc[k] += sy_up[k] + (dx >= 0 ? sx_up[k] : sx_dn[k]) * dx;
        } else {
            for (int k = lo; k < hi; k++) {
                int64_t n = NA[k] * xl + NB[k] * y + NC[k], q = floor_div(n, area);
                acc[k] = q * ((int64_t)1 << sh) + ceil_div((n - q * area) << sh, area);
            }
        }
        px = xl;
        py = y;
        fn(R, row, y, xl, xr, acc, sx_up, sh);
    }
    return filled;
}

/* ---- packet list ---- */

static inline int32_t sext16(uint32_t v) { return (int32_t)(v & 0xFFFF) - (int32_t)((v & 0x8000) << 1); }

/* Reads a word of a packet from RAM or ROM; 0 if outside both. addr is word-aligned. */
static int list_word(const Mei *m, uint32_t addr, uint32_t *out) {
    if (addr < RAM_BASE + RAM_SIZE) { *out = rd32(m->ram + addr); return 1; }
    if (addr - ROM_BASE < ROM_WINDOW) { *out = rom_word(m, addr - ROM_BASE); return 1; }
    return 0;
}

/* Draws one polygon packet; returns 0 if it faulted. */
static int draw_poly(Mei *m, uint32_t addr, uint32_t type) {
    int gouraud = type & 1, textured = (type >> 1) & 1, quad = (type >> 2) & 1, semi = (type >> 3) & 1;
    int nv = quad ? 4 : 3;
    int nw = (gouraud ? nv : 1) + nv + (textured ? nv : 0);
    uint32_t w[12];
    for (int k = 0; k < nw; k++) {
        uint32_t a = addr + 4 + 4 * (uint32_t)k;
        if (!list_word(m, a, &w[k])) { mei_raise(m, MEI_FAULT_UNMAPPED, a); return 0; }
    }

    Vtx vx[4];
    uint32_t col0 = w[0], tex0 = 0;
    int p = 0;
    for (int i = 0; i < nv; i++) {
        uint32_t col = (gouraud || i == 0) ? w[p++] : col0;
        vx[i].a[0] = col & 0xFF;
        vx[i].a[1] = (col >> 8) & 0xFF;
        vx[i].a[2] = (col >> 16) & 0xFF;
        uint32_t pos = w[p++];
        vx[i].x = sext16(pos);
        vx[i].y = sext16(pos >> 16);
        uint32_t t = textured ? w[p++] : 0;
        if (i == 0) tex0 = t;
        vx[i].a[3] = t & 0xFF;
        vx[i].a[4] = (t >> 8) & 0xFF;
    }

    Raster R;
    R.fb = m->vram + FB_OFF(gpu_back_addr(m));
    R.vram = m->vram;
    R.gouraud = gouraud;
    R.textured = textured;
    R.semi = semi;
    R.mode = (col0 >> 24) & 3;
    R.dither = m->gpu_ctrl & 1;
    R.four = (tex0 >> 20) & 1;
    R.flat[0] = vx[0].a[0];
    R.flat[1] = vx[0].a[1];
    R.flat[2] = vx[0].a[2];
    R.slot = ((tex0 >> 16) & 15) * TEXTURE_SLOT_BYTES;
    R.pal = R.four ? (tex0 >> 24) * 16 : ((tex0 >> 24) & 15) * 256;
    R.upper = (planes_on(m) && (col0 >> 26 & 1)) ? 0x8000 : 0;
    R.planes = (planes_on(m) && semi) ? m : NULL;
    R.under = NULL;

    for (int t = 0; t < (quad ? 2 : 1); t++) {
        if ((m->gpu_status & 0xFFFF) >= GPU_TRI_LIMIT) { m->gpu_status |= GPU_STATUS_DROPPED; m->gstat.tris_dropped++; continue; }
        m->gpu_status++;
        uint32_t n = draw_tri(&R, &vx[t], &vx[t + 1], &vx[t + 2]);
        int kind = gouraud | textured << 1 | semi << 2;
        m->gstat.tris++;
        if (!n) m->gstat.tris_empty++;
        m->gstat.px[kind] += n;
        m->gpu_cycles += GPU_CYCLES_TRI + (uint64_t)n * gpu_pixel_cycles(kind);
    }
    return 1;
}

void gpu_draw_list(Mei *m, uint32_t addr) {
    uint32_t count = 0;
    m->gstat.lists++;
    while (addr != LIST_END) {
        if (++count > GPU_LIST_LIMIT) { mei_raise(m, MEI_FAULT_BAD_PACKET_LIST, addr); return; }
        if (addr >= RAM_BASE + RAM_SIZE && addr - ROM_BASE >= ROM_WINDOW) { mei_raise(m, MEI_FAULT_UNMAPPED, addr); return; }
        if (addr & 3) { mei_raise(m, MEI_FAULT_MISALIGNED, addr); return; }
        uint32_t hdr;
        list_word(m, addr, &hdr);
        uint32_t type = hdr >> 24;
        if ((type & 0xF0) == 0x20 && !draw_poly(m, addr, type)) return;
        addr = hdr & 0xFFFFFF;
    }
}

/* ---- error screen ---- */

#define RGB15(r, g, b) ((uint16_t)((r) | (g) << 5 | (b) << 10))

static void text(uint16_t *img, int x, int y, const char *s, uint16_t fg, int scale) {
    for (; *s; s++, x += 8 * scale) {
        const uint8_t *gl = font8x8_glyph((unsigned char)*s);
        for (int row = 0; row < 8 * scale; row++)
            for (int col = 0; col < 8 * scale; col++) {
                int px = x + col, py = y + row;
                if (px < 0 || px >= MEI_W || py < 0 || py >= MEI_H) continue;
                if (gl[row / scale] >> (col / scale) & 1) img[py * MEI_W + px] = fg;
            }
    }
}

/* Writes prefix then v as `digits` upper-case hex digits into buf. */
static const char *hexs(char *buf, const char *prefix, uint32_t v, int digits) {
    char *p = buf;
    while (*prefix) *p++ = *prefix++;
    for (int i = digits - 1; i >= 0; i--) *p++ = "0123456789ABCDEF"[(v >> (4 * i)) & 15];
    *p = 0;
    return buf;
}

void gpu_render_error_screen(Mei *m) {
    const uint16_t bg = RGB15(1, 2, 9), banner = RGB15(18, 2, 3);
    const uint16_t white = RGB15(31, 31, 31), yellow = RGB15(31, 28, 6), grey = RGB15(20, 21, 26);
    uint16_t *img = m->error_screen;
    for (int i = 0; i < MEI_W * MEI_H; i++) img[i] = i < MEI_W * 40 ? banner : bg;
    for (int x = 0; x < MEI_W; x++) img[40 * MEI_W + x] = yellow;

    char buf[48];
    text(img, (MEI_W - 17 * 16) / 2, 12, "MEI - CART HALTED", white, 2);
    text(img, 16, 52, mei_fault_name(m->fault.kind), yellow, 1);
    text(img, 16, 66, hexs(buf, "PC   0x", m->fault.pc, 8), white, 1);
    text(img, 16, 76, hexs(buf, "ADDR 0x", m->fault.addr, 8), white, 1);

    uint32_t pc = m->fault.pc, insn = 0;
    int ok = (pc & 3) == 0;
    if (ok && pc < RAM_BASE + RAM_SIZE) insn = rd32(m->ram + pc);
    else if (ok && pc - ROM_BASE < ROM_WINDOW) insn = rom_word(m, pc - ROM_BASE);
    else if (ok && pc - VRAM_BASE < VRAM_SIZE) insn = rd32(m->vram + (pc - VRAM_BASE));
    else ok = 0;
    text(img, 16, 86, ok ? hexs(buf, "INSN 0x", insn, 8) : "INSN --------", white, 1);

    text(img, 16, 102, "REGISTERS", grey, 1);
    for (int i = 0; i < 16; i++) {
        char lab[8] = "R    0x";          /* "R7   0x", "R12  0x" */
        if (i < 10) lab[1] = (char)('0' + i);
        else { lab[1] = '1'; lab[2] = (char)('0' + i - 10); }
        text(img, i < 8 ? 16 : 168, 114 + (i & 7) * 10, hexs(buf, lab, m->r[i], 8), white, 1);
    }

    /* the last debug output (an assert()'s report, say), wrapped at 36 columns: its last 3 rows */
    enum { COLS = 36, ROWS = 3 };
    char rows[16][COLS + 1];
    int nrows = 0;
    for (int l = 0; l < 4; l++) {
        const char *s = m->debug_tail[l];
        size_t len = strlen(s);
        for (size_t at = 0; at < len; at += COLS) {
            if (nrows == 16) { memmove(rows[0], rows[1], sizeof rows - sizeof rows[0]); nrows--; }
            size_t k = len - at < COLS ? len - at : COLS;
            memcpy(rows[nrows], s + at, k);
            rows[nrows][k] = 0;
            nrows++;
        }
    }
    if (nrows) {
        text(img, 16, 198, "OUTPUT", grey, 1);
        int first = nrows > ROWS ? nrows - ROWS : 0;
        for (int i = first; i < nrows; i++) text(img, 16, 208 + (i - first) * 10, rows[i], yellow, 1);
    }
}
