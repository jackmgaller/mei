/* Large carts (docs/DECISIONS.md, "Cart ROM"). A cart of exactly MEI_ROM_MAX bytes, assembled
 * at test time, runs code and reads data at its far end, well past the old 2 MB / 24-bit
 * limits, through each path that carries an address: call, branch, jmp and callr, la with lw
 * and vld, a pointer stored in ROM, a GPU packet list, an audio channel and a memory card
 * write. Also the ROM window past the image, and carts over the limit. */
#include "machine.h"
#include "asm.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int checks, fails;
#define CHECK(c) do { checks++; if (!(c)) { fails++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)
#define CHECK_EQ(a, b) do { long long a_ = (long long)(a), b_ = (long long)(b); checks++; \
    if (a_ != b_) { fails++; printf("FAIL %s:%d: %s == 0x%llX, expected 0x%llX\n", __FILE__, __LINE__, #a, a_, b_); } } while (0)

#define FAR   (MEI_ROM_BASE + MEI_ROM_MAX - 0x100)   /* the far code and data: the last 256 bytes */
#define CARD  0xFF0380u

static const char *SRC =
    ".cart \"Far\", start, \"FAR-TEST\"\n"
    "start:\n"
    "    call far_fn             ; r1 = 0x1234\n"
    "    la r2, far_data\n"
    "    lw r3, [r2]\n"
    "    vld v1, [r2]\n"
    "    la r5, far_ptr\n"
    "    lw r5, [r5]             ; a code pointer kept in ROM\n"
    "    callr r5                ; r6 = 77\n"
    "    la r7, last + 4\n"
    "    lw r8, [r7]             ; just past the image: 0\n"
    "    lui r9, 0x3FC0          ; I/O\n"
    "    la r10, far_packet\n"
    "    sw r10, [r9+0]          ; GPU_DRAW: a list starting in far ROM\n"
    "    la r10, far_sample\n"
    "    sw r10, [r9+0x100]      ; channel 0 plays 4 bytes from far ROM\n"
    "    li r11, 4\n"
    "    sw r11, [r9+0x104]\n"
    "    lui r11, 64\n"
    "    sw r11, [r9+0x10C]\n"
    "    li r11, 0xFFFF\n"
    "    sw r11, [r9+0x110]\n"
    "    li r11, 1\n"
    "    sw r11, [r9+0x114]\n"
    "    vsync\n"
    "    jmp far_end\n"
    ".org 0x%08X\n"
    "far_fn:\n"
    "    li r1, 0x1234\n"
    "    beq r0, r0, .skip\n"
    "    li r1, 0\n"
    ".skip:\n"
    "    ret\n"
    "far_fn2:\n"
    "    li r6, 77\n"
    "    ret\n"
    "far_end:\n"
    "    brk\n"
    "far_data: .word 0xCAFEF00D, 0x12345678, 3, 4\n"
    "far_ptr: .word far_fn2\n"
    "far_packet: .word 0x20 << 24 | 0x1000, 0x0000FF, 0, 10, 10 << 16   ; red, then the RAM packet\n"
    "far_sample: .byte 0x40, 0x40, 0x40, 0x40\n"
    ".org 0x%08X\n"
    "last: .word 0x600DF00D\n";

static uint32_t sym(const MeiAsmResult *r, const char *name) {
    uint32_t v = 0;
    CHECK(mei_asm_find_symbol(r, name, &v));
    return v;
}

static uint32_t card_rd(Mei *m, uint32_t off) { uint32_t v = 0; bus_read32(m, CARD + off, &v); return v; }
static int card_cmd(Mei *m, uint32_t c) {
    bus_write32(m, CARD, c);
    int e = (int)(card_rd(m, 4) >> 8 & 0xFF);
    for (int i = 0; i < 1000 && (card_rd(m, 4) & 1); i++) card_vsync(m);
    return e;
}

static void test_largest_cart(void) {
    char src[4096];
    snprintf(src, sizeof src, SRC, FAR, MEI_ROM_BASE + MEI_ROM_MAX - 4);
    MeiAsmResult r;
    if (mei_assemble(src, "far.s", &r)) { printf("FAIL: %s\n", r.error); fails++; return; }
    CHECK_EQ(r.rom_len, MEI_ROM_MAX);
    uint32_t far_fn = sym(&r, "far_fn"), far_end = sym(&r, "far_end"), far_data = sym(&r, "far_data");
    CHECK_EQ(far_fn, FAR);
    CHECK(far_data - MEI_ROM_BASE > 0x200000 && far_data > 0xFFFFFF);

    Mei *m = mei_create();
    CHECK_EQ(mei_load_cart(m, r.rom, r.rom_len), 0);
    /* the RAM packet the ROM one links to: a green triangle */
    wr32(m->ram + 0x1000, 0x20u << 24 | 0xFFFFFF);
    wr32(m->ram + 0x1004, 0x00FF00);
    wr32(m->ram + 0x1008, 20 | 20u << 16);
    wr32(m->ram + 0x100C, 30 | 20u << 16);
    wr32(m->ram + 0x1010, 20 | 30u << 16);

    CHECK_EQ(mei_run_frame(m), 1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_NONE);
    CHECK_EQ(m->r[1], 0x1234);
    CHECK_EQ(m->r[3], 0xCAFEF00D);
    CHECK(m->v[1][0] == (int32_t)0xCAFEF00D && m->v[1][1] == 0x12345678 && m->v[1][2] == 3 && m->v[1][3] == 4);
    CHECK_EQ(m->r[6], 77);
    CHECK_EQ(m->r[8], 0);
    const uint16_t *fb = mei_display(m);
    CHECK_EQ(fb[1 * MEI_W + 1], 0x001F);             /* the ROM packet */
    CHECK_EQ(fb[21 * MEI_W + 21], 0x03E0);           /* the RAM packet */
    const int16_t *s;
    CHECK(mei_audio(m, &s) > 4);
    CHECK_EQ(s[0], 0x4000 * 255 / 256);
    CHECK_EQ(s[2 * 3 + 1], 0x4000 * 255 / 256);
    CHECK_EQ(s[2 * 4], 0);

    /* a save written from far ROM, its metadata running past the image into the zeros */
    uint8_t *card = calloc(1, MEI_CARD_SIZE);
    mei_card_insert(m, 0, card);
    bus_write32(m, CARD + 0x0C, 0);                   /* SAVE */
    bus_write32(m, CARD + 0x10, far_data);            /* BUF */
    bus_write32(m, CARD + 0x14, 16);                  /* LEN */
    bus_write32(m, CARD + 0x18, MEI_ROM_BASE + MEI_ROM_MAX - 4);   /* META: the last word, then zeros */
    CHECK_EQ(card_cmd(m, 3), 0);
    bus_write32(m, CARD + 0x10, 0x2000);
    bus_write32(m, CARD + 0x18, 0x3000);
    CHECK_EQ(card_cmd(m, 2), 0);
    CHECK(!memcmp(m->ram + 0x2000, r.rom + (far_data - MEI_ROM_BASE), 16));
    CHECK_EQ(rd32(m->ram + 0x3000), 0x600DF00D);
    CHECK_EQ(rd32(m->ram + 0x3004), 0);
    mei_card_insert(m, 0, NULL);
    free(card);

    /* the next frame jumps to the far brk; the error screen reads the instruction there */
    CHECK_EQ(mei_run_frame(m), 0);
    CHECK_EQ(m->fault.kind, MEI_FAULT_BREAK);
    CHECK_EQ(m->fault.pc, far_end);

    mei_destroy(m);
    mei_asm_free(&r);
}

static void test_over_the_limit(void) {
    char src[256];
    MeiAsmResult r;
    snprintf(src, sizeof src, ".org 0x%08X\n.word 1\n.byte 1\n", MEI_ROM_BASE + MEI_ROM_MAX - 4);
    CHECK(mei_assemble(src, "big.s", &r) != 0 && strstr(r.error, "ROM is full (64 MB)"));
    snprintf(src, sizeof src, ".org 0x%08X\n", MEI_ROM_BASE + MEI_ROM_MAX + 4);
    CHECK(mei_assemble(src, "big.s", &r) != 0 && strstr(r.error, "past the end of ROM"));

    Mei *m = mei_create();
    uint8_t *big = calloc(1, MEI_ROM_MAX + 1);
    CHECK_EQ(mei_load_cart(m, big, MEI_ROM_MAX + 1), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_NO_CART);
    free(big);
    mei_destroy(m);
}

int main(void) {
    test_largest_cart();
    test_over_the_limit();
    printf("test_rom: %d checks, %d failed\n", checks, fails);
    return fails != 0;
}
