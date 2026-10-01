/* Audio: eight sample channels mixed to 22,050 Hz stereo, integer-only. */
#include "machine.h"

#include <string.h>

void audio_reset(Mei *m) {
    memset(m->ch, 0, sizeof m->ch);
    memset(m->audio_out, 0, sizeof m->audio_out);
    m->audio_frames = 0;
    m->audio_phase = 0;
}

int audio_io_read(Mei *m, uint32_t off, uint32_t *out) {
    if (off >= AUD_CHANNELS * 0x20u || (off & 3)) return -1;
    const MeiAudioChannel *c = &m->ch[off >> 5];
    switch (off & 0x1F) {
    case IO_AUD_ADDR:  *out = c->addr; return 0;
    case IO_AUD_LEN:   *out = c->len; return 0;
    case IO_AUD_LOOP:  *out = c->loop; return 0;
    case IO_AUD_PITCH: *out = c->pitch; return 0;
    case IO_AUD_VOL:   *out = c->vol; return 0;
    case IO_AUD_CTRL:  *out = (c->playing ? 1u : 0u) | (c->ctrl & 6); return 0;
    case IO_AUD_POS:   *out = (uint32_t)(c->pos >> 16); return 0;
    default:           return -1;   /* +1C reserved */
    }
}

int audio_io_write(Mei *m, uint32_t off, uint32_t val) {
    if (off >= AUD_CHANNELS * 0x20u || (off & 3)) return -1;
    MeiAudioChannel *c = &m->ch[off >> 5];
    switch (off & 0x1F) {
    case IO_AUD_ADDR:  c->addr = val; return 0;
    case IO_AUD_LEN:   c->len = val; return 0;
    case IO_AUD_LOOP:  c->loop = val; return 0;
    case IO_AUD_PITCH: c->pitch = val; return 0;
    case IO_AUD_VOL:   c->vol = val; return 0;
    case IO_AUD_CTRL:
        c->ctrl = val;
        if (val & 1) { c->pos = 0; c->playing = 1; }
        else c->playing = 0;
        return 0;
    case IO_AUD_POS:   return -2;
    default:           return -1;
    }
}

/* Byte of sample memory (RAM or ROM), or -1 outside them. */
static inline int sample_byte(const Mei *m, uint64_t a) {
    if (a < RAM_BASE + RAM_SIZE) return m->ram[a];
    if (a >= ROM_BASE && a < ROM_BASE + ROM_SIZE) return m->rom[a - ROM_BASE];
    return -1;
}

/* floor(x / 256) without relying on implementation-defined >> of negatives. */
static inline int32_t asr8(int32_t x) { return x >= 0 ? x >> 8 : ~((~x) >> 8); }

/* Current sample of a playing channel as signed 16-bit; stops the channel and
 * returns 0 when the read falls outside RAM/ROM or past LEN. */
static int32_t channel_sample(const Mei *m, MeiAudioChannel *c) {
    uint64_t idx = c->pos >> 16;
    if (idx >= c->len) { c->playing = 0; return 0; }
    if (c->ctrl & 4) {
        uint64_t a = c->addr + idx * 2;
        int lo = sample_byte(m, a), hi = sample_byte(m, a + 1);
        if (lo < 0 || hi < 0) { c->playing = 0; return 0; }
        return (int32_t)(lo | hi << 8) - ((hi & 0x80) ? 0x10000 : 0);
    }
    int b = sample_byte(m, (uint64_t)c->addr + idx);
    if (b < 0) { c->playing = 0; return 0; }
    return ((int32_t)b - ((b & 0x80) ? 0x100 : 0)) * 256;
}

static void channel_advance(MeiAudioChannel *c) {
    c->pos += c->pitch;
    uint64_t len = (uint64_t)c->len << 16;
    if (c->pos < len) return;
    if ((c->ctrl & 2) && c->loop < c->len) {
        uint64_t loop = (uint64_t)c->loop << 16;
        c->pos = loop + (c->pos - len) % (len - loop);
    } else {
        c->playing = 0;
    }
}

void audio_mix_tick(Mei *m) {
    /* 22,050 / 60 = 367.5: the remainder carries, so ticks alternate 367, 368. */
    m->audio_phase += MEI_AUDIO_RATE;
    int n = (int)(m->audio_phase / MEI_FPS);
    m->audio_phase -= (uint32_t)n * MEI_FPS;

    for (int i = 0; i < n; i++) {
        int32_t l = 0, r = 0;
        for (int k = 0; k < AUD_CHANNELS; k++) {
            MeiAudioChannel *c = &m->ch[k];
            if (!c->playing) continue;
            int32_t s = channel_sample(m, c);
            if (!c->playing) continue;
            l += asr8(s * (int32_t)(c->vol & 0xFF));
            r += asr8(s * (int32_t)((c->vol >> 8) & 0xFF));
            channel_advance(c);
        }
        m->audio_out[2 * i] = (int16_t)(l < -32768 ? -32768 : l > 32767 ? 32767 : l);
        m->audio_out[2 * i + 1] = (int16_t)(r < -32768 ? -32768 : r > 32767 ? 32767 : r);
    }
    m->audio_frames = n;
}
