/* Mei language compiler (meic) library API.
 * Compiles an Akari source file (.akr) (plus its imports and the standard library)
 * to assembly text and assembles it into a cart image. See docs/LANGUAGE.md. */
#ifndef MEI_LANG_H
#define MEI_LANG_H

#include <stddef.h>
#include "asm.h"

/* Reads a whole file. On success stores a malloc'd buffer (the caller frees it)
 * and its length and returns 0; returns -1 if the file cannot be read.
 * A trailing NUL is not required. */
typedef int (*MeiReadFileFn)(void *user, const char *path, char **data, size_t *len);

#define MEI_CHECK_BOUNDS 1   /* array indexes and the stack (meic -g) */
#define MEI_CHECK_DIV    2   /* integer and fixed division by zero (--trap-div) */
#define MEI_CHECK_FMUL   4   /* fixed-point multiply overflow (--trap-fmul) */

typedef struct {
    MeiReadFileFn read_file;  /* NULL: read from the host file system with stdio */
    void *user;               /* passed to read_file */
    const char *stdlib_dir;   /* directory holding prelude.akr; NULL: $MEI_STDLIB, else "stdlib" */
    const char *title;        /* cart title; NULL: the `cart "..."` declaration, else the file name */
    int no_stdlib;            /* 1: do not import the standard library (test/bare-metal use) */
    int no_asserts;           /* 1: drop assert()/assert_eq() statements (meic --release) */
    int debug;                /* run-time checks (meic -g): MEI_CHECK_* bits; 0 for release code */
    int extra_warnings;       /* 1: also warn about likely mistakes in the cart's code (meic -W) */
    char **asm_text;          /* if non-NULL, receives the generated assembly (malloc'd, caller frees) */
    char **warnings;          /* if non-NULL, receives the warnings ("file:line:col: warning: ..." lines,
                                 malloc'd, caller frees), or NULL when there are none */
} MeiCompileOptions;

/* Compiles the program rooted at `path`. On success returns 0 and fills `out`
 * (free it with mei_asm_free). On failure returns -1 and writes a message of
 * the form "file:line:col: error: ..." (plus the offending source line) to err. */
int meic_compile(const char *path, const MeiCompileOptions *opt, MeiAsmResult *out,
                 char *err, size_t errlen);

#endif
