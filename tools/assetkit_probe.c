/* Asset visibility probe. Runs a static diagnostic cart and captures the real
 * RGB555 face-ID buffer plus __sv (guard, fog, packed XY, fixed-point depth).
 * No emulator rendering behavior is changed. Input addresses come from meic's
 * symbol file; this tool validates them before reading emulator RAM.
 *
 *   mei-asset-probe cart.mei out.bin sv-address vertex-count [view-address views]
 *
 * With a view address, the cart draws the camera whose index it reads from the s32 global there
 * (docs/ASSETKIT.md, "What is checked"): for each index from 0 to views - 1 the probe starts a
 * fresh machine, loads the cart, writes the index there before the first frame and runs it as
 * without one, so each view is captured exactly as a cart compiled for that camera alone would
 * be. out.bin is then one capture per view, in order. A capture is "MAV1", the vertex count, the
 * last frame's triangles and CPU cycles, __sv and 320 x 240 u16 pixels. */
#include "machine.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void put32(FILE *f, uint32_t n) {
    for (int i=0; i<4; i++) fputc((int)(n>>(8*i))&255,f);
}

/* One view on m, made a fresh machine as mei_create() makes one (zeroed, then reset; the cart's
 * image is its only other memory) but without asking the system for new pages for each view:
 * 0, or 1 when the cart cannot be loaded or does not draw its two frames. */
static int capture(Mei *m, const unsigned char *rom, size_t size, unsigned long address, unsigned long count,
                   long view_address, uint32_t view, FILE *f) {
    free(m->rom);
    memset(m,0,sizeof *m);
    mei_reset(m);
    if (mei_load_cart(m,rom,size)) return 1;
    if (view_address>=0) wr32(m->ram+view_address,view);
    int shown=0;
    for (int i=0; i<16 && shown<2; i++) {
        shown+=mei_run_frame(m)!=0;
        if (mei_fault(m)->kind) break;
    }
    if (mei_fault(m)->kind || shown<2 || m->gstat_last.tris_dropped) {
        fprintf(stderr,"Probe failed: view=%u fault=%d presented=%d dropped=%u\n",view,mei_fault(m)->kind,shown,m->gstat_last.tris_dropped);
        return 1;
    }
    fwrite("MAV1",1,4,f);
    put32(f,(uint32_t)count);
    put32(f,m->gstat_last.tris);
    put32(f,m->gstat_last.cpu_cycles);
    fwrite(m->ram+address,16,count,f);
    static unsigned char out[MEI_W*MEI_H*2];
    const uint16_t *pixels=mei_display(m);
    for (int i=0; i<MEI_W*MEI_H; i++) {
        out[2*i]=(unsigned char)(pixels[i]&255); out[2*i+1]=(unsigned char)(pixels[i]>>8);
    }
    fwrite(out,1,sizeof out,f);
    return 0;
}

int main(int argc, char **argv) {
    if (argc!=5 && argc!=7) { fprintf(stderr,"usage: mei-asset-probe cart.mei output.bin sv-address vertex-count [view-address views]\n"); return 1; }
    char *end;
    unsigned long address=strtoul(argv[3],&end,0);
    if (*end || address>RAM_SIZE || address%16) return 1;
    unsigned long count=strtoul(argv[4],&end,0);
    if (*end || count<3 || count>2048 || count*16>RAM_SIZE-address) return 1;
    long view_address=-1;
    unsigned long views=1;
    if (argc==7) {
        unsigned long a=strtoul(argv[5],&end,0);
        if (*end || a>=RAM_SIZE-4 || a%4) return 1;
        view_address=(long)a;
        views=strtoul(argv[6],&end,0);
        if (*end || views<1 || views>4096) return 1;
    }
    FILE *f=fopen(argv[1],"rb");
    if (!f) { perror(argv[1]); return 1; }
    /* Read up to one byte more than the largest cart, so mei_load_cart rejects an oversized one. */
    fseek(f,0,SEEK_END);
    long length=ftell(f);
    fseek(f,0,SEEK_SET);
    size_t want=length<0 ? 0 : length>(long)MEI_ROM_MAX ? MEI_ROM_MAX+1 : (size_t)length;
    unsigned char *rom=malloc(want ? want : 1);
    if (!rom) { fclose(f); return 1; }
    size_t size=fread(rom,1,want,f);
    fclose(f);
    f=fopen(argv[2],"wb");
    if (!f) { perror(argv[2]); free(rom); return 1; }
    Mei *m=mei_create();
    int failed=!m;
    for (unsigned long v=0; v<views && !failed; v++)
        failed=capture(m,rom,size,address,count,view_address,(uint32_t)v,f);
    mei_destroy(m);
    free(rom);
    if (ferror(f)) failed=1;
    if (fclose(f)) failed=1;
    return failed?1:0;
}
