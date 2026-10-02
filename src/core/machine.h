/* Internal machine state shared by the core modules (bus, cpu, gpu, audio). */
#ifndef MEI_MACHINE_H
#define MEI_MACHINE_H

#include "mei.h"

/* Memory map */
#define RAM_BASE   0x000000u
#define RAM_SIZE   0x200000u
#define ROM_BASE   0x200000u
#define ROM_SIZE   0x200000u
#define VRAM_BASE  0x400000u
#define VRAM_SIZE  0x100000u
#define IO_BASE    0xFF0000u
#define IO_SIZE    0x600u   /* 0x400-0x5FF: audio channels 8-15 and global audio registers */

/* VRAM layout (absolute addresses) */
#define FB_A_ADDR     0x400000u
#define FB_B_ADDR     0x425800u
#define FB_BYTES      (MEI_W * MEI_H * 2)
#define PALETTE_ADDR  0x44C000u
#define TEXTURE_ADDR  0x480000u
#define TEXTURE_SLOT_BYTES 0x8000u

/* I/O offsets from IO_BASE */
#define IO_GPU_DRAW    0x000
#define IO_GPU_CLEAR   0x004
#define IO_GPU_CTRL    0x008
#define IO_GPU_STATUS  0x00C
#define IO_GPU_BACK    0x010
#define IO_AUDIO       0x100   /* channel n at IO_AUDIO + n * 0x20 */
#define IO_AUD_ADDR    0x00
#define IO_AUD_LEN     0x04
#define IO_AUD_LOOP    0x08
#define IO_AUD_PITCH   0x0C
#define IO_AUD_VOL     0x10
#define IO_AUD_CTRL    0x14
#define IO_AUD_POS     0x18
#define IO_AUDIO_HI    0x400   /* channel n (8-15) at IO_AUDIO_HI + (n - 8) * 0x20 */
#define IO_AUD_GLOBAL  0x500   /* global audio registers, 0x500-0x50F */
#define IO_REV_CTRL    0x500   /* bits 0-3: reverb preset (0 off) */
#define IO_REV_VOL     0x504   /* bits 0-7: wet left volume, bits 8-15: wet right */
#define IO_REV_DECAY   0x508   /* bits 0-7: feedback scale /256 (0: preset default) */
#define IO_AUD_ACTIVE  0x50C   /* read-only: bit n = channel n playing */
/* Channel CTRL bits */
#define AUD_CTRL_PLAY    0x01u
#define AUD_CTRL_LOOP    0x02u
#define AUD_CTRL_16BIT   0x04u
#define AUD_CTRL_ADPCM   0x08u
#define AUD_CTRL_REVERB  0x10u
#define AUD_CTRL_UPDATE  0x80u   /* write only: change bits 1 and 4 without starting or stopping */
#define IO_PAD1        0x200
#define IO_PAD2        0x204
#define IO_STICK1_X    0x208
#define IO_STICK1_Y    0x20C
#define IO_STICK2_X    0x210
#define IO_STICK2_Y    0x214
#define IO_SYS_FRAME   0x300
#define IO_SYS_CYCLES  0x304
#define IO_SYS_RAND    0x308
#define IO_SYS_DEBUG   0x30C
#define IO_SYS_LAUNCH  0x310   /* extension for the system ROM: request a cart launch */
#define IO_SYS_CONFIG  0x314   /* extension: one persistent settings word */
#define IO_SYS_TIME    0x318   /* extension: local time of day, seconds since midnight */
#define IO_SYS_DATE    0x31C   /* extension: local date */
#define IO_CARD        0x380   /* extension: memory card controller, 0x380-0x39F */

#define GPU_TRI_LIMIT      2000
#define GPU_LIST_LIMIT     65536
#define GPU_STATUS_DROPPED (1u << 16)

#define AUD_CHANNELS 16
#define AUD_ADPCM_MAX_PITCH 0x100000u   /* ADPCM channels step at most 16.0 samples per output */
#define REV_POOL 24576                  /* reverb delay memory, in samples */

typedef struct {
    uint32_t slot, save, buf, len, meta, result, error;
} MeiCardRegs;

typedef struct {
    uint32_t addr, len, loop, pitch, vol, ctrl;
    uint64_t pos;       /* 32.16 fixed-point sample position */
    int playing;
    uint32_t dec;       /* ADPCM: index of the next sample to decode */
    int32_t h1, h2;     /* ADPCM: the last two decoded samples */
} MeiAudioChannel;

/* Global reverb (audio.c). The state lives in the core, not in cart RAM. */
typedef struct {
    uint32_t ctrl, vol, decay;   /* registers as written */
    int preset;                  /* active preset, 0 = off */
    int32_t gain[8];             /* feedback gains with REV_DECAY applied (Q15) */
    int32_t dc_x, dc_y;          /* input DC blocker */
    int32_t lp[8];               /* damping filters */
    uint32_t at[13];             /* ring positions: predelay, 4 diffusers, 8 lines */
    int32_t buf[REV_POOL];
} MeiReverb;

struct Mei {
    uint8_t ram[RAM_SIZE];
    uint8_t rom[ROM_SIZE];
    uint8_t vram[VRAM_SIZE];
    uint32_t rom_len;
    char title[33];

    /* CPU */
    uint32_t r[16];
    int32_t v[8][4];
    uint32_t pc;
    int32_t cycles;          /* cycles left in this tick */
    int vsync_hit;           /* set by vsync; ends the tick */

    /* System */
    uint32_t frame;          /* ticks since reset */
    uint32_t rng;            /* xorshift32 state */
    MeiFault fault;
    uint32_t launch_index;   /* SYS_LAUNCH request, for the platform */
    int launch_pending;
    uint32_t sys_config;     /* survives reset and cart changes; the platform persists it */
    int config_dirty;
    uint32_t clock_pending[2], clock[2];   /* time, date: set by the platform, latched at vsync */

    /* Memory cards (card.c); images owned by the platform */
    uint8_t *card[2];
    int card_dirty[2];
    MeiCardRegs card_regs;
    int card_busy;           /* frames until the controller is free */
    int privileged;          /* the system ROM is running */
    char cart_id[17];
    MeiDebugFn debug_fn;
    void *debug_user;
    char debug_tail[4][81];  /* the last lines of debug output (shown on the halt screen) */
    int debug_col;

    /* Input: pending from the platform, latched at vsync */
    MeiPadInput pad_pending[2];
    uint32_t pad_buttons[2];
    int32_t pad_stick[2][2]; /* 16.16, dead zone applied */

    /* GPU */
    int back;                /* 0: framebuffer A is the back buffer, 1: B */
    uint32_t gpu_ctrl;
    uint32_t gpu_status;     /* bits 0-15 triangle count, bit 16 dropped */
    MeiGpuStats gstat, gstat_last;   /* this frame so far / the last presented frame */
    uint16_t error_screen[MEI_W * MEI_H];

    /* Audio */
    MeiAudioChannel ch[AUD_CHANNELS];
    int16_t audio_out[MEI_MAX_AUDIO_FRAMES * 2];
    int audio_frames;
    uint32_t audio_phase;    /* sub-sample accounting for 22050 / 60 */
    MeiReverb rev;
};

/* ---- bus.c ---- memory map, I/O dispatch, fault checks.
 * Each returns 0 on success; on failure sets m->fault (pc = m->pc) and returns -1. */
int bus_read8(Mei *m, uint32_t addr, uint32_t *out, int sign);
int bus_read16(Mei *m, uint32_t addr, uint32_t *out, int sign);
int bus_read32(Mei *m, uint32_t addr, uint32_t *out);
int bus_write8(Mei *m, uint32_t addr, uint32_t val);
int bus_write16(Mei *m, uint32_t addr, uint32_t val);
int bus_write32(Mei *m, uint32_t addr, uint32_t val);
int bus_fetch(Mei *m, uint32_t addr, uint32_t *out);  /* instruction fetch */
void mei_raise(Mei *m, MeiFaultKind kind, uint32_t addr);

/* Direct little-endian helpers on host byte arrays (no checks). */
static inline uint32_t rd32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }
static inline uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static inline void wr32(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24); }
static inline void wr16(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }

/* ---- cpu.c ---- */
void cpu_reset(Mei *m);
void cpu_run(Mei *m);   /* runs until cycles <= 0, vsync, or fault */

/* ---- gpu.c ---- */
void gpu_reset(Mei *m);
void gpu_draw_list(Mei *m, uint32_t addr);   /* GPU_DRAW write; may raise a fault */
void gpu_clear(Mei *m, uint32_t colour);     /* GPU_CLEAR write */
void gpu_vsync(Mei *m);                      /* swap buffers, reset triangle count */
uint32_t gpu_back_addr(const Mei *m);
const uint16_t *gpu_front(Mei *m);
void gpu_render_error_screen(Mei *m);        /* fills m->error_screen from m->fault + registers */

/* ---- card.c ---- */
int card_io_read(Mei *m, uint32_t off, uint32_t *out);    /* off relative to IO_CARD; -1 = unmapped */
int card_io_write(Mei *m, uint32_t off, uint32_t val);    /* -1 unmapped, -2 read-only */
void card_vsync(Mei *m);
void card_set_cart_id(Mei *m);

/* ---- audio.c ---- */
void audio_reset(Mei *m);
int audio_io_read(Mei *m, uint32_t off, uint32_t *out);   /* off relative to IO_BASE; -1 = unmapped */
int audio_io_write(Mei *m, uint32_t off, uint32_t val);   /* -1 unmapped, -2 read-only */
void audio_mix_tick(Mei *m);                 /* fills audio_out / audio_frames for this tick */
/* One ADPCM decode step: header byte, 4-bit nibble, two samples of history (updated). */
int32_t audio_adpcm_sample(uint32_t header, uint32_t nibble, int32_t *h1, int32_t *h2);

#endif
