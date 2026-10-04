/* Replay a frame with depth (docs/RENDERING.md) through the core: the plane registers, a full
 * VRAM image, a packet list at RAM 0x1000, then GPU register writes in order, each through the
 * bus as the CPU makes them (GPU_CTRL, GPU_DEPTH, GPU_ZCLEAR, GPU_CLEAR, GPU_DRAW).
 *
 * Input (little-endian): 64 plane register words, 1 MB VRAM, the list's byte count and bytes,
 * the number of writes and (I/O offset, value) pairs.
 * Output: the back framebuffer, the depth buffer and the display after vsync (RGB555 or keys,
 * 320 x 240 halfwords each), then 8 words: GPU cycles, triangles, px_ztest, px_zfail, zclears,
 * tris_recip, px_persp, persp_divs. Exit 0, or 2 for a bad fixture or a fault. */
#include "machine.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    FILE *in = fopen(argv[1], "rb"), *out = NULL;
    Mei *m = mei_create();
    if (!in || !m) return 2;
    unsigned char regs[256], word[4], pair[8];
    int result = 2;
    if (fread(regs, 1, 256, in) != 256 || fread(m->vram, 1, VRAM_SIZE, in) != VRAM_SIZE ||
        fread(word, 1, 4, in) != 4) goto done;
    for (int i = 0; i < 64; i++) m->pln_reg[i] = rd32(regs + 4*i);
    uint32_t bytes = rd32(word);
    if (bytes > RAM_SIZE - 0x1000 || bytes % 4 || fread(m->ram + 0x1000, 1, bytes, in) != bytes ||
        fread(word, 1, 4, in) != 4) goto done;
    m->fault.kind = MEI_FAULT_NONE;
    for (uint32_t n = rd32(word); n; n--) {
        if (fread(pair, 1, 8, in) != 8) goto done;
        if (bus_write32(m, IO_BASE + rd32(pair), rd32(pair + 4)) || m->fault.kind) goto done;
    }
    if (m->gpu_status & GPU_STATUS_DROPPED) goto done;
    out = fopen(argv[2], "wb");
    if (!out) goto done;
    uint32_t stats[8] = {(uint32_t)m->gpu_cycles, m->gpu_status & 0xFFFF, m->gstat.px_ztest,
                         m->gstat.px_zfail, m->gstat.zclears, m->gstat.tris_recip,
                         m->gstat.px_persp, m->gstat.persp_divs};
    if (fwrite(m->vram + gpu_back_addr(m) - VRAM_BASE, 2, MEI_W*MEI_H, out) != MEI_W*MEI_H ||
        fwrite(m->zbuf, 2, MEI_W*MEI_H, out) != MEI_W*MEI_H) goto done;
    gpu_vsync(m);
    planes_vsync(m);
    if (fwrite(mei_display(m), 2, MEI_W*MEI_H, out) != MEI_W*MEI_H ||
        fwrite(stats, 4, 8, out) != 8) goto done;
    result = 0;
done:
    if (out && fclose(out)) result = 2;
    fclose(in);
    mei_destroy(m);
    return result;
}
