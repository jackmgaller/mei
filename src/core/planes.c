/* The plane chip (docs/PLANES.md): two tile planes (BG0, BG1), an affine plane (BG2), a
 * per-line backdrop, eight line channels that rewrite the registers for each line, colour
 * math and a colour offset, all composited with the polygon framebuffer at vsync.
 *
 * The compositor is a pure function of VRAM, the plane registers and the front buffer. It is
 * integer-only, and its output (pln_out) is host-side: nothing it produces is visible to the
 * CPU. The only VRAM it writes is auto-erase. */
#include "machine.h"

#include <string.h>

#define VMASK    (VRAM_SIZE - 1)   /* VRAM offsets: bits 0-20 (2 MB); addresses wrap within VRAM */
#define PAL_OFF  (PALETTE_ADDR - VRAM_BASE)
#define R(off)   ((off) / 4)

/* Layers, in the order of PLN_MATH's nibbles and offset bits (24 + layer). */
enum { L_BG0, L_BG1, L_BG2, L_PL, L_PH, L_BD };
/* Tie order, front to back: PH, PL, BG0, BG1, BG2. A candidate's key is priority * 8 + this. */
static const int tie_order[5] = {2, 1, 0, 3, 4};

static const int8_t dither_m[4][4] = {
    {-4, 0, -3, 1}, {2, -2, 3, -1}, {-3, 1, -4, 0}, {3, -1, 2, -2},
};

/* ---- registers ---- */

/* The register offsets that exist (the rest of 0x00-0xFF is reserved: Unmapped address). */
static int reg_ok(uint32_t off) {
    if ((off & 3) || off >= 0x100) return 0;
    switch (off) {
    case 0x1C: case 0x38: case 0x3C: case 0x58: case 0x5C: case 0x6C: return 0;
    }
    if (off >= 0x90 && off < PLN_LC) return 0;
    return off < PLN_LC + 8 * 8;
}

/* Where a line channel may write: every plane register except PLN_CTRL and the channels. */
static int target_ok(uint32_t off) { return off >= PLN_LAYERS && off <= PLN_BG2_DVY && reg_ok(off); }

void planes_reset(Mei *m) {
    memset(m->pln_reg, 0, sizeof m->pln_reg);
    m->pln_shown = 0;
}

int planes_io_read(Mei *m, uint32_t off, uint32_t *out) {
    if (!reg_ok(off)) return -1;
    *out = m->pln_reg[R(off)];
    return 0;
}

int planes_io_write(Mei *m, uint32_t off, uint32_t val) {
    if (!reg_ok(off)) return -1;
    m->pln_reg[R(off)] = val;
    return 0;
}

/* ---- sampling ---- */

typedef struct {
    const uint8_t *vram;
    uint32_t tiles, map;     /* VRAM offsets of the atlas page and the map */
    int mw, mh;              /* map size in tiles: 32, 64 or 128 */
    int tsh;                 /* log2 of the tile size: 3 (8x8) or 4 (16x16) */
    int eight;               /* 8-bit colour */
    uint32_t pal;            /* palette base */
} Plane;

static int map_dim(uint32_t code) { return 32 << (code > 2 ? 2 : code); }

static void plane_setup(Plane *p, const uint8_t *vram, const uint32_t *b) {
    uint32_t mode = b[R(PLN_BG_MODE)];
    p->vram = vram;
    p->tiles = b[R(PLN_BG_TILES)] & (VMASK & ~0x7FFFu);
    p->map = b[R(PLN_BG_MAP)] & (VMASK & ~0x7FFu);
    p->mw = map_dim(mode & 3);
    p->mh = map_dim((mode >> 2) & 3);
    p->tsh = (mode & 0x10) ? 4 : 3;
    p->eight = (mode >> 5) & 1;
    p->pal = (mode >> 8) & 0xFF;
}

static inline uint32_t map_entry(const Plane *p, uint32_t mx, uint32_t my) {
    return rd16(p->vram + ((p->map + (my * (uint32_t)p->mw + mx) * 2) & VMASK));
}

#if defined(__GNUC__) || defined(__clang__)
#define FORCE_INLINE inline __attribute__((always_inline))
#else
#define FORCE_INLINE inline
#endif

/* Texel (tx, ty) of the tile in map entry e: 0 where transparent (index 0), otherwise
 * bit 31 set, bit 16 = the entry's priority bit, bits 0-14 the palette colour. TSH (log2 of
 * the tile size) and EIGHT are constants in each caller, so each combination is specialised. */
static FORCE_INLINE uint32_t texel(const Plane *p, uint32_t e, uint32_t tx, uint32_t ty, const int TSH, const int EIGHT) {
    const uint32_t last = (1u << TSH) - 1;
    tx ^= (0u - ((e >> 14) & 1)) & last;        /* flips: last - t == t ^ last */
    ty ^= (0u - ((e >> 15) & 1)) & last;
    uint32_t t = e & 0x3FF, cu, cv, idx, ci, pp = (e >> 10) & 7;
    if (TSH == 3) { cu = (t & 31) * 8 + tx; cv = (t >> 5) * 8 + ty; }
    else { cu = (t & 15) * 16 + tx; cv = ((t >> 4) & 15) * 16 + ty; }
    if (EIGHT) {
        idx = p->vram[(p->tiles + cv * 256 + cu) & VMASK];
        ci = ((p->pal + pp) & 15) * 256 + idx;
    } else {
        uint32_t byte = p->vram[(p->tiles + cv * 128 + (cu >> 1)) & VMASK];
        idx = (byte >> ((cu & 1) * 4)) & 15;
        ci = ((p->pal + pp) & 255) * 16 + idx;
    }
    uint32_t c = 0x80000000u | ((e >> 13) & 1) << 16 | (rd16(p->vram + PAL_OFF + ci * 2) & 0x7FFFu);
    return idx ? c : 0;
}

/* A tile plane's pixels x0..x1-1 on line y: one map entry per tile crossed. */
static FORCE_INLINE void tile_line_g(const Plane *p, uint32_t scroll, int y, int x0, int x1, uint32_t *out,
                                     const int TSH, const int EIGHT) {
    const uint32_t ts = 1u << TSH, last = ts - 1;
    const uint8_t *pal = p->vram + PAL_OFF;
    uint32_t wmask = ((uint32_t)p->mw << TSH) - 1, hmask = ((uint32_t)p->mh << TSH) - 1;
    uint32_t py = ((uint32_t)y + (scroll >> 16)) & hmask, my = py >> TSH, ty = py & last;
    int x = x0;
    while (x < x1) {
        uint32_t px = ((uint32_t)x + (scroll & 0xFFFF)) & wmask, tx = px & last;
        uint32_t e = map_entry(p, px >> TSH, my);
        int n = (int)(ts - tx);
        if (n > x1 - x) n = x1 - x;
        /* the tile's row: the same for every pixel of this run */
        uint32_t fx = (0u - ((e >> 14) & 1)) & last, fy = (0u - ((e >> 15) & 1)) & last;
        uint32_t t = e & 0x3FF, pp = (e >> 10) & 7;
        uint32_t cu0 = TSH == 3 ? (t & 31) * 8 : (t & 15) * 16;
        uint32_t cv = (TSH == 3 ? (t >> 5) * 8 : ((t >> 4) & 15) * 16) + (ty ^ fy);
        uint32_t row = p->tiles + cv * (EIGHT ? 256 : 128);
        uint32_t base = EIGHT ? ((p->pal + pp) & 15) * 256 : ((p->pal + pp) & 255) * 16;
        uint32_t hi = 0x80000000u | ((e >> 13) & 1) << 16;
        for (int k = 0; k < n; k++) {
            uint32_t cu = cu0 + ((tx + (uint32_t)k) ^ fx), idx;
            if (EIGHT) idx = p->vram[(row + cu) & VMASK];
            else idx = (p->vram[(row + (cu >> 1)) & VMASK] >> ((cu & 1) * 4)) & 15;
            uint32_t c = hi | (rd16(pal + (base + idx) * 2) & 0x7FFFu);
            out[x + k] = idx ? c : 0;
        }
        x += n;
    }
}

/* floor(v / 65536) without relying on >> of a negative value. */
static FORCE_INLINE int64_t floor16(int64_t v) { return v >= 0 ? v >> 16 : ~((~v) >> 16); }

/* The affine plane's pixels x0..x1-1 on line y. W holds the line's registers. */
static FORCE_INLINE void affine_line_g(const Plane *p, const uint32_t *W, int outside, int y, int x0, int x1,
                                       uint32_t *out, const int TSH, const int EIGHT) {
    int64_t dux = (int32_t)W[R(PLN_BG2_DUX)], dvx = (int32_t)W[R(PLN_BG2_DVX)];
    int64_t u = (int64_t)(int32_t)W[R(PLN_BG2_U0)] + (int64_t)y * (int32_t)W[R(PLN_BG2_DUY)] + (int64_t)x0 * dux;
    int64_t v = (int64_t)(int32_t)W[R(PLN_BG2_V0)] + (int64_t)y * (int32_t)W[R(PLN_BG2_DVY)] + (int64_t)x0 * dvx;
    const uint64_t wpx = (uint64_t)p->mw << TSH, hpx = (uint64_t)p->mh << TSH;
    const uint32_t last = (1u << TSH) - 1;
    for (int x = x0; x < x1; x++, u += dux, v += dvx) {
        uint64_t tu = (uint64_t)floor16(u), tv = (uint64_t)floor16(v);
        if (tu >= wpx || tv >= hpx) {            /* (negative values are huge unsigned) */
            if (outside == 2) {                  /* tile 0, as if the entry were 0x0000 */
                out[x] = texel(p, 0, (uint32_t)tu & last, (uint32_t)tv & last, TSH, EIGHT);
                continue;
            }
            if (outside != 0) { out[x] = 0; continue; }   /* 1, 3: transparent */
            tu &= wpx - 1;
            tv &= hpx - 1;
        }
        uint32_t e = map_entry(p, (uint32_t)tu >> TSH, (uint32_t)tv >> TSH);
        out[x] = texel(p, e, (uint32_t)tu & last, (uint32_t)tv & last, TSH, EIGHT);
    }
}

static void tile_line(const Plane *p, uint32_t scroll, int y, int x0, int x1, uint32_t *out) {
    switch ((p->tsh == 4) << 1 | p->eight) {
    case 0: tile_line_g(p, scroll, y, x0, x1, out, 3, 0); break;
    case 1: tile_line_g(p, scroll, y, x0, x1, out, 3, 1); break;
    case 2: tile_line_g(p, scroll, y, x0, x1, out, 4, 0); break;
    default: tile_line_g(p, scroll, y, x0, x1, out, 4, 1); break;
    }
}

static void affine_line(const Plane *p, const uint32_t *W, int outside, int y, int x0, int x1, uint32_t *out) {
    switch ((p->tsh == 4) << 1 | p->eight) {
    case 0: affine_line_g(p, W, outside, y, x0, x1, out, 3, 0); break;
    case 1: affine_line_g(p, W, outside, y, x0, x1, out, 3, 1); break;
    case 2: affine_line_g(p, W, outside, y, x0, x1, out, 4, 0); break;
    default: affine_line_g(p, W, outside, y, x0, x1, out, 4, 1); break;
    }
}

/* ---- colour ---- */

static inline int clamp31(int v) { return v < 0 ? 0 : v > 31 ? 31 : v; }

/* The GPU's blend modes on 5-bit channels: b is the layer below, a the layer on top. */
static inline uint32_t blend(uint32_t b, uint32_t a, uint32_t mode) {
    int br = b & 31, bg = (b >> 5) & 31, bb = (b >> 10) & 31;
    int ar = a & 31, ag = (a >> 5) & 31, ab = (a >> 10) & 31, r, g, bl;
    switch (mode) {
    case 0: r = (br + ar) >> 1; g = (bg + ag) >> 1; bl = (bb + ab) >> 1; break;
    case 1: r = clamp31(br + ar); g = clamp31(bg + ag); bl = clamp31(bb + ab); break;
    case 2: r = clamp31(br - ar); g = clamp31(bg - ag); bl = clamp31(bb - ab); break;
    default: r = clamp31(br + (ar >> 2)); g = clamp31(bg + (ag >> 2)); bl = clamp31(bb + (ab >> 2)); break;
    }
    return (uint32_t)(r | g << 5 | bl << 10);
}

static inline uint32_t offset(uint32_t c, uint32_t ofs) {
    int r = clamp31((int)(c & 31) + (int8_t)(ofs & 0xFF));
    int g = clamp31((int)((c >> 5) & 31) + (int8_t)((ofs >> 8) & 0xFF));
    int b = clamp31((int)((c >> 10) & 31) + (int8_t)((ofs >> 16) & 0xFF));
    return (uint32_t)(r | g << 5 | b << 10);
}

/* ---- composing ---- */

/* The backdrop colour bd (8 bits a channel) reduced to 15 bits at x mod 4 = 0..3 on line y,
 * dithered if dith. */
static void bd_reduce(uint32_t bd, int dith, int y, uint32_t bd4[4]) {
    for (int i = 0; i < 4; i++) {
        int o = dith ? dither_m[y & 3][i] : 0, c[3];
        for (int k = 0; k < 3; k++) {
            int v = (int)((bd >> (8 * k)) & 0xFF) + o;
            c[k] = (v < 0 ? 0 : v > 255 ? 255 : v) >> 3;
        }
        bd4[i] = (uint32_t)(c[0] | c[1] << 5 | c[2] << 10);
    }
}

/* The registers for line y: the CPU's values, then line channels 0-7 in order. */
static void line_regs(const Mei *m, int y, uint32_t *W) {
    memcpy(W, m->pln_reg, sizeof m->pln_reg);
    for (int ch = 0; ch < 8; ch++) {
        uint32_t ctrl = m->pln_reg[R(PLN_LC + 8 * ch + 4)];
        if (!(ctrl & 0x8000)) continue;
        uint32_t addr = m->pln_reg[R(PLN_LC + 8 * ch)] & (VMASK & ~3u), target = ctrl & 0xFC;
        uint32_t n = ((ctrl >> 8) & 3) + 1;
        for (uint32_t k = 0; k < n; k++) {
            uint32_t off = target + 4 * k;
            if (!target_ok(off)) continue;
            W[R(off)] = rd32(m->vram + ((addr + ((uint32_t)y * n + k) * 4) & VMASK));
        }
    }
}

/* Is line y inside plane n's window? Sets the window's columns [*x0, *x1). */
static int window(const uint32_t *b, int y, int *x0, int *x1) {
    uint32_t wx = b[R(PLN_BG_WINX)], wy = b[R(PLN_BG_WINY)];
    int top = (int)(wy & 0xFF), bottom = (int)((wy >> 8) & 0xFF);
    if (y < top || y >= MEI_H - bottom) return 0;
    *x0 = (int)(wx & 0x1FF);
    *x1 = MEI_W - (int)((wx >> 16) & 0x1FF);
    if (*x1 > MEI_W) *x1 = MEI_W;
    return *x0 < *x1;
}

/* The top of the layer stack at one pixel (as compose() picks it, by key), from the
 * candidates whose key is below cut: the
 * polygon pixel (key kp < 0: none) and the planes' pixels c[n] (0: transparent or outside).
 * Returns the colour before the colour offset and sets *la to the top layer (L_BD: none). */
static FORCE_INLINE uint32_t stack_px(int kp, uint32_t fp, int lp, const uint32_t *c, const int *klo,
                                      const int *khi, uint32_t math, uint32_t bd, int cut, int *la) {
    int ka = -1, kb = -1;
    uint32_t ca = 0, cb = 0;
    *la = L_BD;
#define CAND(key, col, layer) do { \
        if ((key) > ka) { kb = ka; cb = ca; ka = (key); ca = (col); *la = (layer); } \
        else if ((key) > kb) { kb = (key); cb = (col); } } while (0)
    if (kp >= 0 && kp < cut) CAND(kp, fp, lp);
    for (int n = 0; n < 3; n++) {
        if (!c[n]) continue;
        int k = (c[n] & 0x10000) ? khi[n] : klo[n];
        if (k < cut) CAND(k, c[n] & 0x7FFF, n);
    }
#undef CAND
    if (ka < 0) return bd;
    uint32_t mm = (math >> (4 * *la)) & 15;
    return (mm & 4) ? blend(kb < 0 ? bd : cb, ca, mm & 3) : ca;
}

/* Rev 2. A blended polygon pixel over a hole, or an upper one over a lower pixel f, blends with
 * the composite of the layers behind its own layer (PL or PH) at (x, y): the planes and the
 * backdrop, and for an upper packet the lower pixel, with their colour math but not the colour
 * offset. Registers, line tables, maps and atlases are read as they stand when the GPU draws. */
uint32_t planes_under(PlnUnder *u, int x, uint32_t f, int upper) {
    const uint32_t *W = u->W;
    if (!u->ready) {
        u->ready = 1;
        line_regs(u->m, u->y, u->W);
        uint32_t layers = W[R(PLN_LAYERS)], prio = W[R(PLN_PRIO)];
        for (int n = 0; n < 3; n++) u->on[n] = (layers >> n & 1) != 0;
        u->kpl = (int)((prio >> 24) & 15) * 8 + tie_order[L_PL];
        u->kph = (int)((prio >> 28) & 15) * 8 + tie_order[L_PH];
        bd_reduce(W[R(PLN_BD_COLOR)], (W[R(PLN_CTRL)] >> 2) & 1, u->y, u->bd4);
    }
    uint32_t prio = W[R(PLN_PRIO)], c[3] = {0, 0, 0};
    int klo[3], khi[3];
    for (int n = 0; n < 3; n++) {
        klo[n] = (int)((prio >> (8 * n)) & 15) * 8 + tie_order[n];
        khi[n] = (int)((prio >> (8 * n + 4)) & 15) * 8 + tie_order[n];
        const uint32_t *b = W + R(PLN_BG0 + 0x20 * n);
        int x0, x1;
        if (!u->on[n] || !window(b, u->y, &x0, &x1) || x < x0 || x >= x1) continue;
        Plane p;
        plane_setup(&p, u->m->vram, b);
        u->buf[x] = 0;
        if (n < 2) tile_line(&p, b[R(PLN_BG_SCROLL)], u->y, x, x + 1, u->buf);
        else affine_line(&p, W, (int)((b[R(PLN_BG_MODE)] >> 16) & 3), u->y, x, x + 1, u->buf);
        c[n] = u->buf[x];
    }
    int la, kp = f == PLN_HOLE ? -1 : u->kpl;
    return stack_px(kp, f & 0x7FFF, L_PL, c, klo, khi, W[R(PLN_MATH)], u->bd4[x & 3],
                    upper ? u->kph : u->kpl, &la);
}

static void compose(Mei *m) {
    const uint16_t *front = gpu_front(m);
    uint32_t W[64], buf[3][MEI_W];
    for (int y = 0; y < MEI_H; y++) {
        line_regs(m, y, W);
        uint32_t layers = W[R(PLN_LAYERS)], prio = W[R(PLN_PRIO)], math = W[R(PLN_MATH)], ofs = W[R(PLN_OFS)];

        /* backdrop: 8 bits per channel reduced to 5, dithered by x mod 4 if PLN_CTRL bit 2 */
        uint32_t bd4[4];
        bd_reduce(W[R(PLN_BD_COLOR)], (W[R(PLN_CTRL)] >> 2) & 1, y, bd4);

        /* the planes' pixels on this line (0: transparent or outside the window) */
        int on[3], klo[3], khi[3];
        for (int n = 0; n < 3; n++) {
            const uint32_t *b = W + R(PLN_BG0 + 0x20 * n);
            int x0, x1;
            on[n] = (layers >> n & 1) && window(b, y, &x0, &x1);
            if (!on[n]) continue;
            klo[n] = (int)((prio >> (8 * n)) & 15) * 8 + tie_order[n];
            khi[n] = (int)((prio >> (8 * n + 4)) & 15) * 8 + tie_order[n];
            Plane p;
            plane_setup(&p, m->vram, b);
            memset(buf[n], 0, sizeof buf[n]);
            if (n < 2) tile_line(&p, b[R(PLN_BG_SCROLL)], y, x0, x1, buf[n]);
            else affine_line(&p, W, (int)((b[R(PLN_BG_MODE)] >> 16) & 3), y, x0, x1, buf[n]);
        }
        int polys = !(layers & 8);
        int kpl = (int)((prio >> 24) & 15) * 8 + tie_order[L_PL];
        int kph = (int)((prio >> 28) & 15) * 8 + tie_order[L_PH];

        const uint16_t *src = front + y * MEI_W;
        uint16_t *dst = m->pln_out + y * MEI_W;
        for (int x = 0; x < MEI_W; x++) {
            int ka = -1, kb = -1, la = L_BD;
            uint32_t ca = 0, cb = 0;
#define CAND(key, col, layer) do { \
                if ((key) > ka) { kb = ka; cb = ca; ka = (key); ca = (col); la = (layer); } \
                else if ((key) > kb) { kb = (key); cb = (col); } } while (0)
            if (polys) {
                uint32_t f = src[x];
                if (f != PLN_HOLE) {
                    if (f & 0x8000) CAND(kph, f & 0x7FFF, L_PH);
                    else CAND(kpl, f, L_PL);
                }
            }
            for (int n = 0; n < 3; n++) {
                if (!on[n]) continue;
                uint32_t c = buf[n][x];
                if (c) CAND((c & 0x10000) ? khi[n] : klo[n], c & 0x7FFF, n);
            }
#undef CAND
            uint32_t out;
            if (ka < 0) out = bd4[x & 3];
            else {
                out = ca;
                uint32_t mm = (math >> (4 * la)) & 15;
                if (mm & 4) out = blend(kb < 0 ? bd4[x & 3] : cb, ca, mm & 3);
            }
            if ((math >> (24 + la)) & 1) out = offset(out, ofs);
            dst[x] = (uint16_t)out;
        }
    }
}

void planes_vsync(Mei *m) {
    uint32_t ctrl = m->pln_reg[R(PLN_CTRL)];
    m->pln_shown = ctrl & 1;
    if (ctrl & 1) compose(m);
    if (ctrl & 2) {
        uint8_t *fb = m->vram + (gpu_back_addr(m) - VRAM_BASE);
        uint32_t c = m->pln_reg[R(PLN_ERASE)] & 0xFFFF;
        for (int i = 0; i < MEI_W * MEI_H; i++) wr16(fb + 2 * i, c);
    }
}
