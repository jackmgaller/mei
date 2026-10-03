/* Recursive-descent parser: tokens -> AST. Top-level declarations are entered into
 * the global symbol table here; everything else is resolved by the checker. */
#include "internal.h"

#include <string.h>

typedef struct {
    Lexer L;
    Token tok;
    Compiler *C;
    Program *P;
    const char *file;
    int no_struct_lit;
    int in_arm;          /* parsing a single-statement match arm: ',' may end it */
    int priv;            /* the declaration being parsed is `private` */
    int weak;            /* the function being parsed is `weak` */
} Parser;

static const char *keywords[] = {
    "fn", "var", "let", "const", "struct", "if", "else", "while", "for", "in", "break",
    "continue", "return", "import", "asm", "reg", "embed", "as", "true", "false", "null", "cart", "enum", "match",
    "assert", "assert_eq", NULL,
};

static int is_keyword(const char *s) {
    for (int i = 0; keywords[i]; i++) if (!strcmp(s, keywords[i])) return 1;
    return 0;
}

static void next(Parser *p) { p->tok = lex_next(&p->L); }

static int is_op(Parser *p, const char *op) { return p->tok.k == TK_OP && !strcmp(p->tok.s, op); }
static int is_kw(Parser *p, const char *kw) { return p->tok.k == TK_IDENT && !strcmp(p->tok.s, kw); }

static const char *tok_desc(Token *t) {
    switch (t->k) {
    case TK_EOF: return "end of file";
    case TK_NL: return "end of line";
    case TK_INT: case TK_FIXED: return "number";
    case TK_STR: return "string";
    default: return ar_printf("'%s'", t->s);
    }
}

static void expect_op(Parser *p, const char *op) {
    if (!is_op(p, op)) error_at(p->tok.loc, "expected '%s', found %s", op, tok_desc(&p->tok));
    next(p);
}

static void skip_nl(Parser *p) { while (p->tok.k == TK_NL || is_op(p, ";")) next(p); }
static void skip_nl_only(Parser *p) { while (p->tok.k == TK_NL) next(p); }

static const char *expect_ident(Parser *p, const char *what) {
    if (p->tok.k == TK_IDENT && is_keyword(p->tok.s))
        error_at(p->tok.loc, "'%s' is a keyword and cannot be used as %s", p->tok.s, what);
    if (p->tok.k != TK_IDENT)
        error_at(p->tok.loc, "expected %s, found %s", what, tok_desc(&p->tok));
    const char *s = p->tok.s;
    next(p);
    return s;
}

static void end_statement(Parser *p) {
    if (p->tok.k == TK_NL || is_op(p, ";")) { next(p); return; }
    if (is_op(p, "}") || p->tok.k == TK_EOF) return;
    if (p->in_arm && is_op(p, ",")) return;
    error_at(p->tok.loc, "expected end of statement, found %s", tok_desc(&p->tok));
}

#define PUSH(arr, n, cap, v) do { if ((n) == (cap)) { int nc_ = (cap) ? (cap) * 2 : 8; \
    void *np_ = ar_alloc(sizeof(*(arr)) * (size_t)nc_); if (n) memcpy(np_, (arr), sizeof(*(arr)) * (size_t)(n)); \
    (arr) = np_; (cap) = nc_; } (arr)[(n)++] = (v); } while (0)

/* ---- types ---- */

static Expr *parse_expr(Parser *p);

static TypeExpr *parse_type(Parser *p) {
    TypeExpr *t = ar_alloc(sizeof *t);
    t->loc = p->tok.loc;
    if (is_kw(p, "bits")) {
        next(p);
        t->k = 5;
        StructDecl *d = ar_alloc(sizeof *d);
        d->name = "bits"; d->loc = t->loc;
        t->bits = d;
        expect_op(p, "{");
        skip_nl(p);
        int cn = 0, ct = 0, cl = 0, cd = 0, cw = 0;
        int nn = 0, nt = 0, nd = 0, nw = 0;
        while (!is_op(p, "}")) {
            Loc loc = p->tok.loc;
            const char *name = expect_ident(p, "a packed field name");
            for (int i = 0; i < d->nf; i++)
                if (!strcmp(name, d->fnames[i])) error_at(loc, "duplicate packed field '%s'", name);
            TypeExpr *ft = ar_alloc(sizeof *ft);
            ft->loc = loc; ft->name = "bool";
            Expr *width = NULL, *def = NULL;
            if (is_op(p, ":")) {
                next(p); ft = parse_type(p);
                expect_op(p, ":");
                width = parse_expr(p);
            }
            if (is_op(p, "=")) { next(p); def = parse_expr(p); }
            PUSH(d->fnames, nn, cn, name);
            PUSH(d->ftypes, nt, ct, ft);
            PUSH(d->flocs, d->nf, cl, loc);
            PUSH(d->fdefs, nd, cd, def);
            PUSH(d->fwidths, nw, cw, width);
            if (is_op(p, ",")) next(p);
            else if (p->tok.k != TK_NL && !is_op(p, "}"))
                error_at(p->tok.loc, "expected ',' or '}' in bits declaration");
            skip_nl(p);
        }
        if (!d->nf) error_at(t->loc, "bits declarations require at least one field");
        next(p);
    } else if (is_op(p, "*")) {
        next(p);
        t->k = 1;
        t->elem = parse_type(p);
    } else if (is_op(p, "[")) {
        next(p);
        t->k = is_op(p, "]") ? 4 : 2;
        if (t->k == 2) t->len = parse_expr(p);
        expect_op(p, "]");
        if (t->k == 4 && is_kw(p, "const")) { t->readonly = 1; next(p); }
        t->elem = parse_type(p);
    } else if (is_kw(p, "fn")) {
        /* function type: fn(T, U) -> R */
        next(p);
        t->k = 3;
        expect_op(p, "(");
        int cap = 0;
        while (!is_op(p, ")")) {
            TypeExpr *pt = parse_type(p);
            PUSH(t->params, t->nparams, cap, pt);
            if (!is_op(p, ",")) break;
            next(p);
        }
        expect_op(p, ")");
        if (is_op(p, "->")) { next(p); t->elem = parse_type(p); }
    } else {
        t->k = 0;
        t->name = expect_ident(p, "a type");
        if (is_op(p, ".")) { next(p); t->name = ar_printf("%s.%s", t->name, expect_ident(p, "a type name")); }
    }
    return t;
}

/* ---- expressions ---- */

static Expr *new_expr(ExprKind k, Loc loc) {
    Expr *e = ar_alloc(sizeof *e);
    e->k = k;
    e->loc = loc;
    return e;
}

static Expr *parse_unary(Parser *p);
static Expr *parse_match_expr(Parser *p);
static void parse_params(Parser *p, Func *f, int types_optional);
static struct Stmt *parse_block(Parser *p);

/* fn(x: T, ...) -> R { body }   or   fn(x: T, ...) => expr   (parameter types may be omitted
   where the expected function type supplies them) */
static Expr *parse_lambda(Parser *p) {
    Expr *e = new_expr(E_FUNC, p->tok.loc);
    next(p);
    Func *f = ar_alloc(sizeof *f);
    f->loc = e->loc;
    f->is_lambda = 1;
    parse_params(p, f, 1);
    int save = p->no_struct_lit, save_arm = p->in_arm;
    p->no_struct_lit = 0;
    p->in_arm = 0;
    if (is_op(p, "=>")) {
        next(p);
        skip_nl_only(p);
        f->lambda_body = parse_expr(p);
    } else {
        if (!is_op(p, "{")) skip_nl_only(p);
        if (!is_op(p, "{")) error_at(p->tok.loc, "expected '{' or '=>' to start the function literal's body, found %s", tok_desc(&p->tok));
        f->body = parse_block(p);
    }
    p->no_struct_lit = save;
    p->in_arm = save_arm;
    e->lambda = f;
    return e;
}

static Expr *parse_struct_expr(Parser *p, const char *name, Loc loc) {
    Expr *e = new_expr(E_STRUCT, loc);
    e->name = name;
    next(p);
    int cap = 0, fcap = 0, nf = 0;
    skip_nl(p);
    while (!is_op(p, "}")) {
        const char *fname = expect_ident(p, "a field name");
        expect_op(p, ":");
        skip_nl_only(p);
        int save = p->no_struct_lit;
        p->no_struct_lit = 0;
        Expr *v = parse_expr(p);
        p->no_struct_lit = save;
        PUSH(e->fnames, nf, fcap, fname);
        PUSH(e->args, e->nargs, cap, v);
        if (is_op(p, ",")) next(p);
        else if (p->tok.k != TK_NL && !is_op(p, "}"))
            error_at(p->tok.loc, "expected ',' or '}' in struct literal, found %s", tok_desc(&p->tok));
        skip_nl(p);
    }
    expect_op(p, "}");
    return e;
}

static Expr *parse_primary(Parser *p) {
    Token t = p->tok;
    Expr *e;
    switch (t.k) {
    case TK_INT: next(p); e = new_expr(E_INT, t.loc); e->ival = t.ival; return e;
    case TK_FIXED: next(p); e = new_expr(E_FIXED, t.loc); e->ival = t.ival; return e;
    case TK_STR: next(p); e = new_expr(E_STR, t.loc); e->str = t.s; e->slen = t.slen; return e;
    case TK_IDENT:
        if (!strcmp(t.s, "true") || !strcmp(t.s, "false")) {
            next(p);
            e = new_expr(E_BOOL, t.loc);
            e->ival = t.s[0] == 't';
            return e;
        }
        if (!strcmp(t.s, "null")) { next(p); return new_expr(E_NULL, t.loc); }
        if (!strcmp(t.s, "sizeof")) {
            next(p);
            expect_op(p, "(");
            e = new_expr(E_SIZEOF, t.loc);
            e->texpr = parse_type(p);
            expect_op(p, ")");
            return e;
        }
        if (!strcmp(t.s, "fn")) return parse_lambda(p);
        if (!strcmp(t.s, "match")) return parse_match_expr(p);
        if (is_keyword(t.s)) error_at(t.loc, "expected an expression, found the keyword '%s'", t.s);
        next(p);
        if (is_op(p, "{") && !p->no_struct_lit) return parse_struct_expr(p, t.s, t.loc);
        e = new_expr(E_NAME, t.loc);
        e->name = t.s;
        return e;
    case TK_OP:
        if (!strcmp(t.s, "(")) {
            next(p);
            int save = p->no_struct_lit;
            p->no_struct_lit = 0;
            e = parse_expr(p);
            p->no_struct_lit = save;
            expect_op(p, ")");
            return e;
        }
        if (!strcmp(t.s, "[")) {
            next(p);
            e = new_expr(E_ARRAY, t.loc);
            int cap = 0;
            int save = p->no_struct_lit;
            p->no_struct_lit = 0;
            while (!is_op(p, "]")) {
                PUSH(e->args, e->nargs, cap, parse_expr(p));
                if (!is_op(p, ",")) break;
                next(p);
            }
            p->no_struct_lit = save;
            expect_op(p, "]");
            return e;
        }
        break;
    default: break;
    }
    error_at(t.loc, "expected an expression, found %s", tok_desc(&t));
}

static Expr *parse_postfix(Parser *p) {
    Expr *e = parse_primary(p);
    for (;;) {
        Loc loc = p->tok.loc;
        if (is_op(p, "(")) {
            next(p);
            Expr *c = new_expr(E_CALL, loc);
            c->a = e;
            int cap = 0;
            int save = p->no_struct_lit;
            p->no_struct_lit = 0;
            while (!is_op(p, ")")) {
                PUSH(c->args, c->nargs, cap, parse_expr(p));
                if (!is_op(p, ",")) break;
                next(p);
            }
            p->no_struct_lit = save;
            expect_op(p, ")");
            e = c;
        } else if (is_op(p, "[")) {
            next(p);
            Expr *x = new_expr(E_INDEX, loc);
            x->a = e;
            int save = p->no_struct_lit;
            p->no_struct_lit = 0;
            x->b = parse_expr(p);
            if (is_op(p, "..")) {
                next(p);
                x->k = E_SLICE;
                x->args = ar_alloc(2 * sizeof *x->args);
                x->args[0] = x->b;
                x->args[1] = parse_expr(p);
                x->nargs = 2;
                x->b = NULL;
            }
            p->no_struct_lit = save;
            expect_op(p, "]");
            e = x;
        } else if (is_op(p, ".")) {
            next(p);
            Expr *f = new_expr(E_FIELD, loc);
            f->a = e;
            f->name = expect_ident(p, "a field name");
            e = f;
        } else if (is_op(p, "{") && !p->no_struct_lit && e->k == E_FIELD && e->a->k == E_NAME) {
            e = parse_struct_expr(p, ar_printf("%s.%s", e->a->name, e->name), e->a->loc);
        } else return e;
    }
}

static Expr *parse_unary(Parser *p) {
    Loc loc = p->tok.loc;
    static const struct { const char *s; OpKind op; } un[] = {
        {"-", U_NEG}, {"!", U_NOT}, {"~", U_BNOT}, {"&", U_ADDR}, {"*", U_DEREF},
    };
    for (size_t i = 0; i < sizeof un / sizeof un[0]; i++) {
        if (is_op(p, un[i].s)) {
            next(p);
            Expr *operand = parse_unary(p);
            if (un[i].op == U_NEG && (operand->k == E_INT || operand->k == E_FIXED)) {
                operand->ival = -operand->ival;   /* fold so -2147483648 is a valid literal */
                operand->loc = loc;
                return operand;
            }
            Expr *e = new_expr(E_UNARY, loc);
            e->op = un[i].op;
            e->a = operand;
            return e;
        }
    }
    return parse_postfix(p);
}

static Expr *parse_cast(Parser *p) {
    Expr *e = parse_unary(p);
    while (is_kw(p, "as")) {
        Expr *c = new_expr(E_CAST, p->tok.loc);
        next(p);
        c->a = e;
        c->texpr = parse_type(p);
        e = c;
    }
    return e;
}

static int binop_prec(Parser *p, OpKind *op) {
    static const struct { const char *s; OpKind op; int prec; } bin[] = {
        {"||", B_LOR, 1}, {"&&", B_LAND, 2},
        {"==", B_EQ, 3}, {"!=", B_NE, 3}, {"<", B_LT, 3}, {"<=", B_LE, 3}, {">", B_GT, 3}, {">=", B_GE, 3},
        {"|", B_OR, 4}, {"^", B_XOR, 5}, {"&", B_AND, 6}, {"<<", B_SHL, 7}, {">>", B_SHR, 7},
        {"+", B_ADD, 8}, {"-", B_SUB, 8}, {"*", B_MUL, 9}, {"/", B_DIV, 9}, {"%", B_MOD, 9},
    };
    if (p->tok.k != TK_OP) return 0;
    for (size_t i = 0; i < sizeof bin / sizeof bin[0]; i++)
        if (!strcmp(p->tok.s, bin[i].s)) { *op = bin[i].op; return bin[i].prec; }
    return 0;
}

static Expr *parse_binary(Parser *p, int min_prec) {
    Expr *lhs = parse_cast(p);
    for (;;) {
        OpKind op;
        int prec = binop_prec(p, &op);
        if (!prec || prec < min_prec) return lhs;
        Loc loc = p->tok.loc;
        next(p);
        skip_nl_only(p);
        Expr *rhs = parse_binary(p, prec + 1);
        Expr *e = new_expr(E_BINARY, loc);
        e->op = op;
        e->a = lhs;
        e->b = rhs;
        if (prec == 3) {   /* comparisons do not chain */
            OpKind op2;
            if (binop_prec(p, &op2) == 3)
                error_at(p->tok.loc, "comparisons cannot be chained; use && to combine them");
        }
        lhs = e;
    }
}

static Expr *parse_expr(Parser *p) { return parse_binary(p, 1); }

static Expr *parse_cond(Parser *p) {
    int save = p->no_struct_lit;
    p->no_struct_lit = 1;
    Expr *e = parse_expr(p);
    p->no_struct_lit = save;
    return e;
}

/* ---- statements ---- */

static Stmt *new_stmt(StmtKind k, Loc loc) {
    Stmt *s = ar_alloc(sizeof *s);
    s->k = k;
    s->loc = loc;
    return s;
}

static Stmt *parse_block(Parser *p);

static Stmt *parse_var_decl(Parser *p, int is_let) {
    Stmt *s = new_stmt(S_VAR, p->tok.loc);
    next(p);
    s->is_let = is_let;
    s->loc = p->tok.loc;
    s->name = expect_ident(p, "a variable name");
    if (is_op(p, ":")) { next(p); s->texpr = parse_type(p); }
    if (is_op(p, "=")) { next(p); skip_nl_only(p); s->e = parse_expr(p); }
    if (!s->texpr && !s->e) error_at(s->loc, "'%s' needs a type or an initial value", s->name);
    if (is_let && !s->e) error_at(s->loc, "'let %s' needs an initial value (use 'var' for a variable)", s->name);
    return s;
}

static Stmt *parse_if(Parser *p) {
    Stmt *s = new_stmt(S_IF, p->tok.loc);
    next(p);
    s->e = parse_cond(p);
    s->then = parse_block(p);
    /* allow `else` on the line after the closing brace */
    Lexer save_l = p->L;
    Token save_t = p->tok;
    skip_nl_only(p);
    if (is_kw(p, "else")) {
        next(p);
        if (is_kw(p, "if")) s->els = parse_if(p);
        else s->els = parse_block(p);
    } else {
        p->L = save_l;
        p->tok = save_t;
    }
    return s;
}

static Stmt *parse_stmt(Parser *p);

/* The patterns of a match arm and its `=>`: `A, B =>`, `else =>` or `_ =>`. */
static MatchArm parse_arm_head(Parser *p) {
    MatchArm arm = {0};
    arm.loc = p->tok.loc;
    if (is_kw(p, "else") || (p->tok.k == TK_IDENT && !strcmp(p->tok.s, "_"))) {
        arm.is_else = 1;
        next(p);
    } else {
        int pcap = 0;
        for (;;) {
            int save = p->no_struct_lit;
            p->no_struct_lit = 1;
            Expr *pat = parse_expr(p);
            p->no_struct_lit = save;
            PUSH(arm.pats, arm.npats, pcap, pat);
            if (!is_op(p, ",")) break;
            next(p);
            skip_nl_only(p);
        }
    }
    if (!is_op(p, "=>")) error_at(p->tok.loc, "expected '=>' after the match pattern, found %s", tok_desc(&p->tok));
    next(p);
    skip_nl_only(p);
    return arm;
}

/* match x { A, B => value  C => value  else => value }: every arm is one expression. */
static Expr *parse_match_expr(Parser *p) {
    Expr *e = new_expr(E_MATCH, p->tok.loc);
    next(p);
    e->a = parse_cond(p);
    skip_nl_only(p);
    expect_op(p, "{");
    int save = p->no_struct_lit, save_arm = p->in_arm;
    p->in_arm = 0;
    int cap = 0;
    for (;;) {
        skip_nl(p);
        if (is_op(p, "}")) break;
        if (p->tok.k == TK_EOF) error_at(e->loc, "unclosed match");
        MatchArm arm = parse_arm_head(p);
        if (is_op(p, "{"))
            error_at(p->tok.loc, "an arm of a match expression is a value, not a block (use a match statement to run statements)");
        p->no_struct_lit = 0;
        arm.value = parse_expr(p);
        p->no_struct_lit = save;
        if (is_op(p, ",")) next(p);
        else if (p->tok.k != TK_NL && !is_op(p, "}") && !is_op(p, ";"))
            error_at(p->tok.loc, "expected ',' or a new line after the value of the match arm, found %s", tok_desc(&p->tok));
        PUSH(e->arms, e->narms, cap, arm);
    }
    next(p);
    p->in_arm = save_arm;
    if (!e->narms) error_at(e->loc, "a match expression needs at least one arm");
    return e;
}

/* match x { A, B => stmt  C => { ... }  else => ... }   (`_` is the same as else) */
static Stmt *parse_match(Parser *p) {
    Stmt *s = new_stmt(S_MATCH, p->tok.loc);
    next(p);
    s->e = parse_cond(p);
    skip_nl_only(p);
    expect_op(p, "{");
    int cap = 0;
    for (;;) {
        skip_nl(p);
        if (is_op(p, "}")) break;
        if (p->tok.k == TK_EOF) error_at(s->loc, "unclosed match");
        MatchArm arm = parse_arm_head(p);
        if (is_op(p, "{")) arm.body = parse_block(p);
        else {
            int save = p->in_arm;
            p->in_arm = 1;
            arm.body = parse_stmt(p);
            p->in_arm = save;
        }
        if (is_op(p, ",")) next(p);
        PUSH(s->arms, s->narms, cap, arm);
    }
    next(p);
    return s;
}

/* ---- assert(cond[, "message"]) and assert_eq(a, b[, "message"]) ----
 * Desugared here, where the source text is at hand:
 *   assert(c)        ->  if !c { __assert_fail("file:line: assert(c)") }
 *   assert_eq(a, b)  ->  if a != b { __assert_eq_fail("file:line: ...", __kind(a), __raw(a), __kind(b), __raw(b)) }
 * (on a failure a and b are evaluated a second time, for the report). With
 * MeiCompileOptions.no_asserts the statement is checked for syntax only and dropped. */

typedef struct { Lexer L; Token tok; } ParseState;
static ParseState parse_save(Parser *p) { ParseState s = {p->L, p->tok}; return s; }
static void parse_restore(Parser *p, ParseState s) { p->L = s.L; p->tok = s.tok; }

static Expr *mk_call1(const char *fname, Loc loc, Expr **args, int n) {
    Expr *c = new_expr(E_CALL, loc);
    c->a = new_expr(E_NAME, loc);
    c->a->name = fname;
    c->args = ar_alloc(sizeof *c->args * (size_t)n);
    for (int i = 0; i < n; i++) c->args[i] = args[i];
    c->nargs = n;
    return c;
}

static Expr *mk_wrap(const char *fname, Expr *x) { return mk_call1(fname, x->loc, &x, 1); }

static Stmt *parse_assert(Parser *p) {
    Loc loc = p->tok.loc;
    int eq = is_kw(p, "assert_eq");
    const char *kw = eq ? "assert_eq" : "assert";
    next(p);
    if (!is_op(p, "(")) error_at(p->tok.loc, "expected '(' after %s", kw);
    const char *src0 = p->L.p;          /* just after the '(' */
    next(p);
    int save = p->no_struct_lit;
    p->no_struct_lit = 0;
    ParseState args = parse_save(p);
    Expr *a = parse_expr(p), *b = NULL;
    if (eq) {
        if (!is_op(p, ",")) error_at(p->tok.loc, "assert_eq() compares two values: assert_eq(got, expected)");
        next(p);
        b = parse_expr(p);
    }
    if (p->tok.k != TK_OP) error_at(p->tok.loc, "expected ',' or ')' in %s(), found %s", kw, tok_desc(&p->tok));
    const char *src1 = p->L.p - strlen(p->tok.s);
    const char *msg = NULL;
    if (is_op(p, ",")) {
        next(p);
        if (p->tok.k != TK_STR) error_at(p->tok.loc, "the message of %s() must be a string literal", kw);
        msg = p->tok.s;
        next(p);
    }
    expect_op(p, ")");
    p->no_struct_lit = save;
    ParseState after = parse_save(p);

    /* "file.akr:12: assert(x > 0) - message", with whitespace runs collapsed */
    size_t cap = (size_t)(src1 - src0) + 1, n = 0;
    char *text = ar_alloc(cap);
    for (const char *q = src0; q < src1; q++) {
        char ch = (*q == '\n' || *q == '\t' || *q == '\r') ? ' ' : *q;
        if (ch == ' ' && (n == 0 || text[n - 1] == ' ')) continue;
        text[n++] = ch;
    }
    while (n > 0 && text[n - 1] == ' ') n--;
    text[n] = 0;
    const char *base = strrchr(loc.file, '/');
    base = base ? base + 1 : loc.file;
    Expr *str = new_expr(E_STR, loc);
    str->str = ar_printf("%s:%d: %s(%s)%s%s", base, loc.line, kw, text, msg ? " - " : "", msg ? msg : "");
    str->slen = strlen(str->str);

    if (p->C->opt->no_asserts) {
        parse_restore(p, after);
        end_statement(p);
        return new_stmt(S_BLOCK, loc);
    }
    Stmt *s = new_stmt(S_IF, loc);
    Expr *call;
    if (!eq) {
        Expr *nt = new_expr(E_UNARY, loc);
        nt->op = U_NOT;
        nt->a = a;
        s->e = nt;
        call = mk_call1("__assert_fail", loc, &str, 1);
    } else {
        Expr *ne = new_expr(E_BINARY, loc);
        ne->op = B_NE;
        ne->a = a;
        ne->b = b;
        s->e = ne;
        /* fresh copies of the operands for the report (the checker rewrites nodes in place) */
        Expr *cp[4];
        for (int k = 0; k < 2; k++) {
            parse_restore(p, args);
            p->no_struct_lit = 0;
            cp[k * 2] = parse_expr(p);
            next(p);                    /* the ',' */
            cp[k * 2 + 1] = parse_expr(p);
        }
        p->no_struct_lit = save;
        Expr *rep[5] = {str, mk_wrap("__kind", cp[0]), mk_wrap("__raw", cp[2]), mk_wrap("__kind", cp[1]), mk_wrap("__raw", cp[3])};
        call = mk_call1("__assert_eq_fail", loc, rep, 5);
    }
    Stmt *cs = new_stmt(S_EXPR, loc);
    cs->e = call;
    Stmt *then = new_stmt(S_BLOCK, loc);
    then->list = ar_alloc(sizeof *then->list);
    then->list[0] = cs;
    then->n = 1;
    s->then = then;
    parse_restore(p, after);
    end_statement(p);
    return s;
}

static Stmt *parse_stmt(Parser *p) {
    Loc loc = p->tok.loc;
    Stmt *s;
    if (is_kw(p, "assert") || is_kw(p, "assert_eq")) return parse_assert(p);
    if (is_kw(p, "match")) return parse_match(p);
    if (is_kw(p, "var") || is_kw(p, "let")) {
        s = parse_var_decl(p, is_kw(p, "let"));
        end_statement(p);
        return s;
    }
    if (is_kw(p, "if")) return parse_if(p);
    if (is_kw(p, "while")) {
        s = new_stmt(S_WHILE, loc);
        next(p);
        s->e = parse_cond(p);
        s->then = parse_block(p);
        return s;
    }
    if (is_kw(p, "for")) {
        s = new_stmt(S_FOR, loc);
        next(p);
        s->asm_loc = p->tok.loc;
        s->name = expect_ident(p, "a loop variable name");
        if (!is_kw(p, "in")) error_at(p->tok.loc, "expected 'in' after the loop variable");
        next(p);
        int save = p->no_struct_lit;
        p->no_struct_lit = 1;
        s->e = parse_expr(p);
        if (is_op(p, "..=")) error_at(p->tok.loc, "inclusive ranges are not supported; use lo..hi+1");
        if (is_op(p, "{") && s->e->k == E_NAME) s->e2 = NULL;   /* for d in EnumType: every variant */
        else {
            expect_op(p, "..");
            s->e2 = parse_expr(p);
        }
        p->no_struct_lit = save;
        s->then = parse_block(p);
        return s;
    }
    if (is_kw(p, "break") || is_kw(p, "continue")) {
        s = new_stmt(is_kw(p, "break") ? S_BREAK : S_CONTINUE, loc);
        next(p);
        end_statement(p);
        return s;
    }
    if (is_kw(p, "return")) {
        s = new_stmt(S_RETURN, loc);
        next(p);
        if (p->tok.k != TK_NL && !is_op(p, ";") && !is_op(p, "}")) s->e = parse_expr(p);
        end_statement(p);
        return s;
    }
    if (is_kw(p, "asm")) {
        s = new_stmt(S_ASM, loc);
        next(p);
        skip_nl_only(p);
        if (!is_op(p, "{")) error_at(p->tok.loc, "expected '{' after asm");
        s->asm_text = lex_raw_block(&p->L, &s->asm_loc);
        next(p);
        return s;
    }
    if (is_kw(p, "const")) {
        /* a local constant: visible in the rest of its block */
        s = new_stmt(S_CONST, loc);
        next(p);
        s->loc = p->tok.loc;
        s->name = expect_ident(p, "a constant name");
        if (is_op(p, ":")) { next(p); s->texpr = parse_type(p); }
        expect_op(p, "=");
        skip_nl_only(p);
        s->e = parse_expr(p);
        end_statement(p);
        return s;
    }
    if (is_op(p, "{")) return parse_block(p);
    /* '-' and '*' are also unary: a line starting with them is a new statement */
    const char *lead = is_op(p, "-") ? "-" : is_op(p, "*") ? "*" : NULL;
    Expr *e = parse_expr(p);
    static const struct { const char *s; int op; } as[] = {
        {"=", -1}, {"+=", B_ADD}, {"-=", B_SUB}, {"*=", B_MUL}, {"/=", B_DIV}, {"%=", B_MOD},
        {"&=", B_AND}, {"|=", B_OR}, {"^=", B_XOR}, {"<<=", B_SHL}, {">>=", B_SHR},
    };
    for (size_t i = 0; i < sizeof as / sizeof as[0]; i++) {
        if (is_op(p, as[i].s)) {
            s = new_stmt(S_ASSIGN, p->tok.loc);
            next(p);
            skip_nl_only(p);
            s->op = as[i].op;
            s->e = e;
            s->e2 = parse_expr(p);
            end_statement(p);
            return s;
        }
    }
    if (is_op(p, "==")) error_at(p->tok.loc, "'==' compares; use '=' to assign");
    if (lead && e->k != E_CALL)
        error_at(loc, "a line that starts with '%s' begins a new statement ('%s' is also %s, and this value alone does "
                 "nothing); to continue the expression from the line above, end that line with '%s' instead, or put "
                 "the whole expression in parentheses", lead, lead, lead[0] == '-' ? "unary minus" : "the dereference", lead);
    s = new_stmt(S_EXPR, loc);
    s->e = e;
    end_statement(p);
    return s;
}

static Stmt *parse_block(Parser *p) {
    skip_nl_only(p);   /* allow the brace on the next line */
    Stmt *b = new_stmt(S_BLOCK, p->tok.loc);
    if (!is_op(p, "{")) error_at(p->tok.loc, "expected '{', found %s", tok_desc(&p->tok));
    next(p);
    int cap = 0;
    skip_nl(p);
    while (!is_op(p, "}")) {
        if (p->tok.k == TK_EOF) error_at(b->loc, "unclosed '{'");
        PUSH(b->list, b->n, cap, parse_stmt(p));
        skip_nl(p);
    }
    next(p);
    return b;
}

/* ---- declarations ---- */

static Sym *new_global(Parser *p, SymKind k, const char *name, Loc loc) {
    int user = !file_is_stdlib(p->file);
    /* a private name conflicts with this file's names; a public one with every public name and
       with this file's private names */
    if (module_has_alias(p->file, name)) error_at(loc, "'%s' conflicts with an import alias", name);
    Sym *old = sym_lookup_private(name, p->file);
    if (!old) old = sym_lookup_module(name, p->file, 1);
    if (!old && !file_is_module(p->file)) {
        old = sym_lookup_layer(name, user);
        if (old && p->priv && old->loc.file && strcmp(old->loc.file, p->file)) old = NULL;   /* hides another file's public name */
    }
    if (!old && user) {
        old = sym_lookup_layer(name, 0);
        if (old && (old->loc.file || old->k == SY_BUILTIN)) old = NULL;   /* a cart may reuse a library or builtin function name */
    }
    if (!old && p->priv) {
        Sym *b = sym_lookup_layer(name, 0);
        if (b && !b->loc.file && b->k != SY_BUILTIN) old = b;   /* built-in types */
    }
    if (old) {
        if (!old->loc.file) error_at(loc, "'%s' is a built-in name", name);
        error_at(loc, "'%s' is already defined at %s:%d", name, old->loc.file, old->loc.line);
    }
    Sym *s = ar_alloc(sizeof *s);
    s->user = user;
    s->k = k;
    s->name = name;
    s->loc = loc;
    if (p->priv) sym_define_private(s, p->file);
    else if (!file_is_module(p->file)) sym_define_global(s);
    sym_define_module(s, p->file);
    return s;
}

static void parse_params(Parser *p, Func *f, int types_optional) {
    expect_op(p, "(");
    int cap = 0;
    while (!is_op(p, ")")) {
        Param prm = {0};
        prm.loc = p->tok.loc;
        prm.name = expect_ident(p, "a parameter name");
        if (types_optional && !is_op(p, ":")) prm.texpr = NULL;
        else {
            expect_op(p, ":");
            prm.texpr = parse_type(p);
        }
        for (int i = 0; i < f->nparams; i++)
            if (!strcmp(f->params[i].name, prm.name)) error_at(prm.loc, "duplicate parameter '%s'", prm.name);
        PUSH(f->params, f->nparams, cap, prm);
        if (!is_op(p, ",")) break;
        next(p);
    }
    expect_op(p, ")");
    if (is_op(p, "->")) { next(p); f->ret_texpr = parse_type(p); }
}

/* Removes a replaced weak function from the program. */
static void drop_func(Program *P, Func *f) {
    for (int i = 0; i < P->nfuncs; i++)
        if (P->funcs[i] == f) {
            memmove(&P->funcs[i], &P->funcs[i + 1], sizeof(Func *) * (size_t)(P->nfuncs - i - 1));
            P->nfuncs--;
            return;
        }
}

/* Weak functions: returns the symbol a function definition binds to, or NULL when the
   definition is a weak one that an existing definition already replaces (it is then dropped). */
static Sym *define_fn(Parser *p, Func *f) {
    int user = !file_is_stdlib(p->file);
    Sym *old = p->priv ? NULL : file_is_module(p->file)
        ? sym_lookup_module(f->name, p->file, 1) : sym_lookup_layer(f->name, user);
    if (strchr(f->name, '.')) {
        if (p->priv || f->weak) error_at(f->loc, "a qualified function declaration must override a public weak function");
        old = sym_lookup_qualified(f->name, p->file);
        if (!old || old->k != SY_FUNC || !old->fn || !old->fn->weak)
            error_at(f->loc, "'%s' is not a public weak function", f->name);
        f->name = old->name;
    }
    if (old && old->k == SY_FUNC && old->fn) {
        if (old->fn->weak && !f->weak) {
            /* this definition replaces the weak one, wherever it is called from */
            f->overrides = old->fn;
            drop_func(p->P, old->fn);
            Sym *lib = user ? sym_lookup_layer(f->name, 0) : NULL;
            if (lib && lib->k == SY_FUNC && lib->fn == old->fn) lib->fn = f;   /* it had replaced a library default */
            old->fn = f;
            old->loc = f->loc;
            return old;
        }
        if (f->weak && !old->fn->weak) { f->overrides = NULL; return NULL; }
        if (f->weak && old->fn->weak)
            error_at(f->loc, "'%s' already has a weak definition at %s:%d (only one weak default is allowed)",
                     f->name, old->loc.file, old->loc.line);
    }
    if (!old && user && !p->priv && !file_is_module(p->file)) {
        Sym *lib = sym_lookup_layer(f->name, 0);
        if (lib && lib->k == SY_FUNC && lib->fn && lib->fn->weak) {
            /* a cart's function replaces a weak library function, for the library's calls too */
            Sym *s = new_global(p, SY_FUNC, f->name, f->loc);
            f->overrides = lib->fn;
            drop_func(p->P, lib->fn);
            lib->fn = f;
            return s;
        }
    }
    return new_global(p, SY_FUNC, f->name, f->loc);
}

static void parse_fn(Parser *p, int is_asm) {
    Func *f = ar_alloc(sizeof *f);
    next(p);   /* fn */
    f->loc = p->tok.loc;
    f->name = expect_ident(p, "a function name");
    if (is_op(p, ".")) { next(p); f->name = ar_printf("%s.%s", f->name, expect_ident(p, "a function name")); }
    f->is_asm = is_asm;
    f->weak = p->weak;
    parse_params(p, f, 0);
    Sym *s = define_fn(p, f);
    if (!s) {
        /* a weak default for a function defined already: parse it and drop it (its signature
           is still compared with the definition that replaces it) */
        if (is_asm) {
            skip_nl_only(p);
            if (!is_op(p, "{")) error_at(p->tok.loc, "expected '{' to start the asm body");
            f->asm_text = lex_raw_block(&p->L, &f->asm_loc);
            next(p);
        } else f->body = parse_block(p);
        Sym *strong = sym_lookup(f->name, p->file);
        f->sym = strong;
        Func *prev = strong->fn->overrides;
        if (prev && file_is_stdlib(prev->loc.file) == file_is_stdlib(f->loc.file))
            error_at(f->loc, "'%s' already has a weak definition at %s:%d (only one weak default is allowed)",
                     f->name, prev->loc.file, prev->loc.line);
        f->overrides = prev;
        strong->fn->overrides = f;
        return;
    }
    s->fn = f;
    f->sym = s;
    if (is_asm) {
        skip_nl_only(p);
        if (!is_op(p, "{")) error_at(p->tok.loc, "expected '{' to start the asm body");
        f->asm_text = lex_raw_block(&p->L, &f->asm_loc);
        next(p);
    } else {
        f->body = parse_block(p);
    }
    PUSH(p->P->funcs, p->P->nfuncs, p->P->capfuncs, f);
}

static void parse_struct(Parser *p) {
    next(p);
    StructDecl *d = ar_alloc(sizeof *d);
    d->loc = p->tok.loc;
    d->name = expect_ident(p, "a struct name");
    skip_nl_only(p);
    expect_op(p, "{");
    skip_nl(p);
    int c1 = 0, c2 = 0, c3 = 0, c4 = 0, n1 = 0, n2 = 0, n4 = 0;
    while (!is_op(p, "}")) {
        Loc floc = p->tok.loc;
        const char *fname = expect_ident(p, "a field name");
        for (int i = 0; i < d->nf; i++)
            if (!strcmp(d->fnames[i], fname)) error_at(floc, "duplicate field '%s'", fname);
        expect_op(p, ":");
        TypeExpr *t = parse_type(p);
        Expr *def = NULL;
        if (is_op(p, "=")) { next(p); def = parse_expr(p); }
        PUSH(d->fdefs, n4, c4, def);
        PUSH(d->fnames, n1, c1, fname);
        PUSH(d->ftypes, n2, c2, t);
        PUSH(d->flocs, d->nf, c3, floc);
        if (is_op(p, ",")) next(p);
        skip_nl(p);
    }
    next(p);
    Sym *s = new_global(p, SY_TYPE, d->name, d->loc);
    Type *t = ar_alloc(sizeof *t);
    t->k = TY_STRUCT;
    t->name = d->name;
    t->loc = d->loc;
    t->decl = d;
    d->ty = t;
    s->ty = t;
    PUSH(p->P->structs, p->P->nstructs, p->P->capstructs, d);
}

/* enum Name [: IntType] { A, B = expr, ... } */
static void parse_enum(Parser *p) {
    next(p);
    EnumDecl *d = ar_alloc(sizeof *d);
    d->loc = p->tok.loc;
    d->name = expect_ident(p, "an enum name");
    if (is_op(p, ":")) { next(p); d->base = parse_type(p); }
    skip_nl_only(p);
    expect_op(p, "{");
    skip_nl(p);
    int c1 = 0, c2 = 0, c3 = 0, n1 = 0, n2 = 0;
    while (!is_op(p, "}")) {
        Loc vloc = p->tok.loc;
        const char *name = expect_ident(p, "a variant name");
        for (int i = 0; i < n1; i++)
            if (!strcmp(d->names[i], name)) error_at(vloc, "duplicate variant '%s'", name);
        Expr *val = NULL;
        if (is_op(p, "=")) { next(p); val = parse_expr(p); }
        PUSH(d->names, n1, c1, name);
        PUSH(d->vals, n2, c2, val);
        PUSH(d->locs, d->n, c3, vloc);
        if (is_op(p, ",")) next(p);
        else if (p->tok.k != TK_NL && !is_op(p, "}"))
            error_at(p->tok.loc, "expected ',' or '}' after the variant, found %s", tok_desc(&p->tok));
        skip_nl(p);
    }
    next(p);
    if (!d->n) error_at(d->loc, "enum '%s' has no variants", d->name);
    Sym *s = new_global(p, SY_TYPE, d->name, d->loc);
    Type *t = ar_alloc(sizeof *t);
    t->k = TY_ENUM;
    t->name = d->name;
    t->loc = d->loc;
    t->edecl = d;
    t->size = t->align = 4;
    t->layout = 2;
    d->ty = t;
    s->ty = t;
    PUSH(p->P->enums, p->P->nenums, p->P->capenums, d);
}

static void parse_toplevel(Parser *p) {
    Loc loc = p->tok.loc;
    p->priv = 0;
    p->weak = 0;
    if (is_kw(p, "weak")) {
        /* `weak` (only here, so it is not a reserved word): a default another definition replaces */
        next(p);
        if (is_kw(p, "private")) error_at(p->tok.loc, "a weak function cannot be private (only a public function can be replaced)");
        if (!is_kw(p, "fn") && !is_kw(p, "asm")) error_at(p->tok.loc, "expected 'fn' or 'asm fn' after 'weak', found %s", tok_desc(&p->tok));
        p->weak = 1;
    }
    if (is_kw(p, "private")) {
        /* `private` (only here, so it is not a reserved word): the name is visible in this file only */
        next(p);
        static const char *decl[] = {"fn", "asm", "var", "const", "struct", "enum", "embed", "reg", NULL};
        int ok = 0;
        for (int i = 0; decl[i]; i++) ok |= is_kw(p, decl[i]);
        if (!ok) error_at(p->tok.loc, "expected a declaration after 'private' (fn, var, const, struct, enum, embed, reg), found %s", tok_desc(&p->tok));
        if (is_kw(p, "weak")) error_at(p->tok.loc, "a weak function cannot be private (write 'weak fn', without 'private')");
        p->priv = 1;
    }
    if (is_kw(p, "fn")) { parse_fn(p, 0); return; }
    if (is_kw(p, "asm")) {
        next(p);
        if (!is_kw(p, "fn")) error_at(p->tok.loc, "expected 'fn' after 'asm' (asm blocks belong inside functions)");
        parse_fn(p, 1);
        return;
    }
    if (is_kw(p, "struct")) { parse_struct(p); end_statement(p); return; }
    if (is_kw(p, "enum")) { parse_enum(p); end_statement(p); return; }
    if (is_kw(p, "import")) {
        next(p);
        if (p->tok.k != TK_STR) error_at(p->tok.loc, "expected a file name string after import");
        const char *path = p->tok.s;
        Loc ploc = p->tok.loc;
        next(p);
        const char *alias = NULL;
        if (is_kw(p, "as")) { next(p); alias = expect_ident(p, "an import alias"); }
        end_statement(p);
        compiler_import_as(p->C, p->file, path, alias, ploc);
        return;
    }
    if (is_kw(p, "cart")) {
        next(p);
        if (p->tok.k != TK_STR) error_at(p->tok.loc, "expected the cart title as a string");
        if (p->P->title) error_at(loc, "the cart title is already set");
        p->P->title = p->tok.s;
        next(p);
        if (is_op(p, ",")) {
            /* cart "Title", "CART-ID": the ID the memory card controller files saves under */
            next(p);
            if (p->tok.k != TK_STR) error_at(p->tok.loc, "expected the cart ID as a string, e.g. cart \"My Game\", \"MY-GAME\"");
            if (p->tok.slen == 0) error_at(p->tok.loc, "the cart ID is empty (leave it out to use a hash of the title)");
            if (p->tok.slen > 16) error_at(p->tok.loc, "the cart ID \"%s\" is longer than 16 characters", p->tok.s);
            for (size_t i = 0; i < p->tok.slen; i++)
                if ((unsigned char)p->tok.s[i] < 32 || (unsigned char)p->tok.s[i] > 126 || p->tok.s[i] == '"' || p->tok.s[i] == '\\')
                    error_at(p->tok.loc, "the cart ID must be printable ASCII without quotes or backslashes");
            p->P->cart_id = p->tok.s;
            next(p);
        }
        end_statement(p);
        return;
    }
    if (is_kw(p, "const")) {
        next(p);
        Loc nloc = p->tok.loc;
        const char *name = expect_ident(p, "a constant name");
        Sym *s = new_global(p, SY_CONST, name, nloc);
        if (is_op(p, ":")) { next(p); s->texpr = parse_type(p); }
        expect_op(p, "=");
        skip_nl_only(p);
        s->init = parse_expr(p);
        PUSH(p->P->consts, p->P->nconsts, p->P->capconsts, s);
        end_statement(p);
        return;
    }
    if (is_kw(p, "var")) {
        next(p);
        Loc nloc = p->tok.loc;
        const char *name = expect_ident(p, "a variable name");
        Sym *s = new_global(p, SY_GLOBAL, name, nloc);
        if (is_op(p, ":")) { next(p); s->texpr = parse_type(p); }
        if (is_op(p, "=")) { next(p); skip_nl_only(p); s->init = parse_expr(p); }
        if (!s->texpr && !s->init) error_at(nloc, "'%s' needs a type or an initial value", name);
        PUSH(p->P->globals, p->P->nglobals, p->P->capglobals, s);
        end_statement(p);
        return;
    }
    if (is_kw(p, "reg")) {
        next(p);
        Loc nloc = p->tok.loc;
        const char *name = expect_ident(p, "a register name");
        Sym *s = new_global(p, SY_REG, name, nloc);
        expect_op(p, ":");
        s->texpr = parse_type(p);
        expect_op(p, "@");
        s->init = parse_expr(p);
        PUSH(p->P->regs, p->P->nregs, p->P->capregs, s);
        end_statement(p);
        return;
    }
    if (is_kw(p, "embed")) {
        next(p);
        Loc nloc = p->tok.loc;
        const char *name = expect_ident(p, "an asset name");
        Sym *s = new_global(p, SY_EMBED, name, nloc);
        if (is_op(p, ":")) { next(p); s->texpr = parse_type(p); }
        expect_op(p, "=");
        if (p->tok.k != TK_STR) error_at(p->tok.loc, "expected the asset's file name as a string");
        s->path = p->tok.s;
        Loc ploc = p->tok.loc;
        next(p);
        if (is_op(p, ",")) {
            next(p);
            s->off_e = parse_expr(p);
            if (is_op(p, ",")) { next(p); s->len_e = parse_expr(p); }
        }
        s->data = compiler_load_binary(p->C, p->file, s->path, ploc, &s->datalen, &s->file_path);
        s->file_len = s->datalen;
        PUSH(p->P->datas, p->P->ndatas, p->P->capdatas, s);
        end_statement(p);
        return;
    }
    if (is_kw(p, "let")) error_at(loc, "use 'var' or 'const' at the top level ('let' is for locals)");
    error_at(loc, "expected a declaration (fn, var, const, struct, reg, embed, import), found %s", tok_desc(&p->tok));
}

void parse_file(Compiler *C, Program *P, const char *path, const char *text, size_t len) {
    Parser p = {0};
    p.C = C;
    p.P = P;
    p.file = path;
    lex_init(&p.L, path, text, len);
    next(&p);
    for (;;) {
        skip_nl(&p);
        if (p.tok.k == TK_EOF) break;
        parse_toplevel(&p);
    }
}
