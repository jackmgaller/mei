/* GPU tests: packet walking, rasterization rules, pixel pipeline, faults, the depth test and
 * perspective (docs/RENDERING.md), and fog toward a colour (a proposal, docs/DECISIONS.md). */
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
    if (a_ != b_) { fails++; printf("FAIL %s:%d: %s == %lld, expected %lld\n", __FILE__, __LINE__, #a, a_, b_); } } while (0)

static Mei *m;
#define IMAGE 0x1000             /* the blank cart loaded for the tests that put packets in ROM */

static void blank_cart(void) {
    static const uint8_t blank[IMAGE];
    if (mei_load_cart(m, blank, sizeof blank)) { printf("FAIL: can't load a blank cart\n"); exit(1); }
}

static void setup(void) {
    mei_reset(m);
    memset(&m->fault, 0, sizeof m->fault);   /* mei_reset with no cart raises NO_CART */
    gpu_clear(m, 0);
}

/* A fresh frame that keeps VRAM (setup() clears textures and palettes with the rest). */
static void next_frame(void) {
    m->gpu_status = 0;
    gpu_clear(m, 0);
}

/* ---- packet building in RAM ---- */

static uint32_t pk_next = 0x1000, pk_prev, pk_first;

static void list_begin(void) { pk_next = 0x1000; pk_prev = 0; pk_first = 0xFFFFFF; }

static uint32_t emit(uint32_t type, int n, ...) {
    uint32_t a = pk_next;
    wr32(m->ram + a, type << 24 | 0xFFFFFF);
    va_list ap;
    va_start(ap, n);
    for (int i = 0; i < n; i++) wr32(m->ram + a + 4 + 4 * i, va_arg(ap, uint32_t));
    va_end(ap);
    if (pk_prev) wr32(m->ram + pk_prev, (rd32(m->ram + pk_prev) & 0xFF000000u) | a);
    else pk_first = a;
    pk_prev = a;
    pk_next += 4 * (n + 1);
    return a;
}

static void list_draw(void) { gpu_draw_list(m, pk_first); }

static uint32_t P(int x, int y) { return (uint32_t)(uint16_t)x | (uint32_t)(uint16_t)y << 16; }
static uint32_t RGB(int r, int g, int b) { return (uint32_t)r | (uint32_t)g << 8 | (uint32_t)b << 16; }
static uint32_t UV(int u, int v) { return (uint32_t)u | (uint32_t)v << 8; }
static uint32_t TEX0(int u, int v, int slot, int four, int pal) {
    return UV(u, v) | (uint32_t)slot << 16 | (uint32_t)four << 20 | (uint32_t)pal << 24;
}

static uint8_t *back(void) { return m->vram + (gpu_back_addr(m) - VRAM_BASE); }
static uint16_t px(int x, int y) { return rd16(back() + (y * MEI_W + x) * 2); }
static int count_nonzero(void) {
    int n = 0;
    for (int i = 0; i < MEI_W * MEI_H; i++) n += rd16(back() + i * 2) != 0;
    return n;
}
static uint16_t C15(int r, int g, int b) { return (uint16_t)(r | g << 5 | b << 10); }
static void set_pal(int i, uint16_t c) { wr16(m->vram + (PALETTE_ADDR - VRAM_BASE) + i * 2, c); }
static uint8_t *slot_ptr(int s) { return m->vram + (TEXTURE_ADDR - VRAM_BASE) + s * TEXTURE_SLOT_BYTES; }

/* ---- independent reference rasterizer (brute force over the whole screen) ---- */

typedef struct { int x, y, c[5]; } RV;   /* c: r, g, b, u, v */
static const int DM[4][4] = {{-4, 0, -3, 1}, {2, -2, 3, -1}, {-3, 1, -4, 0}, {3, -1, 2, -2}};

static long long fdiv(long long n, long long d) { long long q = n / d; return (n % d && ((n < 0) != (d < 0))) ? q - 1 : q; }
static long long edge(const RV *a, const RV *b, int x, int y) {
    return (long long)(b->x - a->x) * (y - a->y) - (long long)(b->y - a->y) * (x - a->x);
}
static int top_left(const RV *a, const RV *b) { int dy = b->y - a->y, dx = b->x - a->x; return dy < 0 || (dy == 0 && dx > 0); }
static int clampi(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }

/* The texture window the reference applies (bits 16-31 of vertex 1's texture word, 0: none). */
static uint32_t ref_win;
static int ref_wrap(int t, uint32_t w) {   /* w: 3-bit size code, 5-bit origin / 8 */
    return (w & 7) ? (int)(((uint32_t)t % (4u << (w & 7)) + (w >> 3 & 31) * 8) & 255) : t;
}

/* flags as in the packet type; tex: slot/four/pal; colour used flat from v[0] unless Gouraud */
static void ref_tri(uint16_t *fb, RV a, RV b, RV c, int flags, int mode, int dither, int slot, int four, int pal) {
    long long area = edge(&a, &b, c.x, c.y);
    if (area == 0) return;
    if (area < 0) { RV t = b; b = c; c = t; area = -area; }
    RV *V[3] = {&a, &b, &c};
    for (int y = 0; y < MEI_H; y++)
        for (int x = 0; x < MEI_W; x++) {
            long long w[3];
            int in = 1;
            for (int i = 0; i < 3; i++) {
                const RV *e0 = V[(i + 1) % 3], *e1 = V[(i + 2) % 3];
                w[i] = edge(e0, e1, x, y);
                if (w[i] < 0 || (w[i] == 0 && !top_left(e0, e1))) in = 0;
            }
            if (!in) continue;
            int at[5];
            for (int k = 0; k < 5; k++) at[k] = (int)fdiv(w[0] * V[0]->c[k] + w[1] * V[1]->c[k] + w[2] * V[2]->c[k], area);
            int col[3];
            for (int k = 0; k < 3; k++) col[k] = (flags & 1) ? at[k] : a.c[k];
            if (flags & 2) {
                int u = ref_wrap(at[3], ref_win & 0xFF), v = ref_wrap(at[4], ref_win >> 8 & 0xFF), idx;
                if (four) { int byt = slot_ptr(slot)[v * 128 + u / 2]; idx = (u & 1) ? byt >> 4 : byt & 15; idx += pal * 16; if ((idx & 15) == 0) continue; }
                else { idx = m->vram[(TEXTURE_ADDR - VRAM_BASE) + ((slot * 0x8000 + v * 256 + u) & 0x7FFFF)]; if (!idx) continue; idx += (pal & 15) * 256; }
                uint16_t t = rd16(m->vram + (PALETTE_ADDR - VRAM_BASE) + idx * 2);
                for (int k = 0; k < 3; k++) {
                    int c5 = (t >> (5 * k)) & 31, e = (c5 << 3) | (c5 >> 2);
                    col[k] = e * col[k] / 128 > 255 ? 255 : e * col[k] / 128;
                }
            }
            for (int k = 0; k < 3; k++) col[k] = (dither ? clampi(col[k] + DM[y & 3][x & 3], 0, 255) : col[k]) >> 3;
            uint16_t *d = &fb[y * MEI_W + x];
            if (flags & 8)
                for (int k = 0; k < 3; k++) {
                    int bg = (*d >> (5 * k)) & 31, f = col[k];
                    int r = mode == 0 ? (bg + f) / 2 : mode == 1 ? bg + f : mode == 2 ? bg - f : bg + f / 4;
                    col[k] = clampi(r, 0, 31);
                }
            *d = (uint16_t)(col[0] | col[1] << 5 | col[2] << 10);
        }
}

static uint32_t rng = 12345;
static int rnd(int lo, int hi) { rng = rng * 1103515245u + 12345u; return lo + (int)((rng >> 8) % (uint32_t)(hi - lo + 1)); }

/* ---- tests ---- */

static void test_flat_coverage(void) {
    setup(); list_begin();
    emit(0x20, 4, RGB(255, 255, 255), P(0, 0), P(10, 0), P(0, 10));
    list_draw();
    CHECK_EQ(count_nonzero(), 55);   /* rows 0..9 hold 10..1 pixels; hypotenuse excluded */
    CHECK_EQ(px(0, 0), 0x7FFF);
    CHECK_EQ(px(9, 0), 0x7FFF);
    CHECK_EQ(px(10, 0), 0);
    CHECK_EQ(px(5, 5), 0);           /* on the bottom-right edge */
    CHECK_EQ(px(4, 5), 0x7FFF);

    setup(); list_begin();           /* opposite winding draws identically */
    emit(0x20, 4, RGB(255, 255, 255), P(0, 0), P(0, 10), P(10, 0));
    list_draw();
    CHECK_EQ(count_nonzero(), 55);

    setup(); list_begin();           /* axis-aligned quad covers exactly w*h */
    emit(0x24, 5, RGB(255, 0, 0), P(20, 30), P(70, 30), P(20, 50), P(70, 50));
    list_draw();
    CHECK_EQ(count_nonzero(), 50 * 20);
    CHECK_EQ(px(20, 30), 31);
    CHECK_EQ(px(69, 49), 31);
    CHECK_EQ(px(70, 49), 0);
    CHECK_EQ(px(69, 50), 0);
    CHECK_EQ(m->gpu_status, 2);      /* a quad counts two triangles */

    setup(); list_begin();           /* zero-area triangles draw nothing */
    emit(0x20, 4, RGB(255, 255, 255), P(5, 5), P(50, 50), P(100, 100));
    emit(0x20, 4, RGB(255, 255, 255), P(5, 5), P(5, 5), P(5, 5));
    list_draw();
    CHECK_EQ(count_nonzero(), 0);
}

/* A jittered mesh drawn additively (+1 per channel) over black: every pixel
 * inside must be exactly 1, so no seam pixel is drawn twice or skipped. */
static void test_shared_edges(void) {
    setup(); list_begin();
    enum { GX = 9, GY = 7 };
    int vx[GY][GX], vy[GY][GX];
    for (int j = 0; j < GY; j++)
        for (int i = 0; i < GX; i++) {
            vx[j][i] = 20 + i * 35; vy[j][i] = 10 + j * 35;
            if (i > 0 && i < GX - 1) vx[j][i] += rnd(-5, 5);
            if (j > 0 && j < GY - 1) vy[j][i] += rnd(-5, 5);
        }
    for (int j = 0; j < GY - 1; j++)
        for (int i = 0; i < GX - 1; i++) {
            if ((i + j) & 1)   /* mix quads and pairs of triangles with both windings */
                emit(0x2C, 5, RGB(8, 8, 8) | 1u << 24, P(vx[j][i], vy[j][i]), P(vx[j][i + 1], vy[j][i + 1]),
                     P(vx[j + 1][i], vy[j + 1][i]), P(vx[j + 1][i + 1], vy[j + 1][i + 1]));
            else {
                emit(0x28, 4, RGB(8, 8, 8) | 1u << 24, P(vx[j][i], vy[j][i]), P(vx[j + 1][i + 1], vy[j + 1][i + 1]), P(vx[j][i + 1], vy[j][i + 1]));
                emit(0x28, 4, RGB(8, 8, 8) | 1u << 24, P(vx[j][i], vy[j][i]), P(vx[j + 1][i], vy[j + 1][i]), P(vx[j + 1][i + 1], vy[j + 1][i + 1]));
            }
        }
    list_draw();
    int bad = 0, x1 = 20 + (GX - 1) * 35, y1 = 10 + (GY - 1) * 35;
    for (int y = 0; y < MEI_H; y++)
        for (int x = 0; x < MEI_W; x++) {
            int inside = x >= 20 && x < x1 && y >= 10 && y < y1;
            bad += px(x, y) != (inside ? C15(1, 1, 1) : 0);
        }
    CHECK_EQ(bad, 0);

    /* A triangle fan around a centre point, both windings. */
    setup(); list_begin();
    int cx = 160, cy = 120, ring[8][2] = {{160, 20}, {250, 40}, {300, 120}, {240, 210}, {160, 230}, {70, 200}, {20, 120}, {60, 30}};
    for (int i = 0; i < 8; i++) {
        int *a = ring[i], *b = ring[(i + 1) % 8];
        if (i & 1) emit(0x28, 4, RGB(8, 8, 8) | 1u << 24, P(cx, cy), P(a[0], a[1]), P(b[0], b[1]));
        else emit(0x28, 4, RGB(8, 8, 8) | 1u << 24, P(b[0], b[1]), P(a[0], a[1]), P(cx, cy));
    }
    list_draw();
    int twice = 0;
    for (int i = 0; i < MEI_W * MEI_H; i++) twice += rd16(back() + 2 * i) > C15(1, 1, 1);
    CHECK_EQ(twice, 0);
    CHECK_EQ(px(cx, cy), C15(1, 1, 1));
    CHECK_EQ(px(cx + 1, cy), C15(1, 1, 1));
    CHECK_EQ(px(cx, cy - 50), C15(1, 1, 1));
}

static void test_gouraud(void) {
    /* The drawn (top-left) vertex of each triangle shows exactly its colour. */
    int cols[3][3] = {{255, 0, 0}, {0, 255, 0}, {0, 0, 255}};
    for (int k = 0; k < 3; k++) {
        setup(); list_begin();
        int *c0 = cols[k], *c1 = cols[(k + 1) % 3], *c2 = cols[(k + 2) % 3];
        emit(0x21, 6, RGB(c0[0], c0[1], c0[2]), P(10, 10), RGB(c1[0], c1[1], c1[2]), P(200, 10), RGB(c2[0], c2[1], c2[2]), P(10, 200));
        list_draw();
        CHECK_EQ(px(10, 10), C15(c0[0] >> 3, c0[1] >> 3, c0[2] >> 3));
        /* next to the far vertices the colour is within one 5-bit step of the vertex */
        uint16_t p1 = px(198, 10), p2 = px(10, 198);
        CHECK(((p1 >> (5 * ((k + 1) % 3))) & 31) >= 30);
        CHECK(((p2 >> (5 * ((k + 2) % 3))) & 31) >= 30);
    }
    /* Gradient along a horizontal edge: 0 at x=0 to 255 at x=255. */
    setup(); list_begin();
    emit(0x25, 8, RGB(0, 0, 0), P(0, 0), RGB(255, 0, 0), P(255, 0), RGB(0, 0, 0), P(0, 4), RGB(255, 0, 0), P(255, 4));
    list_draw();
    int ok = 1;
    for (int x = 0; x < 255; x++) ok &= px(x, 0) == (x >> 3);
    CHECK(ok);
}

static void test_reference_random(void) {
    /* Random triangles of every flag combination against the brute-force reference. */
    static uint16_t ref[MEI_W * MEI_H];
    setup();
    for (int i = 0; i < 0x10000; i++) slot_ptr(0)[i] = (uint8_t)(rnd(0, 255) * (rnd(0, 7) != 0));
    for (int i = 0; i < 0x8000; i++) slot_ptr(15)[i] = (uint8_t)rnd(0, 255);
    for (int i = 0; i < 4096; i++) set_pal(i, (uint16_t)rnd(0, 0x7FFF));
    int mismatch = 0;
    for (int iter = 0; iter < 400; iter++) {
        int flags = rnd(0, 15) & ~4, mode = rnd(0, 3), dither = rnd(0, 1);
        int four = rnd(0, 1), slot = four ? 15 : rnd(0, 1) * 15, pal = four ? rnd(0, 255) : rnd(0, 15);
        int big = iter % 4 == 0;
        RV v[3];
        for (int i = 0; i < 3; i++) {
            v[i].x = big ? rnd(-2000, 2000) : rnd(-40, 360);
            v[i].y = big ? rnd(-2000, 2000) : rnd(-40, 280);
            for (int k = 0; k < 5; k++) v[i].c[k] = rnd(0, 3) == 0 ? 255 : rnd(0, 255);
        }
        if (iter % 50 == 0) v[0].x = -32768, v[1].y = 32767;
        next_frame();                   /* (not setup(): it would clear the textures) */
        gpu_clear(m, (uint32_t)rnd(0, 0x7FFF));
        m->gpu_ctrl = (uint32_t)dither;
        memcpy(ref, back(), sizeof ref);
        list_begin();
        uint32_t w[10];
        int n = 0;
        for (int i = 0; i < 3; i++) {
            if (i == 0 || (flags & 1)) w[n++] = RGB(v[i].c[0], v[i].c[1], v[i].c[2]) | (i == 0 ? (uint32_t)mode << 24 : 0);
            w[n++] = P(v[i].x, v[i].y);
            if (flags & 2) w[n++] = i == 0 ? TEX0(v[i].c[3], v[i].c[4], slot, four, pal) : UV(v[i].c[3], v[i].c[4]);
        }
        uint32_t a = emit((uint32_t)(0x20 | flags), 0);
        for (int i = 0; i < n; i++) wr32(m->ram + a + 4 + 4 * i, w[i]);
        list_draw();
        ref_tri(ref, v[0], v[1], v[2], flags, mode, dither, slot, four, pal);
        if (memcmp(ref, back(), sizeof ref)) {
            if (!mismatch) printf("  reference mismatch: iter %d flags %x\n", iter, flags);
            mismatch++;
        }
    }
    CHECK_EQ(mismatch, 0);
}

static void test_long_thin(void) {
    /* Long, thin triangles at every angle crossing the screen (floors and walls seen at a
     * grazing angle), against the brute-force reference: u, v and colour interpolation
     * along slivers up to 2,047 pixels long within vproj's range and 60,000 beyond it. */
    static uint16_t ref[MEI_W * MEI_H];
    setup();
    for (int i = 0; i < 0x10000; i++) slot_ptr(1)[i] = (uint8_t)(1 + (i * 7 + (i >> 8) * 13) % 255);
    for (int i = 0; i < 256; i++) set_pal(i, (uint16_t)rnd(0, 0x7FFF));
    int mismatch = 0;
    for (int iter = 0; iter < 240; iter++) {
        int lim = iter % 3 == 2 ? 32767 : 1023;
        long long len = iter % 3 == 0 ? rnd(80, 600) : iter % 3 == 1 ? rnd(600, 2047) : rnd(2000, 60000);
        long long dx = rnd(-1000, 1000), dy = rnd(-1000, 1000), w = rnd(0, 1) ? rnd(0, 300) : rnd(0, 4000);
        if (dx * dx + dy * dy < 250000) dx = dx < 0 ? -1000 : 1000;     /* |d| about 500..1414 */
        long long cx = rnd(0, 319), cy = rnd(0, 239), t0 = -rnd(0, 1000) * len / 1000, tm = t0 + rnd(0, 1000) * len / 1000;
        long long px[3] = {cx + dx * t0 / 1000, cx + dx * (t0 + len) / 1000, cx + (dx * tm - dy * w / 100) / 1000};
        long long py[3] = {cy + dy * t0 / 1000, cy + dy * (t0 + len) / 1000, cy + (dy * tm + dx * w / 100) / 1000};
        RV v[3];
        for (int i = 0; i < 3; i++) {
            v[i].x = (int)(px[i] < -lim - 1 ? -lim - 1 : px[i] > lim ? lim : px[i]);
            v[i].y = (int)(py[i] < -lim - 1 ? -lim - 1 : py[i] > lim ? lim : py[i]);
            for (int k = 0; k < 5; k++) v[i].c[k] = rnd(0, 3) == 0 ? 255 * rnd(0, 1) : rnd(0, 255);
        }
        next_frame();
        m->gpu_ctrl = 1;
        memcpy(ref, back(), sizeof ref);
        list_begin();
        emit(0x23, 9, RGB(v[0].c[0], v[0].c[1], v[0].c[2]), P(v[0].x, v[0].y), TEX0(v[0].c[3], v[0].c[4], 1, 0, 0),
             RGB(v[1].c[0], v[1].c[1], v[1].c[2]), P(v[1].x, v[1].y), UV(v[1].c[3], v[1].c[4]),
             RGB(v[2].c[0], v[2].c[1], v[2].c[2]), P(v[2].x, v[2].y), UV(v[2].c[3], v[2].c[4]));
        list_draw();
        ref_tri(ref, v[0], v[1], v[2], 3, 0, 1, 1, 0, 0);
        if (memcmp(ref, back(), sizeof ref)) {
            if (!mismatch) printf("  long thin triangle mismatch: iter %d\n", iter);
            mismatch++;
        }
    }
    CHECK_EQ(mismatch, 0);
}

static void test_textures(void) {
    /* 4-bit: slot 2, palette 5 (colours 80-95). Texel (u,v) = (u + v) & 15. */
    setup();
    gpu_clear(m, 0x1234);
    for (int v = 0; v < 256; v++)
        for (int u = 0; u < 256; u += 2)
            slot_ptr(2)[v * 128 + u / 2] = (uint8_t)(((u + v) & 15) | ((u + 1 + v) & 15) << 4);
    for (int i = 0; i < 16; i++) set_pal(80 + i, C15(i * 2, 31 - i, i));
    list_begin();
    emit(0x26, 9, RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 2, 1, 5), P(32, 0), UV(32, 0), P(0, 32), UV(0, 32), P(32, 32), UV(32, 32));
    list_draw();
    int ok = 1;
    for (int y = 0; y < 32; y++)
        for (int x = 0; x < 32; x++) {
            int idx = (x + y) & 15;
            ok &= px(x, y) == (idx ? C15(idx * 2, 31 - idx, idx) : 0x1234);
        }
    CHECK(ok);

    /* 8-bit: slot 4 spans slots 4-5; palette 3 (colours 768-1023). Rows 120-140 cross the slot boundary. */
    setup();
    gpu_clear(m, 0x0421);
    for (int v = 0; v < 256; v++)
        for (int u = 0; u < 256; u++) slot_ptr(4)[v * 256 + u] = (uint8_t)((u * 7 + v * 3) & 255);
    for (int i = 0; i < 256; i++) set_pal(768 + i, (uint16_t)((i * 131 + 7) & 0x7FFF));
    list_begin();
    emit(0x2E, 9, RGB(128, 128, 128) | 0u << 24, P(10, 10), TEX0(50, 120, 4, 0, 3), P(60, 10), UV(100, 120), P(10, 30), UV(50, 140), P(60, 30), UV(100, 140));
    /* semi-transparent average over 0x0421 background: index 0 still skipped */
    list_draw();
    ok = 1;
    for (int y = 10; y < 30; y++)
        for (int x = 10; x < 60; x++) {
            int u = x - 10 + 50, v = y - 10 + 120, idx = (u * 7 + v * 3) & 255;
            uint16_t t = (uint16_t)((idx * 131 + 7) & 0x7FFF);
            uint16_t want = idx ? C15(((t & 31) + 1) >> 1, (((t >> 5) & 31) + 1) >> 1, (((t >> 10) & 31) + 1) >> 1) : 0x0421;
            ok &= px(x, y) == want;
        }
    CHECK(ok);
    CHECK_EQ(slot_ptr(5) - slot_ptr(4), 0x8000);

    /* Tint: 128 = unchanged, 255 nearly doubles and clamps, 64 halves. */
    setup();
    set_pal(16 + 3, C15(10, 20, 31));     /* 4-bit palette 1 starts at colour 16 */
    memset(slot_ptr(0), 0x33, 128 * 4);   /* rows 0-3 all index 3 */
    list_begin();
    emit(0x26, 9, RGB(128, 255, 64), P(0, 0), TEX0(0, 0, 0, 1, 1), P(4, 0), UV(4, 0), P(0, 4), UV(0, 4), P(4, 4), UV(4, 4));
    list_draw();
    /* r: 82*128/128 = 82 -> 10; g: 165*255/128 = 328 -> 255 -> 31; b: 255*64/128 = 127 -> 15 */
    CHECK_EQ(px(1, 1), C15(10, 31, 15));
    setup();
    set_pal(16 + 3, C15(10, 10, 10));
    memset(slot_ptr(0), 0x33, 128 * 4);
    list_begin();
    emit(0x26, 9, RGB(255, 200, 0), P(0, 0), TEX0(0, 0, 0, 1, 1), P(4, 0), UV(4, 0), P(0, 4), UV(0, 4), P(4, 4), UV(4, 4));
    list_draw();
    /* 82*255/128 = 163 -> 20; 82*200/128 = 128 -> 16; 0 -> 0 */
    CHECK_EQ(px(2, 2), C15(20, 16, 0));

    /* 8-bit palette field: only 0-15 are meaningful (masked). */
    setup();
    memset(slot_ptr(6), 9, 0x10000);
    set_pal(2 * 256 + 9, C15(3, 4, 5));
    list_begin();
    emit(0x26, 9, RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 6, 0, 0x12), P(4, 0), UV(4, 0), P(0, 4), UV(0, 4), P(4, 4), UV(4, 4));
    list_draw();
    CHECK_EQ(px(0, 0), C15(3, 4, 5));
}

/* Window halfword for vertex 1's texture word: size codes 0-7 (k: 4 << k texels), origins in texels. */
static uint32_t WIN(int usize, int uorg, int vsize, int vorg) {
    return ((uint32_t)usize | (uint32_t)(uorg / 8) << 3 | (uint32_t)vsize << 8 | (uint32_t)(vorg / 8) << 11) << 16;
}

static void test_texture_window(void) {
    /* 4-bit, slot 3, palette 5: a 16x16 tile at (32, 64) in a slot of index 15, repeated over a
     * 128x100 flat quad (u 0-128, v 0-100). The same quad without a window samples the slot. */
    setup();
    memset(slot_ptr(3), 0xFF, TEXTURE_SLOT_BYTES);
    for (int y = 0; y < 16; y++)
        for (int x = 0; x < 16; x++) {
            uint8_t *b = &slot_ptr(3)[(64 + y) * 128 + (32 + x) / 2];
            int c = 1 + (x + 2 * y) % 14;
            *b = (uint8_t)((x & 1) ? (*b & 0x0F) | c << 4 : (*b & 0xF0) | c);
        }
    for (int i = 0; i < 16; i++) set_pal(80 + i, C15(i * 2, 31 - i * 2, i * 7 % 32));
    list_begin();
    emit(0x26, 9, RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 3, 1, 5), P(128, 0), UV(128, 0) | WIN(2, 32, 2, 64),
         P(0, 100), UV(0, 100), P(128, 100), UV(128, 100));
    emit(0x26, 9, RGB(128, 128, 128), P(0, 120), TEX0(0, 0, 3, 1, 5), P(128, 120), UV(128, 0),
         P(0, 220), UV(0, 100), P(128, 220), UV(128, 100));
    list_draw();
    int bad = 0, bad_plain = 0;
    for (int y = 0; y < 100; y++)
        for (int x = 0; x < 128; x++) {
            int c = 1 + (x % 16 + 2 * (y % 16)) % 14;
            bad += px(x, y) != C15(c * 2, 31 - c * 2, c * 7 % 32);
            int in = x >= 32 && x < 48 && y >= 64 && y < 80, cp = in ? 1 + ((x - 32) + 2 * (y - 64)) % 14 : 15;
            bad_plain += px(x, 120 + y) != C15(cp * 2, 31 - cp * 2, cp * 7 % 32);
        }
    CHECK_EQ(bad, 0);
    CHECK_EQ(bad_plain, 0);

    /* 8-bit, slots 6-7 (rows 128-255 are slot 7), palette 2: a 32x32 tile at (200, 160),
     * Gouraud quad. Then the window's origin + size past 256 wraps: 64 wide at u 224 samples
     * u 224-255 then 0-31; 16 high at v 248 samples rows 248-255 then 0-7. */
    setup();
    for (int v = 0; v < 256; v++)
        for (int u = 0; u < 256; u++) slot_ptr(6)[v * 256 + u] = (uint8_t)(1 + (3 * u + 5 * v) % 200);
    for (int i = 0; i < 256; i++) set_pal(512 + i, (uint16_t)((i * 97 + 5) & 0x7FFF));
    list_begin();
    emit(0x27, 12, RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 6, 0, 2), RGB(128, 128, 128), P(150, 0), UV(150, 0) | WIN(3, 200, 3, 160),
         RGB(128, 128, 128), P(0, 120), UV(0, 120), RGB(128, 128, 128), P(150, 120), UV(150, 120));
    emit(0x26, 9, RGB(128, 128, 128), P(160, 0), TEX0(0, 0, 6, 0, 2), P(310, 0), UV(150, 0) | WIN(4, 224, 2, 248),
         P(160, 120), UV(0, 120), P(310, 120), UV(150, 120));
    list_draw();
    int bad8 = 0, badw = 0;
    for (int y = 0; y < 120; y++)
        for (int x = 0; x < 150; x++) {
            int u = 200 + x % 32, v = 160 + y % 32, i = 1 + (3 * u + 5 * v) % 200;
            bad8 += px(x, y) != ((i * 97 + 5) & 0x7FFF);
            u = (224 + x % 64) & 255, v = (248 + y % 16) & 255, i = 1 + (3 * u + 5 * v) % 200;
            badw += px(160 + x, y) != ((i * 97 + 5) & 0x7FFF);
        }
    CHECK_EQ(bad8, 0);
    CHECK_EQ(badw, 0);

    /* Semi-transparent, with palette index 0 inside the window: a 8x8 4-bit tile at (8, 0)
     * whose even columns are index 0. Those pixels keep the background; the rest average. */
    setup();
    gpu_clear(m, C15(20, 10, 4));
    for (int y = 0; y < 8; y++) memset(&slot_ptr(1)[y * 128 + 4], 0x70, 4);   /* (u even: 0, odd: 7) */
    set_pal(7, C15(10, 30, 0));
    list_begin();
    emit(0x2E, 9, RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 1, 1, 0), P(40, 0), UV(40, 0) | WIN(1, 8, 1, 0),
         P(0, 20), UV(0, 20), P(40, 20), UV(40, 20));
    list_draw();
    int bads = 0;
    for (int y = 0; y < 20; y++)
        for (int x = 0; x < 40; x++) bads += px(x, y) != ((x & 1) ? C15(15, 20, 2) : C15(20, 10, 4));
    CHECK_EQ(bads, 0);
    CHECK_EQ(px(40, 0), C15(20, 10, 4));

    /* Every flag combination, triangles and quads, random windows (codes 0-7, any origin)
     * against the brute-force reference. The window is read from vertex 1 only; the high bits
     * of the other vertices' words stay as before (vertex 0: slot, depth, palette). */
    static uint16_t ref[MEI_W * MEI_H];
    setup();
    for (int i = 0; i < 0x10000; i++) slot_ptr(0)[i] = (uint8_t)(rnd(0, 255) * (rnd(0, 7) != 0));
    for (int i = 0; i < 0x8000; i++) slot_ptr(15)[i] = (uint8_t)rnd(0, 255);
    for (int i = 0; i < 4096; i++) set_pal(i, (uint16_t)rnd(0, 0x7FFF));
    int mismatch = 0;
    for (int iter = 0; iter < 400; iter++) {
        int flags = 2 | rnd(0, 15), mode = rnd(0, 3), dither = rnd(0, 1), quad = flags >> 2 & 1, nv = quad ? 4 : 3;
        int four = rnd(0, 1), slot = four ? 15 : rnd(0, 1) * 15, pal = four ? rnd(0, 255) : rnd(0, 15);
        uint32_t win = (uint32_t)rnd(0, 0xFFFF);
        if (iter % 4 == 0) win &= 0xFF00;   /* u only, v only, or neither */
        if (iter % 4 == 1) win &= 0x00FF;
        RV v[4];
        int big = iter % 5 == 0;           /* huge triangles take the exact (slow) span path */
        for (int i = 0; i < nv; i++) {
            v[i].x = big ? rnd(-2000, 2000) : rnd(-40, 360);
            v[i].y = big ? rnd(-2000, 2000) : rnd(-40, 280);
            for (int k = 0; k < 5; k++) v[i].c[k] = rnd(0, 255);
            if (!(flags & 1)) memcpy(v[i].c, v[0].c, 3 * sizeof v[0].c[0]);   /* flat: vertex 0's colour */
        }
        next_frame();
        gpu_clear(m, (uint32_t)rnd(0, 0x7FFF));
        m->gpu_ctrl = (uint32_t)dither;
        memcpy(ref, back(), sizeof ref);
        list_begin();
        uint32_t w[12];
        int n = 0;
        for (int i = 0; i < nv; i++) {
            if (i == 0 || (flags & 1)) w[n++] = RGB(v[i].c[0], v[i].c[1], v[i].c[2]) | (i == 0 ? (uint32_t)mode << 24 : 0);
            w[n++] = P(v[i].x, v[i].y);
            w[n++] = i == 0 ? TEX0(v[i].c[3], v[i].c[4], slot, four, pal) : UV(v[i].c[3], v[i].c[4]) | (i == 1 ? win << 16 : 0);
        }
        uint32_t a = emit((uint32_t)(0x20 | flags), 0);
        for (int i = 0; i < n; i++) wr32(m->ram + a + 4 + 4 * i, w[i]);
        list_draw();
        ref_win = win;
        ref_tri(ref, v[0], v[1], v[2], flags, mode, dither, slot, four, pal);
        if (quad) ref_tri(ref, v[1], v[2], v[3], flags, mode, dither, slot, four, pal);
        ref_win = 0;
        if (memcmp(ref, back(), sizeof ref)) {
            if (!mismatch) printf("  window reference mismatch: iter %d flags %x window %04x\n", iter, flags, win);
            mismatch++;
        }
    }
    CHECK_EQ(mismatch, 0);
}

static void test_dither(void) {
    for (int on = 0; on < 2; on++) {
        int vals[4] = {100, 254, 2, 128};
        for (int k = 0; k < 4; k++) {
            setup();
            m->gpu_ctrl = (uint32_t)on;
            int c = vals[k];
            list_begin();
            emit(0x24, 5, RGB(c, c, 0), P(0, 0), P(8, 0), P(0, 8), P(8, 8));
            list_draw();
            int ok = 1;
            for (int y = 0; y < 8; y++)
                for (int x = 0; x < 8; x++) {
                    int e = (on ? clampi(c + DM[y & 3][x & 3], 0, 255) : c) >> 3;
                    int e0 = (on ? clampi(DM[y & 3][x & 3], 0, 255) : 0) >> 3;
                    ok &= px(x, y) == C15(e, e, e0);
                }
            CHECK(ok);
        }
    }
    /* With dither on, 102 produces both 12 and 13 across the 4x4 cell. */
    setup();
    m->gpu_ctrl = 1;
    list_begin();
    emit(0x24, 5, RGB(102, 0, 0), P(0, 0), P(4, 0), P(0, 4), P(4, 4));
    list_draw();
    int n12 = 0, n13 = 0;
    for (int y = 0; y < 4; y++)
        for (int x = 0; x < 4; x++) { n12 += px(x, y) == 12; n13 += px(x, y) == 13; }
    CHECK_EQ(n12 + n13, 16);
    CHECK(n12 > 0 && n13 > 0);
    CHECK_EQ(px(0, 0), 12);   /* 102 - 4 = 98 -> 12 */
    CHECK_EQ(px(2, 1), 13);   /* 102 + 3 = 105 -> 13 */
    CHECK_EQ(px(0, 3), 13);   /* 102 + 3 */
    CHECK_EQ(px(3, 0), 12);   /* 102 + 1 = 103 -> 12 */
    CHECK_EQ(px(1, 1), 12);   /* 102 - 2 = 100 -> 12 */
}

static void test_blend(void) {
    /* Background (20,10,25); polygon (128,192,32) -> (16,24,4). */
    uint16_t want[4] = {C15(18, 17, 14), C15(31, 31, 29), C15(4, 0, 21), C15(24, 16, 26)};
    for (int mode = 0; mode < 4; mode++) {
        setup();
        gpu_clear(m, C15(20, 10, 25));
        list_begin();
        emit(0x2C, 5, RGB(128, 192, 32) | (uint32_t)mode << 24, P(0, 0), P(4, 0), P(0, 4), P(4, 4));
        list_draw();
        CHECK_EQ(px(1, 1), want[mode]);
        CHECK_EQ(px(5, 1), C15(20, 10, 25));
    }
    /* Opaque packets ignore the blend bits. */
    setup();
    gpu_clear(m, C15(20, 10, 25));
    list_begin();
    emit(0x24, 5, RGB(128, 192, 32) | 1u << 24, P(0, 0), P(4, 0), P(0, 4), P(4, 4));
    list_draw();
    CHECK_EQ(px(1, 1), C15(16, 24, 4));
    /* Pixels are written with bit 15 clear even over a background that had it set. */
    setup();
    for (int i = 0; i < 16; i++) wr16(back() + i * 2, 0xFFFF);
    list_begin();
    emit(0x2C, 5, RGB(0, 0, 0) | 1u << 24, P(0, 0), P(4, 0), P(0, 4), P(4, 4));
    list_draw();
    CHECK_EQ(px(0, 0), 0x7FFF);
}

static void test_clipping(void) {
    setup(); list_begin();
    emit(0x20, 4, RGB(255, 255, 255), P(-500, 10), P(100, 10), P(100, 200));
    list_draw();
    static uint16_t ref[MEI_W * MEI_H];
    memset(ref, 0, sizeof ref);
    RV a = {-500, 10, {255, 255, 255, 0, 0}}, b = {100, 10, {255, 255, 255, 0, 0}}, c = {100, 200, {255, 255, 255, 0, 0}};
    ref_tri(ref, a, b, c, 0, 0, 0, 0, 0, 0);
    CHECK(memcmp(ref, back(), sizeof ref) == 0);
    CHECK(count_nonzero() > 0);
    CHECK_EQ(px(0, 10), 0x7FFF);

    setup(); list_begin();   /* extreme coordinates cover the whole screen */
    emit(0x20, 4, RGB(255, 255, 255), P(-32768, -32768), P(32767, -32768), P(0, 32767));
    list_draw();
    CHECK_EQ(count_nonzero(), MEI_W * MEI_H);

    setup(); list_begin();   /* entirely off-screen */
    emit(0x24, 5, RGB(255, 255, 255), P(-100, -100), P(-10, -100), P(-100, -10), P(-10, -10));
    emit(0x24, 5, RGB(255, 255, 255), P(320, 0), P(400, 0), P(320, 240), P(400, 240));
    emit(0x24, 5, RGB(255, 255, 255), P(0, 240), P(320, 240), P(0, 300), P(320, 300));
    list_draw();
    CHECK_EQ(count_nonzero(), 0);
    CHECK_EQ(m->gpu_status, 6);      /* off-screen triangles still count */

    setup(); list_begin();   /* full-screen quad covers exactly the screen */
    emit(0x24, 5, RGB(255, 255, 255), P(0, 0), P(320, 0), P(0, 240), P(320, 240));
    list_draw();
    CHECK_EQ(count_nonzero(), MEI_W * MEI_H);
}

static void test_limits(void) {
    CHECK_EQ(GPU_TRI_LIMIT, 4000);
    setup(); list_begin();
    for (int i = 0; i < GPU_TRI_LIMIT / 2; i++) emit(0x24, 5, RGB(255, 255, 255), P(0, 0), P(1, 0), P(0, 1), P(1, 1));
    CHECK_EQ(m->gpu_status, 0);
    list_draw();
    CHECK_EQ(m->gpu_status, 4000);
    uint32_t st = 0;
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_STATUS, &st), 0);
    CHECK_EQ(st, 4000);                                  /* the count fits bits 0-15 */
    list_begin();
    emit(0x20, 4, RGB(255, 255, 255), P(10, 10), P(20, 10), P(10, 20));
    list_draw();   /* second GPU_DRAW in the same frame keeps counting */
    CHECK_EQ(m->gpu_status, 4000 | GPU_STATUS_DROPPED);
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_STATUS, &st), 0);
    CHECK_EQ(st, 4000 | GPU_STATUS_DROPPED);
    CHECK_EQ(m->gstat.tris, 4000);
    CHECK_EQ(m->gstat.tris_dropped, 1);
    CHECK_EQ(px(10, 10), 0);
    gpu_vsync(m);
    CHECK_EQ(m->gpu_status, 0);

    /* A quad whose first half is the 4,000th triangle draws only that half. */
    setup(); list_begin();
    for (int i = 0; i < GPU_TRI_LIMIT - 1; i++) emit(0x20, 4, RGB(0, 0, 0), P(300, 200), P(301, 200), P(300, 201));
    emit(0x24, 5, RGB(255, 255, 255), P(0, 0), P(10, 0), P(0, 10), P(10, 10));
    list_draw();
    CHECK_EQ(m->gpu_status, 4000 | GPU_STATUS_DROPPED);
    CHECK_EQ(px(1, 1), 0x7FFF);   /* triangle 0-1-2 */
    CHECK_EQ(px(8, 8), 0);        /* triangle 1-2-3 dropped */
}

/* The cost table (docs/DECISIONS.md, "GPU budget"): 40 a triangle, 1 a flat or Gouraud pixel,
 * x2 textured, x2 semi-transparent, 38,400 a clear. */
static void test_cost_model(void) {
    static const uint32_t per_px[8] = {1, 1, 2, 2, 2, 2, 4, 4};
    for (int k = 0; k < 8; k++) CHECK_EQ(gpu_pixel_cycles(k), per_px[k]);
    CHECK_EQ(GPU_CYCLES_TRI, 40);
    CHECK_EQ(GPU_CYCLES_CLEAR, 38400);
    CHECK_EQ(MEI_GPU_CYCLES_PER_FRAME, 2000000);

    setup();
    CHECK_EQ(m->gpu_cycles, 38400);                     /* setup() clears once */
    gpu_clear(m, 0);
    CHECK_EQ(m->gpu_cycles, 2 * 38400);

    /* the 10x10 right triangle covers 55 pixels, the 10x10 quad 100 */
    struct { uint32_t type; int n; uint32_t w[9]; uint32_t cost; } draws[] = {
        {0x20, 4, {RGB(255, 255, 255), P(0, 0), P(10, 0), P(0, 10)}, 40 + 55},
        {0x21, 6, {RGB(255, 0, 0), P(0, 0), RGB(0, 255, 0), P(10, 0), RGB(0, 0, 255), P(0, 10)}, 40 + 55},
        {0x22, 7, {RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 0, 0, 0), P(10, 0), UV(9, 0), P(0, 10), UV(0, 9)}, 40 + 110},
        {0x28, 4, {RGB(255, 255, 255), P(0, 0), P(10, 0), P(0, 10)}, 40 + 110},
        {0x29, 6, {RGB(255, 0, 0), P(0, 0), RGB(0, 255, 0), P(10, 0), RGB(0, 0, 255), P(0, 10)}, 40 + 110},
        {0x2A, 7, {RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 0, 0, 0), P(10, 0), UV(9, 0), P(0, 10), UV(0, 9)}, 40 + 220},
        {0x2B, 9, {RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 0, 0, 0), RGB(9, 9, 9), P(10, 0), UV(9, 0),
                   RGB(200, 9, 9), P(0, 10), UV(0, 9)}, 40 + 220},
        {0x24, 5, {RGB(255, 255, 255), P(0, 0), P(10, 0), P(0, 10), P(10, 10)}, 2 * 40 + 100},
        {0x20, 4, {RGB(255, 255, 255), P(5, 5), P(5, 5), P(9, 9)}, 40},               /* zero area */
        {0x20, 4, {RGB(255, 255, 255), P(-50, -50), P(-40, -50), P(-50, -40)}, 40},   /* off screen */
        {0x24, 5, {RGB(255, 255, 255), P(0, 0), P(320, 0), P(0, 240), P(320, 240)}, 2 * 40 + 76800},
    };
    for (unsigned i = 0; i < sizeof draws / sizeof *draws; i++) {
        setup(); list_begin();
        m->gpu_cycles = 0;
        uint32_t a = emit(draws[i].type, draws[i].n, 0, 0, 0, 0, 0, 0, 0, 0, 0);
        for (int k = 0; k < draws[i].n; k++) wr32(m->ram + a + 4 + 4 * k, draws[i].w[k]);
        list_draw();
        CHECK_EQ(m->gpu_cycles, draws[i].cost);
    }

    /* dropped triangles cost nothing */
    setup(); list_begin();
    for (int i = 0; i < GPU_TRI_LIMIT; i++) emit(0x20, 4, RGB(0, 0, 0), P(300, 200), P(301, 200), P(300, 201));
    m->gpu_cycles = 0;
    list_draw();
    CHECK_EQ(m->gpu_cycles, GPU_TRI_LIMIT * (40 + 1));
    list_draw();
    CHECK_EQ(m->gpu_cycles, GPU_TRI_LIMIT * (40 + 1));
    CHECK_EQ(m->gstat.tris_dropped, GPU_TRI_LIMIT);
}

/* ---- the GPU budget: lag when a frame's modelled cycles exceed 2,000,000 a tick ---- */

#define V_COUNT  0x100   /* frames the CPU has started */
#define V_CLEARS 0x104   /* GPU_CLEARs per frame */
#define V_LIST   0x108   /* packet list per frame */
#define V_SPIN   0x10C   /* busy-loop iterations per frame */
#define V_SEEN   0x8000  /* frame n's reads: PAD1 at V_SEEN + 4n, GPU_LOAD +0x400, GPU_TICKS +0x800, GPU_LAG +0xC00 */

static const char *lag_src =
    "        lui  r9, 0x3FC0\n"           /* r9 = 0xFF0000 */
    "frame:  lw   r1, [r0+0x100]\n"
    "        addi r1, r1, 1\n"
    "        sw   r1, [r0+0x100]\n"
    "        shli r3, r1, 2\n"
    "        lw   r2, [r9+0x200]\n"       /* PAD1 */
    "        sw   r2, [r3+0x8000]\n"
    "        lw   r2, [r9+0x14]\n"        /* GPU_LOAD */
    "        sw   r2, [r3+0x8400]\n"
    "        lw   r2, [r9+0x18]\n"        /* GPU_TICKS */
    "        sw   r2, [r3+0x8800]\n"
    "        lw   r2, [r9+0x1C]\n"        /* GPU_LAG */
    "        sw   r2, [r3+0x8C00]\n"
    "        lw   r4, [r0+0x104]\n"
    ".clr:   beq  r4, r0, .draw\n"
    "        sw   r0, [r9+4]\n"           /* GPU_CLEAR */
    "        addi r4, r4, -1\n"
    "        jmp  .clr\n"
    ".draw:  lw   r5, [r0+0x108]\n"
    "        sw   r5, [r9+0]\n"           /* GPU_DRAW */
    "        lw   r6, [r0+0x10C]\n"
    ".spin:  beq  r6, r0, .end\n"
    "        addi r6, r6, -1\n"
    "        jmp  .spin\n"
    ".end:   vsync\n"
    "        jmp  frame\n";

static uint32_t ram(uint32_t a) { return rd32(m->ram + a); }
/* what frame n read: 0 PAD1, 1 GPU_LOAD, 2 GPU_TICKS, 3 GPU_LAG */
static uint32_t seen(int frame, int what) { return ram(V_SEEN + 0x400 * (uint32_t)what + 4 * (uint32_t)frame); }

static int lag_load(void) {
    MeiAsmResult res;
    if (mei_assemble(lag_src, "lag.s", &res) != 0) { printf("asm: %s\n", res.error); CHECK(0); return 0; }
    CHECK_EQ(mei_load_cart(m, res.rom, res.rom_len), 0);
    mei_asm_free(&res);
    wr32(m->ram + V_LIST, 0xFFFFFF);
    return 1;
}

/* Runs n ticks with PAD1 pending as 0x100 + the tick number; returns bit i = tick i presented. */
static uint32_t ticks(int n, int *tick) {
    uint32_t bits = 0;
    for (int i = 0; i < n; i++, (*tick)++) {
        MeiPadInput in = {0x100u + (uint32_t)*tick, 0, 0};
        mei_set_pad(m, 0, &in);
        bits |= (uint32_t)mei_run_frame(m) << i;
    }
    return bits;
}

static void test_budget(void) {
    int t = 0;
    /* Under budget: every tick presents; the registers read 0 before the first present. */
    if (!lag_load()) return;
    wr32(m->ram + V_CLEARS, 52);                        /* 1,996,800 */
    CHECK_EQ(ticks(4, &t), 0xF);
    CHECK_EQ(ram(V_COUNT), 4);
    CHECK_EQ(seen(1, 1), 0); CHECK_EQ(seen(1, 2), 0); CHECK_EQ(seen(1, 3), 0);
    CHECK_EQ(seen(2, 0), 0x100);                        /* latched at the first present (tick 0) */
    CHECK_EQ(seen(2, 1), 1996800); CHECK_EQ(seen(2, 2), 1); CHECK_EQ(seen(2, 3), 0);
    CHECK_EQ(seen(4, 0), 0x102);
    CHECK_EQ(mei_gpu_stats(m)->gpu_cycles, 1996800);
    CHECK_EQ(mei_gpu_stats(m)->ticks, 1);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 0);

    /* Exactly the budget presents on time; 40 cycles more is a tick late. */
    list_begin();
    for (int i = 0; i < 80; i++) emit(0x20, 4, RGB(0, 0, 0), P(5, 5), P(5, 5), P(5, 5));   /* empty: 40 each */
    wr32(m->ram + V_LIST, pk_first);
    CHECK_EQ(ticks(2, &t), 0x3);
    CHECK_EQ(mei_gpu_stats(m)->gpu_cycles, 2000000);
    CHECK_EQ(mei_gpu_stats(m)->ticks, 1);
    emit(0x20, 4, RGB(0, 0, 0), P(5, 5), P(5, 5), P(5, 5));
    CHECK_EQ(ticks(2, &t), 0x2);                        /* the frame drawn in the first tick waits */
    CHECK_EQ(mei_gpu_stats(m)->gpu_cycles, 2000040);
    CHECK_EQ(mei_gpu_stats(m)->ticks, 2);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 1);
    CHECK_EQ(m->gpu_lag, 1);

    /* Twice the budget: presented one tick late. The CPU does not run in the wait, and the
     * pads latch only at the present. */
    if (!lag_load()) return;
    t = 0;
    wr32(m->ram + V_CLEARS, 104);                       /* 3,993,600 */
    CHECK_EQ(ticks(1, &t), 0);                          /* frame 1 drawn, over budget */
    CHECK_EQ(ram(V_COUNT), 1);
    uint32_t pc = m->pc, frame0 = m->frame;
    const uint16_t *front = mei_display(m);
    CHECK_EQ(ticks(1, &t), 1);                          /* the wait tick presents */
    CHECK_EQ(ram(V_COUNT), 1);                          /* the CPU did not run */
    CHECK_EQ(m->pc, pc);
    CHECK_EQ(m->frame, frame0 + 1);                     /* FRAME counts ticks */
    CHECK(mei_display(m) != front);                     /* the buffers swapped at the present */
    CHECK_EQ(ticks(1, &t), 0);                          /* frame 2 drawn in tick 2 */
    CHECK_EQ(ram(V_COUNT), 2);
    CHECK_EQ(seen(2, 0), 0x101);                        /* the pad of the present tick, not 0x100 */
    CHECK_EQ(seen(2, 1), 3993600);
    CHECK_EQ(seen(2, 2), 2);
    CHECK_EQ(seen(2, 3), 1);
    CHECK_EQ(ticks(5, &t), 0x15);                       /* ticks 3-7: presents at 3, 5, 7 */
    CHECK_EQ(ram(V_COUNT), 4);
    CHECK_EQ(seen(4, 0), 0x105);
    CHECK_EQ(seen(4, 3), 3);
    CHECK_EQ(m->gpu_lag, 4);
    CHECK_EQ(mei_gpu_stats(m)->ticks, 2);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 1);
    CHECK_EQ(mei_gpu_stats(m)->cpu_cycles < MEI_CYCLES_PER_FRAME, 1);

    /* Three times: two ticks late. */
    if (!lag_load()) return;
    t = 0;
    wr32(m->ram + V_CLEARS, 156);                       /* 5,990,400 */
    CHECK_EQ(ticks(9, &t), 0x124);                      /* presents at ticks 2, 5, 8 */
    CHECK_EQ(ram(V_COUNT), 3);
    CHECK_EQ(seen(2, 0), 0x102);
    CHECK_EQ(seen(3, 0), 0x105);
    CHECK_EQ(seen(3, 1), 5990400);
    CHECK_EQ(seen(3, 2), 3);
    CHECK_EQ(seen(3, 3), 4);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 2);
    wr32(m->ram + V_CLEARS, 157);                       /* 6,028,800: three ticks late */
    CHECK_EQ(ticks(4, &t), 0x8);                        /* frame 4 (from tick 9) at tick 12 */
    CHECK_EQ(mei_gpu_stats(m)->ticks, 4);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 3);
    uint32_t lag = 0, load = 0, tk = 0;
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_LAG, &lag), 0);
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_LOAD, &load), 0);
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_TICKS, &tk), 0);
    CHECK_EQ(lag, 6 + 3);
    CHECK_EQ(load, 6028800);
    CHECK_EQ(tk, 4);
    CHECK_EQ(bus_write32(m, IO_BASE + IO_GPU_LOAD, 0), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_READ_ONLY);
    memset(&m->fault, 0, sizeof m->fault);

    /* CPU overrun composes: a frame whose CPU work spans two ticks has 4,000,000 GPU cycles. */
    if (!lag_load()) return;
    t = 0;
    wr32(m->ram + V_CLEARS, 104);                       /* 3,993,600 */
    wr32(m->ram + V_SPIN, MEI_CYCLES_PER_FRAME * 2 / 5); /* about 1.2 budgets of CPU cycles */
    CHECK_EQ(ticks(4, &t), 0xA);                        /* late for the CPU only */
    CHECK_EQ(mei_gpu_stats(m)->ticks, 2);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 0);
    CHECK_EQ(mei_gpu_stats(m)->cpu_cycles > MEI_CYCLES_PER_FRAME && mei_gpu_stats(m)->cpu_cycles < 2 * MEI_CYCLES_PER_FRAME, 1);
    CHECK_EQ(m->gpu_lag, 0);
    wr32(m->ram + V_CLEARS, 105);                       /* 4,032,000: one tick more */
    CHECK_EQ(ticks(6, &t), 0x24);                       /* frames from ticks 4 and 7 at ticks 6 and 9 */
    CHECK_EQ(mei_gpu_stats(m)->ticks, 3);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 1);
    CHECK_EQ(seen(3, 2), 2);                            /* frame 3 read frame 2's 2 ticks */
    CHECK_EQ(seen(4, 2), 3);                            /* frame 4 read frame 3's 3 */

    /* A reset clears the wait and the registers. */
    wr32(m->ram + V_CLEARS, 400);
    wr32(m->ram + V_SPIN, 0);
    ticks(2, &t);
    mei_reset(m);
    CHECK_EQ(m->gpu_wait, 0);
    CHECK_EQ(m->gpu_lag, 0);
    CHECK_EQ(m->gpu_cycles, 0);
    CHECK_EQ(mei_gpu_stats(m)->gpu_cycles, 0);
}

static void test_list_walk(void) {
    /* Unknown types are skipped; empty packets just link. */
    setup(); list_begin();
    emit(0x00, 0);
    emit(0x10, 3, 0xDEADBEEF, 0, 0);
    emit(0x40, 0);         /* (0x30-0x3F are polygons with depth: test_depth) */
    emit(0x20, 4, RGB(255, 0, 0), P(0, 0), P(10, 0), P(0, 10));
    emit(0xFF, 0);
    emit(0x1F, 0);
    emit(0x24, 5, RGB(0, 255, 0), P(20, 0), P(30, 0), P(20, 10), P(30, 10));
    list_draw();
    CHECK_EQ(m->fault.kind, MEI_FAULT_NONE);
    CHECK_EQ(px(1, 1), 31);
    CHECK_EQ(px(21, 1), 31 << 5);
    CHECK_EQ(m->gpu_status, 3);

    /* Empty list. */
    setup();
    gpu_draw_list(m, 0xFFFFFF);
    CHECK_EQ(m->fault.kind, MEI_FAULT_NONE);

    /* List in ROM (as the first packet: a next address has 24 bits, so it reaches only RAM). */
    blank_cart();
    setup();
    wr32(m->rom + 0x100, 0x20u << 24 | 0xFFFFFF);
    wr32(m->rom + 0x104, RGB(0, 0, 255));
    wr32(m->rom + 0x108, P(0, 0));
    wr32(m->rom + 0x10C, P(10, 0));
    wr32(m->rom + 0x110, P(0, 10));
    gpu_draw_list(m, ROM_BASE + 0x100);
    CHECK_EQ(m->fault.kind, MEI_FAULT_NONE);
    CHECK_EQ(px(0, 0), 31 << 10);
    memset(m->rom, 0, 0x200);

    /* Exactly 65,536 packets is fine; 65,537 faults. */
    for (int len = GPU_LIST_LIMIT; len <= GPU_LIST_LIMIT + 1; len++) {
        setup();
        for (int i = 0; i < len; i++) wr32(m->ram + 0x10000 + 4 * i, i == len - 1 ? 0xFFFFFF : 0x10000u + 4 * (i + 1));
        gpu_draw_list(m, 0x10000);
        CHECK_EQ(m->fault.kind, len == GPU_LIST_LIMIT ? MEI_FAULT_NONE : MEI_FAULT_BAD_PACKET_LIST);
    }
    setup();                 /* a cycle faults instead of hanging */
    wr32(m->ram + 0x100, 0x104);
    wr32(m->ram + 0x104, 0x100);
    gpu_draw_list(m, 0x100);
    CHECK_EQ(m->fault.kind, MEI_FAULT_BAD_PACKET_LIST);

    /* Bad next addresses. Packets before the bad one are drawn. */
    struct { uint32_t next; MeiFaultKind kind; } bad[] = {
        {0x400000, MEI_FAULT_UNMAPPED}, {0xFF0000, MEI_FAULT_UNMAPPED}, {0x1002, MEI_FAULT_MISALIGNED},
        {0x200000, MEI_FAULT_UNMAPPED}, {0xFFFFFE, MEI_FAULT_UNMAPPED},   /* 0x200000: the old ROM base */
    };
    for (unsigned i = 0; i < sizeof bad / sizeof *bad; i++) {
        setup(); list_begin();
        uint32_t a = emit(0x20, 4, RGB(255, 255, 255), P(0, 0), P(10, 0), P(0, 10));
        wr32(m->ram + a, 0x20u << 24 | bad[i].next);
        m->pc = ROM_BASE + 0x40;
        list_draw();
        CHECK_EQ(m->fault.kind, bad[i].kind);
        CHECK_EQ(m->fault.addr, bad[i].next);
        CHECK_EQ(m->fault.pc, ROM_BASE + 0x40);
        CHECK_EQ(px(1, 1), 0x7FFF);
    }
    setup();                 /* first address itself bad */
    gpu_draw_list(m, 0x500000);
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    setup();                 /* polygon running off the end of RAM (no longer into ROM) */
    wr32(m->ram + RAM_SIZE - 8, 0x20u << 24 | 0xFFFFFF);
    gpu_draw_list(m, RAM_SIZE - 8);
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    CHECK_EQ(m->fault.addr, RAM_SIZE);
    setup();                 /* past the cart image the ROM window reads 0: a degenerate triangle */
    wr32(m->rom + IMAGE - 8, 0x20u << 24 | 0xFFFFFF);
    gpu_draw_list(m, ROM_BASE + IMAGE - 8);
    CHECK_EQ(m->fault.kind, MEI_FAULT_NONE);
    CHECK_EQ(m->gpu_status & 0xFFFF, 1);
    setup();                 /* either side of the window is unmapped */
    gpu_draw_list(m, ROM_BASE + ROM_WINDOW);
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    setup();
    gpu_draw_list(m, ROM_BASE - 4);
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    memset(m->rom + IMAGE - 8, 0, 8);
}

static void test_buffers(void) {
    setup();
    CHECK_EQ(gpu_back_addr(m), FB_A_ADDR);
    gpu_clear(m, 0xFFFF);
    CHECK_EQ(px(0, 0), 0x7FFF);
    CHECK_EQ(px(319, 239), 0x7FFF);
    CHECK_EQ(rd16(m->vram + (FB_B_ADDR - VRAM_BASE)), 0);   /* front untouched */
    CHECK_EQ(rd16(m->vram + (FB_A_ADDR - VRAM_BASE) + FB_BYTES), 0);   /* B's first pixel is right after A */
    list_begin();
    emit(0x20, 4, RGB(0, 0, 0), P(0, 0), P(10, 0), P(0, 10));
    list_draw();
    m->gpu_ctrl = 1;
    gpu_vsync(m);
    CHECK_EQ(gpu_back_addr(m), FB_B_ADDR);
    CHECK_EQ(m->gpu_ctrl, 1);
    const uint16_t *f = gpu_front(m);
    CHECK(f == (const uint16_t *)(void *)(m->vram + (FB_A_ADDR - VRAM_BASE)));
    CHECK_EQ(f[0], 0);
    CHECK_EQ(f[20], 0x7FFF);
    CHECK_EQ(f[319 + 239 * 320], 0x7FFF);
    gpu_clear(m, 0x1F);
    CHECK_EQ(f[20], 0x7FFF);
    gpu_vsync(m);
    CHECK_EQ(gpu_back_addr(m), FB_A_ADDR);
    CHECK_EQ(gpu_front(m)[5], 0x1F);
    CHECK(mei_display(m) == gpu_front(m));
}

static void test_error_screen(void) {
    setup();
    m->fault.kind = MEI_FAULT_UNMAPPED;
    m->fault.pc = 0x200010;
    m->fault.addr = 0xABCDEF;
    m->r[5] = 0x12345678;
    gpu_render_error_screen(m);
    int distinct = 0, white = 0;
    uint16_t first = m->error_screen[0];
    for (int i = 0; i < MEI_W * MEI_H; i++) {
        distinct += m->error_screen[i] != first;
        white += m->error_screen[i] == 0x7FFF;
        if (m->error_screen[i] & 0x8000) { CHECK(0); break; }
    }
    CHECK(distinct > 1000);
    CHECK(white > 500);
    m->fault.pc = 0xFFFFFFF0;   /* unreadable pc must not crash */
    gpu_render_error_screen(m);
    if (getenv("MEI_DUMP")) {
        FILE *fp = fopen(getenv("MEI_DUMP"), "wb");
        if (fp) {
            m->fault.pc = 0x200010;
            wr32(m->rom + 0x10, 0x40400005);
            gpu_render_error_screen(m);
            fprintf(fp, "P6\n320 240\n255\n");
            for (int i = 0; i < MEI_W * MEI_H; i++) {
                uint16_t p = m->error_screen[i];
                fputc((p & 31) << 3, fp); fputc(((p >> 5) & 31) << 3, fp); fputc(((p >> 10) & 31) << 3, fp);
            }
            fclose(fp);
        }
    }
}

/* ---- packets with depth: the depth test and perspective (docs/RENDERING.md) ---- */

static uint16_t zat(int x, int y) { return m->zbuf[y * MEI_W + x]; }
static uint32_t W16(double w) { return (uint32_t)(int32_t)(w * 65536.0); }   /* a view depth, 16.16 */

/* The reference, written from RENDERING.md and brute force like ref_tri: the vertex reciprocal,
 * the key, the test, the decal offset and the perspective spans. It counts what the cost table
 * charges for. */
static long long ref_recip(int32_t w) { return w >= 4096 ? (1LL << 40) / w : 1LL << 28; }
static uint32_t ref_key(long long q) {
    if (q < 4096) return 0;
    int e = 0;
    while ((q >> (e + 12)) > 1) e++;
    return e > 15 ? 0xFFFF : (uint32_t)e << 12 | (uint32_t)((q >> e) & 0xFFF);
}
static long long ref_fails, ref_divs, ref_inside;

typedef struct { int flags, mode, dither, slot, four, pal, ztest, zoff; int fog; uint32_t fogcol, frange; } RefZ;

/* Fog toward a colour (the proposal in DECISIONS.md): the factor of a vertex at view depth w,
 * 0-256, from GPU_FOG_RANGE (bits 0-15 near in 1/16 units, bits 16-31 the scale). */
static int ref_fogf(int32_t w, uint32_t range) {
    long long d = w <= 0 ? 0 : w / 4096, n = range & 0xFFFF, sc = range >> 16;
    if (d > 65535) d = 65535;
    if (d <= n) return 0;
    long long f = (d - n) * sc / 4096;
    return f > 256 ? 256 : (int)f;
}

static void ref_tri_z(uint16_t *fb, uint16_t *zb, RV a, RV b, RV c, const int32_t wv[3], const RefZ *o) {
    long long rw[3] = {ref_recip(wv[0]), ref_recip(wv[1]), ref_recip(wv[2])};
    long long fv[3] = {0, 0, 0};
    if (o->fog) for (int i = 0; i < 3; i++) fv[i] = ref_fogf(wv[i], o->frange);
    long long area = edge(&a, &b, c.x, c.y);
    if (area == 0) return;
    if (area < 0) {
        RV t = b; b = c; c = t; long long r = rw[1]; rw[1] = rw[2]; rw[2] = r; area = -area;
        r = fv[1]; fv[1] = fv[2]; fv[2] = r;
    }
    RV *V[3] = {&a, &b, &c};
    int flags = o->flags, persp = 0;
    long long q[3];
    if (flags & 2) {
        long long mx = rw[0];
        for (int i = 1; i < 3; i++) if (rw[i] > mx) mx = rw[i];
        int s = 0;
        while ((mx >> s) > 65535) s++;
        for (int i = 0; i < 3; i++) { q[i] = rw[i] >> s; if (q[i] < 1) q[i] = 1; }
        persp = q[0] != q[1] || q[1] != q[2];
    }
    for (int y = 0; y < MEI_H; y++) {
        int xl = -1, xr = -2;
        long long W[MEI_W][3];
        for (int x = 0; x < MEI_W; x++) {
            int in = 1;
            for (int i = 0; i < 3; i++) {
                const RV *e0 = V[(i + 1) % 3], *e1 = V[(i + 2) % 3];
                W[x][i] = edge(e0, e1, x, y);
                if (W[x][i] < 0 || (W[x][i] == 0 && !top_left(e0, e1))) in = 0;
            }
            if (in) { if (xl < 0) xl = x; xr = x; }
        }
        if (xl < 0) continue;
        long long S[2][MEI_W];   /* s at the divide points, 16.16 */
        if (persp) {
            ref_divs += 1 + (xr - xl + 15) / 16;
            for (int x = xl; x <= xr; x++) {
                if ((x - xl) % 16 && x != xr) continue;
                __int128 Q = 0, U = 0, Vv = 0;
                for (int i = 0; i < 3; i++) {
                    Q += (__int128)q[i] * W[x][i];
                    U += (__int128)q[i] * V[i]->c[3] * W[x][i];
                    Vv += (__int128)q[i] * V[i]->c[4] * W[x][i];
                }
                S[0][x] = (long long)((U << 16) / Q);
                S[1][x] = (long long)((Vv << 16) / Q);
            }
        }
        for (int x = xl; x <= xr; x++) {
            ref_inside++;
            int at[5];
            for (int k = 0; k < 5; k++) at[k] = (int)fdiv(W[x][0] * V[0]->c[k] + W[x][1] * V[1]->c[k] + W[x][2] * V[2]->c[k], area);
            if (persp) {
                for (int t = 0; t < 2; t++) {
                    int p0 = xl + (x - xl) / 16 * 16, p1 = p0 + 16 < xr ? p0 + 16 : xr;
                    long long s = (x == p0 || x == xr) ? S[t][x] : S[t][p0] + (x - p0) * ((S[t][p1] - S[t][p0]) / (p1 - p0));
                    at[3 + t] = (int)(s >> 16);
                }
            }
            uint16_t *zp = &zb[y * MEI_W + x];
            uint32_t key = 0;
            if (o->ztest) {
                long long z = fdiv(W[x][0] * rw[0] + W[x][1] * rw[1] + W[x][2] * rw[2], area);
                key = ref_key(z) + (uint32_t)o->zoff;
                if (key > 0xFFFF) key = 0xFFFF;
                if (key < *zp) { ref_fails++; continue; }
            }
            int col[3];
            for (int k = 0; k < 3; k++) col[k] = (flags & 1) ? at[k] : a.c[k];
            if (flags & 2) {
                int u = ref_wrap(at[3], ref_win & 0xFF), v = ref_wrap(at[4], ref_win >> 8 & 0xFF), idx;
                if (o->four) { int byt = slot_ptr(o->slot)[v * 128 + u / 2]; idx = (u & 1) ? byt >> 4 : byt & 15; idx += o->pal * 16; if ((idx & 15) == 0) continue; }
                else { idx = m->vram[(TEXTURE_ADDR - VRAM_BASE) + ((o->slot * 0x8000 + v * 256 + u) & 0x7FFFF)]; if (!idx) continue; idx += (o->pal & 15) * 256; }
                uint16_t t = rd16(m->vram + (PALETTE_ADDR - VRAM_BASE) + idx * 2);
                for (int k = 0; k < 3; k++) {
                    int c5 = (t >> (5 * k)) & 31, e = (c5 << 3) | (c5 >> 2);
                    col[k] = e * col[k] / 128 > 255 ? 255 : e * col[k] / 128;
                }
            }
            if (o->fog) {   /* toward the fog colour (black for additive and subtractive pixels) */
                long long fz = fdiv(W[x][0] * fv[0] + W[x][1] * fv[1] + W[x][2] * fv[2], area);
                int black = (flags & 8) && o->mode != 0;
                for (int k = 0; k < 3; k++) {
                    int t = black ? 0 : (int)(o->fogcol >> (8 * k) & 0xFF);
                    col[k] += (int)fdiv((long long)(t - col[k]) * fz, 256);
                }
            }
            for (int k = 0; k < 3; k++) col[k] = (o->dither ? clampi(col[k] + DM[y & 3][x & 3], 0, 255) : col[k]) >> 3;
            uint16_t *d = &fb[y * MEI_W + x];
            if (flags & 8)
                for (int k = 0; k < 3; k++) {
                    int bg = (*d >> (5 * k)) & 31, f = col[k], mo = o->mode;
                    int r = mo == 0 ? (bg + f) / 2 : mo == 1 ? bg + f : mo == 2 ? bg - f : bg + f / 4;
                    col[k] = clampi(r, 0, 31);
                }
            *d = (uint16_t)(col[0] | col[1] << 5 | col[2] << 10);
            if (o->ztest && !(flags & 8)) *zp = (uint16_t)key;
        }
    }
}

/* Emits a triangle packet with depth (type 0x30 | flags, flags without the quad bit). */
static uint32_t emit_tri_z(int flags, const RV v[3], const int32_t wv[3], const RefZ *o) {
    uint32_t w[13];
    int n = 0;
    for (int i = 0; i < 3; i++) {
        if (i == 0 || (flags & 1)) w[n++] = RGB(v[i].c[0], v[i].c[1], v[i].c[2]) | (i == 0 ? (uint32_t)o->mode << 24 | (uint32_t)o->zoff << 27 : 0);
        w[n++] = P(v[i].x, v[i].y);
        if (flags & 2) w[n++] = i == 0 ? TEX0(v[i].c[3], v[i].c[4], o->slot, o->four, o->pal) : UV(v[i].c[3], v[i].c[4]) | (i == 1 ? ref_win << 16 : 0);
    }
    for (int i = 0; i < 3; i++) w[n++] = (uint32_t)wv[i];
    uint32_t a = emit((uint32_t)(0x30 | flags), 0);
    for (int i = 0; i < n; i++) wr32(m->ram + a + 4 + 4 * i, w[i]);
    pk_next = a + 4 + 4 * (uint32_t)n;
    return a;
}

static void test_depth_registers(void) {
    setup();
    uint32_t v = 7;
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_DEPTH, &v), 0);
    CHECK_EQ(v, 0);                                     /* off at reset */
    CHECK_EQ(bus_write32(m, IO_BASE + IO_GPU_DEPTH, 0xFFFFFFFF), 0);
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_DEPTH, &v), 0);
    CHECK_EQ(v, 1);                                     /* bits 1-31 reserved, read 0 */
    CHECK_EQ(bus_write32(m, IO_BASE + IO_GPU_DEPTH, 2), 0);
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_DEPTH, &v), 0);
    CHECK_EQ(v, 0);

    m->gpu_cycles = 0;
    CHECK_EQ(bus_write32(m, IO_BASE + IO_GPU_ZCLEAR, 0xABCD1234), 0);
    CHECK_EQ(zat(0, 0), 0x1234);                        /* bits 0-15 */
    CHECK_EQ(zat(319, 239), 0x1234);
    CHECK_EQ(m->gpu_cycles, 38400);
    CHECK_EQ(GPU_CYCLES_ZCLEAR, 38400);
    CHECK_EQ(m->gstat.zclears, 1);
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_ZCLEAR, &v), 0);
    CHECK_EQ(v, 0);                                     /* write-only: reads 0 */

    gpu_clear(m, 0x1F);                                 /* GPU_CLEAR and vsync leave it alone */
    gpu_vsync(m);
    CHECK_EQ(zat(160, 120), 0x1234);
    CHECK_EQ(bus_read8(m, IO_BASE + IO_GPU_DEPTH, &v, 0), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_IO_WIDTH);
    memset(&m->fault, 0, sizeof m->fault);
    CHECK_EQ(bus_read32(m, IO_BASE + 0x30, &v), -1);    /* 0xFF0030-0xFF00FF stay unmapped (0x28, 0x2C: fog) */
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    memset(&m->fault, 0, sizeof m->fault);

    bus_write32(m, IO_BASE + IO_GPU_DEPTH, 1);
    mei_reset(m);                                       /* a reset clears both */
    memset(&m->fault, 0, sizeof m->fault);
    CHECK_EQ(zat(160, 120), 0);
    CHECK_EQ(m->gpu_depth, 0);
}

/* The vertex reciprocal and the key (golden values). */
static void test_depth_key(void) {
    struct { double w; uint16_t key; } g[] = {
        {1.0, 0xC000}, {2.0, 0xB000}, {128.0, 0x5000}, {3.0, 0xA555}, {0.5, 0xD000}, {1.0 / 16, 0xFFFF},
        {0.01, 0xFFFF}, {0.0, 0xFFFF}, {-5.0, 0xFFFF}, {4096.0, 0x0000}, {4095.0, 0x0001}, {30000.0, 0x0000},
        {1.5, 0xB555}, {100.0, 0x547A},
    };
    for (unsigned i = 0; i < sizeof g / sizeof *g; i++) {
        setup(); list_begin();
        bus_write32(m, IO_BASE + IO_GPU_DEPTH, 1);
        uint32_t w = W16(g[i].w);
        emit(0x30, 7, RGB(255, 0, 0), P(0, 0), P(8, 0), P(0, 8), w, w, w);
        list_draw();
        CHECK_EQ(zat(1, 1), g[i].key);
        CHECK_EQ(ref_key(ref_recip((int32_t)w)), g[i].key);
    }
    CHECK_EQ(ref_recip(0x7FFFFFFF), 512);               /* the farthest w */
    CHECK_EQ(ref_recip(4096), 1 << 28);                 /* 1/16: the nearest */
}

/* With GPU_DEPTH off, an untextured packet with depth draws exactly as the plain one, costs the
 * same and leaves the buffer alone; the depth words are read (and fault) like the others. */
static void test_depth_off(void) {
    static uint16_t ref[MEI_W * MEI_H];
    static const int types[8] = {0x0, 0x1, 0x4, 0x5, 0x8, 0x9, 0xC, 0xD};
    for (int t = 0; t < 8; t++) {
        int ty = types[t], gouraud = ty & 1, nv = (ty & 4) ? 4 : 3;
        uint32_t w[16];
        int n = 0;
        int pos[4][2] = {{10, 12}, {250, 30}, {40, 200}, {300, 220}};
        for (int i = 0; i < nv; i++) {
            if (i == 0 || gouraud) w[n++] = RGB(40 + 50 * i, 200 - 40 * i, 90) | (i == 0 ? 1u << 24 | 31u << 27 : 0);
            w[n++] = P(pos[i][0], pos[i][1]);
        }
        uint64_t cost[2];
        for (int depth = 0; depth < 2; depth++) {
            setup(); list_begin();
            gpu_clear(m, 0x1234);
            m->gpu_cycles = 0;
            uint32_t a = emit((uint32_t)(0x20 | depth << 4 | ty), 0);
            for (int i = 0; i < n; i++) wr32(m->ram + a + 4 + 4 * i, w[i]);
            if (depth) for (int i = 0; i < nv; i++) wr32(m->ram + a + 4 + 4 * (n + i), W16(1 + i));
            list_draw();
            cost[depth] = m->gpu_cycles;
            if (!depth) memcpy(ref, back(), sizeof ref);
            else {
                CHECK_EQ(memcmp(ref, back(), sizeof ref), 0);
                CHECK_EQ(zat(100, 100), 0);
                CHECK_EQ(m->gstat.tris_recip, 0);
                CHECK_EQ(m->gstat.px_ztest, 0);
            }
        }
        CHECK_EQ(cost[1], cost[0]);
    }
    /* the largest packet with depth, 0x3F, is 1 + 16 words: its last depth word past the end of
     * RAM faults there */
    setup();
    uint32_t a = RAM_SIZE - 4 * 16;
    wr32(m->ram + a, 0x3Fu << 24 | 0xFFFFFF);
    gpu_draw_list(m, a);
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    CHECK_EQ(m->fault.addr, RAM_SIZE);
    memset(m->ram + a, 0, 4 * 16);
    setup();
    a = RAM_SIZE - 4 * 17;
    wr32(m->ram + a, 0x3Fu << 24 | 0xFFFFFF);
    gpu_draw_list(m, a);
    CHECK_EQ(m->fault.kind, MEI_FAULT_NONE);
    memset(m->ram + a, 0, 4 * 17);
}

/* The test: nearer stays, ties go to the later packet, semi-transparent packets test but do not
 * write, texel 0 writes neither, plain packets are neither tested nor written, the decal offset. */
static void test_depth_test(void) {
    const uint32_t W1 = W16(1), W2 = W16(2), W4 = W16(4);
    setup(); list_begin();
    bus_write32(m, IO_BASE + IO_GPU_DEPTH, 1);
    m->gpu_cycles = 0;
    emit(0x34, 9, RGB(255, 0, 0), P(0, 0), P(20, 0), P(0, 20), P(20, 20), W1, W1, W1, W1);           /* red, w 1 */
    emit(0x34, 9, RGB(0, 255, 0), P(10, 10), P(30, 10), P(10, 30), P(30, 30), W2, W2, W2, W2);       /* green behind */
    list_draw();
    CHECK_EQ(px(15, 15), 31);
    CHECK_EQ(px(25, 25), 31 << 5);
    CHECK_EQ(px(25, 5), 0);
    CHECK_EQ(zat(15, 15), 0xC000);
    CHECK_EQ(zat(25, 25), 0xB000);
    CHECK_EQ(zat(25, 5), 0);
    CHECK_EQ(m->gstat.px_ztest, 800);
    CHECK_EQ(m->gstat.px_zfail, 100);
    CHECK_EQ(m->gstat.tris_recip, 4);
    /* 4 triangles at 40 + 24, 700 pixels at 1, 100 failed at 1 */
    CHECK_EQ(m->gpu_cycles, 4 * (40 + 24) + 700 + 100);

    /* a nearer packet drawn later wins; a tie goes to the later packet */
    list_begin();
    emit(0x34, 9, RGB(0, 0, 255), P(20, 20), P(40, 20), P(20, 40), P(40, 40), W1, W1, W1, W1);       /* blue, w 1 over green */
    emit(0x30, 7, RGB(255, 255, 0), P(0, 0), P(4, 0), P(0, 4), W1, W1, W1);                          /* yellow ties red */
    list_draw();
    CHECK_EQ(px(25, 25), 31 << 10);
    CHECK_EQ(zat(25, 25), 0xC000);
    CHECK_EQ(px(1, 1), 31 | 31 << 5);

    /* a plain packet is neither tested nor written */
    list_begin();
    emit(0x24, 5, RGB(255, 255, 255), P(12, 12), P(18, 12), P(12, 18), P(18, 18));
    list_draw();
    CHECK_EQ(px(13, 13), 0x7FFF);
    CHECK_EQ(zat(13, 13), 0xC000);

    /* semi-transparent: tested, never written */
    list_begin();
    emit(0x3C, 9, RGB(0, 0, 255), P(0, 0), P(50, 0), P(0, 50), P(50, 50), W4, W4, W4, W4);   /* average, behind */
    emit(0x3C, 9, RGB(0, 0, 255), P(44, 44), P(60, 44), P(44, 60), P(60, 60), W1, W1, W1, W1);
    list_draw();
    CHECK_EQ(px(5, 5), 31);                             /* red stays: the blend at w 4 failed */
    CHECK_EQ(px(45, 2), 15 << 10);                      /* over the empty background: blended */
    CHECK_EQ(zat(45, 2), 0);
    CHECK_EQ(px(55, 55), 15 << 10);
    CHECK_EQ(px(47, 47), 23 << 10);                     /* the two blends, both over nothing nearer */
    CHECK_EQ(zat(47, 47), 0);

    /* the decal offset (first colour word bits 27-31): a coplanar decal drawn after or before */
    setup(); list_begin();
    bus_write32(m, IO_BASE + IO_GPU_DEPTH, 1);
    emit(0x34, 9, RGB(255, 0, 0), P(0, 0), P(40, 0), P(0, 40), P(40, 40), W2, W2, W2, W2);           /* wall */
    emit(0x34, 9, RGB(0, 255, 0) | 2u << 27, P(10, 10), P(20, 10), P(10, 20), P(20, 20), W2, W2, W2, W2);   /* decal after */
    emit(0x34, 9, RGB(0, 0, 255) | 2u << 27, P(60, 0), P(70, 0), P(60, 10), P(70, 10), W2, W2, W2, W2);    /* decal before */
    emit(0x34, 9, RGB(255, 0, 0), P(50, 0), P(80, 0), P(50, 20), P(80, 20), W2, W2, W2, W2);          /* its wall */
    list_draw();
    CHECK_EQ(px(15, 15), 31 << 5);
    CHECK_EQ(zat(15, 15), 0xB002);                      /* written with its offset */
    CHECK_EQ(px(65, 5), 31 << 10);                      /* the wall after it failed */
    CHECK_EQ(px(75, 5), 31);
    CHECK_EQ(zat(75, 5), 0xB000);
    list_begin();                                       /* the offset saturates at 0xFFFF */
    emit(0x30, 7, RGB(255, 255, 255) | 31u << 27, P(100, 100), P(108, 100), P(100, 108), W16(0.01), W16(0.01), W16(0.01));
    list_draw();
    CHECK_EQ(zat(101, 101), 0xFFFF);

    /* texel 0: neither colour nor key written (and it still costs as a passing pixel) */
    setup(); list_begin();
    bus_write32(m, IO_BASE + IO_GPU_DEPTH, 1);
    memset(slot_ptr(3), 0, TEXTURE_SLOT_BYTES);
    for (int i = 0; i < 256 * 256; i++) slot_ptr(3)[i] = (uint8_t)((i & 1) ? 0 : 5);   /* odd u: transparent */
    set_pal(5, C15(31, 31, 31));
    m->gpu_cycles = 0;
    emit(0x32, 10, RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 3, 0, 0), P(10, 0), UV(10, 0), P(0, 10), UV(0, 10), W1, W1, W1);
    list_draw();
    CHECK_EQ(px(0, 1), 0x7FFF);
    CHECK_EQ(zat(0, 1), 0xC000);
    CHECK_EQ(px(1, 1), 0);
    CHECK_EQ(zat(1, 1), 0);
    CHECK_EQ(m->gpu_cycles, 40 + 24 + 55 * 2);

    /* a cleared value is a far limit: keys below it fail */
    setup(); list_begin();
    bus_write32(m, IO_BASE + IO_GPU_DEPTH, 1);
    bus_write32(m, IO_BASE + IO_GPU_ZCLEAR, 0xB000);    /* w 2 */
    emit(0x30, 7, RGB(255, 0, 0), P(0, 0), P(10, 0), P(0, 10), W4, W4, W4);
    emit(0x30, 7, RGB(0, 255, 0), P(20, 0), P(30, 0), P(20, 10), W2, W2, W2);
    list_draw();
    CHECK_EQ(px(1, 1), 0);
    CHECK_EQ(px(21, 1), 31 << 5);

    /* GPU_DEPTH is read when a packet is drawn */
    setup(); list_begin();
    emit(0x30, 7, RGB(255, 0, 0), P(0, 0), P(10, 0), P(0, 10), W1, W1, W1);
    list_draw();
    CHECK_EQ(zat(1, 1), 0);
    bus_write32(m, IO_BASE + IO_GPU_DEPTH, 1);
    list_draw();
    CHECK_EQ(zat(1, 1), 0xC000);
}

/* Early depth: a failing pixel costs 1 whatever its kind; the reciprocals are charged once a
 * triangle whether for the test, perspective or both. */
static void test_depth_cost(void) {
    setup(); list_begin();
    for (int i = 0; i < 256 * 256; i++) slot_ptr(0)[i] = 1;
    set_pal(1, C15(10, 20, 30));
    bus_write32(m, IO_BASE + IO_GPU_DEPTH, 1);
    bus_write32(m, IO_BASE + IO_GPU_ZCLEAR, 0xFFFF);    /* everything fails */
    const uint32_t W1 = W16(1);
    struct { uint32_t type; int n; } k[] = {{0x30, 7}, {0x32, 10}, {0x38, 7}, {0x3A, 10}};
    for (int i = 0; i < 4; i++) {
        m->gpu_cycles = 0;
        list_begin();
        if (k[i].type & 2)
            emit(k[i].type, 10, RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 0, 0, 0), P(10, 0), UV(0, 0), P(0, 10), UV(0, 0), W1, W1, W1);
        else emit(k[i].type, 7, RGB(128, 128, 128), P(0, 0), P(10, 0), P(0, 10), W1, W1, W1);
        list_draw();
        CHECK_EQ(m->gpu_cycles, 40 + 24 + 55);          /* 55 failed pixels at 1 */
    }
    CHECK_EQ(m->gstat.px_zfail, 4 * 55);
    bus_write32(m, IO_BASE + IO_GPU_ZCLEAR, 0);         /* everything passes */
    uint32_t pass[4] = {55, 110, 110, 220};
    for (int i = 0; i < 4; i++) {
        m->gpu_cycles = 0;
        list_begin();
        if (k[i].type & 2)
            emit(k[i].type, 10, RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 0, 0, 0), P(10, 0), UV(0, 0), P(0, 10), UV(0, 0), W1, W1, W1);
        else emit(k[i].type, 7, RGB(128, 128, 128), P(0, 0), P(10, 0), P(0, 10), W1, W1, W1);
        list_draw();
        CHECK_EQ(m->gpu_cycles, 40 + 24 + pass[i]);     /* as a plain pixel: the test is free */
        bus_write32(m, IO_BASE + IO_GPU_ZCLEAR, 0);
        m->gpu_cycles = 0;
    }
    /* empty, off-screen and zero-area triangles with depth still pay their setup */
    m->gpu_cycles = 0;
    list_begin();
    emit(0x30, 7, RGB(1, 1, 1), P(5, 5), P(5, 5), P(5, 5), W1, W1, W1);
    emit(0x30, 7, RGB(1, 1, 1), P(-50, -50), P(-40, -50), P(-50, -40), W1, W1, W1);
    list_draw();
    CHECK_EQ(m->gpu_cycles, 2 * (40 + 24));
    /* textured with depth, test off: perspective alone pays the reciprocals */
    bus_write32(m, IO_BASE + IO_GPU_DEPTH, 0);
    m->gpu_cycles = 0;
    list_begin();
    emit(0x32, 10, RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 0, 0, 0), P(10, 0), UV(0, 0), P(0, 10), UV(0, 0), W1, W1, W1);
    list_draw();
    CHECK_EQ(m->gpu_cycles, 40 + 24 + 110);             /* equal depths: affine, no divides */
    CHECK_EQ(GPU_CYCLES_RECIP, 24);
    CHECK_EQ(GPU_CYCLES_DIVIDE, 2);
    CHECK_EQ(GPU_CYCLES_ZFAIL, 1);
}

/* Random packets with depth of every kind against the reference, with the test on and off,
 * drawn over a random depth buffer; then the counts the cost table charges. */
static void test_depth_reference_random(void) {
    static uint16_t ref[MEI_W * MEI_H], zref[MEI_W * MEI_H];
    setup();
    for (int i = 0; i < 0x10000; i++) slot_ptr(0)[i] = (uint8_t)(rnd(0, 255) * (rnd(0, 7) != 0));
    for (int i = 0; i < 0x8000; i++) slot_ptr(15)[i] = (uint8_t)rnd(0, 255);
    for (int i = 0; i < 4096; i++) set_pal(i, (uint16_t)rnd(0, 0x7FFF));
    int mismatch = 0, zmismatch = 0;
    long long cyc_bad = 0;
    for (int iter = 0; iter < 400; iter++) {
        RefZ o = {0};
        o.flags = rnd(0, 15) & ~4;
        o.mode = rnd(0, 3);
        o.dither = rnd(0, 1);
        o.four = rnd(0, 1);
        o.slot = o.four ? 15 : rnd(0, 1) * 15;
        o.pal = o.four ? rnd(0, 255) : rnd(0, 15);
        o.ztest = iter % 5 != 0;
        o.zoff = rnd(0, 3) ? 0 : rnd(0, 31);
        ref_win = (o.flags & 2) && rnd(0, 3) == 0 ? (uint32_t)rnd(0, 0xFFFF) : 0;
        int big = iter % 4 == 0;
        RV v[3];
        int32_t wv[3];
        for (int i = 0; i < 3; i++) {
            v[i].x = big ? rnd(-2000, 2000) : rnd(-40, 360);
            v[i].y = big ? rnd(-2000, 2000) : rnd(-40, 280);
            for (int k = 0; k < 5; k++) v[i].c[k] = rnd(0, 3) == 0 ? 255 : rnd(0, 255);
            int r = rnd(0, 9);
            wv[i] = r == 0 ? rnd(-100, 5000) : r == 1 ? 0x7FFFFFFF - rnd(0, 1000) : rnd(1 << 14, 1 << 24);
        }
        if (iter % 7 == 0) wv[1] = wv[0];
        if (iter % 11 == 0) wv[1] = wv[2] = wv[0];      /* equal depths: affine */
        if (iter % 50 == 0) v[0].x = -32768, v[1].y = 32767;
        next_frame();
        gpu_clear(m, (uint32_t)rnd(0, 0x7FFF));
        for (int i = 0; i < MEI_W * MEI_H; i++) m->zbuf[i] = (uint16_t)(rnd(0, 1) ? rnd(0, 0xFFFF) : 0);
        m->gpu_ctrl = (uint32_t)o.dither;
        m->gpu_depth = (uint32_t)o.ztest;
        memcpy(ref, back(), sizeof ref);
        memcpy(zref, m->zbuf, sizeof zref);
        list_begin();
        emit_tri_z(o.flags, v, wv, &o);
        ref_fails = ref_divs = ref_inside = 0;
        m->gpu_cycles = 0;
        memset(&m->gstat, 0, sizeof m->gstat);
        list_draw();
        ref_tri_z(ref, zref, v[0], v[1], v[2], wv, &o);
        if (memcmp(ref, back(), sizeof ref)) {
            if (!mismatch) printf("  depth reference mismatch: iter %d flags %x\n", iter, o.flags);
            mismatch++;
        }
        if (memcmp(zref, m->zbuf, sizeof zref)) {
            if (!zmismatch) printf("  depth buffer mismatch: iter %d flags %x\n", iter, o.flags);
            zmismatch++;
        }
        static const int per_px[8] = {1, 1, 2, 2, 2, 2, 4, 4};
        int kind = (o.flags & 3) | (o.flags >> 1 & 4);
        long long expect = 40 + (o.ztest || (o.flags & 2) ? 24 : 0) + (ref_inside - ref_fails) * per_px[kind] + ref_fails + 2 * ref_divs;
        if ((long long)m->gpu_cycles != expect) {
            if (!cyc_bad) printf("  depth cost mismatch: iter %d: %llu, expected %lld\n", iter, (unsigned long long)m->gpu_cycles, expect);
            cyc_bad++;
        }
        if (m->gstat.persp_divs != ref_divs || m->gstat.px_zfail != ref_fails) cyc_bad++;
    }
    ref_win = 0;
    m->gpu_depth = 0;
    CHECK_EQ(mismatch, 0);
    CHECK_EQ(zmismatch, 0);
    CHECK_EQ(cyc_bad, 0);
}

/* Perspective: equal depths draw exactly as the plain packet; otherwise the spans divide every
 * 16 pixels (golden pixels below freeze the rule); texture windows apply to the corrected u, v. */
static void test_perspective(void) {
    static uint16_t ref[MEI_W * MEI_H];
    setup();
    uint8_t *t = slot_ptr(2);
    for (int i = 0; i < 0x10000; i++) t[i] = (uint8_t)(1 + (i & 255) % 15 + 15 * ((i >> 8) % 15));
    for (int i = 1; i < 256; i++) set_pal(256 + i, (uint16_t)(i * 97 & 0x7FFF));
    uint32_t col = RGB(128, 128, 128), w1 = W16(1), w4 = W16(4);
    /* equal depths: the plain picture, every textured type, with and without a window */
    static const int types[8] = {0x2, 0x3, 0x6, 0x7, 0xA, 0xB, 0xE, 0xF};
    for (int k = 0; k < 16; k++) {
        int ty = types[k & 7], gouraud = ty & 1, nv = (ty & 4) ? 4 : 3;
        uint32_t win = k >= 8 ? 0x2A15 : 0;
        int pos[4][2] = {{10, 10}, {300, 20}, {5, 230}, {290, 220}}, uv[4][2] = {{0, 0}, {255, 0}, {0, 255}, {255, 255}};
        uint32_t w[16];
        int n = 0;
        for (int i = 0; i < nv; i++) {
            if (i == 0 || gouraud) w[n++] = RGB(128 + 20 * i, 128, 100 + 30 * i);
            w[n++] = P(pos[i][0], pos[i][1]);
            w[n++] = i == 0 ? TEX0(0, 0, 2, 0, 1) : UV(uv[i][0], uv[i][1]) | (i == 1 ? win << 16 : 0);
        }
        for (int depth = 0; depth < 2; depth++) {
            next_frame();
            list_begin();
            uint32_t a = emit((uint32_t)(0x20 | depth << 4 | ty), 0);
            for (int i = 0; i < n; i++) wr32(m->ram + a + 4 + 4 * i, w[i]);
            if (depth) for (int i = 0; i < nv; i++) wr32(m->ram + a + 4 + 4 * (n + i), w4);
            memset(&m->gstat, 0, sizeof m->gstat);
            list_draw();
            if (!depth) memcpy(ref, back(), sizeof ref);
            else {
                CHECK_EQ(memcmp(ref, back(), sizeof ref), 0);
                CHECK_EQ(m->gstat.persp_divs, 0);
                CHECK_EQ(m->gstat.px_persp, 0);
                CHECK_EQ(m->gstat.tris_recip, (uint32_t)(nv - 2));
            }
        }
    }

    /* unequal depths: a floor receding from w 1 (bottom) to w 4 (top), against the reference */
    RefZ o = {2, 0, 0, 2, 0, 1, 0, 0, 0, 0, 0};
    RV q[4] = {{0, 0, {128, 128, 128, 0, 0}}, {319, 0, {128, 128, 128, 255, 0}},
               {0, 239, {128, 128, 128, 0, 255}}, {319, 239, {128, 128, 128, 255, 255}}};
    int32_t wq[4] = {(int32_t)w4, (int32_t)w4, (int32_t)w1, (int32_t)w1};
    next_frame();
    memcpy(ref, back(), sizeof ref);
    static uint16_t zdummy[MEI_W * MEI_H];
    ref_fails = ref_divs = ref_inside = 0;
    list_begin();
    emit(0x36, 13, col, P(0, 0), TEX0(0, 0, 2, 0, 1), P(319, 0), UV(255, 0),
         P(0, 239), UV(0, 255), P(319, 239), UV(255, 255), w4, w4, w1, w1);
    m->gpu_cycles = 0;
    memset(&m->gstat, 0, sizeof m->gstat);
    list_draw();
    int32_t w012[3] = {wq[0], wq[1], wq[2]}, w123[3] = {wq[1], wq[2], wq[3]};
    ref_tri_z(ref, zdummy, q[0], q[1], q[2], w012, &o);
    ref_tri_z(ref, zdummy, q[1], q[2], q[3], w123, &o);
    CHECK_EQ(memcmp(ref, back(), sizeof ref), 0);
    CHECK_EQ(m->gstat.persp_divs, ref_divs);
    CHECK_EQ(m->gstat.px_persp, ref_inside);
    CHECK_EQ(m->gpu_cycles, 2 * (40 + 24) + ref_inside * 2 + ref_divs * 2);
    CHECK_EQ(ref_inside, 76241);                        /* RENDERING.md's cost example */
    CHECK_EQ(ref_divs, 5437);
    CHECK_EQ(m->gpu_cycles, 163484);
    /* golden pixels (docs/RENDERING.md, "Golden values"): the texel u, v at a pixel; the texture's
     * index there is 1 + u % 15 + 15 * (v % 15) and its colour index * 97 */
    static const struct { int x, y, u, v; } gold[] = {
        {0, 0, 0, 0}, {15, 0, 11, 0}, {16, 0, 12, 0}, {17, 0, 13, 0}, {160, 0, 127, 0}, {318, 0, 254, 0},
        {0, 60, 0, 146}, {16, 60, 7, 146}, {17, 60, 7, 146}, {200, 60, 91, 146}, {0, 119, 0, 203},
        {160, 119, 51, 203}, {0, 120, 0, 204}, {160, 120, 52, 204}, {318, 120, 253, 204},
        {17, 180, 4, 235}, {200, 180, 138, 235}, {16, 238, 12, 254}, {318, 238, 254, 254},
    };
    for (unsigned i = 0; i < sizeof gold / sizeof *gold; i++) {
        int idx = 1 + gold[i].u % 15 + 15 * (gold[i].v % 15);
        CHECK_EQ(px(gold[i].x, gold[i].y), (uint16_t)(idx * 97 & 0x7FFF));
    }

    /* the walker divides at a span's start, every 16 pixels and its end: 1 + ceil((n - 1) / 16) */
    static const struct { int x0, x1; uint32_t divs; } spans[] = {{0, 0, 1}, {0, 1, 2}, {0, 16, 2}, {0, 17, 3}, {0, 32, 3}, {0, 33, 4}, {5, 300, 20}};
    for (unsigned i = 0; i < sizeof spans / sizeof *spans; i++) {
        next_frame(); list_begin();
        memset(&m->gstat, 0, sizeof m->gstat);
        int x0 = spans[i].x0, x1 = spans[i].x1 + 1;     /* one row: y 50 only */
        emit(0x36, 13, col, P(x0, 50), TEX0(0, 0, 2, 0, 1), P(x1, 50), UV(255, 0),
             P(x0, 51), UV(0, 255), P(x1, 51), UV(255, 255), w4, w1, w4, w1);
        list_draw();
        CHECK_EQ(m->gstat.persp_divs, spans[i].divs);
        CHECK_EQ(m->gstat.px_persp, (uint32_t)(x1 - x0));
    }

    /* with the depth test: the reciprocals once, and a window over the corrected u, v */
    next_frame(); list_begin();
    for (int i = 0; i < MEI_W * MEI_H; i++) m->zbuf[i] = 0;
    m->gpu_depth = 1;
    ref_win = 0x1B0A;
    o.ztest = 1;
    memcpy(ref, back(), sizeof ref);
    memcpy(zdummy, m->zbuf, sizeof zdummy);
    ref_fails = ref_divs = ref_inside = 0;
    emit(0x36, 13, col, P(0, 0), TEX0(0, 0, 2, 0, 1), P(319, 0), UV(255, 0) | ref_win << 16,
         P(0, 239), UV(0, 255), P(319, 239), UV(255, 255), w4, w4, w1, w1);
    m->gpu_cycles = 0;
    list_draw();
    ref_tri_z(ref, zdummy, q[0], q[1], q[2], w012, &o);
    ref_tri_z(ref, zdummy, q[1], q[2], q[3], w123, &o);
    CHECK_EQ(memcmp(ref, back(), sizeof ref), 0);
    CHECK_EQ(memcmp(zdummy, m->zbuf, sizeof zdummy), 0);
    CHECK_EQ(m->gpu_cycles, 2 * (40 + 24) + ref_inside * 2 + ref_divs * 2);
    ref_win = 0;
    m->gpu_depth = 0;
}

/* With the plane compositor on, packets with depth keep their layer bit; a failing pixel leaves
 * the hole (or whatever was there). */
static void test_depth_planes(void) {
    setup();
    m->pln_reg[PLN_CTRL / 4] = 1;
    gpu_clear(m, PLN_HOLE);
    m->gpu_depth = 1;
    list_begin();
    emit(0x30, 7, RGB(255, 0, 0) | 1u << 26, P(0, 0), P(20, 0), P(0, 20), W16(1), W16(1), W16(1));
    emit(0x30, 7, RGB(0, 255, 0), P(0, 0), P(40, 0), P(0, 40), W16(2), W16(2), W16(2));
    list_draw();
    CHECK_EQ(px(1, 1), 0x8000 | 31);                    /* upper red */
    CHECK_EQ(px(25, 1), 31 << 5);                       /* lower green */
    CHECK_EQ(px(100, 100), PLN_HOLE);
    list_begin();
    emit(0x30, 7, RGB(0, 0, 255), P(50, 50), P(60, 50), P(50, 60), W16(1), W16(1), W16(1));
    list_draw();
    bus_write32(m, IO_BASE + IO_GPU_ZCLEAR, 0xFFFF);
    list_begin();
    emit(0x30, 7, RGB(255, 255, 255), P(0, 0), P(100, 0), P(0, 100), W16(1), W16(1), W16(1));
    list_draw();
    CHECK_EQ(px(1, 1), 0x8000 | 31);                    /* all failed: nothing changed */
    CHECK_EQ(px(80, 5), PLN_HOLE);
    m->gpu_depth = 0;
    m->pln_reg[PLN_CTRL / 4] = 0;
}

/* ---- fog toward a colour (a proposal, docs/DECISIONS.md) ---- */

#define FOG_ON (1u << 24)
static uint32_t FOGR(int near16, int scale) { return (uint32_t)near16 | (uint32_t)scale << 16; }

static void test_fog_registers(void) {
    setup();
    uint32_t v = 7;
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_FOG, &v), 0);
    CHECK_EQ(v, 0);                                     /* off at reset */
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_FOG_RANGE, &v), 0);
    CHECK_EQ(v, 0);
    CHECK_EQ(bus_write32(m, IO_BASE + IO_GPU_FOG, 0xFFFFFFFF), 0);
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_FOG, &v), 0);
    CHECK_EQ(v, 0x1FFFFFF);                             /* bits 25-31 reserved, read 0 */
    CHECK_EQ(bus_write32(m, IO_BASE + IO_GPU_FOG_RANGE, 0xDEADBEEF), 0);
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_FOG_RANGE, &v), 0);
    CHECK_EQ(v, 0xDEADBEEF);
    CHECK_EQ(bus_read8(m, IO_BASE + IO_GPU_FOG, &v, 0), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_IO_WIDTH);
    memset(&m->fault, 0, sizeof m->fault);
    CHECK_EQ(bus_read32(m, IO_BASE + 0x30, &v), -1);    /* 0xFF0030-0xFF00FF stay unmapped */
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    memset(&m->fault, 0, sizeof m->fault);
    mei_reset(m);                                       /* a reset turns it off */
    memset(&m->fault, 0, sizeof m->fault);
    CHECK_EQ(m->gpu_fog, 0);
    CHECK_EQ(m->gpu_fog_range, 0);
}

/* The factor, the blend and what fog leaves alone. */
static void test_fog_blend(void) {
    setup();
    for (int i = 0; i < 256 * 256; i++) slot_ptr(0)[i] = 1;
    set_pal(1, C15(31, 0, 0));                          /* a red texel: 255 at tint 128 */
    const uint32_t W16u = W16(16);                      /* 16 units: 256 sixteenths */
    /* near 0, scale 2048: factor 256 * 2048 / 4096 = 128 at 16 units */
    m->gpu_fog = FOG_ON | RGB(255, 255, 255);
    m->gpu_fog_range = FOGR(0, 2048);
    CHECK_EQ(ref_fogf((int32_t)W16u, m->gpu_fog_range), 128);
    CHECK_EQ(ref_fogf((int32_t)W16(32), m->gpu_fog_range), 256);
    CHECK_EQ(ref_fogf((int32_t)W16(1000), m->gpu_fog_range), 256);   /* clamped */
    CHECK_EQ(ref_fogf(-5, m->gpu_fog_range), 0);
    CHECK_EQ(ref_fogf((int32_t)W16(16), FOGR(256, 2048)), 0);        /* at near: 0 */
    list_begin();
    emit(0x30, 7, RGB(0, 0, 0), P(0, 0), P(20, 0), P(0, 20), W16u, W16u, W16u);
    list_draw();
    CHECK_EQ(px(2, 2), C15(15, 15, 15));                /* black halfway to white: 127 >> 3 */
    /* a textured face fogs toward a bright colour: the point of the proposal */
    m->gpu_fog = FOG_ON | RGB(0, 0, 255);
    list_begin();
    emit(0x32, 10, RGB(128, 128, 128), P(30, 0), TEX0(0, 0, 0, 0, 0), P(50, 0), UV(0, 0), P(30, 20), UV(0, 0),
         W16(32), W16(32), W16(32));
    emit(0x32, 10, RGB(128, 128, 128), P(60, 0), TEX0(0, 0, 0, 0, 0), P(80, 0), UV(0, 0), P(60, 20), UV(0, 0),
         W16(1), W16(1), W16(1));
    list_draw();
    CHECK_EQ(px(32, 2), C15(0, 0, 31));                 /* factor 256: the fog colour exactly */
    CHECK_EQ(px(62, 2), C15(30, 0, 0));                 /* factor 8 at 1 unit: 255 - 8 = 247 */
    /* a packet without depth is never fogged */
    list_begin();
    emit(0x20, 4, RGB(255, 0, 0), P(90, 0), P(110, 0), P(90, 20));
    list_draw();
    CHECK_EQ(px(92, 2), C15(31, 0, 0));
    /* semi-transparent: mode 0 blends the fogged colour; additive fades toward black */
    gpu_clear(m, C15(10, 10, 10));
    m->gpu_fog = FOG_ON | RGB(248, 248, 248);
    list_begin();
    emit(0x38, 7, RGB(0, 0, 0), P(0, 0), P(20, 0), P(0, 20), W16(32), W16(32), W16(32));
    emit(0x38, 7, RGB(200, 200, 200) | 1u << 24, P(30, 0), P(50, 0), P(30, 20), W16(32), W16(32), W16(32));
    emit(0x38, 7, RGB(200, 200, 200) | 2u << 24, P(60, 0), P(80, 0), P(60, 20), W16(32), W16(32), W16(32));
    list_draw();
    CHECK_EQ(px(2, 2), C15(20, 20, 20));                /* (10 + 31) / 2 */
    CHECK_EQ(px(32, 2), C15(10, 10, 10));               /* fully fogged glow adds nothing */
    CHECK_EQ(px(62, 2), C15(10, 10, 10));               /* nor does a fully fogged shadow subtract */
    /* the factor is interpolated: a floor from 0 to 32 units fogs from nothing to all */
    gpu_clear(m, 0);
    m->gpu_fog = FOG_ON | RGB(255, 255, 255);
    list_begin();
    emit(0x30, 7, RGB(0, 0, 0), P(0, 100), P(256, 100), P(0, 120), W16(0), W16(32), W16(0));
    list_draw();
    CHECK_EQ(px(0, 100), 0);
    CHECK_EQ(px(128, 100), C15(15, 15, 15));            /* factor 128 */
    CHECK(px(250, 100) == C15(30, 30, 30) || px(250, 100) == C15(31, 31, 31));
    /* fog off with the colour and range set: exactly as with the registers at 0 */
    static uint16_t a[MEI_W * MEI_H];
    for (int pass = 0; pass < 2; pass++) {
        gpu_clear(m, 0);
        m->gpu_fog = pass ? RGB(255, 255, 255) : 0;     /* bit 24 clear */
        m->gpu_fog_range = pass ? FOGR(0, 2048) : 0;
        list_begin();
        emit(0x30, 7, RGB(10, 200, 30), P(0, 0), P(200, 0), P(0, 200), W16(1), W16(64), W16(500));
        emit(0x32, 10, RGB(128, 128, 128), P(100, 100), TEX0(0, 0, 0, 0, 0), P(300, 100), UV(255, 0), P(100, 230), UV(0, 255),
             W16(3), W16(90), W16(30));
        m->gpu_cycles = 0;
        list_draw();
        if (!pass) memcpy(a, back(), sizeof a);
        else CHECK(memcmp(a, back(), sizeof a) == 0);
    }
    m->gpu_fog = m->gpu_fog_range = 0;
}

/* GPU_CYCLES_FOG a triangle with depth while fog is on; nothing a pixel. */
static void test_fog_cost(void) {
    setup();
    for (int i = 0; i < 256 * 256; i++) slot_ptr(0)[i] = 1;
    set_pal(1, C15(10, 20, 30));
    const uint32_t W1 = W16(1), W99 = W16(99);
    m->gpu_fog = FOG_ON | RGB(200, 210, 220);
    m->gpu_fog_range = FOGR(16, 1024);
    CHECK_EQ(GPU_CYCLES_FOG, 8);
    struct { uint32_t type; int n; uint32_t px; } k[] = {{0x30, 7, 55}, {0x32, 10, 110}, {0x38, 7, 110}, {0x3A, 10, 220}};
    for (int i = 0; i < 4; i++)
        for (int far = 0; far < 2; far++) {   /* factor 0 (drawn without fog) or 256: the same price */
            uint32_t w = far ? W99 : W1;
            m->gpu_cycles = 0;
            list_begin();
            if (k[i].type & 2)
                emit(k[i].type, 10, RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 0, 0, 0), P(10, 0), UV(0, 0), P(0, 10), UV(0, 0), w, w, w);
            else emit(k[i].type, 7, RGB(128, 128, 128), P(0, 0), P(10, 0), P(0, 10), w, w, w);
            list_draw();
            CHECK_EQ(m->gpu_cycles, 40 + ((k[i].type & 2) ? 24 : 0) + 8 + k[i].px);
        }
    /* a quad: two triangles; a packet without depth: no fog, no charge */
    m->gpu_cycles = 0;
    memset(&m->gstat, 0, sizeof m->gstat);
    list_begin();
    emit(0x34, 9, RGB(1, 1, 1), P(0, 0), P(10, 0), P(0, 10), P(10, 10), W99, W99, W99, W99);
    emit(0x24, 5, RGB(1, 1, 1), P(20, 0), P(30, 0), P(20, 10), P(30, 10));
    list_draw();
    CHECK_EQ(m->gpu_cycles, 2 * (40 + 8) + 100 + 2 * 40 + 100);
    CHECK_EQ(m->gstat.tris_fog, 2);
    CHECK_EQ(m->gstat.px_fog, 100);
    /* depth-tested and failing: the test's 1 a pixel, the setup still paid */
    m->gpu_depth = 1;
    bus_write32(m, IO_BASE + IO_GPU_ZCLEAR, 0xFFFF);
    m->gpu_cycles = 0;
    list_begin();
    emit(0x32, 10, RGB(128, 128, 128), P(0, 0), TEX0(0, 0, 0, 0, 0), P(10, 0), UV(0, 0), P(0, 10), UV(0, 0), W99, W99, W99);
    list_draw();
    CHECK_EQ(m->gpu_cycles, 40 + 24 + 8 + 55);
    m->gpu_depth = 0;
    m->gpu_fog = m->gpu_fog_range = 0;
}

/* Random fogged packets with depth of every kind against the reference, with the depth test on
 * and off, and the cost. */
static void test_fog_reference_random(void) {
    static uint16_t ref[MEI_W * MEI_H], zref[MEI_W * MEI_H];
    setup();
    for (int i = 0; i < 0x10000; i++) slot_ptr(0)[i] = (uint8_t)(rnd(0, 255) * (rnd(0, 7) != 0));
    for (int i = 0; i < 0x8000; i++) slot_ptr(15)[i] = (uint8_t)rnd(0, 255);
    for (int i = 0; i < 4096; i++) set_pal(i, (uint16_t)rnd(0, 0x7FFF));
    int mismatch = 0, zmismatch = 0;
    long long cyc_bad = 0;
    for (int iter = 0; iter < 400; iter++) {
        RefZ o;
        o.flags = rnd(0, 15) & ~4;
        o.mode = rnd(0, 3);
        o.dither = rnd(0, 1);
        o.four = rnd(0, 1);
        o.slot = o.four ? 15 : rnd(0, 1) * 15;
        o.pal = o.four ? rnd(0, 255) : rnd(0, 15);
        o.ztest = iter % 3 != 0;
        o.zoff = 0;
        o.fog = 1;
        o.fogcol = (uint32_t)rnd(0, 0xFFFFFF);
        o.frange = FOGR(rnd(0, 3) ? rnd(0, 2000) : rnd(0, 65535), rnd(0, 3) ? rnd(1, 4000) : rnd(0, 65535));
        ref_win = (o.flags & 2) && rnd(0, 3) == 0 ? (uint32_t)rnd(0, 0xFFFF) : 0;
        int big = iter % 4 == 0;
        RV v[3];
        int32_t wv[3];
        for (int i = 0; i < 3; i++) {
            v[i].x = big ? rnd(-2000, 2000) : rnd(-40, 360);
            v[i].y = big ? rnd(-2000, 2000) : rnd(-40, 280);
            for (int k = 0; k < 5; k++) v[i].c[k] = rnd(0, 3) == 0 ? 255 : rnd(0, 255);
            int r = rnd(0, 9);
            wv[i] = r == 0 ? rnd(-100, 5000) : r == 1 ? 0x7FFFFFFF - rnd(0, 1000) : rnd(1 << 16, 1 << 26);
        }
        if (iter % 7 == 0) wv[1] = wv[0];
        if (iter % 50 == 0) v[0].x = -32768, v[1].y = 32767;
        next_frame();
        gpu_clear(m, (uint32_t)rnd(0, 0x7FFF));
        for (int i = 0; i < MEI_W * MEI_H; i++) m->zbuf[i] = (uint16_t)(rnd(0, 1) ? rnd(0, 0xFFFF) : 0);
        m->gpu_ctrl = (uint32_t)o.dither;
        m->gpu_depth = (uint32_t)o.ztest;
        m->gpu_fog = FOG_ON | o.fogcol;
        m->gpu_fog_range = o.frange;
        memcpy(ref, back(), sizeof ref);
        memcpy(zref, m->zbuf, sizeof zref);
        list_begin();
        emit_tri_z(o.flags, v, wv, &o);
        ref_fails = ref_divs = ref_inside = 0;
        m->gpu_cycles = 0;
        memset(&m->gstat, 0, sizeof m->gstat);
        list_draw();
        ref_tri_z(ref, zref, v[0], v[1], v[2], wv, &o);
        if (memcmp(ref, back(), sizeof ref)) {
            if (!mismatch) printf("  fog reference mismatch: iter %d flags %x\n", iter, o.flags);
            mismatch++;
        }
        if (memcmp(zref, m->zbuf, sizeof zref)) zmismatch++;
        static const int per_px[8] = {1, 1, 2, 2, 2, 2, 4, 4};
        int kind = (o.flags & 3) | (o.flags >> 1 & 4);
        long long expect = 40 + 8 + (o.ztest || (o.flags & 2) ? 24 : 0) + (ref_inside - ref_fails) * per_px[kind] + ref_fails + 2 * ref_divs;
        if ((long long)m->gpu_cycles != expect) {
            if (!cyc_bad) printf("  fog cost mismatch: iter %d: %llu, expected %lld\n", iter, (unsigned long long)m->gpu_cycles, expect);
            cyc_bad++;
        }
    }
    ref_win = 0;
    m->gpu_depth = 0;
    m->gpu_fog = m->gpu_fog_range = 0;
    CHECK_EQ(mismatch, 0);
    CHECK_EQ(zmismatch, 0);
    CHECK_EQ(cyc_bad, 0);
}

static void bench_depth(void) {
    setup();
    for (int i = 0; i < 0x8000; i++) slot_ptr(0)[i] = (uint8_t)(i * 7 + 1);
    for (int i = 0; i < 256; i++) set_pal(i, (uint16_t)(i * 97));
    m->gpu_ctrl = 1;
    for (int mode = 0; mode < 4; mode++) {   /* plain, depth-tested, + perspective, + fog */
        list_begin();
        rng = 99;
        for (int i = 0; i < 1000; i++) {
            int x = rnd(0, 280), y = rnd(0, 200);
            uint32_t wa = W16(2 + i % 7), wb = mode >= 2 ? W16(3 + i % 5) : wa;
            if (!mode) emit(0x2F - 8, 12, RGB(200, 128, 90), P(x, y), TEX0(0, 0, 0, 1, 3), RGB(128, 128, 128), P(x + 35, y + 2), UV(60, 0),
                            RGB(90, 255, 128), P(x + 1, y + 36), UV(0, 60), RGB(128, 60, 200), P(x + 34, y + 37), UV(60, 60));
            else emit(0x3F - 8, 16, RGB(200, 128, 90), P(x, y), TEX0(0, 0, 0, 1, 3), RGB(128, 128, 128), P(x + 35, y + 2), UV(60, 0),
                      RGB(90, 255, 128), P(x + 1, y + 36), UV(0, 60), RGB(128, 60, 200), P(x + 34, y + 37), UV(60, 60), wa, wb, wa, wb);
        }
        m->gpu_depth = mode != 0;
        m->gpu_fog = mode == 3 ? FOG_ON | RGB(200, 210, 220) : 0;
        m->gpu_fog_range = FOGR(16, 8192);   /* fog from 1 unit to 9: every factor between 8 and 256 */
        int frames = 50;
        clock_t t0 = clock();
        for (int f = 0; f < frames; f++) { gpu_zclear(m, 0); list_draw(); m->gpu_status = 0; }
        double ms = (double)(clock() - t0) * 1000.0 / CLOCKS_PER_SEC / frames;
        static const char *names[] = {"plain", "depth-tested", "depth-tested, perspective", "depth-tested, perspective, fogged"};
        printf("  bench: 2,000 textured Gouraud dithered triangles, %s, in %.2f ms per frame\n", names[mode], ms);
    }
    m->gpu_depth = 0;
    m->gpu_fog = m->gpu_fog_range = 0;
}

static void bench(void) {
    setup();
    for (int i = 0; i < 0x8000; i++) slot_ptr(0)[i] = (uint8_t)(i * 7 + 1);
    for (int i = 0; i < 256; i++) set_pal(i, (uint16_t)(i * 97));
    m->gpu_ctrl = 1;
    list_begin();
    for (int i = 0; i < 1000; i++) {   /* 2,000 Gouraud textured triangles, ~600 px each */
        int x = rnd(0, 280), y = rnd(0, 200);
        emit(0x2F - 8, 12, RGB(200, 128, 90), P(x, y), TEX0(0, 0, 0, 1, 3), RGB(128, 128, 128), P(x + 35, y + 2), UV(60, 0),
             RGB(90, 255, 128), P(x + 1, y + 36), UV(0, 60), RGB(128, 60, 200), P(x + 34, y + 37), UV(60, 60));
    }
    int frames = 50;
    clock_t t0 = clock();
    for (int f = 0; f < frames; f++) { list_draw(); m->gpu_status = 0; }
    double ms = (double)(clock() - t0) * 1000.0 / CLOCKS_PER_SEC / frames;
    printf("  bench: 2,000 textured Gouraud dithered triangles (1,000 quads ~35x36 px) in %.2f ms per frame\n", ms);

    setup();
    for (int i = 0; i < 0x8000; i++) slot_ptr(0)[i] = (uint8_t)(i * 7 + 1);
    for (int i = 0; i < 256; i++) set_pal(i, (uint16_t)(i * 97));
    list_begin();
    emit(0x2F, 12, RGB(200, 128, 90), P(0, 0), TEX0(0, 0, 0, 1, 3), RGB(128, 128, 128), P(320, 0), UV(255, 0),
         RGB(90, 255, 128), P(0, 240), UV(0, 255), RGB(128, 60, 200), P(320, 240), UV(255, 255));
    t0 = clock();
    for (int f = 0; f < 200; f++) { list_draw(); m->gpu_status = 0; }
    ms = (double)(clock() - t0) * 1000.0 / CLOCKS_PER_SEC / 200;
    printf("  bench: full-screen textured Gouraud semi-transparent quad in %.3f ms\n", ms);
}

int main(void) {
    m = mei_create();
    if (!m) return 1;
    test_flat_coverage();
    test_shared_edges();
    test_gouraud();
    test_textures();
    test_texture_window();
    test_dither();
    test_blend();
    test_clipping();
    test_limits();
    test_cost_model();
    test_budget();
    test_list_walk();
    test_depth_registers();
    test_depth_key();
    test_depth_off();
    test_depth_test();
    test_depth_cost();
    test_depth_reference_random();
    test_perspective();
    test_depth_planes();
    test_fog_registers();
    test_fog_blend();
    test_fog_cost();
    test_fog_reference_random();
    test_buffers();
    test_error_screen();
    test_reference_random();
    test_long_thin();
    if (!getenv("MEI_NO_BENCH")) { bench(); bench_depth(); }
    mei_destroy(m);
    printf("test_gpu: %d/%d checks passed\n", checks - fails, checks);
    return fails != 0;
}
