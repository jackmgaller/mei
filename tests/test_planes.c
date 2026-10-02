/* Plane chip tests (docs/PLANES.md): registers, holes and the priority bit, auto-erase, the
 * backdrop, tile planes (scroll, wrap, flips, palettes, tile sizes, depths, windows), the affine
 * plane (outside modes, 64-bit sums, a Mode 7 perspective table), line channels, priorities,
 * colour math and the colour offset. Hand-worked pixels, plus whole frames against a literal
 * per-pixel transcription of the normative algorithm. */
#include "machine.h"
#include "asm.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static int checks, fails;
#define CHECK(c) do { checks++; if (!(c)) { fails++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)
#define CHECK_EQ(a, b) do { long long a_ = (long long)(a), b_ = (long long)(b); checks++; \
    if (a_ != b_) { fails++; printf("FAIL %s:%d: %s == %lld (0x%llX), expected %lld (0x%llX)\n", __FILE__, __LINE__, #a, a_, a_, b_, b_); } } while (0)

static Mei *m;

static void setup(void) {
    mei_reset(m);
    memset(&m->fault, 0, sizeof m->fault);   /* mei_reset with no cart raises NO_CART */
}

static uint8_t *V(uint32_t addr) { return m->vram + (addr - VRAM_BASE); }
static void pal(int i, uint16_t c) { wr16(V(PALETTE_ADDR) + i * 2, c); }
/* Palette colour i = i: a composited pixel then names the palette entry it came from. */
static void pal_identity(void) { for (int i = 0; i < 4096; i++) pal(i, (uint16_t)(i & 0x7FFF)); }
static uint16_t C15(int r, int g, int b) { return (uint16_t)(r | g << 5 | b << 10); }

static void reg(uint32_t off, uint32_t v) { CHECK_EQ(bus_write32(m, 0xFF0700 + off, v), 0); }
static uint32_t rreg(uint32_t off) { uint32_t v = 0xDEADBEEF; CHECK_EQ(bus_read32(m, 0xFF0700 + off, &v), 0); return v; }
static uint32_t BG(int n, uint32_t r) { return PLN_BG0 + 0x20 * (uint32_t)n + r; }

static uint8_t *back(void) { return V(gpu_back_addr(m)); }
static void back_fill(uint16_t c) { for (int i = 0; i < MEI_W * MEI_H; i++) wr16(back() + 2 * i, c); }
static void back_px(int x, int y, uint16_t c) { wr16(back() + 2 * (y * MEI_W + x), c); }
static uint16_t back_get(int x, int y) { return rd16(back() + 2 * (y * MEI_W + x)); }

/* vsync as mei_run_frame does it: swap, compose, auto-erase. */
static const uint16_t *flip(void) {
    gpu_vsync(m);
    planes_vsync(m);
    return mei_display(m);
}

/* Composes the back buffer and makes it the back buffer again, so a test can change it and
 * compose it again. */
static const uint16_t *present(void) {
    const uint16_t *d = flip();
    m->back ^= 1;
    return d;
}

/* ---- packets (as in test_gpu.c) ---- */

static uint32_t pk_next, pk_prev, pk_first;
static void list_begin(void) { pk_next = 0x1000; pk_prev = 0; pk_first = 0xFFFFFF; }
static void emit(uint32_t type, int n, ...) {
    uint32_t a = pk_next;
    wr32(m->ram + a, type << 24 | 0xFFFFFF);
    va_list ap;
    va_start(ap, n);
    for (int i = 0; i < n; i++) wr32(m->ram + a + 4 + 4 * i, va_arg(ap, uint32_t));
    va_end(ap);
    if (pk_prev) wr32(m->ram + pk_prev, (rd32(m->ram + pk_prev) & 0xFF000000u) | a);
    else pk_first = a;
    pk_prev = a;
    pk_next += 4 * (uint32_t)(n + 1);
}
static void list_draw(void) { gpu_draw_list(m, pk_first); }
static uint32_t P(int x, int y) { return (uint32_t)(uint16_t)x | (uint32_t)(uint16_t)y << 16; }
static uint32_t RGB(int r, int g, int b) { return (uint32_t)r | (uint32_t)g << 8 | (uint32_t)b << 16; }
#define UPPER (1u << 26)
/* A flat quad covering x0..x1-1, y0..y1-1 (type 0x24 + 8 if semi-transparent). */
static void quad(int x0, int y0, int x1, int y1, uint32_t col, int semi) {
    emit(semi ? 0x2C : 0x24, 5, col, P(x0, y0), P(x1, y0), P(x0, y1), P(x1, y1));
}

static uint32_t rng = 12345;
static uint32_t rnd32(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }
static int rnd(int lo, int hi) { return lo + (int)(rnd32() % (uint32_t)(hi - lo + 1)); }

/* ---- the layout used by most tests ---- */

#define ATLAS4   0x460000u   /* page 12: a 4-bit atlas */
#define ATLAS8   0x480000u   /* texture slots 0-1: an 8-bit atlas */
#define MAP0     0x450000u
#define MAP1     0x452000u
#define MAP2     0x458000u
#define TABLES   0x44E000u

/* Writes texel (cu, cv) of a 4-bit atlas. */
static void atlas4_set(uint32_t page, int cu, int cv, int idx) {
    uint8_t *b = V(page) + cv * 128 + cu / 2;
    *b = (cu & 1) ? (uint8_t)((*b & 0x0F) | idx << 4) : (uint8_t)((*b & 0xF0) | idx);
}
/* Fills 8x8 tile t of a 4-bit atlas with f(tx, ty). */
static void tile4(uint32_t page, int t, int (*f)(int, int)) {
    for (int ty = 0; ty < 8; ty++)
        for (int tx = 0; tx < 8; tx++) atlas4_set(page, (t % 32) * 8 + tx, (t / 32) * 8 + ty, f(tx, ty));
}
static int pat_a(int tx, int ty) { return (tx + 2 * ty) % 15 + 1; }        /* never transparent */
static int pat_solid(int tx, int ty) { return 9; }
static int pat_hole(int tx, int ty) { return (tx == 3 && ty == 4) ? 0 : 5; }
static void map_set(uint32_t map, int w, int mx, int my, uint16_t e) { wr16(V(map) + (my * w + mx) * 2, e); }

/* ================================================================ registers */

static void test_registers(void) {
    setup();
    static const uint32_t valid[] = {
        0x00, 0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x20, 0x24, 0x28, 0x2C, 0x30, 0x34,
        0x40, 0x44, 0x48, 0x4C, 0x50, 0x54, 0x60, 0x64, 0x68, 0x70, 0x74, 0x78, 0x7C,
        0x80, 0x84, 0x88, 0x8C, 0xA0, 0xA4, 0xA8, 0xD8, 0xDC,
    };
    for (size_t i = 0; i < sizeof valid / sizeof *valid; i++) {
        CHECK_EQ(rreg(valid[i]), 0);
        reg(valid[i], 0xA5000000u | valid[i] << 8 | 0x5A);
    }
    for (size_t i = 0; i < sizeof valid / sizeof *valid; i++) CHECK_EQ(rreg(valid[i]), 0xA5000000u | valid[i] << 8 | 0x5A);
    static const uint32_t reserved[] = {0x1C, 0x38, 0x3C, 0x58, 0x5C, 0x6C, 0x90, 0x94, 0x9C, 0xE0, 0xF0, 0xFC};
    for (size_t i = 0; i < sizeof reserved / sizeof *reserved; i++) {
        uint32_t v;
        memset(&m->fault, 0, sizeof m->fault);
        CHECK_EQ(bus_read32(m, 0xFF0700 + reserved[i], &v), -1);
        CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
        memset(&m->fault, 0, sizeof m->fault);
        CHECK_EQ(bus_write32(m, 0xFF0700 + reserved[i], 1), -1);
        CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    }
    uint32_t v;
    memset(&m->fault, 0, sizeof m->fault);
    CHECK_EQ(bus_read8(m, 0xFF0700, &v, 0), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_IO_WIDTH);
    memset(&m->fault, 0, sizeof m->fault);
    CHECK_EQ(bus_write16(m, 0xFF0714, 1), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_IO_WIDTH);
    memset(&m->fault, 0, sizeof m->fault);
    CHECK_EQ(bus_read32(m, 0xFF0800, &v), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    memset(&m->fault, 0, sizeof m->fault);
    CHECK_EQ(bus_read32(m, 0xFF0600, &v), -1);    /* the broadcast decoder's range: not here */
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    setup();
    for (size_t i = 0; i < sizeof valid / sizeof *valid; i++) CHECK_EQ(rreg(valid[i]), 0);
    CHECK_EQ(m->pln_shown, 0);
}

/* ================================================================ off by default */

static void test_off(void) {
    setup();
    m->gpu_ctrl = 0;
    list_begin();
    quad(0, 0, 10, 10, RGB(255, 0, 0) | UPPER, 0);
    quad(10, 0, 20, 10, RGB(0, 0, 0) | UPPER, 0);
    list_draw();
    CHECK_EQ(back_get(5, 5), 31);              /* bit 26 ignored: bit 15 clear */
    CHECK_EQ(back_get(15, 5), 0);              /* black is not rewritten */
    gpu_clear(m, 0xFFFF);
    CHECK_EQ(back_get(0, 0), 0x7FFF);          /* GPU_CLEAR writes 15 bits */
    gpu_clear(m, 0x8000);
    CHECK_EQ(back_get(0, 0), 0);
    const uint16_t *d = flip();
    CHECK(d == gpu_front(m));
    CHECK_EQ(m->pln_shown, 0);
    /* auto-erase is its own bit: with the compositor off it still erases, and shows the front */
    reg(PLN_CTRL, 2);
    reg(PLN_ERASE, 0xFFFF1234u);
    back_fill(7);
    d = flip();
    CHECK(d == gpu_front(m));
    CHECK_EQ(d[100], 7);
    CHECK_EQ(back_get(3, 3), 0x1234);
    CHECK_EQ(back_get(319, 239), 0x1234);
}

/* ================================================================ holes and the priority bit */

static void test_holes(void) {
    setup();
    reg(PLN_CTRL, 1);
    m->gpu_ctrl = 0;
    gpu_clear(m, 0x8000);
    CHECK_EQ(back_get(0, 0), 0x8000);          /* 16 bits: the whole buffer is holes */
    gpu_clear(m, 0xFFFF);
    CHECK_EQ(back_get(0, 0), 0xFFFF);
    gpu_clear(m, 0x8000);
    list_begin();
    quad(0, 0, 10, 10, RGB(255, 0, 0) | UPPER, 0);
    quad(10, 0, 20, 10, RGB(0, 0, 0) | UPPER, 0);       /* upper black -> 0x8400 */
    quad(20, 0, 30, 10, RGB(0, 0, 0), 0);               /* lower black stays 0 */
    quad(30, 0, 40, 10, RGB(0, 255, 0), 0);
    quad(40, 0, 50, 10, RGB(80, 80, 80) | 1u << 24 | UPPER, 1);   /* additive, upper, over a hole */
    quad(50, 0, 60, 10, RGB(80, 80, 80) | 1u << 24, 1);           /* additive, lower, over a hole */
    quad(0, 20, 10, 30, RGB(255, 255, 255) | UPPER, 0);
    quad(0, 20, 10, 30, RGB(64, 64, 64) | 2u << 24, 1);           /* subtract, lower, over upper white */
    quad(20, 20, 30, 30, RGB(0, 0, 255), 0);
    quad(20, 20, 30, 30, RGB(8, 8, 0) | 1u << 24 | UPPER, 1);     /* upper add over lower blue */
    list_draw();
    CHECK_EQ(back_get(5, 5), 0x8000 | 31);
    CHECK_EQ(back_get(15, 5), 0x8400);
    CHECK_EQ(back_get(25, 5), 0x0000);
    CHECK_EQ(back_get(35, 5), 31 << 5);
    CHECK_EQ(back_get(45, 5), 0x8000 | C15(10, 10, 10));   /* blends with the hole's black */
    CHECK_EQ(back_get(55, 5), C15(10, 10, 10));
    CHECK_EQ(back_get(5, 25), C15(23, 23, 23));             /* blending reads bits 0-14 only */
    CHECK_EQ(back_get(25, 25), 0x8000 | C15(1, 1, 31));
    CHECK_EQ(back_get(100, 100), 0x8000);
    /* no packet ever writes 0x8000: an upper subtract down to black also becomes 0x8400 */
    list_begin();
    quad(60, 0, 70, 10, RGB(255, 255, 255) | 2u << 24 | UPPER, 1);
    list_draw();
    CHECK_EQ(back_get(65, 5), 0x8400);
    /* turning the compositor off again: bit 26 is ignored */
    reg(PLN_CTRL, 0);
    list_begin();
    quad(70, 0, 80, 10, RGB(0, 0, 0) | UPPER, 0);
    list_draw();
    CHECK_EQ(back_get(75, 5), 0);
}

static void test_auto_erase(void) {
    setup();
    reg(PLN_CTRL, 3);
    reg(PLN_ERASE, 0x8000);
    back_fill(0x1234);
    flip();
    CHECK_EQ(gpu_front(m)[0], 0x1234);
    for (int i = 0; i < MEI_W * MEI_H; i += 997) CHECK_EQ(rd16(back() + 2 * i), 0x8000);
    CHECK_EQ(back_get(319, 239), 0x8000);
    /* the other buffer is erased at the next vsync, after it was composed */
    reg(PLN_ERASE, 0x8000);
    back_px(1, 1, 0x7C00);
    const uint16_t *d = flip();
    CHECK_EQ(d[1 * MEI_W + 1], 0x7C00);
    CHECK_EQ(back_get(1, 1), 0x8000);
}

/* ================================================================ backdrop and the polygon layer */

static void test_backdrop(void) {
    setup();
    reg(PLN_CTRL, 1);
    reg(PLN_BD_COLOR, 0xEEFF8043u);            /* bits 24-31 ignored */
    back_fill(0x8000);
    const uint16_t *d = present();
    CHECK(d == m->pln_out);
    CHECK_EQ(m->pln_shown, 1);
    for (int i = 0; i < MEI_W * MEI_H; i += 37) CHECK_EQ(d[i], C15(0x43 >> 3, 0x80 >> 3, 0xFF >> 3));
    static const int dm[4][4] = {{-4, 0, -3, 1}, {2, -2, 3, -1}, {-3, 1, -4, 0}, {3, -1, 2, -2}};
    reg(PLN_CTRL, 5);
    reg(PLN_BD_COLOR, 0x0002FDA4u);
    back_fill(0x8000);
    d = present();
    int bad = 0;
    for (int y = 0; y < MEI_H; y++)
        for (int x = 0; x < MEI_W; x++) {
            int o = dm[y & 3][x & 3], c[3] = {0xA4, 0xFD, 0x02};
            for (int k = 0; k < 3; k++) { c[k] += o; c[k] = (c[k] < 0 ? 0 : c[k] > 255 ? 255 : c[k]) >> 3; }
            bad += d[y * MEI_W + x] != C15(c[0], c[1], c[2]);
        }
    CHECK_EQ(bad, 0);
    CHECK_EQ(d[0], C15((0xA4 - 4) >> 3, (0xFD - 4) >> 3, 0));
    CHECK_EQ(d[3 + 3 * MEI_W], C15((0xA4 - 2) >> 3, 31, 0));
    CHECK_EQ(d[2 + 1 * MEI_W], C15((0xA4 + 3) >> 3, 31, 0));   /* 0xFD + 3 clamps to 255 */

    /* polygon pixels, holes, and the layer hidden */
    reg(PLN_CTRL, 1);
    reg(PLN_BD_COLOR, 0x080808);
    back_fill(0x8000);
    back_px(5, 5, 0x1234);
    back_px(6, 5, 0x9234);
    back_px(7, 5, 0x0000);
    back_px(8, 5, 0x8400);
    d = present();
    CHECK_EQ(d[5 * MEI_W + 5], 0x1234);
    CHECK_EQ(d[5 * MEI_W + 6], 0x1234);
    CHECK_EQ(d[5 * MEI_W + 7], 0x0000);
    CHECK_EQ(d[5 * MEI_W + 8], 0x0400);
    CHECK_EQ(d[5 * MEI_W + 9], C15(1, 1, 1));
    reg(PLN_LAYERS, 8);
    back_fill(0x1234);
    d = present();
    CHECK_EQ(d[100], C15(1, 1, 1));
}

/* ================================================================ tile planes */

static void test_tile_plane(void) {
    setup();
    pal_identity();
    tile4(ATLAS4, 1, pat_a);
    tile4(ATLAS4, 37, pat_a);       /* column 5, row 1 */
    reg(PLN_CTRL, 1);
    reg(PLN_LAYERS, 1);
    reg(BG(0, PLN_BG_MODE), 2 << 8);                 /* 32x32, 8x8, 4-bit, palette base 2 */
    reg(BG(0, PLN_BG_TILES), ATLAS4);
    reg(BG(0, PLN_BG_MAP), MAP0);
    reg(PLN_BD_COLOR, 0xF8F8F8);                     /* backdrop: 0x7FFF */
    map_set(MAP0, 32, 0, 0, 1);
    map_set(MAP0, 32, 1, 0, 1 | 0x4000);             /* flip x */
    map_set(MAP0, 32, 2, 0, 1 | 0x8000);             /* flip y */
    map_set(MAP0, 32, 3, 0, 1 | 0xC000);             /* both */
    map_set(MAP0, 32, 4, 0, 1 | 3 << 10);            /* palette 3 */
    map_set(MAP0, 32, 5, 0, 37 | 0x400);             /* tile 37, palette 1 */
    map_set(MAP0, 32, 31, 31, 1);                    /* the far corner */
    back_fill(0x8000);
    const uint16_t *d = present();
    int bad = 0;
    for (int ty = 0; ty < 8; ty++)
        for (int tx = 0; tx < 8; tx++) {
            bad += d[ty * MEI_W + tx] != 32 + pat_a(tx, ty);
            bad += d[ty * MEI_W + 8 + tx] != 32 + pat_a(7 - tx, ty);
            bad += d[ty * MEI_W + 16 + tx] != 32 + pat_a(tx, 7 - ty);
            bad += d[ty * MEI_W + 24 + tx] != 32 + pat_a(7 - tx, 7 - ty);
            bad += d[ty * MEI_W + 32 + tx] != 80 + pat_a(tx, ty);
            bad += d[ty * MEI_W + 40 + tx] != 48 + pat_a(tx, ty);
        }
    CHECK_EQ(bad, 0);
    CHECK_EQ(d[0], 33);
    CHECK_EQ(d[8 + 7], 33);
    CHECK_EQ(d[8 * MEI_W], 0x7FFF);                  /* tile 0 is blank: transparent */
    CHECK_EQ(d[48], 0x7FFF);

    /* palette base wraps: 255 + 3 = 2 (mod 256) */
    reg(BG(0, PLN_BG_MODE), 255 << 8);
    d = present();
    CHECK_EQ(d[32], 32 + pat_a(0, 0));
    CHECK_EQ(d[0], 255 * 16 + pat_a(0, 0));

    /* scrolling: screen (x, y) shows plane ((x + sx) mod 256, (y + sy) mod 256) */
    reg(BG(0, PLN_BG_MODE), 2 << 8);
    reg(BG(0, PLN_BG_SCROLL), 3 | 2u << 16);
    d = present();
    CHECK_EQ(d[0], 32 + pat_a(3, 2));
    CHECK_EQ(d[5 * MEI_W + 4], 32 + pat_a(7, 7));
    CHECK_EQ(d[5 * MEI_W + 5], 32 + pat_a(7, 7));       /* plane (8, 7): tile (1, 0), flipped in x: tx 7 */
    reg(BG(0, PLN_BG_SCROLL), 248 | 248u << 16);        /* the far corner wraps to the top left */
    d = present();
    CHECK_EQ(d[0], 32 + pat_a(0, 0));
    CHECK_EQ(d[7 * MEI_W + 7], 32 + pat_a(7, 7));
    CHECK_EQ(d[8 * MEI_W + 8], 32 + pat_a(0, 0));       /* plane (0, 0) */
    reg(BG(0, PLN_BG_SCROLL), 0xFFFF | 0xFFFFu << 16);  /* -1, -1 */
    d = present();
    CHECK_EQ(d[1 * MEI_W + 1], 32 + pat_a(0, 0));
    CHECK_EQ(d[0], 32 + pat_a(7, 7));                   /* plane (255, 255) = tile (31, 31) */
    CHECK_EQ(d[1 * MEI_W + 257], 32 + pat_a(0, 0));     /* x = 257 shows plane x = 0 again */

    /* a wider map: 64 wide wraps at 512 */
    reg(BG(0, PLN_BG_MODE), 2 << 8 | 1);
    reg(BG(0, PLN_BG_SCROLL), 0);
    for (int i = 0; i < 64 * 32; i++) wr16(V(MAP0) + 2 * i, 0);
    map_set(MAP0, 64, 33, 0, 1);
    d = present();
    CHECK_EQ(d[264], 32 + pat_a(0, 0));
    CHECK_EQ(d[8], 0x7FFF);
    reg(BG(0, PLN_BG_SCROLL), 200);
    d = present();
    CHECK_EQ(d[64], 32 + pat_a(0, 0));
    CHECK_EQ(d[63], 0x7FFF);
    reg(BG(0, PLN_BG_SCROLL), 500);                    /* x = 276 shows plane 776 mod 512 = 264 */
    d = present();
    CHECK_EQ(d[276], 32 + pat_a(0, 0));
    /* map height: 128 tall (code 2 and 3 alike) */
    reg(BG(0, PLN_BG_MODE), 2 << 8 | 3 << 2);
    reg(BG(0, PLN_BG_SCROLL), 0x3F8u << 16);           /* y + 1016 */
    for (int i = 0; i < 32 * 128; i++) wr16(V(MAP0) + 2 * i, 0);
    map_set(MAP0, 32, 0, 127, 1);
    d = present();
    CHECK_EQ(d[0], 32 + pat_a(0, 0));

    /* the window: insets left 10, right 20, top 5, bottom 7 */
    reg(BG(0, PLN_BG_MODE), 0);
    reg(BG(0, PLN_BG_SCROLL), 0);
    tile4(ATLAS4, 2, pat_solid);
    for (int i = 0; i < 32 * 32; i++) wr16(V(MAP0) + 2 * i, 2);
    reg(BG(0, PLN_BG_WINX), 10 | 20u << 16);
    reg(BG(0, PLN_BG_WINY), 5 | 7u << 8);
    d = present();
    bad = 0;
    for (int y = 0; y < MEI_H; y++)
        for (int x = 0; x < MEI_W; x++) {
            int in = x >= 10 && x < 300 && y >= 5 && y < 233;
            bad += d[y * MEI_W + x] != (in ? 9 : 0x7FFF);
        }
    CHECK_EQ(bad, 0);
    reg(BG(0, PLN_BG_WINX), 200 | 200u << 16);          /* empty */
    d = present();
    CHECK_EQ(d[160 + 100 * MEI_W], 0x7FFF);
    reg(BG(0, PLN_BG_WINX), 0x1FF);                     /* left inset 511: nothing */
    d = present();
    CHECK_EQ(d[319 + 100 * MEI_W], 0x7FFF);
    reg(BG(0, PLN_BG_WINX), 0);
    reg(PLN_LAYERS, 0);                                 /* BG0 off */
    d = present();
    CHECK_EQ(d[160 + 100 * MEI_W], 0x7FFF);

    /* a transparent texel inside a tile */
    reg(PLN_LAYERS, 1);
    reg(BG(0, PLN_BG_WINY), 0);
    tile4(ATLAS4, 2, pat_hole);
    d = present();
    CHECK_EQ(d[4 * MEI_W + 3], 0x7FFF);
    CHECK_EQ(d[4 * MEI_W + 4], 5);
}

/* 16x16 tiles and 8-bit colour */
static void test_tile_sizes(void) {
    setup();
    pal_identity();
    for (int v = 0; v < 256; v++)
        for (int u = 0; u < 256; u++) V(ATLAS8)[v * 256 + u] = (uint8_t)((u * 3 + v * 7) % 255 + 1);
    reg(PLN_CTRL, 1);
    reg(PLN_LAYERS, 2);
    reg(BG(1, PLN_BG_MODE), 0x10 | 0x20 | 14 << 8);   /* 16x16, 8-bit, palette base 14 */
    reg(BG(1, PLN_BG_TILES), ATLAS8 | 0x7FFF);        /* bits 0-14 ignored */
    reg(BG(1, PLN_BG_MAP), MAP1 | 0x7FF);             /* bits 0-10 ignored */
    map_set(MAP1, 32, 0, 0, 17 | 3 << 10);            /* cell (1, 1); palette (14 + 3) mod 16 = 1 */
    map_set(MAP1, 32, 1, 0, (17 + 256) | 0x4000);     /* bits 8-9 of t ignored; flip x; palette 14 */
    map_set(MAP1, 32, 2, 0, 255 | 0x8000);            /* cell (15, 15), flip y */
    back_fill(0x8000);
    const uint16_t *d = present();
    int bad = 0;
    for (int ty = 0; ty < 16; ty++)
        for (int tx = 0; tx < 16; tx++) {
            int a = ((16 + tx) * 3 + (16 + ty) * 7) % 255 + 1;
            int b = ((16 + 15 - tx) * 3 + (16 + ty) * 7) % 255 + 1;
            int c = ((240 + tx) * 3 + (240 + 15 - ty) * 7) % 255 + 1;
            bad += d[ty * MEI_W + tx] != 256 + a;
            bad += d[ty * MEI_W + 16 + tx] != 14 * 256 + b;
            bad += d[ty * MEI_W + 32 + tx] != 14 * 256 + c;
        }
    CHECK_EQ(bad, 0);
    /* the 4-bit atlas with 16x16 tiles: tile t is cell (t mod 16, (t div 16) mod 16) */
    for (int v = 0; v < 256; v++)
        for (int u = 0; u < 256; u++) atlas4_set(ATLAS4, u, v, (u + v) % 15 + 1);
    reg(BG(1, PLN_BG_MODE), 0x10 | 7 << 8);
    reg(BG(1, PLN_BG_TILES), ATLAS4);
    map_set(MAP1, 32, 0, 0, 0x3FF);                   /* t = 1023 -> cell (15, 15) */
    d = present();
    CHECK_EQ(d[0], 7 * 16 + (240 + 240) % 15 + 1);
    CHECK_EQ(d[15 + 15 * MEI_W], 7 * 16 + (255 + 255) % 15 + 1);
    /* 8x8 tiles in an 8-bit atlas: tile t at column t mod 32, row t div 32; 1,024 tiles */
    reg(BG(1, PLN_BG_MODE), 0x20);
    reg(BG(1, PLN_BG_TILES), ATLAS8);
    map_set(MAP1, 32, 0, 0, 1023);
    d = present();
    CHECK_EQ(d[0], (248 * 3 + 248 * 7) % 255 + 1);
    CHECK_EQ(d[7 + 7 * MEI_W], (255 * 3 + 255 * 7) % 255 + 1);
    /* atlas addresses wrap within VRAM: page 31 (slot 15) with an 8-bit atlas runs into page 0 */
    reg(BG(1, PLN_BG_TILES), 0x4F8000);
    map_set(MAP1, 32, 0, 0, 32 * 16);                 /* row 16: byte 16 * 8 * 256 = 0x8000 past the page */
    V(0x400000)[0] = 77;                              /* VRAM offset 0: framebuffer A's first byte */
    d = present();
    CHECK_EQ(d[0], 77);
}

/* ================================================================ the affine plane */

static int64_t fl16(int64_t v) { return v >= 0 ? v / 65536 : -((-v + 65535) / 65536); }

static void affine_setup(void) {
    setup();
    pal_identity();
    reg(PLN_CTRL, 1);
    reg(PLN_LAYERS, 4);
    reg(PLN_BD_COLOR, 0xF8F8F8);
    reg(BG(2, PLN_BG_MODE), 4 << 8);                  /* 32x32, 8x8, 4-bit, palette 4 */
    reg(BG(2, PLN_BG_TILES), ATLAS4);
    reg(BG(2, PLN_BG_MAP), MAP2);
    /* tile t + 1 at map (mx, my) with t = (mx + my) % 3; tiles 1-3 are textured: plane pixel
     * (u, v) = 64 + 16 * t + (u mod 8 + v mod 8) % 15 + 1 */
    for (int t = 0; t < 4; t++)
        for (int ty = 0; ty < 8; ty++)
            for (int tx = 0; tx < 8; tx++) atlas4_set(ATLAS4, t * 8 + tx, ty, (tx + ty) % 15 + 1);
    for (int my = 0; my < 32; my++)
        for (int mx = 0; mx < 32; mx++) map_set(MAP2, 32, mx, my, (uint16_t)((((mx + my) % 3) + 1) | (((mx + my) % 3) << 10)));
    back_fill(0x8000);
}
static int plane_px(int u, int v) {   /* the expected colour of plane pixel (u, v), 0 <= u, v < 256 */
    int t = (u / 8 + v / 8) % 3;
    return 64 + 16 * t + (u % 8 + v % 8) % 15 + 1;
}
static void affine(int32_t u0, int32_t v0, int32_t dux, int32_t dvx, int32_t duy, int32_t dvy) {
    reg(PLN_BG2_U0, (uint32_t)u0); reg(PLN_BG2_V0, (uint32_t)v0);
    reg(PLN_BG2_DUX, (uint32_t)dux); reg(PLN_BG2_DVX, (uint32_t)dvx);
    reg(PLN_BG2_DUY, (uint32_t)duy); reg(PLN_BG2_DVY, (uint32_t)dvy);
}

static void test_affine(void) {
    affine_setup();
    /* identity with an offset: a scrolling plane */
    affine(5 << 16, 7 << 16, 1 << 16, 0, 0, 1 << 16);
    const uint16_t *d = present();
    int bad = 0;
    for (int y = 0; y < MEI_H; y++)
        for (int x = 0; x < MEI_W; x++) bad += d[y * MEI_W + x] != plane_px((x + 5) & 255, (y + 7) & 255);
    CHECK_EQ(bad, 0);

    /* rotation by 90 degrees: u = y, v = -x + 300 */
    affine(0, 300 << 16, 0, -(1 << 16), 1 << 16, 0);
    d = present();
    bad = 0;
    for (int y = 0; y < MEI_H; y++)
        for (int x = 0; x < MEI_W; x++) bad += d[y * MEI_W + x] != plane_px(y & 255, (300 - x) & 255);
    CHECK_EQ(bad, 0);

    /* scale 0.5 and floor rounding: u = -0.5 + x / 2 */
    affine(-0x8000, 0, 0x8000, 0, 0, 0x8000);
    reg(BG(2, PLN_BG_MODE), 4 << 8 | 1 << 16);       /* outside: transparent */
    d = present();
    CHECK_EQ(d[0], 0x7FFF);                          /* u = -0.5: texel -1, outside */
    CHECK_EQ(d[1], plane_px(0, 0));                  /* u = 0 */
    CHECK_EQ(d[2], plane_px(0, 0));                  /* u = 0.5 */
    CHECK_EQ(d[3], plane_px(1, 0));
    CHECK_EQ(d[2 * MEI_W + 3], plane_px(1, 1));
    bad = 0;
    for (int y = 0; y < MEI_H; y++)
        for (int x = 1; x < MEI_W; x++) bad += d[y * MEI_W + x] != plane_px((x - 1) / 2, y / 2);
    CHECK_EQ(bad, 0);

    /* outside the map: wrap, transparent, tile 0, and 3 as 1 */
    tile4(ATLAS4, 0, pat_a);
    affine(-20 * 65536, -3 * 65536, 1 << 16, 0, 0, 1 << 16);   /* u = x - 20, v = y - 3 */
    for (int mode = 0; mode < 4; mode++) {
        reg(BG(2, PLN_BG_MODE), 4 << 8 | (uint32_t)mode << 16);
        d = present();
        bad = 0;
        for (int y = 0; y < MEI_H; y++)
            for (int x = 0; x < MEI_W; x++) {
                int u = x - 20, v = y - 3, want;
                if (u >= 0 && u < 256 && v >= 0 && v < 256) want = plane_px(u, v);
                else if (mode == 0) want = plane_px(u & 255, v & 255);
                else if (mode == 2) want = 64 + pat_a(u & 7, v & 7);   /* entry 0x0000: tile 0, palette 0 */
                else want = 0x7FFF;
                bad += d[y * MEI_W + x] != want;
            }
        CHECK_EQ(bad, 0);
    }
    /* entries are flipped as they say */
    reg(BG(2, PLN_BG_MODE), 4 << 8);
    affine(0, 0, 1 << 16, 0, 0, 1 << 16);
    map_set(MAP2, 32, 0, 0, 1 | 0xC000 | 2 << 10);
    d = present();
    CHECK_EQ(d[0], 64 + 32 + (7 + 7) % 15 + 1);
    CHECK_EQ(d[7 * MEI_W + 6], 64 + 32 + (1 + 0) % 15 + 1);

    /* the sums are 64-bit: u = U0 + y DUY + x DUX overflows 32 bits */
    affine_setup();
    affine(0x7FFF0000, 0x7FFF0000, 0x7FFF0000, 0x10000, 0x7FFF8000, 0x7FFF0000);
    d = present();
    bad = 0;
    for (int y = 0; y < MEI_H; y += 7)
        for (int x = 0; x < MEI_W; x += 3) {
            int64_t u = 0x7FFF0000LL + (int64_t)y * 0x7FFF8000LL + (int64_t)x * 0x7FFF0000LL;
            int64_t v = 0x7FFF0000LL + (int64_t)y * 0x7FFF0000LL + (int64_t)x * 0x10000LL;
            bad += d[y * MEI_W + x] != plane_px((int)(fl16(u) & 255), (int)(fl16(v) & 255));
        }
    CHECK_EQ(bad, 0);
    affine((int32_t)0x80000000u, 0, (int32_t)0x80000001u, 0, (int32_t)0x80000000u, 0x10000);
    d = present();
    bad = 0;
    for (int y = 0; y < MEI_H; y += 5)
        for (int x = 0; x < MEI_W; x += 3) {
            int64_t u = -0x80000000LL + (int64_t)y * -0x80000000LL + (int64_t)x * -0x7FFFFFFFLL;
            bad += d[y * MEI_W + x] != plane_px((int)(fl16(u) & 255), y & 255);
        }
    CHECK_EQ(bad, 0);

}

/* 16x16 tiles in a 64x32 map: 1,024 x 512 pixels. */
static void test_affine_16(void) {
    affine_setup();
    reg(BG(2, PLN_BG_MODE), 0x10 | 1 | 3 << 8 | 1 << 16);   /* 64x32 of 16x16: 1,024 x 512; outside transparent */
    for (int i = 0; i < 64 * 32; i++) wr16(V(MAP2) + 2 * i, 0);
    map_set(MAP2, 64, 63, 31, 0x4001);                /* map (63, 31) = plane (1008..1023, 496..511) */
    affine(1000 << 16, 490 << 16, 1 << 16, 0, 0, 1 << 16);
    const uint16_t *d = present();
    /* screen (8, 6) = plane (1008, 496): tile 1 = cell (1, 0) of the 16x16 grid, flipped in x, so
     * texel (16 + 15, 0) of the atlas, which affine_setup() filled as 8x8 tile 3: (7 + 0) % 15 + 1 */
    CHECK_EQ(d[6 * MEI_W + 8], 3 * 16 + 8);
    CHECK_EQ(d[6 * MEI_W + 9], 3 * 16 + 7);            /* texel (30, 0) */
    CHECK_EQ(d[7 * MEI_W + 8], 3 * 16 + 9);            /* texel (31, 1) */
    CHECK_EQ(d[14 * MEI_W + 8], 0x7FFF);               /* texel (31, 8): index 0 */
    CHECK_EQ(d[6 * MEI_W + 7], 3 * 16 + 8);            /* (1007, 496): entry 0x0000, tile 0, texel (7, 0) */
    CHECK_EQ(d[22 * MEI_W + 8], 0x7FFF);               /* v = 512: outside, transparent */
    CHECK_EQ(d[6 * MEI_W + 24], 0x7FFF);               /* u = 1024 */
}

/* Mode 7: the worked example's perspective rows (docs/PLANES.md), one table of 4 words a line. */
static void test_perspective(void) {
    affine_setup();
    static const struct { int y; uint32_t u0, v0, dux; } rows[] = {
        {98, 0xFF198E69u, 0x024D9E71u, 0x000270B5u}, {100, 0xFF6DABD9u, 0x01DF4B8Fu, 0x0001EA20u},
        {120, 0x003EE2FFu, 0x00CCE452u, 0x00009B61u}, {160, 0x0076F42Fu, 0x00835AEDu, 0x000041ACu},
        {239, 0x008CD25Cu, 0x0066AC75u, 0x00001EAFu},
    };
    for (int y = 0; y < 240; y++) for (int k = 0; k < 4; k++) wr32(V(0x44F000) + (y * 4 + k) * 4, 0);
    for (size_t i = 0; i < sizeof rows / sizeof *rows; i++) {
        uint8_t *e = V(0x44F000) + rows[i].y * 16;
        wr32(e, rows[i].u0); wr32(e + 4, rows[i].v0); wr32(e + 8, rows[i].dux); wr32(e + 12, 0);
    }
    affine(0x11110000, 0x22220000, 0x33330000, 0x44440000, 0, 0);   /* the CPU values: overwritten */
    reg(PLN_LC + 7 * 8, 0x44F000);
    reg(PLN_LC + 7 * 8 + 4, 0x8000 | 3 << 8 | PLN_BG2_U0);
    reg(BG(2, PLN_BG_WINY), 98);
    const uint16_t *d = present();
    int bad = 0;
    for (size_t i = 0; i < sizeof rows / sizeof *rows; i++) {
        int y = rows[i].y;
        for (int x = 0; x < MEI_W; x++) {
            int64_t u = (int64_t)(int32_t)rows[i].u0 + (int64_t)x * (int32_t)rows[i].dux;
            int64_t v = (int32_t)rows[i].v0;
            bad += d[y * MEI_W + x] != plane_px((int)(fl16(u) & 255), (int)(fl16(v) & 255));
        }
    }
    CHECK_EQ(bad, 0);
    /* row 98, x = 0: u = -230.44 -> texel -231 -> 25 (wrap); v = 589.62 -> 589 -> 77 */
    CHECK_EQ(d[98 * MEI_W], plane_px(25, 77));
    CHECK_EQ(d[97 * MEI_W + 100], 0x7FFF);            /* above the top inset: the backdrop */
    CHECK_EQ(rreg(PLN_BG2_U0), 0x11110000);           /* the CPU still reads what it wrote */
}

/* ================================================================ line channels */

static void test_line_channels(void) {
    setup();
    reg(PLN_CTRL, 1);
    back_fill(0x8000);
    /* channel 0: a backdrop colour per line */
    for (int y = 0; y < 240; y++) wr32(V(TABLES) + y * 4, (uint32_t)(y * 8) << 16 | (uint32_t)(255 - y) << 8 | 0x10);
    reg(PLN_LC + 0, TABLES | 3);                      /* bits 0-1 ignored */
    reg(PLN_LC + 4, 0x8000 | PLN_BD_COLOR);
    const uint16_t *d = present();
    int bad = 0;
    for (int y = 0; y < 240; y++) bad += d[y * MEI_W + y] != C15(2, (255 - y) >> 3, (y * 8 & 255) >> 3);
    CHECK_EQ(bad, 0);
    CHECK_EQ(rreg(PLN_LC + 0), TABLES | 3);           /* read back as written */
    CHECK_EQ(rreg(PLN_BD_COLOR), 0);

    /* a later channel wins: channel 3 also writes BD_COLOR, from a table of constant colour */
    for (int y = 0; y < 240; y++) wr32(V(TABLES + 0x400) + y * 4, 0x0000F8);
    reg(PLN_LC + 3 * 8, TABLES + 0x400);
    reg(PLN_LC + 3 * 8 + 4, 0x8000 | PLN_BD_COLOR);
    d = present();
    CHECK_EQ(d[50 * MEI_W], 31);
    /* and an earlier one loses: move it to channel 0 and the gradient to channel 5 */
    reg(PLN_LC + 5 * 8, TABLES);
    reg(PLN_LC + 5 * 8 + 4, 0x8000 | PLN_BD_COLOR);
    reg(PLN_LC + 0, TABLES + 0x400);
    reg(PLN_LC + 3 * 8 + 4, 0);                       /* channel 3 disabled */
    d = present();
    CHECK_EQ(d[50 * MEI_W], C15(2, (255 - 50) >> 3, (400 & 255) >> 3));
    reg(PLN_LC + 5 * 8 + 4, 0x7FFF);                  /* bit 15 clear: off */
    reg(PLN_LC + 4, 0);
    d = present();
    CHECK_EQ(d[50 * MEI_W], 0);

    /* words per line and dropped targets. A table of 4 words per line. */
    setup();
    pal_identity();
    tile4(ATLAS4, 1, pat_solid);
    for (int i = 0; i < 32 * 32; i++) wr16(V(MAP0) + 2 * i, 1);
    reg(PLN_CTRL, 1);
    reg(PLN_LAYERS, 1);
    reg(BG(0, PLN_BG_TILES), ATLAS4);
    reg(BG(0, PLN_BG_MAP), MAP0);
    back_fill(0x8000);
    for (int y = 0; y < 240; y++) {
        wr32(V(TABLES) + (y * 4 + 0) * 4, (uint32_t)(y & 1));                 /* -> PLN_LAYERS */
        wr32(V(TABLES) + (y * 4 + 1) * 4, 0);                                 /* -> PLN_PRIO */
        wr32(V(TABLES) + (y * 4 + 2) * 4, 0);                                 /* -> PLN_MATH */
        wr32(V(TABLES) + (y * 4 + 3) * 4, 0x00100000);                        /* -> PLN_OFS */
    }
    reg(PLN_LC + 2 * 8, TABLES);
    reg(PLN_LC + 2 * 8 + 4, 0x8000 | 3 << 8 | PLN_LAYERS);
    d = present();
    CHECK_EQ(d[10 * MEI_W], 0);                       /* even lines: BG0 off */
    CHECK_EQ(d[11 * MEI_W], 9);
    CHECK_EQ(rreg(PLN_LAYERS), 1);
    /* target PLN_CTRL: dropped (a line can't turn the compositor or dither on) */
    reg(PLN_LC + 2 * 8 + 4, 0x8000 | 0 << 8 | PLN_CTRL);
    for (int y = 0; y < 240; y++) wr32(V(TABLES) + y * 4, 4);
    reg(PLN_LC + 2 * 8 + 4, 0x8000 | PLN_CTRL);
    d = present();
    CHECK_EQ(d[0], 9);
    /* PLN_ERASE accepted but changes nothing; 0x1C (reserved) dropped; BG0_MODE (0x20) taken */
    for (int y = 0; y < 240; y++) {
        wr32(V(TABLES) + (y * 3 + 0) * 4, 0x7C00);
        wr32(V(TABLES) + (y * 3 + 1) * 4, 0xFFFFFFFFu);
        wr32(V(TABLES) + (y * 3 + 2) * 4, 5 << 8);
    }
    reg(PLN_CTRL, 3);
    reg(PLN_ERASE, 0x8000);
    reg(PLN_LC + 2 * 8 + 4, 0x8000 | 2 << 8 | PLN_ERASE);
    d = present();
    CHECK_EQ(d[0], 5 * 16 + 9);                       /* palette base 5 from the table */
    CHECK_EQ(back_get(0, 0), 0x8000);                 /* erase used the CPU's value */
    /* a run past BG2_DVY: the words that land at 0x90 and beyond are dropped */
    reg(PLN_CTRL, 1);
    for (int y = 0; y < 240; y++) for (int k = 0; k < 4; k++) wr32(V(TABLES) + (y * 4 + k) * 4, 0x12345678);
    reg(PLN_LC + 2 * 8 + 4, 0x8000 | 3 << 8 | PLN_BG2_DVY);
    d = present();
    CHECK_EQ(d[0], 9);
    /* targets inside the channel registers are dropped too (a channel can't move a channel) */
    for (int y = 0; y < 240; y++) {
        wr32(V(TABLES) + (y * 2 + 0) * 4, TABLES + 0x800);
        wr32(V(TABLES) + (y * 2 + 1) * 4, 0x8000 | PLN_LAYERS);
    }
    for (int y = 0; y < 240; y++) wr32(V(TABLES + 0x800) + y * 4, 0);
    reg(PLN_LC + 2 * 8 + 4, 0x8000 | 1 << 8 | (PLN_LC + 8));
    d = present();
    CHECK_EQ(d[0], 9);
    /* scroll per line: wavy plane */
    reg(PLN_LC + 2 * 8 + 4, 0);
    tile4(ATLAS4, 1, pat_a);
    reg(BG(0, PLN_BG_MODE), 0);
    for (int y = 0; y < 240; y++) wr32(V(TABLES + 0x400) + y * 4, (uint32_t)(y % 5));
    reg(PLN_LC + 6 * 8, TABLES + 0x400);
    reg(PLN_LC + 6 * 8 + 4, 0x8000 | BG(0, PLN_BG_SCROLL));
    d = present();
    bad = 0;
    for (int y = 0; y < 240; y++)
        for (int x = 0; x < 320; x += 13) bad += d[y * MEI_W + x] != pat_a((x + y % 5) & 7, y & 7);
    CHECK_EQ(bad, 0);
    /* a per-line window: an iris */
    for (int y = 0; y < 240; y++) {
        int h = y < 120 ? y : 239 - y;
        wr32(V(TABLES + 0x400) + y * 4, (uint32_t)(160 - h) | (uint32_t)(160 - h) << 16);
    }
    reg(PLN_LC + 6 * 8 + 4, 0x8000 | BG(0, PLN_BG_WINX));
    d = present();
    CHECK_EQ(d[0 * MEI_W + 160], 0);                  /* line 0: left 160, right 160: empty */
    CHECK_EQ(d[100 * MEI_W + 59], 0);                 /* line 100: insets 60 and 60 */
    CHECK_EQ(d[100 * MEI_W + 60], pat_a(60 & 7, 100 & 7));
    CHECK_EQ(d[100 * MEI_W + 259], pat_a(259 & 7, 100 & 7));
    CHECK_EQ(d[100 * MEI_W + 260], 0);
    /* table addresses wrap within VRAM: ADDR 0xFFFFC, line 1 reads VRAM offset 0 */
    reg(PLN_LC + 6 * 8 + 4, 0);
    reg(PLN_LAYERS, 8);                               /* (the table runs into framebuffer A) */
    wr32(V(0x4FFFFC), 0x0000F8);
    wr32(V(0x400000), 0x00F800);
    reg(PLN_LC + 1 * 8, 0x4FFFFC);
    reg(PLN_LC + 1 * 8 + 4, 0x8000 | PLN_BD_COLOR);
    d = present();
    CHECK_EQ(d[0], 31);
    CHECK_EQ(d[MEI_W], 31 << 5);
}

/* ================================================================ priorities */

static void test_priority(void) {
    setup();
    pal_identity();
    tile4(ATLAS4, 1, pat_solid);                      /* every plane solid: index 9 */
    for (int n = 0; n < 3; n++) {
        uint32_t map = n == 0 ? MAP0 : n == 1 ? MAP1 : MAP2;
        for (int i = 0; i < 32 * 32; i++) wr16(V(map) + 2 * i, 1);
        reg(BG(n, PLN_BG_MODE), (uint32_t)(n + 1) << 8);     /* BGn shows 16 (n + 1) + 9 */
        reg(BG(n, PLN_BG_TILES), ATLAS4);
        reg(BG(n, PLN_BG_MAP), map);
    }
    affine(0, 0, 1 << 16, 0, 0, 1 << 16);
    reg(PLN_CTRL, 1);
    reg(PLN_LAYERS, 7);
    back_fill(0x8000);
    back_px(0, 0, 0x0111);                            /* PL */
    back_px(1, 0, 0x8222);                            /* PH */
    const uint16_t *d = present();
    enum { B0 = 16 + 9, B1 = 32 + 9, B2 = 48 + 9 };
    CHECK_EQ(d[0], 0x111);                            /* all priorities 0: polygons on top */
    CHECK_EQ(d[1], 0x222);
    CHECK_EQ(d[2], B0);                               /* then BG0 */
    reg(PLN_LAYERS, 6);
    back_fill(0x8000);
    d = present();
    CHECK_EQ(d[2], B1);
    reg(PLN_LAYERS, 4);
    back_fill(0x8000);
    d = present();
    CHECK_EQ(d[2], B2);
    /* BG2 at 1: above the polygons */
    reg(PLN_LAYERS, 7);
    reg(PLN_PRIO, 1 << 16);
    back_fill(0x8000);
    back_px(0, 0, 0x0111);
    back_px(1, 0, 0x8222);
    d = present();
    CHECK_EQ(d[0], B2);
    CHECK_EQ(d[1], B2);
    /* PL 5, PH 2, BG0 3: low polygons in front of BG0, high ones behind it */
    reg(PLN_PRIO, 3 | 5u << 24 | 2u << 28);
    back_fill(0x8000);
    back_px(0, 0, 0x0111);
    back_px(1, 0, 0x8222);
    d = present();
    CHECK_EQ(d[0], 0x111);
    CHECK_EQ(d[1], B0);
    /* ties: PH over BG0 at the same priority, BG0 over BG1, BG1 over BG2 */
    reg(PLN_PRIO, 4 | 4u << 8 | 4u << 16 | 4u << 28);
    back_fill(0x8000);
    back_px(1, 0, 0x8222);
    d = present();
    CHECK_EQ(d[1], 0x222);
    CHECK_EQ(d[2], B0);
    reg(PLN_PRIO, 2 | 4u << 8 | 4u << 16);
    d = present();
    CHECK_EQ(d[2], B1);
    /* priority tiles: BG1's front tiles at 15 */
    map_set(MAP1, 32, 1, 0, 1 | 0x2000);
    reg(PLN_PRIO, 0xFu << 12);
    back_fill(0x8000);
    back_px(8, 0, 0x8333);
    back_px(0, 0, 0x8333);
    d = present();
    CHECK_EQ(d[8], B1);                               /* tile (1, 0) has the bit */
    CHECK_EQ(d[0], 0x333);
    /* BG0's priority tile at its own front priority 1 vs BG2 at 1: tie, BG0 wins */
    map_set(MAP0, 32, 2, 0, 1 | 0x2000);
    reg(PLN_PRIO, 1u << 4 | 1u << 16);
    back_fill(0x8000);
    d = present();
    CHECK_EQ(d[16], B0);
    CHECK_EQ(d[24], B2);
    /* the polygon layer hidden: its pixels never take part */
    reg(PLN_PRIO, 0);
    reg(PLN_LAYERS, 8 | 4);
    back_fill(0x0111);
    d = present();
    CHECK_EQ(d[100], B2);
}

/* ================================================================ colour math and offset */

static void test_colour_math(void) {
    setup();
    tile4(ATLAS4, 1, pat_solid);
    for (int i = 0; i < 32 * 32; i++) { wr16(V(MAP0) + 2 * i, 1); wr16(V(MAP1) + 2 * i, 1); }
    pal(16 + 9, C15(20, 10, 30));                     /* BG0 (palette 1) */
    pal(32 + 9, C15(15, 25, 4));                      /* BG1 (palette 2) */
    reg(BG(0, PLN_BG_MODE), 1 << 8); reg(BG(0, PLN_BG_TILES), ATLAS4); reg(BG(0, PLN_BG_MAP), MAP0);
    reg(BG(1, PLN_BG_MODE), 2 << 8); reg(BG(1, PLN_BG_TILES), ATLAS4); reg(BG(1, PLN_BG_MAP), MAP1);
    reg(PLN_CTRL, 1);
    reg(PLN_LAYERS, 3);
    reg(PLN_BD_COLOR, 0x404040);                      /* 8, 8, 8 */
    back_fill(0x8000);
    const uint16_t want[4] = {
        C15((15 + 20) >> 1, (25 + 10) >> 1, (4 + 30) >> 1),
        C15(31, 31, 31),
        C15(0, 15, 0),
        C15(20, 27, 11),
    };
    for (int mode = 0; mode < 4; mode++) {
        reg(PLN_MATH, 4u | (uint32_t)mode);           /* BG0 translucent */
        const uint16_t *d = present();
        CHECK_EQ(d[0], want[mode]);
    }
    /* over nothing: blends with the backdrop */
    reg(PLN_LAYERS, 1);
    reg(PLN_MATH, 4);
    const uint16_t *d = present();
    CHECK_EQ(d[0], C15((8 + 20) >> 1, (8 + 10) >> 1, (8 + 30) >> 1));
    /* only the top two take part: BG0 and BG1 both translucent over BG2 */
    reg(PLN_LAYERS, 3);
    reg(PLN_MATH, 4 | 5 << 4);
    d = present();
    CHECK_EQ(d[0], want[0]);
    /* the math bit of a layer that is not on top does nothing */
    reg(PLN_MATH, 5 << 4);
    d = present();
    CHECK_EQ(d[0], C15(20, 10, 30));
}

static void test_colour_math_exact(void) {
    /* the cases of test_colour_math, worked by hand */
    setup();
    tile4(ATLAS4, 1, pat_solid);
    for (int i = 0; i < 32 * 32; i++) wr16(V(MAP0) + 2 * i, 1);
    pal(16 + 9, C15(20, 10, 30));
    reg(BG(0, PLN_BG_MODE), 1 << 8); reg(BG(0, PLN_BG_TILES), ATLAS4); reg(BG(0, PLN_BG_MAP), MAP0);
    reg(PLN_CTRL, 1);
    reg(PLN_LAYERS, 1);
    reg(PLN_BD_COLOR, 0x404040);
    reg(PLN_MATH, 4u << 12 | 7u << 16);
    back_fill(0x8000);
    back_px(0, 0, C15(2, 2, 2));                      /* PL half over BG0 */
    back_px(1, 0, 0x8000 | C15(31, 1, 1));            /* PH quarter-add over BG0 */
    back_px(2, 0, 0x8000 | C15(4, 4, 4));
    reg(PLN_LAYERS, 1);
    const uint16_t *d = present();
    CHECK_EQ(d[0], C15((20 + 2) >> 1, (10 + 2) >> 1, (30 + 2) >> 1));
    CHECK_EQ(d[1], C15(20 + 7, 10 + 0, 30 + 0));
    CHECK_EQ(d[2], C15(21, 11, 31));
    /* subtract and add clamp per channel */
    reg(PLN_MATH, 6u << 16);
    back_fill(0x8000);
    back_px(0, 0, 0x8000 | C15(25, 3, 0));
    d = present();
    CHECK_EQ(d[0], C15(0, 7, 30));
    reg(PLN_MATH, 5u << 16);
    back_fill(0x8000);
    back_px(0, 0, 0x8000 | C15(25, 3, 0));
    d = present();
    CHECK_EQ(d[0], C15(31, 13, 30));

    /* the colour offset: on the winning layer's bit, after blending, clamped */
    reg(PLN_MATH, 1u << 24);
    reg(PLN_OFS, 0x00FDE00Au | 0xAA000000u);          /* r +10, g -32, b -3; bits 24-31 ignored */
    back_fill(0x8000);
    d = present();
    CHECK_EQ(d[0], C15(30, 0, 27));
    reg(PLN_MATH, 1u << 29);                          /* backdrop only */
    reg(PLN_LAYERS, 0);
    d = present();
    CHECK_EQ(d[0], C15(18, 0, 5));
    reg(PLN_LAYERS, 1);
    d = present();
    CHECK_EQ(d[0], C15(20, 10, 30));                  /* BG0 won: its bit is clear */
    reg(PLN_MATH, 1u << 27 | 4u << 12);               /* PL: half over BG0, then the offset */
    reg(PLN_OFS, 0x7F7F7F);
    back_fill(0x8000);
    back_px(0, 0, C15(0, 0, 0));
    d = present();
    CHECK_EQ(d[0], C15(31, 31, 31));
    CHECK_EQ(d[1], C15(20, 10, 30));
    reg(PLN_OFS, 0x808080);                           /* -128: black */
    d = present();
    CHECK_EQ(d[0], 0);
}

/* ================================================================ a literal reference */

/* The normative algorithm, transcribed per pixel with nothing shared with planes.c. */
static uint32_t ref_reg[64];
static uint32_t ref_W(int y, uint32_t off) {
    uint32_t v = ref_reg[off / 4];
    for (int ch = 0; ch < 8; ch++) {
        uint32_t ctrl = ref_reg[(0xA4 + 8 * ch) / 4];
        if (!(ctrl & 0x8000)) continue;
        uint32_t n = ((ctrl >> 8) & 3) + 1, t = ctrl & 0xFC, addr = ref_reg[(0xA0 + 8 * ch) / 4] & 0xFFFFC;
        for (uint32_t k = 0; k < n; k++) {
            uint32_t o = t + 4 * k;
            int ok = o >= 4 && o <= 0x8C && o != 0x1C && o != 0x38 && o != 0x3C && o != 0x58 && o != 0x5C && o != 0x6C;
            if (ok && o == off) v = rd32(m->vram + ((addr + ((uint32_t)y * n + k) * 4) & 0xFFFFF));
        }
    }
    return v;
}
static int ref_sample(int n, int y, int x, int *hi) {
    uint32_t b = 0x20 + 0x20 * (uint32_t)n;
    uint32_t mode = ref_W(y, b), tiles = ref_W(y, b + 4) & 0xF8000, map = ref_W(y, b + 8) & 0xFF800;
    int mw = (mode & 3) == 0 ? 32 : (mode & 3) == 1 ? 64 : 128;
    int mh = ((mode >> 2) & 3) == 0 ? 32 : ((mode >> 2) & 3) == 1 ? 64 : 128;
    int ts = (mode & 16) ? 16 : 8;
    long long wpx = mw * ts, hpx = mh * ts, tu, tv;
    uint32_t e;
    if (n < 2) {
        uint32_t sc = ref_W(y, b + 12);
        tu = (x + (sc & 0xFFFF)) % wpx;
        tv = (y + (sc >> 16)) % hpx;
    } else {
        long long u = (int32_t)ref_W(y, 0x78) + (long long)y * (int32_t)ref_W(y, 0x88) + (long long)x * (int32_t)ref_W(y, 0x80);
        long long v = (int32_t)ref_W(y, 0x7C) + (long long)y * (int32_t)ref_W(y, 0x8C) + (long long)x * (int32_t)ref_W(y, 0x84);
        tu = fl16(u); tv = fl16(v);
    }
    int outside = n == 2 && (tu < 0 || tu >= wpx || tv < 0 || tv >= hpx);
    int om = (mode >> 16) & 3;
    if (outside && (om == 1 || om == 3)) return -1;
    if (outside && om == 2) { e = 0; tu = ((tu % ts) + ts) % ts; tv = ((tv % ts) + ts) % ts; }
    else {
        tu = ((tu % wpx) + wpx) % wpx; tv = ((tv % hpx) + hpx) % hpx;
        e = rd16(m->vram + ((map + (uint32_t)((tv / ts) * mw + tu / ts) * 2) & 0xFFFFF));
    }
    int tx = (int)(tu % ts), ty = (int)(tv % ts);
    if (e & 0x4000) tx = ts - 1 - tx;
    if (e & 0x8000) ty = ts - 1 - ty;
    int t = e & 0x3FF, cu, cv;
    if (ts == 8) { cu = (t % 32) * 8 + tx; cv = (t / 32) * 8 + ty; }
    else { cu = (t % 16) * 16 + tx; cv = ((t / 16) % 16) * 16 + ty; }
    int idx, ci, p = (e >> 10) & 7, base = (mode >> 8) & 255;
    if (mode & 32) { idx = m->vram[(tiles + (uint32_t)(cv * 256 + cu)) & 0xFFFFF]; ci = ((base + p) % 16) * 256 + idx; }
    else {
        int byte = m->vram[(tiles + (uint32_t)(cv * 128 + cu / 2)) & 0xFFFFF];
        idx = (cu % 2) ? byte >> 4 : byte & 15;
        ci = ((base + p) % 256) * 16 + idx;
    }
    if (idx == 0) return -1;
    *hi = (e >> 13) & 1;
    return rd16(m->vram + (PALETTE_ADDR - VRAM_BASE) + (uint32_t)ci * 2) & 0x7FFF;
}
static int ref_backdrop(int y, int x) {
    static const int dm[4][4] = {{-4, 0, -3, 1}, {2, -2, 3, -1}, {-3, 1, -4, 0}, {3, -1, 2, -2}};
    uint32_t c = ref_W(y, 0x14);
    int out = 0;
    for (int k = 0; k < 3; k++) {
        int v = (int)((c >> (8 * k)) & 255);
        if (ref_reg[0] & 4) { v += dm[y % 4][x % 4]; v = v < 0 ? 0 : v > 255 ? 255 : v; }
        out |= (v >> 3) << (5 * k);
    }
    return out;
}
static int ref_c31(int v) { return v < 0 ? 0 : v > 31 ? 31 : v; }
static uint16_t ref_pixel(const uint16_t *front, int x, int y) {
    struct { int layer, prio, order, col; } c[4];
    int nc = 0;
    static const int order[5] = {2, 1, 0, 3, 4};
    uint32_t layers = ref_W(y, 4), prio = ref_W(y, 8), math = ref_W(y, 12), ofs = ref_W(y, 16);
    if (!(layers & 8)) {
        uint16_t f = front[y * MEI_W + x];
        if (f != 0x8000) {
            int L = (f & 0x8000) ? 4 : 3;
            c[nc].layer = L; c[nc].prio = (int)(prio >> (L == 4 ? 28 : 24)) & 15; c[nc].order = order[L]; c[nc].col = f & 0x7FFF; nc++;
        }
    }
    for (int n = 0; n < 3; n++) {
        if (!(layers >> n & 1)) continue;
        uint32_t b = 0x20 + 0x20 * (uint32_t)n, wx = ref_W(y, b + 0x10), wy = ref_W(y, b + 0x14);
        if (x < (int)(wx & 0x1FF) || x >= 320 - (int)((wx >> 16) & 0x1FF) || y < (int)(wy & 0xFF) || y >= 240 - (int)((wy >> 8) & 0xFF)) continue;
        int hi = 0, col = ref_sample(n, y, x, &hi);
        if (col < 0) continue;
        c[nc].layer = n; c[nc].prio = (int)(prio >> (8 * n + (hi ? 4 : 0))) & 15; c[nc].order = order[n]; c[nc].col = col; nc++;
    }
    int a = -1, b = -1;
    for (int i = 0; i < nc; i++) {
        int better_a = a < 0 || c[i].prio > c[a].prio || (c[i].prio == c[a].prio && c[i].order > c[a].order);
        if (better_a) { b = a; a = i; continue; }
        if (b < 0 || c[i].prio > c[b].prio || (c[i].prio == c[b].prio && c[i].order > c[b].order)) b = i;
    }
    int out = a < 0 ? ref_backdrop(y, x) : c[a].col, layer = a < 0 ? 5 : c[a].layer;
    if (a >= 0 && (math >> (4 * layer)) & 4) {
        int B = b < 0 ? ref_backdrop(y, x) : c[b].col, A = c[a].col, r = 0, mode = (math >> (4 * layer)) & 3;
        for (int k = 0; k < 3; k++) {
            int bb = (B >> (5 * k)) & 31, aa = (A >> (5 * k)) & 31, v;
            if (mode == 0) v = (bb + aa) / 2;
            else if (mode == 1) v = ref_c31(bb + aa);
            else if (mode == 2) v = ref_c31(bb - aa);
            else v = ref_c31(bb + aa / 4);
            r |= v << (5 * k);
        }
        out = r;
    }
    if ((math >> (24 + layer)) & 1) {
        int r = 0;
        for (int k = 0; k < 3; k++) r |= ref_c31(((out >> (5 * k)) & 31) + (int8_t)(ofs >> (8 * k))) << (5 * k);
        out = r;
    }
    return (uint16_t)out;
}

static void test_reference_random(void) {
    int total_bad = 0;
    for (int iter = 0; iter < 40; iter++) {
        setup();
        for (int i = 0; i < 4096; i++) pal(i, (uint16_t)(rnd32() & 0x7FFF));
        /* random atlases, maps and tables in the plane area and slots 0-1 */
        for (uint32_t a = 0x44E000; a < 0x490000; a += 4) wr32(V(a), rnd32() & (rnd(0, 3) ? 0xFFFFFFFFu : 0));
        uint16_t *fr = (uint16_t *)(void *)back();
        for (int i = 0; i < MEI_W * MEI_H; i++) fr[i] = rnd(0, 2) ? 0x8000 : (uint16_t)rnd32();
        uint32_t r[64] = {0};
        r[0] = 1 | (uint32_t)rnd(0, 1) << 2;
        r[1] = rnd32() & 15;
        r[2] = rnd32();
        r[3] = rnd32() & 0x3F0FFFFF;
        r[4] = rnd32();
        r[5] = rnd32();
        static const uint32_t maps[] = {0x450000, 0x452000, 0x454000, 0x458000, 0x45C800};
        static const uint32_t pages[] = {0x460000, 0x468000, 0x470000, 0x478000, 0x480000, 0x488000};
        for (int n = 0; n < 3; n++) {
            uint32_t b = (0x20 + 0x20 * (uint32_t)n) / 4;
            r[b] = rnd32() & 0x3FF3F;
            r[b + 1] = pages[rnd(0, 5)];
            r[b + 2] = maps[rnd(0, 4)];
            if (n < 2) r[b + 3] = rnd32();
            if (rnd(0, 2) == 0) { r[b + 4] = (uint32_t)rnd(0, 60) | (uint32_t)rnd(0, 60) << 16; r[b + 5] = (uint32_t)rnd(0, 50) | (uint32_t)rnd(0, 50) << 8; }
        }
        for (int k = 0; k < 6; k++) r[0x78 / 4 + k] = rnd(0, 1) ? rnd32() : (uint32_t)(rnd(-0x30000, 0x30000));
        int nch = rnd(0, 4);
        for (int i = 0; i < nch; i++) {
            int ch = rnd(0, 7);
            r[(0xA0 + 8 * ch) / 4] = 0x44E000 + (uint32_t)rnd(0, 0x1000) * 4;
            r[(0xA4 + 8 * ch) / 4] = 0x8000 | (uint32_t)rnd(0, 3) << 8 | (uint32_t)rnd(0, 0x90);
        }
        for (int i = 0; i < 64; i++) {
            m->pln_reg[i] = r[i];
            ref_reg[i] = r[i];
        }
        const uint16_t *d = present();
        const uint16_t *front = fr;
        int bad = 0;
        for (int y = 0; y < MEI_H; y++)
            for (int x = 0; x < MEI_W; x += (iter < 10 ? 1 : 7)) {
                uint16_t want = ref_pixel(front, x, y);
                if (d[y * MEI_W + x] != want) {
                    if (!bad) printf("  random %d: (%d, %d) = 0x%04X, reference 0x%04X\n", iter, x, y, d[y * MEI_W + x], want);
                    bad++;
                }
            }
        total_bad += bad;
    }
    CHECK_EQ(total_bad, 0);
}

/* ================================================================ through a cart */

/* The display path: mei_display shows the composite after a vsync with the compositor on, the
 * front buffer with it off, the previous composite after an overrun, the error screen after a
 * fault. */
static void test_display_path(void) {
    MeiAsmResult res;
    const char *src =
        "    lui  r1, 0x3FC0\n"            /* r1 = 0xFF0000 */
        "    addi r2, r0, 1\n"
        "    sw   r2, [r1+0x700]\n"        /* PLN_CTRL = 1 */
        "    li   r2, 0x0000F8\n"
        "    sw   r2, [r1+0x714]\n"        /* BD_COLOR: red */
        "    li   r2, 0x8000\n"
        "    sw   r2, [r1+4]\n"            /* GPU_CLEAR = holes */
        "    vsync\n"
        "    sw   r0, [r1+0x700]\n"        /* compositor off */
        "    li   r2, 0x3E0\n"
        "    sw   r2, [r1+4]\n"            /* clear green */
        "    vsync\n"
        "    addi r2, r0, 1\n"
        "    sw   r2, [r1+0x700]\n"
        "    sw   r0, [r1+4]\n"            /* clear black: not holes */
        "    vsync\n"
        "    sw   r0, [r1+4]\n"
        "    vsync\n"
        "    li   r2, 0x8000\n"
        "    sw   r2, [r1+4]\n"
        "    vsync\n"
        "spin: jmp spin\n";
    if (mei_assemble(src, "planes_display.s", &res) != 0) { printf("asm: %s\n", res.error); CHECK(0); return; }
    CHECK_EQ(mei_load_cart(m, res.rom, res.rom_len), 0);
    mei_asm_free(&res);
    CHECK_EQ(mei_run_frame(m), 1);
    CHECK(mei_display(m) == m->pln_out);
    CHECK_EQ(mei_display(m)[0], 31);                  /* holes: the red backdrop */
    CHECK_EQ(mei_run_frame(m), 1);
    CHECK(mei_display(m) == gpu_front(m));
    CHECK_EQ(mei_display(m)[0], 0x3E0);
    CHECK_EQ(mei_run_frame(m), 1);
    CHECK_EQ(mei_display(m)[0], 0);                   /* black polygon pixels, not holes */
    CHECK_EQ(mei_run_frame(m), 1);
    CHECK_EQ(mei_run_frame(m), 1);
    CHECK_EQ(mei_display(m)[0], 31);
    CHECK_EQ(mei_run_frame(m), 0);                    /* overrun: the composite repeats */
    CHECK(mei_display(m) == m->pln_out);
    CHECK_EQ(mei_display(m)[0], 31);
    m->pln_out[0] = 0x1234;
    mei_raise(m, MEI_FAULT_BREAK, 0);
    gpu_render_error_screen(m);
    CHECK(mei_display(m) == m->error_screen);
    /* a reset (a cart load) turns the chip off */
    mei_reset(m);
    CHECK_EQ(m->pln_shown, 0);
    CHECK_EQ(m->pln_reg[0], 0);
}

/* ================================================================ speed */

static void bench(void) {
    setup();
    for (uint32_t a = 0x44E000; a < 0x490000; a += 4) wr32(V(a), rnd32() | 0x11111111u);
    for (int i = 0; i < 4096; i++) pal(i, (uint16_t)(rnd32() & 0x7FFF));
    uint16_t *fr = (uint16_t *)(void *)back();
    for (int i = 0; i < MEI_W * MEI_H; i++) fr[i] = (i / 7) % 3 ? 0x8000 : (uint16_t)i;
    m->pln_reg[0] = 7;
    m->pln_reg[1] = 7;
    m->pln_reg[3] = 4 << 8 | 1u << 29;
    for (int n = 0; n < 3; n++) {
        m->pln_reg[(0x20 + 0x20 * n) / 4] = 1 | 4;
        m->pln_reg[(0x24 + 0x20 * n) / 4] = 0x460000 + 0x8000u * (uint32_t)n;
        m->pln_reg[(0x28 + 0x20 * n) / 4] = 0x450000 + 0x2000u * (uint32_t)n;
    }
    m->pln_reg[0x78 / 4] = 0x123456; m->pln_reg[0x80 / 4] = 0xC000; m->pln_reg[0x84 / 4] = 0x3000;
    m->pln_reg[0x8C / 4] = 0x10000;
    m->pln_reg[0xA0 / 4] = 0x44E000; m->pln_reg[0xA4 / 4] = 0x8000 | 0x14;
    m->pln_reg[0xDC / 4] = 0x8000 | 3 << 8 | 0x78; m->pln_reg[0xD8 / 4] = 0x44F000;
    int frames = 200;
    clock_t t0 = clock();
    for (int f = 0; f < frames; f++) { planes_vsync(m); m->back ^= 1; }
    double ms = (double)(clock() - t0) * 1000.0 / CLOCKS_PER_SEC / frames;
    printf("  bench: three planes (BG2 Mode 7 per line), backdrop table, math and offset: %.3f ms per frame\n", ms);
    static const struct { uint32_t layers; const char *what; } cases[] = {
        {1, "BG0 (tile plane) only"}, {4, "BG2 (Mode 7) only"}, {8 | 4, "BG2 only, polygons hidden"},
    };
    for (int c = 0; c < 3; c++) {
        m->pln_reg[1] = cases[c].layers;
        t0 = clock();
        for (int f = 0; f < frames; f++) { planes_vsync(m); m->back ^= 1; }
        ms = (double)(clock() - t0) * 1000.0 / CLOCKS_PER_SEC / frames;
        printf("  bench: %s: %.3f ms per frame\n", cases[c].what, ms);
    }
    m->pln_reg[1] = 0;
    t0 = clock();
    for (int f = 0; f < frames; f++) { planes_vsync(m); m->back ^= 1; }
    ms = (double)(clock() - t0) * 1000.0 / CLOCKS_PER_SEC / frames;
    printf("  bench: polygons over a backdrop table only: %.3f ms per frame\n", ms);
}

int main(void) {
    m = mei_create();
    if (!m) return 1;
    test_registers();
    test_off();
    test_holes();
    test_auto_erase();
    test_backdrop();
    test_tile_plane();
    test_tile_sizes();
    test_affine();
    test_affine_16();
    test_perspective();
    test_line_channels();
    test_priority();
    test_colour_math();
    test_colour_math_exact();
    test_reference_random();
    test_display_path();
    if (!getenv("MEI_NO_BENCH")) bench();
    mei_destroy(m);
    printf("test_planes: %d/%d checks passed\n", checks - fails, checks);
    return fails != 0;
}
