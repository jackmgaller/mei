/* Public core API: cart loading, reset, the per-tick frame loop, input latching. */
#include "machine.h"

#include <stdlib.h>
#include <string.h>

#define RNG_RESET_SEED 0x4D454921u
#define STICK_ONE      65536
#define STICK_DEAD     13107          /* 0.2 in 16.16, rounded down */

Mei *mei_create(void) {
    Mei *m = calloc(1, sizeof *m);
    if (m) mei_reset(m);
    return m;
}

void mei_destroy(Mei *m) { free(m); }

int mei_load_cart(Mei *m, const uint8_t *data, size_t len) {
    if (!data || len == 0 || len > ROM_SIZE) return -1;
    memset(m->rom, 0, sizeof m->rom);
    memcpy(m->rom, data, len);
    m->rom_len = (uint32_t)len;
    memset(m->title, 0, sizeof m->title);
    if (len >= 40 && !memcmp(data + 4, "MEI1", 4)) memcpy(m->title, data + 8, 32);
    card_set_cart_id(m);
    m->privileged = 0;
    mei_reset(m);
    return 0;
}

void mei_reset(Mei *m) {
    memset(m->ram, 0, sizeof m->ram);
    memset(m->vram, 0, sizeof m->vram);
    cpu_reset(m);
    m->frame = 0;
    m->rng = RNG_RESET_SEED;
    memset(&m->fault, 0, sizeof m->fault);
    m->launch_pending = 0;
    memset(&m->card_regs, 0, sizeof m->card_regs);
    m->card_busy = 0;
    m->clock[0] = m->clock_pending[0];
    m->clock[1] = m->clock_pending[1];
    memset(m->pad_buttons, 0, sizeof m->pad_buttons);
    memset(m->pad_stick, 0, sizeof m->pad_stick);
    gpu_reset(m);
    audio_reset(m);
    if (m->rom_len == 0) {
        mei_raise(m, MEI_FAULT_NO_CART, 0);
        gpu_render_error_screen(m);
    }
}

const char *mei_cart_title(const Mei *m) { return m->title; }

int mei_launch_request(Mei *m, uint32_t *index) {
    if (!m->launch_pending) return 0;
    m->launch_pending = 0;
    *index = m->launch_index;
    return 1;
}

uint32_t mei_config(Mei *m, int *dirty) {
    if (dirty) { *dirty = m->config_dirty; m->config_dirty = 0; }
    return m->sys_config;
}

void mei_set_config(Mei *m, uint32_t value) { m->sys_config = value; m->config_dirty = 0; }

void mei_card_insert(Mei *m, int slot, uint8_t *image) {
    if (slot < 0 || slot > 1) return;
    m->card[slot] = image;
    m->card_dirty[slot] = 0;
}

int mei_card_dirty(Mei *m, int slot) {
    if (slot < 0 || slot > 1 || !m->card_dirty[slot]) return 0;
    m->card_dirty[slot] = 0;
    return 1;
}

void mei_set_privileged(Mei *m, int on) { m->privileged = on; }

void mei_set_clock(Mei *m, int year, int month, int day, int weekday, int hour, int minute, int second) {
    m->clock_pending[0] = (uint32_t)(hour * 3600 + minute * 60 + second);
    m->clock_pending[1] = (uint32_t)(day | month << 5 | weekday << 9 | year << 16);
}

void mei_set_pad(Mei *m, int index, const MeiPadInput *in) {
    if (index >= 0 && index < 2 && in) m->pad_pending[index] = *in;
}

/* Float -> 16.16, rounded to nearest and clamped to -1..1. This is the only
 * float math in the core; the multiply by 2^16 is exact, so it is deterministic. */
static int32_t stick_fixed(float f) {
    if (!(f == f)) return 0;                       /* NaN */
    double d = (double)f * STICK_ONE;
    if (d >= STICK_ONE) return STICK_ONE;
    if (d <= -STICK_ONE) return -STICK_ONE;
    return (int32_t)(d < 0 ? d - 0.5 : d + 0.5);
}

static uint32_t isqrt64(uint64_t n) {
    uint64_t r = 0, bit = (uint64_t)1 << 62;
    while (bit > n) bit >>= 2;
    while (bit) {
        if (n >= r + bit) { n -= r + bit; r = (r >> 1) + bit; }
        else r >>= 1;
        bit >>= 2;
    }
    return (uint32_t)r;
}

/* Radial dead zone of 0.2, rescaled so its edge reads 0 and full deflection
 * reads 1.0, clamped to unit length. Integer math after the conversion. */
static void latch_stick(const MeiPadInput *in, int32_t out[2]) {
    int64_t x = stick_fixed(in->stick_x), y = stick_fixed(in->stick_y);
    int64_t mag = isqrt64((uint64_t)(x * x + y * y));
    if (mag <= STICK_DEAD) { out[0] = out[1] = 0; return; }
    int64_t s = (mag - STICK_DEAD) * STICK_ONE / (STICK_ONE - STICK_DEAD);
    if (s > STICK_ONE) s = STICK_ONE;
    out[0] = (int32_t)(x * s / mag);
    out[1] = (int32_t)(y * s / mag);
}

int mei_run_frame(Mei *m) {
    int presented = 0;
    if (!m->fault.kind) {
        m->cycles = MEI_CYCLES_PER_FRAME;
        m->vsync_hit = 0;
        cpu_run(m);
        if (m->vsync_hit) {
            gpu_vsync(m);
            for (int i = 0; i < 2; i++) {
                m->pad_buttons[i] = m->pad_pending[i].buttons;
                latch_stick(&m->pad_pending[i], m->pad_stick[i]);
            }
            m->clock[0] = m->clock_pending[0];
            m->clock[1] = m->clock_pending[1];
            card_vsync(m);
            presented = 1;
        }
        m->frame++;
        if (m->fault.kind) {
            for (int i = 0; i < AUD_CHANNELS; i++) m->ch[i].playing = 0;
            gpu_render_error_screen(m);
        }
    }
    audio_mix_tick(m);   /* silent once faulted: every channel was stopped */
    return presented;
}

const uint16_t *mei_display(Mei *m) {
    return m->fault.kind ? m->error_screen : gpu_front(m);
}

int mei_audio(Mei *m, const int16_t **samples) {
    if (samples) *samples = m->audio_out;
    return m->audio_frames;
}

const MeiFault *mei_fault(const Mei *m) { return &m->fault; }

const char *mei_fault_name(MeiFaultKind k) {
    static const char *const names[] = {
        [MEI_FAULT_NONE] = "None",
        [MEI_FAULT_BREAK] = "Break",
        [MEI_FAULT_ILLEGAL] = "Illegal instruction",
        [MEI_FAULT_MISALIGNED] = "Misaligned access",
        [MEI_FAULT_UNMAPPED] = "Unmapped address",
        [MEI_FAULT_READ_ONLY] = "Read-only write",
        [MEI_FAULT_IO_WIDTH] = "Bad I/O width",
        [MEI_FAULT_BAD_PACKET_LIST] = "Bad packet list",
        [MEI_FAULT_NO_CART] = "No cart",
    };
    return (unsigned)k < sizeof names / sizeof *names ? names[k] : "Unknown";
}

void mei_set_debug_output(Mei *m, MeiDebugFn fn, void *user) {
    m->debug_fn = fn;
    m->debug_user = user;
}
