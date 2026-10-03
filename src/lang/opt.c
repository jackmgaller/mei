/* AST optimisation passes, run on the checked program before code generation: inlining of
 * small functions, let forwarding and induction pointers. opt_program is the entry point. */
#include "internal.h"

#include <string.h>

#define PUSH(arr, n, cap, v) do { if ((n) == (cap)) { int nc_ = (cap) ? (cap) * 2 : 8; \
    void *np_ = ar_alloc(sizeof(*(arr)) * (size_t)nc_); if (n) memcpy(np_, (arr), sizeof(*(arr)) * (size_t)(n)); \
    (arr) = np_; (cap) = nc_; } (arr)[(n)++] = (v); } while (0)

/* ------------------------------------------------------------ inlining
 * A call to a small function whose whole body is `return E`, with E free of calls, is replaced
 * by E with the arguments in place of the parameters. Arguments must be free of calls and
 * I/O register reads (so evaluating them where E uses them, rather than all first, changes
 * nothing), and an argument E uses more than once must be cheap to repeat (a constant or a
 * variable). The function itself is still emitted for other uses (values, asm). */

#define INLINE_MAX_NODES 24

static int inl_count(Expr *e, Func *f, int *uses, int *ok) {
    if (!e || !*ok) return 0;
    int n = 1;
    switch (e->k) {
    case E_CALL:
        if (e->callee || e->indirect || bi_is_higher_order(e->bi) || e->bi == BI_LENGTH || e->bi == BI_NORMALIZE) { *ok = 0; return 0; }
        break;
    case E_FUNC: case E_MATCH: case E_ARRAY: case E_STRUCT: *ok = 0; return 0;
    case E_NAME:
        if (e->sym && e->sym->k == SY_LOCAL) {
            int found = 0;
            for (int i = 0; i < f->nparams; i++)
                if (f->params[i].local == e->sym->local) { uses[i]++; found = 1; }
            if (!found) *ok = 0;
        }
        break;
    default: break;
    }
    if (e->isconst && e->k != E_CONV) return n;
    n += inl_count(e->a, f, uses, ok) + inl_count(e->b, f, uses, ok);
    for (int i = 0; i < e->nargs; i++) n += inl_count(e->args[i], f, uses, ok);
    return n;
}

static int inlinable(Func *f) {
    if (f->inl) return f->inl == 1;
    f->inl = 2;
    if (f->is_asm || f->is_lambda || f->is_init || f->ncaps || !f->body || !f->ret || f->hidden_ret) return 0;
    if (f->ret->k == TY_VOID || ty_is_aggr(f->ret) || f->nparams > 8) return 0;
    Stmt *b = f->body;
    while (b && b->k == S_BLOCK && b->n == 1) b = b->list[0];
    if (!b || b->k != S_RETURN || !b->e) return 0;
    for (int i = 0; i < f->nparams; i++) if (f->params[i].local->addr_taken || f->params[i].local->in_asm) return 0;
    int uses[8] = {0}, ok = 1;
    int n = inl_count(b->e, f, uses, &ok);
    if (!ok || n > INLINE_MAX_NODES) return 0;
    f->inl = 1;
    f->inl_e = b->e;
    return 1;
}

/* Does evaluating e call a function or read an I/O register? */
static int inl_effects(Expr *e) {
    if (!e) return 0;
    if (e->k == E_CALL && (e->callee || e->indirect || bi_is_higher_order(e->bi))) return 1;
    if (e->k == E_FUNC || e->k == E_MATCH) return 1;
    if (e->k == E_NAME && e->sym && e->sym->k == SY_REG) return 1;
    if (e->isconst && e->k != E_CONV) return 0;
    if (inl_effects(e->a) || inl_effects(e->b)) return 1;
    for (int i = 0; i < e->nargs; i++) if (inl_effects(e->args[i])) return 1;
    return 0;
}

static int inl_cheap(Expr *e) {
    if (e->isconst) return 1;
    if (e->k == E_NAME) return 1;
    if (e->k == E_STR) return 1;
    if (e->k == E_CONV && !ty_is_aggr(e->ty)) return inl_cheap(e->a) && e->ty->size == 4 && e->conv_from && e->conv_from->size == 4
                                                && (e->ty->k == TY_FIXED) == (e->conv_from->k == TY_FIXED);
    return 0;
}

static Expr *inl_clone(Expr *e, Func *f, Expr **args) {
    if (!e) return NULL;
    if (f && e->k == E_NAME && e->sym && e->sym->k == SY_LOCAL)
        for (int i = 0; i < f->nparams; i++)
            if (f->params[i].local == e->sym->local) return inl_clone(args[i], NULL, NULL);
    Expr *c = ar_alloc(sizeof *c);
    *c = *e;
    c->a = inl_clone(e->a, f, args);
    c->b = inl_clone(e->b, f, args);
    if (e->nargs) {
        c->args = ar_alloc(sizeof(Expr *) * (size_t)e->nargs);
        for (int i = 0; i < e->nargs; i++) c->args[i] = inl_clone(e->args[i], f, args);
    }
    return c;
}

static void inline_expr(Expr *e);

static void inline_into(Expr *e) {
    Func *f = e->callee;
    if (!f || e->indirect || e->bi || !inlinable(f)) return;
    if (e->nargs != f->nparams) return;
    int uses[8] = {0}, ok = 1;
    inl_count(f->inl_e, f, uses, &ok);
    for (int i = 0; i < e->nargs; i++) {
        Expr *a = e->args[i];
        if (inl_effects(a)) return;
        if (uses[i] > 1 && !inl_cheap(a)) return;
        if (ty_is_aggr(a->ty) && !(is_lvalue(a) || (a->k == E_NAME && a->sym && a->sym->k == SY_DATA))) return;
    }
    Expr *c = inl_clone(f->inl_e, f, e->args);
    Loc loc = e->loc;
    *e = *c;
    e->loc = loc;
}

static void inline_expr(Expr *e) {
    if (!e) return;
    inline_expr(e->a);
    inline_expr(e->b);
    for (int i = 0; i < e->nargs; i++) inline_expr(e->args[i]);
    for (int i = 0; i < e->narms; i++) inline_expr(e->arms[i].value);
    if (e->k == E_CALL) inline_into(e);
}

static void inline_stmt(Stmt *s) {
    if (!s) return;
    for (int i = 0; i < s->n; i++) inline_stmt(s->list[i]);
    if (s->k != S_CONST) { inline_expr(s->e); inline_expr(s->e2); }
    inline_stmt(s->then);
    inline_stmt(s->els);
    for (int i = 0; i < s->narms; i++) inline_stmt(s->arms[i].body);
}

static int expr_calls(Expr *e) {
    if (!e) return 0;
    if (e->k == E_CALL && (e->callee || e->indirect || bi_is_higher_order(e->bi))) return 1;
    if (expr_calls(e->a) || expr_calls(e->b)) return 1;
    for (int i = 0; i < e->nargs; i++) if (expr_calls(e->args[i])) return 1;
    for (int i = 0; i < e->narms; i++) if (expr_calls(e->arms[i].value)) return 1;
    return 0;
}

static int stmt_calls(Stmt *s) {
    if (!s) return 0;
    for (int i = 0; i < s->n; i++) if (stmt_calls(s->list[i])) return 1;
    if (s->k != S_CONST && (expr_calls(s->e) || expr_calls(s->e2))) return 1;
    if (stmt_calls(s->then) || stmt_calls(s->els)) return 1;
    for (int i = 0; i < s->narms; i++) if (stmt_calls(s->arms[i].body)) return 1;
    return 0;
}

/* ---- let forwarding: `let x = E` with E built only from constants and locals (no memory
 * reads, no calls) is substituted into its uses when that cannot change its value: every use
 * when E is a constant, or else its only use, in the value of a later simple statement of the
 * same block, with nothing in between assigning a local E reads. x then needs no register. */

static int fw_local_ok(Local *l) { return l && !l->addr_taken && !l->in_asm && !l->captured; }

static int fw_pure(Expr *e) {
    if (!e) return 1;
    if (e->isconst && e->k != E_CONV && !ty_is_aggr(e->ty)) return 1;
    switch (e->k) {
    case E_NAME: return e->sym && e->sym->k == SY_LOCAL && fw_local_ok(e->sym->local) && !ty_is_aggr(e->ty);
    case E_UNARY: return e->op != U_DEREF && e->op != U_ADDR && fw_pure(e->a);
    case E_BINARY:
        if (e->a->ty->k == TY_MAT4 || ty_is_aggr(e->ty)) return 0;
        return fw_pure(e->a) && fw_pure(e->b);
    case E_CONV: return !ty_is_aggr(e->ty) && (!e->a || fw_pure(e->a));
    case E_FIELD: return !e->field && fw_pure(e->a);
    case E_CALL:
        if (e->callee || e->indirect || !e->bi || bi_is_higher_order(e->bi) || e->bi == BI_KIND || e->bi == BI_RAW) return 0;
        for (int i = 0; i < e->nargs; i++) if (!fw_pure(e->args[i])) return 0;
        return 1;
    default: return 0;
    }
}

static void fw_reads(Expr *e, Local **v, int *n) {
    if (!e) return;
    if (e->k == E_NAME && e->sym && e->sym->k == SY_LOCAL) { if (*n < 16) v[(*n)++] = e->sym->local; return; }
    if (e->isconst && e->k != E_CONV) return;
    fw_reads(e->a, v, n);
    fw_reads(e->b, v, n);
    for (int i = 0; i < e->nargs; i++) fw_reads(e->args[i], v, n);
}

/* Collects the E_NAME nodes in e that name x (up to max); returns how many there are. */
static int fw_uses_e(Expr *e, Local *x, Expr **out, int max, int n) {
    if (!e) return n;
    if (e->k == E_NAME && e->sym && e->sym->k == SY_LOCAL && e->sym->local == x) { if (n < max) out[n] = e; return n + 1; }
    if (e->k == E_FUNC) return n;
    n = fw_uses_e(e->a, x, out, max, n);
    n = fw_uses_e(e->b, x, out, max, n);
    for (int i = 0; i < e->nargs; i++) n = fw_uses_e(e->args[i], x, out, max, n);
    for (int i = 0; i < e->narms; i++) n = fw_uses_e(e->arms[i].value, x, out, max, n);
    return n;
}

static int fw_uses_s(Stmt *s, Local *x, Expr **out, int max, int n) {
    if (!s) return n;
    for (int i = 0; i < s->n; i++) n = fw_uses_s(s->list[i], x, out, max, n);
    if (s->k != S_CONST) { n = fw_uses_e(s->e, x, out, max, n); n = fw_uses_e(s->e2, x, out, max, n); }
    for (int i = 0; i < s->nips; i++) n = fw_uses_e(s->ipinit[i], x, out, max, n);   /* (a for loop's induction pointers) */
    if (s->k == S_ASM && s->asm_text && strstr(s->asm_text, "{")) n += 1000;   /* named in asm: keep it */
    n = fw_uses_s(s->then, x, out, max, n);
    n = fw_uses_s(s->els, x, out, max, n);
    for (int i = 0; i < s->narms; i++) n = fw_uses_s(s->arms[i].body, x, out, max, n);
    return n;
}

static Expr *fw_root(Expr *e) {
    while (e && (e->k == E_FIELD || e->k == E_INDEX) && e->a && e->a->ty->k != TY_PTR) e = e->a;
    return e;
}

static int fw_assigns(Stmt *s, Local *l) {
    if (!s) return 0;
    if (s->k == S_ASSIGN) {
        Expr *r = fw_root(s->e);
        if (r && r->k == E_NAME && r->sym && r->sym->k == SY_LOCAL && r->sym->local == l) return 1;
    }
    if (s->k == S_ASM) return 1;
    for (int i = 0; i < s->n; i++) if (fw_assigns(s->list[i], l)) return 1;
    if (fw_assigns(s->then, l) || fw_assigns(s->els, l)) return 1;
    for (int i = 0; i < s->narms; i++) if (fw_assigns(s->arms[i].body, l)) return 1;
    return 0;
}

static void fw_block(Stmt *b) {
    if (!b) return;
    if (b->k == S_BLOCK) {
        for (int i = 0; i < b->n; i++) {
            Stmt *s = b->list[i];
            if (s->k != S_VAR || !s->is_let || !s->e || !s->var) continue;
            Local *x = s->var;
            Expr *e = s->e;
            if (!fw_local_ok(x) || ty_is_aggr(x->ty) || e->ty != x->ty || !fw_pure(e)) continue;
            int isk = e->isconst && !ty_is_vec(x->ty) && x->ty->k != TY_FUNC;
            if (e->isconst && !isk) continue;   /* a vector constant: keep it in its register */
            if (!isk && e->k == E_NAME && e->sym && e->sym->k == SY_LOCAL) {
                /* a copy of a local that the rest of the block never assigns: use it directly */
                int assigned = 0;
                for (int j = i + 1; j < b->n && !assigned; j++) assigned = fw_assigns(b->list[j], e->sym->local);
                if (!assigned) isk = 1;
            }
            Expr *uses[64];
            int nu = 0;
            for (int j = i + 1; j < b->n; j++) nu = fw_uses_s(b->list[j], x, uses, 64, nu);
            if (nu == 0 || nu > 64) continue;
            if (!isk) {
                if (nu != 1) continue;
                /* the statement holding the use: a simple one, the use in its own value */
                int j = i + 1, found = -1;
                for (; j < b->n && found < 0; j++) {
                    Expr *one[1];
                    if (fw_uses_s(b->list[j], x, one, 1, 0)) found = j;
                }
                Stmt *t = b->list[found];
                if (t->k != S_VAR && t->k != S_ASSIGN && t->k != S_EXPR && t->k != S_RETURN && t->k != S_IF && t->k != S_MATCH) continue;
                Expr *one[1];
                if (!(fw_uses_e(t->e, x, one, 1, 0) || (t->k != S_IF && t->k != S_MATCH && fw_uses_e(t->e2, x, one, 1, 0)))) continue;
                Local *rd[16];
                int nr = 0;
                fw_reads(e, rd, &nr);
                if (nr >= 16) continue;
                int clash = 0;
                for (int k = 0; k < nr && !clash; k++) {
                    for (int m = i + 1; m < found && !clash; m++) if (fw_assigns(b->list[m], rd[k])) clash = 1;
                    if (t->k == S_ASSIGN && t->op >= 0) {
                        Expr *r = fw_root(t->e);
                        if (r && r->k == E_NAME && r->sym && r->sym->local == rd[k] && fw_uses_e(t->e, x, one, 1, 0)) clash = 1;
                    }
                }
                if (clash) continue;
            }
            for (int u = 0; u < nu; u++) {
                Loc loc = uses[u]->loc;
                *uses[u] = *inl_clone(e, NULL, NULL);
                uses[u]->loc = loc;
            }
            x->elided = 1;
            s->k = S_BLOCK;
            s->n = 0;
            s->e = NULL;
        }
    }
    for (int i = 0; i < b->n; i++) fw_block(b->list[i]);
    fw_block(b->then);
    fw_block(b->els);
    for (int i = 0; i < b->narms; i++) fw_block(b->arms[i].body);
}

/* ---- induction pointers: in `for i in lo..hi`, a[i] for a fixed array a (a global, const
 * data, a local array, or a pointer local the loop does not change) becomes *p, with p = &a[i]
 * set up with i and stepped by one element whenever i is: no index arithmetic per use. */

#define MAX_IPS 3

typedef struct { Expr *base; Expr **uses; int nuses, cap; } IpGroup;

static int ip_same_base(Expr *a, Expr *b) {
    return a->k == E_NAME && b->k == E_NAME && a->sym && b->sym &&
           (a->sym->k == SY_LOCAL ? b->sym->k == SY_LOCAL && a->sym->local == b->sym->local : a->sym == b->sym);
}

static int ip_base_ok(Expr *a, Stmt *body) {
    if (a->k != E_NAME || !a->sym) return 0;
    switch (a->sym->k) {
    case SY_GLOBAL: case SY_DATA: return a->ty->k == TY_ARRAY;
    case SY_LOCAL: {
        Local *l = a->sym->local;
        if (a->ty->k == TY_ARRAY) return 1;
        if (a->ty->k == TY_PTR) return !l->addr_taken && !l->in_asm && !fw_assigns(body, l);
        return 0;
    }
    default: return 0;
    }
}

static void ip_collect_e(Expr *e, Local *iv, Stmt *body, IpGroup *g, int *ng) {
    if (!e || e->k == E_FUNC) return;
    if (e->isconst && e->k != E_CONV) return;
    if (e->k == E_UNARY && e->op == U_ADDR && e->a->k == E_INDEX) {
        /* &a[i]: the whole address is the pointer (collected as the E_INDEX, rewritten below) */
        int before = 0;
        for (int k = 0; k < *ng; k++) before += g[k].nuses;
        ip_collect_e(e->a, iv, body, g, ng);
        int after = 0;
        for (int k = 0; k < *ng; k++) after += g[k].nuses;
        if (after > before) e->a->hid[0] = (Local *)e;   /* remember the & around it */
        return;
    }
    if (e->k == E_INDEX && !e->chk && e->b->k == E_NAME && e->b->sym && e->b->sym->k == SY_LOCAL && e->b->sym->local == iv
        && ip_base_ok(e->a, body) && e->ty->size > 0) {
        int k;
        for (k = 0; k < *ng; k++) if (ip_same_base(g[k].base, e->a)) break;
        if (k == *ng) {
            if (*ng == MAX_IPS) return;
            g[k] = (IpGroup){e->a, NULL, 0, 0};
            (*ng)++;
        }
        PUSH(g[k].uses, g[k].nuses, g[k].cap, e);
        return;
    }
    ip_collect_e(e->a, iv, body, g, ng);
    ip_collect_e(e->b, iv, body, g, ng);
    for (int i = 0; i < e->nargs; i++) ip_collect_e(e->args[i], iv, body, g, ng);
    for (int i = 0; i < e->narms; i++) ip_collect_e(e->arms[i].value, iv, body, g, ng);
}

static void ip_collect_s(Stmt *s, Local *iv, Stmt *body, IpGroup *g, int *ng) {
    if (!s) return;
    for (int i = 0; i < s->n; i++) ip_collect_s(s->list[i], iv, body, g, ng);
    if (s->k != S_CONST) { ip_collect_e(s->e, iv, body, g, ng); ip_collect_e(s->e2, iv, body, g, ng); }
    ip_collect_s(s->then, iv, body, g, ng);
    ip_collect_s(s->els, iv, body, g, ng);
    for (int i = 0; i < s->narms; i++) ip_collect_s(s->arms[i].body, iv, body, g, ng);
}

static Expr *ip_name(Local *l) {
    Expr *n = ar_alloc(sizeof *n);
    n->k = E_NAME;
    n->name = l->name;
    n->ty = l->ty;
    n->sym = ar_alloc(sizeof(Sym));
    n->sym->k = SY_LOCAL;
    n->sym->name = l->name;
    n->sym->local = l;
    n->sym->ty = l->ty;
    return n;
}

static void ip_stmt(Func *f, Stmt *s) {
    if (!s) return;
    for (int i = 0; i < s->n; i++) ip_stmt(f, s->list[i]);
    ip_stmt(f, s->then);
    ip_stmt(f, s->els);
    for (int i = 0; i < s->narms; i++) ip_stmt(f, s->arms[i].body);
    if (s->k == S_FOR && !s->e2->isconst && s->e2->k == E_NAME && s->e2->sym && s->e2->sym->k == SY_LOCAL) {
        Local *l = s->e2->sym->local;
        if (fw_local_ok(l) && l != s->var && ty_is_scalar(l->ty) && !fw_assigns(s->then, l)) s->end_direct = 1;
    }
    if (s->k != S_FOR || s->var->addr_taken || s->var->in_asm || s->var->captured) return;
    IpGroup g[MAX_IPS];
    int ng = 0;
    ip_collect_s(s->then, s->var, s->then, g, &ng);
    for (int k = 0; k < ng; k++) {
        Expr *u0 = g[k].uses[0];
        Type *el = u0->ty;
        Local *p = ar_alloc(sizeof *p);
        p->name = "";
        p->ty = ty_ptr(el);
        p->loc = u0->loc;
        p->immutable = 1;
        p->weight = (int64_t)16 * g[k].nuses + 8;
        PUSH(f->locals, f->nlocals, f->caplocals, p);
        /* p = &a[i], with i just set to lo */
        Expr *ix = ar_alloc(sizeof *ix);
        *ix = *u0;
        ix->a = inl_clone(u0->a, NULL, NULL);
        ix->b = inl_clone(u0->b, NULL, NULL);
        Expr *addr = ar_alloc(sizeof *addr);
        addr->k = E_UNARY; addr->op = U_ADDR; addr->loc = u0->loc; addr->a = ix; addr->ty = p->ty;
        if (ix->a->sym->k == SY_LOCAL && ix->a->ty->k == TY_ARRAY) ix->a->sym->local->addr_taken = 1;
        if (!s->ips) {
            s->ips = ar_alloc(sizeof(Local *) * MAX_IPS);
            s->ipinit = ar_alloc(sizeof(Expr *) * MAX_IPS);
            s->ipstep = ar_alloc(sizeof(int) * MAX_IPS);
        }
        s->ips[s->nips] = p;
        s->ipinit[s->nips] = addr;
        s->ipstep[s->nips] = el->size;
        s->nips++;
        for (int u = 0; u < g[k].nuses; u++) {
            Expr *e = g[k].uses[u];
            Expr *amp = (Expr *)e->hid[0];
            Loc loc = e->loc;
            memset(e, 0, sizeof *e);
            e->k = E_UNARY; e->op = U_DEREF; e->loc = loc; e->a = ip_name(p); e->ty = el;
            if (amp) { Type *t = amp->ty; *amp = *ip_name(p); amp->loc = loc; amp->ty = t; }
        }
    }
    s->narms = 0;
}

void opt_program(Program *P) {
    for (int i = 0; i < P->nfuncs; i++) {
        Func *f = P->funcs[i];
        if (f->is_asm || !f->body) continue;
        inline_stmt(f->body);
        ip_stmt(f, f->body);
        fw_block(f->body);
        /* a function whose only calls were inlined is now a leaf */
        if (f->has_call && !f->uses_xfm && !stmt_calls(f->body)) f->has_call = 0;
    }
}
