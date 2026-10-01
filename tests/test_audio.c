/* Audio tests: tick sizes, sample formats, volume, pitch, looping, clipping, registers. */
#include "machine.h"

#include <stdio.h>
#include <string.h>

static int checks, fails;
#define CHECK(c) do { checks++; if (!(c)) { fails++; printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #c); } } while (0)
#define CHECK_EQ(a, b) do { long long a_ = (long long)(a), b_ = (long long)(b); checks++; \
    if (a_ != b_) { fails++; printf("FAIL %s:%d: %s == %lld, expected %lld\n", __FILE__, __LINE__, #a, a_, b_); } } while (0)

static Mei *m;

static void setup(void) {
    mei_reset(m);
    memset(&m->fault, 0, sizeof m->fault);
}

static void wr(int ch, uint32_t reg, uint32_t v) { CHECK_EQ(audio_io_write(m, (uint32_t)ch * 0x20 + reg, v), 0); }
static uint32_t rd(int ch, uint32_t reg) { uint32_t v = 0xDEAD; CHECK_EQ(audio_io_read(m, (uint32_t)ch * 0x20 + reg, &v), 0); return v; }

static void play(int ch, uint32_t addr, uint32_t len, uint32_t loop, uint32_t pitch, int lv, int rv, uint32_t ctrl) {
    wr(ch, IO_AUD_ADDR, addr);
    wr(ch, IO_AUD_LEN, len);
    wr(ch, IO_AUD_LOOP, loop);
    wr(ch, IO_AUD_PITCH, pitch);
    wr(ch, IO_AUD_VOL, (uint32_t)lv | (uint32_t)rv << 8);
    wr(ch, IO_AUD_CTRL, ctrl | 1);
}
static int16_t L(int i) { return m->audio_out[2 * i]; }
static int16_t R(int i) { return m->audio_out[2 * i + 1]; }

static void test_tick_sizes(void) {
    setup();
    int total = 0, ok = 1;
    for (int t = 0; t < 60; t++) {
        audio_mix_tick(m);
        ok &= m->audio_frames == (t % 2 ? 368 : 367);
        total += m->audio_frames;
    }
    CHECK(ok);
    CHECK_EQ(total, 22050);
    for (int t = 0; t < 600; t++) { audio_mix_tick(m); total += m->audio_frames; }
    CHECK_EQ(total, 22050 * 11);
    CHECK_EQ(m->audio_out[0], 0);   /* silence with nothing playing */
}

static void test_8bit(void) {
    setup();
    int8_t s[6] = {64, -128, 127, 1, -1, 0};
    memcpy(m->ram + 0x2000, s, sizeof s);
    play(0, 0x2000, 6, 0, 0x10000, 255, 128, 0);
    audio_mix_tick(m);
    for (int i = 0; i < 6; i++) {
        int32_t v = s[i] * 256;
        int32_t l = v * 255, r = v * 128;
        CHECK_EQ(L(i), l >= 0 ? l / 256 : -((-l + 255) / 256));
        CHECK_EQ(R(i), r >= 0 ? r / 256 : -((-r + 255) / 256));
    }
    CHECK_EQ(L(0), 16320);
    CHECK_EQ(R(1), -16384);
    CHECK_EQ(L(6), 0);   /* stopped at the end */
    CHECK_EQ(rd(0, IO_AUD_CTRL) & 1, 0);
    CHECK_EQ(rd(0, IO_AUD_POS), 6);

    /* Sample data in ROM works too. */
    setup();
    m->rom[0x40] = 0x10;
    play(1, ROM_BASE + 0x40, 1, 0, 0x10000, 128, 0, 0);
    audio_mix_tick(m);
    CHECK_EQ(L(0), 0x1000 * 128 / 256);
    CHECK_EQ(R(0), 0);
}

static void test_16bit(void) {
    setup();
    int16_t s[4] = {-1234, 32767, -32768, -1};
    for (int i = 0; i < 4; i++) wr16(m->ram + 0x3000 + 2 * i, (uint16_t)s[i]);
    play(2, 0x3000, 4, 0, 0x10000, 128, 1, 4);
    audio_mix_tick(m);
    CHECK_EQ(L(0), -617);
    CHECK_EQ(R(0), -5);       /* floor(-1234 / 256) */
    CHECK_EQ(L(1), 16383);
    CHECK_EQ(L(2), -16384);
    CHECK_EQ(R(3), -1);       /* floor(-1 / 256), arithmetic shift */
    CHECK_EQ(L(4), 0);
    CHECK_EQ(rd(2, IO_AUD_CTRL), 4);   /* stopped; bits 1-2 as written */
}

static void ramp(uint32_t addr, int n) { for (int i = 0; i < n; i++) m->ram[addr + i] = (uint8_t)i; }

static void test_pitch(void) {
    setup();
    ramp(0x4000, 100);
    play(0, 0x4000, 100, 0, 0x20000, 0, 255, 0);   /* 2.0: every other sample */
    audio_mix_tick(m);
    int ok = 1;
    for (int i = 0; i < 50; i++) ok &= R(i) == (i * 2 * 256) * 255 / 256;
    CHECK(ok);
    CHECK_EQ(R(50), 0);

    setup();
    ramp(0x4000, 100);
    play(0, 0x4000, 100, 0, 0x8000, 0, 255, 0);    /* 0.5: each sample twice */
    audio_mix_tick(m);
    ok = 1;
    for (int i = 0; i < 200; i++) ok &= R(i) == ((i / 2) * 256) * 255 / 256;
    CHECK(ok);
    CHECK_EQ(R(200), 0);
    CHECK_EQ(rd(0, IO_AUD_POS), 100);

    setup();                                       /* 1.5 */
    ramp(0x4000, 100);
    play(0, 0x4000, 100, 0, 0x18000, 0, 255, 0);
    audio_mix_tick(m);
    ok = 1;
    for (int i = 0; i < 66; i++) ok &= R(i) == ((i * 3 / 2) * 256) * 255 / 256;
    CHECK(ok);
    CHECK_EQ(R(67), 0);
}

static void test_loop(void) {
    setup();
    ramp(0x5000, 4);
    play(3, 0x5000, 4, 1, 0x10000, 255, 0, 2);
    audio_mix_tick(m);
    int seq[10] = {0, 1, 2, 3, 1, 2, 3, 1, 2, 3}, ok = 1;
    for (int i = 0; i < 10; i++) ok &= L(i) == seq[i] * 255;
    CHECK(ok);
    CHECK_EQ(rd(3, IO_AUD_CTRL), 3);   /* playing + loop */

    /* Fractional overshoot carries: pitch 1.5, len 4, loop 1 -> 0, 1.5, 3, 4.5 -> 1.5, 3, ... */
    setup();
    ramp(0x5000, 4);
    play(3, 0x5000, 4, 1, 0x18000, 255, 0, 2);
    audio_mix_tick(m);
    int seq2[8] = {0, 1, 3, 1, 3, 1, 3, 1};
    ok = 1;
    for (int i = 0; i < 8; i++) ok &= L(i) == seq2[i] * 255;
    CHECK(ok);

    /* Large pitch wraps modulo the loop length. pitch 9, len 4, loop 0: 0, 9->1, 10->2, 11->3, 12->0 */
    setup();
    ramp(0x5000, 4);
    play(3, 0x5000, 4, 0, 0x90000, 255, 0, 2);
    audio_mix_tick(m);
    int seq3[5] = {0, 1, 2, 3, 0};
    ok = 1;
    for (int i = 0; i < 5; i++) ok &= L(i) == seq3[i] * 255;
    CHECK(ok);

    /* LOOP >= LEN cannot loop: the channel stops at the end. */
    setup();
    ramp(0x5000, 4);
    m->ram[0x5000] = 9;
    play(3, 0x5000, 4, 4, 0x10000, 255, 0, 2);
    audio_mix_tick(m);
    CHECK_EQ(L(3), 3 * 255);
    CHECK_EQ(L(4), 0);
}

static void test_clip(void) {
    setup();
    memset(m->ram + 0x6000, 127, 16);
    for (int c = 0; c < 8; c++) play(c, 0x6000, 16, 0, 0x10000, 255, 255, 0);
    audio_mix_tick(m);
    CHECK_EQ(L(0), 32767);
    CHECK_EQ(R(15), 32767);
    CHECK_EQ(L(16), 0);
    setup();
    memset(m->ram + 0x6100, 0x80, 16);
    for (int c = 0; c < 8; c++) play(c, 0x6100, 16, 0, 0x10000, 255, 255, 0);
    audio_mix_tick(m);
    CHECK_EQ(L(0), -32768);
    /* two channels that cancel */
    setup();
    memset(m->ram + 0x6000, 127, 16);
    for (int i = 0; i < 16; i++) m->ram[0x6100 + i] = (uint8_t)(int8_t)-127;
    play(0, 0x6000, 16, 0, 0x10000, 200, 200, 0);
    play(5, 0x6100, 16, 0, 0x10000, 200, 200, 0);
    audio_mix_tick(m);
    CHECK_EQ(L(0), (127 * 256 * 200) / 256 + -((127 * 256 * 200 + 255) / 256));
}

static void test_registers(void) {
    setup();
    uint32_t v;
    CHECK_EQ(audio_io_write(m, 0x18, 5), -2);           /* POS is read-only */
    CHECK_EQ(audio_io_write(m, 0x7 * 0x20 + 0x18, 5), -2);
    CHECK_EQ(audio_io_write(m, 0x1C, 5), -1);           /* reserved */
    CHECK_EQ(audio_io_read(m, 0x1C, &v), -1);
    CHECK_EQ(audio_io_read(m, 0x3C, &v), -1);
    CHECK_EQ(audio_io_read(m, 0x100, &v), -1);          /* past channel 7 */
    CHECK_EQ(audio_io_write(m, 0x100, 0), -1);
    CHECK_EQ(audio_io_read(m, 0x02, &v), -1);           /* unaligned */
    wr(6, IO_AUD_ADDR, 0x123456);
    wr(6, IO_AUD_LEN, 1000);
    wr(6, IO_AUD_LOOP, 7);
    wr(6, IO_AUD_PITCH, 0x12345);
    wr(6, IO_AUD_VOL, 0xA0B0);
    CHECK_EQ(rd(6, IO_AUD_ADDR), 0x123456);
    CHECK_EQ(rd(6, IO_AUD_LEN), 1000);
    CHECK_EQ(rd(6, IO_AUD_LOOP), 7);
    CHECK_EQ(rd(6, IO_AUD_PITCH), 0x12345);
    CHECK_EQ(rd(6, IO_AUD_VOL), 0xA0B0);
    CHECK_EQ(rd(5, IO_AUD_ADDR), 0);

    /* POS advances one per output sample at pitch 1.0 */
    setup();
    play(4, 0x10000, 100000, 0, 0x10000, 0, 0, 0);
    CHECK_EQ(rd(4, IO_AUD_POS), 0);
    audio_mix_tick(m);
    CHECK_EQ(rd(4, IO_AUD_POS), 367);
    audio_mix_tick(m);
    CHECK_EQ(rd(4, IO_AUD_POS), 735);
    CHECK_EQ(rd(4, IO_AUD_CTRL), 1);
    wr(4, IO_AUD_CTRL, 1);            /* restart */
    CHECK_EQ(rd(4, IO_AUD_POS), 0);
    wr(4, IO_AUD_CTRL, 6);            /* bit 0 clear stops */
    CHECK_EQ(rd(4, IO_AUD_CTRL), 6);
    audio_mix_tick(m);
    CHECK_EQ(rd(4, IO_AUD_POS), 0);

    /* Sample data outside RAM/ROM stops the channel silently. */
    setup();
    play(0, VRAM_BASE, 100, 0, 0x10000, 255, 255, 0);
    audio_mix_tick(m);
    CHECK_EQ(rd(0, IO_AUD_CTRL) & 1, 0);
    CHECK_EQ(L(0), 0);
    CHECK_EQ(m->fault.kind, MEI_FAULT_NONE);
    setup();                          /* runs off the end of ROM mid-sample */
    m->rom[ROM_SIZE - 1] = 0x40;
    play(0, ROM_BASE + ROM_SIZE - 2, 100, 0, 0x10000, 0, 255, 0);
    audio_mix_tick(m);
    CHECK_EQ(R(0), 0);
    CHECK_EQ(R(1), 0x4000 * 255 / 256);
    CHECK_EQ(R(2), 0);
    CHECK_EQ(rd(0, IO_AUD_CTRL) & 1, 0);
    setup();                          /* 16-bit sample straddling the end of ROM */
    play(0, ROM_BASE + ROM_SIZE - 1, 100, 0, 0x10000, 0, 255, 4);
    audio_mix_tick(m);
    CHECK_EQ(rd(0, IO_AUD_CTRL) & 1, 0);

    /* LEN = 0 plays nothing. */
    setup();
    memset(m->ram + 0x100, 100, 4);
    play(0, 0x100, 0, 0, 0x10000, 255, 255, 2);
    audio_mix_tick(m);
    CHECK_EQ(L(0), 0);
    CHECK_EQ(rd(0, IO_AUD_CTRL) & 1, 0);
}

int main(void) {
    m = mei_create();
    if (!m) return 1;
    test_tick_sizes();
    test_8bit();
    test_16bit();
    test_pitch();
    test_loop();
    test_clip();
    test_registers();
    mei_destroy(m);
    printf("test_audio: %d/%d checks passed\n", checks - fails, checks);
    return fails != 0;
}
