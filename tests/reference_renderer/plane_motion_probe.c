/* Persistent plane animation replay. Captures before/after presentation and auto-erase.
 * Header: frame count, then initial 1 MB VRAM. Per frame: 64 registers, palette,
 * two atlases, line tables, packet byte count and packets. All words little-endian. */
#include "machine.h"
#include <stdio.h>
#include <stdlib.h>

static int read_exact(FILE *f, void *p, size_t n) { return fread(p, 1, n, f) == n; }
static int capture(FILE *f, const uint16_t *p) { return fwrite(p, 2, MEI_W * MEI_H, f) == MEI_W * MEI_H; }
int main(int argc, char **argv) {
    if (argc != 3) return 2;
    FILE *in = fopen(argv[1], "rb"), *out = NULL;
    Mei *m = mei_create();
    int result = 2;
    if (!in || !m) goto done;
    unsigned char header[4], regs[256];
    if (!read_exact(in, header, 4)) goto done;
    uint32_t count = rd32(header);
    if (count > 4096 || !read_exact(in, m->vram, VRAM_SIZE)) goto done;
    m->fault.kind = MEI_FAULT_NONE;
    for (uint32_t frame = 0; frame < count; frame++) {
        if (!read_exact(in, regs, 256)) goto done;
        for (int i = 0; i < 64; i++) m->pln_reg[i] = rd32(regs + 4*i);
        if (!read_exact(in, m->vram + 0x4c000, 8192) ||
            !read_exact(in, m->vram + 0x60000, 32768) ||
            !read_exact(in, m->vram + 0x70000, 65536) ||
            !read_exact(in, m->vram + 0x52000, 6144) || !read_exact(in, header, 4)) goto done;
        uint32_t bytes = rd32(header);
        if (bytes > 65536 || bytes % 4 || !read_exact(in, m->ram + 0x1000, bytes)) goto done;
        m->gpu_ctrl = 0;
        gpu_clear(m, PLN_HOLE);
        if (bytes) gpu_draw_list(m, 0x1000);
        if (m->fault.kind || (m->gpu_status & GPU_STATUS_DROPPED)) goto done;
        if (!out) { out = fopen(argv[2], "wb"); if (!out) goto done; }
        if (!capture(out, mei_display(m))) goto done;
        gpu_vsync(m);
        planes_vsync(m);
        if (!capture(out, mei_display(m)) ||
            !capture(out, (const uint16_t *)(m->vram + gpu_back_addr(m) - VRAM_BASE))) goto done;
    }
    result = 0;
done:
    if (out && fclose(out)) result = 2;
    if (in) fclose(in);
    if (m) mei_destroy(m);
    return result;
}
