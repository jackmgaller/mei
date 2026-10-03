/* The World Checker's probe (docs/WORLDCHECKER.md). Runs a verification cart that the World Kit
 * generates (tools/worldkit/verify_render.py) and records, after every presented frame, the
 * frame's GPU statistics, a block of the cart's RAM (where the cart leaves what it measured)
 * and, when the cart asks for it, the picture: the triangle-ID buffer.
 *
 *   mei-scene-probe cart.mei out.bin frames ram-address ram-bytes
 *
 * The RAM block's first word is the cart's request: bit 0 set means "record this frame", bit 1
 * "and its picture". The output is "MSP1", the number of records, the block size, then per
 * record: the frame's MeiGpuStats as 18 u32 (tris, tris_empty, tris_dropped, px[8], clears,
 * lists, cpu_cycles, gpu_cycles, ticks, gpu_lag, then 0), the RAM block, and 320 x 240 u16
 * pixels if bit 1 was set. Exit 0, or 1 on a bad argument or I/O error, or 2 if the cart
 * faulted or stopped presenting frames (with a message on stderr). The cart's debug output goes
 * to stderr. No emulator behaviour is changed: this only reads state between frames. */
#include "machine.h"
#include <stdio.h>
#include <stdlib.h>

static void put32(FILE *f, uint32_t n) {
    for (int i = 0; i < 4; i++) fputc((int)(n >> (8 * i)) & 255, f);
}

static void debug_out(void *user, char c) { (void)user; fputc(c, stderr); }

int main(int argc, char **argv) {
    if (argc != 6) {
        fprintf(stderr, "usage: mei-scene-probe cart.mei out.bin frames ram-address ram-bytes\n");
        return 1;
    }
    char *end;
    unsigned long frames = strtoul(argv[3], &end, 0);
    if (*end || frames < 1 || frames > 100000) return 1;
    unsigned long address = strtoul(argv[4], &end, 0);
    if (*end || address >= RAM_SIZE || address % 4) return 1;
    unsigned long bytes = strtoul(argv[5], &end, 0);
    if (*end || bytes < 4 || bytes > RAM_SIZE - address) return 1;
    FILE *f = fopen(argv[1], "rb");
    if (!f) { perror(argv[1]); return 1; }
    fseek(f, 0, SEEK_END);
    long length = ftell(f);
    fseek(f, 0, SEEK_SET);
    size_t want = length < 0 ? 0 : length > (long)MEI_ROM_MAX ? MEI_ROM_MAX + 1 : (size_t)length;
    unsigned char *rom = malloc(want ? want : 1);
    if (!rom) { fclose(f); return 1; }
    size_t size = fread(rom, 1, want, f);
    fclose(f);
    Mei *m = mei_create();
    if (!m) { free(rom); return 1; }
    if (mei_load_cart(m, rom, size)) { free(rom); mei_destroy(m); fprintf(stderr, "bad cart\n"); return 1; }
    free(rom);
    mei_set_debug_output(m, debug_out, NULL);
    FILE *out = fopen(argv[2], "wb");
    if (!out) { perror(argv[2]); mei_destroy(m); return 1; }
    fwrite("MSP1", 1, 4, out);
    put32(out, 0);
    put32(out, (uint32_t)bytes);
    uint32_t records = 0;
    unsigned long shown = 0, idle = 0;
    int status = 0;
    while (shown < frames) {
        int presented = mei_run_frame(m);
        if (mei_fault(m)->kind) {
            fprintf(stderr, "mei-scene-probe: cart faulted: %s at pc 0x%08X addr 0x%08X\n",
                    mei_fault_name(mei_fault(m)->kind), mei_fault(m)->pc, mei_fault(m)->addr);
            status = 2;
            break;
        }
        if (!presented) {
            /* a frame over its CPU or GPU budget shows late; one that never shows is a hang */
            if (++idle > 600) { fprintf(stderr, "mei-scene-probe: no frame in 600 ticks\n"); status = 2; break; }
            continue;
        }
        idle = 0;
        shown++;
        uint32_t want_rec = rd32(m->ram + address);
        if (!(want_rec & 1)) continue;
        const MeiGpuStats *g = &m->gstat_last;
        put32(out, g->tris); put32(out, g->tris_empty); put32(out, g->tris_dropped);
        for (int k = 0; k < 8; k++) put32(out, g->px[k]);
        put32(out, g->clears); put32(out, g->lists); put32(out, g->cpu_cycles);
        put32(out, g->gpu_cycles); put32(out, g->ticks); put32(out, g->gpu_lag); put32(out, 0);
        fwrite(m->ram + address, 1, bytes, out);
        if (want_rec & 2) {
            const uint16_t *pixels = mei_display(m);
            for (int i = 0; i < MEI_W * MEI_H; i++) { fputc(pixels[i] & 255, out); fputc(pixels[i] >> 8, out); }
        }
        records++;
    }
    fseek(out, 4, SEEK_SET);
    put32(out, records);
    if (ferror(out)) status = 1;
    if (fclose(out)) status = 1;
    mei_destroy(m);
    return status;
}
