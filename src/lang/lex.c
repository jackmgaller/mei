/* Lexer. Newlines end statements: a TK_NL token is produced at a line break
 * when the previous token can end a statement and we are not inside ( ) or [ ]. */
#include "internal.h"

#include <ctype.h>
#include <string.h>

void lex_init(Lexer *L, const char *file, const char *src, size_t len) {
    memset(L, 0, sizeof *L);
    L->src = L->p = src;
    L->end = src + len;
    L->file = file;
    L->line = 1;
    L->line_start = src;
    L->last.k = TK_NL;
}

static Loc here(Lexer *L) { return (Loc){L->file, L->line, (int)(L->p - L->line_start) + 1}; }

/* Newlines are not significant directly inside ( ) or [ ]; a { } block re-enables them. */
static int in_parens(Lexer *L) {
    if (L->depth == 0) return 0;
    int i = L->depth - 1;
    return i >= (int)sizeof L->nest || L->nest[i] == '(';
}

static int ends_statement(const Token *t) {
    switch (t->k) {
    case TK_IDENT: case TK_INT: case TK_FIXED: case TK_STR: return 1;
    case TK_OP: return !strcmp(t->s, ")") || !strcmp(t->s, "]") || !strcmp(t->s, "}");
    default: return 0;
    }
}

static const char *ops3[] = {"<<=", ">>=", "..=", NULL};
static const char *ops2[] = {"->", "=>", "..", "==", "!=", "<=", ">=", "&&", "||", "<<", ">>",
                             "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", NULL};
static const char ops1[] = "+-*/%&|^~!<>=()[]{},;:.@";

static int read_escape(Lexer *L, Loc loc) {
    if (L->p >= L->end) error_at(loc, "unterminated literal");
    char c = *L->p++;
    switch (c) {
    case 'n': return '\n';
    case 't': return '\t';
    case 'r': return '\r';
    case '0': return 0;
    case '\\': return '\\';
    case '\'': return '\'';
    case '"': return '"';
    case 'x': {
        int v = 0;
        for (int i = 0; i < 2; i++) {
            if (L->p >= L->end || !isxdigit((unsigned char)*L->p)) error_at(loc, "\\x needs two hex digits");
            char h = *L->p++;
            v = v * 16 + (isdigit((unsigned char)h) ? h - '0' : (tolower((unsigned char)h) - 'a' + 10));
        }
        return v;
    }
    default: error_at(loc, "unknown escape '\\%c'", c);
    }
}

static Token lex_number(Lexer *L, Loc loc) {
    Token t = {.k = TK_INT, .loc = loc};
    const char *p = L->p;
    uint64_t v = 0;
    int digits = 0, overflow = 0;
    if (p[0] == '0' && p + 1 < L->end && (p[1] == 'x' || p[1] == 'X' || p[1] == 'b' || p[1] == 'B')) {
        int base = (p[1] == 'x' || p[1] == 'X') ? 16 : 2;
        p += 2;
        for (; p < L->end; p++) {
            int d;
            if (*p == '_') continue;
            if (isdigit((unsigned char)*p)) d = *p - '0';
            else if (base == 16 && isxdigit((unsigned char)*p)) d = tolower((unsigned char)*p) - 'a' + 10;
            else break;
            if (d >= base) error_at(loc, "invalid digit in number");
            if (v > (UINT64_MAX >> 4)) overflow = 1;
            v = v * (uint64_t)base + (uint64_t)d;
            digits++;
        }
        if (!digits) error_at(loc, "number has no digits");
    } else {
        for (; p < L->end && (isdigit((unsigned char)*p) || *p == '_'); p++) {
            if (*p == '_') continue;
            if (v > UINT64_MAX / 10 - 10) overflow = 1;
            v = v * 10 + (uint64_t)(*p - '0');
        }
        if (p + 1 < L->end && *p == '.' && isdigit((unsigned char)p[1])) {
            /* fixed literal: round the fraction to the nearest 1/65536 */
            p++;
            uint64_t num = 0, den = 1;
            int k = 0;
            for (; p < L->end && (isdigit((unsigned char)*p) || *p == '_'); p++) {
                if (*p == '_') continue;
                if (k < 12) { num = num * 10 + (uint64_t)(*p - '0'); den *= 10; k++; }
            }
            if (v > 0x7FFFFFFF) overflow = 1;
            t.k = TK_FIXED;
            t.ival = (int64_t)(v << 16) + (int64_t)((num * 65536 + den / 2) / den);
        }
    }
    if (overflow || (t.k == TK_INT && v > (uint64_t)INT64_MAX)) error_at(loc, "number is too large");
    if (p < L->end && (isalnum((unsigned char)*p) || *p == '_')) error_at(loc, "invalid character '%c' in number", *p);
    if (t.k == TK_INT) t.ival = (int64_t)v;
    L->p = p;
    return t;
}

Token lex_next(Lexer *L) {
    for (;;) {
        /* skip whitespace and comments, noting newlines */
        int saw_nl = 0;
        for (;;) {
            if (L->p >= L->end) break;
            char c = *L->p;
            if (c == '\n') { saw_nl = 1; L->p++; L->line++; L->line_start = L->p; }
            else if (c == ' ' || c == '\t' || c == '\r') L->p++;
            else if (c == '/' && L->p + 1 < L->end && L->p[1] == '/') {
                while (L->p < L->end && *L->p != '\n') L->p++;
            } else if (c == '/' && L->p + 1 < L->end && L->p[1] == '*') {
                Loc loc = here(L);
                L->p += 2;
                for (;;) {
                    if (L->p + 1 >= L->end) error_at(loc, "unterminated /* comment");
                    if (*L->p == '*' && L->p[1] == '/') { L->p += 2; break; }
                    if (*L->p == '\n') { saw_nl = 1; L->line++; L->line_start = L->p + 1; }
                    L->p++;
                }
            } else break;
            if (saw_nl && !in_parens(L) && ends_statement(&L->last)) {
                Token t = {.k = TK_NL, .loc = here(L), .s = "newline"};
                L->last = t;
                return t;
            }
        }
        Loc loc = here(L);
        Token t = {.loc = loc};
        if (L->p >= L->end) {
            if (!in_parens(L) && ends_statement(&L->last)) { t.k = TK_NL; t.s = "newline"; L->last = t; return t; }
            t.k = TK_EOF; t.s = "end of file";
            return t;
        }
        char c = *L->p;
        if (isalpha((unsigned char)c) || c == '_') {
            const char *s = L->p;
            while (L->p < L->end && (isalnum((unsigned char)*L->p) || *L->p == '_')) L->p++;
            t.k = TK_IDENT;
            t.s = ar_strndup(s, (size_t)(L->p - s));
        } else if (isdigit((unsigned char)c)) {
            t = lex_number(L, loc);
        } else if (c == '"') {
            L->p++;
            Buf b = {0};
            for (;;) {
                if (L->p >= L->end || *L->p == '\n') { buf_free(&b); error_at(loc, "unterminated string"); }
                char ch = *L->p++;
                if (ch == '"') break;
                if (ch == '\\') ch = (char)read_escape(L, loc);
                buf_putc(&b, ch);
            }
            t.k = TK_STR;
            t.slen = b.len;
            t.s = ar_strndup(b.p ? b.p : "", b.len);
            buf_free(&b);
        } else if (c == '\'') {
            L->p++;
            if (L->p >= L->end) error_at(loc, "unterminated character literal");
            int v = (unsigned char)*L->p++;
            if (v == '\\') v = read_escape(L, loc);
            if (L->p >= L->end || *L->p != '\'') error_at(loc, "character literal must hold exactly one character");
            L->p++;
            t.k = TK_INT;
            t.ival = v & 0xFF;
        } else {
            t.k = TK_OP;
            for (int i = 0; ops3[i]; i++)
                if (L->end - L->p >= 3 && !strncmp(L->p, ops3[i], 3)) { t.s = ops3[i]; break; }
            if (!t.s) for (int i = 0; ops2[i]; i++)
                if (L->end - L->p >= 2 && !strncmp(L->p, ops2[i], 2)) { t.s = ops2[i]; break; }
            if (!t.s) {
                const char *f = strchr(ops1, c);
                if (!f || !c) error_at(loc, "unexpected character '%c'", c);
                t.s = ar_strndup(&c, 1);
            }
            L->p += strlen(t.s);
            if (!strcmp(t.s, "(") || !strcmp(t.s, "[") || !strcmp(t.s, "{")) {
                if (L->depth < (int)sizeof L->nest) L->nest[L->depth] = t.s[0] == '{' ? '{' : '(';
                L->depth++;
            }
            if ((!strcmp(t.s, ")") || !strcmp(t.s, "]") || !strcmp(t.s, "}")) && L->depth > 0) L->depth--;
        }
        L->last = t;
        return t;
    }
}

char *lex_raw_block(Lexer *L, Loc *start) {
    *start = here(L);
    const char *s = L->p;
    int depth = 1;
    while (L->p < L->end) {
        char c = *L->p;
        if (c == '\n') { L->line++; L->line_start = L->p + 1; }
        else if (c == ';' || (c == '/' && L->p + 1 < L->end && L->p[1] == '/')) {
            /* asm comment: skip to end of line so braces in comments don't count */
            while (L->p < L->end && *L->p != '\n') L->p++;
            continue;
        } else if (c == '{') depth++;
        else if (c == '}' && --depth == 0) {
            char *r = ar_strndup(s, (size_t)(L->p - s));
            L->p++;
            if (L->depth > 0) L->depth--;   /* the `{` that opened the block */
            L->last = (Token){.k = TK_OP, .s = "}"};
            return r;
        }
        L->p++;
    }
    error_at(*start, "unterminated asm block (missing '}')");
}
