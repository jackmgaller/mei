/* Replay full VRAM and plane state without a cart/compiler/reference implementation. */
#include "machine.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    FILE *in = fopen(argv[1], "rb"), *out = NULL;
    Mei *m = mei_create();
    if (!in || !m) return 2;
    unsigned char regs[256], header[4];
    int result = 2;
    if (fread(regs, 1, 256, in) != 256 || fread(m->vram, 1, VRAM_SIZE, in) != VRAM_SIZE ||
        fread(header, 1, 4, in) != 4) goto done;
    for (int i = 0; i < 64; i++) m->pln_reg[i] = rd32(regs + 4*i);
    uint32_t bytes = rd32(header);
    if (bytes > 65536 || bytes % 4 || fread(m->ram + 0x1000, 1, bytes, in) != bytes) goto done;
    m->fault.kind = MEI_FAULT_NONE;
    m->gpu_ctrl = 0;
    if (bytes) gpu_draw_list(m, 0x1000);
    if (m->fault.kind || (m->gpu_status & GPU_STATUS_DROPPED)) goto done;
    out = fopen(argv[2], "wb");
    if (!out) goto done;
    if (fwrite(m->vram, 2, MEI_W*MEI_H, out) != MEI_W*MEI_H) goto done;
    gpu_vsync(m);
    planes_vsync(m);
    if (fwrite(mei_display(m), 2, MEI_W*MEI_H, out) != MEI_W*MEI_H) goto done;
    result = 0;
done:
    if (out && fclose(out)) result = 2;
    fclose(in);
    mei_destroy(m);
    return result;
}
