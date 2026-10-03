/* Memory card controller (docs/MEMCARD.md): two 128 KB cards of 512-byte blocks,
 * per-cart saves with icons, system-only management commands. The card images belong
 * to the platform; the core edits them in place and flags them dirty. */
#include "machine.h"

#include <string.h>

#define BLK          512
#define FAT          16            /* allocation table: one byte per block */
#define STARTS       (FAT + 256)   /* bitmap: block begins a save */
#define F_FREE       0x00
#define F_END        0xFF
#define F_RESERVED   0xFE
#define HDR_ID       4
#define HDR_NUM      20
#define HDR_LEN      24
#define HDR_META     28
#define META_SIZE    452
#define MAX_DATA     32000
#define LIST_ENTRY   64

enum { CMD_STAT = 1, CMD_READ, CMD_WRITE, CMD_DELETE, CMD_FREE, CMD_LIST_MINE,
       CMD_LIST = 16, CMD_META_ANY, CMD_DELETE_ANY, CMD_COPY_ANY, CMD_FORMAT };
enum { E_NONE, E_NO_CARD, E_NOT_FOUND, E_FULL, E_BAD_ADDR, E_NOT_ALLOWED, E_BAD_CMD, E_BUSY };

static int is_start(const uint8_t *c, int b) { return c[STARTS + b / 8] >> (b % 8) & 1; }
static void set_start(uint8_t *c, int b, int on) {
    if (on) c[STARTS + b / 8] |= (uint8_t)(1 << (b % 8));
    else c[STARTS + b / 8] &= (uint8_t)~(1 << (b % 8));
}

static void format(uint8_t *c) {
    memset(c, 0, MEI_CARD_SIZE);
    memcpy(c, "MEICARD1", 8);
    c[FAT] = F_RESERVED;
}

static void ensure_formatted(Mei *m, int slot) {
    uint8_t *c = m->card[slot];
    if (memcmp(c, "MEICARD1", 8) != 0) { format(c); m->card_dirty[slot] = 1; }
}

static int free_blocks(const uint8_t *c) {
    int n = 0;
    for (int b = 1; b < MEI_CARD_BLOCKS; b++) n += c[FAT + b] == F_FREE;
    return n;
}

static int chain_length(const uint8_t *c, int b) {
    int n = 1;
    while (c[FAT + b] != F_END && n < MEI_CARD_BLOCKS) { b = c[FAT + b]; n++; }
    return n;
}

static int find_save(const uint8_t *c, const char *id, uint32_t num) {
    for (int b = 1; b < MEI_CARD_BLOCKS; b++) {
        if (!is_start(c, b)) continue;
        const uint8_t *h = c + b * BLK;
        if (!memcmp(h, "SAVE", 4) && !memcmp(h + HDR_ID, id, 16) && rd32(h + HDR_NUM) == num) return b;
    }
    return -1;
}

static void free_chain(uint8_t *c, int b) {
    set_start(c, b, 0);
    for (int n = 0; n < MEI_CARD_BLOCKS; n++) {
        int next = c[FAT + b];
        c[FAT + b] = F_FREE;
        memset(c + b * BLK, 0, BLK);
        if (next == F_END) break;
        b = next;
    }
}

/* Writes a save (replacing any with the same id and number). Returns an error code. */
static int write_save(uint8_t *c, const char *id, uint32_t num, const uint8_t *data, uint32_t len, const uint8_t *meta) {
    int old = find_save(c, id, num);
    int need = 1 + (int)((len + BLK - 1) / BLK);
    if (free_blocks(c) + (old >= 0 ? chain_length(c, old) : 0) < need) return E_FULL;
    if (old >= 0) free_chain(c, old);
    int blocks[MEI_CARD_BLOCKS], n = 0;
    for (int b = 1; b < MEI_CARD_BLOCKS && n < need; b++) if (c[FAT + b] == F_FREE) blocks[n++] = b;
    for (int i = 0; i < n; i++) c[FAT + blocks[i]] = (uint8_t)(i + 1 < n ? blocks[i + 1] : F_END);
    set_start(c, blocks[0], 1);
    uint8_t *h = c + blocks[0] * BLK;
    memcpy(h, "SAVE", 4);
    memcpy(h + HDR_ID, id, 16);
    wr32(h + HDR_NUM, num);
    wr32(h + HDR_LEN, len);
    memcpy(h + HDR_META, meta, META_SIZE);
    for (int i = 1; i < n; i++) {
        uint32_t off = (uint32_t)(i - 1) * BLK, chunk = len - off < BLK ? len - off : BLK;
        memcpy(c + blocks[i] * BLK, data + off, chunk);
    }
    return E_NONE;
}

static uint32_t read_save(const uint8_t *c, int first, uint8_t *dst, uint32_t max) {
    uint32_t len = rd32(c + first * BLK + HDR_LEN), done = 0;
    if (len > max) len = max;
    int b = first;
    while (done < len && c[FAT + b] != F_END) {
        b = c[FAT + b];
        uint32_t chunk = len - done < BLK ? len - done : BLK;
        memcpy(dst + done, c + b * BLK, chunk);
        done += chunk;
    }
    return done;
}

/* Host pointers for cart-supplied buffers: destinations must lie in RAM, sources may also be in
 * the ROM window. A source running past the cart image reads zeros there, staged in tmp (len bytes). */
static uint8_t *ram_ptr(Mei *m, uint32_t addr, uint32_t len) {
    return addr < RAM_SIZE && len <= RAM_SIZE - addr ? m->ram + addr : NULL;
}

static const uint8_t *src_ptr(Mei *m, uint32_t addr, uint32_t len, uint8_t *tmp) {
    if (addr < RAM_SIZE && len <= RAM_SIZE - addr) return m->ram + addr;
    uint32_t off = addr - ROM_BASE;
    if (off >= ROM_WINDOW || len > ROM_WINDOW - off) return NULL;
    uint32_t n = off < m->rom_len ? m->rom_len - off : 0;
    if (n >= len) return m->rom + off;
    if (n) memcpy(tmp, m->rom + off, n);
    memset(tmp + n, 0, len - n);
    return tmp;
}

static int run(Mei *m, uint32_t cmd, int *blocks_moved) {
    MeiCardRegs *r = &m->card_regs;
    int slot = r->slot & 1;
    uint8_t *c = m->card[slot];
    if (cmd >= CMD_LIST && !m->privileged) return E_NOT_ALLOWED;
    if (!c) return E_NO_CARD;
    ensure_formatted(m, slot);
    const char *id = m->cart_id;
    int b;
    switch (cmd) {
    case CMD_STAT:
        b = find_save(c, id, r->save);
        r->result = b >= 0;
        r->len = b >= 0 ? rd32(c + b * BLK + HDR_LEN) : 0;
        return E_NONE;
    case CMD_READ: {
        if ((b = find_save(c, id, r->save)) < 0) return E_NOT_FOUND;
        uint32_t len = rd32(c + b * BLK + HDR_LEN);
        if (len > r->len) len = r->len;
        uint8_t *dst = ram_ptr(m, r->buf, len), *meta = r->meta ? ram_ptr(m, r->meta, META_SIZE) : NULL;
        if (!dst || (r->meta && !meta)) return E_BAD_ADDR;
        r->len = read_save(c, b, dst, len);
        if (meta) memcpy(meta, c + b * BLK + HDR_META, META_SIZE);
        *blocks_moved = 1 + (int)((r->len + BLK - 1) / BLK);
        return E_NONE;
    }
    case CMD_WRITE: {
        uint8_t tmp[MAX_DATA], tmp_meta[META_SIZE];
        if (r->len > MAX_DATA) return E_BAD_ADDR;
        const uint8_t *src = src_ptr(m, r->buf, r->len, tmp), *meta = src_ptr(m, r->meta, META_SIZE, tmp_meta);
        if (!src || !meta || r->save > 15) return E_BAD_ADDR;
        int e = write_save(c, id, r->save, src, r->len, meta);
        if (e == E_NONE) { m->card_dirty[slot] = 1; *blocks_moved = 3 * (1 + (int)((r->len + BLK - 1) / BLK)); }
        return e;
    }
    case CMD_DELETE:
        if ((b = find_save(c, id, r->save)) < 0) return E_NOT_FOUND;
        free_chain(c, b);
        m->card_dirty[slot] = 1;
        return E_NONE;
    case CMD_FREE:
        r->result = (uint32_t)free_blocks(c);
        return E_NONE;
    case CMD_LIST_MINE:
        r->result = 0;
        for (uint32_t n = 0; n < 16; n++) if (find_save(c, id, n) >= 0) r->result |= 1u << n;
        return E_NONE;
    case CMD_LIST: {
        uint32_t max = r->len / LIST_ENTRY, count = 0;
        uint8_t *dst = ram_ptr(m, r->buf, max * LIST_ENTRY);
        if (!dst) return E_BAD_ADDR;
        for (b = 1; b < MEI_CARD_BLOCKS; b++) {
            if (!is_start(c, b)) continue;
            const uint8_t *h = c + b * BLK;
            if (count < max) {
                uint8_t *e = dst + count * LIST_ENTRY;
                memcpy(e, h + HDR_ID, 16);
                memcpy(e + 16, h + HDR_META, 32);
                wr32(e + 48, rd32(h + HDR_NUM));
                wr32(e + 52, (uint32_t)chain_length(c, b));
                wr32(e + 56, rd32(h + HDR_LEN));
                wr32(e + 60, (uint32_t)b);
            }
            count++;
        }
        r->result = count;
        return E_NONE;
    }
    case CMD_META_ANY: case CMD_DELETE_ANY: case CMD_COPY_ANY: {
        b = (int)r->save;
        if (b < 1 || b >= MEI_CARD_BLOCKS || !is_start(c, b)) return E_NOT_FOUND;
        const uint8_t *h = c + b * BLK;
        if (cmd == CMD_META_ANY) {
            uint8_t *meta = ram_ptr(m, r->meta, META_SIZE);
            if (!meta) return E_BAD_ADDR;
            memcpy(meta, h + HDR_META, META_SIZE);
            return E_NONE;
        }
        if (cmd == CMD_DELETE_ANY) { free_chain(c, b); m->card_dirty[slot] = 1; return E_NONE; }
        uint8_t *other = m->card[slot ^ 1];
        if (!other) return E_NO_CARD;
        ensure_formatted(m, slot ^ 1);
        static uint8_t data[MAX_DATA];
        uint32_t len = read_save(c, b, data, MAX_DATA);
        int e = write_save(other, (const char *)h + HDR_ID, rd32(h + HDR_NUM), data, len, h + HDR_META);
        if (e == E_NONE) { m->card_dirty[slot ^ 1] = 1; *blocks_moved = 4 * (1 + (int)((len + BLK - 1) / BLK)); }
        return e;
    }
    case CMD_FORMAT:
        format(c);
        m->card_dirty[slot] = 1;
        *blocks_moved = 20;
        return E_NONE;
    }
    return E_BAD_CMD;
}

int card_io_read(Mei *m, uint32_t off, uint32_t *out) {
    MeiCardRegs *r = &m->card_regs;
    switch (off) {
    case 0x00: *out = 0; return 0;
    case 0x04: *out = (m->card_busy > 0) | r->error << 8 | (m->card[0] != NULL) << 16 | (m->card[1] != NULL) << 17; return 0;
    case 0x08: *out = r->slot; return 0;
    case 0x0C: *out = r->save; return 0;
    case 0x10: *out = r->buf; return 0;
    case 0x14: *out = r->len; return 0;
    case 0x18: *out = r->meta; return 0;
    case 0x1C: *out = r->result; return 0;
    }
    return -1;
}

int card_io_write(Mei *m, uint32_t off, uint32_t val) {
    MeiCardRegs *r = &m->card_regs;
    switch (off) {
    case 0x00: {
        if (m->card_busy > 0) { r->error = E_BUSY; return 0; }
        int moved = 0;
        r->error = (uint32_t)run(m, val, &moved);
        m->card_busy = 2 + moved;
        return 0;
    }
    case 0x08: r->slot = val & 1; return 0;
    case 0x0C: r->save = val; return 0;
    case 0x10: r->buf = val; return 0;
    case 0x14: r->len = val; return 0;
    case 0x18: r->meta = val; return 0;
    case 0x04: case 0x1C: return -2;
    }
    return -1;
}

void card_vsync(Mei *m) { if (m->card_busy > 0) m->card_busy--; }

/* The cart ID from header bytes 40-55, else "T:" + FNV-1a of the title. */
void card_set_cart_id(Mei *m) {
    memset(m->cart_id, 0, sizeof m->cart_id);
    if (m->rom_len >= 56 && !memcmp(m->rom + 4, "MEI1", 4) && m->rom[40]) {
        memcpy(m->cart_id, m->rom + 40, 16);
        return;
    }
    uint32_t h = 2166136261u;
    for (const char *p = m->title; *p; p++) h = (h ^ (uint8_t)*p) * 16777619u;
    static const char hex[] = "0123456789ABCDEF";
    m->cart_id[0] = 'T';
    m->cart_id[1] = ':';
    for (int i = 0; i < 8; i++) m->cart_id[2 + i] = hex[h >> (28 - 4 * i) & 15];
}
