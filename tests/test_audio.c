/* Audio tests: tick sizes, sample formats, volume, pitch, looping, clipping, registers;
 * ADPCM (against tests/adpcm_vectors.h from the Python reference), channels 8-15, reverb. */
#include "machine.h"
#include "adpcm_vectors.h"

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

/* I/O offset of channel ch's registers (0-7 at 0x100, 8-15 at 0x400). */
static uint32_t cbase(int ch) { return ch < 8 ? IO_AUDIO + (uint32_t)ch * 0x20 : IO_AUDIO_HI + (uint32_t)(ch - 8) * 0x20; }
static void wr(int ch, uint32_t reg, uint32_t v) { CHECK_EQ(audio_io_write(m, cbase(ch) + reg, v), 0); }
static uint32_t rd(int ch, uint32_t reg) { uint32_t v = 0xDEAD; CHECK_EQ(audio_io_read(m, cbase(ch) + reg, &v), 0); return v; }

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
    CHECK_EQ(audio_io_write(m, IO_AUDIO + 0x18, 5), -2);           /* POS is read-only */
    CHECK_EQ(audio_io_write(m, IO_AUDIO + 0x7 * 0x20 + 0x18, 5), -2);
    CHECK_EQ(audio_io_write(m, IO_AUDIO + 0x1C, 5), -1);           /* reserved */
    CHECK_EQ(audio_io_read(m, IO_AUDIO + 0x1C, &v), -1);
    CHECK_EQ(audio_io_read(m, IO_AUDIO + 0x3C, &v), -1);
    CHECK_EQ(audio_io_read(m, IO_AUDIO + 0x100, &v), -1);          /* past channel 7 */
    CHECK_EQ(audio_io_write(m, IO_AUDIO + 0x100, 0), -1);
    CHECK_EQ(audio_io_read(m, IO_AUDIO + 0x02, &v), -1);           /* unaligned */
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

static int32_t asr8_ref(int32_t x) { return x >= 0 ? x / 256 : -((-x + 255) / 256); }   /* floor */

/* ---------------------------------------------------------------- backward compatibility */

/* A busy 8-channel PCM scene through the bus (absolute addresses work for both the old
 * and the new core); returns an FNV-1a hash of 40 ticks of output. */
static uint32_t legacy_scene_hash(Mei *mm) {
    uint32_t seed = 12345;
    for (uint32_t i = 0; i < 0x20000; i++) {
        seed = seed * 1103515245u + 12345u;
        mm->ram[0x40000 + i] = (uint8_t)(seed >> 16);
    }
    for (uint32_t i = 0; i < 0x8000; i++)          /* a smooth 16-bit wave */
        wr16(mm->ram + 0x80000 + 2 * i, (uint16_t)(int16_t)((int32_t)((i * 37) & 0xFFFF) - 32768));
    static const uint32_t cfg[8][7] = {   /* addr, len, loop, pitch, vol, ctrl */
        {0x40000, 5000, 100, 0x10000, 0x8040, 3},
        {0x80000, 0x8000, 0, 0xBB33, 0x30C0, 7},
        {0x41000, 900, 0, 0x34CCC, 0xFFFF, 1},
        {0x80100, 3000, 2999, 0x18000, 0x6060, 7},
        {0x42000, 100000, 0, 0x2000, 0x10F0, 1},
        {0x50000, 777, 3, 0x91234, 0xF010, 3},
        {0x80000, 200, 50, 0x10000, 0xFFFF, 6},     /* written but not started */
        {0x1FFF00, 0x1000, 0, 0x10000, 0x8080, 1},  /* runs off the end of RAM into ROM */
    };
    uint32_t h = 2166136261u;
    for (int k = 0; k < 8; k++) {
        uint32_t base = 0xFF0100 + (uint32_t)k * 0x20;
        for (int r = 0; r < 6; r++) bus_write32(mm, base + (uint32_t)r * 4, cfg[k][r]);
    }
    for (int t = 0; t < 40; t++) {
        if (t == 20) bus_write32(mm, 0xFF0100 + 2 * 0x20 + 0x14, 1);   /* restart ch 2 */
        audio_mix_tick(mm);
        for (int i = 0; i < mm->audio_frames * 2; i++) {
            uint16_t v = (uint16_t)mm->audio_out[i];
            h = (h ^ (v & 0xFF)) * 16777619u;
            h = (h ^ (v >> 8)) * 16777619u;
        }
    }
    return h;
}

/* The old 8-bit/16-bit behaviour is unchanged: this hash was produced by the 8-channel core
 * before the upgrade (same scene, same bus writes). */
static void test_legacy_unchanged(void) {
    setup();
    memset(m->rom, 0, 0x1000);   /* channel 7 runs into ROM, which was blank */
    CHECK_EQ(legacy_scene_hash(m), 0x8277EC03u);
    CHECK_EQ(m->fault.kind, MEI_FAULT_NONE);
}

/* ---------------------------------------------------------------- ADPCM */

static uint32_t mix_into(int16_t *l, int16_t *r, int n) {   /* runs ticks until n outputs */
    int got = 0;
    while (got < n) {
        audio_mix_tick(m);
        for (int i = 0; i < m->audio_frames && got < n; i++, got++) {
            if (l) l[got] = L(i);
            if (r) r[got] = R(i);
        }
    }
    return (uint32_t)got;
}

static void test_adpcm_decode(void) {
    /* The decode step against the Python reference: every header byte 0-255 (all shifts,
     * all filters including the reserved ones), random nibbles, history carried across. */
    int32_t h1 = 0, h2 = 0, ok = 1, bad = -1;
    for (int n = 0; n < ADPCM_VEC_BLOCKS_N * 28; n++) {
        const uint8_t *b = ADPCM_VEC_BLOCKS + (n / 28) * 16;
        int j = n % 28;
        int32_t s = audio_adpcm_sample(b[0], (j & 1) ? b[2 + j / 2] >> 4 : b[2 + j / 2] & 15, &h1, &h2);
        if (s != ADPCM_VEC_DECODED[n] && bad < 0) bad = n;
        ok &= s == ADPCM_VEC_DECODED[n];
    }
    CHECK(ok);
    CHECK_EQ(bad, -1);
    h1 = h2 = 0;
    ok = 1;
    for (int n = 0; n < ADPCM_VEC_MUSIC_N; n++) {
        const uint8_t *b = ADPCM_VEC_MUSIC + (n / 28) * 16;
        int j = n % 28;
        ok &= audio_adpcm_sample(b[0], (j & 1) ? b[2 + j / 2] >> 4 : b[2 + j / 2] & 15, &h1, &h2)
              == ADPCM_VEC_MUSIC_DECODED[n];
    }
    CHECK(ok);

    /* Hand-checked steps. Filter 1 (60/64), shift 12: nibble 7 -> 7 + floor((1000*60 + 32) / 64). */
    h1 = 1000; h2 = -500;
    CHECK_EQ(audio_adpcm_sample(0x1C, 7, &h1, &h2), 7 + 938);
    CHECK_EQ(h1, 945);
    CHECK_EQ(h2, 1000);
    h1 = 0; h2 = 0;
    CHECK_EQ(audio_adpcm_sample(0x00, 8, &h1, &h2), -32768);     /* -8 << 12 */
    CHECK_EQ(audio_adpcm_sample(0x00, 7, &h1, &h2), 28672);
    CHECK_EQ(audio_adpcm_sample(0x0D, 1, &h1, &h2), 8);          /* shift 13 acts as 9 */
    h1 = 32767; h2 = -32768;
    CHECK_EQ(audio_adpcm_sample(0x40, 7, &h1, &h2), 32767);      /* clamps */
    h1 = -3; h2 = 5;
    CHECK_EQ(audio_adpcm_sample(0x5C, 0, &h1, &h2), 0);          /* filter 5: no prediction */
    h1 = -1; h2 = 0;
    CHECK_EQ(audio_adpcm_sample(0x1C, 0, &h1, &h2), -1);         /* floor((-60 + 32) / 64) = -1 */
}

static void load_blocks(uint32_t addr, const uint8_t *b, uint32_t n) { memcpy(m->ram + addr, b, n); }

static void play_adpcm_ch(int ch, uint32_t addr, uint32_t len, uint32_t loop, uint32_t pitch, int lv, int rv, uint32_t ctrl) {
    play(ch, addr, len, loop, pitch, lv, rv, ctrl | AUD_CTRL_ADPCM);
}

static void test_adpcm_channel(void) {
    /* Pitch, loops (LOOP not a multiple of 28, history carried over the wrap), the 16.0
     * pitch cap and running off the end, on channels 0-15, against the Python channel model. */
    static int16_t l[2400], r[2400];
    for (size_t k = 0; k < sizeof ADPCM_SCENARIOS / sizeof ADPCM_SCENARIOS[0]; k++) {
        const AdpcmScenario *sc = &ADPCM_SCENARIOS[k];
        setup();
        if (sc->music) load_blocks(0x10000, ADPCM_VEC_MUSIC, sizeof ADPCM_VEC_MUSIC);
        else load_blocks(0x10000, ADPCM_VEC_BLOCKS, sizeof ADPCM_VEC_BLOCKS);
        play_adpcm_ch(sc->ch, 0x10000, sc->len, sc->loop, sc->pitch, sc->vol_l, sc->vol_r, sc->looping ? 2 : 0);
        mix_into(l, r, sc->n);
        int first_bad = -1;
        for (int i = 0; i < sc->n; i++)
            if ((l[i] != sc->l[i] || r[i] != sc->r[i]) && first_bad < 0) first_bad = i;
        if (first_bad >= 0) printf("  scenario %d differs at output %d\n", (int)k, first_bad);
        CHECK_EQ(first_bad, -1);
    }

    /* POS, CTRL readback, restart resets the history. */
    setup();
    load_blocks(0x10000, ADPCM_VEC_MUSIC, sizeof ADPCM_VEC_MUSIC);
    play_adpcm_ch(10, 0x10000, ADPCM_VEC_MUSIC_N, 0, 0x10000, 255, 0, AUD_CTRL_16BIT);   /* ADPCM wins over 16-bit */
    CHECK_EQ(rd(10, IO_AUD_CTRL), 1 | AUD_CTRL_16BIT | AUD_CTRL_ADPCM);
    int16_t a[400], b[400];
    mix_into(a, NULL, 400);
    CHECK_EQ(rd(10, IO_AUD_POS), 735);   /* two ticks ran */
    wr(10, IO_AUD_CTRL, 1 | AUD_CTRL_ADPCM);
    CHECK_EQ(rd(10, IO_AUD_POS), 0);
    mix_into(b, NULL, 400);
    CHECK(!memcmp(a, b, sizeof a));
    int ok = 1;
    for (int i = 0; i < 400; i++) ok &= a[i] == asr8_ref(ADPCM_VEC_MUSIC_DECODED[i] * 255);
    CHECK(ok);

    /* A loop to a filter-0 block (no prediction, so no history) repeats exactly. */
    setup();
    load_blocks(0x10000, ADPCM_VEC_MUSIC, sizeof ADPCM_VEC_MUSIC);
    m->ram[0x10000 + 10 * 16] &= 0x0F;   /* block 10: filter 0 */
    play_adpcm_ch(4, 0x10000, 560, 280, 0x10000, 255, 0, 2);
    static int16_t lp[1200];
    mix_into(lp, NULL, 1120);
    CHECK(!memcmp(lp + 280, lp + 560, 280 * sizeof lp[0]));
    CHECK(!memcmp(lp + 560, lp + 840, 280 * sizeof lp[0]));

    /* ... whereas a loop into a predicting block continues from the current history. */
    setup();
    load_blocks(0x10000, ADPCM_VEC_MUSIC, sizeof ADPCM_VEC_MUSIC);
    play_adpcm_ch(4, 0x10000, 560, 280, 0x10000, 255, 0, 2);
    mix_into(lp, NULL, 1120);
    CHECK((m->ram[0x10000 + 10 * 16] >> 4) != 0);
    CHECK(memcmp(lp + 280, lp + 560, 28 * sizeof lp[0]) != 0);

    /* Out-of-range reads stop the channel: a block whose header is the last byte of ROM. */
    setup();
    m->rom[ROM_SIZE - 1] = 0x0C;
    play_adpcm_ch(1, ROM_BASE + ROM_SIZE - 1, 28, 0, 0x10000, 255, 255, 0);
    audio_mix_tick(m);
    CHECK_EQ(rd(1, IO_AUD_CTRL) & 1, 0);
    CHECK_EQ(L(0), 0);
    CHECK_EQ(m->fault.kind, MEI_FAULT_NONE);
    /* The last block of RAM decodes, and the next one (in ROM) too. */
    setup();
    memset(m->ram + RAM_SIZE - 16, 0, 16);
    m->ram[RAM_SIZE - 16] = 0x04;              /* shift 4: a nibble step of 256 */
    m->ram[RAM_SIZE - 14] = 0x31;              /* samples 0, 1: nibbles 1, 3 */
    m->rom[0] = 0x04;
    m->rom[2] = 0x02;
    play_adpcm_ch(1, RAM_SIZE - 16, 56, 0, 0x10000, 0, 255, 0);
    audio_mix_tick(m);
    CHECK_EQ(R(0), 255);
    CHECK_EQ(R(1), 3 * 255);
    CHECK_EQ(R(27), 0);
    CHECK_EQ(R(28), 2 * 255);
    CHECK_EQ(R(56), 0);
    /* Pitch skipping into an unmapped block stops the channel there. */
    setup();
    play_adpcm_ch(1, VRAM_BASE - 32, 1000, 0, 0x100000, 255, 255, 0);
    audio_mix_tick(m);   /* the last two blocks of ROM, then block 2 lies in VRAM */
    CHECK_EQ(m->ch[1].dec, 56);
    CHECK_EQ(rd(1, IO_AUD_CTRL) & 1, 0);
}

/* ---------------------------------------------------------------- channels 8-15 */

static void test_channels_hi(void) {
    setup();
    uint32_t v;
    for (int c = 0; c < 16; c++) wr(c, IO_AUD_ADDR, 0x1000u + (uint32_t)c);
    for (int c = 0; c < 16; c++) CHECK_EQ(rd(c, IO_AUD_ADDR), 0x1000u + (uint32_t)c);
    CHECK_EQ(m->ch[12].addr, 0x100C);
    CHECK_EQ(audio_io_write(m, IO_AUDIO_HI + 7 * 0x20 + 0x18, 1), -2);   /* POS read-only */
    CHECK_EQ(audio_io_read(m, IO_AUDIO_HI + 0x1C, &v), -1);              /* reserved */
    CHECK_EQ(audio_io_read(m, IO_AUDIO_HI + 0x3C, &v), -1);
    CHECK_EQ(audio_io_read(m, IO_AUDIO_HI + 0x06, &v), -1);              /* unaligned */
    CHECK_EQ(audio_io_read(m, IO_AUD_GLOBAL + 0x10, &v), -1);            /* past the globals */
    CHECK_EQ(audio_io_read(m, IO_AUD_GLOBAL + 0xFC, &v), -1);
    CHECK_EQ(audio_io_write(m, IO_AUD_ACTIVE, 0), -2);

    /* 16 channels of 127 at full volume clip; 16 at volume 16 sum exactly. */
    memset(m->ram + 0x6000, 127, 16);
    for (int c = 0; c < 16; c++) play(c, 0x6000, 16, 0, 0x10000, 16, 16, 0);
    CHECK_EQ(rd(0, 0) , 0x6000);
    CHECK_EQ(audio_io_read(m, IO_AUD_ACTIVE, &v), 0);
    CHECK_EQ(v, 0xFFFF);
    audio_mix_tick(m);
    CHECK_EQ(L(0), 16 * (127 * 256 * 16 / 256));
    CHECK_EQ(L(16), 0);
    CHECK_EQ(audio_io_read(m, IO_AUD_ACTIVE, &v), 0);
    CHECK_EQ(v, 0);
    setup();
    memset(m->ram + 0x6000, 127, 16);
    for (int c = 0; c < 16; c++) play(c, 0x6000, 16, 0, 0x10000, 255, 255, 0);
    audio_mix_tick(m);
    CHECK_EQ(R(3), 32767);
    setup();
    memset(m->ram + 0x6000, 0x80, 16);
    for (int c = 8; c < 16; c++) play(c, 0x6000, 16, 0, 0x10000, 255, 255, 0);
    audio_mix_tick(m);
    CHECK_EQ(L(0), -32768);

    /* A channel 8-15 behaves like 0-7: same data, same output. */
    setup();
    ramp(0x4000, 100);
    play(13, 0x4000, 100, 10, 0x18000, 200, 30, 2);
    static int16_t a[600], b[600];
    mix_into(a, b, 600);
    setup();
    ramp(0x4000, 100);
    play(5, 0x4000, 100, 10, 0x18000, 200, 30, 2);
    static int16_t c2[600], d2[600];
    mix_into(c2, d2, 600);
    CHECK(!memcmp(a, c2, sizeof a));
    CHECK(!memcmp(b, d2, sizeof b));
    CHECK_EQ(audio_io_read(m, IO_AUD_ACTIVE, &v), 0);
    CHECK_EQ(v, 1u << 5);

    /* CTRL bit 7 changes loop and reverb send without restarting. */
    setup();
    ramp(0x4000, 100);
    play(11, 0x4000, 100, 0, 0x10000, 255, 0, 2);
    audio_mix_tick(m);
    uint32_t pos = rd(11, IO_AUD_POS);
    wr(11, IO_AUD_CTRL, AUD_CTRL_UPDATE | AUD_CTRL_REVERB | 1 | AUD_CTRL_16BIT);   /* only bits 1, 4 apply */
    CHECK_EQ(rd(11, IO_AUD_POS), pos);
    CHECK_EQ(rd(11, IO_AUD_CTRL), 1 | AUD_CTRL_REVERB);    /* loop cleared, still playing 8-bit */
    audio_mix_tick(m);
    CHECK_EQ(rd(11, IO_AUD_CTRL) & 1, 0);                  /* ran off the end */
}

/* Faults for the new I/O space, through the bus. */
static void test_io_faults(void) {
    static const struct { uint32_t addr; MeiFaultKind k; } rd_cases[] = {
        {0xFF041C, MEI_FAULT_UNMAPPED}, {0xFF04FC, MEI_FAULT_UNMAPPED}, {0xFF0510, MEI_FAULT_UNMAPPED},
        {0xFF0580, MEI_FAULT_UNMAPPED}, {0xFF05FC, MEI_FAULT_UNMAPPED}, {0xFF0800, MEI_FAULT_UNMAPPED},   /* 0x600: broadcast, 0x700: planes */
        {0xFF0402, MEI_FAULT_MISALIGNED},
    };
    uint32_t v;
    for (size_t i = 0; i < sizeof rd_cases / sizeof rd_cases[0]; i++) {
        setup();
        CHECK_EQ(bus_read32(m, rd_cases[i].addr, &v), -1);
        CHECK_EQ(m->fault.kind, rd_cases[i].k);
        CHECK_EQ(m->fault.addr, rd_cases[i].addr);
    }
    setup();
    CHECK_EQ(bus_read8(m, 0xFF0400, &v, 0), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_IO_WIDTH);
    setup();
    CHECK_EQ(bus_write32(m, 0xFF050C, 1), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_READ_ONLY);
    setup();
    CHECK_EQ(bus_write32(m, 0xFF0400 + 4 * 0x20 + 0x18, 1), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_READ_ONLY);
    setup();
    CHECK_EQ(bus_write32(m, 0xFF04E0, 0x1234), 0);   /* channel 15 ADDR */
    CHECK_EQ(bus_read32(m, 0xFF04E0, &v), 0);
    CHECK_EQ(v, 0x1234);
    CHECK_EQ(bus_write32(m, 0xFF0500, 3), 0);
    CHECK_EQ(bus_write32(m, 0xFF0504, 0x8080), 0);
    CHECK_EQ(bus_write32(m, 0xFF0508, 200), 0);
    CHECK_EQ(bus_read32(m, 0xFF0500, &v), 0);
    CHECK_EQ(v, 3);
    CHECK_EQ(bus_read32(m, 0xFF0504, &v), 0);
    CHECK_EQ(v, 0x8080);
    CHECK_EQ(bus_read32(m, 0xFF0508, &v), 0);
    CHECK_EQ(v, 200);
    CHECK_EQ(bus_read32(m, 0xFF050C, &v), 0);
    CHECK_EQ(v, 0);
    CHECK_EQ(m->fault.kind, MEI_FAULT_NONE);
    /* The old reserved +1C of channels 0-7 still faults. */
    CHECK_EQ(bus_read32(m, 0xFF011C, &v), -1);
    CHECK_EQ(m->fault.kind, MEI_FAULT_UNMAPPED);
}

/* ---------------------------------------------------------------- reverb */

static uint32_t hash_out(uint32_t h) {
    for (int i = 0; i < m->audio_frames * 2; i++) {
        uint16_t v = (uint16_t)m->audio_out[i];
        h = (h ^ (v & 0xFF)) * 16777619u;
        h = (h ^ (v >> 8)) * 16777619u;
    }
    return h;
}

/* A short burst on channel 9 sent to the reverb; returns the hash of `ticks` ticks. */
static uint32_t reverb_scene(uint32_t preset, uint32_t decay, int ticks, int64_t *tail_energy) {
    setup();
    for (int i = 0; i < 2000; i++) wr16(m->ram + 0x8000 + 2 * i, (uint16_t)(int16_t)(((i * 7919) % 20001) - 10000));
    CHECK_EQ(audio_io_write(m, IO_REV_CTRL, preset), 0);
    CHECK_EQ(audio_io_write(m, IO_REV_VOL, 0xC0FF), 0);
    CHECK_EQ(audio_io_write(m, IO_REV_DECAY, decay), 0);
    play(9, 0x8000, 2000, 0, 0x10000, 200, 120, AUD_CTRL_16BIT | AUD_CTRL_REVERB);
    uint32_t h = 2166136261u;
    int64_t e = 0;
    for (int t = 0; t < ticks; t++) {
        audio_mix_tick(m);
        h = hash_out(h);
        if (t >= 30)
            for (int i = 0; i < m->audio_frames * 2; i++) e += (int64_t)m->audio_out[i] * m->audio_out[i];
    }
    if (tail_energy) *tail_energy = e;
    return h;
}

static void test_reverb(void) {
    /* Off: the send bit changes nothing. */
    uint32_t dry = reverb_scene(0, 0, 60, NULL);
    setup();
    for (int i = 0; i < 2000; i++) wr16(m->ram + 0x8000 + 2 * i, (uint16_t)(int16_t)(((i * 7919) % 20001) - 10000));
    play(9, 0x8000, 2000, 0, 0x10000, 200, 120, AUD_CTRL_16BIT);
    uint32_t h = 2166136261u;
    for (int t = 0; t < 60; t++) { audio_mix_tick(m); h = hash_out(h); }
    CHECK_EQ(h, dry);
    CHECK_EQ(reverb_scene(6, 0, 60, NULL), dry);      /* presets 6-15 are off */
    CHECK_EQ(reverb_scene(15, 0, 60, NULL), dry);

    /* Each preset is deterministic, differs from the others and has a tail. Golden hashes
     * pin the algorithm: a change to the reverb must update them deliberately. */
    static const uint32_t golden[6] = {0, 0xEC3CBF92u, 0xF8A85318u, 0x5FA338F8u, 0x8818F7EEu, 0x7D792E8Bu};
    uint32_t hs[6];
    for (uint32_t p = 1; p <= 5; p++) {
        int64_t e1, e2;
        hs[p] = reverb_scene(p, 0, 120, &e1);
        CHECK_EQ(reverb_scene(p, 0, 120, &e2), hs[p]);
        CHECK_EQ(e1, e2);
        CHECK(hs[p] != dry);
        CHECK(e1 > 0);                               /* sound after the dry burst ended */
        int64_t es;
        reverb_scene(p, 64, 120, &es);               /* REV_DECAY 64: a quarter of the feedback */
        CHECK(es < e1);
        if (hs[p] != golden[p]) printf("  reverb preset %u hash 0x%08X\n", p, hs[p]);
        CHECK_EQ(hs[p], golden[p]);
    }
    for (int p = 1; p <= 5; p++)
        for (int q = p + 1; q <= 5; q++) CHECK(hs[p] != hs[q]);

    /* The dry burst is 2000 samples: with the reverb off, ticks 6+ are silent. */
    int64_t e0;
    reverb_scene(0, 0, 120, &e0);
    CHECK_EQ(e0, 0);

    /* The tail decays to exactly zero, and so does all reverb memory (integer truncation
     * toward zero in every feedback path). */
    for (uint32_t p = 1; p <= 5; p++) {
        reverb_scene(p, 0, 1, NULL);
        for (int t = 0; t < 60 * 40; t++) audio_mix_tick(m);
        int nz = 0;
        for (int i = 0; i < REV_POOL; i++) nz += m->rev.buf[i] != 0;
        for (int i = 0; i < 8; i++) nz += m->rev.lp[i] != 0;
        CHECK_EQ(nz, 0);
        CHECK_EQ(L(0), 0);
        CHECK_EQ(R(100), 0);
    }

    /* Wet volume 0 mutes the reverb but it keeps running; switching preset clears it;
     * writing the same preset again does not. */
    reverb_scene(3, 0, 10, NULL);
    CHECK_EQ(audio_io_write(m, IO_REV_VOL, 0), 0);
    audio_mix_tick(m);
    CHECK_EQ(L(5), 0);
    int nz = 0;
    for (int i = 0; i < REV_POOL; i++) nz += m->rev.buf[i] != 0;
    CHECK(nz > 0);
    CHECK_EQ(audio_io_write(m, IO_REV_CTRL, 0x103), 0);   /* same preset (bits 0-3) */
    int nz2 = 0;
    for (int i = 0; i < REV_POOL; i++) nz2 += m->rev.buf[i] != 0;
    CHECK_EQ(nz2, nz);
    uint32_t v;
    CHECK_EQ(audio_io_read(m, IO_REV_CTRL, &v), 0);
    CHECK_EQ(v, 0x103);                                   /* all 32 bits read back */
    CHECK_EQ(audio_io_write(m, IO_REV_CTRL, 2), 0);
    nz2 = 0;
    for (int i = 0; i < REV_POOL; i++) nz2 += m->rev.buf[i] != 0;
    CHECK_EQ(nz2, 0);

    /* Reset clears the reverb; a fault silences it. */
    reverb_scene(4, 0, 10, NULL);
    mei_reset(m);
    CHECK_EQ(m->rev.preset, 0);
    CHECK_EQ(m->rev.vol, 0);
    reverb_scene(4, 0, 10, NULL);
    m->fault.kind = MEI_FAULT_BREAK;
    for (int c = 0; c < AUD_CHANNELS; c++) m->ch[c].playing = 0;
    audio_mix_tick(m);
    int ok = 1;
    for (int i = 0; i < m->audio_frames; i++) ok &= L(i) == 0 && R(i) == 0;
    CHECK(ok);

    /* Mixing: dry + wet, summed in 32 bits, hard-clipped. A full-scale square sent to the
     * hall at full wet volume clips cleanly, never wraps. */
    setup();
    for (int i = 0; i < 4000; i++) wr16(m->ram + 0x8000 + 2 * i, (i / 50) & 1 ? 0x7FFF : 0x8000);
    audio_io_write(m, IO_REV_CTRL, 3);
    audio_io_write(m, IO_REV_VOL, 0xFFFF);
    for (int c = 0; c < 16; c++) play(c, 0x8000, 4000, 0, 0x10000, 255, 255, AUD_CTRL_16BIT | AUD_CTRL_REVERB);
    int clipped = 0;
    for (int t = 0; t < 30; t++) {
        audio_mix_tick(m);
        for (int i = 0; i < m->audio_frames; i++) clipped += L(i) == 32767 || L(i) == -32768;
    }
    CHECK(clipped > 1000);
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
    test_legacy_unchanged();
    test_adpcm_decode();
    test_adpcm_channel();
    test_channels_hi();
    test_io_faults();
    test_reverb();
    mei_destroy(m);
    printf("test_audio: %d/%d checks passed\n", checks - fails, checks);
    return fails != 0;
}
