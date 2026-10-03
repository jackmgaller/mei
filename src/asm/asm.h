/* Mei assembler and disassembler library. Used by the meiasm tool and the compiler. */
#ifndef MEI_ASM_H
#define MEI_ASM_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    char *name;
    uint32_t value;
} MeiSymbol;

typedef struct {
    uint8_t *rom;          /* ROM image, loaded at MEI_ROM_BASE; caller frees with mei_asm_free */
    size_t rom_len;
    MeiSymbol *symbols;    /* every label and constant, sorted by value */
    size_t symbol_count;
    uint32_t ram_used;     /* end address of the RAM section */
    char error[512];       /* "file:line: message" when assembly fails */
    char *listing;         /* source listing, only when MeiAsmOptions.listing is set */
} MeiAsmResult;

/* A file held in memory: `.incbin "name"` takes these bytes instead of reading a file. */
typedef struct {
    const char *name;      /* matched exactly against the .incbin file name */
    const uint8_t *data;   /* not copied: must stay valid until mei_assemble_opts returns */
    size_t len;
} MeiAsmBlob;

typedef struct {
    int listing;           /* produce MeiAsmResult.listing (address, bytes, source line) */
    const MeiAsmBlob *blobs;   /* in-memory files for .incbin (the compiler's embeds), or NULL */
    size_t blob_count;
} MeiAsmOptions;

/* Assembles `source`. `filename` is used in error messages and as the base
 * directory for .include / .incbin. Returns 0 on success, -1 with
 * out->error set on failure. */
int mei_assemble(const char *source, const char *filename, MeiAsmResult *out);
void mei_asm_free(MeiAsmResult *r);

/* As mei_assemble, with options (opts may be NULL). */
int mei_assemble_opts(const char *source, const char *filename, const MeiAsmOptions *opts,
                      MeiAsmResult *out);

/* Looks up a symbol in a successful result. Returns 1 and sets *value if found. */
int mei_asm_find_symbol(const MeiAsmResult *r, const char *name, uint32_t *value);

/* Disassembles one word at address pc into buf (e.g. "addi r1, r0, 5",
 * "beq r1, r2, 0x200010"). Illegal words come out as ".word 0x...". */
void mei_disasm(uint32_t word, uint32_t pc, char *buf, size_t bufsize);

#endif
