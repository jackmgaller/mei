/* Memory card controller tests (docs/MEMCARD.md). */
#include "machine.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int checks, failures;
#define CHECK(c) do { checks++; if (!(c)) { failures++; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

#define CARD 0xFF0380u
enum { CMD = 0x00, STATUS = 0x04, SLOT = 0x08, SAVE = 0x0C, BUF = 0x10, LEN = 0x14, META = 0x18, RESULT = 0x1C };

static uint32_t rd(Mei *m, uint32_t off) { uint32_t v = 0; bus_read32(m, CARD + off, &v); return v; }
static void wr(Mei *m, uint32_t off, uint32_t v) { bus_write32(m, CARD + off, v); }
static int err(Mei *m) { return (int)(rd(m, STATUS) >> 8 & 0xFF); }

/* Loads a tiny cart with the given title and cart ID (NULL: no ID). */
static void load(Mei *m, const char *title, const char *id) {
    uint8_t rom[64] = {0};
    memcpy(rom + 4, "MEI1", 4);
    strncpy((char *)rom + 8, title, 32);
    if (id) strncpy((char *)rom + 40, id, 16);
    mei_load_cart(m, rom, sizeof rom);
}

static void wait_idle(Mei *m) {
    /* the controller counts down at vsync; simulate the frames directly */
    for (int i = 0; i < 1000 && (rd(m, STATUS) & 1); i++) card_vsync(m);
}

/* Issues a command and waits; returns the error code. */
static int cmd(Mei *m, uint32_t c) { wr(m, CMD, c); int e = err(m); wait_idle(m); return e; }

static void put_meta(Mei *m, uint32_t addr, const char *title) {
    memset(m->ram + addr, 0, 452);
    strncpy((char *)m->ram + addr, title, 32);
    wr32(m->ram + addr + 32, 2);
    for (int i = 0; i < 384; i++) m->ram[addr + 68 + i] = (uint8_t)i;
}

int main(void) {
    Mei *m = mei_create();
    uint8_t *card1 = calloc(1, MEI_CARD_SIZE), *card2 = calloc(1, MEI_CARD_SIZE);

    /* no card inserted */
    load(m, "Game A", "GAME-A");
    CHECK((rd(m, STATUS) >> 16 & 3) == 0);
    CHECK(cmd(m, 5) == 1);

    mei_card_insert(m, 0, card1);
    mei_card_insert(m, 1, card2);
    CHECK((rd(m, STATUS) >> 16 & 3) == 3);

    /* a blank card is formatted on first use: 255 free blocks */
    CHECK(cmd(m, 5) == 0);
    CHECK(rd(m, RESULT) == 255);
    CHECK(!memcmp(card1, "MEICARD1", 8));
    CHECK(mei_card_dirty(m, 0) == 1);
    CHECK(mei_card_dirty(m, 0) == 0);

    /* write a 1,300-byte save: 1 header + 3 data blocks */
    for (int i = 0; i < 1300; i++) m->ram[0x1000 + i] = (uint8_t)(i * 7);
    put_meta(m, 0x3000, "GAME A - SLOT 1");
    wr(m, SAVE, 1); wr(m, BUF, 0x1000); wr(m, LEN, 1300); wr(m, META, 0x3000);
    wr(m, CMD, 3);
    CHECK(err(m) == 0);
    CHECK(rd(m, STATUS) & 1);                      /* busy: 2 + 3 frames per block */
    CHECK(m->card_busy == 2 + 3 * 4);
    wr(m, CMD, 5);
    CHECK(err(m) == 7);                            /* busy */
    wait_idle(m);
    CHECK(mei_card_dirty(m, 0) == 1);
    CHECK(cmd(m, 5) == 0 && rd(m, RESULT) == 251);

    /* stat and read back */
    CHECK(cmd(m, 1) == 0 && rd(m, RESULT) == 1 && rd(m, LEN) == 1300);
    memset(m->ram + 0x5000, 0, 2000);
    memset(m->ram + 0x7000, 0, 452);
    wr(m, BUF, 0x5000); wr(m, LEN, 2000); wr(m, META, 0x7000);
    CHECK(cmd(m, 2) == 0);
    CHECK(rd(m, LEN) == 1300);
    CHECK(!memcmp(m->ram + 0x5000, m->ram + 0x1000, 1300));
    CHECK(!memcmp(m->ram + 0x7000, m->ram + 0x3000, 452));
    /* a shorter read truncates */
    wr(m, LEN, 10); wr(m, META, 0);
    CHECK(cmd(m, 2) == 0 && rd(m, LEN) == 10);

    /* save 0 too; LIST_MINE */
    wr(m, SAVE, 0); wr(m, BUF, 0x1000); wr(m, LEN, 100); wr(m, META, 0x3000);
    CHECK(cmd(m, 3) == 0);
    CHECK(cmd(m, 6) == 0 && rd(m, RESULT) == 3);

    /* replacing keeps the block count right */
    wr(m, SAVE, 1); wr(m, LEN, 500);
    CHECK(cmd(m, 3) == 0);
    CHECK(cmd(m, 5) == 0 && rd(m, RESULT) == 255 - 2 - 2);

    /* metadata and data may come from ROM */
    wr(m, SAVE, 2); wr(m, BUF, ROM_BASE); wr(m, LEN, 64); wr(m, META, ROM_BASE);
    CHECK(cmd(m, 3) == 0);
    /* bad addresses */
    wr(m, BUF, 0x1FFFFF); wr(m, LEN, 100);
    CHECK(cmd(m, 3) == 4);
    wr(m, BUF, 0x1000); wr(m, LEN, 32001);
    CHECK(cmd(m, 3) == 4);
    wr(m, LEN, 10); wr(m, SAVE, 16);
    CHECK(cmd(m, 3) == 4);
    wr(m, SAVE, 2); wr(m, BUF, ROM_BASE); wr(m, LEN, 10);   /* reading into ROM */
    CHECK(cmd(m, 2) == 4);

    /* another cart can't see Game A's saves */
    load(m, "Game B", "GAME-B");
    wr(m, SAVE, 1);
    CHECK(cmd(m, 1) == 0 && rd(m, RESULT) == 0);
    CHECK(cmd(m, 2) == 2);
    CHECK(cmd(m, 4) == 2);
    CHECK(cmd(m, 6) == 0 && rd(m, RESULT) == 0);
    /* system commands are not allowed */
    CHECK(cmd(m, 16) == 5);
    CHECK(cmd(m, 20) == 5);

    /* a cart without an ID uses a title hash, stable across loads */
    load(m, "Untitled Thing", NULL);
    CHECK(!strncmp(m->cart_id, "T:", 2) && strlen(m->cart_id) == 10);
    char id1[17];
    memcpy(id1, m->cart_id, 17);
    load(m, "Untitled Thing", NULL);
    CHECK(!memcmp(id1, m->cart_id, 17));

    /* fill the card: 63-block saves until it's full */
    load(m, "Filler", "FILLER");
    put_meta(m, 0x3000, "FILL");
    int written = 0;
    for (int n = 0; n < 16; n++) {
        wr(m, SAVE, (uint32_t)n); wr(m, BUF, 0x1000); wr(m, LEN, 32000); wr(m, META, 0x3000);
        int e = cmd(m, 3);
        if (e == 3) break;
        CHECK(e == 0);
        written++;
    }
    CHECK(written == 3);                           /* 249 free / 64 blocks each */
    CHECK(cmd(m, 5) == 0 && rd(m, RESULT) == 249 - 3 * 64);
    /* replacing a save that doesn't fit leaves the old one intact */
    wr(m, SAVE, 0); wr(m, LEN, 32000);
    CHECK(cmd(m, 3) == 0);                         /* same size: fits by reusing its blocks */
    CHECK(cmd(m, 1) == 0 && rd(m, RESULT) == 1);

    /* the system ROM lists, inspects, copies and deletes */
    mei_set_privileged(m, 1);
    wr(m, SLOT, 0); wr(m, BUF, 0x8000); wr(m, LEN, 64 * 32);
    CHECK(cmd(m, 16) == 0);
    uint32_t count = rd(m, RESULT);
    CHECK(count == 3 + 3);                         /* Game A: 0, 1, 2; Filler: 0, 1, 2 */
    int found = -1;
    for (uint32_t i = 0; i < count; i++) {
        uint8_t *e = m->ram + 0x8000 + i * 64;
        if (!strncmp((char *)e, "GAME-A", 16) && rd32(e + 48) == 1) found = (int)i;
    }
    CHECK(found >= 0);
    uint8_t *ea = m->ram + 0x8000 + found * 64;
    CHECK(!strncmp((char *)ea + 16, "GAME A - SLOT 1", 32));
    CHECK(rd32(ea + 52) == 2 && rd32(ea + 56) == 500);
    uint32_t handle = rd32(ea + 60);
    wr(m, SAVE, handle); wr(m, META, 0x9000);
    CHECK(cmd(m, 17) == 0 && !memcmp(m->ram + 0x9000, m->ram + 0x3000 + 32, 0) && !strcmp((char *)m->ram + 0x9000, "GAME A - SLOT 1"));
    CHECK(cmd(m, 19) == 0);                        /* copy to card 2 */
    CHECK(mei_card_dirty(m, 1) == 1);
    wr(m, SLOT, 1); wr(m, BUF, 0x8000); wr(m, LEN, 64 * 32);
    CHECK(cmd(m, 16) == 0 && rd(m, RESULT) == 1);
    CHECK(!strncmp((char *)m->ram + 0x8000, "GAME-A", 16));
    wr(m, SLOT, 0); wr(m, SAVE, handle);
    CHECK(cmd(m, 18) == 0);                        /* delete from card 1 */
    wr(m, SAVE, 999);
    CHECK(cmd(m, 18) == 2);
    wr(m, BUF, 0x8000); wr(m, LEN, 64 * 32);
    CHECK(cmd(m, 16) == 0 && rd(m, RESULT) == 5);

    /* the copy on card 2 is readable by Game A */
    load(m, "Game A", "GAME-A");
    wr(m, SLOT, 1); wr(m, SAVE, 1); wr(m, BUF, 0x5000); wr(m, LEN, 2000); wr(m, META, 0);
    CHECK(cmd(m, 2) == 0 && rd(m, LEN) == 500);
    CHECK(!m->privileged);                         /* loading a cart drops the privilege */

    /* format */
    mei_set_privileged(m, 1);
    wr(m, SLOT, 1);
    CHECK(cmd(m, 20) == 0);
    CHECK(cmd(m, 5) == 0 && rd(m, RESULT) == 255);

    /* registers: unmapped and read-only offsets fault like other I/O */
    uint32_t v;
    CHECK(bus_read32(m, CARD + 0x20, &v) != 0 || mei_fault(m)->kind == MEI_FAULT_UNMAPPED);

    printf("test_card: %d checks, %d failed\n", checks, failures);
    return failures != 0;
}
