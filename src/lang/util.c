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

/* Warnings: collected during compilation, handed to the caller on success. */
static Buf g_warn;
static int g_nwarn;

void warn_at(Loc loc, const char *fmt, ...) {
    if (g_nwarn >= 50) return;
    g_nwarn++;
    if (g_warn.len) buf_putc(&g_warn, '\n');
    if (loc.file) buf_printf(&g_warn, "%s:%d:%d: warning: ", loc.file, loc.line, loc.col);
    else buf_puts(&g_warn, "warning: ");
    va_list ap;
    va_start(ap, fmt);
    buf_vprintf(&g_warn, fmt, ap);
    va_end(ap);
    if (loc.file) quote_line(&g_warn, loc);
}

void warn_reset(void) { buf_free(&g_warn); g_warn = (Buf){0}; g_nwarn = 0; }

char *warn_take(void) {
    if (!g_warn.len) { warn_reset(); return NULL; }
    char *r = malloc(g_warn.len + 1);
    memcpy(r, g_warn.p, g_warn.len);
    r[g_warn.len] = 0;
    warn_reset();
    return r;
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
/* `private` declarations: one table per file, searched before the layers */
typedef struct { const char *file; SymTab tab; } FileTab;
static FileTab *g_ftabs;
static int g_nftabs, g_capftabs;
typedef struct Import { const char *file, *alias; struct Import *next; } Import;
typedef struct { const char *file; SymTab tab; Import *imports; int isolated; } Module;
static Module *g_modules;
static int g_nmodules, g_capmodules;
static Sym *qualified_private(const char *name, const char *file);
static const char **g_stdfiles;
static int g_nstdfiles, g_capstdfiles;

static size_t hash_str(const char *s) {
    size_t h = 2166136261u;
    while (*s) h = (h ^ (unsigned char)*s++) * 16777619u;
    return h;
}

void symtab_reset(void) {
    for (int i = 0; i < 2; i++) { free(g_layers[i].tab); g_layers[i] = (SymTab){0}; }
    for (int i = 0; i < g_nftabs; i++) free(g_ftabs[i].tab.tab);
    free(g_ftabs);
    g_ftabs = NULL;
    g_nftabs = g_capftabs = 0;
    for (int i = 0; i < g_nmodules; i++) free(g_modules[i].tab.tab);
    free(g_modules); g_modules = NULL; g_nmodules = g_capmodules = 0;
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

static Sym *tab_lookup(SymTab *t, const char *name) {
    if (!t->cap) return NULL;
    for (size_t i = hash_str(name) & (t->cap - 1);; i = (i + 1) & (t->cap - 1)) {
        if (!t->tab[i]) return NULL;
        if (!strcmp(t->tab[i]->name, name)) return t->tab[i];
    }
}

Sym *sym_lookup_layer(const char *name, int layer) { return tab_lookup(&g_layers[layer], name); }

/* The private table of a file (its number, from 1, in *index), optionally created. */
static FileTab *file_tab(const char *file, int create) {
    if (!file) return NULL;
    for (int i = 0; i < g_nftabs; i++)
        if (g_ftabs[i].file == file || !strcmp(g_ftabs[i].file, file)) return &g_ftabs[i];
    if (!create) return NULL;
    if (g_nftabs == g_capftabs) {
        g_capftabs = g_capftabs ? g_capftabs * 2 : 16;
        g_ftabs = realloc(g_ftabs, sizeof *g_ftabs * (size_t)g_capftabs);
    }
    g_ftabs[g_nftabs] = (FileTab){file, {0}};
    return &g_ftabs[g_nftabs++];
}

Sym *sym_lookup_private(const char *name, const char *file) {
    FileTab *f = file_tab(file, 0);
    return f ? tab_lookup(&f->tab, name) : NULL;
}

/* A private symbol of some file other than `from_file` (for error messages). */
Sym *sym_private_elsewhere(const char *name, const char *from_file) {
    if (strchr(name, '.')) return qualified_private(name, from_file);
    for (int i = 0; i < g_nftabs; i++) {
        if (from_file && !strcmp(g_ftabs[i].file, from_file)) continue;
        Sym *s = tab_lookup(&g_ftabs[i].tab, name);
        if (s) return s;
    }
    return NULL;
}

Sym *sym_lookup(const char *name, const char *from_file) {
    if (strchr(name, '.')) return sym_lookup_qualified(name, from_file);
    Sym *p = sym_lookup_private(name, from_file);
    if (p) return p;
    if (file_is_module(from_file)) {
        p = sym_lookup_module(name, from_file, 0);
        return p ? p : sym_lookup_layer(name, 0);
    }
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

void sym_define_private(Sym *s, const char *file) {
    FileTab *f = file_tab(file, 1);
    s->priv = (int)(f - g_ftabs) + 1;
    define_in(&f->tab, s);
}

/* File modules retain their own public table even when a plain import also publishes
   those names to the legacy global layer. Import aliases belong to the importing file. */
static Module *module_get(const char *file) {
    if (!file) return NULL;
    for (int i = 0; i < g_nmodules; i++)
        if (!strcmp(g_modules[i].file, file)) return &g_modules[i];
    return NULL;
}
void module_begin(const char *file, int isolated) {
    if (module_get(file)) return;
    if (g_nmodules == g_capmodules) {
        g_capmodules = g_capmodules ? g_capmodules * 2 : 16;
        g_modules = realloc(g_modules, sizeof *g_modules * (size_t)g_capmodules);
    }
    g_modules[g_nmodules++] = (Module){.file=file, .isolated=isolated};
}
int file_is_module(const char *file) { Module *m = module_get(file); return m && m->isolated; }
static Sym *module_lookup_inner(const char *name, const char *file, int public_only,
                               const char **visited, int n) {
    Module *m = module_get(file);
    if (!m || n >= 256) return NULL;
    for (int i = 0; i < n; i++) if (!strcmp(visited[i], file)) return NULL;
    visited[n++] = file;
    Sym *s = tab_lookup(&m->tab, name);
    if (s || public_only) return s;
    Sym *found = NULL;
    for (Import *i = m->imports; i; i = i->next) if (!i->alias) {
        Sym *x = module_lookup_inner(name, i->file, 0, visited, n);
        if (x && found && x != found)
            error_at(x->loc, "ambiguous imported name '%s'; use named imports", name);
        if (x) found = x;
    }
    return found;
}
Sym *sym_lookup_module(const char *name, const char *file, int public_only) {
    const char *visited[256];
    return module_lookup_inner(name, file, public_only, visited, 0);
}
void sym_define_module(Sym *s, const char *file) {
    Module *m = module_get(file);
    if (!m) return;
    if (m->isolated) s->module = (int)(m - g_modules) + 1;
    if (!s->priv) define_in(&m->tab, s);
}
int module_has_alias(const char *file, const char *name) {
    Module *m = module_get(file);
    if (!m) return 0;
    for (Import *i = m->imports; i; i = i->next)
        if (i->alias && !strcmp(i->alias, name)) return 1;
    return 0;
}
void module_import(const char *from, const char *target, const char *alias, Loc loc) {
    Module *m = module_get(from);
    if (!m) return;
    for (Import *i = m->imports; i; i = i->next) {
        if (alias && i->alias && !strcmp(alias, i->alias)) {
            if (!strcmp(target, i->file)) return;
            error_at(loc, "import alias '%s' is already defined", alias);
        }
        if (!alias && !i->alias && !strcmp(target, i->file)) return;
    }
    if (alias && (sym_lookup_module(alias, from, 1) || sym_lookup_private(alias, from)))
        error_at(loc, "import alias '%s' conflicts with a declaration", alias);
    Import *i = ar_alloc(sizeof *i); i->file=target; i->alias=alias;
    i->next=m->imports; m->imports=i;
}
Sym *sym_lookup_qualified(const char *name, const char *file) {
    const char *dot = strchr(name, '.');
    if (!dot) return sym_lookup(name, file);
    const char *alias = ar_strndup(name, (size_t)(dot-name));
    Module *m = module_get(file);
    if (!m) return NULL;
    for (Import *i = m->imports; i; i = i->next) if (i->alias && !strcmp(i->alias, alias)) {
        Sym *s = sym_lookup_module(dot+1, i->file, 1);
        return s;
    }
    return NULL;
}
static Sym *qualified_private(const char *name, const char *file) {
    const char *dot = strchr(name, '.');
    Module *m = module_get(file);
    if (!dot || !m) return NULL;
    size_t n = (size_t)(dot - name);
    for (Import *i = m->imports; i; i = i->next)
        if (i->alias && strlen(i->alias) == n && !strncmp(i->alias, name, n))
            return sym_lookup_private(dot + 1, i->file);
    return NULL;
}
static void publish_drop_func(Program *P, Func *f) {
    for (int i = 0; i < P->nfuncs; i++) if (P->funcs[i] == f) {
        memmove(&P->funcs[i], &P->funcs[i + 1], sizeof(Func *) * (size_t)(P->nfuncs - i - 1));
        P->nfuncs--;
        return;
    }
}
void module_publish(const char *file, Program *P) {
    Module *m = module_get(file);
    if (!m || !m->isolated) return;
    m->isolated = 0;  /* also breaks plain-import cycles */
    for (size_t j = 0; j < m->tab.cap; j++) {
        Sym *s = m->tab.tab[j];
        if (!s) continue;
        Sym *old = sym_lookup_layer(s->name, s->user);
        if (old && old != s) {
            if (old->k == SY_FUNC && s->k == SY_FUNC && old->fn != s->fn &&
                old->fn->weak != s->fn->weak) {
                Func *strong = old->fn->weak ? s->fn : old->fn;
                Func *weak = old->fn->weak ? old->fn : s->fn;
                for (Func *w = strong->overrides; w; w = w->overrides)
                    if (file_is_stdlib(w->loc.file) == file_is_stdlib(weak->loc.file))
                        error_at(weak->loc, "'%s' already has a weak definition at %s:%d (only one weak default is allowed)",
                                 s->name, w->loc.file, w->loc.line);
                weak->overrides = strong->overrides;
                strong->overrides = weak;
                publish_drop_func(P, weak);
                old->fn = s->fn = strong;
            } else if (!(old->k == SY_FUNC && s->k == SY_FUNC && old->fn == s->fn)) {
                error_at(s->loc, "'%s' is already defined at %s:%d", s->name,
                         old->loc.file ? old->loc.file : "<built-in>", old->loc.line);
            }
        }
        if (!old) sym_define_global(s);
    }
    for (Import *i = m->imports; i; i = i->next) if (!i->alias) module_publish(i->file, P);
}
