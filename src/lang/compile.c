/* Compiler driver: file loading (through the reader callback), imports,
 * the standard library prelude, and the final call into the assembler. */
#define _POSIX_C_SOURCE 200809L
#include "internal.h"

#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int default_read(void *user, const char *path, char **data, size_t *len) {
    (void)user;
    FILE *f = fopen(path, "rb");
    if (!f) return -1;
    size_t cap = 4096, n = 0;
    char *buf = malloc(cap);
    for (;;) {
        if (n == cap) { cap *= 2; buf = realloc(buf, cap); }
        size_t r = fread(buf + n, 1, cap - n, f);
        if (!r) break;
        n += r;
    }
    int bad = ferror(f);
    fclose(f);
    if (bad) { free(buf); return -1; }
    *data = buf;
    *len = n;
    return 0;
}

/* Joins `rel` onto the directory of `from` and removes "." and ".." segments. */
static char *resolve_path(const char *from, const char *rel) {
    Buf b = {0};
    if (rel[0] != '/' && from) {
        const char *slash = strrchr(from, '/');
        if (slash) buf_putn(&b, from, (size_t)(slash - from + 1));
    }
    buf_puts(&b, rel);
    /* normalise */
    char *segs[256];
    int n = 0, absolute = b.p[0] == '/';
    char *s = b.p;
    for (char *tok = strtok(s, "/"); tok; tok = strtok(NULL, "/")) {
        if (!strcmp(tok, ".")) continue;
        if (!strcmp(tok, "..") && n > 0 && strcmp(segs[n - 1], "..")) { n--; continue; }
        if (n < 256) segs[n++] = tok;
    }
    Buf o = {0};
    if (absolute) buf_putc(&o, '/');
    for (int i = 0; i < n; i++) { if (i) buf_putc(&o, '/'); buf_puts(&o, segs[i]); }
    char *r = ar_strdup(o.p ? o.p : ".");
    buf_free(&b);
    buf_free(&o);
    return r;
}

static int read_file(Compiler *C, const char *path, char **data, size_t *len) {
    MeiReadFileFn fn = C->opt->read_file ? C->opt->read_file : default_read;
    char *raw = NULL;
    size_t n = 0;
    if (fn(C->opt->user, path, &raw, &n) != 0) return -1;
    /* copy into the arena with a terminating NUL */
    char *p = ar_alloc(n + 1);
    if (n) memcpy(p, raw, n);
    free(raw);
    *data = p;
    *len = n;
    return 0;
}

void compiler_import_as(Compiler *C, const char *from_file, const char *path, const char *alias, Loc loc) {
    char *full = resolve_path(from_file, path);
    int std = C->importing_stdlib || (from_file && file_is_stdlib(from_file));
    if (!std && path[0] != '/' && C->stdlib_dir) {
        /* not next to the importing file: a standard library file outside the prelude
           (planes.akr), which a cart imports by name */
        char *probe;
        size_t plen;
        if (read_file(C, full, &probe, &plen) != 0) {
            char *alt = resolve_path(NULL, ar_printf("%s/%s", C->stdlib_dir, path));
            if (read_file(C, alt, &probe, &plen) == 0) { full = alt; std = 1; }
        }
    }
    int isolated = alias || file_is_module(from_file);
    module_import(from_file, full, alias, loc);
    for (int i = 0; i < C->nseen; i++) if (!strcmp(C->seen[i], full)) {
        if (!isolated) module_publish(full, C->prog);
        return;
    }
    module_begin(full, isolated);
    if (C->nseen == C->capseen) {
        int nc = C->capseen ? C->capseen * 2 : 16;
        char **ns = ar_alloc(sizeof(char *) * (size_t)nc);
        if (C->nseen) memcpy(ns, C->seen, sizeof(char *) * (size_t)C->nseen);
        C->seen = ns;
        C->capseen = nc;
    }
    C->seen[C->nseen++] = full;
    if (std) mark_stdlib_file(full);
    char *text;
    size_t len;
    if (read_file(C, full, &text, &len) != 0) {
        if (from_file) error_at(loc, "cannot read '%s'", full);
        error_plain("error: cannot read '%s'", full);
    }
    src_register(full, text, len);
    parse_file(C, C->prog, full, text, len);
}

void compiler_import(Compiler *C, const char *from_file, const char *path, Loc loc) {
    compiler_import_as(C, from_file, path, NULL, loc);
}

const uint8_t *compiler_load_binary(Compiler *C, const char *from_file, const char *path, Loc loc, size_t *len) {
    char *full = resolve_path(from_file, path);
    char *data;
    if (read_file(C, full, &data, len) != 0) error_at(loc, "cannot read asset '%s'", full);
    return (const uint8_t *)data;
}

static const char *basename_noext(const char *path) {
    const char *s = strrchr(path, '/');
    s = s ? s + 1 : path;
    const char *dot = strrchr(s, '.');
    return dot ? ar_strndup(s, (size_t)(dot - s)) : ar_strdup(s);
}

/* Maps an assembler error ("file.s:LINE: message") inside an asm block back to the
 * Akari source; anything else is a compiler bug. */
static void report_asm_error(const char *text, const char *aerr, char *err, size_t errlen) {
    const char *colon = strchr(aerr, ':');
    long line = colon ? strtol(colon + 1, NULL, 10) : 0;
    const char *msg = colon ? strchr(colon + 1, ':') : NULL;
    msg = msg ? msg + 1 : aerr;
    while (*msg == ' ') msg++;
    /* walk the generated text up to the failing line, tracking asm markers */
    const char *p = text, *mfile = NULL;
    long n = 1, mline = 0, mstart = 0;
    size_t mfilelen = 0;
    while (*p && n < line) {
        const char *e = strchr(p, '\n');
        if (!e) break;
        const char *m = strstr(p, "; @asm ");
        if (m && m < e) {
            const char *f = m + 7, *c = e;
            while (c > f && *c != ':') c--;
            mfile = f; mfilelen = (size_t)(c - f); mline = strtol(c + 1, NULL, 10); mstart = n;
        }
        m = strstr(p, "; @end");
        if (m && m < e) mfile = NULL;
        p = e + 1;
        n++;
    }
    if (mfile && line > mstart && err && errlen) {
        snprintf(err, errlen, "%.*s:%ld:1: error: in asm: %s", (int)mfilelen, mfile, mline + (line - mstart - 1), msg);
        return;
    }
    if (err && errlen)
        snprintf(err, errlen, "internal compiler error: the generated assembly failed to assemble: %s\n"
                 "(please report this; meic -S writes the generated assembly)", aerr);
}

int meic_compile(const char *path, const MeiCompileOptions *opt, MeiAsmResult *out, char *err, size_t errlen) {
    static const MeiCompileOptions defaults;
    if (!opt) opt = &defaults;
    memset(out, 0, sizeof *out);
    if (err && errlen) err[0] = 0;
    jmp_buf jb;
    void *saved = g_error_jmp;
    g_error_jmp = &jb;
    error_reset(err, errlen);
    Buf text = {0};
    warn_reset();
    if (opt->warnings) *opt->warnings = NULL;
    if (setjmp(jb)) {
        warn_reset();
        buf_free(&text);
        symtab_reset();
        ar_free_all();
        g_error_jmp = saved;
        return -1;
    }
    symtab_reset();
    types_init();
    Program *P = ar_alloc(sizeof *P);
    Compiler C = {.opt = opt, .prog = P};
    if (!opt->no_stdlib) {
        const char *dir = opt->stdlib_dir;
        if (!dir) dir = getenv("MEI_STDLIB");
        if (!dir || !*dir) dir = "stdlib";
        /* Akari sources end in .akr; .mls is the older extension */
        char *prelude = ar_printf("%s/prelude.akr", dir);
        char *probe;
        size_t plen;
        if (read_file(&C, resolve_path(NULL, prelude), &probe, &plen) != 0) {
            prelude = ar_printf("%s/prelude.mls", dir);
            if (read_file(&C, resolve_path(NULL, prelude), &probe, &plen) != 0)
                error_plain("error: cannot find the standard library in '%s' (set MEI_STDLIB to the stdlib directory)", dir);
        }
        C.stdlib_dir = dir;
        C.importing_stdlib = 1;
        compiler_import(&C, NULL, prelude, (Loc){0});
        C.importing_stdlib = 0;
    }
    compiler_import(&C, NULL, path, (Loc){0});
    if (opt->title) P->title = opt->title;
    if (!P->title) P->title = basename_noext(path);
    P->debug = opt->debug;
    P->wextra = opt->extra_warnings;
    check_program(P);
    gen_program(P, &text);
    if (opt->asm_text) *opt->asm_text = strdup(text.p ? text.p : "");
    if (opt->warnings) *opt->warnings = warn_take();
    else warn_reset();

    const char *asm_name = ar_printf("%s.s", basename_noext(path));
    int r = mei_assemble(text.p ? text.p : "", asm_name, out);
    if (r != 0) report_asm_error(text.p ? text.p : "", out->error, err, errlen);
    buf_free(&text);
    symtab_reset();
    ar_free_all();
    g_error_jmp = saved;
    return r;
}
