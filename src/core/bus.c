/* Bus: memory map, I/O register dispatch and fault checks. */
#include "machine.h"

#include <string.h>

#define RNG_RESET_SEED 0x4D454921u

void mei_raise(Mei *m, MeiFaultKind kind, uint32_t addr) {
    if (m->fault.kind) return;
    m->fault.kind = kind;
    m->fault.pc = m->pc;
    m->fault.addr = addr;
}

static int fail(Mei *m, MeiFaultKind kind, uint32_t addr) {
    mei_raise(m, kind, addr);
    return -1;
}

/* Host pointer for a plain-memory access of `size` bytes, or NULL if the
 * address is not RAM/ROM/VRAM. Callers have already checked alignment, so an
 * access never straddles a region end, nor the end of the word-padded cart image. */
static uint8_t *mem_ptr(Mei *m, uint32_t addr, int *rom) {
    static uint8_t past_image[4];   /* the ROM window past the cart reads 0; ROM writes fault before using it */
    *rom = 0;
    if (addr < RAM_BASE + RAM_SIZE) return m->ram + addr;
    if (addr - ROM_BASE < ROM_WINDOW) {
        *rom = 1;
        return addr - ROM_BASE < m->rom_len ? m->rom + (addr - ROM_BASE) : past_image;
    }
    if (addr - VRAM_BASE < VRAM_SIZE) return m->vram + (addr - VRAM_BASE);
    return NULL;
}

static int is_io(uint32_t addr) { return addr - IO_BASE < IO_SIZE; }

/* Audio: channels 0-7 at 0x100 and 8-15 at 0x400, 32 bytes each (+1C in each is
 * reserved), and the global audio registers at 0x500-0x50F. */
static int is_audio(uint32_t off) {
    if (off - IO_AUDIO < 8 * 0x20 || off - IO_AUDIO_HI < 8 * 0x20) return (off & 0x1F) != 0x1C;
    return off - IO_AUD_GLOBAL < 0x10;
}

static uint32_t rng_next(Mei *m) {
    uint32_t x = m->rng;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return m->rng = x;
}

/* Returns 0 or the fault kind. */
static MeiFaultKind io_read(Mei *m, uint32_t off, uint32_t *out) {
    *out = 0;
    switch (off) {
    case IO_GPU_DRAW: case IO_GPU_CLEAR: case IO_GPU_ZCLEAR: case IO_SYS_DEBUG: case IO_SYS_LAUNCH: return 0;   /* write-only */
    case IO_GPU_DEPTH:  *out = m->gpu_depth; return 0;
    case IO_SYS_CONFIG: *out = m->sys_config; return 0;
    case IO_SYS_TIME:   *out = m->clock[0]; return 0;
    case IO_SYS_DATE:   *out = m->clock[1]; return 0;
    case IO_GPU_CTRL:   *out = m->gpu_ctrl; return 0;
    case IO_GPU_STATUS: *out = m->gpu_status; return 0;
    case IO_GPU_BACK:   *out = gpu_back_addr(m); return 0;
    case IO_GPU_LOAD:   *out = m->gstat_last.gpu_cycles; return 0;
    case IO_GPU_TICKS:  *out = m->gstat_last.ticks; return 0;
    case IO_GPU_LAG:    *out = m->gpu_lag; return 0;
    case IO_PAD1:       *out = m->pad_buttons[0]; return 0;
    case IO_PAD2:       *out = m->pad_buttons[1]; return 0;
    case IO_STICK1_X:   *out = (uint32_t)m->pad_stick[0][0]; return 0;
    case IO_STICK1_Y:   *out = (uint32_t)m->pad_stick[0][1]; return 0;
    case IO_STICK2_X:   *out = (uint32_t)m->pad_stick[1][0]; return 0;
    case IO_STICK2_Y:   *out = (uint32_t)m->pad_stick[1][1]; return 0;
    case IO_SYS_FRAME:  *out = m->frame; return 0;
    case IO_SYS_CYCLES: *out = (uint32_t)m->cycles; return 0;
    case IO_SYS_RAND:   *out = rng_next(m); return 0;
    }
    if (is_audio(off) && audio_io_read(m, off, out) == 0) return 0;
    if (off - IO_CARD < 0x20 && card_io_read(m, off - IO_CARD, out) == 0) return 0;
    if (off - IO_BC < IO_BC_SIZE && broadcast_io_read(m, off - IO_BC, out) == 0) return 0;
    if (off - IO_PLANES < 0x100 && planes_io_read(m, off - IO_PLANES, out) == 0) return 0;
    return MEI_FAULT_UNMAPPED;
}

static MeiFaultKind io_write(Mei *m, uint32_t off, uint32_t val) {
    switch (off) {
    case IO_GPU_DRAW:  gpu_draw_list(m, val); return 0;   /* raises its own faults */
    case IO_GPU_CLEAR: gpu_clear(m, val); return 0;
    case IO_GPU_CTRL:  m->gpu_ctrl = val; return 0;
    case IO_GPU_DEPTH: m->gpu_depth = val & 1; return 0;   /* bits 1-31 reserved: read as 0 */
    case IO_GPU_ZCLEAR: gpu_zclear(m, val); return 0;
    case IO_SYS_RAND:  m->rng = val ? val : RNG_RESET_SEED; return 0;
    case IO_SYS_DEBUG: {
        char ch = (char)(val & 0xFF);
        if (m->debug_fn) m->debug_fn(m->debug_user, ch);
        if (ch == '\n') {
            memmove(m->debug_tail[0], m->debug_tail[1], sizeof m->debug_tail - sizeof m->debug_tail[0]);
            m->debug_tail[3][0] = 0;
            m->debug_col = 0;
        } else if (m->debug_col < 80 && (unsigned char)ch >= 32) {
            m->debug_tail[3][m->debug_col++] = ch;
            m->debug_tail[3][m->debug_col] = 0;
        }
        return 0;
    }
    case IO_SYS_LAUNCH: m->launch_index = val; m->launch_pending = 1; return 0;
    case IO_SYS_CONFIG: m->config_dirty |= m->sys_config != val; m->sys_config = val; return 0;
    case IO_GPU_STATUS: case IO_GPU_BACK: case IO_GPU_LOAD: case IO_GPU_TICKS: case IO_GPU_LAG:
    case IO_PAD1: case IO_PAD2:
    case IO_STICK1_X: case IO_STICK1_Y: case IO_STICK2_X: case IO_STICK2_Y:
    case IO_SYS_FRAME: case IO_SYS_CYCLES: case IO_SYS_TIME: case IO_SYS_DATE:
        return MEI_FAULT_READ_ONLY;
    }
    if (is_audio(off)) {
        int r = audio_io_write(m, off, val);
        if (r == 0) return 0;
        if (r == -2) return MEI_FAULT_READ_ONLY;
    }
    if (off - IO_CARD < 0x20) {
        int r = card_io_write(m, off - IO_CARD, val);
        if (r == 0) return 0;
        if (r == -2) return MEI_FAULT_READ_ONLY;
    }
    if (off - IO_BC < IO_BC_SIZE) {
        int r = broadcast_io_write(m, off - IO_BC, val);
        if (r == 0) return 0;
        if (r == -2) return MEI_FAULT_READ_ONLY;
    }
    if (off - IO_PLANES < 0x100 && planes_io_write(m, off - IO_PLANES, val) == 0) return 0;
    return MEI_FAULT_UNMAPPED;
}

/* Shared read path for 1, 2 and 4 byte accesses. */
static int read_n(Mei *m, uint32_t addr, int size, uint32_t *out) {
    if (addr & (uint32_t)(size - 1)) return fail(m, MEI_FAULT_MISALIGNED, addr);
    int rom;
    uint8_t *p = mem_ptr(m, addr, &rom);
    if (p) {
        *out = size == 1 ? p[0] : size == 2 ? rd16(p) : rd32(p);
        return 0;
    }
    if (is_io(addr)) {
        if (size != 4) return fail(m, MEI_FAULT_IO_WIDTH, addr);
        MeiFaultKind k = io_read(m, addr - IO_BASE, out);
        return k ? fail(m, k, addr) : 0;
    }
    return fail(m, MEI_FAULT_UNMAPPED, addr);
}

static int write_n(Mei *m, uint32_t addr, int size, uint32_t val) {
    if (addr & (uint32_t)(size - 1)) return fail(m, MEI_FAULT_MISALIGNED, addr);
    int rom;
    uint8_t *p = mem_ptr(m, addr, &rom);
    if (p) {
        if (rom) return fail(m, MEI_FAULT_READ_ONLY, addr);
        if (size == 1) p[0] = (uint8_t)val;
        else if (size == 2) wr16(p, val);
        else wr32(p, val);
        return 0;
    }
    if (is_io(addr)) {
        if (size != 4) return fail(m, MEI_FAULT_IO_WIDTH, addr);
        MeiFaultKind k = io_write(m, addr - IO_BASE, val);
        if (k) return fail(m, k, addr);
        return m->fault.kind ? -1 : 0;   /* GPU_DRAW may have faulted */
    }
    return fail(m, MEI_FAULT_UNMAPPED, addr);
}

int bus_read8(Mei *m, uint32_t addr, uint32_t *out, int sign) {
    if (read_n(m, addr, 1, out)) return -1;
    if (sign) *out = (uint32_t)(int32_t)(int8_t)*out;
    return 0;
}

int bus_read16(Mei *m, uint32_t addr, uint32_t *out, int sign) {
    if (read_n(m, addr, 2, out)) return -1;
    if (sign) *out = (uint32_t)(int32_t)(int16_t)*out;
    return 0;
}

int bus_read32(Mei *m, uint32_t addr, uint32_t *out) { return read_n(m, addr, 4, out); }
int bus_write8(Mei *m, uint32_t addr, uint32_t val) { return write_n(m, addr, 1, val); }
int bus_write16(Mei *m, uint32_t addr, uint32_t val) { return write_n(m, addr, 2, val); }
int bus_write32(Mei *m, uint32_t addr, uint32_t val) { return write_n(m, addr, 4, val); }

int bus_fetch(Mei *m, uint32_t addr, uint32_t *out) {
    if (addr & 3) return fail(m, MEI_FAULT_MISALIGNED, addr);
    int rom;
    uint8_t *p = mem_ptr(m, addr, &rom);
    if (!p) return fail(m, MEI_FAULT_UNMAPPED, addr);
    *out = rd32(p);
    return 0;
}
