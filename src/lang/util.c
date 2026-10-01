/* Arena allocation, string buffers, error reporting and the global symbol table. */
#include "internal.h"

#include <setjmp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ---- arena ---- */

typedef struct Chunk { struct Chunk *next; size_t used, cap; max_align_t data[]; } Chunk;
static Chunk *g_chunks;

void *ar_alloc(size_t n) {
    n = (n + 15) & ~(size_t)15;
    if (!g_chunks || g_chunks->used + n > g_chunks->cap) {
        size_t cap = n > 65536 ? n : 65536;
        Chunk *c = malloc(sizeof(Chunk) + cap);
        if (!c) { fprintf(stderr, "meic: out of memory\n"); exit(1); }
        c->next = g_chunks; c->used = 0; c->cap = cap;
        g_chunks = c;
    }
    void *p = (char *)g_chunks->data + g_chunks->used;
    g_chunks->used += n;
    memset(p, 0, n);
    return p;
}

char *ar_strndup(const char *s, size_t n) {
    char *p = ar_alloc(n + 1);
    memcpy(p, s, n);
    p[n] = 0;
    return p;
}

char *ar_strdup(const char *s) { return ar_strndup(s, strlen(s)); }

char *ar_printf(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    char tmp[512];
    int n = vsnprintf(tmp, sizeof tmp, fmt, ap);
    va_end(ap);
    if (n < (int)sizeof tmp) return ar_strdup(tmp);
    char *p = ar_alloc((size_t)n + 1);
    va_start(ap, fmt);
    vsnprintf(p, (size_t)n + 1, fmt, ap);
    va_end(ap);
    return p;
}

void ar_free_all(void) {
    while (g_chunks) { Chunk *n = g_chunks->next; free(g_chunks); g_chunks = n; }
}

/* ---- buffers ---- */

static void buf_grow(Buf *b, size_t extra) {
    if (b->len + extra + 1 <= b->cap) return;
    size_t cap = b->cap ? b->cap * 2 : 256;
    while (cap < b->len + extra + 1) cap *= 2;
    b->p = realloc(b->p, cap);
    if (!b->p) { fprintf(stderr, "meic: out of memory\n"); exit(1); }
    b->cap = cap;
}

void buf_putn(Buf *b, const char *s, size_t n) {
    buf_grow(b, n);
    memcpy(b->p + b->len, s, n);
    b->len += n;
    b->p[b->len] = 0;
}
void buf_putc(Buf *b, char c) { buf_putn(b, &c, 1); }
void buf_puts(Buf *b, const char *s) { buf_putn(b, s, strlen(s)); }

void buf_vprintf(Buf *b, const char *fmt, va_list ap) {
    va_list ap2;
    va_copy(ap2, ap);
    int n = vsnprintf(NULL, 0, fmt, ap2);
    va_end(ap2);
    buf_grow(b, (size_t)n);
    vsnprintf(b->p + b->len, (size_t)n + 1, fmt, ap);
    b->len += (size_t)n;
}

void buf_printf(Buf *b, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    buf_vprintf(b, fmt, ap);
    va_end(ap);
}

void buf_free(Buf *b) { free(b->p); b->p = NULL; b->len = b->cap = 0; }

/* ---- sources and errors ---- */

static SrcFile *g_srcs;
static char *g_errbuf;
static size_t g_errlen;
void *g_error_jmp;

SrcFile *src_register(const char *path, const char *text, size_t len) {
    SrcFile *f = ar_alloc(sizeof *f);
    f->path = path; f->text = text; f->len = len;
    f->next = g_srcs; g_srcs = f;
    return f;
}

void error_reset(char *buf, size_t len) { g_errbuf = buf; g_errlen = len; g_srcs = NULL; }

static void quote_line(Buf *b, Loc loc) {
    for (SrcFile *f = g_srcs; f; f = f->next) {
        if (f->path != loc.file && strcmp(f->path, loc.file)) continue;
        const char *p = f->text, *end = f->text + f->len;
        for (int line = 1; line < loc.line && p < end; p++) if (*p == '\n') line++;
        const char *e = p;
        while (e < end && *e != '\n' && *e != '\r') e++;
        if (e - p > 200) return;
        buf_puts(b, "\n    ");
        buf_putn(b, p, (size_t)(e - p));
        buf_puts(b, "\n    ");
        for (int i = 1; i < loc.col && p + i - 1 < e; i++) buf_putc(b, p[i - 1] == '\t' ? '\t' : ' ');
        buf_putc(b, '^');
        return;
    }
}

_Noreturn static void error_finish(Buf *b) {
    if (g_errbuf && g_errlen) {
        size_t n = b->len < g_errlen - 1 ? b->len : g_errlen - 1;
        memcpy(g_errbuf, b->p, n);
        g_errbuf[n] = 0;
    }
    buf_free(b);
    longjmp(*(jmp_buf *)g_error_jmp, 1);
}

_Noreturn void error_at(Loc loc, const char *fmt, ...) {
    Buf b = {0};
    if (loc.file) buf_printf(&b, "%s:%d:%d: error: ", loc.file, loc.line, loc.col);
    else buf_puts(&b, "error: ");
    va_list ap;
    va_start(ap, fmt);
    buf_vprintf(&b, fmt, ap);
    va_end(ap);
    if (loc.file) quote_line(&b, loc);
    error_finish(&b);
}

_Noreturn void error_plain(const char *fmt, ...) {
    Buf b = {0};
    va_list ap;
    va_start(ap, fmt);
    buf_vprintf(&b, fmt, ap);
    va_end(ap);
    error_finish(&b);
}

/* ---- global symbol tables (open addressing) ----
 * Layer 0 holds the built-in names and the standard library, layer 1 the cart's own
 * declarations. Cart code sees layer 1 first, so a cart may reuse a library name;
 * library code always binds to the library. */

typedef struct { Sym **tab; size_t cap, n; } SymTab;
static SymTab g_layers[2];
static const char **g_stdfiles;
static int g_nstdfiles, g_capstdfiles;

static size_t hash_str(const char *s) {
    size_t h = 2166136261u;
    while (*s) h = (h ^ (unsigned char)*s++) * 16777619u;
    return h;
}

void symtab_reset(void) {
    for (int i = 0; i < 2; i++) { free(g_layers[i].tab); g_layers[i] = (SymTab){0}; }
    g_stdfiles = NULL;
    g_nstdfiles = g_capstdfiles = 0;
}

void mark_stdlib_file(const char *path) {
    if (g_nstdfiles == g_capstdfiles) {
        int nc = g_capstdfiles ? g_capstdfiles * 2 : 16;
        const char **n = ar_alloc(sizeof(char *) * (size_t)nc);
        if (g_nstdfiles) memcpy(n, g_stdfiles, sizeof(char *) * (size_t)g_nstdfiles);
        g_stdfiles = n;
        g_capstdfiles = nc;
    }
    g_stdfiles[g_nstdfiles++] = path;
}

int file_is_stdlib(const char *path) {
    if (!path) return 1;
    for (int i = 0; i < g_nstdfiles; i++) if (g_stdfiles[i] == path || !strcmp(g_stdfiles[i], path)) return 1;
    return 0;
}

Sym *sym_lookup_layer(const char *name, int layer) {
    SymTab *t = &g_layers[layer];
    if (!t->cap) return NULL;
    for (size_t i = hash_str(name) & (t->cap - 1);; i = (i + 1) & (t->cap - 1)) {
        if (!t->tab[i]) return NULL;
        if (!strcmp(t->tab[i]->name, name)) return t->tab[i];
    }
}

Sym *sym_lookup(const char *name, const char *from_file) {
    if (file_is_stdlib(from_file)) return sym_lookup_layer(name, 0);
    Sym *s = sym_lookup_layer(name, 1);
    return s ? s : sym_lookup_layer(name, 0);
}

Sym *sym_lookup_global(const char *name) {
    Sym *s = sym_lookup_layer(name, 1);
    return s ? s : sym_lookup_layer(name, 0);
}

static void define_in(SymTab *t, Sym *s) {
    if ((t->n + 1) * 2 > t->cap) {
        size_t oc = t->cap;
        Sym **old = t->tab;
        t->cap = oc ? oc * 2 : 256;
        t->tab = calloc(t->cap, sizeof *t->tab);
        t->n = 0;
        for (size_t i = 0; i < oc; i++) if (old[i]) define_in(t, old[i]);
        free(old);
    }
    size_t i = hash_str(s->name) & (t->cap - 1);
    while (t->tab[i]) i = (i + 1) & (t->cap - 1);
    t->tab[i] = s;
    t->n++;
}

void sym_define_global(Sym *s) { define_in(&g_layers[s->user ? 1 : 0], s); }
