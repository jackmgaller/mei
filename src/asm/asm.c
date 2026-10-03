/* Mei assembler: two passes over the source, driven by the opcode table in isa.c.
 * Syntax reference: docs/ASSEMBLY.md. Errors abort via longjmp with "file:line: message". */
#include "asm.h"
#include "isa.h"
#include "mei.h"

#include <ctype.h>
#include <setjmp.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ROM_START   MEI_ROM_BASE
#define ROM_MAX     MEI_ROM_MAX
#define RAM_START   MEI_RAM_USER_BASE
#define RAM_END     MEI_RAM_SIZE   /* RAM starts at 0 */
#define MAX_LINE    4096
#define NAME_MAX_   256
#define MAX_DEPTH   16

enum { SEC_ROM, SEC_RAM };

typedef struct { char *name; int64_t value; int known, defpass; } Sym;
typedef struct { char *path; char *data; size_t len; } FileBuf;
typedef struct { char *s; size_t len, cap; } Str;

typedef struct {
    jmp_buf jb;
    char err[512];
    int pass;
    Sym *syms; size_t nsyms, capsyms;
    uint32_t *tab; size_t tabcap;  /* open addressing; slot = symbol index + 1, 0 = empty */
    FileBuf *files; size_t nfiles;
    uint8_t *rom;                  /* image buffer of rom_cap bytes, sized after pass 1 */
    uint32_t rom_cap;
    uint32_t loc[2];               /* location counters */
    int sec;
    uint32_t rom_end;              /* one past the highest ROM byte written */
    int rom_touched;
    char scope[NAME_MAX_];         /* last global label, for .local labels */
    uint8_t *lisz; size_t nlisz, caplisz, liidx;  /* li sizes chosen in pass 1 */
    const char *file; int line, depth;
    int listing, insn;
    const MeiAsmBlob *blobs; size_t nblobs, blob_last;   /* in-memory .incbin files */
    uint32_t emit_start, emit_n;   /* bytes emitted by the current statement */
    Str list;
} Asm;

static _Noreturn void fail(Asm *a, const char *fmt, ...) {
    int n = snprintf(a->err, sizeof a->err, "%s:%d: ", a->file ? a->file : "<input>", a->line);
    if (n < 0 || n >= (int)sizeof a->err) n = 0;
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(a->err + n, sizeof a->err - n, fmt, ap);
    va_end(ap);
    longjmp(a->jb, 1);
}

static void *xrealloc(Asm *a, void *p, size_t n) {
    void *q = realloc(p, n ? n : 1);
    if (!q) fail(a, "out of memory");
    return q;
}

static char *xstrdup(Asm *a, const char *s) {
    size_t n = strlen(s) + 1;
    return memcpy(xrealloc(a, NULL, n), s, n);
}

static void sb_printf(Asm *a, Str *b, const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(NULL, 0, fmt, ap);
    va_end(ap);
    if (b->len + n + 1 > b->cap) {
        b->cap = (b->len + n + 1) * 2;
        b->s = xrealloc(a, b->s, b->cap);
    }
    va_start(ap, fmt);
    vsnprintf(b->s + b->len, n + 1, fmt, ap);
    va_end(ap);
    b->len += n;
}

/* ---- symbols ---- */

static uint32_t hash(const char *s) {
    uint32_t h = 2166136261u;
    while (*s) h = (h ^ (unsigned char)*s++) * 16777619u;
    return h;
}

static Sym *sym_find(Asm *a, const char *name) {
    if (!a->tabcap) return NULL;
    for (size_t i = hash(name) & (a->tabcap - 1);; i = (i + 1) & (a->tabcap - 1)) {
        if (!a->tab[i]) return NULL;
        Sym *s = &a->syms[a->tab[i] - 1];
        if (!strcmp(s->name, name)) return s;
    }
}

static Sym *sym_get(Asm *a, const char *name) {
    Sym *s = sym_find(a, name);
    if (s) return s;
    if ((a->nsyms + 1) * 2 > a->tabcap) {
        size_t cap = a->tabcap ? a->tabcap * 2 : 256;
        uint32_t *t = calloc(cap, sizeof *t);
        if (!t) fail(a, "out of memory");
        for (size_t k = 0; k < a->nsyms; k++) {
            size_t i = hash(a->syms[k].name) & (cap - 1);
            while (t[i]) i = (i + 1) & (cap - 1);
            t[i] = (uint32_t)k + 1;
        }
        free(a->tab);
        a->tab = t, a->tabcap = cap;
    }
    if (a->nsyms == a->capsyms) {
        a->capsyms = a->capsyms ? a->capsyms * 2 : 128;
        a->syms = xrealloc(a, a->syms, a->capsyms * sizeof *a->syms);
    }
    s = &a->syms[a->nsyms++];
    *s = (Sym){xstrdup(a, name), 0, 0, 0};
    size_t i = hash(name) & (a->tabcap - 1);
    while (a->tab[i]) i = (i + 1) & (a->tabcap - 1);
    a->tab[i] = (uint32_t)a->nsyms;
    return s;
}

/* ---- lexing helpers ---- */

static void ws(const char **p) { while (**p == ' ' || **p == '\t' || **p == '\r' || **p == '\f') (*p)++; }
static int is_id0(int c) { return isalpha(c) || c == '_' || c == '.'; }
static int is_id(int c) { return isalnum(c) || c == '_' || c == '.' || c == '$'; }

static int read_ident(Asm *a, const char **p, char *out) {
    const char *s = *p;
    if (!is_id0((unsigned char)*s)) return 0;
    size_t n = 0;
    while (is_id((unsigned char)s[n])) n++;
    if (n >= NAME_MAX_) fail(a, "name too long");
    memcpy(out, s, n);
    out[n] = 0;
    *p = s + n;
    return 1;
}

/* Register number for "r0".."r15"/"sp"/"ra" (kind 'r') or "v0".. (kind 'v'), any number;
 * -1 if the name is not register-shaped. Case-insensitive. */
static int reg_index(const char *id, char kind) {
    char l[4];
    size_t n = strlen(id);
    if (n < 2 || n > 3) return -1;
    for (size_t i = 0; i <= n; i++) l[i] = (char)tolower((unsigned char)id[i]);
    if (kind == 'r' && !strcmp(l, "sp")) return 14;
    if (kind == 'r' && !strcmp(l, "ra")) return 15;
    if (l[0] != kind || !isdigit((unsigned char)l[1]) || (l[2] && !isdigit((unsigned char)l[2]))) return -1;
    if (l[1] == '0' && l[2]) return -1;
    return atoi(l + 1);
}

static int is_reg_name(const char *id) { return reg_index(id, 'r') >= 0 || reg_index(id, 'v') >= 0; }

static void qualify(Asm *a, const char *id, char *out) {
    if (id[0] == '.' && id[1]) {
        if (!a->scope[0]) fail(a, "local label '%s' has no preceding global label", id);
        if (strlen(a->scope) + strlen(id) >= NAME_MAX_) fail(a, "name too long");
        snprintf(out, NAME_MAX_, "%s%s", a->scope, id);
    } else {
        snprintf(out, NAME_MAX_, "%s", id);
    }
}

static void comma(Asm *a, const char **p) {
    ws(p);
    if (**p != ',') fail(a, "expected ','");
    (*p)++;
}

static int at_end(const char **p) { ws(p); return **p == 0; }

static int parse_escape(Asm *a, const char **p) {
    (*p)++;  /* backslash */
    int c = (unsigned char)*(*p)++;
    switch (c) {
    case 'n': return '\n';
    case 't': return '\t';
    case 'r': return '\r';
    case 'a': return 7;
    case 'b': return 8;
    case 'f': return 12;
    case 'v': return 11;
    case 'e': return 27;
    case '\\': case '\'': case '"': case '?': return c;
    case 'x': {
        int v = 0, n = 0;
        while (n < 2 && isxdigit((unsigned char)**p)) {
            int d = *(*p)++;
            v = v * 16 + (isdigit(d) ? d - '0' : tolower(d) - 'a' + 10);
            n++;
        }
        if (!n) fail(a, "bad \\x escape");
        return v;
    }
    default:
        if (c >= '0' && c <= '7') {
            int v = c - '0', n = 1;
            while (n < 3 && **p >= '0' && **p <= '7') v = v * 8 + (*(*p)++ - '0'), n++;
            if (v > 255) fail(a, "octal escape out of range");
            return v;
        }
        fail(a, "unknown escape '\\%c'", c ? c : '0');
    }
}

static size_t parse_string(Asm *a, const char **p, char *out, size_t cap) {
    ws(p);
    if (**p != '"') fail(a, "expected a string");
    (*p)++;
    size_t n = 0;
    while (**p != '"') {
        if (!**p) fail(a, "unterminated string");
        int c = **p == '\\' ? parse_escape(a, p) : (unsigned char)*(*p)++;
        if (n >= cap) fail(a, "string too long");
        out[n++] = (char)c;
    }
    (*p)++;
    return n;
}

/* ---- expressions ---- */

static int64_t ebin(Asm *a, const char **p, int *ok, int minprec);

static int64_t parse_number(Asm *a, const char **p) {
    const char *s = *p;
    uint64_t v = 0;
    int64_t result;
    if (s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) {
        s += 2;
        if (!isxdigit((unsigned char)*s)) fail(a, "bad hex number");
        for (; isxdigit((unsigned char)*s) || *s == '_'; s++) {
            if (*s == '_') continue;
            v = v * 16 + (isdigit((unsigned char)*s) ? *s - '0' : tolower((unsigned char)*s) - 'a' + 10);
            if (v > 0xFFFFFFFFu) fail(a, "number too large");
        }
        result = (int64_t)v;
    } else if (s[0] == '0' && (s[1] == 'b' || s[1] == 'B')) {
        s += 2;
        if (*s != '0' && *s != '1') fail(a, "bad binary number");
        for (; *s == '0' || *s == '1' || *s == '_'; s++) {
            if (*s == '_') continue;
            v = v * 2 + (uint64_t)(*s - '0');
            if (v > 0xFFFFFFFFu) fail(a, "number too large");
        }
        result = (int64_t)v;
    } else {
        for (; isdigit((unsigned char)*s); s++) {
            v = v * 10 + (uint64_t)(*s - '0');
            if (v > 0xFFFFFFFFu) fail(a, "number too large");
        }
        result = (int64_t)v;
        if (*s == '.' && isdigit((unsigned char)s[1])) {  /* fixed-point literal -> 16.16 */
            s++;
            uint64_t num = 0, den = 1;
            for (; isdigit((unsigned char)*s); s++)
                if (den < 1000000000000ull) num = num * 10 + (uint64_t)(*s - '0'), den *= 10;
            result = (int64_t)(v << 16) + (int64_t)((num * 65536 + den / 2) / den);
        }
    }
    if (is_id((unsigned char)*s)) fail(a, "bad number");
    *p = s;
    return result;
}

static int64_t eunary(Asm *a, const char **p, int *ok) {
    ws(p);
    char c = **p;
    if (c == '-') { (*p)++; return (int64_t)(0 - (uint64_t)eunary(a, p, ok)); }
    if (c == '~') { (*p)++; return ~eunary(a, p, ok); }
    if (c == '+') { (*p)++; return eunary(a, p, ok); }
    if (c == '(') {
        (*p)++;
        int64_t v = ebin(a, p, ok, 1);
        ws(p);
        if (**p != ')') fail(a, "expected ')'");
        (*p)++;
        return v;
    }
    if (c == '\'') {
        (*p)++;
        if (**p == '\'' || !**p) fail(a, "bad character literal");
        int v = **p == '\\' ? parse_escape(a, p) : (unsigned char)*(*p)++;
        if (**p != '\'') fail(a, "bad character literal");
        (*p)++;
        return v;
    }
    if (isdigit((unsigned char)c)) return parse_number(a, p);
    char id[NAME_MAX_], name[NAME_MAX_];
    if (!read_ident(a, p, id)) {
        if (!**p) fail(a, "expected an expression");
        fail(a, "expected an expression at '%.20s'", *p);
    }
    if (!strcmp(id, ".")) return a->loc[a->sec];
    ws(p);
    if (**p == '(' && (!strcmp(id, "hi") || !strcmp(id, "lo"))) {
        int64_t v = eunary(a, p, ok);
        return id[0] == 'h' ? (int64_t)((uint32_t)v >> 10) : (v & 0x3FF);
    }
    if (is_reg_name(id)) fail(a, "register '%s' not allowed in an expression", id);
    qualify(a, id, name);
    Sym *s = sym_find(a, name);
    if (s && s->known) return s->value;
    if (a->pass == 1) { *ok = 0; return 0; }
    if (s) fail(a, "symbol '%s' is used before its value can be resolved", name);
    fail(a, "undefined symbol '%s'", name);
}

static int binop(const char *p, int *prec, int *len) {
    *len = 1;
    switch (p[0]) {
    case '*': case '/': case '%': *prec = 6; return p[0];
    case '+': case '-': *prec = 5; return p[0];
    case '<': if (p[1] != '<') return 0; *prec = 4, *len = 2; return '<';
    case '>': if (p[1] != '>') return 0; *prec = 4, *len = 2; return '>';
    case '&': *prec = 3; return '&';
    case '^': *prec = 2; return '^';
    case '|': *prec = 1; return '|';
    }
    return 0;
}

static int64_t ebin(Asm *a, const char **p, int *ok, int minprec) {
    int64_t l = eunary(a, p, ok);
    for (;;) {
        ws(p);
        int prec, len, op = binop(*p, &prec, &len);
        if (!op || prec < minprec) return l;
        *p += len;
        int64_t r = ebin(a, p, ok, prec + 1);
        uint64_t ul = (uint64_t)l, ur = (uint64_t)r;
        switch (op) {
        case '*': l = (int64_t)(ul * ur); break;
        case '+': l = (int64_t)(ul + ur); break;
        case '-': l = (int64_t)(ul - ur); break;
        case '&': l &= r; break;
        case '^': l ^= r; break;
        case '|': l |= r; break;
        case '/': case '%':
            if (r == 0) { if (*ok) fail(a, "division by zero"); l = 0; break; }
            if (r == -1) l = op == '/' ? (int64_t)(0 - ul) : 0;
            else l = op == '/' ? l / r : l % r;
            break;
        case '<': case '>':
            if (r < 0 || r > 63) { if (*ok) fail(a, "shift count %lld out of range", (long long)r); l = 0; break; }
            l = op == '<' ? (int64_t)(ul << r) : l >> r;
            break;
        }
    }
}

static int64_t expr(Asm *a, const char **p, int *ok) {
    *ok = 1;
    return ebin(a, p, ok, 1);
}

/* An expression whose value must be known in pass 1 (sizes and locations depend on it). */
static int64_t expr_now(Asm *a, const char **p, const char *what) {
    int ok;
    int64_t v = expr(a, p, &ok);
    if (!ok) fail(a, "%s must not depend on symbols defined later", what);
    return v;
}

static int64_t check(Asm *a, int64_t v, int ok, int64_t lo, int64_t hi, const char *what) {
    if (ok && (v < lo || v > hi))
        fail(a, "%s %lld out of range (%lld..%lld)", what, (long long)v, (long long)lo, (long long)hi);
    return ok ? v : 0;
}

/* Real-number expressions for .fixed: literals, + - * / and parentheses, evaluated in double. */
static double rbin(Asm *a, const char **p, int minprec);
static double runary(Asm *a, const char **p) {
    ws(p);
    char c = **p;
    if (c == '-') { (*p)++; return -runary(a, p); }
    if (c == '+') { (*p)++; return runary(a, p); }
    if (c == '(') {
        (*p)++;
        double v = rbin(a, p, 1);
        ws(p);
        if (**p != ')') fail(a, "expected ')'");
        (*p)++;
        return v;
    }
    if (!isdigit((unsigned char)c) && c != '.') fail(a, ".fixed takes numbers and + - * / only (use .word for symbols)");
    char *end;
    double v = strtod(*p, &end);
    if (end == *p || is_id((unsigned char)*end)) fail(a, "bad number");
    *p = end;
    return v;
}
static double rbin(Asm *a, const char **p, int minprec) {
    double l = runary(a, p);
    for (;;) {
        ws(p);
        int prec, len, op = binop(*p, &prec, &len);
        if (!op || prec < minprec) return l;
        if (prec != 5 && prec != 6) fail(a, ".fixed takes numbers and + - * / only");
        *p += len;
        double r = rbin(a, p, prec + 1);
        if (op == '+') l += r;
        else if (op == '-') l -= r;
        else if (op == '*') l *= r;
        else if (op == '/') { if (r == 0) fail(a, "division by zero"); l /= r; }
        else fail(a, ".fixed takes numbers and + - * / only");
    }
}

/* ---- emission ---- */

static void need_rom(Asm *a, const char *what) {
    if (a->sec != SEC_ROM) fail(a, "%s not allowed in the ram section (it holds no initialised data)", what);
}

static void emit_byte(Asm *a, uint8_t b) {
    uint32_t l = a->loc[SEC_ROM];
    if (l >= ROM_START + ROM_MAX) fail(a, "ROM is full (%u MB)", ROM_MAX >> 20);
    if (a->pass == 2) {
        if (l - ROM_START >= a->rom_cap) fail(a, "internal error: ROM grew between passes");
        a->rom[l - ROM_START] = b;
    }
    if (!a->emit_n++) a->emit_start = l;
    a->loc[SEC_ROM] = ++l;
    if (l > a->rom_end) a->rom_end = l;
    a->rom_touched = 1;
}

/* n bytes at once (.incbin): the same as n emit_byte calls, without the per-byte work. */
static void emit_block(Asm *a, const uint8_t *p, uint32_t n) {
    uint32_t l = a->loc[SEC_ROM];
    if (!n) return;
    if (n > ROM_START + ROM_MAX - l) fail(a, "ROM is full (%u MB)", ROM_MAX >> 20);
    if (a->pass == 2) {
        if (l - ROM_START + n > a->rom_cap) fail(a, "internal error: ROM grew between passes");
        memcpy(a->rom + (l - ROM_START), p, n);
    }
    if (!a->emit_n) a->emit_start = l;
    a->emit_n += n;
    a->loc[SEC_ROM] = l += n;
    if (l > a->rom_end) a->rom_end = l;
    a->rom_touched = 1;
}

static void emit_le(Asm *a, uint32_t v, int n) {
    for (int i = 0; i < n; i++) emit_byte(a, (uint8_t)(v >> (8 * i)));
}

static void emit_insn(Asm *a, uint32_t w) {
    need_rom(a, "instructions");
    if (a->loc[SEC_ROM] & 3) fail(a, "instruction at misaligned address 0x%06X (use .align 4)", a->loc[SEC_ROM]);
    a->insn = 1;
    emit_le(a, w, 4);
}

/* ---- operands ---- */

static int sreg(Asm *a, const char **p) {
    char id[NAME_MAX_];
    ws(p);
    if (!read_ident(a, p, id)) fail(a, "expected a scalar register");
    int r = reg_index(id, 'r');
    if (r < 0 || r > 15) fail(a, "bad scalar register '%s' (r0-r15, sp, ra)", id);
    return r;
}

static int vreg(Asm *a, const char **p) {
    char id[NAME_MAX_];
    ws(p);
    if (!read_ident(a, p, id)) fail(a, "expected a vector register");
    int r = reg_index(id, 'v');
    if (r < 0 || r > 7) fail(a, "bad vector register '%s' (v0-v7)", id);
    return r;
}

/* [rB], [rB+expr], [rB-expr], [expr] -> base register and sign-extended 18-bit offset. */
static uint32_t mem_operand(Asm *a, const char **p, int *base) {
    ws(p);
    if (**p != '[') fail(a, "expected a memory operand like [r1+8]");
    (*p)++;
    ws(p);
    const char *save = *p;
    char id[NAME_MAX_];
    int ok = 1, r;
    int64_t off = 0;
    if (read_ident(a, p, id) && (r = reg_index(id, 'r')) >= 0) {
        if (r > 15) fail(a, "bad scalar register '%s' (r0-r15, sp, ra)", id);
        *base = r;
        ws(p);
        if (**p == '+' || **p == '-') off = expr(a, p, &ok);
    } else {
        *p = save;
        *base = 0;
        off = expr(a, p, &ok);
    }
    ws(p);
    if (**p != ']') fail(a, "expected ']'");
    (*p)++;
    return (uint32_t)check(a, off, ok, MEI_IMM_MIN, MEI_IMM_MAX, *base ? "memory offset" : "absolute address");
}

static uint32_t branch_imm(Asm *a, const char **p) {
    int ok;
    int64_t t = expr(a, p, &ok);
    if (!ok) return 0;
    if (t < -0x80000000ll || t > 0xFFFFFFFFll) fail(a, "branch target out of range");
    if (t & 3) fail(a, "branch target 0x%llX is not word-aligned", (long long)t);
    int32_t diff = (int32_t)((uint32_t)t - (a->loc[SEC_ROM] + 4));
    int32_t off = diff / 4;
    if (off < MEI_IMM_MIN || off > MEI_IMM_MAX) fail(a, "branch target 0x%llX out of range (%d words away)", (long long)t, off);
    return (uint32_t)off & 0x3FFFF;
}

static uint32_t jump_imm(Asm *a, const char **p) {
    int ok;
    int64_t t = expr(a, p, &ok);
    if (!ok) return 0;
    if (t < 0 || t >= (1ll << 28)) fail(a, "jump target 0x%llX out of range", (long long)t);
    if (t & 3) fail(a, "jump target 0x%llX is not word-aligned", (long long)t);
    return (uint32_t)(t >> 2);
}

static uint32_t encode(Asm *a, int op, const char **p) {
    int ra, rb, rc, ok;
    int64_t v;
    switch (mei_ops[op].shape) {
    case SHAPE_NONE:
        if (at_end(p)) return MEI_ENC_J(op, 0);
        v = expr(a, p, &ok);
        return MEI_ENC_J(op, check(a, v, ok, 0, 0x3FFFFFF, "code"));
    case SHAPE_SSS:
        ra = sreg(a, p), comma(a, p), rb = sreg(a, p), comma(a, p), rc = sreg(a, p);
        return MEI_ENC_R(op, ra, rb, rc);
    case SHAPE_SSI:
        ra = sreg(a, p), comma(a, p), rb = sreg(a, p), comma(a, p);
        v = expr(a, p, &ok);
        if (op == OP_ANDI || op == OP_ORI || op == OP_XORI) v = check(a, v, ok, 0, MEI_UIMM_MAX, "unsigned immediate");
        else if (op >= OP_SHLI && op <= OP_SARI) v = check(a, v, ok, 0, 31, "shift amount");
        else v = check(a, v, ok, MEI_IMM_MIN, MEI_IMM_MAX, "immediate");
        return MEI_ENC_I(op, ra, rb, v);
    case SHAPE_SU:
        ra = sreg(a, p), comma(a, p);
        v = expr(a, p, &ok);
        return MEI_ENC_U(op, ra, check(a, v, ok, -0x200000, 0x3FFFFF, "lui immediate"));
    case SHAPE_SMEM:
        ra = sreg(a, p), comma(a, p);
        v = mem_operand(a, p, &rb);
        return MEI_ENC_I(op, ra, rb, v);
    case SHAPE_BRANCH:
        ra = sreg(a, p), comma(a, p), rb = sreg(a, p), comma(a, p);
        return MEI_ENC_I(op, ra, rb, branch_imm(a, p));
    case SHAPE_JUMP:
        return MEI_ENC_J(op, jump_imm(a, p));
    case SHAPE_JREG:
        return MEI_ENC_I(op, 0, sreg(a, p), 0);
    case SHAPE_VMEM:
        ra = vreg(a, p), comma(a, p);
        v = mem_operand(a, p, &rb);
        return MEI_ENC_I(op, ra, rb, v);
    case SHAPE_VV:
        ra = vreg(a, p), comma(a, p), rb = vreg(a, p);
        return MEI_ENC_R(op, ra, rb, 0);
    case SHAPE_SVLANE:
    case SHAPE_VSLANE:
        if (mei_ops[op].shape == SHAPE_SVLANE) ra = sreg(a, p), comma(a, p), rb = vreg(a, p);
        else ra = vreg(a, p), comma(a, p), rb = sreg(a, p);
        comma(a, p);
        v = expr(a, p, &ok);
        return MEI_ENC_I(op, ra, rb, check(a, v, ok, 0, 3, "lane"));
    case SHAPE_VVV:
        ra = vreg(a, p), comma(a, p), rb = vreg(a, p), comma(a, p), rc = vreg(a, p);
        return MEI_ENC_R(op, ra, rb, rc);
    case SHAPE_VVS:
        ra = vreg(a, p), comma(a, p), rb = vreg(a, p), comma(a, p), rc = sreg(a, p);
        return MEI_ENC_R(op, ra, rb, rc);
    case SHAPE_SVV:
        ra = sreg(a, p), comma(a, p), rb = vreg(a, p), comma(a, p), rc = vreg(a, p);
        return MEI_ENC_R(op, ra, rb, rc);
    case SHAPE_VV3:
        ra = vreg(a, p), comma(a, p), rb = vreg(a, p);
        if (ra > 5 || rb > 5) fail(a, "%s uses three consecutive registers: v0-v5 only", mei_ops[op].mnemonic);
        return MEI_ENC_R(op, ra, rb, 0);
    }
    fail(a, "internal error: bad shape");
}

static int find_op(const char *mn) {
    for (int i = 0; i < 64; i++)
        if (mei_ops[i].mnemonic && !strcmp(mei_ops[i].mnemonic, mn)) return i;
    return -1;
}

/* Loads a 32-bit constant as lui + ori. */
static void emit_lui_ori(Asm *a, int r, int64_t v) {
    uint32_t u = (uint32_t)v;
    emit_insn(a, MEI_ENC_U(OP_LUI, r, u >> 10));
    emit_insn(a, MEI_ENC_I(OP_ORI, r, r, u & 0x3FF));
}

static void instruction(Asm *a, const char *mn, const char **p) {
    int op = find_op(mn), ra, rb, ok;
    int64_t v;
    if (op >= 0) {
        need_rom(a, "instructions");
        emit_insn(a, encode(a, op, p));
        return;
    }
    if (!strcmp(mn, "nop")) {
        emit_insn(a, MEI_ENC_R(OP_ADD, 0, 0, 0));
    } else if (!strcmp(mn, "mov")) {
        ra = sreg(a, p), comma(a, p), rb = sreg(a, p);
        emit_insn(a, MEI_ENC_R(OP_ADD, ra, rb, 0));
    } else if (!strcmp(mn, "ret")) {
        emit_insn(a, MEI_ENC_I(OP_JR, 0, 15, 0));
    } else if (!strcmp(mn, "li") || !strcmp(mn, "la")) {
        ra = sreg(a, p), comma(a, p);
        v = expr(a, p, &ok);
        check(a, v, ok, -0x80000000ll, 0xFFFFFFFFll, "constant");
        int32_t s = (int32_t)(uint32_t)v;
        int words = 2;
        if (mn[1] == 'i') {
            if (a->pass == 1) {
                words = ok && s >= MEI_IMM_MIN && s <= MEI_IMM_MAX ? 1 : 2;
                if (a->nlisz == a->caplisz)
                    a->lisz = xrealloc(a, a->lisz, a->caplisz = a->caplisz ? a->caplisz * 2 : 64);
                a->lisz[a->nlisz++] = (uint8_t)words;
            } else {
                if (a->liidx >= a->nlisz) fail(a, "internal error: li phase mismatch");
                words = a->lisz[a->liidx++];
            }
        }
        if (words == 1) {
            if (s < MEI_IMM_MIN || s > MEI_IMM_MAX) fail(a, "internal error: li size changed between passes");
            emit_insn(a, MEI_ENC_I(OP_ADDI, ra, 0, s));
        } else {
            emit_lui_ori(a, ra, v);
        }
    } else if (!strcmp(mn, "bgt") || !strcmp(mn, "ble") || !strcmp(mn, "bgtu") || !strcmp(mn, "bleu")) {
        static const int swapped[] = {OP_BLT, OP_BGE, OP_BLTU, OP_BGEU};
        int k = (mn[1] == 'l') + 2 * (mn[3] == 'u');
        ra = sreg(a, p), comma(a, p), rb = sreg(a, p), comma(a, p);
        need_rom(a, "instructions");
        emit_insn(a, MEI_ENC_I(swapped[k], rb, ra, branch_imm(a, p)));
    } else if (!strcmp(mn, "beqz") || !strcmp(mn, "bnez")) {
        ra = sreg(a, p), comma(a, p);
        need_rom(a, "instructions");
        emit_insn(a, MEI_ENC_I(mn[1] == 'e' ? OP_BEQ : OP_BNE, ra, 0, branch_imm(a, p)));
    } else if (!strcmp(mn, "b")) {
        emit_insn(a, MEI_ENC_J(OP_JMP, jump_imm(a, p)));
    } else if (!strcmp(mn, "neg") || !strcmp(mn, "not")) {
        ra = sreg(a, p), comma(a, p), rb = sreg(a, p);
        emit_insn(a, MEI_ENC_R(OP_SUB, ra, 0, rb));
        if (mn[1] == 'o') emit_insn(a, MEI_ENC_I(OP_ADDI, ra, ra, -1));
    } else if (!strcmp(mn, "push")) {
        ra = sreg(a, p);
        emit_insn(a, MEI_ENC_I(OP_ADDI, 14, 14, -4));
        emit_insn(a, MEI_ENC_I(OP_SW, ra, 14, 0));
    } else if (!strcmp(mn, "pop")) {
        ra = sreg(a, p);
        emit_insn(a, MEI_ENC_I(OP_LW, ra, 14, 0));
        emit_insn(a, MEI_ENC_I(OP_ADDI, 14, 14, 4));
    } else {
        fail(a, "unknown instruction '%s'", mn);
    }
}

/* ---- files ---- */

static FileBuf *load_file(Asm *a, const char *name) {
    char path[1024];
    const char *slash = a->file ? strrchr(a->file, '/') : NULL;
    if (name[0] == '/' || !slash) snprintf(path, sizeof path, "%s", name);
    else snprintf(path, sizeof path, "%.*s/%s", (int)(slash - a->file), a->file, name);
    for (size_t i = 0; i < a->nfiles; i++)
        if (!strcmp(a->files[i].path, path)) return &a->files[i];
    FILE *f = fopen(path, "rb");
    if (!f) fail(a, "cannot open '%s'", path);
    FileBuf fb = {xstrdup(a, path), NULL, 0};
    size_t cap = 0;
    for (;;) {
        if (fb.len + 65536 + 1 > cap) fb.data = xrealloc(a, fb.data, cap = (fb.len + 65536 + 1) * 2);
        size_t n = fread(fb.data + fb.len, 1, 65536, f);
        fb.len += n;
        if (n < 65536) break;
    }
    fclose(f);
    fb.data[fb.len] = 0;
    a->files = xrealloc(a, a->files, (a->nfiles + 1) * sizeof *a->files);
    a->files[a->nfiles] = fb;
    return &a->files[a->nfiles++];
}

static void process_source(Asm *a, const char *src, size_t len, const char *fname);

/* ---- directives ---- */

static void define(Asm *a, const char *id, int64_t v, int ok, int label) {
    char name[NAME_MAX_];
    if (is_reg_name(id)) fail(a, "'%s' is a register name", id);
    if (!strcmp(id, ".")) fail(a, "cannot define '.'");
    qualify(a, id, name);
    Sym *s = sym_get(a, name);
    if (a->pass == 1) {
        if (s->defpass == 1) fail(a, "duplicate symbol '%s'", name);
    } else if (label && s->value != v) {
        fail(a, "internal error: label '%s' moved between passes", name);
    }
    s->defpass = a->pass;
    s->value = v;
    s->known = ok;
    if (label && id[0] != '.') snprintf(a->scope, sizeof a->scope, "%s", id);
}

static void directive(Asm *a, const char *d, const char **p) {
    char buf[MAX_LINE];
    int ok;
    int64_t v;
    if (!strcmp(d, ".org")) {
        v = expr_now(a, p, ".org address");
        if (a->sec == SEC_ROM) {
            if (v < a->loc[SEC_ROM]) fail(a, ".org 0x%llX moves backwards (location is 0x%06X)", (long long)v, a->loc[SEC_ROM]);
            if (v > ROM_START + ROM_MAX) fail(a, ".org 0x%llX is past the end of ROM", (long long)v);
        } else if (v < 0 || v > RAM_END) {
            fail(a, ".org 0x%llX is outside RAM", (long long)v);
        }
        a->loc[a->sec] = (uint32_t)v;
    } else if (!strcmp(d, ".align")) {
        v = expr_now(a, p, ".align size");
        if (v < 1 || v > 0x10000 || (v & (v - 1))) fail(a, ".align needs a power of two (1..65536)");
        uint32_t l = a->loc[a->sec], n = (uint32_t)((l + v - 1) & ~(v - 1));
        if (a->sec == SEC_ROM && n > ROM_START + ROM_MAX) fail(a, "ROM is full (%u MB)", ROM_MAX >> 20);
        a->loc[a->sec] = n;
    } else if (!strcmp(d, ".byte") || !strcmp(d, ".half") || !strcmp(d, ".word")) {
        int size = d[1] == 'b' ? 1 : d[1] == 'h' ? 2 : 4;
        need_rom(a, d);
        do {
            ws(p);
            if (size == 1 && **p == '"') {
                size_t n = parse_string(a, p, buf, sizeof buf);
                for (size_t i = 0; i < n; i++) emit_byte(a, (uint8_t)buf[i]);
                continue;
            }
            v = expr(a, p, &ok);
            int64_t lo = size == 4 ? -0x80000000ll : -(1ll << (8 * size - 1));
            int64_t hi = size == 4 ? 0xFFFFFFFFll : (1ll << (8 * size)) - 1;
            emit_le(a, (uint32_t)check(a, v, ok, lo, hi, "value"), size);
        } while (ws(p), **p == ',' && (++*p, 1));
    } else if (!strcmp(d, ".fixed")) {
        need_rom(a, d);
        do {
            double r = rbin(a, p, 1) * 65536.0;
            r = r < 0 ? -(double)(int64_t)(-r + 0.5) : (double)(int64_t)(r + 0.5);
            if (r < -2147483648.0 || r > 2147483647.0) fail(a, ".fixed value out of range (-32768..32767.99998)");
            emit_le(a, (uint32_t)(int32_t)r, 4);
        } while (ws(p), **p == ',' && (++*p, 1));
    } else if (!strcmp(d, ".ascii") || !strcmp(d, ".asciz")) {
        need_rom(a, d);
        do {
            size_t n = parse_string(a, p, buf, sizeof buf);
            for (size_t i = 0; i < n; i++) emit_byte(a, (uint8_t)buf[i]);
            if (d[5] == 'z') emit_byte(a, 0);
        } while (ws(p), **p == ',' && (++*p, 1));
    } else if (!strcmp(d, ".space") || !strcmp(d, ".zero")) {
        v = expr_now(a, p, "size");
        int64_t fill = 0;
        if (v < 0) fail(a, "negative size");
        ws(p);
        if (**p == ',') (*p)++, fill = check(a, expr_now(a, p, "fill"), 1, -128, 255, "fill byte");
        if (a->sec == SEC_RAM) {
            if (fill) fail(a, "fill value not allowed in the ram section (it holds no initialised data)");
            if (a->loc[SEC_RAM] + v > RAM_END) fail(a, "RAM is full (%u MB)", RAM_END >> 20);
            a->loc[SEC_RAM] += (uint32_t)v;
        } else {
            if (a->loc[SEC_ROM] + v > ROM_START + ROM_MAX) fail(a, "ROM is full (%u MB)", ROM_MAX >> 20);
            for (int64_t i = 0; i < v; i++) emit_byte(a, (uint8_t)fill);
        }
    } else if (!strcmp(d, ".equ") || !strcmp(d, ".set")) {
        char id[NAME_MAX_];
        ws(p);
        if (!read_ident(a, p, id)) fail(a, "expected a name");
        comma(a, p);
        v = expr(a, p, &ok);
        define(a, id, v, ok, 0);
    } else if (!strcmp(d, ".include")) {
        size_t n = parse_string(a, p, buf, sizeof buf - 1);
        buf[n] = 0;
        if (!at_end(p)) fail(a, "unexpected text after .include");
        if (a->depth >= MAX_DEPTH) fail(a, ".include nested too deeply");
        FileBuf *f = load_file(a, buf);
        const char *path = f->path, *data = f->data;
        size_t len = f->len;
        a->depth++;
        process_source(a, data, len, path);
        a->depth--;
    } else if (!strcmp(d, ".incbin")) {
        need_rom(a, d);
        size_t n = parse_string(a, p, buf, sizeof buf - 1);
        buf[n] = 0;
        const uint8_t *data = NULL;
        size_t flen = 0;
        /* blobs are usually named in order: start the search at the last match */
        for (size_t k = 0; k < a->nblobs && !data; k++) {
            size_t i = (a->blob_last + k) % a->nblobs;
            if (!strcmp(a->blobs[i].name, buf)) data = a->blobs[i].data, flen = a->blobs[i].len, a->blob_last = i;
        }
        if (!data) {
            FileBuf *f = load_file(a, buf);
            data = (const uint8_t *)f->data, flen = f->len;
        }
        int64_t off = 0, len = (int64_t)flen;
        ws(p);
        if (**p == ',') {
            (*p)++, off = expr_now(a, p, ".incbin offset");
            if (off < 0 || off > (int64_t)flen) fail(a, ".incbin offset %lld past end of file (%zu bytes)", (long long)off, flen);
            len = (int64_t)flen - off;
            ws(p);
            if (**p == ',') {
                (*p)++, v = expr_now(a, p, ".incbin length");
                if (v < 0 || off + v > (int64_t)flen) fail(a, ".incbin length %lld past end of file (%zu bytes)", (long long)v, flen);
                len = v;
            }
        }
        if (a->loc[SEC_ROM] + len > ROM_START + ROM_MAX) fail(a, "ROM is full (%u MB)", ROM_MAX >> 20);
        emit_block(a, data + off, (uint32_t)len);
    } else if (!strcmp(d, ".section")) {
        char id[NAME_MAX_];
        ws(p);
        if (!read_ident(a, p, id)) fail(a, "expected 'rom' or 'ram'");
        if (!strcmp(id, "rom")) a->sec = SEC_ROM;
        else if (!strcmp(id, "ram")) a->sec = SEC_RAM;
        else fail(a, "unknown section '%s' (rom or ram)", id);
    } else if (!strcmp(d, ".cart")) {
        need_rom(a, d);
        if (a->loc[SEC_ROM] != ROM_START || a->rom_touched) fail(a, ".cart must come first in the rom section");
        size_t n = parse_string(a, p, buf, sizeof buf);
        if (n > MEI_HDR_TITLE_LEN) fail(a, "cart title is longer than %d bytes", MEI_HDR_TITLE_LEN);
        uint32_t target = (ROM_START + MEI_HDR_SIZE) >> 2;
        char id[512];
        size_t idn = 0;
        int has_id = 0;
        /* .cart "Title" [, entry] [, "ID"]   (also .cart "Title", , "ID") */
        ws(p);
        if (**p == ',') {
            (*p)++;
            ws(p);
            if (**p == '"') has_id = 1;
            else {
                if (**p != ',') target = jump_imm(a, p);
                ws(p);
                if (**p == ',') { (*p)++; has_id = 1; }
            }
        }
        if (has_id) {
            idn = parse_string(a, p, id, sizeof id);
            if (idn == 0) fail(a, "the cart ID is empty (leave it out to use the title hash)");
            if (idn > MEI_HDR_ID_LEN) fail(a, "cart ID is longer than %d characters", MEI_HDR_ID_LEN);
            for (size_t i = 0; i < idn; i++)
                if ((unsigned char)id[i] < 32 || (unsigned char)id[i] > 126) fail(a, "cart ID must be printable ASCII");
        }
        emit_insn(a, MEI_ENC_J(OP_JMP, target));
        a->insn = 0;
        for (size_t i = 0; i < MEI_HDR_MAGIC_LEN; i++) emit_byte(a, (uint8_t)MEI_HDR_MAGIC[i]);
        for (size_t i = 0; i < MEI_HDR_TITLE_LEN; i++) emit_byte(a, i < n ? (uint8_t)buf[i] : 0);
        for (size_t i = 0; i < MEI_HDR_ID_LEN; i++) emit_byte(a, i < idn ? (uint8_t)id[i] : 0);
    } else {
        fail(a, "unknown directive '%s'", d);
    }
}

/* ---- lines ---- */

static void strip_comment(char *s) {
    for (char *p = s; *p; p++) {
        if (*p == '"' || *p == '\'') {
            char q = *p++;
            while (*p && *p != q) p += (*p == '\\' && p[1]) ? 2 : 1;
            if (!*p) return;
        } else if (*p == ';' || (*p == '/' && p[1] == '/')) {
            *p = 0;
            return;
        }
    }
}

static void statement(Asm *a, const char *p) {
    for (;;) {
        if (at_end(&p)) return;
        char id[NAME_MAX_], mn[NAME_MAX_];
        if (!read_ident(a, &p, id)) fail(a, "expected a label, instruction or directive at '%.20s'", p);
        if (*p == ':') {
            p++;
            define(a, id, a->loc[a->sec], 1, 1);
            continue;
        }
        ws(&p);
        if (*p == '=') {
            int ok;
            p++;
            int64_t v = expr(a, &p, &ok);
            define(a, id, v, ok, 0);
        } else {
            size_t i = 0;
            for (; id[i]; i++) mn[i] = (char)tolower((unsigned char)id[i]);
            mn[i] = 0;
            if (mn[0] == '.') directive(a, mn, &p);
            else instruction(a, mn, &p);
        }
        if (!at_end(&p)) fail(a, "unexpected '%.30s'", p);
        return;
    }
}

static void list_line(Asm *a, const char *src, uint32_t addr, int nonblank) {
    Str *L = &a->list;
    if (!a->emit_n) {
        if (nonblank) sb_printf(a, L, "%08X              %s\n", addr, src);
        else sb_printf(a, L, "                      %s\n", src);
        return;
    }
    uint32_t n = a->emit_n, rows = 0;
    for (uint32_t off = 0; off < n; off += 4, rows++) {
        char hex[16];
        uint32_t at = a->emit_start + off, k = n - off < 4 ? n - off : 4;
        const uint8_t *b = a->rom + (at - ROM_START);
        if (rows == 4 && n > 20) {
            sb_printf(a, L, "          ...         (%u bytes)\n", n);
            break;
        }
        if (a->insn && k == 4) snprintf(hex, sizeof hex, "%08X", b[0] | b[1] << 8 | b[2] << 16 | (uint32_t)b[3] << 24);
        else {
            int m = 0;
            for (uint32_t i = 0; i < k; i++) m += snprintf(hex + m, sizeof hex - m, i ? " %02X" : "%02X", b[i]);
        }
        sb_printf(a, L, "%08X  %-11s  %s\n", at, hex, off ? "" : src);
    }
}

static void process_source(Asm *a, const char *src, size_t len, const char *fname) {
    const char *savef = a->file;
    int savel = a->line;
    a->file = fname;
    a->line = 0;
    const char *s = src, *end = src + len;
    char buf[MAX_LINE];
    while (s < end) {
        const char *e = memchr(s, '\n', (size_t)(end - s));
        size_t n = e ? (size_t)(e - s) : (size_t)(end - s);
        a->line++;
        if (n >= MAX_LINE) fail(a, "line too long");
        memcpy(buf, s, n);
        buf[n] = 0;
        if (memchr(buf, 0, n)) fail(a, "NUL byte in source");
        if (n && buf[n - 1] == '\r') buf[--n] = 0;
        char raw[MAX_LINE];
        if (a->listing && a->pass == 2) memcpy(raw, buf, n + 1);
        strip_comment(buf);
        a->emit_n = 0, a->insn = 0;
        uint32_t addr = a->loc[a->sec];
        int inc = a->pass == 2 && a->listing && !strncmp(buf + strspn(buf, " \t"), ".include", 8);
        if (inc) sb_printf(a, &a->list, "                      %s\n", raw);
        statement(a, buf);
        if (a->listing && a->pass == 2 && !inc) {
            const char *q = buf;
            list_line(a, raw, addr, !at_end(&q));
        }
        s = e ? e + 1 : end;
    }
    a->file = savef;
    a->line = savel;
}

/* ---- API ---- */

static int sym_cmp(const void *x, const void *y) {
    const MeiSymbol *a = x, *b = y;
    if (a->value != b->value) return a->value < b->value ? -1 : 1;
    return strcmp(a->name, b->name);
}

static void asm_destroy(Asm *a) {
    for (size_t i = 0; i < a->nsyms; i++) free(a->syms[i].name);
    for (size_t i = 0; i < a->nfiles; i++) free(a->files[i].path), free(a->files[i].data);
    free(a->syms), free(a->tab), free(a->files), free(a->rom), free(a->lisz), free(a->list.s);
    free(a);
}

int mei_assemble_opts(const char *source, const char *filename, const MeiAsmOptions *opts, MeiAsmResult *out) {
    memset(out, 0, sizeof *out);
    Asm *a = calloc(1, sizeof *a);
    if (!a) { snprintf(out->error, sizeof out->error, "out of memory"); return -1; }
    if (setjmp(a->jb)) {
        mei_asm_free(out);
        snprintf(out->error, sizeof out->error, "%s", a->err);
        asm_destroy(a);
        return -1;
    }
    a->listing = opts && opts->listing;
    if (opts) a->blobs = opts->blobs, a->nblobs = opts->blob_count;
    const char *fname = filename ? filename : "<input>";
    for (a->pass = 1; a->pass <= 2; a->pass++) {
        if (a->pass == 2) {   /* pass 1 found the image size; pass 2 writes it */
            a->rom_cap = a->rom_end - ROM_START;
            a->rom = calloc(a->rom_cap + 1, 1);
            if (!a->rom) fail(a, "out of memory");
        }
        a->loc[SEC_ROM] = ROM_START, a->loc[SEC_RAM] = RAM_START, a->sec = SEC_ROM;
        a->rom_end = ROM_START, a->rom_touched = 0, a->scope[0] = 0, a->liidx = 0;
        process_source(a, source, strlen(source), fname);
    }
    a->file = fname;
    a->line = 0;

    out->rom_len = a->rom_end - ROM_START;
    out->rom = a->rom;             /* the image buffer moves to the result */
    a->rom = NULL;
    out->ram_used = a->loc[SEC_RAM];
    out->symbols = xrealloc(a, NULL, a->nsyms * sizeof *out->symbols);
    for (size_t i = 0; i < a->nsyms; i++) {
        if (!a->syms[i].known) continue;
        MeiSymbol *s = &out->symbols[out->symbol_count++];
        s->name = a->syms[i].name;
        s->value = (uint32_t)a->syms[i].value;
        a->syms[i].name = NULL;  /* ownership moves to the result */
    }
    qsort(out->symbols, out->symbol_count, sizeof *out->symbols, sym_cmp);
    if (a->listing) {
        if (!a->list.s) a->list.s = xstrdup(a, "");
        out->listing = a->list.s;
        a->list.s = NULL;
    }
    asm_destroy(a);
    return 0;
}

int mei_assemble(const char *source, const char *filename, MeiAsmResult *out) {
    return mei_assemble_opts(source, filename, NULL, out);
}

void mei_asm_free(MeiAsmResult *r) {
    if (!r) return;
    for (size_t i = 0; i < r->symbol_count; i++) free(r->symbols[i].name);
    free(r->symbols), free(r->rom), free(r->listing);
    r->symbols = NULL, r->rom = NULL, r->listing = NULL;
    r->symbol_count = r->rom_len = 0;
}

int mei_asm_find_symbol(const MeiAsmResult *r, const char *name, uint32_t *value) {
    for (size_t i = 0; i < r->symbol_count; i++)
        if (!strcmp(r->symbols[i].name, name)) { if (value) *value = r->symbols[i].value; return 1; }
    return 0;
}
