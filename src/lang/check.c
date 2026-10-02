/* Type checker: resolves names and types, folds constants, inserts implicit
 * conversions and collects per-function facts (locals, calls) for the code generator. */
#include "internal.h"

#include <string.h>
#include <stdio.h>

/* ------------------------------------------------------------------ types */

static Type builtin_types[TY_NULL + 1];
Type *ty_void, *ty_bool, *ty_s8, *ty_s16, *ty_s32, *ty_u8, *ty_u16, *ty_u32, *ty_fixed,
     *ty_vec2, *ty_vec3, *ty_vec4, *ty_ivec4, *ty_mat4, *ty_uint, *ty_ufixed, *ty_null;

static Type *mk_builtin(TyKind k, const char *name, int size, int align) {
    Type *t = &builtin_types[k];
    memset(t, 0, sizeof *t);
    t->k = k; t->name = name; t->size = size; t->align = align; t->layout = 2;
    return t;
}

static Sym *def_builtin(const char *name, SymKind k) {
    Sym *s = ar_alloc(sizeof *s);
    s->k = k;
    s->name = name;
    s->state = 2;
    sym_define_global(s);
    return s;
}

static Type *g_functypes;
static int g_lambda_n;

void types_init(void) {
    g_functypes = NULL;
    g_lambda_n = 0;
    ty_void = mk_builtin(TY_VOID, "void", 0, 1);
    ty_bool = mk_builtin(TY_BOOL, "bool", 1, 1);
    ty_s8 = mk_builtin(TY_S8, "s8", 1, 1);
    ty_s16 = mk_builtin(TY_S16, "s16", 2, 2);
    ty_s32 = mk_builtin(TY_S32, "s32", 4, 4);
    ty_u8 = mk_builtin(TY_U8, "u8", 1, 1);
    ty_u16 = mk_builtin(TY_U16, "u16", 2, 2);
    ty_u32 = mk_builtin(TY_U32, "u32", 4, 4);
    ty_fixed = mk_builtin(TY_FIXED, "fixed", 4, 4);
    ty_vec2 = mk_builtin(TY_VEC2, "vec2", 16, 4);
    ty_vec3 = mk_builtin(TY_VEC3, "vec3", 16, 4);
    ty_vec4 = mk_builtin(TY_VEC4, "vec4", 16, 4);
    ty_ivec4 = mk_builtin(TY_IVEC4, "ivec4", 16, 4);
    ty_mat4 = mk_builtin(TY_MAT4, "mat4", 64, 4);
    ty_uint = mk_builtin(TY_UINT, "integer constant", 4, 4);
    ty_ufixed = mk_builtin(TY_UFIXED, "fixed constant", 4, 4);
    ty_null = mk_builtin(TY_NULL, "null", 4, 4);
    Type *named[] = {ty_bool, ty_s8, ty_s16, ty_s32, ty_u8, ty_u16, ty_u32, ty_fixed,
                     ty_vec2, ty_vec3, ty_vec4, ty_ivec4, ty_mat4};
    for (size_t i = 0; i < sizeof named / sizeof named[0]; i++) def_builtin(named[i]->name, SY_TYPE)->ty = named[i];
    static const struct { const char *name; Builtin bi; } bis[] = {
        {"dot", BI_DOT}, {"cross", BI_CROSS}, {"len", BI_LEN}, {"bits", BI_BITS}, {"from_bits", BI_FROM_BITS},
        {"abs", BI_ABS}, {"min", BI_MIN}, {"max", BI_MAX}, {"clamp", BI_CLAMP}, {"lerp", BI_LERP},
        {"length", BI_LENGTH}, {"normalize", BI_NORMALIZE},
        {"nclip", BI_NCLIP}, {"otz", BI_OTZ}, {"clerp", BI_CLERP},
        {"__kind", BI_KIND}, {"__raw", BI_RAW},
        {"map", BI_MAP}, {"map_into", BI_MAP_INTO}, {"filter", BI_FILTER}, {"filter_into", BI_FILTER_INTO},
        {"reduce", BI_REDUCE}, {"each", BI_EACH},
    };
    for (size_t i = 0; i < sizeof bis / sizeof bis[0]; i++) def_builtin(bis[i].name, SY_BUILTIN)->bi = bis[i].bi;
}

Type *ty_ptr(Type *t) {
    if (!t->ptr_cache) {
        Type *p = ar_alloc(sizeof *p);
        p->k = TY_PTR; p->elem = t; p->size = 4; p->align = 4; p->layout = 2;
        t->ptr_cache = p;
    }
    return t->ptr_cache;
}

static void layout_struct(Type *t, Loc use);

Type *ty_array(Type *t, int64_t n) {
    for (Type *a = t->arr_list; a; a = a->arr_sib)
        if (a->n == n) return a;
    Type *a = ar_alloc(sizeof *a);
    a->k = TY_ARRAY; a->elem = t; a->n = n;
    a->size = (int)((int64_t)t->size * n);
    a->align = t->align;
    a->layout = 2;
    a->arr_sib = t->arr_list;
    t->arr_list = a;
    return a;
}

Type *ty_func(Type **params, int n, Type *ret) {
    for (Type *f = g_functypes; f; f = f->func_next) {
        if (f->elem != ret || f->nparams != n) continue;
        int same = 1;
        for (int i = 0; i < n; i++) if (f->params[i] != params[i]) same = 0;
        if (same) return f;
    }
    Type *f = ar_alloc(sizeof *f);
    f->k = TY_FUNC;
    f->elem = ret;
    f->nparams = n;
    f->params = ar_alloc(sizeof(Type *) * (size_t)(n ? n : 1));
    for (int i = 0; i < n; i++) f->params[i] = params[i];
    f->size = 16;   /* code address + 3 captured words */
    f->align = 4;
    f->layout = 2;
    f->func_next = g_functypes;
    g_functypes = f;
    return f;
}

Type *ty_base(Type *t) { return t->k == TY_ENUM && t->elem ? t->elem : t; }

const char *ty_str(Type *t) {
    switch (t->k) {
    case TY_FUNC: {
        Buf b = {0};
        buf_puts(&b, "fn(");
        for (int i = 0; i < t->nparams; i++) buf_printf(&b, "%s%s", i ? ", " : "", ty_str(t->params[i]));
        buf_puts(&b, ")");
        if (t->elem && t->elem->k != TY_VOID) buf_printf(&b, " -> %s", ty_str(t->elem));
        char *r = ar_strdup(b.p);
        buf_free(&b);
        return r;
    }
    case TY_PTR: return ar_printf("*%s", ty_str(t->elem));
    case TY_ARRAY: return ar_printf("[%lld]%s", (long long)t->n, ty_str(t->elem));
    default: return t->name;
    }
}

int ty_is_int(Type *t) { return t->k >= TY_S8 && t->k <= TY_U32; }
int ty_is_signed(Type *t) { t = ty_base(t); return t->k == TY_S8 || t->k == TY_S16 || t->k == TY_S32 || t->k == TY_FIXED || t->k == TY_UINT || t->k == TY_UFIXED; }
int ty_is_scalar(Type *t) { return (t->k >= TY_BOOL && t->k <= TY_FIXED) || t->k == TY_PTR || t->k == TY_NULL || t->k == TY_UINT || t->k == TY_UFIXED || t->k == TY_ENUM; }
int ty_is_vec(Type *t) { return t->k >= TY_VEC2 && t->k <= TY_IVEC4; }
int ty_is_aggr(Type *t) { return t->k == TY_STRUCT || t->k == TY_ARRAY || t->k == TY_MAT4; }
int ty_lanes(Type *t) { return t->k == TY_VEC2 ? 2 : t->k == TY_VEC3 ? 3 : 4; }
static int is_intish(Type *t) { return ty_is_int(t) || t->k == TY_UINT; }
static int is_fixedish(Type *t) { return t->k == TY_FIXED || t->k == TY_UFIXED; }
static int is_numeric(Type *t) { return is_intish(t) || is_fixedish(t); }

int fits_s18(int64_t v) { return v >= -131072 && v <= 131071; }

/* -------------------------------------------------------------- contexts */

typedef struct Scope {
    struct Scope *up;
    Local **locals; int n, cap;
} Scope;

typedef struct Ctx {
    Program *P;
    Func *fn;           /* NULL: constant context */
    Scope *scope;
    int loop_depth;
    int in_loop;
    struct Ctx *outer;  /* the function enclosing a function literal */
} Ctx;

#define PUSH(arr, n, cap, v) do { if ((n) == (cap)) { int nc_ = (cap) ? (cap) * 2 : 8; \
    void *np_ = ar_alloc(sizeof(*(arr)) * (size_t)nc_); if (n) memcpy(np_, (arr), sizeof(*(arr)) * (size_t)(n)); \
    (arr) = np_; (cap) = nc_; } (arr)[(n)++] = (v); } while (0)

static Stmt *g_loop_stack[256];
static int g_loop_n;

static Expr *check(Ctx *c, Expr *e, Type *want);
static Expr *coerce(Ctx *c, Expr *e, Type *to, const char *what);
static void resolve_const(Sym *s);
static void resolve_const_in(Sym *s, Ctx *in);
static void resolve_embed(Sym *s);
static Program *g_prog;

static void note_call(Ctx *c, Func *f) {
    if (!c->fn) return;
    for (int i = 0; i < c->fn->ncalls; i++) if (c->fn->calls[i] == f) return;
    PUSH(c->fn->calls, c->fn->ncalls, c->fn->capcalls, f);
}

static void note_ref(Ctx *c, Sym *s) {
    if (!c->fn) { s->reachable = 1; return; }
    for (int i = 0; i < c->fn->nrefs; i++) if (c->fn->refs[i] == s) return;
    PUSH(c->fn->refs, c->fn->nrefs, c->fn->caprefs, s);
}

static void check_signature(Func *f);

/* The type of a function used as a value. */
static Type *func_type_of(Func *f) {
    Type *ps[32];
    if (f->nparams > 32) error_at(f->loc, "too many parameters for a function value");
    for (int i = 0; i < f->nparams; i++) ps[i] = f->params[i].ty;
    return ty_func(ps, f->nparams, f->ret);
}

/* A compiler-made local (loop state of an intrinsic, match scrutinee): not in any scope. */
static Local *hidden_local(Ctx *c, Type *t, Loc loc) {
    Local *l = ar_alloc(sizeof *l);
    l->name = "";
    l->ty = t;
    l->loc = loc;
    int d = c->loop_depth > 5 ? 5 : c->loop_depth;
    l->weight = (int64_t)64 << (2 * d);
    PUSH(c->fn->locals, c->fn->nlocals, c->fn->caplocals, l);
    return l;
}

/* The assembly label of a global symbol: prefix + name, plus "$u" for a cart symbol that reuses a
   standard library name. */
static const char *sym_label(const char *prefix, Sym *s) {
    if (s->priv) return ar_printf("%s%s$p%d", prefix, s->name, s->priv);   /* private: per file */
    return ar_printf("%s%s%s", prefix, s->name, s->user && sym_lookup_layer(s->name, 0) ? "$u" : "");
}

/* "unknown name 'x'", or that it is private to another file. */
_Noreturn void error_unknown(Loc loc, const char *what, const char *name) {
    Sym *p = sym_private_elsewhere(name, loc.file);
    if (p) {
        const char *base = strrchr(p->loc.file, '/');
        error_at(loc, "'%s' is private to %s (declared at line %d), so it cannot be used from this file",
                 name, base ? base + 1 : p->loc.file, p->loc.line);
    }
    error_at(loc, "unknown %s '%s'", what, name);
}

static Sym *stdlib_fn(Ctx *c, const char *name, Loc loc) {
    Sym *s = sym_lookup_layer(name, 0);
    if (!s || s->k != SY_FUNC) error_at(loc, "this operation needs the standard library function '%s'", name);
    if (c->fn) { c->fn->has_call = 1; note_call(c, s->fn); }
    return s;
}

/* ---------------------------------------------------------- type resolution */

static int64_t const_int(Ctx *c, Expr *e, const char *what);

static void resolve_enum(Type *t);

/* Resolves a written type. `in` is the function whose body it appears in (array lengths may
   use its local constants), or NULL. */
static Type *resolve_type_in(TypeExpr *te, Ctx *in) {
    if (te->resolved) return te->resolved;
    Type *t;
    if (te->k == 3) {
        Type *ps[32];
        if (te->nparams > 32) error_at(te->loc, "too many parameters in a function type");
        for (int i = 0; i < te->nparams; i++) {
            ps[i] = resolve_type_in(te->params[i], in);
            if (ps[i]->k == TY_VOID) error_at(te->params[i]->loc, "parameters cannot be void");
        }
        Type *ret = te->elem ? resolve_type_in(te->elem, in) : ty_void;
        if (ret->k == TY_ARRAY) error_at(te->elem->loc, "functions cannot return arrays; wrap the array in a struct");
        t = ty_func(ps, te->nparams, ret);
    } else if (te->k == 1) t = ty_ptr(resolve_type_in(te->elem, in));
    else if (te->k == 2) {
        Ctx c = {.P = g_prog};
        int64_t n = const_int(in ? in : &c, te->len, "array length");
        if (n <= 0) error_at(te->len->loc, "array length must be positive (got %lld)", (long long)n);
        Type *el = resolve_type_in(te->elem, in);
        if (el->k == TY_STRUCT) layout_struct(el, te->loc);
        if (el->k == TY_VOID) error_at(te->loc, "arrays of void are not allowed");
        if (n * el->size > 0x200000) error_at(te->loc, "array is larger than 2 MB");
        t = ty_array(el, n);
    } else {
        Sym *s = sym_lookup(te->name, te->loc.file);
        if (!s) error_unknown(te->loc, "type", te->name);
        if (s->k != SY_TYPE) error_at(te->loc, "unknown type '%s'", te->name);
        t = s->ty;
        if (t->k == TY_ENUM) resolve_enum(t);
    }
    te->resolved = t;
    return t;
}

static Type *resolve_type(TypeExpr *te) { return resolve_type_in(te, NULL); }

static int align_up(int v, int a) { return (v + a - 1) / a * a; }

static void layout_struct(Type *t, Loc use) {
    if (t->k != TY_STRUCT || t->layout == 2) return;
    if (t->layout == 1) error_at(use, "struct '%s' contains itself", t->name);
    t->layout = 1;
    StructDecl *d = t->decl;
    t->fields = ar_alloc(sizeof(Field) * (size_t)(d->nf ? d->nf : 1));
    t->nfields = d->nf;
    int off = 0, align = 1;
    for (int i = 0; i < d->nf; i++) {
        Type *ft = resolve_type(d->ftypes[i]);
        if (ft->k == TY_STRUCT) layout_struct(ft, d->flocs[i]);
        if (ft->k == TY_ARRAY) { Type *b = ft; while (b->k == TY_ARRAY) b = b->elem; layout_struct(b, d->flocs[i]); }
        off = align_up(off, ft->align);
        t->fields[i] = (Field){d->fnames[i], ft, off, d->flocs[i]};
        off += ft->size;
        if (ft->align > align) align = ft->align;
    }
    t->align = align;
    t->size = align_up(off, align);
    if (t->size == 0) t->size = 0;
    t->layout = 2;
}

static Type *complete(Type *t, Loc loc) {
    if (t->k == TY_STRUCT) layout_struct(t, loc);
    if (t->k == TY_ENUM) resolve_enum(t);
    return t;
}

/* ---------------------------------------------------------- constants */

static int64_t norm(Type *t, int64_t v) {
    t = ty_base(t);
    switch (t->k) {
    case TY_BOOL: return v != 0;
    case TY_S8: return (int8_t)v;
    case TY_S16: return (int16_t)v;
    case TY_S32: case TY_FIXED: return (int32_t)(uint32_t)v;
    case TY_U8: return (uint8_t)v;
    case TY_U16: return (uint16_t)v;
    case TY_U32: case TY_PTR: case TY_NULL: return (uint32_t)v;
    default: return v;
    }
}

static int fits(Type *t, int64_t v) {
    switch (t->k) {
    case TY_S8: case TY_U8: return v >= -128 && v <= 255;
    case TY_S16: case TY_U16: return v >= -32768 && v <= 65535;
    case TY_S32: case TY_U32: return v >= -2147483648LL && v <= 4294967295LL;
    default: return 1;
    }
}

static Expr *mk_const(Expr *like, Type *t, int64_t v) {
    Expr *e = ar_alloc(sizeof *e);
    *e = *like;
    e->k = E_CONV;
    e->a = like;
    e->conv_from = like->ty;
    e->ty = t;
    e->isconst = 1;
    e->cval = norm(t, v);
    return e;
}

static void check_ufixed_range(Loc loc, int64_t v) {
    if (v < INT32_MIN || v > INT32_MAX) error_at(loc, "fixed-point constant out of range (-32768 .. 32767.99998)");
}

/* ------------------------------------------------------------- scopes */

static Local *lookup_local(Ctx *c, const char *name) {
    for (Scope *s = c->scope; s; s = s->up)
        for (int i = s->n - 1; i >= 0; i--)
            if (!strcmp(s->locals[i]->name, name)) return s->locals[i];
    return NULL;
}

static void check_new_name(Ctx *c, const char *name, Loc loc, const char *what) {
    if (c->scope)
        for (int i = 0; i < c->scope->n; i++)
            if (!strcmp(c->scope->locals[i]->name, name))
                error_at(loc, "'%s' is already declared in this block (line %d)", name, c->scope->locals[i]->loc.line);
    Sym *g = sym_lookup(name, loc.file);
    if (g && g->k == SY_TYPE) error_at(loc, "'%s' is a type name and cannot be used for a %s", name, what);
}

/* A local `const`: a name in the current block for a constant (the caller sets csym). */
static Local *declare_local_const(Ctx *c, const char *name, Loc loc) {
    check_new_name(c, name, loc, "constant");
    Local *l = ar_alloc(sizeof *l);
    l->name = name;
    l->loc = loc;
    l->immutable = 1;
    PUSH(c->scope->locals, c->scope->n, c->scope->cap, l);
    return l;
}

static Local *new_local(Ctx *c, const char *name, Type *t, Loc loc) {
    check_new_name(c, name, loc, "variable");
    Local *l = ar_alloc(sizeof *l);
    l->name = name;
    l->ty = t;
    l->loc = loc;
    if (c->scope) PUSH(c->scope->locals, c->scope->n, c->scope->cap, l);
    PUSH(c->fn->locals, c->fn->nlocals, c->fn->caplocals, l);
    return l;
}

/* ------------------------------------------------------------ helpers */

static int is_lvalue(Expr *e) {
    switch (e->k) {
    case E_NAME: return e->sym && (e->sym->k == SY_LOCAL || e->sym->k == SY_GLOBAL || e->sym->k == SY_REG || e->sym->k == SY_DATA);
    case E_INDEX: return e->a->ty->k == TY_PTR || is_lvalue(e->a) || ty_is_aggr(e->a->ty);
    case E_FIELD:
        if (e->field) return e->a->ty->k == TY_PTR || is_lvalue(e->a) || ty_is_aggr(e->a->ty);
        return e->nlanes == 1 && is_lvalue(e->a);
    case E_UNARY: return e->op == U_DEREF;
    default: return 0;
    }
}

/* Why an expression cannot be assigned to, or NULL if it can. */
static const char *not_assignable(Expr *e) {
    switch (e->k) {
    case E_NAME:
        if (!e->sym) return "it is not a variable";
        if (e->sym->k == SY_LOCAL) {
            Local *l = e->sym->local;
            if (l->is_loopvar) return "it is the loop variable (use a separate variable or a while loop)";
            if (l->is_capture) return ar_printf("'%s' is a copy captured by the function literal: captures are copied when "
                                                "the literal is evaluated and are read-only (to share a changing value, use a "
                                                "global, or capture a pointer to it)", l->name);
            if (l->immutable) return ty_is_aggr(l->ty) && l->is_param
                ? "struct/array/mat4 parameters are passed by reference and are read-only; pass a pointer to modify the caller's value"
                : "it was declared with 'let' (use 'var' for a variable you assign to)";
            return NULL;
        }
        if (e->sym->k == SY_GLOBAL || e->sym->k == SY_REG) return NULL;
        if (e->sym->k == SY_DATA) return "constant data lives in ROM and is read-only";
        return "it is not a variable";
    case E_INDEX:
        if (e->a->ty->k == TY_PTR) return NULL;
        if (e->a->ty->k == TY_ARRAY || e->a->ty->k == TY_MAT4) return not_assignable(e->a);
        return "it is not a variable";
    case E_FIELD:
        if (e->field && e->a->ty->k == TY_PTR) return NULL;
        if (!e->field && e->nlanes != 1) return "multi-lane swizzles cannot be assigned; assign lanes one at a time";
        return not_assignable(e->a);
    case E_UNARY: if (e->op == U_DEREF) return NULL; return "it is not a variable";
    default: return "it is not a variable";
    }
}

static void mark_addr_taken(Expr *e) {
    switch (e->k) {
    case E_NAME: if (e->sym && e->sym->k == SY_LOCAL) e->sym->local->addr_taken = 1; break;
    case E_INDEX: if (e->a->ty->k != TY_PTR) mark_addr_taken(e->a); break;
    case E_FIELD: if (e->a->ty->k != TY_PTR) mark_addr_taken(e->a); break;
    default: break;
    }
}

static const char *conv_hint(Type *from, Type *to) {
    if (ty_is_int(from) && to->k == TY_FIXED) return "; convert with 'as fixed' (scales by 65536)";
    if (from->k == TY_FIXED && ty_is_int(to)) return ar_printf("; convert with 'as %s' (rounds down)", to->name);
    if (from->k == TY_UFIXED && ty_is_int(to)) return ar_printf("; convert with 'as %s'", to->name);
    if (from->k == TY_ARRAY && to->k == TY_PTR) return "; take the address of an element with '&a[0]'";
    if (ty_is_vec(from) && ty_is_vec(to)) return ar_printf("; convert with 'as %s'", to->name);
    if ((ty_is_int(from) && to->k == TY_PTR) || (from->k == TY_PTR && ty_is_int(to)) || (from->k == TY_PTR && to->k == TY_PTR))
        return ar_printf("; convert with 'as %s'", ty_str(to));
    if (from->k == TY_UINT && to->k == TY_PTR) return "; use 'null' or an explicit 'as' conversion";
    if (to->k == TY_ENUM && (is_intish(from) || from->k == TY_ENUM))
        return ar_printf("; enums do not mix with integers: use a variant such as %s.%s, or 'as %s'", to->name,
                         to->nvariants ? to->vnames[0] : "X", to->name);
    if (from->k == TY_ENUM && is_intish(to)) return ar_printf("; convert with 'as %s'", to->name);
    if (from->k == TY_FUNC && to->k == TY_FUNC) return "; function types must match exactly";
    return "";
}

/* Implicit conversion (assignment, argument passing, return). */
static Expr *coerce(Ctx *c, Expr *e, Type *to, const char *what) {
    (void)c;
    Type *from = e->ty;
    /* untyped types belong to compile-time constants only (they are folded below) */
    if ((from->k == TY_UINT || from->k == TY_UFIXED) && !e->isconst)
        error_at(e->loc, "internal compiler error: untyped value that is not a constant");
    if (from == to) return e;
    if (to->k == TY_VOID) error_at(e->loc, "%s has no value", what);
    if (from->k == TY_UINT) {
        if (ty_is_int(to)) {
            if (!fits(to, e->cval)) error_at(e->loc, "constant %lld does not fit in %s (%s)", (long long)e->cval, to->name, what);
            return mk_const(e, to, e->cval);
        }
        if (to->k == TY_FIXED) {
            if (e->cval < -32768 || e->cval > 32767) error_at(e->loc, "constant %lld is out of range for fixed (-32768 .. 32767)", (long long)e->cval);
            return mk_const(e, to, e->cval * 65536);
        }
    }
    if (from->k == TY_UFIXED && to->k == TY_FIXED) { check_ufixed_range(e->loc, e->cval); return mk_const(e, to, e->cval); }
    if (from->k == TY_NULL && (to->k == TY_PTR || to->k == TY_FUNC)) return mk_const(e, to, 0);
    if (ty_is_int(from) && ty_is_int(to)) {
        if (e->isconst) return mk_const(e, to, e->cval);
        Expr *x = ar_alloc(sizeof *x);
        x->k = E_CONV; x->loc = e->loc; x->a = e; x->conv_from = from; x->ty = to;
        return x;
    }
    if (from->k == TY_PTR && to->k == TY_PTR && (to->elem == ty_u8 || from->elem->k == TY_VOID)) {
        Expr *x = ar_alloc(sizeof *x);
        x->k = E_CONV; x->loc = e->loc; x->a = e; x->conv_from = from; x->ty = to;
        x->isconst = e->isconst; x->cval = e->cval;
        return x;
    }
    if (from->k == TY_ARRAY && to->k == TY_PTR && (to->elem == from->elem || to->elem == ty_u8) && is_lvalue(e)) {
        /* array decays to a pointer to its first element */
        mark_addr_taken(e);
        Expr *x = ar_alloc(sizeof *x);
        x->k = E_UNARY; x->op = U_ADDR; x->loc = e->loc; x->a = e; x->ty = ty_ptr(from->elem);
        if (to != x->ty) {
            Expr *y = ar_alloc(sizeof *y);
            y->k = E_CONV; y->loc = e->loc; y->a = x; y->conv_from = x->ty; y->ty = to;
            return y;
        }
        return x;
    }
    error_at(e->loc, "type mismatch: %s is %s, expected %s%s", what, ty_str(from), ty_str(to), conv_hint(from, to));
}

/* Default type of an untyped constant. */
static Type *default_type(Expr *e) {
    if (e->ty->k == TY_UINT) return ty_s32;
    if (e->ty->k == TY_UFIXED) return ty_fixed;
    return e->ty;
}

static int64_t const_int(Ctx *c, Expr *e, const char *what) {
    Expr *x = check(c, e, NULL);
    if (!x->isconst || !is_intish(x->ty)) error_at(e->loc, "%s must be an integer constant", what);
    return x->cval;
}

/* ------------------------------------------------------------- folding */

static int64_t fold_bin(Loc loc, OpKind op, Type *t, int64_t a, int64_t b) {
    int untyped = t->k == TY_UINT;
    int fx = t->k == TY_FIXED || t->k == TY_UFIXED;
    int sgn = ty_is_signed(t);
    uint32_t ua = (uint32_t)a, ub = (uint32_t)b;
    int64_t r;
    switch (op) {
    case B_ADD: if (untyped || t->k == TY_UFIXED) { if (__builtin_add_overflow(a, b, &r)) goto big; return r; } return norm(t, (int64_t)(ua + ub));
    case B_SUB: if (untyped || t->k == TY_UFIXED) { if (__builtin_sub_overflow(a, b, &r)) goto big; return r; } return norm(t, (int64_t)(ua - ub));
    case B_MUL:
        if (fx) { int64_t p = a * b; return t->k == TY_UFIXED ? (p >> 16) : norm(t, p >> 16); }
        if (untyped) { if (__builtin_mul_overflow(a, b, &r)) goto big; return r; }
        return norm(t, (int64_t)(ua * ub));
    case B_DIV: case B_MOD:
        if (b == 0) error_at(loc, "division by zero in a constant expression");
        if (fx && op == B_DIV) { int64_t q = (a * 65536) / b; return t->k == TY_UFIXED ? q : norm(t, q); }
        if (untyped || (fx && op == B_MOD)) return op == B_DIV ? a / b : a % b;
        if (sgn) {
            int32_t sa = (int32_t)ua, sb = (int32_t)ub;
            if (sa == INT32_MIN && sb == -1) return op == B_DIV ? norm(t, sa) : 0;
            return norm(t, op == B_DIV ? sa / sb : sa % sb);
        }
        return norm(t, op == B_DIV ? ua / ub : ua % ub);
    case B_AND: return untyped ? (a & b) : norm(t, ua & ub);
    case B_OR: return untyped ? (a | b) : norm(t, ua | ub);
    case B_XOR: return untyped ? (a ^ b) : norm(t, ua ^ ub);
    case B_SHL:
        if (untyped) { if (b < 0 || b > 62) error_at(loc, "constant shift count out of range"); return a << b; }
        return norm(t, (int64_t)(ua << (ub & 31)));
    case B_SHR:
        if (untyped) { if (b < 0 || b > 63) error_at(loc, "constant shift count out of range"); return a >> b; }
        if (sgn) return norm(t, (int64_t)((int32_t)ua >> (ub & 31)));
        return norm(t, ua >> (ub & 31));
    default: break;
    }
    return 0;
big:
    error_at(loc, "constant expression overflows");
}

static int fold_cmp(OpKind op, Type *t, int64_t a, int64_t b) {
    if (!ty_is_signed(t) && t->k != TY_UINT) { a = (uint32_t)a; b = (uint32_t)b; }
    switch (op) {
    case B_EQ: return a == b;
    case B_NE: return a != b;
    case B_LT: return a < b;
    case B_LE: return a <= b;
    case B_GT: return a > b;
    case B_GE: return a >= b;
    default: return 0;
    }
}

/* ------------------------------------------------------------ captures */

/* Is `name` a local of this function or of a function around it (for function literals)? */
static int is_local_name(Ctx *c, const char *name) {
    for (Ctx *o = c; o; o = o->outer)
        if (o->fn && lookup_local(o, name)) return 1;
    return 0;
}

/* A function literal (context c) uses `name`, a local of an enclosing function: the literal
   gets a read-only copy, taken when the literal is evaluated. Returns the copy, or NULL when
   no enclosing function has such a local. Nested literals capture through each level. */
static Local *capture(Ctx *c, const char *name, Loc loc) {
    Func *f = c->fn;
    for (int i = 0; i < f->ncaps; i++) if (!strcmp(f->caps[i]->name, name)) return f->caps[i];
    Ctx *o = c->outer;
    if (!o->fn) return NULL;
    Local *ol = lookup_local(o, name);
    if (!ol && o->outer) ol = capture(o, name, loc);
    if (!ol) return NULL;
    Type *t = ol->ty;
    if (t->k == TY_FUNC)
        error_at(loc, "a function literal cannot capture '%s': it is a function value (4 words), and a function value "
                 "holds at most 3 captured words (pass it as an argument, or keep it in a global)", name);
    if (ty_is_vec(t))
        error_at(loc, "a function literal cannot capture '%s': vectors (%s) cannot be captured; copy the lanes you need "
                 "into locals first (let %s_x = %s.x) and use those, or capture a pointer", name, ty_str(t), name, name);
    if (t->k == TY_STRUCT || t->k == TY_MAT4)
        error_at(loc, "a function literal cannot capture '%s': %s values cannot be captured; copy the fields you need "
                 "into locals first and use those, or capture a pointer to data that outlives the function", name, ty_str(t));
    if (t->k == TY_ARRAY)
        error_at(loc, "a function literal cannot capture '%s': arrays cannot be captured; copy the elements you need "
                 "into locals first, or capture a pointer to data that outlives the function (a global array)", name);
    if (!ty_is_scalar(t)) error_at(loc, "a function literal cannot capture '%s' (%s)", name, ty_str(t));
    Local *l = ar_alloc(sizeof *l);
    l->name = ol->name;
    l->ty = t;
    l->loc = loc;
    l->immutable = 1;
    l->is_param = 1;
    l->is_capture = 1;
    l->points_local = ol->points_local;
    PUSH(f->locals, f->nlocals, f->caplocals, l);
    if (f->ncaps == f->capcaps) {
        int nc = f->capcaps ? f->capcaps * 2 : 4;
        Local **nl = ar_alloc(sizeof(Local *) * (size_t)nc), **no = ar_alloc(sizeof(Local *) * (size_t)nc);
        Loc *nlc = ar_alloc(sizeof(Loc) * (size_t)nc);
        if (f->ncaps) {
            memcpy(nl, f->caps, sizeof(Local *) * (size_t)f->ncaps);
            memcpy(no, f->cap_outer, sizeof(Local *) * (size_t)f->ncaps);
            memcpy(nlc, f->cap_locs, sizeof(Loc) * (size_t)f->ncaps);
        }
        f->caps = nl; f->cap_outer = no; f->cap_locs = nlc; f->capcaps = nc;
    }
    f->caps[f->ncaps] = l;
    f->cap_outer[f->ncaps] = ol;
    f->cap_locs[f->ncaps] = loc;
    f->ncaps++;
    int d = o->loop_depth > 6 ? 6 : o->loop_depth;
    ol->weight += (int64_t)1 << (2 * d);
    return l;
}

/* Does this pointer expression hold the address of local storage of the current function? */
static int refs_local_storage(Expr *e) {
    if (!e) return 0;
    switch (e->k) {
    case E_UNARY:
        if (e->op != U_ADDR) return 0;
        for (Expr *x = e->a; x;) {
            if (x->k == E_NAME) return x->sym && x->sym->k == SY_LOCAL && !x->sym->local->is_param;
            if ((x->k == E_FIELD || x->k == E_INDEX) && x->a->ty->k != TY_PTR) { x = x->a; continue; }
            return 0;
        }
        return 0;
    case E_NAME: return e->sym && e->sym->k == SY_LOCAL && e->sym->local->points_local;
    case E_CONV: return refs_local_storage(e->a);
    case E_BINARY: return e->ty->k == TY_PTR && (refs_local_storage(e->a) || refs_local_storage(e->b));
    default: return 0;
    }
}

/* ------------------------------------------------------------ expressions */

static const char *g_in_local_const;   /* the local constant whose value is being checked */

static Expr *check_name(Ctx *c, Expr *e) {
    Sym *s = NULL;
    if (c->fn) {
        Local *l = lookup_local(c, e->name);
        if (l && l->csym) { s = l->csym; l = NULL; }
        else if (!l)
            /* a local constant of an enclosing function needs no capture */
            for (Ctx *o = c->outer; o && o->fn; o = o->outer) {
                Local *ol = lookup_local(o, e->name);
                if (ol) { if (ol->csym) s = ol->csym; break; }
            }
        if ((l || (!s && c->outer && is_local_name(c, e->name))) && g_in_local_const)
            error_at(e->loc, "a constant cannot use the variable '%s' (constants are fixed when the cart is built)", e->name);
        if (l) {
            Sym *s = ar_alloc(sizeof *s);
            s->k = SY_LOCAL; s->name = l->name; s->local = l; s->ty = l->ty;
            e->sym = s;
            e->ty = l->ty;
            int d = c->loop_depth > 6 ? 6 : c->loop_depth;
            l->weight += (int64_t)1 << (2 * d);
            return e;
        }
        if (!s && c->outer && (l = capture(c, e->name, e->loc))) {
            Sym *s = ar_alloc(sizeof *s);
            s->k = SY_LOCAL; s->name = l->name; s->local = l; s->ty = l->ty;
            e->sym = s;
            e->ty = l->ty;
            int d = c->loop_depth > 6 ? 6 : c->loop_depth;
            l->weight += (int64_t)1 << (2 * d);
            return e;
        }
    }
    if (!s) s = sym_lookup(e->name, e->loc.file);
    if (!s) error_unknown(e->loc, "name", e->name);
    e->sym = s;
    switch (s->k) {
    case SY_CONST:
        resolve_const(s);
        if (s->k == SY_CONST) {
            e->ty = s->ty;
            e->isconst = 1;
            e->cval = s->cval;
            memcpy(e->cvec, s->cvec, sizeof e->cvec);
            return e;
        }
        /* became SY_DATA */
        /* fallthrough */
    case SY_DATA:
        resolve_const(s);
        note_ref(c, s);
        e->ty = s->ty;
        return e;
    case SY_GLOBAL:
        if (!c->fn) error_at(e->loc, "a constant cannot use the variable '%s' (constants are fixed when the cart is built)", s->name);
        if (!s->ty) error_at(e->loc, "'%s' is used in its own initialiser", s->name);
        e->ty = s->ty;
        return e;
    case SY_REG:
        e->ty = s->ty;
        if (c->fn) c->fn->uses_io += 1 << (2 * (c->loop_depth > 6 ? 6 : c->loop_depth));
        return e;
    case SY_EMBED:
        resolve_embed(s);
        note_ref(c, s);
        e->ty = s->ty;
        return e;
    case SY_FUNC:
        /* a function used as a value: its address */
        check_signature(s->fn);
        if (c->fn) note_call(c, s->fn);
        e->ty = func_type_of(s->fn);
        return e;
    case SY_TYPE: error_at(e->loc, "'%s' is a type, not a value", s->name);
    case SY_BUILTIN: error_at(e->loc, "'%s' is a built-in function; call it with %s(...)", s->name, s->name);
    default: error_at(e->loc, "'%s' cannot be used here", s->name);
    }
}

/* Unifies the operand types of an arithmetic/comparison operator. */
static Type *arith_type(Expr *e, Type *a, Type *b, const char *opname) {
    if (a->k == TY_UINT && b->k == TY_UINT) return ty_uint;
    if ((a->k == TY_UFIXED || a->k == TY_UINT) && (b->k == TY_UFIXED || b->k == TY_UINT)) return ty_ufixed;
    if (is_fixedish(a) && is_fixedish(b)) return ty_fixed;
    if (a->k == TY_FIXED && (b->k == TY_UINT || b->k == TY_UFIXED)) return ty_fixed;
    if (b->k == TY_FIXED && (a->k == TY_UINT || a->k == TY_UFIXED)) return ty_fixed;
    if (is_intish(a) && is_intish(b)) {
        int au = a->k == TY_U32, bu = b->k == TY_U32;
        int as = a->k == TY_S8 || a->k == TY_S16 || a->k == TY_S32;
        int bs = b->k == TY_S8 || b->k == TY_S16 || b->k == TY_S32;
        if ((au && bs) || (bu && as))
            error_at(e->loc, "cannot mix signed and unsigned values in '%s' (%s and %s); convert one with 'as'", opname, a->name, b->name);
        if (au || bu) return ty_u32;
        return ty_s32;
    }
    return NULL;
}

static const char *op_name(OpKind op) {
    static const char *n[] = {"+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>", "==", "!=", "<", "<=", ">", ">=",
                              "&&", "||", "-", "!", "~", "&", "*"};
    return n[op];
}

static Expr *coerce_operand(Ctx *c, Expr *e, Type *t) {
    if (e->ty == t) return e;
    if (t == ty_ufixed && e->ty->k == TY_UINT) {
        int64_t v;
        if (__builtin_mul_overflow(e->cval, (int64_t)65536, &v)) error_at(e->loc, "constant out of range");
        check_ufixed_range(e->loc, v);
        return mk_const(e, ty_ufixed, v);
    }
    if (t->k == TY_FIXED || (ty_is_int(t) && (e->ty->k == TY_UINT))) return coerce(c, e, t, "operand");
    return e;   /* int widening: registers already hold 32-bit values */
}

static void vec_const_fold(Expr *e, Expr *a, Expr *b, OpKind op) {
    if (!a->isconst || !b->isconst) return;
    for (int i = 0; i < 4; i++) {
        uint32_t x = (uint32_t)a->cvec[i], y = (uint32_t)b->cvec[i];
        e->cvec[i] = (int32_t)(op == B_ADD ? x + y : x - y);
    }
    e->isconst = 1;
}

static Expr *check_binary(Ctx *c, Expr *e) {
    e->a = check(c, e->a, NULL);
    e->b = check(c, e->b, NULL);
    Type *a = e->a->ty, *b = e->b->ty;
    OpKind op = e->op;
    const char *on = op_name(op);

    if (op == B_LAND || op == B_LOR) {
        if (a->k != TY_BOOL) error_at(e->a->loc, "'%s' needs bool operands, found %s", on, ty_str(a));
        if (b->k != TY_BOOL) error_at(e->b->loc, "'%s' needs bool operands, found %s", on, ty_str(b));
        e->ty = ty_bool;
        if (e->a->isconst && e->b->isconst) { e->isconst = 1; e->cval = op == B_LAND ? (e->a->cval && e->b->cval) : (e->a->cval || e->b->cval); }
        return e;
    }

    /* vectors and matrices */
    if (ty_is_vec(a) || ty_is_vec(b) || a->k == TY_MAT4 || b->k == TY_MAT4) {
        if (a->k == TY_MAT4 && b->k == TY_MAT4 && op == B_MUL) {
            Sym *s = stdlib_fn(c, "mat4_mul", e->loc);
            Expr *call = ar_alloc(sizeof *call);
            call->k = E_CALL; call->loc = e->loc; call->ty = ty_mat4; call->callee = s->fn;
            call->args = ar_alloc(sizeof(Expr *) * 2);
            call->args[0] = e->a; call->args[1] = e->b; call->nargs = 2;
            return call;
        }
        if (a->k == TY_MAT4 && (b->k == TY_VEC4 || b->k == TY_VEC3) && op == B_MUL) {
            e->ty = b;
            if (c->fn) c->fn->uses_xfm = 1;
            return e;
        }
        if (ty_is_vec(a) && a == b && (op == B_ADD || op == B_SUB)) { e->ty = a; vec_const_fold(e, e->a, e->b, op); return e; }
        if (ty_is_vec(a) && a == b && op == B_MUL && a->k != TY_IVEC4) { e->ty = a; return e; }
        if (ty_is_vec(a) && a->k != TY_IVEC4 && (op == B_MUL || op == B_DIV) && (is_fixedish(b) || b->k == TY_UINT)) {
            e->b = coerce(c, e->b, ty_fixed, "the scale factor");
            if (op == B_DIV && e->b->isconst && e->b->cval == 0) error_at(e->b->loc, "division by zero");
            e->ty = a;
            return e;
        }
        if (ty_is_vec(b) && b->k != TY_IVEC4 && op == B_MUL && (is_fixedish(a) || a->k == TY_UINT)) {
            /* f * v: put the vector on the left */
            Expr *t = e->a; e->a = e->b; e->b = coerce(c, t, ty_fixed, "the scale factor");
            e->ty = b;
            return e;
        }
        if (ty_is_vec(a) && ty_is_vec(b) && a != b)
            error_at(e->loc, "'%s' needs vectors of the same type (%s and %s); convert with 'as'", on, a->name, b->name);
        if ((op == B_EQ || op == B_NE) && a == b)
            error_at(e->loc, "vectors cannot be compared with '%s'; compare their lanes", on);
        error_at(e->loc, "operator '%s' is not defined for %s and %s", on, ty_str(a), ty_str(b));
    }

    /* enums: comparisons between values of one enum */
    if (a->k == TY_ENUM || b->k == TY_ENUM) {
        if (op >= B_EQ && op <= B_GE) {
            if (a != b) error_at(e->loc, "cannot compare %s with %s%s", ty_str(a), ty_str(b),
                                 is_intish(a) || is_intish(b) ? "; convert with 'as' (enums do not mix with integers)" : "");
            e->ty = ty_bool;
            e->conv_from = a;
            if (e->a->isconst && e->b->isconst) { e->isconst = 1; e->cval = fold_cmp(op, a, e->a->cval, e->b->cval); }
            return e;
        }
        error_at(e->loc, "operator '%s' is not defined for enum %s; convert with 'as' to do arithmetic",
                 on, a->k == TY_ENUM ? a->name : b->name);
    }

    /* function values: == and != only */
    if (a->k == TY_FUNC || b->k == TY_FUNC) {
        if (op == B_EQ || op == B_NE) {
            int ok = a == b || (a->k == TY_NULL && b->k == TY_FUNC) || (b->k == TY_NULL && a->k == TY_FUNC);
            if (!ok) error_at(e->loc, "cannot compare %s with %s", ty_str(a), ty_str(b));
            if (a->k == TY_NULL) e->a = coerce(c, e->a, b, "operand");
            if (b->k == TY_NULL) e->b = coerce(c, e->b, a, "operand");
            e->conv_from = ty_u32;
            e->ty = ty_bool;
            return e;
        }
        error_at(e->loc, "operator '%s' is not defined for function values", on);
    }

    /* pointers */
    if (a->k == TY_PTR || b->k == TY_PTR || a->k == TY_NULL || b->k == TY_NULL) {
        if (op >= B_EQ && op <= B_GE) {
            int ok = (a == b) || (a->k == TY_NULL && b->k == TY_PTR) || (b->k == TY_NULL && a->k == TY_PTR);
            if (!ok) error_at(e->loc, "cannot compare %s with %s", ty_str(a), ty_str(b));
            if (a->k == TY_NULL) e->a = coerce(c, e->a, b, "operand");
            if (b->k == TY_NULL) e->b = coerce(c, e->b, a, "operand");
            e->conv_from = ty_u32;
            e->ty = ty_bool;
            return e;
        }
        if (a->k == TY_PTR && (op == B_ADD || op == B_SUB) && is_intish(b)) {
            if (complete(a->elem, e->loc)->size == 0) error_at(e->loc, "pointer arithmetic on a zero-sized type");
            if (b->k == TY_UINT) e->b = coerce(c, e->b, ty_s32, "offset");
            e->ty = a;
            return e;
        }
        if (b->k == TY_PTR && op == B_ADD && is_intish(a)) {
            Expr *t = e->a; e->a = e->b; e->b = t;
            if (e->b->ty->k == TY_UINT) e->b = coerce(c, e->b, ty_s32, "offset");
            e->ty = b;
            return e;
        }
        if (a->k == TY_PTR && b == a && op == B_SUB) { e->ty = ty_s32; e->conv_from = a; return e; }
        error_at(e->loc, "operator '%s' is not defined for %s and %s", on, ty_str(a), ty_str(b));
    }

    if (a->k == TY_BOOL || b->k == TY_BOOL) {
        if ((op == B_EQ || op == B_NE) && a == b) {
            e->ty = ty_bool; e->conv_from = ty_bool;
            if (e->a->isconst && e->b->isconst) { e->isconst = 1; e->cval = fold_cmp(op, ty_bool, e->a->cval, e->b->cval); }
            return e;
        }
        error_at(e->loc, "operator '%s' is not defined for %s and %s", on, ty_str(a), ty_str(b));
    }
    if (!is_numeric(a) || !is_numeric(b)) error_at(e->loc, "operator '%s' is not defined for %s and %s", on, ty_str(a), ty_str(b));

    /* shifts: the result has the left operand's type */
    if (op == B_SHL || op == B_SHR) {
        if (!is_intish(b)) error_at(e->b->loc, "shift count must be an integer");
        Type *t = a->k == TY_UINT ? ty_uint : a->k == TY_UFIXED ? ty_ufixed : a->k == TY_FIXED ? ty_fixed : a->k == TY_U32 ? ty_u32 : ty_s32;
        if ((t == ty_uint || t == ty_ufixed) && !e->b->isconst) {
            /* a constant shifted by a variable is not a constant: give it a real type
               (s32, or u32 for constants above 0x7FFFFFFF; fixed for fixed constants) */
            t = t == ty_ufixed ? ty_fixed : (e->a->cval > INT32_MAX ? ty_u32 : ty_s32);
            e->a = coerce(c, e->a, t, "the shifted value");
        }
        if (b->k == TY_UINT && t != ty_uint && t != ty_ufixed) {
            if (e->b->cval < 0 || e->b->cval > 31) error_at(e->b->loc, "shift count %lld is out of range (0..31)", (long long)e->b->cval);
            e->b = coerce(c, e->b, ty_s32, "shift count");
        }
        e->ty = t;
        e->conv_from = t;
        if (e->a->isconst && e->b->isconst) { e->isconst = 1; e->cval = fold_bin(e->loc, op, t, e->a->cval, e->b->cval); }
        return e;
    }

    /* fixed * int, int * fixed and fixed / int scale by an integer without fmul/fdiv */
    if ((op == B_MUL || op == B_DIV) && a->k == TY_UFIXED && ty_is_int(b)) { e->a = coerce(c, e->a, ty_fixed, "operand"); a = ty_fixed; }
    if (op == B_MUL && b->k == TY_UFIXED && ty_is_int(a)) { e->b = coerce(c, e->b, ty_fixed, "operand"); b = ty_fixed; }
    if (((op == B_MUL || op == B_DIV) && a->k == TY_FIXED && ty_is_int(b)) || (op == B_MUL && ty_is_int(a) && b->k == TY_FIXED)) {
        if (b->k == TY_FIXED) { Expr *t = e->a; e->a = e->b; e->b = t; }
        if (e->b->ty->k == TY_U32) error_at(e->loc, "fixed values can be scaled by signed integers only; convert the u32 with 'as s32'");
        e->ty = ty_fixed;
        e->conv_from = ty_s32;   /* marks the mixed form */
        return e;
    }

    Type *t = arith_type(e, a, b, on);
    if (!t) {
        if ((is_fixedish(a) && is_intish(b)) || (is_intish(a) && is_fixedish(b)))
            error_at(e->loc, "cannot mix fixed and integer values in '%s' (%s and %s); convert with 'as fixed' or 'as s32'", on, a->name, b->name);
        error_at(e->loc, "operator '%s' is not defined for %s and %s", on, ty_str(a), ty_str(b));
    }
    if (op == B_MOD && (t->k == TY_FIXED || t->k == TY_UFIXED)) error_at(e->loc, "'%%' is not defined for fixed values");
    if ((op == B_AND || op == B_OR || op == B_XOR) && (t->k == TY_FIXED || t->k == TY_UFIXED))
        error_at(e->loc, "bitwise '%s' is not defined for fixed values; use bits()/from_bits()", on);
    e->a = coerce_operand(c, e->a, t);
    e->b = coerce_operand(c, e->b, t);
    e->conv_from = t;
    int cmp = op >= B_EQ && op <= B_GE;
    e->ty = cmp ? ty_bool : t;
    if ((op == B_DIV || op == B_MOD) && e->b->isconst && e->b->cval == 0) error_at(e->b->loc, "division by zero");
    if (e->a->isconst && e->b->isconst) {
        e->isconst = 1;
        e->cval = cmp ? fold_cmp(op, t, e->a->cval, e->b->cval) : fold_bin(e->loc, op, t, e->a->cval, e->b->cval);
        if (t == ty_ufixed && !cmp) check_ufixed_range(e->loc, e->cval);
    }
    return e;
}

static Expr *check_unary(Ctx *c, Expr *e) {
    e->a = check(c, e->a, NULL);
    Type *t = e->a->ty;
    switch (e->op) {
    case U_NEG:
        if (ty_is_vec(t)) {
            e->ty = t;
            if (e->a->isconst) { e->isconst = 1; for (int i = 0; i < 4; i++) e->cvec[i] = (int32_t)(0u - (uint32_t)e->a->cvec[i]); }
            return e;
        }
        if (!is_numeric(t)) error_at(e->loc, "'-' needs a number, found %s", ty_str(t));
        e->ty = t->k == TY_U32 ? ty_u32 : (ty_is_int(t) ? ty_s32 : t);
        if (e->a->isconst) { e->isconst = 1; e->cval = (t->k == TY_UINT || t->k == TY_UFIXED) ? -e->a->cval : norm(e->ty, -e->a->cval); }
        return e;
    case U_NOT:
        if (t->k != TY_BOOL) error_at(e->loc, "'!' needs a bool, found %s (compare with 0 instead)", ty_str(t));
        e->ty = ty_bool;
        if (e->a->isconst) { e->isconst = 1; e->cval = !e->a->cval; }
        return e;
    case U_BNOT:
        if (!is_intish(t)) error_at(e->loc, "'~' needs an integer, found %s", ty_str(t));
        e->ty = t->k == TY_UINT ? ty_uint : t->k == TY_U32 ? ty_u32 : ty_s32;
        if (e->a->isconst) { e->isconst = 1; e->cval = t->k == TY_UINT ? ~e->a->cval : norm(e->ty, ~e->a->cval); }
        return e;
    case U_ADDR:
        if (e->a->k == E_NAME && e->a->sym && e->a->sym->k == SY_EMBED)
            error_at(e->loc, "'%s' is already a pointer to the embedded data", e->a->sym->name);
        if (!is_lvalue(e->a) || (e->a->k == E_FIELD && !e->a->field && e->a->nlanes != 1))
            error_at(e->loc, "cannot take the address of this expression");
        if (e->a->k == E_FIELD && !e->a->field) error_at(e->loc, "cannot take the address of a vector lane");
        if (e->a->k == E_NAME && e->a->sym->k == SY_LOCAL && e->a->sym->local->is_capture)
            error_at(e->loc, "cannot take the address of '%s': it is a read-only copy captured by the function literal", e->a->name);
        mark_addr_taken(e->a);
        e->ty = ty_ptr(t);
        return e;
    case U_DEREF:
        if (t->k != TY_PTR) error_at(e->loc, "'*' needs a pointer, found %s", ty_str(t));
        if (t->elem->k == TY_VOID) error_at(e->loc, "cannot dereference a void pointer");
        e->ty = complete(t->elem, e->loc);
        return e;
    default: break;
    }
    return e;
}

static Expr *check_index(Ctx *c, Expr *e) {
    e->a = check(c, e->a, NULL);
    e->b = check(c, e->b, NULL);
    Type *t = e->a->ty;
    if (!is_intish(e->b->ty) && e->b->ty->k != TY_ENUM) error_at(e->b->loc, "index must be an integer or an enum, found %s", ty_str(e->b->ty));
    if (e->b->ty->k == TY_UINT) e->b = coerce(c, e->b, ty_s32, "index");
    if (t->k == TY_ARRAY) {
        if (e->b->isconst && (e->b->cval < 0 || e->b->cval >= t->n))
            error_at(e->b->loc, "index %lld is out of bounds for %s", (long long)e->b->cval, ty_str(t));
        e->ty = t->elem;
    } else if (t->k == TY_PTR) {
        if (t->elem->k == TY_VOID) error_at(e->loc, "cannot index a void pointer");
        e->ty = complete(t->elem, e->loc);
    } else if (t->k == TY_MAT4) {
        if (e->b->isconst && (e->b->cval < 0 || e->b->cval > 3)) error_at(e->b->loc, "mat4 row index must be 0..3");
        e->ty = ty_vec4;
    } else error_at(e->loc, "cannot index a value of type %s", ty_str(t));
    return e;
}

static int enum_variant(Type *t, const char *name);

static Expr *check_field(Ctx *c, Expr *e) {
    if (e->a->k == E_NAME && !(c->fn && lookup_local(c, e->a->name))) {
        Sym *ts = sym_lookup(e->a->name, e->a->loc.file);
        if (ts && ts->k == SY_TYPE && ts->ty->k == TY_ENUM) {
            /* State.Title */
            Type *t = ts->ty;
            resolve_enum(t);
            int i = enum_variant(t, e->name);
            if (i < 0) error_at(e->loc, "enum %s has no variant '%s'", t->name, e->name);
            e->ty = t;
            e->isconst = 1;
            e->cval = t->vvals[i];
            return e;
        }
    }
    e->a = check(c, e->a, NULL);
    Type *t = e->a->ty;
    if (t->k == TY_PTR) t = complete(t->elem, e->loc);
    if (t->k == TY_STRUCT) {
        complete(t, e->loc);
        for (int i = 0; i < t->nfields; i++)
            if (!strcmp(t->fields[i].name, e->name)) { e->field = &t->fields[i]; e->ty = t->fields[i].type; return e; }
        error_at(e->loc, "struct %s has no field '%s'", t->name, e->name);
    }
    if (ty_is_vec(t) && e->a->ty->k == TY_PTR) {
        /* p.x on a pointer to a vector: dereference explicitly */
        Expr *d = ar_alloc(sizeof *d);
        d->k = E_UNARY; d->op = U_DEREF; d->loc = e->a->loc; d->a = e->a; d->ty = t;
        e->a = d;
    }
    if (ty_is_vec(e->a->ty)) {
        int n = (int)strlen(e->name);
        int lanes = ty_lanes(t);
        if (n < 1 || n > 4) error_at(e->loc, "%s has no field '%s'", t->name, e->name);
        for (int i = 0; i < n; i++) {
            const char *p = strchr("xyzw", e->name[i]);
            if (!p || !e->name[i]) error_at(e->loc, "%s has no field '%s' (lanes are x, y, z, w)", t->name, e->name);
            int l = (int)(p - "xyzw");
            if (l >= lanes) error_at(e->loc, "%s has no lane '%c'", t->name, e->name[i]);
            e->lanes[i] = l;
        }
        e->nlanes = n;
        if (n == 1) e->ty = t->k == TY_IVEC4 ? ty_s32 : ty_fixed;
        else {
            if (t->k == TY_IVEC4) error_at(e->loc, "ivec4 supports single-lane access only");
            e->ty = n == 2 ? ty_vec2 : n == 3 ? ty_vec3 : ty_vec4;
        }
        if (e->a->isconst) {
            if (n == 1) { e->isconst = 1; e->cval = e->a->cvec[e->lanes[0]]; }
            else { e->isconst = 1; memset(e->cvec, 0, sizeof e->cvec); for (int i = 0; i < n; i++) e->cvec[i] = e->a->cvec[e->lanes[i]]; }
        }
        return e;
    }
    error_at(e->loc, "a value of type %s has no fields", ty_str(e->a->ty));
}

/* Explicit conversion `x as T` / `T(x)`. */
static Expr *check_cast(Ctx *c, Expr *e, Expr *x, Type *to) {
    x = check(c, x, NULL);
    Type *from = x->ty;
    e->a = x;
    e->ty = to;
    e->conv_from = from;
    e->k = E_CONV;
    if (from == to) return x;
    if (from->k == TY_UINT && (ty_is_int(to) || to->k == TY_FIXED)) {
        if (to->k == TY_FIXED) return coerce(c, x, to, "value");
        return mk_const(x, to, x->cval);   /* explicit: wrap */
    }
    if (from->k == TY_UINT && (to->k == TY_PTR || to->k == TY_ENUM)) return mk_const(x, to, x->cval);
    if (from->k == TY_UFIXED) {
        check_ufixed_range(x->loc, x->cval);
        if (to->k == TY_FIXED) return mk_const(x, to, x->cval);
        if (ty_is_int(to)) return mk_const(x, to, x->cval >> 16);
    }
    if (from->k == TY_NULL && (to->k == TY_PTR || to->k == TY_FUNC)) return mk_const(x, to, 0);
    int ok = 0;
    if ((ty_is_int(from) || from->k == TY_FIXED) && (ty_is_int(to) || to->k == TY_FIXED)) ok = 1;
    if (from->k == TY_BOOL && ty_is_int(to)) ok = 1;
    if ((from->k == TY_PTR || ty_is_int(from)) && to->k == TY_PTR) ok = 1;
    if (from->k == TY_PTR && (to->k == TY_U32 || to->k == TY_S32)) ok = 1;
    if (ty_is_vec(from) && ty_is_vec(to)) ok = 1;
    if ((from->k == TY_ENUM && (ty_is_int(to) || to->k == TY_ENUM)) || (ty_is_int(from) && to->k == TY_ENUM)) ok = 1;
    if ((from->k == TY_FUNC && (to->k == TY_U32 || to->k == TY_S32)) || ((from->k == TY_U32 || from->k == TY_S32) && to->k == TY_FUNC)) ok = 1;
    if (!ok) error_at(e->loc, "cannot convert %s to %s", ty_str(from), ty_str(to));
    if (x->isconst && ty_is_scalar(from)) {
        e->isconst = 1;
        int64_t v = x->cval;
        if (to->k == TY_FIXED && from->k != TY_FIXED) v = (int64_t)(uint64_t)((uint32_t)norm(from, v) << 16);
        else if (from->k == TY_FIXED && to->k != TY_FIXED) v = (int32_t)v >> 16;
        e->cval = norm(to, v);
    }
    return e;
}

static Expr *check_ctor(Ctx *c, Expr *e, Type *t) {
    int lanes = ty_lanes(t);
    Type *lt = t->k == TY_IVEC4 ? ty_s32 : ty_fixed;
    e->bi = t->k == TY_VEC2 ? BI_VEC2 : t->k == TY_VEC3 ? BI_VEC3 : t->k == TY_VEC4 ? BI_VEC4 : BI_IVEC4;
    e->ty = t;
    if (t->k == TY_VEC4 && e->nargs == 2) {
        /* vec4(v: vec3, w) */
        e->args[0] = check(c, e->args[0], NULL);
        if (e->args[0]->ty != ty_vec3) error_at(e->args[0]->loc, "vec4(v, w) needs a vec3 first argument");
        e->args[1] = coerce(c, check(c, e->args[1], NULL), ty_fixed, "the w lane");
        if (e->args[0]->isconst && e->args[1]->isconst) {
            e->isconst = 1;
            memcpy(e->cvec, e->args[0]->cvec, sizeof e->cvec);
            e->cvec[3] = (int32_t)e->args[1]->cval;
        }
        return e;
    }
    if (e->nargs != lanes) error_at(e->loc, "%s(...) takes %d values, got %d", t->name, lanes, e->nargs);
    int allc = 1;
    memset(e->cvec, 0, sizeof e->cvec);
    for (int i = 0; i < lanes; i++) {
        e->args[i] = coerce(c, check(c, e->args[i], NULL), lt, ar_printf("lane %d of %s(...)", i, t->name));
        if (e->args[i]->isconst) e->cvec[i] = (int32_t)e->args[i]->cval; else allc = 0;
    }
    e->isconst = allc;
    return e;
}

/* Checks call arguments against parameter types (aggregates are passed by reference). */
static void check_args(Ctx *c, Expr *e, Type **pts, int n, const char *name) {
    if (e->nargs != n)
        error_at(e->loc, "%s takes %d argument%s, got %d", name, n, n == 1 ? "" : "s", e->nargs);
    for (int i = 0; i < n; i++) {
        Type *pt = pts[i];
        Expr *arg = check(c, e->args[i], pt);
        if (ty_is_aggr(pt)) {
            if (arg->ty != pt) error_at(arg->loc, "type mismatch: argument %d of %s is %s, expected %s", i + 1, name, ty_str(arg->ty), ty_str(pt));
            if (is_lvalue(arg)) mark_addr_taken(arg);
        } else arg = coerce(c, arg, pt, ar_printf("argument %d of %s", i + 1, name));
        e->args[i] = arg;
    }
}

/* A call through a function value: compiled to callr. */
static int g_lambda_noescape;   /* the literal about to be checked cannot outlive its function */

static Expr *check_indirect_call(Ctx *c, Expr *e) {
    g_lambda_noescape = e->a->k == E_FUNC;
    e->a = check(c, e->a, NULL);
    g_lambda_noescape = 0;
    Type *ft = e->a->ty;
    if (ft->k != TY_FUNC) {
        if (e->a->k == E_NAME) error_at(e->a->loc, "'%s' is a %s, not a function", e->a->name, ty_str(ft));
        error_at(e->a->loc, "this is a %s, not a function", ty_str(ft));
    }
    check_args(c, e, ft->params, ft->nparams, e->a->k == E_NAME ? ar_printf("%s()", e->a->name) : "the function value");
    e->indirect = 1;
    e->ty = ft->elem;
    if (!c->fn) error_at(e->loc, "function calls are not allowed in constant expressions");
    c->fn->has_call = 1;
    return e;
}

static Expr *check_intrinsic(Ctx *c, Expr *e, Builtin bi, const char *name);

static Expr *check_call(Ctx *c, Expr *e) {
    if (e->callee) return e;   /* synthesized */
    if (e->a->k != E_NAME) return check_indirect_call(c, e);
    const char *name = e->a->name;
    Sym *s = NULL;
    if (c->fn && is_local_name(c, name)) return check_indirect_call(c, e);
    s = sym_lookup(name, e->loc.file);
    if (!s) error_unknown(e->a->loc, "function", name);
    if (s->k == SY_GLOBAL || s->k == SY_CONST || s->k == SY_DATA || s->k == SY_REG || s->k == SY_EMBED) return check_indirect_call(c, e);
    if (s->k == SY_TYPE) {
        Type *t = s->ty;
        if (ty_is_vec(t)) return check_ctor(c, e, t);
        if (ty_is_scalar(t)) {
            if (e->nargs != 1) error_at(e->loc, "%s(...) converts one value", t->name);
            return check_cast(c, e, e->args[0], t);
        }
        error_at(e->loc, "'%s' cannot be called; build a %s with a literal", name, name);
    }
    if (s->k == SY_BUILTIN) {
        if (s->bi >= BI_MAP) return check_intrinsic(c, e, s->bi, name);
        e->bi = s->bi;
        int want = (s->bi == BI_DOT || s->bi == BI_CROSS || s->bi == BI_MIN || s->bi == BI_MAX) ? 2
                 : (s->bi == BI_CLAMP || s->bi == BI_LERP || s->bi == BI_NCLIP || s->bi == BI_OTZ || s->bi == BI_CLERP) ? 3 : 1;
        if (e->nargs != want) error_at(e->loc, "%s() takes %d argument%s, got %d", name, want, want == 1 ? "" : "s", e->nargs);
        if (s->bi == BI_LEN) {
            Expr *x = e->args[0];
            if (x->k == E_NAME && !(c->fn && is_local_name(c, x->name))) {
                Sym *ts = sym_lookup(x->name, x->loc.file);
                if (ts && ts->k == SY_TYPE && ts->ty->k == TY_ENUM) {
                    /* len(Dir): the number of variants */
                    resolve_enum(ts->ty);
                    e->ty = ty_uint; e->isconst = 1; e->cval = ts->ty->nvariants;
                    return e;
                }
            }
            if (x->k == E_NAME) {
                Sym *xs = sym_lookup(x->name, x->loc.file);
                if (xs && xs->k == SY_EMBED && !(c->fn && lookup_local(c, x->name))) {
                    resolve_embed(xs);
                    note_ref(c, xs);
                    e->ty = ty_uint; e->isconst = 1;
                    e->cval = (int64_t)(xs->datalen / (size_t)(xs->ty->elem->size ? xs->ty->elem->size : 1));
                    return e;
                }
            }
            x = check(c, x, NULL);
            if (x->ty->k != TY_ARRAY) error_at(x->loc, "len() needs an array, an embedded asset or an enum type, found %s", ty_str(x->ty));
            e->ty = ty_uint; e->isconst = 1; e->cval = x->ty->n;
            return e;
        }
        for (int i = 0; i < e->nargs; i++) e->args[i] = check(c, e->args[i], NULL);
        Expr **a = e->args;
        switch (s->bi) {
        case BI_DOT:
            if (!ty_is_vec(a[0]->ty) || a[0]->ty != a[1]->ty || a[0]->ty->k == TY_IVEC4)
                error_at(e->loc, "dot() needs two vectors of the same type, found %s and %s", ty_str(a[0]->ty), ty_str(a[1]->ty));
            e->ty = ty_fixed;
            return e;
        case BI_CROSS:
            if (a[0]->ty != ty_vec3 || a[1]->ty != ty_vec3) error_at(e->loc, "cross() needs two vec3 values");
            e->ty = ty_vec3;
            return e;
        case BI_BITS:
            if (a[0]->ty->k != TY_FIXED && a[0]->ty->k != TY_UFIXED) error_at(e->loc, "bits() needs a fixed value");
            a[0] = coerce(c, a[0], ty_fixed, "argument");
            e->ty = ty_s32;
            if (a[0]->isconst) { e->isconst = 1; e->cval = a[0]->cval; }
            return e;
        case BI_FROM_BITS:
            if (!is_intish(a[0]->ty)) error_at(e->loc, "from_bits() needs an integer");
            if (a[0]->ty->k == TY_UINT) a[0] = coerce(c, a[0], ty_s32, "argument");
            e->ty = ty_fixed;
            if (a[0]->isconst) { e->isconst = 1; e->cval = norm(ty_fixed, a[0]->cval); }
            return e;
        case BI_ABS: case BI_MIN: case BI_MAX: case BI_CLAMP: {
            Type *t = default_type(a[0]);
            for (int i = 1; i < e->nargs; i++) {
                Type *u = arith_type(e, t, a[i]->ty, name);
                if (!u) error_at(e->loc, "%s() needs numbers of one type, found %s and %s", name, ty_str(t), ty_str(a[i]->ty));
                t = u;
            }
            t = t == ty_uint ? ty_s32 : t == ty_ufixed ? ty_fixed : t;
            if (!is_numeric(t)) error_at(e->loc, "%s() needs numbers, found %s", name, ty_str(t));
            if (s->bi == BI_ABS && t == ty_u32) error_at(e->loc, "abs() of an unsigned value");
            for (int i = 0; i < e->nargs; i++) a[i] = coerce_operand(c, a[i], t);
            e->ty = t;
            int allc = 1;
            for (int i = 0; i < e->nargs; i++) allc &= a[i]->isconst;
            if (allc) {
                int64_t v = a[0]->cval;
                int sg = ty_is_signed(t);
                #define LT(x, y) (sg ? (int64_t)(x) < (int64_t)(y) : (uint32_t)(x) < (uint32_t)(y))
                if (s->bi == BI_ABS) v = v < 0 ? norm(t, -v) : v;
                else if (s->bi == BI_MIN) v = LT(a[1]->cval, v) ? a[1]->cval : v;
                else if (s->bi == BI_MAX) v = LT(v, a[1]->cval) ? a[1]->cval : v;
                else { if (LT(v, a[1]->cval)) v = a[1]->cval; if (LT(a[2]->cval, v)) v = a[2]->cval; }
                #undef LT
                e->isconst = 1; e->cval = v;
            }
            return e;
        }
        case BI_LERP: {
            Type *t = a[0]->ty;
            if (ty_is_vec(t) && t->k != TY_IVEC4) {
                if (a[1]->ty != t) error_at(e->loc, "lerp() needs two values of the same type");
            } else {
                t = ty_fixed;
                a[0] = coerce(c, a[0], ty_fixed, "argument 1 of lerp()");
                a[1] = coerce(c, a[1], ty_fixed, "argument 2 of lerp()");
            }
            a[2] = coerce(c, a[2], ty_fixed, "argument 3 of lerp()");
            e->ty = t;
            return e;
        }
        case BI_NCLIP: case BI_OTZ: case BI_CLERP: {
            /* one instruction each: nclip(p0, p1, p2), otz(bias, depth, scale), clerp(from, to, t) */
            static const char *what[3] = {"argument 1 of %s()", "argument 2 of %s()", "argument 3 of %s()"};
            Type *want[3] = {ty_u32, ty_u32, ty_u32};
            if (s->bi == BI_OTZ) { want[0] = ty_s32; want[1] = want[2] = ty_fixed; }
            if (s->bi == BI_CLERP) want[2] = ty_fixed;
            for (int i = 0; i < 3; i++) {
                if (want[i] != ty_fixed && !is_intish(a[i]->ty))
                    error_at(a[i]->loc, "%s() needs integers for argument %d, found %s", name, i + 1, ty_str(a[i]->ty));
                a[i] = coerce(c, a[i], want[i], ar_printf(what[i], name));
            }
            e->ty = s->bi == BI_CLERP ? ty_u32 : ty_s32;
            return e;
        }
        case BI_KIND: case BI_RAW: {
            /* assert_eq()'s report: 0 signed, 1 unsigned, 2 fixed, 3 bool, 4 pointer */
            Expr *x = a[0];
            if (x->ty->k == TY_UINT) x = coerce(c, x, ty_s32, "argument");
            else if (x->ty->k == TY_UFIXED) x = coerce(c, x, ty_fixed, "argument");
            a[0] = x;
            Type *t = x->ty;
            if (!ty_is_scalar(t) && t->k != TY_PTR && t->k != TY_NULL && t->k != TY_ENUM)
                error_at(x->loc, "assert_eq() compares numbers, booleans, enums and pointers, found %s", ty_str(t));
            e->ty = ty_s32;
            if (s->bi == BI_KIND) {
                e->isconst = 1;
                e->cval = t->k == TY_FIXED ? 2 : t->k == TY_BOOL ? 3 : (t->k == TY_PTR || t->k == TY_NULL) ? 4
                        : (t->k == TY_U8 || t->k == TY_U16 || t->k == TY_U32) ? 1 : 0;
            }
            return e;
        }
        case BI_LENGTH: case BI_NORMALIZE: {
            Type *t = a[0]->ty;
            if (!ty_is_vec(t) || t->k == TY_IVEC4) error_at(e->loc, "%s() needs a vector, found %s", name, ty_str(t));
            e->callee = stdlib_fn(c, s->bi == BI_LENGTH ? "sqrt" : "normalize4", e->loc)->fn;
            e->ty = s->bi == BI_LENGTH ? ty_fixed : t;
            return e;
        }
        default: break;
        }
        return e;
    }
    if (s->k != SY_FUNC) error_at(e->a->loc, "'%s' is not a function", name);
    Func *f = s->fn;
    e->callee = f;
    e->sym = s;
    Type *pts[64];
    if (f->nparams > 64) error_at(f->loc, "too many parameters");
    for (int i = 0; i < f->nparams; i++) pts[i] = f->params[i].ty;
    check_args(c, e, pts, f->nparams, ar_printf("%s()", name));
    e->ty = f->ret;
    if (c->fn) { c->fn->has_call = 1; note_call(c, f); }
    else error_at(e->loc, "function calls are not allowed in constant expressions");
    return e;
}

static Expr *check_array_lit(Ctx *c, Expr *e, Type *want) {
    Type *el = NULL;
    if (want && want->k == TY_ARRAY) {
        el = want->elem;
        if (e->nargs != want->n)
            error_at(e->loc, "array literal has %d element%s, %s needs %lld", e->nargs, e->nargs == 1 ? "" : "s", ty_str(want), (long long)want->n);
    }
    if (e->nargs == 0) error_at(e->loc, "empty array literal");
    int allc = 1;
    for (int i = 0; i < e->nargs; i++) {
        Expr *x = check(c, e->args[i], el);
        if (!el) { el = default_type(x); if (el->k == TY_NULL) error_at(x->loc, "cannot infer the element type"); }
        if (ty_is_aggr(el)) { if (x->ty != el) error_at(x->loc, "type mismatch: element is %s, expected %s", ty_str(x->ty), ty_str(el)); }
        else x = coerce(c, x, el, ar_printf("element %d", i));
        e->args[i] = x;
        if (!x->isconst) allc = 0;
    }
    e->ty = ty_array(complete(el, e->loc), e->nargs);
    e->isconst = allc;
    return e;
}

static Expr *check_struct_lit(Ctx *c, Expr *e) {
    Sym *s = sym_lookup(e->name, e->loc.file);
    if (!s || s->k != SY_TYPE || s->ty->k != TY_STRUCT) error_at(e->loc, "'%s' is not a struct type", e->name);
    Type *t = complete(s->ty, e->loc);
    int allc = 1;
    for (int i = 0; i < e->nargs; i++) {
        Field *f = NULL;
        for (int j = 0; j < t->nfields; j++) if (!strcmp(t->fields[j].name, e->fnames[i])) f = &t->fields[j];
        if (!f) error_at(e->args[i]->loc, "struct %s has no field '%s'", t->name, e->fnames[i]);
        for (int j = 0; j < i; j++) if (!strcmp(e->fnames[j], e->fnames[i])) error_at(e->args[i]->loc, "field '%s' is given twice", e->fnames[i]);
        Expr *x = check(c, e->args[i], f->type);
        if (ty_is_aggr(f->type)) { if (x->ty != f->type) error_at(x->loc, "type mismatch: field '%s' is %s, got %s", f->name, ty_str(f->type), ty_str(x->ty)); }
        else x = coerce(c, x, f->type, ar_printf("field '%s'", f->name));
        e->args[i] = x;
        if (!x->isconst) allc = 0;
    }
    e->ty = t;
    e->isconst = allc;
    return e;
}

/* ---- function literals ---- */

static void check_func_body(Program *P, Func *f, Ctx *outer);

static Expr *check_lambda(Ctx *c, Expr *e, Type *want) {
    Func *f = e->lambda;
    int noescape = g_lambda_noescape;
    g_lambda_noescape = 0;
    if (!c->fn) error_at(e->loc, "function literals cannot be used in constant expressions");
    if (!f->checked) {
        f->noescape = noescape;
        Type *wt = want && want->k == TY_FUNC ? want : NULL;
        if (wt && wt->nparams != f->nparams)
            error_at(e->loc, "this function literal takes %d parameter%s, but %s is expected", f->nparams,
                     f->nparams == 1 ? "" : "s", wt->elem ? ty_str(wt) : ar_printf("a function of %d parameter%s", wt->nparams, wt->nparams == 1 ? "" : "s"));
        for (int i = 0; i < f->nparams; i++) {
            Param *pr = &f->params[i];
            if (pr->texpr) pr->ty = complete(resolve_type_in(pr->texpr, c), pr->loc);
            else if (wt) pr->ty = wt->params[i];
            else error_at(pr->loc, "parameter '%s' needs a type (write '%s: T'; types can be left out only where a function type is expected)", pr->name, pr->name);
            if (pr->ty->k == TY_VOID) error_at(pr->loc, "parameters cannot be void");
        }
        if (f->ret_texpr) f->ret = complete(resolve_type_in(f->ret_texpr, c), f->ret_texpr->loc);
        else if (wt && wt->elem && !f->lambda_body) f->ret = wt->elem;
        else if (!f->lambda_body) f->ret = ty_void;
        else f->ret = wt && wt->elem ? wt->elem : NULL;   /* NULL: inferred from the expression */
        if (f->ret && f->ret->k == TY_ARRAY) error_at(e->loc, "functions cannot return arrays; wrap the array in a struct");
        f->name = ar_printf("function literal (line %d)", e->loc.line);
        f->label = ar_printf("FL%d", ++g_lambda_n);
        f->checked = 1;
        PUSH(c->P->funcs, c->P->nfuncs, c->P->capfuncs, f);
        Stmt *saved[256];
        int nsaved = g_loop_n;
        memcpy(saved, g_loop_stack, sizeof(Stmt *) * (size_t)nsaved);
        g_loop_n = 0;
        check_func_body(c->P, f, c);
        g_loop_n = nsaved;
        memcpy(g_loop_stack, saved, sizeof(Stmt *) * (size_t)nsaved);
        if (f->ncaps > 3) {
            Buf b = {0};
            for (int i = 0; i < f->ncaps; i++)
                buf_printf(&b, "%s%s (%s, 1 word)", i ? ", " : "", f->caps[i]->name, ty_str(f->caps[i]->ty));
            error_at(e->loc, "function literal captures %d words, but a function value holds at most 3\n"
                     "  captured: %s\n"
                     "  note: pass the extra values as arguments, or capture one pointer to a struct that holds them",
                     f->ncaps, b.p);
        }
        for (int i = 0; i < f->ncaps && !f->noescape; i++)
            if (f->caps[i]->points_local)
                error_at(f->cap_locs[i], "this function literal captures the pointer '%s', which points into a local variable "
                         "of the function around it; the function value can outlive that variable, leaving the pointer "
                         "dangling (keep the data in a global, or pass the pointer as an argument)", f->caps[i]->name);
    }
    note_call(c, f);
    e->ty = func_type_of(f);
    return e;
}

/* ---- map / filter / reduce / each ---- */

/* A sequence argument: an array, or a pointer (which needs an explicit count). */
static Type *seq_elem(Ctx *c, Expr **xp, int64_t *n, const char *fname, const char *role, int writes) {
    Expr *x = check(c, *xp, NULL);
    *xp = x;
    if (x->ty->k == TY_ARRAY) {
        *n = x->ty->n;
        if (writes) {
            const char *why = not_assignable(x);
            if (why) error_at(x->loc, "%s() writes to %s, which cannot be modified: %s", fname, role, why);
        }
        if (is_lvalue(x)) mark_addr_taken(x);
        return complete(x->ty->elem, x->loc);
    }
    if (x->ty->k == TY_PTR && x->ty->elem->k != TY_VOID) { *n = -1; return complete(x->ty->elem, x->loc); }
    error_at(x->loc, "%s() needs an array or a pointer as %s, found %s", fname, role, ty_str(x->ty));
}

/* The function argument of an intrinsic: checked against fn(params) -> ret (ret NULL: any). */
static Expr *fn_arg(Ctx *c, Expr *call, int i, Type **ps, int np, Type *ret, const char *fname) {
    g_lambda_noescape = call->args[i]->k == E_FUNC;
    Expr *f = check(c, call->args[i], ty_func(ps, np, ret));
    g_lambda_noescape = 0;
    call->args[i] = f;
    Type *t = f->ty;
    if (t->k != TY_FUNC) error_at(f->loc, "%s() needs a function as argument %d, found %s", fname, i + 1, ty_str(t));
    int ok = t->nparams == np && (!ret || t->elem == ret);
    for (int k = 0; ok && k < np; k++) if (t->params[k] != ps[k]) ok = 0;
    if (!ok) error_at(f->loc, "type mismatch: %s() needs a function of type %s here, found %s", fname,
                      ret ? ty_str(ty_func(ps, np, ret)) : ar_printf("%s -> ...", ty_str(ty_func(ps, np, ty_void))), ty_str(t));
    if (f->k == E_FUNC) call->target = f->lambda;
    else if (f->k == E_NAME && f->sym && f->sym->k == SY_FUNC) call->target = f->sym->fn;
    return f;
}

static Expr *check_intrinsic(Ctx *c, Expr *e, Builtin bi, const char *name) {
    static const struct { Builtin bi; int lo, hi; const char *usage; } forms[] = {
        {BI_MAP, 2, 2, "map(xs, f) -> array"},
        {BI_MAP_INTO, 3, 4, "map_into(out, xs, f [, count])"},
        {BI_FILTER, 2, 3, "filter(xs, keep [, count]) -> new count"},
        {BI_FILTER_INTO, 3, 4, "filter_into(out, xs, keep [, count]) -> count"},
        {BI_REDUCE, 3, 4, "reduce(xs, init, f [, count]) -> value"},
        {BI_EACH, 2, 3, "each(xs, f [, count])"},
    };
    int fi = 0;
    while (forms[fi].bi != bi) fi++;
    if (!c->fn) error_at(e->loc, "%s() cannot be used in a constant expression", name);
    if (e->nargs < forms[fi].lo || e->nargs > forms[fi].hi)
        error_at(e->loc, "wrong number of arguments: the form is %s", forms[fi].usage);
    e->bi = bi;
    e->has_count = e->nargs == forms[fi].hi && forms[fi].lo != forms[fi].hi;
    int has_out = bi == BI_MAP_INTO || bi == BI_FILTER_INTO;
    int xi = has_out ? 1 : 0;
    int64_t n = -1, nout = -1;
    Type *out_t = NULL;
    if (has_out) out_t = seq_elem(c, &e->args[0], &nout, name, "the output", 1);
    Type *t = seq_elem(c, &e->args[xi], &n, name, "the input", bi == BI_FILTER);
    if (bi == BI_MAP && n < 0) error_at(e->args[0]->loc, "map() returns an array, so it needs an array; use map_into(out, ptr, f, count) for pointers");
    int fidx = bi == BI_REDUCE ? 2 : xi + 1;
    if (e->has_count) {
        Expr *cnt = check(c, e->args[e->nargs - 1], NULL);
        if (!is_intish(cnt->ty)) error_at(cnt->loc, "the element count must be an integer, found %s", ty_str(cnt->ty));
        e->args[e->nargs - 1] = coerce(c, cnt, ty_s32, "the element count");
        if (cnt->isconst && n >= 0 && cnt->cval > n) error_at(cnt->loc, "count %lld is more than the %lld elements of the array", (long long)cnt->cval, (long long)n);
    } else if (n < 0) error_at(e->args[xi]->loc, "%s() over a pointer needs an element count: %s", name, forms[fi].usage);
    if (has_out && !e->has_count && nout >= 0 && nout < n)
        error_at(e->args[0]->loc, "the output has %lld elements but the input has %lld", (long long)nout, (long long)n);
    Type *ps[2] = {t, t};
    switch (bi) {
    case BI_MAP: {
        Expr *f = fn_arg(c, e, 1, ps, 1, NULL, name);
        Type *u = f->ty->elem;
        if (u->k == TY_VOID) error_at(f->loc, "map() needs a function that returns a value (use each() for side effects)");
        e->ty = ty_array(complete(u, f->loc), n);
        break;
    }
    case BI_MAP_INTO:
        fn_arg(c, e, 2, ps, 1, out_t, name);
        e->ty = ty_void;
        break;
    case BI_FILTER: case BI_FILTER_INTO:
        if (bi == BI_FILTER_INTO && out_t != t) error_at(e->args[0]->loc, "type mismatch: filter_into() copies %s elements, but the output holds %s", ty_str(t), ty_str(out_t));
        fn_arg(c, e, xi + 1, ps, 1, ty_bool, name);
        e->ty = ty_s32;
        break;
    case BI_REDUCE: {
        Expr *init = check(c, e->args[1], NULL);
        Type *a = default_type(init);
        if (!(ty_is_scalar(a) || ty_is_vec(a) || a->k == TY_FUNC) || a->k == TY_NULL)
            error_at(init->loc, "reduce() needs a scalar or vector starting value, found %s", ty_str(a));
        e->args[1] = coerce(c, init, a, "the starting value");
        ps[0] = a;
        fn_arg(c, e, 2, ps, 2, a, name);
        e->ty = a;
        break;
    }
    case BI_EACH: {
        g_lambda_noescape = e->args[1]->k == E_FUNC;
        Expr *f = check(c, e->args[1], ty_func(ps, 1, NULL));
        g_lambda_noescape = 0;
        e->args[1] = f;
        Type *ft = f->ty;
        if (ft->k != TY_FUNC || ft->nparams != 1 || (ft->params[0] != t && ft->params[0] != ty_ptr(t)))
            error_at(f->loc, "type mismatch: each() needs a function taking %s or %s, found %s", ty_str(t), ty_str(ty_ptr(t)), ty_str(ft));
        e->elem_byref = ft->params[0] == ty_ptr(t);
        if (f->k == E_FUNC) e->target = f->lambda;
        else if (f->k == E_NAME && f->sym && f->sym->k == SY_FUNC) e->target = f->sym->fn;
        e->ty = ty_void;
        break;
    }
    default: break;
    }
    /* loop state lives in compiler-made locals: count, source, destination, function, accumulator */
    e->hid[0] = hidden_local(c, ty_s32, e->loc);
    e->hid[1] = hidden_local(c, ty_u32, e->loc);
    e->hid[2] = hidden_local(c, ty_u32, e->loc);
    if (!e->target) e->hid[3] = hidden_local(c, e->args[fidx]->ty, e->loc);
    if (bi == BI_REDUCE) e->hid[4] = hidden_local(c, e->ty, e->loc);
    if (bi == BI_FILTER || bi == BI_FILTER_INTO) e->hid[4] = hidden_local(c, ty_u32, e->loc);
    /* a known literal's captures: copied once, passed in r6-r8 on every call */
    if (e->target) for (int k = 0; k < e->target->ncaps && k < 3; k++) e->hid[5 + k] = hidden_local(c, e->target->caps[k]->ty, e->loc);
    c->fn->has_call = 1;
    if (e->target) note_call(c, e->target);
    return e;
}

static Expr *check_match_head(Ctx *c, Expr *x, MatchArm *arms, int narms, Loc loc);

/* match x { A => value ... }: every arm yields a value of one type (the expected type when
   there is one, else the first arm's type; untyped constants alone default to s32 or fixed). */
static Expr *check_match_expr(Ctx *c, Expr *e, Type *want) {
    e->a = check_match_head(c, e->a, e->arms, e->narms, e->loc);
    Type *t = want && want->k != TY_VOID && want->k != TY_UINT && want->k != TY_UFIXED && want->k != TY_NULL ? want : NULL;
    for (int i = 0; i < e->narms; i++) e->arms[i].value = check(c, e->arms[i].value, t);
    if (!t) {
        int fx = 0, nul = 0;
        for (int i = 0; i < e->narms && !t; i++) {
            Type *at = e->arms[i].value->ty;
            if (at->k == TY_UFIXED) fx = 1;
            else if (at->k == TY_NULL) nul = 1;
            else if (at->k != TY_UINT) t = at;
        }
        if (!t && nul) error_at(e->loc, "cannot infer the type of this match from null; give the variable a type");
        if (!t) t = fx ? ty_fixed : ty_s32;
    }
    if (t->k == TY_VOID) error_at(e->arms[0].value->loc, "the arms of a match expression must have values");
    for (int i = 0; i < e->narms; i++) {
        Expr *v = e->arms[i].value;
        if (ty_is_aggr(t)) {
            if (v->ty != t) error_at(v->loc, "type mismatch: this arm is %s, but the match yields %s", ty_str(v->ty), ty_str(t));
        } else v = coerce(c, v, t, "the value of this match arm");
        e->arms[i].value = v;
    }
    e->ty = t;
    if (e->a->isconst && !ty_is_aggr(t)) {
        /* a constant value picks its arm at compile time */
        MatchArm *pick = NULL;
        for (int i = 0; i < e->narms && !pick; i++) {
            if (e->arms[i].is_else) pick = &e->arms[i];
            for (int k = 0; k < e->arms[i].npats; k++) if (e->arms[i].pats[k]->cval == e->a->cval) pick = &e->arms[i];
        }
        if (pick && pick->value->isconst) {
            e->isconst = 1;
            e->cval = pick->value->cval;
            memcpy(e->cvec, pick->value->cvec, sizeof e->cvec);
        }
    }
    return e;
}

static Sym *intern_string(Ctx *c, const char *str, size_t len) {
    Program *P = c->P;
    for (int i = 0; i < P->ndatas; i++) {
        Sym *s = P->datas[i];
        if (s->is_str && s->slen == len && !memcmp(s->str, str, len)) return s;
    }
    Sym *s = ar_alloc(sizeof *s);
    s->k = SY_DATA;
    s->is_str = 1;
    s->str = str;
    s->slen = len;
    s->name = ar_printf("string %d", P->ndatas);
    s->label = ar_printf("S%d", P->ndatas);
    s->ty = ty_array(ty_u8, (int64_t)len + 1);
    s->state = 2;
    PUSH(P->datas, P->ndatas, P->capdatas, s);
    return s;
}

static Expr *check(Ctx *c, Expr *e, Type *want) {
    if (e->ty) return e;
    switch (e->k) {
    case E_INT: e->ty = ty_uint; e->isconst = 1; e->cval = e->ival; return e;
    case E_FIXED: e->ty = ty_ufixed; e->isconst = 1; e->cval = e->ival; check_ufixed_range(e->loc, e->cval); return e;
    case E_BOOL: e->ty = ty_bool; e->isconst = 1; e->cval = e->ival; return e;
    case E_NULL: e->ty = ty_null; e->isconst = 1; e->cval = 0; return e;
    case E_STR: {
        Sym *s = intern_string(c, e->str, e->slen);
        note_ref(c, s);
        e->sym = s;
        e->ty = ty_ptr(ty_u8);
        return e;
    }
    case E_NAME: return check_name(c, e);
    case E_UNARY: return check_unary(c, e);
    case E_BINARY: return check_binary(c, e);
    case E_CALL: return check_call(c, e);
    case E_INDEX: return check_index(c, e);
    case E_FIELD: return check_field(c, e);
    case E_CAST: return check_cast(c, e, e->a, complete(resolve_type_in(e->texpr, c->fn ? c : NULL), e->loc));
    case E_ARRAY: return check_array_lit(c, e, want);
    case E_STRUCT: return check_struct_lit(c, e);
    case E_SIZEOF: {
        Type *t = complete(resolve_type_in(e->texpr, c->fn ? c : NULL), e->loc);
        e->ty = ty_uint; e->isconst = 1; e->cval = t->size;
        return e;
    }
    case E_CONV: return e;
    case E_FUNC: return check_lambda(c, e, want);
    case E_MATCH: return check_match_expr(c, e, want);
    }
    return e;
}

/* ------------------------------------------------------------ constants */

const char *const_addr_label(Expr *e) {
    if (e->isconst) return NULL;
    switch (e->k) {
    case E_NAME:
        if (!e->sym) return NULL;
        if (e->sym->k == SY_EMBED) return e->sym->label;
        if (e->sym->k == SY_FUNC) return e->sym->fn->label;
        return NULL;
    case E_STR: return e->sym ? e->sym->label : NULL;
    case E_UNARY:   /* an array constant decayed to a pointer */
        return e->op == U_ADDR && e->a->k == E_NAME && e->a->sym && e->a->sym->k == SY_DATA ? e->a->sym->label : NULL;
    case E_CONV: {
        /* address-preserving conversions: to a pointer, u32 or s32 (a function: its code address) */
        Type *to = e->ty, *from = e->a->ty;
        int to_ok = to->k == TY_PTR || to->k == TY_U32 || to->k == TY_S32;
        int from_ok = from->k == TY_PTR || from->k == TY_FUNC;
        return to_ok && from_ok ? const_addr_label(e->a) : NULL;
    }
    default: return NULL;
    }
}

static int is_const_data(Expr *e) {
    if (e->k == E_ARRAY || e->k == E_STRUCT) {
        for (int i = 0; i < e->nargs; i++) if (!is_const_data(e->args[i])) return 0;
        return 1;
    }
    return e->isconst || const_addr_label(e) != NULL;
}

/* Functions named in const data must be emitted when the data is. */
static void collect_data_funcs(Sym *s, Expr *e) {
    if (!e) return;
    if (e->k == E_NAME && e->sym && e->sym->k == SY_FUNC) {
        for (int i = 0; i < s->ndfuncs; i++) if (s->dfuncs[i] == e->sym->fn) return;
        PUSH(s->dfuncs, s->ndfuncs, s->capdfuncs, e->sym->fn);
        return;
    }
    if (e->k == E_CONV) collect_data_funcs(s, e->a);
    if (e->k == E_ARRAY || e->k == E_STRUCT) for (int i = 0; i < e->nargs; i++) collect_data_funcs(s, e->args[i]);
}

static int g_lconst_n;

static void resolve_const(Sym *s) { resolve_const_in(s, NULL); }

/* A constant's value. `in`: the function a local constant is declared in (NULL: a global one). */
static void resolve_const_in(Sym *s, Ctx *in) {
    if (s->state == 2) return;
    if (s->state == 1) error_at(s->loc, "constant '%s' depends on itself", s->name);
    s->state = 1;
    Ctx c0 = {.P = g_prog};
    Ctx *c = in ? in : &c0;
    const char *label = in ? ar_printf("K_%s$L%d", s->name, ++g_lconst_n) : sym_label("K_", s);
    Type *t = s->texpr ? complete(resolve_type_in(s->texpr, in), s->loc) : NULL;
    if (s->init->k == E_STR && !t) {
        /* const NAME = "text": a NUL-terminated byte array in ROM */
        s->k = SY_DATA;
        s->is_str = 1; s->str = s->init->str; s->slen = s->init->slen;
        s->ty = ty_array(ty_u8, (int64_t)s->slen + 1);
        s->label = label;
        PUSH(g_prog->datas, g_prog->ndatas, g_prog->capdatas, s);
        s->state = 2;
        return;
    }
    const char *saved_in = g_in_local_const;
    g_in_local_const = in ? s->name : NULL;
    Expr *e = check(c, s->init, t);
    g_in_local_const = saved_in;
    if (!t) t = e->ty;   /* untyped constants stay untyped */
    if (ty_is_aggr(t)) {
        if (e->ty != t) error_at(e->loc, "type mismatch: '%s' is %s, initialiser is %s", s->name, ty_str(t), ty_str(e->ty));
        if (!is_const_data(e))
            error_at(e->loc, "the initialiser of constant '%s' must be built from constants (numbers, and the addresses "
                     "of embeds, strings, const data and functions)", s->name);
        collect_data_funcs(s, e);
        s->k = SY_DATA;
        s->ty = t;
        s->init = e;
        s->label = label;
        PUSH(g_prog->datas, g_prog->ndatas, g_prog->capdatas, s);
        s->state = 2;
        return;
    }
    if (t->k == TY_VOID || t->k == TY_NULL) error_at(e->loc, "cannot infer a type for constant '%s'", s->name);
    e = coerce(c, e, t, ar_printf("the value of '%s'", s->name));
    if (!e->isconst && const_addr_label(e))
        error_at(e->loc, "a single constant cannot hold an address; use the name directly, or put the addresses "
                 "in a const array or struct (const TABLE: [2]*Mesh = [A, B])");
    if (!e->isconst) error_at(e->loc, "the value of constant '%s' must be known at compile time", s->name);
    s->ty = t;
    s->cval = e->cval;
    memcpy(s->cvec, e->cvec, sizeof s->cvec);
    s->state = 2;
}

/* ------------------------------------------------------------ enums */

static void resolve_enum(Type *t) {
    EnumDecl *d = t->edecl;
    if (d->state == 2) return;
    if (d->state == 1) error_at(d->loc, "the values of enum '%s' depend on themselves", d->name);
    d->state = 1;
    Type *base = d->base ? resolve_type(d->base) : ty_s32;
    if (!ty_is_int(base)) error_at(d->base->loc, "an enum's underlying type must be an integer type, found %s", ty_str(base));
    t->elem = base;
    t->size = base->size;
    t->align = base->align;
    t->vnames = d->names;
    t->vvals = ar_alloc(sizeof(int64_t) * (size_t)d->n);
    t->nvariants = d->n;
    Ctx c = {.P = g_prog};
    int64_t next = 0;
    for (int i = 0; i < d->n; i++) {
        int64_t v = next;
        if (d->vals[i]) v = const_int(&c, d->vals[i], ar_printf("the value of %s.%s", d->name, d->names[i]));
        int ok = ty_is_signed(base) ? norm(base, v) == v : (v >= 0 && norm(base, v) == v);
        if (!ok) error_at(d->locs[i], "%s.%s = %lld does not fit in %s", d->name, d->names[i], (long long)v, base->name);
        for (int j = 0; j < i; j++)
            if (t->vvals[j] == v) error_at(d->locs[i], "%s.%s has the same value (%lld) as %s.%s", d->name, d->names[i], (long long)v, d->name, d->names[j]);
        t->vvals[i] = v;
        next = v + 1;
    }
    d->state = 2;
}

static int enum_variant(Type *t, const char *name) {
    for (int i = 0; i < t->nvariants; i++) if (!strcmp(t->vnames[i], name)) return i;
    return -1;
}

/* ------------------------------------------------------------ statements */

static int stmt_returns(Stmt *s) {
    if (!s) return 0;
    switch (s->k) {
    case S_RETURN: return 1;
    case S_BLOCK: for (int i = 0; i < s->n; i++) if (stmt_returns(s->list[i])) return 1; return 0;
    case S_IF: return s->els && stmt_returns(s->then) && stmt_returns(s->els);
    case S_WHILE: {
        /* `while true` without break never falls through */
        if (!(s->e->isconst && s->e->cval)) return 0;
        return !s->op;    /* op is set when a break leaves this loop */
    }
    case S_MATCH:
        if (!s->op) return 0;   /* op is set when the arms cover every value */
        for (int i = 0; i < s->narms; i++) if (!stmt_returns(s->arms[i].body)) return 0;
        return 1;
    default: return 0;
    }
}

static void check_block(Ctx *c, Stmt *b);


/* Checks the {name} references of asm text. Local constants are substituted here (their
   value, or the label of const data); returns the text to assemble. */
static const char *check_asm_refs(Ctx *c, const char *text, Loc loc) {
    Buf out = {0};
    const char *done = text;
    for (const char *p = text; *p; p++) {
        if (*p != '{') continue;
        const char *q = strchr(p, '}');
        if (!q) break;
        char *name = ar_strndup(p + 1, (size_t)(q - p - 1));
        Local *l = c->fn ? lookup_local(c, name) : NULL;
        if (l && l->csym) {
            Sym *k = l->csym;
            buf_putn(&out, done, (size_t)(p - done));
            if (k->k == SY_CONST) buf_printf(&out, "%lld", (long long)k->cval);
            else { note_ref(c, k); buf_puts(&out, k->label); }
            done = q + 1;
        } else if (l) {
            if (!ty_is_scalar(l->ty) && !ty_is_vec(l->ty))
                error_at(loc, "asm can only name scalar or vector locals ('%s' is %s); use a pointer", name, ty_str(l->ty));
            l->in_asm = 1;
            l->weight += 1000;
        } else {
            Sym *s = sym_lookup(name, loc.file);
            if (!s) error_at(loc, "unknown name '{%s}' in asm block", name);
            if (s->k == SY_FUNC) { note_call(c, s->fn); if (c->fn) c->fn->has_call = 1; }
            else if (s->k == SY_CONST) resolve_const(s);
            if (s->k == SY_DATA || s->k == SY_EMBED) note_ref(c, s);
            if (s->k == SY_TYPE || s->k == SY_BUILTIN) error_at(loc, "'{%s}' in asm must name a variable, constant or function", name);
        }
        p = q;
    }
    if (done == text) { buf_free(&out); return text; }
    buf_puts(&out, done);
    char *r = ar_strdup(out.p);
    buf_free(&out);
    return r;
}

/* A match's value and patterns: patterns are constants of the value's type (a bare variant
   name in a match on an enum), each value at most once; a match on an enum handles every
   variant or has an else arm, a match on an integer has an else arm. Returns the checked value. */
static Expr *check_match_head(Ctx *c, Expr *x, MatchArm *arms, int narms, Loc loc) {
    x = check(c, x, NULL);
    if (x->ty->k == TY_UINT) x = coerce(c, x, ty_s32, "the matched value");
    Type *t = x->ty;
    if (t->k != TY_ENUM && !ty_is_int(t))
        error_at(x->loc, "match needs an enum or an integer, found %s", ty_str(t));
    int64_t *seen = ar_alloc(sizeof(int64_t) * 4096);
    Loc *seenloc = ar_alloc(sizeof(Loc) * 4096);
    int nseen = 0, has_else = 0;
    for (int i = 0; i < narms; i++) {
        MatchArm *arm = &arms[i];
        if (arm->is_else) {
            if (has_else) error_at(arm->loc, "match has two else arms");
            if (i != narms - 1) error_at(arm->loc, "the else arm must come last");
            has_else = 1;
        }
        for (int k = 0; k < arm->npats; k++) {
            Expr *pe = arm->pats[k];
            if (t->k == TY_ENUM && pe->k == E_NAME && !(c->fn && lookup_local(c, pe->name)) && enum_variant(t, pe->name) >= 0) {
                /* a bare variant name: State.X can be written X in a match on a State */
                pe->ty = t;
                pe->isconst = 1;
                pe->cval = t->vvals[enum_variant(t, pe->name)];
            } else {
                pe = check(c, pe, t);
                if (pe->ty != t) pe = coerce(c, pe, t, "the pattern");
                if (!pe->isconst) error_at(pe->loc, "match patterns must be constants");
            }
            arm->pats[k] = pe;
            for (int j = 0; j < nseen; j++)
                if (seen[j] == pe->cval) error_at(pe->loc, "this value is already matched at line %d", seenloc[j].line);
            if (nseen == 4096) error_at(pe->loc, "too many match patterns");
            seen[nseen] = pe->cval;
            seenloc[nseen++] = pe->loc;
        }
    }
    if (t->k == TY_ENUM && !has_else) {
        Buf missing = {0};
        int nm = 0;
        for (int v = 0; v < t->nvariants; v++) {
            int found = 0;
            for (int j = 0; j < nseen; j++) if (seen[j] == t->vvals[v]) found = 1;
            if (!found) { buf_printf(&missing, "%s%s.%s", nm ? ", " : "", t->name, t->vnames[v]); nm++; }
        }
        if (nm) {
            char *m = ar_strdup(missing.p);
            buf_free(&missing);
            error_at(loc, "match on %s does not handle %s (add %s or an else arm)", t->name, m, nm == 1 ? "it" : "them");
        }
    }
    if (t->k != TY_ENUM && !has_else)
        error_at(loc, "match on %s needs an else arm (integers cannot be matched exhaustively)", ty_str(t));
    return x;
}

static void check_stmt(Ctx *c, Stmt *s) {
    switch (s->k) {
    case S_BLOCK: {
        Scope sc = {.up = c->scope};
        c->scope = &sc;
        check_block(c, s);
        c->scope = sc.up;
        break;
    }
    case S_VAR: {
        Type *t = s->texpr ? complete(resolve_type_in(s->texpr, c), s->loc) : NULL;
        Expr *init = s->e ? check(c, s->e, t) : NULL;
        if (!t) {
            t = default_type(init);
            if (t->k == TY_NULL) error_at(init->loc, "cannot infer the type of '%s' from null; give it a type", s->name);
            if (t->k == TY_VOID) error_at(init->loc, "the initialiser has no value");
        }
        if (t->k == TY_VOID) error_at(s->loc, "variables cannot be void");
        if (init) {
            if (ty_is_aggr(t)) { if (init->ty != t) error_at(init->loc, "type mismatch: '%s' is %s, initialiser is %s", s->name, ty_str(t), ty_str(init->ty)); }
            else init = coerce(c, init, t, ar_printf("the initial value of '%s'", s->name));
        }
        s->e = init;
        s->var = new_local(c, s->name, t, s->loc);
        s->var->immutable = s->is_let;
        if (t->k == TY_PTR && refs_local_storage(init)) s->var->points_local = 1;
        break;
    }
    case S_ASSIGN: {
        Expr *lhs = check(c, s->e, NULL);
        s->e = lhs;
        const char *why = not_assignable(lhs);
        if (why) error_at(lhs->loc, "cannot assign to this: %s", why);
        if (lhs->k == E_NAME && lhs->sym->k == SY_LOCAL) {
            int d = c->loop_depth > 6 ? 6 : c->loop_depth;
            lhs->sym->local->weight += (int64_t)1 << (2 * d);
        }
        if (s->op < 0) {
            Expr *rhs = check(c, s->e2, lhs->ty);
            if (ty_is_aggr(lhs->ty)) {
                if (rhs->ty != lhs->ty) error_at(rhs->loc, "type mismatch: assigning %s to %s", ty_str(rhs->ty), ty_str(lhs->ty));
            } else rhs = coerce(c, rhs, lhs->ty, "the assigned value");
            s->e2 = rhs;
            if (lhs->ty->k == TY_PTR && lhs->k == E_NAME && lhs->sym->k == SY_LOCAL && refs_local_storage(rhs))
                lhs->sym->local->points_local = 1;
        } else {
            Expr *bin = ar_alloc(sizeof *bin);
            bin->k = E_BINARY; bin->loc = s->loc; bin->op = (OpKind)s->op; bin->a = lhs; bin->b = s->e2;
            bin = check(c, bin, NULL);
            if (bin->k != E_BINARY) error_at(s->loc, "compound assignment is not supported for %s", ty_str(lhs->ty));
            if (bin->ty != lhs->ty && !(ty_is_int(bin->ty) && ty_is_int(lhs->ty)))
                error_at(s->loc, "result of '%s' is %s, which cannot be stored in %s", op_name(bin->op), ty_str(bin->ty), ty_str(lhs->ty));
            s->e2 = bin;
        }
        break;
    }
    case S_EXPR: {
        Expr *e = check(c, s->e, NULL);
        s->e = e;
        if (e->k == E_BINARY && e->op == B_EQ) error_at(e->loc, "'==' compares; use '=' to assign");
        if (e->k != E_CALL || (e->bi && e->bi < BI_MAP && !e->callee)) error_at(s->loc, "this expression does nothing (only calls and assignments are statements)");
        break;
    }
    case S_IF: {
        s->e = check(c, s->e, NULL);
        if (s->e->ty->k != TY_BOOL) error_at(s->e->loc, "condition must be bool, found %s", ty_str(s->e->ty));
        check_stmt(c, s->then);
        if (s->els) check_stmt(c, s->els);
        break;
    }
    case S_WHILE: {
        s->e = check(c, s->e, NULL);
        if (s->e->ty->k != TY_BOOL) error_at(s->e->loc, "condition must be bool, found %s", ty_str(s->e->ty));
        c->loop_depth++;
        g_loop_stack[g_loop_n++] = s;
        check_stmt(c, s->then);
        g_loop_n--;
        c->loop_depth--;
        break;
    }
    case S_FOR: {
        Type *t;
        if (!s->e2) {
            /* for d in Dir: every variant, in order of value (they must be consecutive) */
            Expr *n = s->e;
            Sym *ts = c->fn && lookup_local(c, n->name) ? NULL : sym_lookup(n->name, n->loc.file);
            if (!ts || ts->k != SY_TYPE || ts->ty->k != TY_ENUM)
                error_at(n->loc, "expected a range lo..hi or an enum type after 'in', found '%s'", n->name);
            t = ts->ty;
            resolve_enum(t);
            int64_t lo = t->vvals[0], hi = t->vvals[0];
            for (int i = 1; i < t->nvariants; i++) { if (t->vvals[i] < lo) lo = t->vvals[i]; if (t->vvals[i] > hi) hi = t->vvals[i]; }
            if (hi - lo + 1 != t->nvariants)
                error_at(n->loc, "'for %s in %s' needs variants with consecutive values, but %s's values run from %lld to %lld "
                         "with gaps; loop over a range of values instead", s->name, t->name, t->name, (long long)lo, (long long)hi);
            Type *b = ty_base(t);
            if (b->size < 4 && norm(b, hi + 1) != hi + 1)
                error_at(n->loc, "'for %s in %s': the last value of %s (%lld) is the largest %s, so the loop cannot count past it",
                         s->name, t->name, t->name, (long long)hi, b->name);
            Expr *elo = ar_alloc(sizeof *elo), *ehi = ar_alloc(sizeof *ehi);
            *elo = *n; elo->k = E_INT; elo->ty = t; elo->isconst = 1; elo->cval = lo;
            *ehi = *n; ehi->k = E_INT; ehi->ty = t; ehi->isconst = 1; ehi->cval = hi + 1;
            s->e = elo;
            s->e2 = ehi;
        } else {
            Expr *lo = check(c, s->e, NULL), *hi = check(c, s->e2, NULL);
            if (lo->ty->k == TY_ENUM || hi->ty->k == TY_ENUM) {
                /* for d in Dir.A..Dir.D: d is a Dir, counting through the values A, A+1, ... before D */
                if (lo->ty != hi->ty)
                    error_at(s->loc, "for-loop bounds must have one type (found %s and %s)", ty_str(lo->ty), ty_str(hi->ty));
                t = lo->ty;
            } else {
                if (!is_intish(lo->ty) || !is_intish(hi->ty)) error_at(s->loc, "for-loop bounds must be integers or values of one enum (found %s and %s)", ty_str(lo->ty), ty_str(hi->ty));
                t = arith_type(s->e, lo->ty, hi->ty, "..");
                if (t == ty_uint) t = ty_s32;
                lo = coerce(c, lo, t, "the loop start");
                hi = coerce(c, hi, t, "the loop end");
            }
            s->e = lo;
            s->e2 = hi;
        }
        Scope sc = {.up = c->scope};
        c->scope = &sc;
        c->loop_depth++;
        s->for_end = new_local(c, "", t, s->loc);
        s->for_end->immutable = 1;
        s->for_end->weight = 4;
        s->var = new_local(c, s->name, t, s->asm_loc);
        s->var->immutable = 1;
        s->var->is_loopvar = 1;
        s->var->weight += 4 << (2 * (c->loop_depth > 6 ? 6 : c->loop_depth));
        g_loop_stack[g_loop_n++] = s;
        check_stmt(c, s->then);
        g_loop_n--;
        c->loop_depth--;
        c->scope = sc.up;
        break;
    }
    case S_BREAK: case S_CONTINUE:
        if (!g_loop_n) error_at(s->loc, "'%s' outside a loop", s->k == S_BREAK ? "break" : "continue");
        if (s->k == S_BREAK && g_loop_stack[g_loop_n - 1]->k == S_WHILE) g_loop_stack[g_loop_n - 1]->op = 1;
        break;
    case S_RETURN: {
        Type *rt = c->fn->ret;
        if (c->fn->is_init) error_at(s->loc, "return outside a function");
        if (!s->e) {
            if (rt->k != TY_VOID) error_at(s->loc, "%s() must return a %s value", c->fn->name, ty_str(rt));
            break;
        }
        if (rt->k == TY_VOID) error_at(s->e->loc, "%s() does not return a value", c->fn->name);
        Expr *v = check(c, s->e, rt);
        if (ty_is_aggr(rt)) { if (v->ty != rt) error_at(v->loc, "type mismatch: returning %s, expected %s", ty_str(v->ty), ty_str(rt)); }
        else v = coerce(c, v, rt, "the return value");
        s->e = v;
        break;
    }
    case S_MATCH:
        s->e = check_match_head(c, s->e, s->arms, s->narms, s->loc);
        for (int i = 0; i < s->narms; i++) {
            Scope sc = {.up = c->scope};
            c->scope = &sc;
            check_stmt(c, s->arms[i].body);
            c->scope = sc.up;
        }
        s->op = 1;   /* exhaustive */
        break;
    case S_CONST: {
        Sym *k = ar_alloc(sizeof *k);
        k->k = SY_CONST;
        k->name = s->name;
        k->loc = s->loc;
        k->texpr = s->texpr;
        k->init = s->e;
        resolve_const_in(k, c);
        Local *l = declare_local_const(c, s->name, s->loc);
        l->csym = k;
        break;
    }
    case S_ASM:
        c->fn->has_asm = 1;
        s->asm_text = check_asm_refs(c, s->asm_text, s->asm_loc);
        break;
    }
}

static void check_block(Ctx *c, Stmt *b) {
    for (int i = 0; i < b->n; i++) check_stmt(c, b->list[i]);
}

/* ------------------------------------------------------------ program */

static void check_signature(Func *f) {
    if (f->label) return;
    f->ret = f->ret_texpr ? complete(resolve_type(f->ret_texpr), f->ret_texpr->loc) : ty_void;
    if (f->ret->k == TY_ARRAY) error_at(f->ret_texpr->loc, "functions cannot return arrays; wrap the array in a struct");
    for (int i = 0; i < f->nparams; i++) {
        Param *p = &f->params[i];
        p->ty = complete(resolve_type(p->texpr), p->loc);
        if (p->ty->k == TY_VOID) error_at(p->loc, "parameters cannot be void");
        if (f->is_asm && ty_is_aggr(p->ty)) error_at(p->loc, "asm functions take scalars, vectors and pointers only");
    }
    if (f->is_asm && ty_is_aggr(f->ret)) error_at(f->ret_texpr->loc, "asm functions cannot return %s", ty_str(f->ret));
    f->label = sym_label("F_", f->sym);
    const char *n = f->name;
    if (f->sym->priv && f->sym->user && (!strcmp(n, "init") || !strcmp(n, "update") || !strcmp(n, "draw")))
        error_at(f->loc, "%s() is called by the runtime, so it cannot be private", n);
    if (!strcmp(n, "init") || !strcmp(n, "update") || !strcmp(n, "draw")) {
        if (f->nparams || f->ret->k != TY_VOID) error_at(f->loc, "%s() must take no arguments and return nothing", n);
    }
}

static void make_hidden_ret(Func *f) {
    if (ty_is_aggr(f->ret)) {
        f->hidden_ret = ar_alloc(sizeof(Local));
        f->hidden_ret->name = "";
        f->hidden_ret->ty = ty_ptr(f->ret);
        f->hidden_ret->is_param = 1;
        f->hidden_ret->immutable = 1;
        f->hidden_ret->weight = 2;
        PUSH(f->locals, f->nlocals, f->caplocals, f->hidden_ret);
    }
}

/* Checks a function's body; `outer` is the enclosing function's context for literals. */
static void check_func_body(Program *P, Func *f, Ctx *outer) {
    Ctx c = {.P = P, .fn = f, .outer = outer};
    Scope sc = {0};
    c.scope = &sc;
    if (f->ret) make_hidden_ret(f);
    for (int i = 0; i < f->nparams; i++) {
        Param *p = &f->params[i];
        Local *l = new_local(&c, p->name, p->ty, p->loc);
        l->is_param = 1;
        l->immutable = ty_is_aggr(p->ty);
        p->local = l;
    }
    if (f->is_asm) { check_asm_refs(&c, f->asm_text, f->asm_loc); return; }
    if (f->lambda_body) {
        /* fn(x) => expr: the body is `return expr` (or the call, for no result) */
        Expr *v = check(&c, f->lambda_body, f->ret);
        if (!f->ret) {
            f->ret = v->ty->k == TY_VOID ? ty_void : default_type(v);
            if (f->ret->k == TY_NULL) error_at(v->loc, "cannot infer the result type from null; write the type with '->'");
            if (f->ret->k == TY_ARRAY) error_at(v->loc, "functions cannot return arrays; wrap the array in a struct");
            make_hidden_ret(f);
        }
        Stmt *st = ar_alloc(sizeof *st);
        st->loc = v->loc;
        if (f->ret->k == TY_VOID) {
            if (v->ty->k != TY_VOID && v->k != E_CALL) error_at(v->loc, "this function literal returns nothing, so its body must be a call");
            st->k = S_EXPR;
        } else {
            if (ty_is_aggr(f->ret)) { if (v->ty != f->ret) error_at(v->loc, "type mismatch: the result is %s, expected %s", ty_str(v->ty), ty_str(f->ret)); }
            else v = coerce(&c, v, f->ret, "the result");
            st->k = S_RETURN;
        }
        st->e = v;
        f->body = ar_alloc(sizeof(Stmt));
        f->body->k = S_BLOCK;
        f->body->loc = v->loc;
        f->body->list = ar_alloc(sizeof(Stmt *));
        f->body->list[0] = st;
        f->body->n = 1;
        return;
    }
    check_block(&c, f->body);
    if (f->ret->k != TY_VOID && !stmt_returns(f->body))
        error_at(f->loc, "%s can reach its end without returning a %s",
                 f->is_lambda ? f->name : ar_printf("%s()", f->name), ty_str(f->ret));
}

static void check_func(Program *P, Func *f) {
    if (f->checked) return;
    f->checked = 1;
    check_func_body(P, f, NULL);
}

/* An embed's type and byte range; resolved on first use (constants may refer to it). */
static void resolve_embed(Sym *s) {
    if (s->state == 2) return;
    if (s->state == 1) error_at(s->loc, "the offset or length of embed '%s' depends on itself", s->name);
    s->state = 1;
    Type *t = s->texpr ? complete(resolve_type(s->texpr), s->loc) : ty_u8;
    if (t->size == 0) error_at(s->loc, "cannot embed data as a zero-sized type");
    s->ty = ty_ptr(t);
    s->label = sym_label("E_", s);
    Ctx c = {.P = g_prog};
    int64_t off = s->off_e ? const_int(&c, s->off_e, "embed offset") : 0;
    int64_t len = s->len_e ? const_int(&c, s->len_e, "embed length") : (int64_t)s->datalen - off;
    if (off < 0 || off > (int64_t)s->datalen || len < 0 || off + len > (int64_t)s->datalen)
        error_at(s->loc, "embed range %lld+%lld is outside '%s' (%zu bytes)", (long long)off, (long long)len, s->path, s->datalen);
    s->data += off;
    s->datalen = (size_t)len;
    s->state = 2;
}

void check_program(Program *P) {
    g_prog = P;
    g_loop_n = 0;
    for (int i = 0; i < P->nenums; i++) resolve_enum(P->enums[i]->ty);
    for (int i = 0; i < P->nstructs; i++) layout_struct(P->structs[i]->ty, P->structs[i]->loc);
    for (int i = 0; i < P->nconsts; i++) resolve_const(P->consts[i]);
    for (int i = 0; i < P->nregs; i++) {
        Sym *s = P->regs[i];
        s->ty = resolve_type(s->texpr);
        if (s->ty->size != 4 || !ty_is_scalar(s->ty))
            error_at(s->loc, "I/O registers are 32 bits wide; declare '%s' as u32, s32, fixed or a pointer", s->name);
        Ctx c = {.P = P};
        int64_t a = const_int(&c, s->init, "register address");
        if (a < 0 || a > 0xFFFFFF || (a & 3)) error_at(s->init->loc, "register address must be a word-aligned 24-bit address");
        s->addr = (uint32_t)a;
    }
    for (int i = 0; i < P->ndatas; i++) if (P->datas[i]->k == SY_EMBED) resolve_embed(P->datas[i]);
    for (int i = 0; i < P->nfuncs; i++) check_signature(P->funcs[i]);
    for (int i = 0; i < P->nglobals; i++) {
        Sym *s = P->globals[i];
        if (s->texpr) s->ty = complete(resolve_type(s->texpr), s->loc);
        if (s->ty && s->ty->k == TY_VOID) error_at(s->loc, "variables cannot be void");
        s->label = sym_label("G_", s);
    }
    /* global initialisers become the body of a synthesized function, in declaration order */
    Func *init = ar_alloc(sizeof *init);
    init->name = "global initialisers";
    init->label = "F__init_globals";
    init->is_init = 1;
    init->ret = ty_void;
    init->body = ar_alloc(sizeof(Stmt));
    init->body->k = S_BLOCK;
    int cap = 0;
    {
        Ctx c = {.P = P, .fn = init};
        Scope sc = {0};
        c.scope = &sc;
        for (int i = 0; i < P->nglobals; i++) {
            Sym *s = P->globals[i];
            if (!s->init) continue;
            Type *t = s->ty;
            Expr *v = check(&c, s->init, t);
            if (!t) {
                t = default_type(v);
                if (t->k == TY_NULL || t->k == TY_VOID) error_at(v->loc, "cannot infer the type of '%s'", s->name);
                s->ty = t;
            }
            if (ty_is_aggr(t)) { if (v->ty != t) error_at(v->loc, "type mismatch: '%s' is %s, initialiser is %s", s->name, ty_str(t), ty_str(v->ty)); }
            else v = coerce(&c, v, t, ar_printf("the initial value of '%s'", s->name));
            Stmt *st = ar_alloc(sizeof *st);
            st->k = S_ASSIGN; st->loc = s->loc; st->op = -1;
            Expr *lhs = ar_alloc(sizeof *lhs);
            lhs->k = E_NAME; lhs->loc = s->loc; lhs->name = s->name; lhs->sym = s; lhs->ty = t;
            st->e = lhs;
            st->e2 = v;
            PUSH(init->body->list, init->body->n, cap, st);
        }
    }
    P->init_fn = init;
    for (int i = 0; i < P->nfuncs; i++) check_func(P, P->funcs[i]);   /* literals are appended and already checked */
}
