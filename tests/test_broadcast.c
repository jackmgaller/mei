/* Broadcast decoder tests (docs/BROADCAST.md). */
#include "machine.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int checks, failures;
#define CHECK(c) do { checks++; if (!(c)) { failures++; printf("FAIL line %d: %s\n", __LINE__, #c); } } while (0)

#define BC 0xFF0600u
enum { CTRL = 0x00, STATUS = 0x04, CMD = 0x08, RESULT = 0x0C, SLOT = 0x10, PAGE = 0x14, PSTAT = 0x18,
       ROWS0 = 0x1C, ROWS1 = 0x20, STAMP = 0x24, BUF = 0x28, LEN = 0x2C, ROW = 0x30,
       OK = 0x34, FIXED = 0x38, DROPPED = 0x3C, FIFO = 0x40, FIFO_LEVEL = 0x44 };

static uint32_t rd(Mei *m, uint32_t off) { uint32_t v = 0; bus_read32(m, BC + off, &v); return v; }
static void wr(Mei *m, uint32_t off, uint32_t v) { bus_write32(m, BC + off, v); }

static const uint8_t HAM[16] = {0x15, 0x02, 0x49, 0x5E, 0x64, 0x73, 0x38, 0x2F,
                                0xD0, 0xC7, 0x8C, 0x9B, 0xA1, 0xB6, 0xFD, 0xEA};

/* Builds a packet; the payload is filled with `fill` + row (or copied from data if not NULL). */
static void make_packet(uint8_t *p, uint32_t page_id, int row, int last, int version, const uint8_t *data, uint8_t fill) {
    uint32_t h = (page_id & 0xFFFF) | (uint32_t)(row & 63) << 16 | (uint32_t)(last != 0) << 23 | (uint32_t)(version & 255) << 24;
    p[0] = 0x55; p[1] = 0xA7;
    for (int i = 0; i < 8; i++) p[2 + i] = HAM[h >> (4 * i) & 15];
    for (int i = 0; i < 52; i++) p[10 + i] = data ? data[i] : (uint8_t)(fill + row + i);
    uint8_t hb[4] = {(uint8_t)h, (uint8_t)(h >> 8), (uint8_t)(h >> 16), (uint8_t)(h >> 24)};
    uint16_t c = bc_crc16(p + 10, 52, bc_crc16(hb, 4, 0xFFFF));
    p[62] = (uint8_t)c; p[63] = (uint8_t)(c >> 8);
}

/* Delivers bytes 16 per tick, as the frame loop does (ticks are simulated directly). */
static void deliver(Mei *m, const uint8_t *data, int len) {
    for (int i = 0; i < len; i += 16) {
        int n = len - i < 16 ? len - i : 16;
        CHECK(mei_broadcast_feed(m, data + i, n) == n);
        broadcast_tick(m);
        m->frame++;
    }
}

static void send(Mei *m, uint32_t page_id, int row, int last, int version, uint8_t fill) {
    uint8_t p[64];
    make_packet(p, page_id, row, last, version, NULL, fill);
    deliver(m, p, 64);
}

static int slot_of(Mei *m, int slot) { wr(m, SLOT, (uint32_t)slot); return slot; }

static void fresh(Mei *m) {
    mei_reset(m);
    mei_broadcast_carrier(m, 1);
    mei_broadcast_noise(m, 0, 0);
    wr(m, CTRL, 1);
}

int main(void) {
    Mei *m = mei_create();
    uint8_t rom[64] = {0};
    mei_load_cart(m, rom, sizeof rom);

    /* Hamming 8/4: every code byte, every single-bit error corrected, every double detected */
    int ham_ok = 1;
    for (int n = 0; n < 16; n++) {
        if (bc_hamming84(HAM[n]) != n) ham_ok = 0;
        for (int a = 0; a < 8; a++) {
            if (bc_hamming84((uint8_t)(HAM[n] ^ 1 << a)) != (0x10 | n)) ham_ok = 0;
            for (int b = a + 1; b < 8; b++) if (bc_hamming84((uint8_t)(HAM[n] ^ 1 << a ^ 1 << b)) != -1) ham_ok = 0;
        }
    }
    CHECK(ham_ok);
    int singles = 0, doubles = 0;
    for (int b = 0; b < 256; b++) { int v = bc_hamming84((uint8_t)b); singles += v >= 0x10; doubles += v < 0; }
    CHECK(singles == 128 && doubles == 112);

    /* CRC-16/CCITT-FALSE check value */
    CHECK(bc_crc16((const uint8_t *)"123456789", 9, 0xFFFF) == 0x29B1);

    /* idle after reset: receiver off, slots free, nothing received */
    mei_reset(m);
    CHECK(rd(m, CTRL) == 0);
    CHECK(rd(m, STATUS) == 0);
    CHECK(rd(m, PAGE) == 0xFFFFFFFFu);
    mei_broadcast_carrier(m, 1);
    CHECK(rd(m, STATUS) == 1);
    wr(m, PAGE, 0x0401);
    send(m, 0x0401, 0, 1, 1, 0);
    CHECK(rd(m, OK) == 0 && rd(m, PSTAT) == 0);            /* receiver still off */

    /* a one-row page */
    fresh(m);
    CHECK(rd(m, STATUS) == 1);
    slot_of(m, 2);
    wr(m, PAGE, 0x0401);
    CHECK(rd(m, PAGE) == 0x0401);
    m->frame = 100;
    send(m, 0x0401, 0, 1, 7, 0x20);
    CHECK(rd(m, OK) == 1);
    CHECK(rd(m, STATUS) == (3u | 1u << 10 | 1u << 18));   /* carrier, locked, slot 2 complete + changed */
    CHECK(rd(m, PSTAT) == (1u | 2 | 4 | 7u << 8 | 1u << 16 | 1u << 24));
    CHECK(rd(m, STAMP) == 100);
    CHECK(rd(m, ROWS0) == 1 && rd(m, ROWS1) == 0);
    memset(m->ram + 0x1000, 0xEE, 200);
    wr(m, BUF, 0x1000); wr(m, LEN, 200); wr(m, CMD, 1);
    CHECK(rd(m, RESULT) == 0 && rd(m, LEN) == 52);
    CHECK(m->ram[0x1000] == 0x20 && m->ram[0x1000 + 51] == 0x20 + 51 && m->ram[0x1000 + 52] == 0xEE);
    CHECK((rd(m, PSTAT) & 2) == 0);                         /* read: no longer changed */
    /* the same version again is ignored: still complete, not changed */
    send(m, 0x0401, 0, 1, 7, 0x20);
    CHECK((rd(m, PSTAT) & 3) == 1);
    /* other pages and filler are counted, not stored */
    send(m, 0x0402, 0, 1, 1, 0);
    send(m, 0x0FFF, 0, 1, 0, 0);
    CHECK(rd(m, OK) == 4);
    CHECK(rd(m, PSTAT) >> 8 == (7u | 1u << 8 | 1u << 16));

    /* out-of-order assembly of a 3-row page, with two slots on different pages */
    fresh(m);
    slot_of(m, 0); wr(m, PAGE, 0x3401);
    slot_of(m, 1); wr(m, PAGE, 0x0401);
    send(m, 0x3401, 2, 1, 5, 0x40);
    slot_of(m, 0);
    CHECK((rd(m, PSTAT) & 7) == 4 && rd(m, PSTAT) >> 24 == 3);   /* on air, 3 rows, not complete */
    send(m, 0x0401, 0, 1, 1, 0x10);
    send(m, 0x3401, 0, 0, 5, 0x40);
    CHECK((rd(m, PSTAT) & 1) == 0 && rd(m, ROWS0) == 5);
    wr(m, ROW, 1); wr(m, BUF, 0x2000); wr(m, LEN, 52); wr(m, CMD, 2);
    CHECK(rd(m, RESULT) == 4 && rd(m, LEN) == 0);            /* row 1 not yet here */
    wr(m, ROW, 2); wr(m, LEN, 52); wr(m, CMD, 2);
    CHECK(rd(m, RESULT) == 0 && rd(m, LEN) == 52 && m->ram[0x2000] == 0x42);
    send(m, 0x3401, 1, 0, 5, 0x40);
    CHECK((rd(m, PSTAT) & 3) == 3 && (rd(m, PSTAT) >> 16 & 255) == 3);
    CHECK((rd(m, STATUS) >> 8 & 3) == 3);                     /* slots 0 and 1 complete */
    wr(m, BUF, 0x3000); wr(m, LEN, 1000); wr(m, CMD, 1);
    CHECK(rd(m, LEN) == 156);
    CHECK(m->ram[0x3000] == 0x40 && m->ram[0x3000 + 52] == 0x41 && m->ram[0x3000 + 104] == 0x42);
    /* a short buffer truncates; a bad address is refused */
    wr(m, LEN, 10); wr(m, CMD, 1);
    CHECK(rd(m, RESULT) == 0 && rd(m, LEN) == 10);
    wr(m, BUF, 0x1FFFF0); wr(m, LEN, 100); wr(m, CMD, 1);
    CHECK(rd(m, RESULT) == 2);
    wr(m, BUF, ROM_BASE); wr(m, CMD, 1);
    CHECK(rd(m, RESULT) == 2);
    slot_of(m, 5); wr(m, CMD, 1);
    CHECK(rd(m, RESULT) == 3);                                /* free slot */
    wr(m, CMD, 9);
    CHECK(rd(m, RESULT) == 1);

    /* a version change restarts assembly */
    slot_of(m, 0);
    send(m, 0x3401, 0, 0, 6, 0x50);
    CHECK((rd(m, PSTAT) & 3) == 0 && (rd(m, PSTAT) >> 8 & 255) == 6 && rd(m, ROWS0) == 1);
    CHECK(rd(m, PSTAT) >> 24 == 0);                           /* the length is not known again yet */
    send(m, 0x3401, 2, 1, 6, 0x50);
    send(m, 0x3401, 1, 0, 6, 0x50);
    CHECK((rd(m, PSTAT) & 3) == 3);
    wr(m, BUF, 0x3000); wr(m, LEN, 1000); wr(m, CMD, 1);
    CHECK(m->ram[0x3000] == 0x50);
    /* reselecting clears the slot; bit 31 frees it */
    wr(m, PAGE, 0x3401);
    CHECK(rd(m, PSTAT) == 0 && rd(m, ROWS0) == 0);
    wr(m, PAGE, 0x80000000u);
    CHECK(rd(m, PAGE) == 0xFFFFFFFFu);

    /* Hamming correction in the header; double errors and CRC errors drop the packet */
    fresh(m);
    slot_of(m, 0); wr(m, PAGE, 0x0123);
    uint8_t p[64];
    make_packet(p, 0x0123, 0, 1, 1, NULL, 0);
    p[2] ^= 0x08; p[9] ^= 0x80;                               /* one bit in each of two nibbles */
    deliver(m, p, 64);
    CHECK(rd(m, OK) == 1 && rd(m, FIXED) == 1 && (rd(m, PSTAT) & 1));
    make_packet(p, 0x0123, 0, 1, 2, NULL, 0);
    p[4] ^= 0x11;                                             /* two bits in one nibble */
    deliver(m, p, 64);
    CHECK(rd(m, OK) == 1 && rd(m, DROPPED) == 1 && (rd(m, PSTAT) >> 8 & 255) == 1);
    make_packet(p, 0x0123, 0, 1, 2, NULL, 0);
    p[30] ^= 0x04;                                            /* payload bit: CRC fails */
    deliver(m, p, 64);
    CHECK(rd(m, DROPPED) == 2 && (rd(m, PSTAT) >> 8 & 255) == 1);
    CHECK(rd(m, STATUS) & 2);                                 /* still locked (flywheel) */
    make_packet(p, 0x0123, 0, 1, 2, NULL, 0);
    p[0] ^= 0x01; p[1] ^= 0x40;                               /* sync off by 2 bits: accepted when locked */
    deliver(m, p, 64);
    CHECK(rd(m, OK) == 2 && (rd(m, PSTAT) >> 8 & 255) == 2);
    wr(m, CMD, 4);
    CHECK(rd(m, OK) == 0 && rd(m, FIXED) == 0 && rd(m, DROPPED) == 0);

    /* four bad packets in a row lose the lock */
    for (int i = 0; i < 4; i++) {
        make_packet(p, 0x0123, 0, 1, 3, NULL, 0);
        p[20] ^= 1;
        deliver(m, p, 64);
    }
    CHECK(rd(m, DROPPED) == 4 && !(rd(m, STATUS) & 2));

    /* sync hunt from the middle of the stream, past a false sync word in a payload */
    fresh(m);
    slot_of(m, 0); wr(m, PAGE, 0x0200);
    {
        static uint8_t stream[64 * 6];
        uint8_t data[52] = {0};
        data[10] = 0x55; data[11] = 0xA7;                     /* a sync word inside the payload */
        make_packet(stream, 0x0200, 0, 0, 3, data, 0);
        for (int r = 1; r < 6; r++) make_packet(stream + 64 * r, 0x0200, r, r == 5, 3, data, 0);
        deliver(m, stream + 15, 64 * 6 - 15);                 /* tune in mid-packet, before the false sync */
        CHECK(rd(m, STATUS) & 2);
        CHECK(rd(m, OK) == 5 && rd(m, DROPPED) == 0);         /* rows 1-5; row 0 was missed */
        CHECK(rd(m, ROWS0) == 0x3E && (rd(m, PSTAT) & 1) == 0);
        deliver(m, stream, 64);                               /* row 0 on the next pass */
        CHECK((rd(m, PSTAT) & 3) == 3);
        /* garbage between packets: lock is lost and found again */
        uint8_t junk[100];
        for (int i = 0; i < 100; i++) junk[i] = (uint8_t)(i * 37 + 11);
        deliver(m, junk, 100);
        deliver(m, stream, 64 * 6);
        CHECK(rd(m, STATUS) & 2);
        CHECK(rd(m, OK) >= 11);
    }

    /* bytes can arrive unevenly (a live socket): packets still assemble */
    fresh(m);
    slot_of(m, 0); wr(m, PAGE, 0x0100);
    make_packet(p, 0x0100, 0, 1, 9, NULL, 0);
    for (int i = 0; i < 64; i += 5) { mei_broadcast_feed(m, p + i, i + 5 <= 64 ? 5 : 64 - i); broadcast_tick(m); m->frame++; }
    CHECK(rd(m, PSTAT) & 1);
    CHECK(mei_broadcast_feed(m, p, 64) == 16);                /* at most 16 bytes per tick */
    broadcast_tick(m);

    /* the stamp is the tick of the sync word's first byte */
    fresh(m);
    slot_of(m, 0); wr(m, PAGE, 0x0100);
    {
        uint8_t two[72] = {0};
        make_packet(two + 8, 0x0100, 0, 1, 1, NULL, 0);       /* sync at byte 8 of tick 500 */
        m->frame = 500;
        deliver(m, two, 72);
        CHECK(rd(m, STAMP) == 500);
        make_packet(two, 0x0100, 0, 1, 2, NULL, 0);
        uint8_t pad[16 + 64] = {0};
        memcpy(pad + 16, two, 64);                            /* sync at byte 0 of tick 506 */
        deliver(m, pad, 80);
        CHECK(rd(m, STAMP) == 506);
    }

    /* no carrier, or receiver off: nothing is received and the lock goes */
    fresh(m);
    send(m, 0x0100, 0, 1, 1, 0);
    CHECK(rd(m, STATUS) & 2);
    mei_broadcast_carrier(m, 0);
    CHECK((rd(m, STATUS) & 3) == 0);
    send(m, 0x0100, 0, 1, 1, 0);
    CHECK(rd(m, OK) == 1);
    mei_broadcast_carrier(m, 1);
    wr(m, CTRL, 0);
    send(m, 0x0100, 0, 1, 1, 0);
    CHECK(rd(m, OK) == 1 && !(rd(m, STATUS) & 2));

    /* raw FIFO */
    fresh(m);
    wr(m, CTRL, 3);
    CHECK(rd(m, CTRL) == 3);
    make_packet(p, 0x0100, 0, 1, 1, NULL, 0);
    deliver(m, p, 64);
    CHECK(rd(m, FIFO_LEVEL) == 64 && rd(m, OK) == 1);         /* the decoder runs as well */
    CHECK(rd(m, FIFO) == 0x155 && rd(m, FIFO) == 0x1A7 && rd(m, FIFO_LEVEL) == 62);
    wr(m, BUF, 0x4000); wr(m, LEN, 100); wr(m, CMD, 3);
    CHECK(rd(m, RESULT) == 0 && rd(m, LEN) == 62 && !memcmp(m->ram + 0x4000, p + 2, 62));
    CHECK(rd(m, FIFO) == 0 && rd(m, FIFO_LEVEL) == 0);
    for (int i = 0; i < 17; i++) deliver(m, p, 64);           /* 1,088 bytes: overflows */
    CHECK(rd(m, FIFO_LEVEL) == 1024 && (rd(m, STATUS) & 4));
    wr(m, LEN, 0); wr(m, CMD, 3);
    CHECK(!(rd(m, STATUS) & 4) && rd(m, FIFO_LEVEL) == 1024);
    wr(m, CTRL, 1); wr(m, CTRL, 3);                           /* turning capture on empties it */
    CHECK(rd(m, FIFO_LEVEL) == 0);

    /* noise: deterministic, corrected and dropped packets, pages still assemble */
    {
        static uint8_t stream[64 * 400];
        for (int i = 0; i < 400; i++) make_packet(stream + 64 * i, 0x0300 + (i % 10 == 0), i % 4, i % 4 == 3, 1, NULL, 0);
        uint32_t ok[2], fixed[2], dropped[2];
        for (int run = 0; run < 2; run++) {
            fresh(m);
            mei_broadcast_noise(m, 1000, 12345);              /* 0.1 % of bits: about 35 % of packets lost */
            slot_of(m, 0); wr(m, PAGE, 0x0300);
            deliver(m, stream, sizeof stream);
            ok[run] = rd(m, OK); fixed[run] = rd(m, FIXED); dropped[run] = rd(m, DROPPED);
            CHECK(rd(m, PSTAT) & 1);
        }
        CHECK(ok[0] == ok[1] && fixed[0] == fixed[1] && dropped[0] == dropped[1]);
        CHECK(fixed[0] > 0 && dropped[0] > 0 && ok[0] > 200);
        printf("noise 1000 ppm over 400 packets: %u ok (%u corrected), %u dropped\n", ok[0], fixed[0], dropped[0]);
        mei_broadcast_noise(m, 0, 0);
    }

    /* register access rules */
    fresh(m);
    uint32_t v;
    CHECK(bus_read32(m, BC + 0x48, &v) == -1 && mei_fault(m)->kind == MEI_FAULT_UNMAPPED);
    m->fault.kind = 0;
    CHECK(bus_read32(m, 0xFF06FC, &v) == -1 && mei_fault(m)->kind == MEI_FAULT_UNMAPPED);
    m->fault.kind = 0;
    CHECK(bus_read32(m, 0xFF0700, &v) == -1 && mei_fault(m)->kind == MEI_FAULT_UNMAPPED);
    m->fault.kind = 0;
    CHECK(bus_write32(m, BC + STATUS, 1) == -1 && mei_fault(m)->kind == MEI_FAULT_READ_ONLY);
    m->fault.kind = 0;
    CHECK(bus_write32(m, BC + OK, 1) == -1 && mei_fault(m)->kind == MEI_FAULT_READ_ONLY);
    m->fault.kind = 0;
    CHECK(bus_read8(m, BC + CTRL, &v, 0) == -1 && mei_fault(m)->kind == MEI_FAULT_IO_WIDTH);
    m->fault.kind = 0;
    CHECK(bus_read32(m, BC + CMD, &v) == 0 && v == 0);
    wr(m, CTRL, 0xFFFFFFFFu);
    CHECK(rd(m, CTRL) == 3);
    wr(m, SLOT, 13);
    CHECK(rd(m, SLOT) == 5);
    /* reset turns it all off but keeps the signal */
    wr(m, PAGE, 0x0100);
    mei_reset(m);
    CHECK(rd(m, CTRL) == 0 && rd(m, PAGE) == 0xFFFFFFFFu && (rd(m, STATUS) & 1));

    mei_destroy(m);
    printf("broadcast: %d checks, %d failures\n", checks, failures);
    return failures != 0;
}
