/* Broadcast decoder (docs/BROADCAST.md): finds 64-byte packets in the 9,600-baud stream,
 * corrects the Hamming 8/4 header, checks the CRC, and assembles up to eight selected pages
 * in its own page memory. Driven by the frame loop: up to 16 bytes per tick. */
#include "machine.h"

#include <string.h>

enum { CMD_READ_PAGE = 1, CMD_READ_ROW, CMD_READ_FIFO, CMD_CLEAR_COUNTERS };
enum { E_NONE, E_BAD_CMD, E_BAD_ADDR, E_SLOT_FREE, E_NO_ROW };

#define SYNC0 0x55
#define SYNC1 0xA7
#define PAGE_FREE 0xFFFFFFFFu
#define FILL_PAGE 0xFFF
#define MAX_MISSES 4

/* byte -> nibble (bits 0-3), or 0x10 | nibble when one bit was corrected, or 0xFF */
static uint8_t ham_decode[256];
static int ham_ready;

static uint8_t ham_encode(unsigned d) {
    unsigned d1 = d & 1, d2 = d >> 1 & 1, d3 = d >> 2 & 1, d4 = d >> 3 & 1;
    unsigned p1 = 1 ^ d1 ^ d3 ^ d4, p2 = 1 ^ d1 ^ d2 ^ d4, p3 = 1 ^ d1 ^ d2 ^ d3;
    unsigned p4 = 1 ^ p1 ^ d1 ^ p2 ^ d2 ^ p3 ^ d3 ^ d4;
    return (uint8_t)(p1 | d1 << 1 | p2 << 2 | d2 << 3 | p3 << 4 | d3 << 5 | p4 << 6 | d4 << 7);
}

static int popcount8(unsigned v) { int n = 0; for (; v; v &= v - 1) n++; return n; }

static void ham_init(void) {
    if (ham_ready) return;
    for (int b = 0; b < 256; b++) {
        ham_decode[b] = 0xFF;
        for (unsigned n = 0; n < 16; n++) {
            int dist = popcount8((unsigned)b ^ ham_encode(n));
            if (dist == 0) ham_decode[b] = (uint8_t)n;
            else if (dist == 1) ham_decode[b] = (uint8_t)(0x10 | n);
        }
    }
    ham_ready = 1;
}

int bc_hamming84(uint8_t byte) {
    ham_init();
    uint8_t v = ham_decode[byte];
    return v == 0xFF ? -1 : v;
}

uint16_t bc_crc16(const uint8_t *p, int n, uint16_t crc) {
    for (int i = 0; i < n; i++) {
        crc ^= (uint16_t)(p[i] << 8);
        for (int k = 0; k < 8; k++) crc = crc & 0x8000 ? (uint16_t)((crc << 1) ^ 0x1021) : (uint16_t)(crc << 1);
    }
    return crc;
}

static uint64_t rows_mask(int count) { return count >= 64 ? ~0ull : (1ull << count) - 1; }

static void slot_clear(MeiBcSlot *s, uint32_t page) {
    memset(s, 0, sizeof *s);
    s->page = page;
}

void broadcast_reset(Mei *m) {
    MeiBroadcast *b = &m->bc;
    ham_init();
    b->ctrl = 0;
    b->sel = b->buf = b->len = b->row = b->result = 0;
    b->n_ok = b->n_fixed = b->n_dropped = 0;
    b->locked = 0;
    b->misses = 0;
    b->pk_n = 0;
    b->fifo_head = b->fifo_n = 0;
    b->fifo_over = 0;
    for (int i = 0; i < MEI_BC_SLOTS; i++) slot_clear(&b->slot[i], PAGE_FREE);
    /* the carrier, the bytes queued for this tick and the noise generator belong to the signal */
}

/* Decodes the packet in pk[0..63]. Returns 1 if accepted (header and CRC good). */
static int try_packet(Mei *m) {
    MeiBroadcast *b = &m->bc;
    uint32_t h = 0;
    int corrected = 0;
    for (int i = 0; i < 8; i++) {
        uint8_t v = ham_decode[b->pk[2 + i]];
        if (v == 0xFF) return 0;
        corrected |= v >> 4;
        h |= (uint32_t)(v & 15) << (4 * i);
    }
    uint8_t hb[4] = {(uint8_t)h, (uint8_t)(h >> 8), (uint8_t)(h >> 16), (uint8_t)(h >> 24)};
    uint16_t crc = bc_crc16(b->pk + 10, MEI_BC_ROW_BYTES, bc_crc16(hb, 4, 0xFFFF));
    if (crc != (uint16_t)(b->pk[62] | b->pk[63] << 8)) return 0;

    b->n_ok++;
    if (corrected) b->n_fixed++;
    uint32_t page = h & 0xFFFF;
    if ((page & 0xFFF) == FILL_PAGE) return 1;
    int row = (int)(h >> 16 & 63), last = (int)(h >> 23 & 1);
    uint8_t version = (uint8_t)(h >> 24);
    for (int i = 0; i < MEI_BC_SLOTS; i++) {
        MeiBcSlot *s = &b->slot[i];
        if (s->page != page) continue;
        if (!s->seen || s->version != version) {
            slot_clear(s, page);
            s->version = version;
            s->seen = 1;
        }
        memcpy(s->data + row * MEI_BC_ROW_BYTES, b->pk + 10, MEI_BC_ROW_BYTES);
        s->rows |= 1ull << row;
        s->stamp = b->pk_tick[0];
        if (last) s->count = (uint8_t)(row + 1);
        if (!s->complete && s->count && (s->rows & rows_mask(s->count)) == rows_mask(s->count)) {
            s->complete = 1;
            s->changed = 1;
        }
    }
    return 1;
}

static void shift(MeiBroadcast *b, int n) {
    if (n >= b->pk_n) { b->pk_n = 0; return; }
    memmove(b->pk, b->pk + n, (size_t)(b->pk_n - n));
    memmove(b->pk_tick, b->pk_tick + n, (size_t)(b->pk_n - n) * sizeof b->pk_tick[0]);
    b->pk_n -= n;
}

/* Runs the packet state machine over the buffered bytes. */
static void scan(Mei *m) {
    MeiBroadcast *b = &m->bc;
    for (;;) {
        if (!b->locked) {
            int i = 0;   /* drop bytes until the buffer starts with a possible sync word */
            while (i < b->pk_n && !(b->pk[i] == SYNC0 && (i + 1 == b->pk_n || b->pk[i + 1] == SYNC1))) i++;
            shift(b, i);
            if (b->pk_n < MEI_BC_PACKET) return;
            if (try_packet(m)) { b->locked = 1; b->misses = 0; b->pk_n = 0; }
            else shift(b, 1);
        } else {
            if (b->pk_n < MEI_BC_PACKET) return;
            int sync_err = popcount8(b->pk[0] ^ SYNC0) + popcount8(b->pk[1] ^ SYNC1);
            if (sync_err <= 2 && try_packet(m)) { b->misses = 0; b->pk_n = 0; continue; }
            b->n_dropped++;
            if (sync_err > 2 || ++b->misses >= MAX_MISSES) { b->locked = 0; shift(b, 1); }
            else b->pk_n = 0;
        }
    }
}

static uint32_t noise_next(MeiBroadcast *b) {
    uint32_t x = b->noise_rng;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    return b->noise_rng = x;
}

/* End of a tick: take the bytes the line delivered during it. */
void broadcast_tick(Mei *m) {
    MeiBroadcast *b = &m->bc;
    int n = b->in_n;
    b->in_n = 0;
    for (int i = 0; i < n; i++) {
        uint8_t byte = b->in[i];
        if (b->noise_ppm) {
            for (int bit = 0; bit < 8; bit++)
                if (noise_next(b) % 1000000u < b->noise_ppm) byte ^= (uint8_t)(1 << bit);
        }
        if (!(b->ctrl & 1) || !b->carrier) continue;
        if (b->ctrl & 2) {
            if (b->fifo_n < MEI_BC_FIFO) {
                b->fifo[(b->fifo_head + b->fifo_n) % MEI_BC_FIFO] = byte;
                b->fifo_n++;
            } else b->fifo_over = 1;
        }
        b->pk[b->pk_n] = byte;
        b->pk_tick[b->pk_n] = m->frame;
        b->pk_n++;
        scan(m);
    }
}

static void lose_lock(MeiBroadcast *b) { b->locked = 0; b->misses = 0; b->pk_n = 0; }

void mei_broadcast_carrier(Mei *m, int on) {
    m->bc.carrier = on != 0;
    if (!on) lose_lock(&m->bc);
}

int mei_broadcast_feed(Mei *m, const uint8_t *data, int len) {
    MeiBroadcast *b = &m->bc;
    int n = 0;
    while (n < len && b->in_n < MEI_BC_BYTES_PER_TICK) b->in[b->in_n++] = data[n++];
    return n;
}

void mei_broadcast_noise(Mei *m, uint32_t errors_per_million_bits, uint32_t seed) {
    m->bc.noise_ppm = errors_per_million_bits;
    m->bc.noise_rng = seed ? seed : 0x4D454E4Fu;
}

static uint8_t *ram_dst(Mei *m, uint32_t addr, uint32_t len) {
    return addr < RAM_SIZE && len <= RAM_SIZE - addr ? m->ram + addr : NULL;
}

static uint32_t run(Mei *m, uint32_t cmd) {
    MeiBroadcast *b = &m->bc;
    MeiBcSlot *s = &b->slot[b->sel & 7];
    switch (cmd) {
    case CMD_READ_PAGE: {
        if (s->page == PAGE_FREE) return E_SLOT_FREE;
        uint32_t n = (uint32_t)(s->count ? s->count : MEI_BC_MAX_ROWS) * MEI_BC_ROW_BYTES;
        if (n > b->len) n = b->len;
        uint8_t *dst = ram_dst(m, b->buf, n);
        if (!dst) return E_BAD_ADDR;
        memcpy(dst, s->data, n);
        b->len = n;
        s->changed = 0;
        return E_NONE;
    }
    case CMD_READ_ROW: {
        if (s->page == PAGE_FREE) return E_SLOT_FREE;
        if (b->row >= MEI_BC_MAX_ROWS || !(s->rows >> b->row & 1)) { b->len = 0; return E_NO_ROW; }
        uint32_t n = b->len < MEI_BC_ROW_BYTES ? b->len : MEI_BC_ROW_BYTES;
        uint8_t *dst = ram_dst(m, b->buf, n);
        if (!dst) return E_BAD_ADDR;
        memcpy(dst, s->data + b->row * MEI_BC_ROW_BYTES, n);
        b->len = n;
        return E_NONE;
    }
    case CMD_READ_FIFO: {
        uint32_t n = b->len < (uint32_t)b->fifo_n ? b->len : (uint32_t)b->fifo_n;
        uint8_t *dst = ram_dst(m, b->buf, n);
        if (!dst) return E_BAD_ADDR;
        for (uint32_t i = 0; i < n; i++) dst[i] = b->fifo[(b->fifo_head + (int)i) % MEI_BC_FIFO];
        b->fifo_head = (b->fifo_head + (int)n) % MEI_BC_FIFO;
        b->fifo_n -= (int)n;
        b->fifo_over = 0;
        b->len = n;
        return E_NONE;
    }
    case CMD_CLEAR_COUNTERS:
        b->n_ok = b->n_fixed = b->n_dropped = 0;
        return E_NONE;
    }
    return E_BAD_CMD;
}

static uint32_t pstat(const MeiBcSlot *s) {
    int received = 0;
    for (uint64_t r = s->rows; r; r &= r - 1) received++;
    return (uint32_t)s->complete | (uint32_t)s->changed << 1 | (uint32_t)s->seen << 2 |
           (uint32_t)s->version << 8 | (uint32_t)received << 16 | (uint32_t)s->count << 24;
}

int broadcast_io_read(Mei *m, uint32_t off, uint32_t *out) {
    MeiBroadcast *b = &m->bc;
    MeiBcSlot *s = &b->slot[b->sel & 7];
    switch (off) {
    case 0x00: *out = b->ctrl; return 0;
    case 0x04: {
        uint32_t v = (uint32_t)b->carrier | (uint32_t)b->locked << 1 | (uint32_t)b->fifo_over << 2;
        for (int i = 0; i < MEI_BC_SLOTS; i++) {
            v |= (uint32_t)b->slot[i].complete << (8 + i);
            v |= (uint32_t)b->slot[i].changed << (16 + i);
        }
        *out = v;
        return 0;
    }
    case 0x08: *out = 0; return 0;                      /* BC_CMD: write-only */
    case 0x0C: *out = b->result; return 0;
    case 0x10: *out = b->sel; return 0;
    case 0x14: *out = s->page; return 0;
    case 0x18: *out = pstat(s); return 0;
    case 0x1C: *out = (uint32_t)s->rows; return 0;
    case 0x20: *out = (uint32_t)(s->rows >> 32); return 0;
    case 0x24: *out = s->stamp; return 0;
    case 0x28: *out = b->buf; return 0;
    case 0x2C: *out = b->len; return 0;
    case 0x30: *out = b->row; return 0;
    case 0x34: *out = b->n_ok; return 0;
    case 0x38: *out = b->n_fixed; return 0;
    case 0x3C: *out = b->n_dropped; return 0;
    case 0x40:
        if (!b->fifo_n) { *out = 0; return 0; }
        *out = 0x100u | b->fifo[b->fifo_head];
        b->fifo_head = (b->fifo_head + 1) % MEI_BC_FIFO;
        b->fifo_n--;
        return 0;
    case 0x44: *out = (uint32_t)b->fifo_n; return 0;
    }
    return -1;
}

int broadcast_io_write(Mei *m, uint32_t off, uint32_t val) {
    MeiBroadcast *b = &m->bc;
    switch (off) {
    case 0x00: {
        uint32_t old = b->ctrl;
        b->ctrl = val & 3;
        if (!(b->ctrl & 1)) lose_lock(b);
        if ((b->ctrl & 2) && !(old & 2)) { b->fifo_head = b->fifo_n = 0; b->fifo_over = 0; }
        return 0;
    }
    case 0x08: b->result = run(m, val); return 0;
    case 0x10: b->sel = val & 7; return 0;
    case 0x14: slot_clear(&b->slot[b->sel & 7], val & 0x80000000u ? PAGE_FREE : val & 0xFFFF); return 0;
    case 0x28: b->buf = val; return 0;
    case 0x2C: b->len = val; return 0;
    case 0x30: b->row = val; return 0;
    case 0x04: case 0x0C: case 0x18: case 0x1C: case 0x20: case 0x24:
    case 0x34: case 0x38: case 0x3C: case 0x40: case 0x44:
        return -2;
    }
    return -1;
}
