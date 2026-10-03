/* meiasm: the Mei assembler and disassembler.
 *   meiasm in.s [-o out.mei] [--sym out.sym] [--list]
 *   meiasm --disasm cart.mei
 * The default output is the input name with ".mei" appended. */
#include "asm.h"
#include "mei.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *read_file(const char *path, size_t *len) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    size_t cap = 1 << 16, n = 0;
    char *buf = malloc(cap + 1);
    for (size_t r; buf && (r = fread(buf + n, 1, cap - n, f)) > 0;) {
        n += r;
        if (n == cap) buf = realloc(buf, (cap *= 2) + 1);
    }
    fclose(f);
    if (!buf) return NULL;
    buf[n] = 0;
    *len = n;
    return buf;
}

static int usage(void) {
    fprintf(stderr, "usage: meiasm in.s [-o out.mei] [--sym out.sym] [--list]\n"
                    "       meiasm --disasm cart.mei\n");
    return 1;
}

static int disasm(const char *path) {
    size_t len;
    unsigned char *rom = (unsigned char *)read_file(path, &len);
    if (!rom) { perror(path); return 1; }
    int header = len >= 56 && !memcmp(rom + 4, "MEI1", 4);
    if (header) printf("; cart header, title \"%.32s\", ID \"%.16s\"\n", (const char *)rom + 8, (const char *)rom + 40);
    for (size_t i = 0; i + 4 <= len; i += 4) {
        uint32_t w = rom[i] | rom[i + 1] << 8 | rom[i + 2] << 16 | (uint32_t)rom[i + 3] << 24, pc = MEI_ROM_BASE + (uint32_t)i;
        char text[64];
        if (header && i >= 4 && i < 56) snprintf(text, sizeof text, ".word 0x%08X", w);
        else mei_disasm(w, pc, text, sizeof text);
        printf("%08X  %08X  %s\n", pc, w, text);
    }
    for (size_t i = len & ~(size_t)3; i < len; i++) printf("%08X  %02X        .byte 0x%02X\n", MEI_ROM_BASE + (unsigned)i, rom[i], rom[i]);
    free(rom);
    return 0;
}

int main(int argc, char **argv) {
    const char *in = NULL, *out = NULL, *sym = NULL, *dis = NULL;
    int list = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "--sym") && i + 1 < argc) sym = argv[++i];
        else if (!strcmp(argv[i], "--list")) list = 1;
        else if (!strcmp(argv[i], "--disasm") && i + 1 < argc) dis = argv[++i];
        else if (argv[i][0] != '-' && !in) in = argv[i];
        else return usage();
    }
    if (dis) return in ? usage() : disasm(dis);
    if (!in) return usage();

    size_t len;
    char *src = read_file(in, &len);
    if (!src) { perror(in); return 1; }
    if (strlen(src) != len) { fprintf(stderr, "%s: NUL byte in source\n", in); return 1; }
    MeiAsmOptions opts = {.listing = list};
    MeiAsmResult r;
    int rc = mei_assemble_opts(src, in, &opts, &r);
    free(src);
    if (rc) { fprintf(stderr, "%s\n", r.error); return 1; }

    char defout[1024];
    if (!out) snprintf(defout, sizeof defout, "%s.mei", in), out = defout;
    FILE *f = fopen(out, "wb");
    if (!f || fwrite(r.rom, 1, r.rom_len, f) != r.rom_len || fclose(f)) { perror(out); return 1; }
    if (sym) {
        FILE *s = fopen(sym, "w");
        if (!s) { perror(sym); return 1; }
        for (size_t i = 0; i < r.symbol_count; i++) fprintf(s, "%08X %s\n", r.symbols[i].value, r.symbols[i].name);
        fclose(s);
    }
    if (list) fputs(r.listing, stdout);
    mei_asm_free(&r);
    return 0;
}
