/* GPU tests: packet walking, rasterization rules, pixel pipeline, faults. */
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
                int u = at[3], v = at[4], idx;
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
    CHECK_EQ(MEI_GPU_CYCLES_PER_FRAME, 1000000);

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

/* ---- the GPU budget: lag when a frame's modelled cycles exceed 1,000,000 a tick ---- */

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
    wr32(m->ram + V_CLEARS, 26);                        /* 998,400 */
    CHECK_EQ(ticks(4, &t), 0xF);
    CHECK_EQ(ram(V_COUNT), 4);
    CHECK_EQ(seen(1, 1), 0); CHECK_EQ(seen(1, 2), 0); CHECK_EQ(seen(1, 3), 0);
    CHECK_EQ(seen(2, 0), 0x100);                        /* latched at the first present (tick 0) */
    CHECK_EQ(seen(2, 1), 998400); CHECK_EQ(seen(2, 2), 1); CHECK_EQ(seen(2, 3), 0);
    CHECK_EQ(seen(4, 0), 0x102);
    CHECK_EQ(mei_gpu_stats(m)->gpu_cycles, 998400);
    CHECK_EQ(mei_gpu_stats(m)->ticks, 1);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 0);

    /* Exactly the budget presents on time; 40 cycles more is a tick late. */
    list_begin();
    for (int i = 0; i < 40; i++) emit(0x20, 4, RGB(0, 0, 0), P(5, 5), P(5, 5), P(5, 5));   /* empty: 40 each */
    wr32(m->ram + V_LIST, pk_first);
    CHECK_EQ(ticks(2, &t), 0x3);
    CHECK_EQ(mei_gpu_stats(m)->gpu_cycles, 1000000);
    CHECK_EQ(mei_gpu_stats(m)->ticks, 1);
    emit(0x20, 4, RGB(0, 0, 0), P(5, 5), P(5, 5), P(5, 5));
    CHECK_EQ(ticks(2, &t), 0x2);                        /* the frame drawn in the first tick waits */
    CHECK_EQ(mei_gpu_stats(m)->gpu_cycles, 1000040);
    CHECK_EQ(mei_gpu_stats(m)->ticks, 2);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 1);
    CHECK_EQ(m->gpu_lag, 1);

    /* Twice the budget: presented one tick late. The CPU does not run in the wait, and the
     * pads latch only at the present. */
    if (!lag_load()) return;
    t = 0;
    wr32(m->ram + V_CLEARS, 52);                        /* 1,996,800 */
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
    CHECK_EQ(seen(2, 1), 1996800);
    CHECK_EQ(seen(2, 2), 2);
    CHECK_EQ(seen(2, 3), 1);
    CHECK_EQ(ticks(5, &t), 0x15);                       /* ticks 3-7: presents at 3, 5, 7 */
    CHECK_EQ(ram(V_COUNT), 4);
    CHECK_EQ(seen(4, 0), 0x105);
    CHECK_EQ(seen(4, 3), 3);
    CHECK_EQ(m->gpu_lag, 4);
    CHECK_EQ(mei_gpu_stats(m)->ticks, 2);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 1);
    CHECK_EQ(mei_gpu_stats(m)->cpu_cycles < 500000, 1);

    /* Three times: two ticks late. */
    if (!lag_load()) return;
    t = 0;
    wr32(m->ram + V_CLEARS, 78);                        /* 2,995,200 */
    CHECK_EQ(ticks(9, &t), 0x124);                      /* presents at ticks 2, 5, 8 */
    CHECK_EQ(ram(V_COUNT), 3);
    CHECK_EQ(seen(2, 0), 0x102);
    CHECK_EQ(seen(3, 0), 0x105);
    CHECK_EQ(seen(3, 1), 2995200);
    CHECK_EQ(seen(3, 2), 3);
    CHECK_EQ(seen(3, 3), 4);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 2);
    wr32(m->ram + V_CLEARS, 79);                        /* 3,033,600: three ticks late */
    CHECK_EQ(ticks(4, &t), 0x8);                        /* frame 4 (from tick 9) at tick 12 */
    CHECK_EQ(mei_gpu_stats(m)->ticks, 4);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 3);
    uint32_t lag = 0, load = 0, tk = 0;
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_LAG, &lag), 0);
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_LOAD, &load), 0);
    CHECK_EQ(bus_read32(m, IO_BASE + IO_GPU_TICKS, &tk), 0);
    CHECK_EQ(lag, 6 + 3);
    CHECK_EQ(load, 3033600);
    CHECK_EQ(tk, 4);
    CHECK_EQ(bus_write32(m, IO_BASE + IO_GPU_LOAD, 0), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_READ_ONLY);
    memset(&m->fault, 0, sizeof m->fault);

    /* CPU overrun composes: a frame whose CPU work spans two ticks has 2,000,000 GPU cycles. */
    if (!lag_load()) return;
    t = 0;
    wr32(m->ram + V_CLEARS, 52);                        /* 1,996,800 */
    wr32(m->ram + V_SPIN, 200000);                      /* about 600,000 CPU cycles */
    CHECK_EQ(ticks(4, &t), 0xA);                        /* late for the CPU only */
    CHECK_EQ(mei_gpu_stats(m)->ticks, 2);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 0);
    CHECK_EQ(mei_gpu_stats(m)->cpu_cycles > 500000 && mei_gpu_stats(m)->cpu_cycles < 1000000, 1);
    CHECK_EQ(m->gpu_lag, 0);
    wr32(m->ram + V_CLEARS, 53);                        /* 2,035,200: one tick more */
    CHECK_EQ(ticks(6, &t), 0x24);                       /* frames from ticks 4 and 7 at ticks 6 and 9 */
    CHECK_EQ(mei_gpu_stats(m)->ticks, 3);
    CHECK_EQ(mei_gpu_stats(m)->gpu_lag, 1);
    CHECK_EQ(seen(3, 2), 2);                            /* frame 3 read frame 2's 2 ticks */
    CHECK_EQ(seen(4, 2), 3);                            /* frame 4 read frame 3's 3 */

    /* A reset clears the wait and the registers. */
    wr32(m->ram + V_CLEARS, 200);
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
    emit(0x30, 0);
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

    /* List in ROM. */
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
        {0x200001, MEI_FAULT_MISALIGNED}, {0xFFFFFE, MEI_FAULT_UNMAPPED},
    };
    for (unsigned i = 0; i < sizeof bad / sizeof *bad; i++) {
        setup(); list_begin();
        uint32_t a = emit(0x20, 4, RGB(255, 255, 255), P(0, 0), P(10, 0), P(0, 10));
        wr32(m->ram + a, 0x20u << 24 | bad[i].next);
        m->pc = 0x200040;
        list_draw();
        CHECK_EQ(m->fault.kind, bad[i].kind);
        CHECK_EQ(m->fault.addr, bad[i].next);
        CHECK_EQ(m->fault.pc, 0x200040);
        CHECK_EQ(px(1, 1), 0x7FFF);
    }
    setup();                 /* first address itself bad */
    gpu_draw_list(m, 0x500000);
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    setup();                 /* polygon running off the end of ROM */
    wr32(m->rom + ROM_SIZE - 8, 0x20u << 24 | 0xFFFFFF);
    gpu_draw_list(m, ROM_BASE + ROM_SIZE - 8);
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
    CHECK_EQ(m->fault.addr, 0x400000);
    memset(m->rom + ROM_SIZE - 8, 0, 8);
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
    test_dither();
    test_blend();
    test_clipping();
    test_limits();
    test_cost_model();
    test_budget();
    test_list_walk();
    test_buffers();
    test_error_screen();
    test_reference_random();
    test_long_thin();
    if (!getenv("MEI_NO_BENCH")) bench();
    mei_destroy(m);
    printf("test_gpu: %d/%d checks passed\n", checks - fails, checks);
    return fails != 0;
}
