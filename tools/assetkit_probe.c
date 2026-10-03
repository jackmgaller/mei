/* Asset visibility probe. Runs a static diagnostic cart and captures the real
 * RGB555 face-ID buffer plus __sv (guard, fog, packed XY, fixed-point depth).
 * No emulator rendering behavior is changed. Input addresses come from meic's
 * symbol file; this tool validates them before reading emulator RAM. */
#include "machine.h"
#include <stdio.h>
#include <stdlib.h>

static void put32(FILE *f, uint32_t n) {
    for (int i=0; i<4; i++) fputc((int)(n>>(8*i))&255,f);
}

int main(int argc, char **argv) {
    if (argc!=5) { fprintf(stderr,"usage: mei-asset-probe cart.mei output.bin sv-address vertex-count\n"); return 1; }
    char *end;
    unsigned long address=strtoul(argv[3],&end,0);
    if (*end || address>RAM_SIZE || address%16) return 1;
    unsigned long count=strtoul(argv[4],&end,0);
    if (*end || count<3 || count>2048 || count*16>RAM_SIZE-address) return 1;
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
    Mei *m=mei_create();
    if (!m) { free(rom); return 1; }
    if (mei_load_cart(m,rom,size)) { free(rom); mei_destroy(m); return 1; }
    free(rom);
    int shown=0;
    for (int i=0; i<16 && shown<2; i++) {
        shown+=mei_run_frame(m)!=0;
        if (mei_fault(m)->kind) break;
    }
    if (mei_fault(m)->kind || shown<2 || m->gstat_last.tris_dropped) {
        fprintf(stderr,"Probe failed: fault=%d presented=%d dropped=%u\n",mei_fault(m)->kind,shown,m->gstat_last.tris_dropped);
        mei_destroy(m); return 1;
    }
    f=fopen(argv[2],"wb");
    if (!f) { perror(argv[2]); mei_destroy(m); return 1; }
    fwrite("MAV1",1,4,f);
    put32(f,(uint32_t)count);
    put32(f,m->gstat_last.tris);
    put32(f,m->gstat_last.cpu_cycles);
    fwrite(m->ram+address,16,count,f);
    const uint16_t *pixels=mei_display(m);
    for (int i=0; i<MEI_W*MEI_H; i++) {
        fputc(pixels[i]&255,f); fputc(pixels[i]>>8,f);
    }
    int failed=ferror(f);
    if (fclose(f)) failed=1;
    mei_destroy(m);
    return failed?1:0;
}
