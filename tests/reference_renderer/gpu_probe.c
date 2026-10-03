/* Replay oracle-generated packets through the real GPU, bypassing Akari geometry.
 * Input: LE clear/dither/list byte count, 8 KB palette, 512 KB texture RAM, list.
 * Output: native little-endian RGB555 framebuffer. */
#include "machine.h"
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (argc != 3) return 1;
    FILE *in = fopen(argv[1], "rb");
    if (!in) return 1;
    Mei *m = mei_create();
    if (!m) { fclose(in); return 1; }
    unsigned char header[12];
    int result = 1;
    if (fread(header, 1, sizeof header, in) != sizeof header) goto done;
    uint32_t bytes = rd32(header + 8);
    if (bytes > RAM_SIZE - 0x1000 || bytes % 4) goto done;
    if (fread(m->vram + PALETTE_ADDR - VRAM_BASE, 1, 8192, in) != 8192) goto done;
    if (fread(m->vram + TEXTURE_ADDR - VRAM_BASE, 1, 524288, in) != 524288) goto done;
    if (fread(m->ram + 0x1000, 1, bytes, in) != bytes) goto done;
    m->fault.kind = MEI_FAULT_NONE;
    m->gpu_ctrl = rd32(header + 4);
    gpu_clear(m, rd32(header));
    gpu_draw_list(m, bytes ? 0x1000 : 0xFFFFFF);
    if (m->fault.kind || (m->gpu_status & GPU_STATUS_DROPPED)) goto done;
    FILE *out = fopen(argv[2], "wb");
    if (!out) goto done;
    result = fwrite(m->vram + gpu_back_addr(m) - VRAM_BASE, 2, MEI_W * MEI_H, out) == MEI_W * MEI_H ? 0 : 1;
    if (fclose(out)) result = 1;
done:
    fclose(in);
    mei_destroy(m);
    return result;
}
