/* Mei console core: public API used by platform layers and tools.
 * The core is plain C with no platform calls. */
#ifndef MEI_CORE_H
#define MEI_CORE_H

#include <stddef.h>
#include <stdint.h>

#define MEI_W 320
#define MEI_H 240
#define MEI_AUDIO_RATE 22050
#define MEI_FPS 60
#define MEI_CYCLES_PER_FRAME 500000
#define MEI_MAX_AUDIO_FRAMES 368   /* per 60 Hz tick: alternates 367 / 368 */

/* Pad button bits (PAD1 / PAD2). */
enum {
    MEI_BTN_UP = 1 << 0, MEI_BTN_DOWN = 1 << 1, MEI_BTN_LEFT = 1 << 2, MEI_BTN_RIGHT = 1 << 3,
    MEI_BTN_A = 1 << 4, MEI_BTN_B = 1 << 5, MEI_BTN_X = 1 << 6, MEI_BTN_Y = 1 << 7,
    MEI_BTN_L = 1 << 8, MEI_BTN_R = 1 << 9, MEI_BTN_START = 1 << 10,
    MEI_BTN_SELECT = 1 << 11,   /* an addition to the spec, see DECISIONS.md */
};

typedef enum {
    MEI_FAULT_NONE = 0,
    MEI_FAULT_BREAK,
    MEI_FAULT_ILLEGAL,
    MEI_FAULT_MISALIGNED,
    MEI_FAULT_UNMAPPED,
    MEI_FAULT_READ_ONLY,
    MEI_FAULT_IO_WIDTH,
    MEI_FAULT_BAD_PACKET_LIST,   /* GPU list too long (> 65,536 packets) */
    MEI_FAULT_NO_CART,
} MeiFaultKind;

typedef struct {
    MeiFaultKind kind;
    uint32_t pc;       /* address of the faulting instruction */
    uint32_t addr;     /* offending data address, where relevant */
} MeiFault;

/* Controller state as the platform reports it. Sticks are raw floats
 * (-1..1, y up = +1); the core applies the dead zone and converts to 16.16. */
typedef struct {
    uint32_t buttons;
    float stick_x, stick_y;
} MeiPadInput;

typedef struct Mei Mei;

typedef void (*MeiDebugFn)(void *user, char c);

Mei *mei_create(void);
void mei_destroy(Mei *m);

/* Loads a ROM image (at most 2 MB) and resets. Returns 0 on success. */
int mei_load_cart(Mei *m, const uint8_t *data, size_t len);
void mei_reset(Mei *m);

/* Cart title from the optional header, or "" if none. */
const char *mei_cart_title(const Mei *m);

/* Latest input from the platform; latched into PAD/STICK registers at vsync. */
void mei_set_pad(Mei *m, int index, const MeiPadInput *in);

/* Runs one 60 Hz tick: up to 500,000 cycles or until vsync, then produces
 * that tick's audio. Returns 1 if a new picture was presented (vsync),
 * 0 if the frame overran and the previous picture repeats. */
int mei_run_frame(Mei *m);

/* The front buffer: 320x240 pixels, 15-bit colour (R bits 0-4, G 5-9, B 10-14).
 * When the cart has faulted this is the error screen. */
const uint16_t *mei_display(Mei *m);

/* Interleaved stereo s16 samples produced by the last mei_run_frame.
 * Returns the number of stereo frames (367 or 368). */
int mei_audio(Mei *m, const int16_t **samples);

const MeiFault *mei_fault(const Mei *m);
const char *mei_fault_name(MeiFaultKind k);

void mei_set_debug_output(Mei *m, MeiDebugFn fn, void *user);

/* System ROM extensions (see docs/SYSTEM.md). SYS_LAUNCH requests a cart:
 * returns 1 and the requested catalogue index once per request. SYS_CONFIG is one
 * settings word that survives resets; *dirty reports (and clears) a cart write. */
int mei_launch_request(Mei *m, uint32_t *index);
uint32_t mei_config(Mei *m, int *dirty);
void mei_set_config(Mei *m, uint32_t value);

/* Local wall-clock time from the platform (weekday 0 = Sunday). Like input it is
 * latched at vsync, so SYS_TIME/SYS_DATE change once per frame and replays stay
 * deterministic if the platform records it. Until set, the clock reads midnight, day 0. */
void mei_set_clock(Mei *m, int year, int month, int day, int weekday, int hour, int minute, int second);

/* Memory cards (docs/MEMCARD.md). The platform owns each card image (MEI_CARD_SIZE
 * bytes, or NULL for an empty slot) and saves it when mei_card_dirty reports a change. */
#define MEI_CARD_SIZE   131072
#define MEI_CARD_BLOCKS 256
void mei_card_insert(Mei *m, int slot, uint8_t *image);
int mei_card_dirty(Mei *m, int slot);           /* 1 once after the card changed */
/* Grants the running program the system ROM's card commands; cleared by mei_load_cart. */
void mei_set_privileged(Mei *m, int on);

#endif
