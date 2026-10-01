/* Code generator: checked AST -> Mei assembly text.
 *
 * Tree-based code generation with a small register allocator:
 *  - scalar locals that never have their address taken live in registers for the whole
 *    function (r9-r13 in functions that make calls; any free register in leaf functions);
 *    vector locals live in v registers in leaf functions; everything else lives in the frame.
 *  - expression temporaries come from the remaining registers. When none is free, the oldest
 *    unlocked temporary is spilled to a frame slot and reloaded on its next use. Around a call,
 *    temporaries in caller-saved registers move to free callee-saved registers or are spilled.
 *  - temporaries never live across statements, and short-circuit operators in value context
 *    flush live temporaries first, so the register state is identical at every join point. */
#include "internal.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define NT 512

typedef struct { int cls, reg, slot, live, lock, resv; unsigned age; } Temp;
typedef enum { O_NONE, O_IMM, O_TMP, O_REG, O_VTMP, O_VREG } OKind;
typedef struct { OKind k; int32_t v; } Opnd;
enum { LV_REG, LV_VREG, LV_VLANE, LV_MEM };
typedef struct {
    int k;
    int reg, lane;
    Opnd base;
    const char *sym;      /* symbolic part of the address (low RAM globals, base r0) */
    int64_t symval;
    int32_t off;
    Type *ty;
    int frame_rel;        /* offset is relative to the caller's frame (incoming stack args) */
} LV;
typedef struct { Opnd o; Type *t; } Arg;

static Buf g_body;
static Func *g_fn;
static Program *g_P;
static int g_leaf;
static Temp g_t[NT];
static unsigned g_age;
static int g_rown[16];             /* -1 free, -2 not allocatable, else temp id */
static int g_vown[8];
static int g_spool[16], g_nspool;
static int g_vpool[8], g_nvpool;
static int g_saved;                /* callee-saved registers written by this function */
static int g_frame, g_frame_max;   /* temporary slot area (offsets from sp) */
static int g_label;
static int g_ret_label;
static int g_brk[128], g_cont[128], g_nloop;
static int g_out_size;
static int g_iobase_reg;           /* register holding 0xFF0000, or -1 */

static const char *RN[16] = {"r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11", "r12", "r13", "sp", "ra"};
static const char *VN[8] = {"v0", "v1", "v2", "v3", "v4", "v5", "v6", "v7"};

static _Noreturn void ice(const char *what) { error_plain("internal compiler error: %s (in %s)", what, g_fn ? g_fn->name : "?"); }

/* ------------------------------------------------------------- emission */

static void unlock_all(void) { for (int i = 0; i < NT; i++) g_t[i].lock = 0; }

static void emitv(const char *fmt, va_list ap) {
    buf_puts(&g_body, "    ");
    buf_vprintf(&g_body, fmt, ap);
    buf_putc(&g_body, '\n');
}

/* An instruction; afterwards no temporary is locked. */
static void I(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    emitv(fmt, ap);
    va_end(ap);
    unlock_all();
}

/* Internal spill/reload code: keeps locks. */
static void Ik(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    emitv(fmt, ap);
    va_end(ap);
}

static int new_label(void) { return ++g_label; }
static void put_label(int l) { buf_printf(&g_body, ".L%d:\n", l); }

static int slot_alloc(int size) {
    int off = (g_frame + 3) & ~3;
    g_frame = off + ((size + 3) & ~3);
    if (g_frame > g_frame_max) g_frame_max = g_frame;
    return off;
}

/* ------------------------------------------------------------- temporaries */

static void t_spill(int t) {
    Temp *x = &g_t[t];
    if (x->reg < 0) return;
    if (x->slot < 0) x->slot = slot_alloc(x->cls ? 16 : 4);
    if (x->cls) { Ik("vst %s, [sp+%d]", VN[x->reg], x->slot); g_vown[x->reg] = x->resv ? -2 : -1; }
    else { Ik("sw %s, [sp+%d]", RN[x->reg], x->slot); g_rown[x->reg] = x->resv ? -2 : -1; }
    x->reg = -1;
    x->resv = 0;
}

static int find_free(int cls) {
    if (cls) { for (int i = 0; i < g_nvpool; i++) if (g_vown[g_vpool[i]] == -1) return g_vpool[i]; }
    else for (int i = 0; i < g_nspool; i++) if (g_rown[g_spool[i]] == -1) return g_spool[i];
    return -1;
}

static int take_reg(int cls) {
    int r = find_free(cls);
    if (r >= 0) return r;
    int best = -1;
    for (int i = 0; i < NT; i++) {
        Temp *x = &g_t[i];
        if (x->live && x->cls == cls && x->reg >= 0 && !x->lock && (best < 0 || x->age < g_t[best].age)) best = i;
    }
    if (best < 0) ice("out of registers");
    r = g_t[best].reg;
    t_spill(best);
    return r;
}

static void own(int t, int r) {
    Temp *x = &g_t[t];
    x->reg = r;
    if (x->cls) g_vown[r] = t;
    else { g_rown[r] = t; if (r >= 9 && r <= 13) g_saved |= 1 << r; }
}

static int t_alloc_id(int cls) {
    for (int i = 0; i < NT; i++) if (!g_t[i].live) {
        g_t[i] = (Temp){.cls = cls, .reg = -1, .slot = -1, .live = 1, .lock = 1, .age = ++g_age};
        return i;
    }
    ice("expression too complex");
}

static int tnew(int cls) {
    int r = take_reg(cls);
    int t = t_alloc_id(cls);
    own(t, r);
    return t;
}

/* A temporary in a specific (free) register, e.g. a call result. */
static int tnew_at(int cls, int r) {
    int o = cls ? g_vown[r] : g_rown[r];
    if (o >= 0) ice("result register busy");
    int t = t_alloc_id(cls);
    g_t[t].resv = o == -2;   /* a register of locals that are not live here */
    own(t, r);
    return t;
}

static int treg(int t) {
    Temp *x = &g_t[t];
    if (!x->live) ice("use of a dead temporary");
    if (x->reg < 0) {
        x->lock = 1;
        int r = take_reg(x->cls);
        if (x->cls) Ik("vld %s, [sp+%d]", VN[r], x->slot);
        else Ik("lw %s, [sp+%d]", RN[r], x->slot);
        own(t, r);
    }
    x->lock = 1;
    return x->reg;
}

static void tfree(int t) {
    Temp *x = &g_t[t];
    if (!x->live) return;
    if (x->reg >= 0) { if (x->cls) g_vown[x->reg] = x->resv ? -2 : -1; else g_rown[x->reg] = x->resv ? -2 : -1; }
    x->live = 0;
}

static int live_temps(void) { int n = 0; for (int i = 0; i < NT; i++) n += g_t[i].live; return n; }

/* Spill every live temporary (before branches inside an expression). */
static void flush_temps(void) {
    for (int i = 0; i < NT; i++) if (g_t[i].live && g_t[i].reg >= 0) t_spill(i);
}

/* ------------------------------------------------------------- operands */

static Opnd o_imm(int64_t v) { return (Opnd){O_IMM, (int32_t)(uint32_t)v}; }
static Opnd o_tmp(int t) { return (Opnd){g_t[t].cls ? O_VTMP : O_TMP, t}; }

static void li(int r, int32_t v) {
    if (v == 0) I("mov %s, r0", RN[r]);
    else if (fits_s18(v)) I("addi %s, r0, %d", RN[r], v);
    else if (((uint32_t)v & 0x3FF) == 0) I("lui %s, %u", RN[r], (uint32_t)v >> 10);
    else I("li %s, %d", RN[r], v);
}

static int R(Opnd *o) {
    switch (o->k) {
    case O_IMM: {
        if (o->v == 0) return 0;
        int t = tnew(0);
        li(g_t[t].reg, o->v);
        g_t[t].lock = 1;
        *o = o_tmp(t);
        return g_t[t].reg;
    }
    case O_TMP: return treg(o->v);
    case O_REG: return o->v;
    default: ice("expected a scalar operand");
    }
}

static int VR(Opnd *o) {
    if (o->k == O_VTMP) return treg(o->v);
    if (o->k == O_VREG) return o->v;
    ice("expected a vector operand");
}

static void ofree(Opnd o) { if (o.k == O_TMP || o.k == O_VTMP) tfree(o.v); }

/* Destination for a result: the hint register, or a new temporary. */
static Opnd dest(int cls, int hint, int *reg) {
    if (hint >= 0) { *reg = hint; return (Opnd){cls ? O_VREG : O_REG, hint}; }
    int t = tnew(cls);
    *reg = g_t[t].reg;
    return o_tmp(t);
}

/* Makes sure the value is in an owned temporary (so it may be modified). */
static Opnd owned(Opnd o, int cls) {
    if (o.k == O_TMP || o.k == O_VTMP) return o;
    if (cls) {
        int s = VR(&o), r;
        Opnd d = dest(1, -1, &r);
        I("vmov %s, %s", VN[r], VN[s]);
        return d;
    }
    if (o.k == O_IMM) { R(&o); return o; }
    int s = R(&o), r;
    Opnd d = dest(0, -1, &r);
    I("mov %s, %s", RN[r], RN[s]);
    return d;
}

/* Moves an operand into a specific register (no ownership change). */
static void move_to(Opnd o, int r, int cls) {
    if (cls) { int s = VR(&o); if (s != r) I("vmov %s, %s", VN[r], VN[s]); return; }
    if (o.k == O_IMM) { li(r, o.v); return; }
    int s = R(&o);
    if (s != r) I("mov %s, %s", RN[r], RN[s]);
}

/* ------------------------------------------------------------- forward */

static Opnd gen_expr(Expr *e, int hint);
static LV gen_lv(Expr *e);
static void gen_cond(Expr *e, int label, int jump_if);
static void gen_stmt(Stmt *s);
static Opnd lv_addr(LV *lv);
static Opnd arith(OpKind op, Type *ty, int mixed, Opnd a, Opnd b, int hint);

static int log2_exact(int64_t v) {
    if (v <= 0 || (v & (v - 1))) return -1;
    int n = 0;
    while ((1LL << n) != v) n++;
    return n;
}

/* Lives in a vector register: vectors, and function values ([code, 3 captured words]). */
static int is_v(Type *t) { return ty_is_vec(t) || t->k == TY_FUNC; }

static int is_small_int(Type *t) { t = ty_base(t); return t->k == TY_S8 || t->k == TY_U8 || t->k == TY_S16 || t->k == TY_U16; }

/* Sign/zero-extends register r in place to the canonical form of type t. */
static void normalize(int d, int s, Type *t) {
    switch (ty_base(t)->k) {
    case TY_S8: I("shli %s, %s, 24", RN[d], RN[s]); I("sari %s, %s, 24", RN[d], RN[d]); break;
    case TY_S16: I("shli %s, %s, 16", RN[d], RN[s]); I("sari %s, %s, 16", RN[d], RN[d]); break;
    case TY_U8: I("andi %s, %s, 255", RN[d], RN[s]); break;
    case TY_U16: I("andi %s, %s, 65535", RN[d], RN[s]); break;
    default: if (d != s) I("mov %s, %s", RN[d], RN[s]); break;
    }
}

/* ------------------------------------------------------------- lvalues */

static void lv_fix(LV *lv) {
    if (lv->frame_rel) return;
    int64_t total = lv->symval + lv->off;
    if (fits_s18(total)) return;
    /* fold the address into a register */
    if (lv->base.k == O_REG && lv->base.v == 0) {
        Opnd a = o_imm(total);
        R(&a);
        lv->base = a;
    } else lv->base = arith(B_ADD, ty_u32, 0, lv->base, o_imm(total), -1);
    lv->sym = NULL; lv->symval = 0; lv->off = 0;
}

static const char *mem(LV *lv) {
    int b = R(&lv->base);
    if (lv->frame_rel) return ar_printf("[%s+%d+\001]", RN[b], lv->off);
    if (lv->sym) return lv->off ? ar_printf("[%s+%s+%d]", RN[b], lv->sym, lv->off) : ar_printf("[%s+%s]", RN[b], lv->sym);
    if (lv->off == 0) return ar_printf("[%s]", RN[b]);
    return ar_printf("[%s%+d]", RN[b], lv->off);
}

static LV lv_mem(Opnd base, int32_t off, Type *t) {
    LV lv = {.k = LV_MEM, .base = base, .off = off, .ty = t};
    if (base.k == O_IMM) {
        /* constant address */
        if (fits_s18((int64_t)(uint32_t)base.v + off)) { lv.base = (Opnd){O_REG, 0}; lv.off = (int32_t)((uint32_t)base.v + (uint32_t)off); }
        else R(&lv.base);
    }
    return lv;
}

static LV lv_abs(uint32_t addr, const char *sym, Type *t) {
    LV lv = {.k = LV_MEM, .ty = t, .base = {O_REG, 0}};
    if (addr < 0x20000) { lv.sym = sym; lv.symval = addr; return lv; }
    if (g_iobase_reg >= 0 && addr >= IO_BASE_ADDR && addr < IO_BASE_ADDR + 0x400) {
        lv.base = (Opnd){O_REG, g_iobase_reg};
        lv.off = (int32_t)(addr - IO_BASE_ADDR);
        return lv;
    }
    int tt = tnew(0);
    I("lui %s, %u", RN[g_t[tt].reg], addr >> 10);
    lv.base = o_tmp(tt);
    lv.off = (int32_t)(addr & 0x3FF);
    return lv;
}

static LV lv_label(const char *label, Type *t) {
    int tt = tnew(0);
    I("la %s, %s", RN[g_t[tt].reg], label);
    return lv_mem(o_tmp(tt), 0, t);
}

static LV lv_local(Local *l) {
    if (l->home == 1) {
        if (ty_is_aggr(l->ty)) return lv_mem((Opnd){O_REG, l->reg}, 0, l->ty);   /* by-reference param */
        return (LV){.k = LV_REG, .reg = l->reg, .ty = l->ty};
    }
    if (l->home == 2) return (LV){.k = LV_VREG, .reg = l->reg, .ty = l->ty};
    LV lv = lv_mem((Opnd){O_REG, 14}, l->off, l->ty);
    if (l->is_param && !l->in_reg_arg) { lv.frame_rel = 1; lv.off = l->stack_arg_off; }
    if (ty_is_aggr(l->ty) && l->is_param) {
        /* by-reference parameter spilled to memory: load the pointer */
        int t = tnew(0);
        I("lw %s, %s", RN[g_t[t].reg], mem(&lv));
        return lv_mem(o_tmp(t), 0, l->ty);
    }
    return lv;
}

static void lv_free(LV *lv) { if (lv->k == LV_MEM) ofree(lv->base); }

/* Adds a scaled index to a memory lvalue. */
static void lv_index(LV *lv, Expr *idx, int size) {
    if (idx->isconst) { lv->off += (int32_t)(idx->cval * size); return; }
    Opnd i = gen_expr(idx, -1);
    int sh = log2_exact(size);
    Opnd sc = sh == 0 ? i : sh > 0 ? arith(B_SHL, ty_s32, 0, i, o_imm(sh), -1) : arith(B_MUL, ty_s32, 0, i, o_imm(size), -1);
    if (lv->base.k == O_REG && lv->base.v == 0) { lv->base = sc; return; }   /* absolute: the index becomes the base */
    lv->base = arith(B_ADD, ty_u32, 0, lv->base, sc, -1);
}

/* An lvalue (or aggregate rvalue) in memory or a register. */
static LV gen_aggr_lv(Expr *e);

static LV gen_lv(Expr *e) {
    switch (e->k) {
    case E_NAME: {
        Sym *s = e->sym;
        switch (s->k) {
        case SY_LOCAL: return lv_local(s->local);
        case SY_GLOBAL: return lv_abs(s->addr, s->label, s->ty);
        case SY_REG: return lv_abs(s->addr, NULL, s->ty);
        case SY_DATA: return lv_label(s->label, s->ty);
        default: ice("bad lvalue name");
        }
    }
    case E_UNARY:
        if (e->op == U_DEREF) { Opnd p = gen_expr(e->a, -1); return lv_mem(p, 0, e->ty); }
        break;
    case E_INDEX: {
        Type *bt = e->a->ty;
        LV lv;
        int size;
        if (bt->k == TY_PTR) { lv = lv_mem(gen_expr(e->a, -1), 0, e->ty); size = e->ty->size; }
        else if (bt->k == TY_MAT4) { lv = gen_aggr_lv(e->a); size = 16; }
        else { lv = gen_aggr_lv(e->a); size = bt->elem->size; }
        if (lv.k != LV_MEM) ice("indexing a register value");
        if (lv.frame_rel && !e->b->isconst) {
            /* make the frame-relative address absolute */
            Opnd a = lv_addr(&lv);
            lv = lv_mem(a, 0, e->ty);
        }
        lv_index(&lv, e->b, size);
        lv.ty = e->ty;
        return lv;
    }
    case E_FIELD: {
        if (e->field) {
            LV lv;
            if (e->a->ty->k == TY_PTR) lv = lv_mem(gen_expr(e->a, -1), 0, e->ty);
            else lv = gen_aggr_lv(e->a);
            lv.off += e->field->offset;
            lv.ty = e->ty;
            return lv;
        }
        if (e->nlanes == 1) {
            LV lv = gen_lv(e->a);
            if (lv.k == LV_VREG) { lv.k = LV_VLANE; lv.lane = e->lanes[0]; lv.ty = e->ty; return lv; }
            if (lv.k == LV_MEM) { lv.off += 4 * e->lanes[0]; lv.ty = e->ty; return lv; }
        }
        break;
    }
    case E_CALL: case E_ARRAY: case E_STRUCT:
        if (ty_is_aggr(e->ty)) return gen_aggr_lv(e);
        break;
    default: break;
    }
    ice("expression is not an lvalue");
}

static int lv_able(Expr *e) {
    switch (e->k) {
    case E_NAME: return e->sym && (e->sym->k == SY_LOCAL || e->sym->k == SY_GLOBAL || e->sym->k == SY_REG || e->sym->k == SY_DATA);
    case E_UNARY: return e->op == U_DEREF;
    case E_INDEX: return 1;
    case E_FIELD: return e->field ? 1 : (e->nlanes == 1 && lv_able(e->a) && !e->a->isconst);
    default: return ty_is_aggr(e->ty);
    }
}

/* A new temporary holding the address of lv (lv is not consumed). */
static Opnd lv_addr_copy(LV *lv) {
    if (lv->k != LV_MEM) ice("address of a register value");
    lv_fix(lv);
    int b = R(&lv->base);
    int r;
    Opnd d = dest(0, -1, &r);
    if (lv->frame_rel) I("addi %s, %s, %d+\001", RN[r], RN[b], lv->off);
    else if (lv->sym) I("addi %s, %s, %s+%d", RN[r], RN[b], lv->sym, lv->off);
    else I("addi %s, %s, %d", RN[r], RN[b], lv->off);
    return d;
}

/* The address of lv as an operand; consumes lv. */
static Opnd lv_addr(LV *lv) {
    if (lv->k != LV_MEM) ice("address of a register value");
    if (!lv->frame_rel && !lv->sym && lv->off == 0 && lv->base.k != O_REG) return lv->base;
    if (!lv->frame_rel && lv->base.k == O_REG && lv->base.v == 0) return o_imm(lv->symval + lv->off);
    if (!lv->frame_rel && !lv->sym && lv->off == 0 && lv->base.v != 14) return lv->base;
    Opnd d = lv_addr_copy(lv);
    lv_free(lv);
    return d;
}

/* ------------------------------------------------------------- loads/stores */

static const char *load_op(Type *t) {
    switch (ty_base(t)->k) {
    case TY_S8: return "lb";
    case TY_U8: case TY_BOOL: return "lbu";
    case TY_S16: return "lh";
    case TY_U16: return "lhu";
    default: return "lw";
    }
}
static const char *store_op(Type *t) {
    switch (t->size) { case 1: return "sb"; case 2: return "sh"; default: return "sw"; }
}

static Opnd load_lv(LV *lv, int hint) {
    Type *t = lv->ty;
    switch (lv->k) {
    case LV_REG: return (Opnd){O_REG, lv->reg};
    case LV_VREG: return (Opnd){O_VREG, lv->reg};
    case LV_VLANE: { int r; Opnd d = dest(0, hint, &r); I("vget %s, %s, %d", RN[r], VN[lv->reg], lv->lane); return d; }
    default: break;
    }
    if (ty_is_aggr(t)) return lv_addr(lv);
    lv_fix(lv);
    const char *m = mem(lv);
    lv_free(lv);
    int r;
    if (is_v(t)) { Opnd d = dest(1, hint, &r); I("vld %s, %s", VN[r], m); return d; }
    Opnd d = dest(0, hint, &r);
    I("%s %s, %s", load_op(t), RN[r], m);
    return d;
}

static void copy_mem(LV *dst, LV *src, int size, int align);

/* Stores `v` (of type vt) into lv. Consumes v. */
static void store_lv_k(LV *lv, Opnd v, Type *vt, int keep) {
    Type *t = lv->ty;
    switch (lv->k) {
    case LV_REG:
        if (is_small_int(t) && ty_base(vt) != ty_base(t)) { int s = R(&v); normalize(lv->reg, s, t); }
        else move_to(v, lv->reg, 0);
        ofree(v);
        return;
    case LV_VREG: move_to(v, lv->reg, 1); ofree(v); return;
    case LV_VLANE: { int s = R(&v); I("vset %s, %s, %d", VN[lv->reg], RN[s], lv->lane); ofree(v); return; }
    default: break;
    }
    lv_fix(lv);
    if (is_v(t)) {
        int s = VR(&v);
        I("vst %s, %s", VN[s], mem(lv));
    } else {
        int s = R(&v);
        I("%s %s, %s", store_op(t), RN[s], mem(lv));
    }
    ofree(v);
    if (!keep) lv_free(lv);
}

static void store_lv(LV *lv, Opnd v, Type *vt) { store_lv_k(lv, v, vt, 0); }

static void copy_mem(LV *dst, LV *src, int size, int align) {
    lv_fix(dst);
    lv_fix(src);
    if (size > 128 && align >= 4) {
        /* loop: 16 bytes per iteration, then the tail */
        Opnd d = lv_addr_copy(dst), s = lv_addr_copy(src);
        int n16 = size / 16;
        int cnt = tnew(0);
        li(g_t[cnt].reg, n16);
        int vt = tnew(1);
        int l = new_label();
        put_label(l);
        I("vld %s, [%s]", VN[treg(vt)], RN[R(&s)]);
        I("vst %s, [%s]", VN[treg(vt)], RN[R(&d)]);
        I("addi %s, %s, 16", RN[R(&s)], RN[R(&s)]);
        I("addi %s, %s, 16", RN[R(&d)], RN[R(&d)]);
        I("addi %s, %s, -1", RN[treg(cnt)], RN[treg(cnt)]);
        I("bne %s, r0, .L%d", RN[treg(cnt)], l);
        for (int o = 0; o < size % 16; o += 4) {
            int t = tnew(0);
            I("lw %s, [%s%+d]", RN[g_t[t].reg], RN[R(&s)], o);
            I("sw %s, [%s%+d]", RN[treg(t)], RN[R(&d)], o);
            tfree(t);
        }
        tfree(vt); tfree(cnt); ofree(d); ofree(s);
        return;
    }
    if (size > 128) {
        Opnd d = lv_addr_copy(dst), s = lv_addr_copy(src);
        int unit = align >= 2 ? 2 : 1;
        int cnt = tnew(0);
        li(g_t[cnt].reg, size / unit);
        int t = tnew(0);
        int l = new_label();
        put_label(l);
        I("%s %s, [%s]", unit == 2 ? "lhu" : "lbu", RN[treg(t)], RN[R(&s)]);
        I("%s %s, [%s]", unit == 2 ? "sh" : "sb", RN[treg(t)], RN[R(&d)]);
        I("addi %s, %s, %d", RN[R(&s)], RN[R(&s)], unit);
        I("addi %s, %s, %d", RN[R(&d)], RN[R(&d)], unit);
        I("addi %s, %s, -1", RN[treg(cnt)], RN[treg(cnt)]);
        I("bne %s, r0, .L%d", RN[treg(cnt)], l);
        tfree(t); tfree(cnt); ofree(d); ofree(s);
        return;
    }
    int o = 0;
    if (align >= 4) {
        if (size >= 16) {
            int vt = tnew(1);
            for (; o + 16 <= size; o += 16) {
                LV a = *src, b = *dst;
                a.off += o; b.off += o;
                I("vld %s, %s", VN[treg(vt)], mem(&a));
                I("vst %s, %s", VN[treg(vt)], mem(&b));
            }
            tfree(vt);
        }
    }
    int t = tnew(0);
    while (o < size) {
        int unit = (align >= 4 && size - o >= 4) ? 4 : (align >= 2 && size - o >= 2) ? 2 : 1;
        LV a = *src, b = *dst;
        a.off += o; b.off += o;
        I("%s %s, %s", unit == 4 ? "lw" : unit == 2 ? "lhu" : "lbu", RN[treg(t)], mem(&a));
        I("%s %s, %s", unit == 4 ? "sw" : unit == 2 ? "sh" : "sb", RN[treg(t)], mem(&b));
        o += unit;
    }
    tfree(t);
}

static void zero_mem(LV *dst, int size, int align) {
    lv_fix(dst);
    if (size > 128) {
        Opnd d = lv_addr_copy(dst);
        int unit = align >= 4 ? 4 : align >= 2 ? 2 : 1;
        int cnt = tnew(0);
        li(g_t[cnt].reg, size / unit);
        int l = new_label();
        put_label(l);
        I("%s r0, [%s]", unit == 4 ? "sw" : unit == 2 ? "sh" : "sb", RN[R(&d)]);
        I("addi %s, %s, %d", RN[R(&d)], RN[R(&d)], unit);
        I("addi %s, %s, -1", RN[treg(cnt)], RN[treg(cnt)]);
        I("bne %s, r0, .L%d", RN[treg(cnt)], l);
        for (int o = 0; o < size % unit; o++) I("sb r0, [%s%+d]", RN[R(&d)], o);
        tfree(cnt); ofree(d);
        return;
    }
    for (int o = 0; o < size;) {
        int unit = (align >= 4 && size - o >= 4) ? 4 : (align >= 2 && size - o >= 2) ? 2 : 1;
        LV b = *dst;
        b.off += o;
        I("%s r0, %s", unit == 4 ? "sw" : unit == 2 ? "sh" : "sb", mem(&b));
        o += unit;
    }
}

/* ------------------------------------------------------------- constants */

typedef struct VConst { int32_t v[4]; int label; struct VConst *next; } VConst;
static VConst *g_vconsts;
static int g_vconst_n;

static Opnd gen_vconst(const int32_t c[4], int hint) {
    int nz = 0, cost = 1;
    for (int i = 0; i < 4; i++) if (c[i]) { nz++; cost += fits_s18(c[i]) || !(c[i] & 0x3FF) ? 2 : 3; }
    int r;
    if (cost <= 6) {
        Opnd d = dest(1, hint, &r);
        I("vsub %s, %s, %s", VN[r], VN[r], VN[r]);
        for (int i = 0; i < 4; i++) if (c[i]) {
            Opnd x = o_imm(c[i]);
            int s = R(&x);
            int dr = d.k == O_VTMP ? treg(d.v) : r;
            I("vset %s, %s, %d", VN[dr], RN[s], i);
            ofree(x);
        }
        (void)nz;
        return d;
    }
    VConst *k;
    for (k = g_vconsts; k; k = k->next) if (!memcmp(k->v, c, sizeof k->v)) break;
    if (!k) {
        k = ar_alloc(sizeof *k);
        memcpy(k->v, c, sizeof k->v);
        k->label = g_vconst_n++;
        k->next = g_vconsts;
        g_vconsts = k;
    }
    int t = tnew(0);
    I("la %s, VC%d", RN[g_t[t].reg], k->label);
    int b = treg(t);
    tfree(t);
    Opnd d = dest(1, hint, &r);
    I("vld %s, [%s]", VN[r], RN[b]);
    return d;
}

/* ------------------------------------------------------------- calls */

static void spill_for_call(Arg *args, int n) {
    for (int i = 0; i < NT; i++) {
        Temp *x = &g_t[i];
        if (!x->live || x->reg < 0) continue;
        int is_arg = 0;
        for (int j = 0; j < n; j++) if ((args[j].o.k == O_TMP || args[j].o.k == O_VTMP) && args[j].o.v == i) is_arg = 1;
        if (is_arg) continue;
        if (x->cls == 0 && x->reg >= 9 && x->reg <= 13) continue;
        if (x->cls == 0) {
            int dst = -1;
            for (int k = 0; k < g_nspool; k++) {
                int r = g_spool[k];
                if (r >= 9 && r <= 13 && g_rown[r] == -1) { dst = r; break; }
            }
            if (dst >= 0) {
                Ik("mov %s, %s", RN[dst], RN[x->reg]);
                g_rown[x->reg] = x->resv ? -2 : -1;
                x->resv = 0;
                own(i, dst);
                continue;
            }
        }
        t_spill(i);
    }
}

typedef struct { int src, dst; } Move;

static void parallel_move(Move *mv, int n, int cls, int scratch) {
    const char **N = cls ? VN : RN;
    while (n > 0) {
        int k = -1;
        for (int i = 0; i < n && k < 0; i++) {
            int blocked = 0;
            for (int j = 0; j < n; j++) if (j != i && mv[j].src == mv[i].dst) blocked = 1;
            if (!blocked) k = i;
        }
        if (k < 0) {
            I("%s %s, %s", cls ? "vmov" : "mov", N[scratch], N[mv[0].src]);
            mv[0].src = scratch;
            continue;
        }
        if (mv[k].src != mv[k].dst) I("%s %s, %s", cls ? "vmov" : "mov", N[mv[k].dst], N[mv[k].src]);
        mv[k] = mv[--n];
    }
}

static int stack_arg_bytes(Type **types, int n) {
    int si = 0, vi = 0, off = 0;
    for (int i = 0; i < n; i++) {
        if (is_v(types[i])) { if (vi++ >= 4) off += 16; }
        else if (si++ >= 4) off += 4;
    }
    return off;
}

/* Calls `label`, or a function value (callr), with evaluated arguments (aggregates already as
   addresses). Returns the result (type ret).
   A function value is 16 bytes, [code, c1, c2, c3]. A call through one passes the code address
   in r5 and the address of the 16-byte value in r6, then does `callr r5`. Functions without
   captures ignore r6; the code address of a capturing literal is an entry stub that loads
   c1-c3 into r6-r8 and falls into the literal's body, which finds its captures in r6-r8.
   The value is either in a vector register / temporary (*fn) or in memory (*fnmem). A direct
   call to a capturing literal passes its captured words in caps[0..ncaps-1], straight to r6-r8. */
static Opnd call_target(const char *label, Opnd *fn, LV *fnmem, Opnd *caps, int ncaps, Type *ret, Arg *args, int n, int hint) {
    int dst[20], soff[20];
    int si = 0, vi = 0, off = 0;
    if (n > 20) ice("too many arguments");
    for (int i = 0; i < n; i++) {
        if (is_v(args[i].t)) { if (vi < 4) dst[i] = 100 + vi++; else { dst[i] = -1; soff[i] = off; off += 16; } }
        else { if (si < 4) dst[i] = 1 + si++; else { dst[i] = -1; soff[i] = off; off += 4; } }
    }
    for (int i = 0; i < n; i++) {
        if (dst[i] != -1) continue;
        if (is_v(args[i].t)) I("vst %s, [sp+%d]", VN[VR(&args[i].o)], soff[i]);
        else I("sw %s, [sp+%d]", RN[R(&args[i].o)], soff[i]);
        ofree(args[i].o);
        args[i].o.k = O_NONE;
    }
    {
        Arg all[25];
        memcpy(all, args, sizeof(Arg) * (size_t)n);
        int na = n;
        if (fn) all[na++] = (Arg){*fn, ty_u32};
        for (int k = 0; k < ncaps; k++) all[na++] = (Arg){caps[k], ty_u32};
        spill_for_call(all, na);
    }
    /* scalar arguments to r1-r4 and captured words to r6-r8, as one parallel move */
    Move mv[12];
    Opnd so[12];
    int sd[12], nso = 0, nm = 0;
    for (int i = 0; i < n; i++) if (dst[i] >= 1 && dst[i] <= 4) { so[nso] = args[i].o; sd[nso++] = dst[i]; }
    for (int k = 0; k < ncaps; k++) { so[nso] = caps[k]; sd[nso++] = 6 + k; }
    for (int i = 0; i < nso; i++) {
        Opnd o = so[i];
        if (o.k == O_REG) mv[nm++] = (Move){o.v, sd[i]};
        else if (o.k == O_TMP && g_t[o.v].reg >= 0) mv[nm++] = (Move){g_t[o.v].reg, sd[i]};
    }
    parallel_move(mv, nm, 0, 15);
    for (int i = 0; i < nso; i++) {
        Opnd o = so[i];
        if (o.k == O_IMM) { li(sd[i], o.v); }
        else if (o.k == O_TMP && g_t[o.v].reg < 0) I("lw %s, [sp+%d]", RN[sd[i]], g_t[o.v].slot);
    }
    /* the function value: its address to r6, the code address to r5 (before the vector
       argument moves, which may overwrite a vector register holding it) */
    if (fnmem) {
        Opnd b = fnmem->base;
        int rb;
        if (b.k == O_REG) rb = b.v;
        else if (b.k == O_TMP && g_t[b.v].reg >= 0) rb = g_t[b.v].reg;
        else if (b.k == O_TMP) { I("lw r6, [sp+%d]", g_t[b.v].slot); rb = 6; }
        else ice("function value address");
        if (fnmem->frame_rel) I("addi r6, %s, %d+\001", RN[rb], fnmem->off);
        else if (fnmem->sym) I("addi r6, %s, %s+%d", RN[rb], fnmem->sym, fnmem->off);
        else if (fnmem->off || rb != 6) I("addi r6, %s, %d", RN[rb], fnmem->off);
        I("lw r5, [r6]");
    } else if (fn) {
        if (fn->k == O_VTMP && g_t[fn->v].reg < 0) {
            I("addi r6, sp, %d", g_t[fn->v].slot);
            I("lw r5, [r6]");
        } else {
            int vr = fn->k == O_VREG ? fn->v : fn->k == O_VTMP ? g_t[fn->v].reg : -1;
            if (vr < 0) ice("function value operand");
            int slot = slot_alloc(16);
            I("vst %s, [sp+%d]", VN[vr], slot);
            I("addi r6, sp, %d", slot);
            I("vget r5, %s, 0", VN[vr]);
        }
    }
    /* vector arguments */
    nm = 0;
    int used = 0;
    for (int i = 0; i < n; i++) {
        if (dst[i] < 100) continue;
        Opnd o = args[i].o;
        int s = o.k == O_VREG ? o.v : (o.k == O_VTMP ? g_t[o.v].reg : -1);
        if (s >= 0) { mv[nm++] = (Move){s, dst[i] - 100}; used |= 1 << s; }
        used |= 1 << (dst[i] - 100);
    }
    int vscratch = 7;
    while (vscratch >= 0 && (used >> vscratch & 1)) vscratch--;
    parallel_move(mv, nm, 1, vscratch);
    for (int i = 0; i < n; i++) {
        if (dst[i] < 100) continue;
        Opnd o = args[i].o;
        if (o.k == O_VTMP && g_t[o.v].reg < 0) I("vld %s, [sp+%d]", VN[dst[i] - 100], g_t[o.v].slot);
    }
    /* anything else still in a caller-saved register was spilled above */
    for (int i = 0; i < n; i++) ofree(args[i].o);
    for (int k = 0; k < ncaps; k++) ofree(caps[k]);
    if (fnmem) { lv_free(fnmem); I("callr r5"); }
    else if (fn) { ofree(*fn); I("callr r5"); }
    else I("call %s", label);
    Type *rt = ret;
    if (rt->k == TY_VOID || ty_is_aggr(rt)) return (Opnd){O_NONE, 0};
    if (is_v(rt)) {
        int t = tnew_at(1, 0);
        if (hint >= 0) { if (hint) I("vmov %s, v0", VN[hint]); tfree(t); return (Opnd){O_VREG, hint}; }
        return o_tmp(t);
    }
    int t = tnew_at(0, 1);
    if (hint >= 0) { if (hint != 1) I("mov %s, r1", RN[hint]); tfree(t); return (Opnd){O_REG, hint}; }
    return o_tmp(t);
}

static Opnd call_func(Func *f, Arg *args, int n, int hint) { return call_target(f->label, NULL, NULL, NULL, 0, f->ret, args, n, hint); }

static int count_calls(Expr *e);

static LV *g_ret_into;   /* when set: memory the next aggregate-returning call writes into */

static Opnd gen_call(Expr *e, int hint, LV *aggr_out) {
    Func *f = e->callee;
    Type *ret = e->indirect ? e->a->ty->elem : f->ret;
    LV *into = g_ret_into;
    g_ret_into = NULL;
    Arg args[20];
    int n = 0, hidden = ty_is_aggr(ret);
    Opnd fn = {O_NONE, 0};
    LV fnlv;
    int fn_in_mem = 0;
    if (e->indirect) {
        /* the function value is evaluated first; one in memory is called in place when the
           arguments make no calls (nothing can change it in between) */
        int calls = 0;
        for (int i = 0; i < e->nargs; i++) calls += count_calls(e->args[i]);
        if (!calls && lv_able(e->a)) {
            fnlv = gen_lv(e->a);
            if (fnlv.k == LV_MEM) { lv_fix(&fnlv); fn_in_mem = 1; }
            else fn = load_lv(&fnlv, -1);
        } else fn = gen_expr(e->a, -1);
    }
    if (e->nargs + hidden > 20) error_at(e->loc, "too many arguments");
    if (hidden) n = 1;
    for (int i = 0; i < e->nargs; i++) {
        Expr *a = e->args[i];
        if (ty_is_aggr(a->ty)) {
            LV lv = gen_aggr_lv(a);
            args[n++] = (Arg){lv_addr(&lv), ty_ptr(a->ty)};
        } else args[n++] = (Arg){gen_expr(a, -1), a->ty};
    }
    int slot = 0;
    if (hidden && into) {
        args[0] = (Arg){lv_addr_copy(into), ty_ptr(ret)};
    } else if (hidden) {
        slot = slot_alloc(ret->size);
        int r;
        Opnd d = dest(0, -1, &r);
        I("addi %s, sp, %d", RN[r], slot);
        args[0] = (Arg){d, ty_ptr(ret)};
    }
    Opnd r = call_target(e->indirect ? NULL : f->label, e->indirect && !fn_in_mem ? &fn : NULL, fn_in_mem ? &fnlv : NULL,
                         NULL, 0, ret, args, n, hint);
    if (hidden && aggr_out) *aggr_out = lv_mem((Opnd){O_REG, 14}, slot, ret);
    return r;
}

/* ------------------------------------------------------------- aggregates */

static void gen_aggr_into(Expr *e, LV *dst);

static void store_value_into(Expr *v, LV *dst) {
    if (ty_is_aggr(v->ty)) {
        LV d = *dst;
        gen_aggr_into(v, &d);
        if ((d.base.k == O_TMP) && !(dst->base.k == O_TMP && dst->base.v == d.base.v)) ofree(d.base);
        return;
    }
    Opnd o = gen_expr(v, -1);
    LV d = *dst;
    store_lv_k(&d, o, v->ty, 1);
    dst->base = d.base;
}

/* Builds an aggregate value directly into memory. */
static void gen_aggr_into(Expr *e, LV *dst) {
    Type *t = e->ty;
    if (e->k == E_STRUCT) {
        int covered = 0;
        for (int i = 0; i < t->nfields; i++) covered += t->fields[i].type->size;
        if (e->nargs < t->nfields || covered != t->size) zero_mem(dst, t->size, t->align);
        for (int i = 0; i < e->nargs; i++) {
            Field *f = NULL;
            for (int j = 0; j < t->nfields; j++) if (!strcmp(t->fields[j].name, e->fnames[i])) f = &t->fields[j];
            LV d = *dst;
            d.off += f->offset;
            d.ty = f->type;
            store_value_into(e->args[i], &d);
        }
        return;
    }
    if (e->k == E_ARRAY) {
        for (int i = 0; i < e->nargs; i++) {
            LV d = *dst;
            d.off += i * t->elem->size;
            d.ty = t->elem;
            store_value_into(e->args[i], &d);
        }
        return;
    }
    LV src = gen_aggr_lv(e);
    copy_mem(dst, &src, t->size, t->align);
    lv_free(&src);
}

static LV gen_intrinsic_aggr(Expr *e);

static LV gen_aggr_lv(Expr *e) {
    if (e->k == E_CALL && e->bi == BI_MAP) return gen_intrinsic_aggr(e);
    if (e->k == E_CALL && (e->callee || e->indirect) && !e->bi) {
        LV out;
        gen_call(e, -1, &out);
        return out;
    }
    if (e->k == E_STRUCT || e->k == E_ARRAY) {
        int slot = slot_alloc(e->ty->size);
        LV d = lv_mem((Opnd){O_REG, 14}, slot, e->ty);
        gen_aggr_into(e, &d);
        lv_free(&d);
        return lv_mem((Opnd){O_REG, 14}, slot, e->ty);
    }
    if (e->k == E_CONV) return gen_aggr_lv(e->a);
    return gen_lv(e);
}

/* ------------------------------------------------------------- expressions */



static Opnd fn_diff(Expr *e);

static Opnd gen_cmp_value(Expr *e, int hint) {
    if (e->a->ty->k == TY_FUNC) {
        Opnd x = fn_diff(e);
        int rx = R(&x), r;
        ofree(x);
        Opnd d = dest(0, hint, &r);
        I("sltu %s, r0, %s", RN[r], RN[rx]);
        if (e->op == B_EQ) I("xori %s, %s, 1", RN[r], RN[r]);
        return d;
    }
    Opnd a = gen_expr(e->a, -1), b = gen_expr(e->b, -1);
    Type *ot = e->conv_from ? e->conv_from : e->a->ty;
    int uns = !ty_is_signed(ot) && ot->k != TY_BOOL ? 1 : 0;
    if (ot->k == TY_BOOL) uns = 0;
    OpKind op = e->op;
    /* normalise > and <= by swapping */
    if (op == B_GT || op == B_LE) { Opnd t = a; a = b; b = t; op = op == B_GT ? B_LT : B_GE; }
    int r;
    if (op == B_LT || op == B_GE) {
        if (b.k == O_IMM && !uns && fits_s18(b.v)) {
            int ra = R(&a);
            ofree(a);
            Opnd d = dest(0, hint, &r);
            I("slti %s, %s, %d", RN[r], RN[ra], b.v);
            if (op == B_GE) I("xori %s, %s, 1", RN[r], RN[r]);
            return d;
        }
        int ra = R(&a), rb = R(&b);
        ofree(a); ofree(b);
        Opnd d = dest(0, hint, &r);
        I("%s %s, %s, %s", uns ? "sltu" : "slt", RN[r], RN[ra], RN[rb]);
        if (op == B_GE) I("xori %s, %s, 1", RN[r], RN[r]);
        return d;
    }
    /* == and != */
    if (a.k == O_IMM) { Opnd t = a; a = b; b = t; }
    int ra = R(&a);
    if (b.k == O_IMM && b.v == 0) {
        ofree(a);
        Opnd d = dest(0, hint, &r);
        I("sltu %s, r0, %s", RN[r], RN[ra]);
        if (op == B_EQ) I("xori %s, %s, 1", RN[r], RN[r]);
        return d;
    }
    if (b.k == O_IMM && b.v >= 0 && b.v <= 0x3FFFF) {
        ofree(a);
        Opnd d = dest(0, hint, &r);
        I("xori %s, %s, %d", RN[r], RN[ra], b.v);
        I("sltu %s, r0, %s", RN[r], RN[r]);
        if (op == B_EQ) I("xori %s, %s, 1", RN[r], RN[r]);
        return d;
    }
    int rb = R(&b);
    ra = R(&a);
    ofree(a); ofree(b);
    Opnd d = dest(0, hint, &r);
    I("xor %s, %s, %s", RN[r], RN[ra], RN[rb]);
    I("sltu %s, r0, %s", RN[r], RN[r]);
    if (op == B_EQ) I("xori %s, %s, 1", RN[r], RN[r]);
    return d;
}

/* Scalar arithmetic on evaluated operands. ty: operation type; mixed: fixed*int form. */
static Opnd arith(OpKind op, Type *ty, int mixed, Opnd a, Opnd b, int hint) {
    int fx = ty->k == TY_FIXED && !mixed;
    int sgn = ty_is_signed(ty);
    int r;
    /* commutative: put the immediate on the right */
    if (a.k == O_IMM && b.k != O_IMM && (op == B_ADD || op == B_MUL || op == B_AND || op == B_OR || op == B_XOR)) {
        Opnd t = a; a = b; b = t;
    }
    if (b.k == O_IMM) {
        int32_t v = b.v;
        const char *iop = NULL;
        int32_t imm = v;
        switch (op) {
        case B_ADD: if (fits_s18(v)) iop = "addi"; break;
        case B_SUB: if (fits_s18(-(int64_t)v)) { iop = "addi"; imm = -v; } break;
        case B_AND: if (v >= 0 && v <= 0x3FFFF) iop = "andi"; break;
        case B_OR: if (v >= 0 && v <= 0x3FFFF) iop = "ori"; break;
        case B_XOR: if (v >= 0 && v <= 0x3FFFF) iop = "xori"; break;
        case B_SHL: iop = "shli"; imm = v & 31; break;
        case B_SHR: iop = sgn ? "sari" : "shri"; imm = v & 31; break;
        case B_MUL: {
            int64_t m = fx ? -1 : v;
            if (fx) {
                if (v == 65536) { Opnd x = a; if (hint >= 0) { move_to(x, hint, 0); ofree(x); return (Opnd){O_REG, hint}; } return x; }
                if (v > 0 && (v & (v - 1)) == 0) {
                    int k = log2_exact(v);
                    if (k >= 16) { iop = "shli"; imm = k - 16; } else { iop = "sari"; imm = 16 - k; }
                }
            } else if (m == 1) { if (hint >= 0) { move_to(a, hint, 0); ofree(a); return (Opnd){O_REG, hint}; } return a; }
            else if (m > 0 && log2_exact(m) >= 0) { iop = "shli"; imm = log2_exact(m); }
            break;
        }
        case B_DIV:
            if (!fx && v > 0 && log2_exact(v) >= 0) {
                int k = log2_exact(v);
                if (k == 0) return a;
                if (!sgn) { iop = "shri"; imm = k; break; }
                /* signed division by 2^k rounds toward zero */
                int ra = R(&a);
                int t = tnew(0);
                int rt = g_t[t].reg;
                I("sari %s, %s, 31", RN[rt], RN[ra]);
                I("shri %s, %s, %d", RN[rt], RN[rt], 32 - k);
                I("add %s, %s, %s", RN[treg(t)], RN[treg(t)], RN[R(&a)]);
                ofree(a);
                rt = treg(t);
                tfree(t);
                Opnd d = dest(0, hint, &r);
                I("sari %s, %s, %d", RN[r], RN[rt], k);
                return d;
            }
            break;
        case B_MOD:
            if (!sgn && v > 0 && log2_exact(v) >= 0 && v - 1 <= 0x3FFFF) { iop = "andi"; imm = v - 1; }
            break;
        default: break;
        }
        if (iop) {
            int ra = R(&a);
            ofree(a);
            Opnd d = dest(0, hint, &r);
            I("%s %s, %s, %d", iop, RN[r], RN[ra], imm);
            return d;
        }
    }
    const char *ins;
    switch (op) {
    case B_ADD: ins = "add"; break;
    case B_SUB: ins = "sub"; break;
    case B_MUL: ins = fx ? "fmul" : "mul"; break;
    case B_DIV: ins = fx ? "fdiv" : sgn ? "div" : "divu"; break;
    case B_MOD: ins = sgn ? "rem" : "remu"; break;
    case B_AND: ins = "and"; break;
    case B_OR: ins = "or"; break;
    case B_XOR: ins = "xor"; break;
    case B_SHL: ins = "shl"; break;
    case B_SHR: ins = sgn ? "sar" : "shr"; break;
    default: ice("bad arithmetic operator");
    }
    int ra = R(&a), rb = R(&b);
    ofree(a); ofree(b);
    Opnd d = dest(0, hint, &r);
    I("%s %s, %s, %s", ins, RN[r], RN[ra], RN[rb]);
    return d;
}

static Opnd gen_vec_binary(Expr *e, Opnd a, Opnd b, int hint) {
    int r;
    Type *at = e->a->ty, *bt = e->b->ty;
    if (at->k == TY_MAT4) ice("matrix operand");
    if (ty_is_vec(at) && ty_is_vec(bt)) {
        const char *ins = e->op == B_ADD ? "vadd" : e->op == B_SUB ? "vsub" : "vmul";
        int ra = VR(&a), rb = VR(&b);
        ofree(a); ofree(b);
        Opnd d = dest(1, hint, &r);
        I("%s %s, %s, %s", ins, VN[r], VN[ra], VN[rb]);
        return d;
    }
    /* vector * fixed, vector / fixed */
    if (e->op == B_DIV) {
        if (b.k == O_IMM) {
            int64_t recip = ((int64_t)1 << 32) / b.v;
            b = o_imm(recip);
        } else {
            int rb = R(&b);
            ofree(b);
            int t = tnew(0);
            I("lui %s, 64", RN[g_t[t].reg]);
            I("fdiv %s, %s, %s", RN[treg(t)], RN[treg(t)], RN[rb]);
            b = o_tmp(t);
        }
    }
    int ra = VR(&a), rb = R(&b);
    ofree(a); ofree(b);
    Opnd d = dest(1, hint, &r);
    I("vscale %s, %s, %s", VN[r], VN[ra], RN[rb]);
    return d;
}

/* Moves a vector temporary into v0-v3 (vxfm reads its matrix from v4-v7). */
static Opnd vec_low(Opnd o) {
    if (o.k == O_VREG) { if (o.v < 4) return o; o = owned(o, 1); }
    int r = treg(o.v);
    if (r < 4) return o;
    int dst = -1;
    for (int i = 0; i < 4; i++) if (g_vown[i] == -1) { dst = i; break; }
    if (dst < 0) {
        for (int i = 0; i < NT; i++) if (g_t[i].live && g_t[i].cls == 1 && g_t[i].reg >= 0 && g_t[i].reg < 4 && i != o.v) { dst = g_t[i].reg; t_spill(i); break; }
        if (dst < 0) ice("no low vector register");
    }
    Ik("vmov %s, %s", VN[dst], VN[r]);
    g_vown[r] = -1;
    own(o.v, dst);
    return o;
}

static Opnd gen_xfm(Expr *e, int hint) {
    LV m = gen_aggr_lv(e->a);
    Opnd v = gen_expr(e->b, -1);
    v = vec_low(v);
    /* free v4-v7 */
    for (int r = 4; r < 8; r++) {
        int t = g_vown[r];
        if (t >= 0) t_spill(t);
    }
    int saved[4];
    for (int r = 4; r < 8; r++) { saved[r - 4] = g_vown[r]; g_vown[r] = -2; }
    lv_fix(&m);
    for (int i = 0; i < 4; i++) {
        LV row = m;
        row.off += 16 * i;
        I("vld %s, %s", VN[4 + i], mem(&row));
    }
    lv_free(&m);
    for (int r = 4; r < 8; r++) g_vown[r] = saved[r - 4];
    int rv = VR(&v);
    ofree(v);
    int r;
    Opnd d = dest(1, hint, &r);
    I("vxfm %s, %s", VN[r], VN[rv]);
    if (e->ty->k == TY_VEC3) I("vset %s, r0, 3", VN[r]);
    return d;
}

static Opnd gen_binary(Expr *e, int hint) {
    OpKind op = e->op;
    if (op == B_LAND || op == B_LOR) {
        flush_temps();
        int lf = new_label(), le = new_label();
        gen_cond(e, lf, 0);
        int r = hint >= 0 ? hint : find_free(0);
        if (r < 0) r = take_reg(0);
        I("addi %s, r0, 1", RN[r]);
        I("jmp .L%d", le);
        put_label(lf);
        I("mov %s, r0", RN[r]);
        put_label(le);
        if (hint >= 0) return (Opnd){O_REG, hint};
        int t = tnew_at(0, r);
        return o_tmp(t);
    }
    if (op >= B_EQ && op <= B_GE) return gen_cmp_value(e, hint);
    Type *at = e->a->ty;
    if (at->k == TY_MAT4) return gen_xfm(e, hint);
    if (is_v(e->ty)) {
        Opnd a = gen_expr(e->a, -1), b = gen_expr(e->b, -1);
        return gen_vec_binary(e, a, b, hint);
    }
    if (e->ty->k == TY_PTR || (at->k == TY_PTR && op == B_SUB)) {
        Opnd a = gen_expr(e->a, -1);
        if (e->b->ty->k == TY_PTR) {
            /* pointer difference */
            Opnd b = gen_expr(e->b, -1);
            Opnd d = arith(B_SUB, ty_s32, 0, a, b, -1);
            int size = at->elem->size;
            if (size == 1) { if (hint >= 0) { move_to(d, hint, 0); ofree(d); return (Opnd){O_REG, hint}; } return d; }
            int k = log2_exact(size);
            if (k > 0) return arith(B_SHR, ty_s32, 0, d, o_imm(k), hint);
            return arith(B_DIV, ty_s32, 0, d, o_imm(size), hint);
        }
        int size = e->ty->elem->size;
        Opnd b;
        if (e->b->isconst) b = o_imm(e->b->cval * size);
        else {
            b = gen_expr(e->b, -1);
            if (size != 1) b = arith(B_MUL, ty_s32, 0, b, o_imm(size), -1);
        }
        return arith(op, ty_u32, 0, a, b, hint);
    }
    Opnd a = gen_expr(e->a, -1), b = gen_expr(e->b, -1);
    return arith(op, e->conv_from && e->conv_from != ty_s32 ? e->conv_from : e->ty,
                 e->ty->k == TY_FIXED && e->conv_from == ty_s32, a, b, hint);
}

static Opnd gen_conv(Expr *e, int hint) {
    Type *from = ty_base(e->conv_from ? e->conv_from : e->a->ty), *to = ty_base(e->ty);
    if (from->k == TY_FUNC && to->k != TY_FUNC) {
        /* the code address; captured words are dropped */
        Opnd v = gen_expr(e->a, -1);
        int vr = VR(&v), r;
        ofree(v);
        Opnd d = dest(0, hint, &r);
        I("vget %s, %s, 0", RN[r], VN[vr]);
        return d;
    }
    if (to->k == TY_FUNC && from->k != TY_FUNC) {
        /* a code address: a function value with no captured words */
        Opnd v = gen_expr(e->a, -1);
        int r;
        Opnd d = dest(1, hint, &r);
        I("vsub %s, %s, %s", VN[r], VN[r], VN[r]);
        int sr = R(&v);
        int vr = d.k == O_VTMP ? treg(d.v) : r;
        I("vset %s, %s, 0", VN[vr], RN[sr]);
        ofree(v);
        return d;
    }
    if (ty_is_vec(to)) {
        Opnd a = gen_expr(e->a, -1);
        int lf = ty_lanes(from), lt = ty_lanes(to);
        int ifrom = from->k == TY_IVEC4, ito = to->k == TY_IVEC4;
        if (ifrom == ito && lt >= lf) {
            if (hint >= 0) { move_to(a, hint, 1); ofree(a); return (Opnd){O_VREG, hint}; }
            return a;
        }
        int ra = VR(&a);
        ofree(a);
        int r;
        Opnd d = dest(1, hint, &r);
        if (r != ra) I("vmov %s, %s", VN[r], VN[ra]);
        if (ifrom != ito) {
            int t = tnew(0);
            for (int i = 0; i < 4; i++) {
                int dr = d.k == O_VTMP ? treg(d.v) : r;
                I("vget %s, %s, %d", RN[treg(t)], VN[dr], i);
                I("%s %s, %s, 16", ito ? "sari" : "shli", RN[treg(t)], RN[treg(t)]);
                dr = d.k == O_VTMP ? treg(d.v) : r;
                I("vset %s, %s, %d", VN[dr], RN[treg(t)], i);
            }
            tfree(t);
        }
        for (int i = lt; i < 4; i++) {
            int dr = d.k == O_VTMP ? treg(d.v) : r;
            I("vset %s, r0, %d", VN[dr], i);
        }
        return d;
    }
    if (ty_is_aggr(to)) ice("aggregate conversion");
    /* conversions that change nothing in a register: let the operand use the hint */
    int noop = (from->k == TY_FIXED) == (to->k == TY_FIXED) &&
               !(is_small_int(to) && (from->size > to->size || ty_is_signed(from) != ty_is_signed(to)));
    if (noop) return gen_expr(e->a, hint);
    Opnd a = gen_expr(e->a, -1);
    int r;
    if (from->k == TY_FIXED && to->k != TY_FIXED) {
        int ra = R(&a);
        ofree(a);
        Opnd d = dest(0, hint, &r);
        I("sari %s, %s, 16", RN[r], RN[ra]);
        if (is_small_int(to)) normalize(r, r, to);
        return d;
    }
    if (to->k == TY_FIXED && from->k != TY_FIXED) {
        int ra = R(&a);
        ofree(a);
        Opnd d = dest(0, hint, &r);
        I("shli %s, %s, 16", RN[r], RN[ra]);
        return d;
    }
    if (is_small_int(to) && (from->size > to->size || ty_is_signed(from) != ty_is_signed(to))) {
        int ra = R(&a);
        ofree(a);
        Opnd d = dest(0, hint, &r);
        normalize(r, ra, to);
        return d;
    }
    if (hint >= 0) { move_to(a, hint, 0); ofree(a); return (Opnd){O_REG, hint}; }
    return a;
}

static Opnd gen_builtin(Expr *e, int hint) {
    Expr **a = e->args;
    int r;
    switch (e->bi) {
    case BI_VEC2: case BI_VEC3: case BI_VEC4: case BI_IVEC4: {
        if (e->bi == BI_VEC4 && e->nargs == 2) {
            Opnd v = gen_expr(a[0], -1);
            Opnd w = gen_expr(a[1], -1);
            if (hint >= 0) { move_to(v, hint, 1); ofree(v); v = (Opnd){O_VREG, hint}; }
            else v = owned(v, 1);
            int rw = R(&w);
            I("vset %s, %s, 3", VN[VR(&v)], RN[rw]);
            ofree(w);
            return v;
        }
        Opnd lanes[4];
        for (int i = 0; i < e->nargs; i++) lanes[i] = gen_expr(a[i], -1);
        Opnd d = dest(1, hint, &r);
        I("vsub %s, %s, %s", VN[r], VN[r], VN[r]);
        for (int i = 0; i < e->nargs; i++) {
            if (lanes[i].k == O_IMM && lanes[i].v == 0) continue;
            int s = R(&lanes[i]);
            I("vset %s, %s, %d", VN[VR(&d)], RN[s], i);
            ofree(lanes[i]);
        }
        return d;
    }
    case BI_DOT: {
        Opnd x = gen_expr(a[0], -1), y = gen_expr(a[1], -1);
        int rx = VR(&x), ry = VR(&y);
        ofree(x); ofree(y);
        Opnd d = dest(0, hint, &r);
        I("vdot %s, %s, %s", RN[r], VN[rx], VN[ry]);
        return d;
    }
    case BI_CROSS: {
        Opnd x = gen_expr(a[0], -1), y = gen_expr(a[1], -1);
        int rx = VR(&x), ry = VR(&y);
        ofree(x); ofree(y);
        Opnd d = dest(1, hint, &r);
        I("vcross %s, %s, %s", VN[r], VN[rx], VN[ry]);
        return d;
    }
    case BI_BITS: case BI_FROM_BITS: return gen_expr(a[0], hint);
    case BI_ABS: {
        Opnd x = gen_expr(a[0], -1);
        int rx = R(&x);
        int t = tnew(0);
        I("sari %s, %s, 31", RN[g_t[t].reg], RN[rx]);
        int u = tnew(0);
        I("xor %s, %s, %s", RN[g_t[u].reg], RN[R(&x)], RN[treg(t)]);
        ofree(x);
        int rt = treg(t), ru = treg(u);
        tfree(t); tfree(u);
        Opnd d = dest(0, hint, &r);
        I("sub %s, %s, %s", RN[r], RN[ru], RN[rt]);
        return d;
    }
    case BI_MIN: case BI_MAX: case BI_CLAMP: {
        int uns = !ty_is_signed(e->ty);
        Opnd x = gen_expr(a[0], -1), y = gen_expr(a[1], -1);
        Opnd z = e->bi == BI_CLAMP ? gen_expr(a[2], -1) : (Opnd){O_NONE, 0};
        /* min(x, y) = y ^ ((x ^ y) & -(x < y)); max swaps the comparison */
        for (int step = 0; step < (e->bi == BI_CLAMP ? 2 : 1); step++) {
            int want_min = e->bi == BI_MIN || (e->bi == BI_CLAMP && step == 1);
            Opnd p = x, q = step == 0 ? y : z;
            int last = e->bi != BI_CLAMP || step == 1;
            int m = tnew(0);
            int rp = R(&p), rq = R(&q);
            if (want_min) I("%s %s, %s, %s", uns ? "sltu" : "slt", RN[g_t[m].reg], RN[rp], RN[rq]);
            else I("%s %s, %s, %s", uns ? "sltu" : "slt", RN[g_t[m].reg], RN[rq], RN[rp]);
            I("sub %s, r0, %s", RN[treg(m)], RN[treg(m)]);
            int xo = tnew(0);
            I("xor %s, %s, %s", RN[g_t[xo].reg], RN[R(&p)], RN[R(&q)]);
            I("and %s, %s, %s", RN[treg(xo)], RN[treg(xo)], RN[treg(m)]);
            tfree(m);
            int rq2 = R(&q), rx2 = treg(xo);
            ofree(p); ofree(q); tfree(xo);
            Opnd d = dest(0, last ? hint : -1, &r);
            I("xor %s, %s, %s", RN[r], RN[rq2], RN[rx2]);
            x = d;
        }
        return x;
    }
    case BI_LERP: {
        Opnd x = gen_expr(a[0], -1), y = gen_expr(a[1], -1), t = gen_expr(a[2], -1);
        if (is_v(e->ty)) {
            int rx = VR(&x), ry = VR(&y);
            int d = tnew(1);
            I("vsub %s, %s, %s", VN[g_t[d].reg], VN[ry], VN[rx]);
            ofree(y);
            int rt = R(&t);
            I("vscale %s, %s, %s", VN[treg(d)], VN[treg(d)], RN[rt]);
            ofree(t);
            rx = VR(&x);
            int rd = treg(d);
            ofree(x); tfree(d);
            Opnd o = dest(1, hint, &r);
            I("vadd %s, %s, %s", VN[r], VN[rx], VN[rd]);
            return o;
        }
        ice("scalar lerp");
    }
    case BI_NCLIP: case BI_OTZ: case BI_CLERP: {
        /* a = f(a, b, c): the first argument is computed into a register we own */
        Opnd x = gen_expr(a[0], -1), y = gen_expr(a[1], -1), z = gen_expr(a[2], -1);
        if (x.k == O_IMM) { int t = tnew(0); li(g_t[t].reg, x.v); x = o_tmp(t); }   /* even 0: not r0 */
        else x = owned(x, 0);
        int ry = R(&y), rz = R(&z), rx = R(&x);
        I("%s %s, %s, %s", e->bi == BI_NCLIP ? "nclip" : e->bi == BI_OTZ ? "otz" : "clerp", RN[rx], RN[ry], RN[rz]);
        ofree(y); ofree(z);
        if (hint >= 0) { move_to(x, hint, 0); ofree(x); return (Opnd){O_REG, hint}; }
        return x;
    }
    case BI_LENGTH: {
        Opnd v = gen_expr(a[0], -1);
        int rv = VR(&v);
        ofree(v);
        int t = tnew(0);
        I("vdot %s, %s, %s", RN[g_t[t].reg], VN[rv], VN[rv]);
        Arg arg = {o_tmp(t), ty_fixed};
        return call_func(e->callee, &arg, 1, hint);
    }
    case BI_NORMALIZE: {
        Arg arg = {gen_expr(a[0], -1), ty_vec4};
        return call_func(e->callee, &arg, 1, hint);
    }
    default: ice("unknown builtin");
    }
}

/* ---- map / filter / reduce / each: an inline loop with one call per element.
   Loop state lives in compiler-made locals (e->hid), which the allocator keeps in
   callee-saved registers, so it survives the calls. */

static void set_local(Local *l, Opnd v, Type *vt) { LV lv = lv_local(l); store_lv(&lv, v, vt); }
static Opnd get_local(Local *l) { LV lv = lv_local(l); return load_lv(&lv, -1); }

static void bump_local(Local *l, int32_t delta) {
    LV lv = lv_local(l);
    Opnd cur = load_lv(&lv, -1);
    Opnd r = arith(B_ADD, l->ty, 0, cur, o_imm(delta), lv.k == LV_REG ? lv.reg : -1);
    set_local(l, r, l->ty);
}

static Opnd seq_addr(Expr *x) {
    if (x->ty->k == TY_ARRAY) { LV lv = gen_aggr_lv(x); return lv_addr(&lv); }
    return gen_expr(x, -1);
}

static Opnd gen_intrinsic(Expr *e, int hint, LV *into) {
    Builtin bi = e->bi;
    int has_out = bi == BI_MAP_INTO || bi == BI_FILTER_INTO;
    int xi = has_out ? 1 : 0;
    int fidx = bi == BI_REDUCE ? 2 : xi + 1;
    Expr *xs = e->args[xi], *f = e->args[fidx];
    Type *T = xs->ty->elem, *ft = f->ty, *U = ft->elem;
    Local *cnt = e->hid[0], *src = e->hid[1], *dst = e->hid[2], *fv = e->hid[3], *acc = e->hid[4];
    flush_temps();
    /* set up: source, destination, count, function, accumulator */
    set_local(src, seq_addr(xs), ty_u32);
    if (has_out) set_local(dst, seq_addr(e->args[0]), ty_u32);
    else if (bi == BI_FILTER) set_local(dst, get_local(src), ty_u32);
    else if (bi == BI_MAP) set_local(dst, lv_addr_copy(into), ty_u32);
    if (e->has_count) set_local(cnt, gen_expr(e->args[e->nargs - 1], -1), ty_s32);
    else set_local(cnt, o_imm(xs->ty->n), ty_s32);
    if (fv) set_local(fv, gen_expr(f, -1), ft);
    int ncaps = e->target ? e->target->ncaps : 0;
    for (int k = 0; k < ncaps; k++) {
        LV lv = lv_local(e->target->cap_outer[k]);
        set_local(e->hid[5 + k], load_lv(&lv, -1), e->hid[5 + k]->ty);
    }
    if (bi == BI_REDUCE) set_local(acc, gen_expr(e->args[1], -1), U);
    else if (acc) set_local(acc, o_imm(0), ty_u32);
    int ltop = new_label(), lend = new_label();
    {
        Opnd c0 = get_local(cnt);
        int rc = R(&c0);
        ofree(c0);
        I("bge r0, %s, .L%d", RN[rc], lend);
    }
    put_label(ltop);
    /* arguments: [result pointer], [accumulator], element (or its address) */
    Arg args[3];
    int na = 0;
    int writes_result = bi == BI_MAP || bi == BI_MAP_INTO;
    if (writes_result && ty_is_aggr(U)) args[na++] = (Arg){get_local(dst), ty_ptr(U)};
    if (bi == BI_REDUCE) args[na++] = (Arg){get_local(acc), U};
    if (ty_is_aggr(T) || e->elem_byref) args[na++] = (Arg){get_local(src), ty_u32};
    else {
        /* load the element straight into its argument register when that register is free */
        int vec = is_v(T), nv = 0, ns = 0;
        for (int k = 0; k < na; k++) { if (is_v(args[k].t)) nv++; else ns++; }
        int areg = vec ? nv : 1 + ns;
        int owner = vec ? g_vown[areg] : g_rown[areg];
        LV el = lv_mem(get_local(src), 0, T);
        if (owner == -1 || owner == -2) {
            int t = tnew_at(vec, areg);
            const char *m = mem(&el);
            lv_free(&el);
            I("%s %s, %s", vec ? "vld" : load_op(T), vec ? VN[areg] : RN[areg], m);
            args[na++] = (Arg){o_tmp(t), T};
        } else args[na++] = (Arg){load_lv(&el, -1), T};
    }
    Opnd res;
    if (e->target) {
        Opnd caps[3];
        for (int k = 0; k < ncaps; k++) caps[k] = get_local(e->hid[5 + k]);
        res = call_target(e->target->label, NULL, NULL, caps, ncaps, U, args, na, -1);
    } else {
        LV lv = lv_local(fv);
        if (lv.k == LV_MEM) res = call_target(NULL, NULL, &lv, NULL, 0, U, args, na, -1);
        else { Opnd fn = load_lv(&lv, -1); res = call_target(NULL, &fn, NULL, NULL, 0, U, args, na, -1); }
    }
    switch (bi) {
    case BI_MAP: case BI_MAP_INTO:
        if (!ty_is_aggr(U)) {
            LV d = lv_mem(get_local(dst), 0, U);
            store_lv(&d, res, U);
        }
        bump_local(dst, U->size);
        break;
    case BI_FILTER: case BI_FILTER_INTO: {
        int lskip = new_label();
        int rr = R(&res);
        ofree(res);
        I("beq %s, r0, .L%d", RN[rr], lskip);
        LV ls = lv_mem(get_local(src), 0, T), ld = lv_mem(get_local(dst), 0, T);
        if (ty_is_aggr(T)) {
            copy_mem(&ld, &ls, T->size, T->align);
            lv_free(&ls);
            lv_free(&ld);
        } else {
            Opnd v = load_lv(&ls, -1);
            store_lv(&ld, v, T);
        }
        bump_local(dst, T->size);
        bump_local(acc, 1);
        put_label(lskip);
        break;
    }
    case BI_REDUCE: set_local(acc, res, U); break;
    default: ofree(res); break;
    }
    bump_local(src, T->size);
    bump_local(cnt, -1);
    {
        Opnd c1 = get_local(cnt);
        int rc = R(&c1);
        ofree(c1);
        I("bne %s, r0, .L%d", RN[rc], ltop);
    }
    put_label(lend);
    if (bi == BI_REDUCE || bi == BI_FILTER || bi == BI_FILTER_INTO) {
        Opnd r = get_local(acc);
        if (hint >= 0) { move_to(r, hint, is_v(e->ty)); ofree(r); return (Opnd){is_v(e->ty) ? O_VREG : O_REG, hint}; }
        return r;
    }
    return (Opnd){O_NONE, 0};
}

/* map(xs, f): the new array in a frame slot (or g_ret_into). */
static LV gen_intrinsic_aggr(Expr *e) {
    LV *into = g_ret_into;
    g_ret_into = NULL;
    if (into) { gen_intrinsic(e, -1, into); return *into; }
    int slot = slot_alloc(e->ty->size);
    LV d = lv_mem((Opnd){O_REG, 14}, slot, e->ty);
    gen_intrinsic(e, -1, &d);
    return lv_mem((Opnd){O_REG, 14}, slot, e->ty);
}

static Opnd gen_lerp_scalar(Expr *e, int hint) {
    /* a + (b - a) * t */
    Opnd x = gen_expr(e->args[0], -1), y = gen_expr(e->args[1], -1), t = gen_expr(e->args[2], -1);
    Opnd x2 = owned(x, 0);
    int rx = R(&x2);
    int dd = tnew(0);
    I("sub %s, %s, %s", RN[g_t[dd].reg], RN[R(&y)], RN[rx]);
    ofree(y);
    I("fmul %s, %s, %s", RN[treg(dd)], RN[treg(dd)], RN[R(&t)]);
    ofree(t);
    int rd = treg(dd);
    rx = R(&x2);
    ofree(x2); tfree(dd);
    int r;
    Opnd d = dest(0, hint, &r);
    I("add %s, %s, %s", RN[r], RN[rx], RN[rd]);
    return d;
}

/* A function value [code, c1, c2, c3]: the code address of `label` and copies of the captured
   locals (unused words are zero). */
static Opnd fn_value(const char *label, Local **caps, int ncaps, int hint) {
    int r;
    Opnd d = dest(1, hint, &r);
    I("vsub %s, %s, %s", VN[r], VN[r], VN[r]);
    int t = tnew(0);
    I("la %s, %s", RN[g_t[t].reg], label);
    int vr = d.k == O_VTMP ? treg(d.v) : r;
    I("vset %s, %s, 0", VN[vr], RN[treg(t)]);
    tfree(t);
    for (int k = 0; k < ncaps; k++) {
        LV lv = lv_local(caps[k]);
        Opnd o = load_lv(&lv, -1);
        int sr = R(&o);
        vr = d.k == O_VTMP ? treg(d.v) : r;
        I("vset %s, %s, %d", VN[vr], RN[sr], k + 1);
        ofree(o);
    }
    return d;
}

/* For == and != on function values: a scalar that is zero exactly when the operands are equal.
   Against null only the code address matters (no other value has code address 0). */
static Opnd fn_diff(Expr *e) {
    Expr *a = e->a, *b = e->b;
    if (a->isconst) { Expr *t = a; a = b; b = t; }
    if (b->isconst && b->cval == 0) {
        Opnd v = gen_expr(a, -1);
        int vr = VR(&v);
        ofree(v);
        int r;
        Opnd d = dest(0, -1, &r);
        I("vget %s, %s, 0", RN[r], VN[vr]);
        return d;
    }
    Opnd x = gen_expr(a, -1), y = gen_expr(b, -1);
    int rx = VR(&x), ry = VR(&y);
    ofree(x); ofree(y);
    int vd;
    Opnd dv = dest(1, -1, &vd);
    I("vsub %s, %s, %s", VN[vd], VN[rx], VN[ry]);
    int r;
    Opnd d = dest(0, -1, &r);
    int t = tnew(0);
    vd = VR(&dv);
    I("vget %s, %s, 0", RN[r], VN[vd]);
    for (int k = 1; k < 4; k++) {
        vd = VR(&dv);
        I("vget %s, %s, %d", RN[treg(t)], VN[vd], k);
        int rd = d.k == O_TMP ? treg(d.v) : r;
        I("or %s, %s, %s", RN[rd], RN[rd], RN[treg(t)]);
    }
    tfree(t);
    ofree(dv);
    return d;
}

static Opnd gen_expr(Expr *e, int hint) {
    if (e->isconst && !ty_is_aggr(e->ty)) {
        if (e->ty->k == TY_FUNC) { int32_t z[4] = {(int32_t)e->cval, 0, 0, 0}; return gen_vconst(z, hint); }
        if (is_v(e->ty)) return gen_vconst(e->cvec, hint);
        if (hint >= 0) { li(hint, (int32_t)(uint32_t)e->cval); return (Opnd){O_REG, hint}; }
        return o_imm(e->cval);
    }
    switch (e->k) {
    case E_NAME: {
        Sym *s = e->sym;
        if (s->k == SY_FUNC) return fn_value(s->fn->label, NULL, 0, hint);
        if (s->k == SY_EMBED) {
            int r;
            Opnd d = dest(0, hint, &r);
            I("la %s, %s", RN[r], s->label);
            return d;
        }
        LV lv = gen_lv(e);
        Opnd o = load_lv(&lv, hint);
        if (hint >= 0 && !((o.k == O_REG || o.k == O_VREG) && o.v == hint)) {
            move_to(o, hint, is_v(e->ty));
            ofree(o);
            return (Opnd){is_v(e->ty) ? O_VREG : O_REG, hint};
        }
        return o;
    }
    case E_STR: {
        int r;
        Opnd d = dest(0, hint, &r);
        I("la %s, %s", RN[r], e->sym->label);
        return d;
    }
    case E_FUNC: {
        Func *f = e->lambda;
        return fn_value(f->ncaps ? ar_printf("%s$v", f->label) : f->label, f->cap_outer, f->ncaps, hint);
    }
    case E_UNARY: {
        int r;
        switch (e->op) {
        case U_NEG:
            if (is_v(e->ty)) {
                Opnd a = gen_expr(e->a, -1);
                VR(&a);
                int z = tnew(1);
                I("vsub %s, %s, %s", VN[g_t[z].reg], VN[g_t[z].reg], VN[g_t[z].reg]);
                int ra = VR(&a);
                int rz = treg(z);
                ofree(a);
                tfree(z);
                Opnd d = dest(1, hint, &r);
                I("vsub %s, %s, %s", VN[r], VN[rz], VN[ra]);
                return d;
            } else {
                Opnd a = gen_expr(e->a, -1);
                int ra = R(&a);
                ofree(a);
                Opnd d = dest(0, hint, &r);
                I("sub %s, r0, %s", RN[r], RN[ra]);
                return d;
            }
        case U_NOT: {
            Opnd a = gen_expr(e->a, -1);
            int ra = R(&a);
            ofree(a);
            Opnd d = dest(0, hint, &r);
            I("xori %s, %s, 1", RN[r], RN[ra]);
            return d;
        }
        case U_BNOT: {
            Opnd a = gen_expr(e->a, -1);
            int ra = R(&a);
            ofree(a);
            Opnd d = dest(0, hint, &r);
            I("sub %s, r0, %s", RN[r], RN[ra]);
            I("addi %s, %s, -1", RN[r], RN[r]);
            if (is_small_int(e->ty)) normalize(r, r, e->ty);
            return d;
        }
        case U_ADDR: {
            LV lv = gen_aggr_lv(e->a);
            Opnd a = lv_addr(&lv);
            if (hint >= 0) { move_to(a, hint, 0); ofree(a); return (Opnd){O_REG, hint}; }
            return a;
        }
        case U_DEREF: {
            LV lv = gen_lv(e);
            return load_lv(&lv, hint);
        }
        default: break;
        }
        break;
    }
    case E_BINARY: return gen_binary(e, hint);
    case E_CALL:
        if (e->bi == BI_MAP) { LV lv = gen_intrinsic_aggr(e); return lv_addr(&lv); }
        if (e->bi >= BI_MAP) return gen_intrinsic(e, hint, NULL);
        if (e->bi == BI_LERP && !is_v(e->ty)) return gen_lerp_scalar(e, hint);
        if (e->bi) return gen_builtin(e, hint);
        if (ty_is_aggr(e->ty)) { LV out; gen_call(e, -1, &out); return lv_addr(&out); }
        return gen_call(e, hint, NULL);
    case E_INDEX: case E_FIELD:
        if (e->k == E_FIELD && !e->field) {
            /* vector lanes */
            if (e->nlanes == 1 && lv_able(e)) {
                LV lv = gen_lv(e);
                return load_lv(&lv, hint);
            }
            Opnd v = gen_expr(e->a, -1);
            int rv = VR(&v);
            int r;
            if (e->nlanes == 1) {
                ofree(v);
                Opnd d = dest(0, hint, &r);
                I("vget %s, %s, %d", RN[r], VN[rv], e->lanes[0]);
                return d;
            }
            int d = tnew(1);
            I("vsub %s, %s, %s", VN[g_t[d].reg], VN[g_t[d].reg], VN[g_t[d].reg]);
            int t = tnew(0);
            for (int i = 0; i < e->nlanes; i++) {
                I("vget %s, %s, %d", RN[treg(t)], VN[VR(&v)], e->lanes[i]);
                I("vset %s, %s, %d", VN[treg(d)], RN[treg(t)], i);
            }
            tfree(t);
            ofree(v);
            if (hint >= 0) { I("vmov %s, %s", VN[hint], VN[treg(d)]); tfree(d); return (Opnd){O_VREG, hint}; }
            return o_tmp(d);
        } else {
            LV lv = gen_lv(e);
            return load_lv(&lv, hint);
        }
    case E_CONV: return gen_conv(e, hint);
    case E_ARRAY: case E_STRUCT: {
        LV lv = gen_aggr_lv(e);
        return lv_addr(&lv);
    }
    default: break;
    }
    ice("unhandled expression");
}

/* ------------------------------------------------------------- conditions */

static const char *branch_op(OpKind op, int uns) {
    switch (op) {
    case B_EQ: return "beq";
    case B_NE: return "bne";
    case B_LT: return uns ? "bltu" : "blt";
    case B_GE: return uns ? "bgeu" : "bge";
    default: return NULL;
    }
}

static OpKind negate(OpKind op) {
    switch (op) {
    case B_EQ: return B_NE;
    case B_NE: return B_EQ;
    case B_LT: return B_GE;
    case B_GE: return B_LT;
    case B_GT: return B_LE;
    case B_LE: return B_GT;
    default: return op;
    }
}

static void gen_cond(Expr *e, int label, int jump_if) {
    if (e->isconst) {
        if (!!e->cval == !!jump_if) I("jmp .L%d", label);
        return;
    }
    if (e->k == E_BINARY && (e->op == B_LAND || e->op == B_LOR)) {
        int is_and = e->op == B_LAND;
        if (is_and != jump_if) {
            /* and/jump-if-false, or/jump-if-true: either operand decides */
            gen_cond(e->a, label, jump_if);
            gen_cond(e->b, label, jump_if);
        } else {
            int skip = new_label();
            gen_cond(e->a, skip, !jump_if);
            gen_cond(e->b, label, jump_if);
            put_label(skip);
        }
        return;
    }
    if (e->k == E_UNARY && e->op == U_NOT) { gen_cond(e->a, label, !jump_if); return; }
    if (e->k == E_BINARY && (e->op == B_EQ || e->op == B_NE) && e->a->ty->k == TY_FUNC) {
        Opnd x = fn_diff(e);
        int rx = R(&x);
        ofree(x);
        I("%s %s, r0, .L%d", (e->op == B_EQ) == !!jump_if ? "beq" : "bne", RN[rx], label);
        return;
    }
    if (e->k == E_BINARY && e->op >= B_EQ && e->op <= B_GE) {
        Type *ot = e->conv_from ? e->conv_from : e->a->ty;
        int uns = !ty_is_signed(ot) && ot->k != TY_BOOL;
        OpKind op = jump_if ? e->op : negate(e->op);
        Opnd a = gen_expr(e->a, -1), b = gen_expr(e->b, -1);
        if (op == B_GT || op == B_LE) { Opnd t = a; a = b; b = t; op = op == B_GT ? B_LT : B_GE; }
        int ra = R(&a), rb = R(&b);
        ra = R(&a);
        ofree(a); ofree(b);
        I("%s %s, %s, .L%d", branch_op(op, uns), RN[ra], RN[rb], label);
        return;
    }
    Opnd v = gen_expr(e, -1);
    int rv = R(&v);
    ofree(v);
    I("%s %s, r0, .L%d", jump_if ? "bne" : "beq", RN[rv], label);
}

/* ------------------------------------------------------------- statements */

static int ends_with_jump(Stmt *s) {
    if (!s) return 0;
    if (s->k == S_RETURN || s->k == S_BREAK || s->k == S_CONTINUE) return 1;
    if (s->k == S_BLOCK && s->n) return ends_with_jump(s->list[s->n - 1]);
    return 0;
}

static void gen_assign_value(LV *lv, Expr *rhs, Type *lt) {
    if (ty_is_aggr(lt)) {
        LV src = gen_aggr_lv(rhs);
        copy_mem(lv, &src, lt->size, lt->align);
        lv_free(&src);
        lv_free(lv);
        return;
    }
    /* stores to memory truncate by themselves */
    if (lv->k == LV_MEM && rhs->k == E_CONV && !rhs->isconst && ty_is_int(rhs->ty) && ty_is_int(rhs->conv_from) && rhs->ty->size < 4)
        rhs = rhs->a;
    if (lv->k == LV_REG || lv->k == LV_VREG) {
        Opnd v = gen_expr(rhs, lv->reg);
        store_lv(lv, v, rhs->ty);
        return;
    }
    Opnd v = gen_expr(rhs, -1);
    store_lv(lv, v, rhs->ty);
}

static void gen_compound(Stmt *s) {
    Expr *bin = s->e2;
    LV lv = gen_lv(s->e);
    Opnd cur;
    int hint = -1;
    if (lv.k == LV_MEM) {
        /* load without consuming the address: it is used again by the store */
        lv_fix(&lv);
        int r;
        Type *t = lv.ty;
        const char *m = mem(&lv);
        if (is_v(t)) { cur = dest(1, -1, &r); I("vld %s, %s", VN[r], m); }
        else { cur = dest(0, -1, &r); I("%s %s, %s", load_op(t), RN[r], m); }
    } else {
        cur = load_lv(&lv, -1);
        if (lv.k == LV_REG || lv.k == LV_VREG) hint = lv.reg;
    }
    Opnd b, res;
    if (is_v(bin->ty)) {
        b = gen_expr(bin->b, -1);
        res = gen_vec_binary(bin, cur, b, hint);
    } else if (bin->ty->k == TY_PTR) {
        int size = bin->ty->elem->size;
        if (bin->b->isconst) b = o_imm(bin->b->cval * size);
        else { b = gen_expr(bin->b, -1); if (size != 1) b = arith(B_MUL, ty_s32, 0, b, o_imm(size), -1); }
        res = arith(bin->op, ty_u32, 0, cur, b, hint);
    } else {
        b = gen_expr(bin->b, -1);
        Type *ot = bin->conv_from && bin->conv_from != ty_s32 ? bin->conv_from : bin->ty;
        res = arith(bin->op, ot, bin->ty->k == TY_FIXED && bin->conv_from == ty_s32, cur, b, hint);
    }
    store_lv(&lv, res, bin->ty);
}

static void zero_local(Local *l) {
    LV lv = lv_local(l);
    if (lv.k == LV_REG) { I("mov %s, r0", RN[lv.reg]); return; }
    if (lv.k == LV_VREG) { I("vsub %s, %s, %s", VN[lv.reg], VN[lv.reg], VN[lv.reg]); return; }
    /* frame slots are word aligned and padded to a whole word */
    zero_mem(&lv, (l->ty->size + 3) & ~3, 4);
    lv_free(&lv);
}

static void gen_stmt(Stmt *s) {
    int mark = g_frame;
    switch (s->k) {
    case S_BLOCK:
        for (int i = 0; i < s->n; i++) gen_stmt(s->list[i]);
        break;
    case S_VAR: {
        Local *l = s->var;
        if (!s->e) { zero_local(l); break; }
        LV lv = lv_local(l);
        if (ty_is_aggr(l->ty) && (s->e->k == E_STRUCT || s->e->k == E_ARRAY)) { gen_aggr_into(s->e, &lv); lv_free(&lv); break; }
        if (ty_is_aggr(l->ty) && s->e->k == E_CALL && s->e->bi == BI_MAP) {
            g_ret_into = &lv;
            gen_intrinsic_aggr(s->e);
            lv_free(&lv);
            break;
        }
        if (ty_is_aggr(l->ty) && s->e->k == E_CALL && ((s->e->callee || s->e->indirect) && !s->e->bi)) {
            /* a new variable cannot alias the arguments: the callee writes the result in place */
            g_ret_into = &lv;
            gen_call(s->e, -1, NULL);
            lv_free(&lv);
            break;
        }
        gen_assign_value(&lv, s->e, l->ty);
        break;
    }
    case S_ASSIGN: {
        if (s->op >= 0) { gen_compound(s); break; }
        Expr *lhs = s->e;
        if (ty_is_aggr(lhs->ty)) {
            LV src = gen_aggr_lv(s->e2);
            LV dst = gen_lv(lhs);
            copy_mem(&dst, &src, lhs->ty->size, lhs->ty->align);
            lv_free(&src);
            lv_free(&dst);
            break;
        }
        /* evaluate the value first when the destination is a register local */
        LV lv;
        if (lhs->k == E_NAME && lhs->sym->k == SY_LOCAL && lhs->sym->local->home) {
            lv = gen_lv(lhs);
            gen_assign_value(&lv, s->e2, lhs->ty);
        } else if (lhs->k == E_NAME) {
            Expr *rhs = s->e2;
            if (rhs->k == E_CONV && !rhs->isconst && ty_is_int(rhs->ty) && ty_is_int(rhs->conv_from) && rhs->ty->size < 4)
                rhs = rhs->a;
            Opnd v = gen_expr(rhs, -1);
            lv = gen_lv(lhs);
            store_lv(&lv, v, rhs->ty);
        } else {
            lv = gen_lv(lhs);
            gen_assign_value(&lv, s->e2, lhs->ty);
        }
        break;
    }
    case S_EXPR: {
        Expr *e = s->e;
        Opnd o;
        if (e->bi >= BI_MAP) { if (e->bi == BI_MAP) gen_intrinsic_aggr(e); else ofree(gen_intrinsic(e, -1, NULL)); o.k = O_NONE; }
        else if (ty_is_aggr(e->ty)) { LV out; gen_call(e, -1, &out); o.k = O_NONE; }
        else o = gen_expr(e, -1);
        ofree(o);
        break;
    }
    case S_IF: {
        /* `if c { break }` / `if c { continue }`: branch straight to the target */
        Stmt *t = s->then;
        while (t && t->k == S_BLOCK && t->n == 1) t = t->list[0];
        if (!s->els && t && (t->k == S_BREAK || t->k == S_CONTINUE) && g_nloop) {
            gen_cond(s->e, t->k == S_BREAK ? g_brk[g_nloop - 1] : g_cont[g_nloop - 1], 1);
            break;
        }
        if (!s->els && t && t->k == S_RETURN && !t->e) {
            gen_cond(s->e, g_ret_label, 1);
            break;
        }
        int lelse = new_label();
        gen_cond(s->e, lelse, 0);
        gen_stmt(s->then);
        if (s->els) {
            int lend = new_label();
            if (!ends_with_jump(s->then)) I("jmp .L%d", lend);
            put_label(lelse);
            gen_stmt(s->els);
            put_label(lend);
        } else put_label(lelse);
        break;
    }
    case S_WHILE: {
        int ltop = new_label(), lcond = new_label(), lbrk = new_label();
        int forever = s->e->isconst && s->e->cval;
        if (!forever) I("jmp .L%d", lcond);
        put_label(ltop);
        g_brk[g_nloop] = lbrk; g_cont[g_nloop] = forever ? ltop : lcond; g_nloop++;
        gen_stmt(s->then);
        g_nloop--;
        put_label(lcond);
        if (forever) I("jmp .L%d", ltop);
        else gen_cond(s->e, ltop, 1);
        put_label(lbrk);
        break;
    }
    case S_FOR: {
        Local *v = s->var, *end = s->for_end;
        LV lv = lv_local(v);
        gen_assign_value(&lv, s->e, v->ty);
        LV le = lv_local(end);
        gen_assign_value(&le, s->e2, end->ty);
        int ltop = new_label(), lcont = new_label(), lcond = new_label(), lbrk = new_label();
        I("jmp .L%d", lcond);
        put_label(ltop);
        g_brk[g_nloop] = lbrk; g_cont[g_nloop] = lcont; g_nloop++;
        gen_stmt(s->then);
        g_nloop--;
        put_label(lcont);
        LV li_ = lv_local(v);
        Opnd cur = load_lv(&li_, -1);
        int hint = li_.k == LV_REG ? li_.reg : -1;
        Opnd nx = arith(B_ADD, v->ty, 0, cur, o_imm(1), hint);
        LV li2 = lv_local(v);
        store_lv(&li2, nx, v->ty);
        put_label(lcond);
        LV a = lv_local(v), b = lv_local(end);
        Opnd oa = load_lv(&a, -1), ob = load_lv(&b, -1);
        int ra = R(&oa), rb = R(&ob);
        ra = R(&oa);
        ofree(oa); ofree(ob);
        I("%s %s, %s, .L%d", ty_is_signed(v->ty) ? "blt" : "bltu", RN[ra], RN[rb], ltop);
        put_label(lbrk);
        break;
    }
    case S_MATCH: {
        /* a chain of compares straight from the value, then the arm bodies */
        int lend = new_label(), lelse = lend;
        int *labels = ar_alloc(sizeof(int) * (size_t)s->narms);
        for (int i = 0; i < s->narms; i++) {
            labels[i] = new_label();
            if (s->arms[i].is_else) lelse = labels[i];
        }
        Opnd x = gen_expr(s->e, -1);
        for (int i = 0; i < s->narms; i++)
            for (int k = 0; k < s->arms[i].npats; k++) {
                Opnd pv = o_imm(s->arms[i].pats[k]->cval);
                int rp = R(&pv), rx = R(&x);
                I("beq %s, %s, .L%d", RN[rx], RN[rp], labels[i]);
                ofree(pv);
            }
        ofree(x);
        I("jmp .L%d", lelse);
        for (int i = 0; i < s->narms; i++) {
            put_label(labels[i]);
            gen_stmt(s->arms[i].body);
            if (i != s->narms - 1 && !ends_with_jump(s->arms[i].body)) I("jmp .L%d", lend);
        }
        put_label(lend);
        break;
    }
    case S_BREAK: I("jmp .L%d", g_brk[g_nloop - 1]); break;
    case S_CONTINUE: I("jmp .L%d", g_cont[g_nloop - 1]); break;
    case S_RETURN: {
        if (s->e) {
            Type *rt = g_fn->ret;
            if (ty_is_aggr(rt)) {
                LV src = gen_aggr_lv(s->e);
                LV dst = lv_local(g_fn->hidden_ret);
                Opnd p = load_lv(&dst, -1);
                LV d = lv_mem(p, 0, rt);
                copy_mem(&d, &src, rt->size, rt->align);
                lv_free(&src);
                lv_free(&d);
            } else if (is_v(rt)) {
                Opnd v = gen_expr(s->e, 0);
                move_to(v, 0, 1);
                ofree(v);
            } else {
                Opnd v = gen_expr(s->e, 1);
                move_to(v, 1, 0);
                ofree(v);
            }
        }
        I("jmp .L%d", g_ret_label);
        break;
    }
    case S_ASM: {
        buf_printf(&g_body, "    ; @asm %s:%d\n", s->asm_loc.file, s->asm_loc.line);
        /* substitute {name} */
        const char *p = s->asm_text;
        Buf line = {0};
        while (*p) {
            if (*p == '{') {
                const char *q = strchr(p, '}');
                char *name = ar_strndup(p + 1, (size_t)(q - p - 1));
                Local *l = NULL;
                for (int i = 0; i < g_fn->nlocals; i++)
                    if (!strcmp(g_fn->locals[i]->name, name) && g_fn->locals[i]->in_asm) l = g_fn->locals[i];
                if (l) {
                    if (!l->home) error_at(s->asm_loc, "'%s' could not be kept in a register for asm (too many asm-named locals)", name);
                    buf_puts(&line, l->home == 2 ? VN[l->reg] : RN[l->reg]);
                } else {
                    Sym *g = sym_lookup(name, s->asm_loc.file);
                    if (g->k == SY_CONST) buf_printf(&line, "%lld", (long long)g->cval);
                    else if (g->k == SY_FUNC) buf_puts(&line, g->fn->label);
                    else if (g->k == SY_REG) buf_printf(&line, "0x%06X", g->addr);
                    else buf_puts(&line, g->label);
                }
                p = q + 1;
                continue;
            }
            buf_putc(&line, *p++);
        }
        /* emit line by line with indentation */
        const char *t = line.p ? line.p : "";
        while (*t) {
            const char *nl = strchr(t, '\n');
            size_t n = nl ? (size_t)(nl - t) : strlen(t);
            buf_puts(&g_body, "    ");
            buf_putn(&g_body, t, n);
            buf_putc(&g_body, '\n');
            t += n + (nl ? 1 : 0);
        }
        buf_puts(&g_body, "    ; @end\n");
        buf_free(&line);
        break;
    }
    }
    if (live_temps()) ice("temporary leaked past a statement");
    g_frame = mark;
}

/* ------------------------------------------------------------- functions */

static void scan_expr(Expr *e, int *max_out);

static void scan_call(Expr *e, int *max_out) {
    Type *types[24];
    int n = 0;
    if (e->indirect) {
        Type *ft = e->a->ty;
        if (ty_is_aggr(ft->elem)) types[n++] = ty_ptr(ft->elem);
        for (int i = 0; i < ft->nparams && n < 24; i++) types[n++] = ty_is_aggr(ft->params[i]) ? ty_ptr(ft->params[i]) : ft->params[i];
    } else {
        Func *f = e->callee;
        if (!f || e->bi) return;
        if (ty_is_aggr(f->ret)) types[n++] = ty_ptr(f->ret);
        for (int i = 0; i < f->nparams && n < 24; i++) types[n++] = ty_is_aggr(f->params[i].ty) ? ty_ptr(f->params[i].ty) : f->params[i].ty;
    }
    int b = stack_arg_bytes(types, n);
    if (b > *max_out) *max_out = b;
}

static void scan_expr(Expr *e, int *max_out) {
    if (!e) return;
    if (e->k == E_CALL) scan_call(e, max_out);
    scan_expr(e->a, max_out);
    scan_expr(e->b, max_out);
    for (int i = 0; i < e->nargs; i++) scan_expr(e->args[i], max_out);
}

static void scan_stmt(Stmt *s, int *max_out) {
    if (!s) return;
    for (int i = 0; i < s->n; i++) scan_stmt(s->list[i], max_out);
    scan_expr(s->e, max_out);
    scan_expr(s->e2, max_out);
    scan_stmt(s->then, max_out);
    scan_stmt(s->els, max_out);
    for (int i = 0; i < s->narms; i++) scan_stmt(s->arms[i].body, max_out);
}

/* ---- live ranges: statements are numbered in order; a local is live from its
 * declaration to its last use, extended to the end of any loop it is used in but
 * declared outside of. Locals whose ranges do not overlap can share a register. */

typedef struct { int *v; int n, cap; } IntVec;
static IntVec g_callpos, g_xfmpos, g_asmpos;
typedef struct { int first, last; } LoopRange;
static LoopRange *g_loops;
static int g_nloops, g_caploops;
static int g_pos;

static void iv_push(IntVec *v, int x) {
    if (v->n && v->v[v->n - 1] == x) return;
    if (v->n == v->cap) {
        int nc = v->cap ? v->cap * 2 : 64;
        int *nv = ar_alloc(sizeof(int) * (size_t)nc);
        if (v->n) memcpy(nv, v->v, sizeof(int) * (size_t)v->n);
        v->v = nv;
        v->cap = nc;
    }
    v->v[v->n++] = x;
}

static void use_local(Local *l, int p) { if (p > l->end) l->end = p; }

static void live_expr(Expr *e, int p) {
    if (!e) return;
    if (e->k == E_NAME && e->sym && e->sym->k == SY_LOCAL) use_local(e->sym->local, p);
    if (e->k == E_CALL && (e->callee || e->indirect)) iv_push(&g_callpos, p);
    if (e->k == E_CALL && e->bi >= BI_MAP) {
        /* the loop state is live across the per-element calls */
        iv_push(&g_callpos, p);
        for (int i = 0; i < 8; i++) if (e->hid[i]) { use_local(e->hid[i], p); e->hid[i]->start = p - 1; }
        /* the arguments are all evaluated before the first call */
        for (int i = 0; i < e->nargs; i++) live_expr(e->args[i], p - 1);
        return;
    }
    if (e->k == E_FUNC) for (int i = 0; i < e->lambda->ncaps; i++) use_local(e->lambda->cap_outer[i], p);
    if (e->k == E_BINARY && e->a && e->a->ty && e->a->ty->k == TY_MAT4 && e->ty && is_v(e->ty)) iv_push(&g_xfmpos, p);
    if (e->k == E_STR || e->isconst) { if (e->k != E_CONV) return; }
    live_expr(e->a, p);
    live_expr(e->b, p);
    for (int i = 0; i < e->nargs; i++) live_expr(e->args[i], p);
}

static void live_asm_refs(Func *f, const char *text, int p) {
    for (const char *q = text; *q; q++) {
        if (*q != '{') continue;
        const char *e = strchr(q, '}');
        if (!e) break;
        size_t n = (size_t)(e - q - 1);
        for (int i = 0; i < f->nlocals; i++) {
            Local *l = f->locals[i];
            if (l->in_asm && strlen(l->name) == n && !strncmp(l->name, q + 1, n)) use_local(l, p);
        }
        q = e;
    }
}

static int count_calls(Expr *e) {
    if (!e) return 0;
    int n = (e->k == E_CALL && (e->callee || e->indirect)) || (e->k == E_BINARY && e->a && e->a->ty && e->a->ty->k == TY_MAT4 && e->ty && is_v(e->ty));
    if (e->k == E_CALL && e->bi >= BI_MAP) n += 2;   /* a loop of calls: never a single call */
    n += count_calls(e->a) + count_calls(e->b);
    for (int i = 0; i < e->nargs; i++) n += count_calls(e->args[i]);
    return n;
}

/* The value expression of a simple statement, if its single call is the whole value: its
   arguments are all evaluated before the call, so they need not survive it. */
static Expr *sole_call(Stmt *s) {
    Expr *v = s->k == S_EXPR || s->k == S_RETURN ? s->e : s->k == S_VAR ? s->e : (s->k == S_ASSIGN && s->op < 0) ? s->e2 : NULL;
    if (!v || v->k != E_CALL || !(v->callee || v->indirect) || v->bi || ty_is_aggr(v->ty)) return NULL;
    int n = count_calls(v);
    if (s->k == S_ASSIGN) n += count_calls(s->e);
    return n == 1 ? v : NULL;
}

/* Statement k has position 2k; uses consumed before its only call are at 2k - 1. */
static void live_stmt(Func *f, Stmt *s) {
    if (!s) return;
    int p;
    switch (s->k) {
    case S_BLOCK: for (int i = 0; i < s->n; i++) live_stmt(f, s->list[i]); break;
    case S_VAR: case S_ASSIGN: case S_EXPR: case S_RETURN: {
        g_pos += 2;
        p = g_pos;
        Expr *call = sole_call(s);
        if (call) {
            iv_push(&g_callpos, p);
            for (int i = 0; i < call->nargs; i++) live_expr(call->args[i], p - 1);
            if (call->indirect) live_expr(call->a, p - 1);
            if (s->k == S_ASSIGN) live_expr(s->e, p);
        } else {
            live_expr(s->e, p);
            live_expr(s->e2, p);
        }
        if (s->k == S_VAR) s->var->start = s->var->end = p;
        if (s->k == S_RETURN && f->hidden_ret) use_local(f->hidden_ret, p);
        break;
    }
    case S_IF:
        g_pos += 2;
        p = g_pos;
        live_expr(s->e, p);
        live_stmt(f, s->then);
        live_stmt(f, s->els);
        break;
    case S_WHILE: case S_FOR: {
        g_pos += 2;
        int first = g_pos;
        live_expr(s->e, first);
        live_expr(s->e2, first);
        if (s->k == S_FOR) {
            /* the loop variable is written before the end bound is evaluated, so it must
               survive any call in the header: start the ranges just before it */
            s->var->start = first - 1;
            s->var->end = first;
            s->for_end->start = first - 1;
            s->for_end->end = first;
        }
        live_stmt(f, s->then);
        g_pos += 2;
        int last = g_pos;
        if (s->k == S_WHILE) live_expr(s->e, last);
        else { use_local(s->var, last); use_local(s->for_end, last); }
        if (g_nloops == g_caploops) {
            int nc = g_caploops ? g_caploops * 2 : 16;
            LoopRange *nl = ar_alloc(sizeof *nl * (size_t)nc);
            if (g_nloops) memcpy(nl, g_loops, sizeof *nl * (size_t)g_nloops);
            g_loops = nl;
            g_caploops = nc;
        }
        g_loops[g_nloops++] = (LoopRange){first, last};
        break;
    }
    case S_MATCH:
        g_pos += 2;
        live_expr(s->e, g_pos);
        for (int i = 0; i < s->narms; i++) live_stmt(f, s->arms[i].body);
        break;
    case S_BREAK: case S_CONTINUE: g_pos += 2; break;
    case S_ASM:
        g_pos += 2;
        p = g_pos;
        iv_push(&g_asmpos, p);
        live_asm_refs(f, s->asm_text, p);
        break;
    }
}

static int any_in(IntVec *v, int lo, int hi) {   /* lo < x <= hi */
    for (int i = 0; i < v->n; i++) if (v->v[i] > lo && v->v[i] <= hi) return 1;
    return 0;
}

static int cmp_prio(const void *a, const void *b) {
    const Local *x = *(Local *const *)a, *y = *(Local *const *)b;
    if (x->in_asm != y->in_asm) return y->in_asm - x->in_asm;
    if (x->weight != y->weight) return x->weight > y->weight ? -1 : 1;
    return x->start - y->start;
}

typedef struct { Local **v; int n, cap; } LocalVec;
static LocalVec g_regusers[24];   /* 0-15 scalar, 16-23 vector */

static int reg_free_for(int slot, Local *l) {
    LocalVec *u = &g_regusers[slot];
    for (int i = 0; i < u->n; i++)
        if (!(u->v[i]->end < l->start || l->end < u->v[i]->start)) return 0;
    return 1;
}

static void reg_take(int slot, Local *l) {
    LocalVec *u = &g_regusers[slot];
    if (u->n == u->cap) {
        int nc = u->cap ? u->cap * 2 : 8;
        Local **nv = ar_alloc(sizeof(Local *) * (size_t)nc);
        if (u->n) memcpy(nv, u->v, sizeof(Local *) * (size_t)u->n);
        u->v = nv;
        u->cap = nc;
    }
    u->v[u->n++] = l;
}

static Local g_iolocal;

/* Decides where every local lives and builds the temporary pools. */
static void assign_homes(Func *f, int *locals_size) {
    g_leaf = !(f->has_call || f->has_asm || f->is_init);
    for (int i = 0; i < 16; i++) g_rown[i] = -2;
    for (int i = 0; i < 8; i++) g_vown[i] = -2;
    memset(g_regusers, 0, sizeof g_regusers);

    /* argument registers */
    int si = 0, vi = 0, soff = 0;
    Local *order[28];
    int norder = 0;
    if (f->hidden_ret) order[norder++] = f->hidden_ret;
    for (int i = 0; i < f->nparams && norder < 24; i++) order[norder++] = f->params[i].local;
    for (int i = 0; i < norder; i++) {
        Local *l = order[i];
        l->in_reg_arg = 0;
        if (is_v(l->ty)) {
            if (vi < 4) { l->in_reg_arg = 1; l->arg_reg = vi++; }
            else { l->stack_arg_off = soff; soff += 16; }
        } else {
            if (si < 4) { l->in_reg_arg = 1; l->arg_reg = 1 + si++; }
            else { l->stack_arg_off = soff; soff += 4; }
        }
    }
    /* a function literal's captured words arrive in r6-r8 */
    for (int i = 0; i < f->ncaps && norder < 28; i++) {
        Local *l = order[norder++] = f->caps[i];
        l->in_reg_arg = 1;
        l->arg_reg = 6 + i;
    }

    /* live ranges */
    g_callpos = g_xfmpos = g_asmpos = (IntVec){0};
    g_nloops = 0;
    g_pos = 0;
    for (int i = 0; i < f->nlocals; i++) { f->locals[i]->start = 0; f->locals[i]->end = 0; f->locals[i]->home = 0; }
    live_stmt(f, f->body);
    for (int i = 0; i < norder; i++) { order[i]->start = 0; if (order[i]->end < 1) order[i]->end = 0; }
    for (int changed = 1; changed;) {
        changed = 0;
        for (int k = 0; k < g_nloops; k++)
            for (int i = 0; i < f->nlocals; i++) {
                Local *l = f->locals[i];
                if (l->start < g_loops[k].first && l->end >= g_loops[k].first && l->end < g_loops[k].last) {
                    l->end = g_loops[k].last;
                    changed = 1;
                }
            }
    }
    for (int i = 0; i < f->nlocals; i++) {
        Local *l = f->locals[i];
        l->crosses_call = any_in(&g_callpos, l->start, l->end) || (!l->in_asm && any_in(&g_asmpos, l->start, l->end));
        l->crosses_xfm = any_in(&g_xfmpos, l->start - 1, l->end);
    }

    /* candidates, best first */
    Local **cand = ar_alloc(sizeof(Local *) * (size_t)(f->nlocals + 2));
    int nc = 0;
    for (int i = 0; i < f->nlocals; i++) {
        Local *l = f->locals[i];
        int byref = ty_is_aggr(l->ty) && l->is_param;
        if (l->addr_taken && !byref) continue;
        if (ty_is_scalar(l->ty) || byref || is_v(l->ty)) cand[nc++] = l;
    }
    g_iobase_reg = -1;
    if (f->uses_io >= 2) {
        memset(&g_iolocal, 0, sizeof g_iolocal);
        g_iolocal.name = "<io base>";
        g_iolocal.ty = ty_u32;
        g_iolocal.weight = f->uses_io;
        g_iolocal.start = 0;
        g_iolocal.end = g_pos + 1;
        g_iolocal.crosses_call = g_callpos.n > 0 || g_asmpos.n > 0;
        cand[nc++] = &g_iolocal;
    }
    qsort(cand, (size_t)nc, sizeof *cand, cmp_prio);

    int sused = 0, vused = 0, argmask = 0;
    /* argument registers of parameters that will probably stay in them */
    for (int i = 0; i < norder; i++) {
        Local *l = order[i];
        if (l->in_reg_arg && !is_v(l->ty) && !l->crosses_call && !(l->addr_taken && !ty_is_aggr(l->ty))) argmask |= 1 << l->arg_reg;
    }
    for (int i = 0; i < nc; i++) {
        Local *l = cand[i];
        int list[16], n = 0;
        if (is_v(l->ty)) {
            if (l->crosses_call && !l->in_asm) continue;
            int lim = l->crosses_xfm || f->uses_xfm ? 3 : 5;
            if (l->in_asm && !f->uses_xfm) lim = 8;
            if (l->is_param && l->in_reg_arg && l->arg_reg < lim) list[n++] = l->arg_reg;
            for (int r = 0; r < lim; r++) list[n++] = r;
            for (int k = 0; k < n; k++)
                if (reg_free_for(16 + list[k], l)) { l->home = 2; l->reg = list[k]; reg_take(16 + list[k], l); vused |= 1 << list[k]; break; }
            continue;
        }
        if (l->crosses_call || l->in_asm) { for (int r = 9; r <= 13; r++) list[n++] = r; }
        else {
            /* parameters keep their argument register; other locals avoid argument registers */
            if (l->is_param && l->in_reg_arg) list[n++] = l->arg_reg;
            for (int r = 1; r <= 4; r++) if (!(argmask >> r & 1)) list[n++] = r;
            for (int r = 9; r <= 13; r++) list[n++] = r;
            for (int r = 1; r <= 4; r++) if (argmask >> r & 1) list[n++] = r;
        }
        for (int k = 0; k < n; k++)
            if (reg_free_for(list[k], l)) { l->home = 1; l->reg = list[k]; reg_take(list[k], l); sused |= 1 << list[k]; break; }
        if (!l->home && l->in_asm) error_at(l->loc, "too many locals named in asm blocks: '%s' cannot get a register", l->name);
    }
    if (f->uses_io >= 2 && g_iolocal.home == 1) g_iobase_reg = g_iolocal.reg;

    /* memory homes */
    int off = g_out_size;
    for (int i = 0; i < f->nlocals; i++) {
        Local *l = f->locals[i];
        if (l->home) continue;
        if (l->is_param && !l->in_reg_arg) continue;   /* stays in the caller's frame */
        int size = (ty_is_aggr(l->ty) && l->is_param) ? 4 : l->ty->size;
        off = (off + 3) & ~3;
        l->off = off;
        off += (size + 3) & ~3;
    }
    *locals_size = off - g_out_size;

    /* temporary pools: everything no local uses */
    g_nspool = g_nvpool = 0;
    static const int sorder[] = {5, 6, 7, 8, 1, 2, 3, 4, 9, 10, 11, 12, 13};
    for (size_t k = 0; k < sizeof sorder / sizeof sorder[0]; k++) {
        int r = sorder[k];
        if (sused >> r & 1) continue;
        g_spool[g_nspool++] = r;
        g_rown[r] = -1;
    }
    for (int r = 0; r < 8; r++) {
        if (vused >> r & 1) continue;
        g_vpool[g_nvpool++] = r;
        g_vown[r] = -1;
    }
    g_saved = sused & 0x3E00;
}

static void gen_asm_func(Func *f, Buf *out) {
    buf_printf(out, "\n; asm fn %s (%s:%d)\n%s:\n", f->name, f->loc.file, f->loc.line, f->label);
    buf_printf(out, "    ; @asm %s:%d\n", f->asm_loc.file, f->asm_loc.line);
    int si = 0, vi = 0;
    const char *names[20], *regs[20];
    int n = 0;
    for (int i = 0; i < f->nparams; i++) {
        Param *p = &f->params[i];
        if (is_v(p->ty)) { if (vi >= 4) error_at(p->loc, "asm functions take at most 4 vector arguments"); regs[n] = VN[vi++]; }
        else { if (si >= 4) error_at(p->loc, "asm functions take at most 4 scalar arguments"); regs[n] = RN[1 + si++]; }
        names[n++] = p->name;
    }
    const char *p = f->asm_text;
    Buf b = {0};
    while (*p) {
        if (*p == '{') {
            const char *q = strchr(p, '}');
            char *name = ar_strndup(p + 1, (size_t)(q - p - 1));
            int found = 0;
            for (int i = 0; i < n; i++) if (!strcmp(names[i], name)) { buf_puts(&b, regs[i]); found = 1; }
            if (!found) {
                Sym *g = sym_lookup(name, f->asm_loc.file);
                if (g->k == SY_CONST) buf_printf(&b, "%lld", (long long)g->cval);
                else if (g->k == SY_FUNC) buf_puts(&b, g->fn->label);
                else if (g->k == SY_REG) buf_printf(&b, "0x%06X", g->addr);
                else buf_puts(&b, g->label);
            }
            p = q + 1;
            continue;
        }
        buf_putc(&b, *p++);
    }
    const char *t = b.p ? b.p : "";
    while (*t) {
        const char *nl = strchr(t, '\n');
        size_t len = nl ? (size_t)(nl - t) : strlen(t);
        buf_puts(out, "    ");
        buf_putn(out, t, len);
        buf_putc(out, '\n');
        t += len + (nl ? 1 : 0);
    }
    buf_puts(out, "    ; @end\n    ret\n");
    buf_free(&b);
}

static void gen_func(Func *f, Buf *out) {
    if (f->is_asm) { gen_asm_func(f, out); return; }
    g_fn = f;
    memset(g_t, 0, sizeof g_t);
    g_body.len = 0;
    if (g_body.p) g_body.p[0] = 0;
    int max_out = 0;
    scan_stmt(f->body, &max_out);
    g_out_size = max_out;
    int locals_size;
    assign_homes(f, &locals_size);
    if (g_out_size + locals_size > 120000) {
        Local *big = NULL;
        for (int i = 0; i < f->nlocals; i++)
            if (!f->locals[i]->home && (!big || f->locals[i]->ty->size > big->ty->size)) big = f->locals[i];
        error_at(big ? big->loc : f->loc, "the locals of %s() need %d bytes of stack; the limit is 120000 (make large arrays global)",
                 f->name, g_out_size + locals_size);
    }
    g_frame = g_frame_max = g_out_size + locals_size;
    g_nloop = 0;
    g_ret_label = new_label();

    /* parameters: move to their homes */
    Local *order[28];
    int norder = 0;
    if (f->hidden_ret) order[norder++] = f->hidden_ret;
    for (int i = 0; i < f->nparams; i++) order[norder++] = f->params[i].local;
    for (int i = 0; i < f->ncaps; i++) order[norder++] = f->caps[i];
    /* 1: register arguments that live in memory; 2: register-to-register moves;
       3: stack arguments that live in registers */
    Move mv[12], vmv[8];
    int nm = 0, nvm = 0, vbusy = 0;
    for (int i = 0; i < norder; i++) {
        Local *l = order[i];
        if (!l->in_reg_arg) continue;
        if (l->home == 0) {
            if (is_v(l->ty)) I("vst %s, [sp+%d]", VN[l->arg_reg], l->off);
            else if (ty_is_aggr(l->ty)) I("sw %s, [sp+%d]", RN[l->arg_reg], l->off);
            else I("%s %s, [sp+%d]", store_op(l->ty), RN[l->arg_reg], l->off);
        } else if (l->home == 1 && l->reg != l->arg_reg) mv[nm++] = (Move){l->arg_reg, l->reg};
        else if (l->home == 2) {
            vbusy |= 1 << l->arg_reg | 1 << l->reg;
            if (l->reg != l->arg_reg) vmv[nvm++] = (Move){l->arg_reg, l->reg};
        }
    }
    parallel_move(mv, nm, 0, 5);
    int vscratch = 7;
    while (vscratch > 0 && (vbusy >> vscratch & 1)) vscratch--;
    parallel_move(vmv, nvm, 1, vscratch);
    for (int i = 0; i < norder; i++) {
        Local *l = order[i];
        if (l->in_reg_arg) continue;
        if (l->home == 1) I("lw %s, [sp+%d+\001]", RN[l->reg], l->stack_arg_off);
        else if (l->home == 2) I("vld %s, [sp+%d+\001]", VN[l->reg], l->stack_arg_off);
    }
    if (g_iobase_reg >= 0) I("lui %s, %u", RN[g_iobase_reg], IO_BASE_ADDR >> 10);

    gen_stmt(f->body);

    /* frame layout: [out args][locals][temps][saved regs][ra] */
    int nonleaf = !g_leaf;
    int saved_regs[8], ns = 0;
    for (int r = 9; r <= 13; r++) if (g_saved >> r & 1) saved_regs[ns++] = r;
    int frame = (g_frame_max + 3) & ~3;
    int save_base = frame;
    frame += 4 * ns + (nonleaf ? 4 : 0);
    if (frame > 131000) error_at(f->loc, "the stack frame of %s() is too large (%d bytes)", f->name, frame);

    buf_printf(out, "\n; fn %s (%s:%d)%s\n", f->name, f->loc.file ? f->loc.file : "-", f->loc.line, g_leaf ? " leaf" : "");
    if (f->ncaps) {
        /* entry through a function value: r6 points at [code, c1, c2, c3] */
        buf_printf(out, "%s$v:\n", f->label);
        for (int k = 1; k < f->ncaps; k++) buf_printf(out, "    lw r%d, [r6+%d]\n", 6 + k, 4 + 4 * k);
        buf_puts(out, "    lw r6, [r6+4]\n");
    }
    buf_printf(out, "%s:\n", f->label);
    if (frame) buf_printf(out, "    addi sp, sp, %d\n", -frame);
    if (nonleaf) buf_printf(out, "    sw ra, [sp+%d]\n", frame - 4);
    for (int i = 0; i < ns; i++) buf_printf(out, "    sw %s, [sp+%d]\n", RN[saved_regs[i]], save_base + 4 * i);
    /* body, with @F replaced by the frame size */
    const char *b = g_body.p ? g_body.p : "";
    /* drop a trailing jump to the return label */
    char tail[64];
    snprintf(tail, sizeof tail, "    jmp .L%d\n", g_ret_label);
    size_t blen = strlen(b), tl = strlen(tail);
    if (blen >= tl && !strcmp(b + blen - tl, tail)) blen -= tl;
    for (size_t i = 0; i < blen; i++) {
        if (b[i] == '\001') buf_printf(out, "%d", frame);
        else buf_putc(out, b[i]);
    }
    buf_printf(out, ".L%d:\n", g_ret_label);
    for (int i = 0; i < ns; i++) buf_printf(out, "    lw %s, [sp+%d]\n", RN[saved_regs[i]], save_base + 4 * i);
    if (nonleaf) buf_printf(out, "    lw ra, [sp+%d]\n", frame - 4);
    if (frame) buf_printf(out, "    addi sp, sp, %d\n", frame);
    buf_puts(out, "    ret\n");
    g_fn = NULL;
}

/* ------------------------------------------------------------- data */

static void serialize(Expr *e, Type *t, uint8_t *buf) {
    if (e->k == E_ARRAY) {
        for (int i = 0; i < e->nargs; i++) serialize(e->args[i], t->elem, buf + i * t->elem->size);
        return;
    }
    if (e->k == E_STRUCT) {
        for (int i = 0; i < e->nargs; i++)
            for (int j = 0; j < t->nfields; j++)
                if (!strcmp(t->fields[j].name, e->fnames[i])) serialize(e->args[i], t->fields[j].type, buf + t->fields[j].offset);
        return;
    }
    if (is_v(t)) {
        for (int i = 0; i < 4; i++) {
            uint32_t v = (uint32_t)e->cvec[i];
            for (int k = 0; k < 4; k++) buf[i * 4 + k] = (uint8_t)(v >> (8 * k));
        }
        return;
    }
    uint32_t v = (uint32_t)e->cval;
    for (int k = 0; k < t->size; k++) buf[k] = (uint8_t)(v >> (8 * k));
}

static void emit_bytes(Buf *out, const uint8_t *p, size_t n) {
    size_t i = 0;
    while (i + 4 <= n) {
        buf_puts(out, "    .word ");
        for (int k = 0; k < 8 && i + 4 <= n; k++, i += 4) {
            uint32_t w = p[i] | (p[i + 1] << 8) | (p[i + 2] << 16) | ((uint32_t)p[i + 3] << 24);
            buf_printf(out, k ? ",0x%08X" : "0x%08X", w);
        }
        buf_putc(out, '\n');
    }
    if (i < n) {
        buf_puts(out, "    .byte ");
        for (int k = 0; i < n; k++, i++) buf_printf(out, k ? ",%u" : "%u", p[i]);
        buf_putc(out, '\n');
    }
}

static void mark_reachable(Func *f) {
    if (f->reachable) return;
    f->reachable = 1;
    for (int i = 0; i < f->nrefs; i++) f->refs[i]->reachable = 1;
    for (int i = 0; i < f->ncalls; i++) mark_reachable(f->calls[i]);
}

static Func *find_fn(const char *name) {
    Sym *s = sym_lookup_global(name);
    return s && s->k == SY_FUNC ? s->fn : NULL;
}

void gen_program(Program *P, Buf *out) {
    g_P = P;
    g_label = 0;
    g_vconsts = NULL;
    g_vconst_n = 0;
    memset(&g_body, 0, sizeof g_body);

    /* RAM layout: small globals first so they stay reachable from r0 */
    Sym **gl = ar_alloc(sizeof(Sym *) * (size_t)(P->nglobals + 1));
    for (int i = 0; i < P->nglobals; i++) gl[i] = P->globals[i];
    /* stable sort: keep declaration order inside each class */
    for (int i = 1; i < P->nglobals; i++) {
        Sym *x = gl[i];
        int j = i - 1;
        while (j >= 0 && (gl[j]->ty->size > 64) > (x->ty->size > 64)) { gl[j + 1] = gl[j]; j--; }
        gl[j + 1] = x;
    }
    uint32_t addr = RAM_GLOBALS_BASE;
    char title[33];
    snprintf(title, sizeof title, "%s", P->title);
    for (char *c = title; *c; c++) if (*c == '"' || *c == '\\' || (unsigned char)*c < 32) *c = '\'';
    if (P->cart_id) buf_printf(out, "; generated by meic\n    .cart \"%s\", __start, \"%s\"\n\n; RAM globals\n", title, P->cart_id);
    else buf_printf(out, "; generated by meic\n    .cart \"%s\", __start\n\n; RAM globals\n", title);
    for (int i = 0; i < P->nglobals; i++) {
        Sym *s = gl[i];
        uint32_t al = (uint32_t)(s->ty->align < 4 && s->ty->size >= 4 ? 4 : s->ty->align);
        addr = (addr + al - 1) & ~(al - 1);
        s->addr = addr;
        buf_printf(out, "%s = 0x%06X    ; %s, %d bytes\n", s->label, addr, ty_str(s->ty), s->ty->size);
        addr += (uint32_t)s->ty->size;
    }
    addr = (addr + 15) & ~15u;
    P->ram_end = addr;
    if (addr > 0x1F0000) error_plain("error: global variables use %u bytes of RAM, leaving too little for the stack", addr);
    buf_printf(out, "__ram_end = 0x%06X\n", addr);

    /* reachability */
    Func *roots[] = {P->init_fn, find_fn("__rt_init"), find_fn("init"), find_fn("__rt_frame_begin"),
                     find_fn("update"), find_fn("draw"), find_fn("__rt_frame_end")};
    for (size_t i = 0; i < sizeof roots / sizeof roots[0]; i++) if (roots[i]) mark_reachable(roots[i]);

    /* entry point and frame loop */
    buf_puts(out, "\n__start:\n");
    if (P->init_fn->body->n) buf_puts(out, "    call F__init_globals\n");
    if (roots[1]) buf_puts(out, "    call F___rt_init\n");
    if (roots[2]) buf_puts(out, "    call F_init\n");
    buf_puts(out, ".frame:\n");
    if (roots[3]) buf_puts(out, "    call F___rt_frame_begin\n");
    if (roots[4]) buf_puts(out, "    call F_update\n");
    if (roots[5]) buf_puts(out, "    call F_draw\n");
    if (roots[6]) buf_puts(out, "    call F___rt_frame_end\n");
    else buf_puts(out, "    vsync\n");
    buf_puts(out, "    jmp .frame\n");

    if (P->init_fn->body->n) gen_func(P->init_fn, out);
    for (int i = 0; i < P->nfuncs; i++) if (P->funcs[i]->reachable) gen_func(P->funcs[i], out);

    /* ROM data */
    buf_puts(out, "\n; ROM data\n    .align 4\n");
    for (VConst *k = g_vconsts; k; k = k->next)
        buf_printf(out, "VC%d: .word 0x%08X,0x%08X,0x%08X,0x%08X\n", k->label,
                   (uint32_t)k->v[0], (uint32_t)k->v[1], (uint32_t)k->v[2], (uint32_t)k->v[3]);
    for (int i = 0; i < P->ndatas; i++) {
        Sym *s = P->datas[i];
        if (!s->reachable) continue;
        buf_puts(out, "    .align 4\n");
        if (s->k == SY_EMBED) {
            buf_printf(out, "%s:    ; embed \"%s\", %zu bytes\n", s->label, s->path, s->datalen);
            emit_bytes(out, s->data, s->datalen);
        } else if (s->is_str) {
            buf_printf(out, "%s:\n", s->label);
            uint8_t *tmp = ar_alloc(s->slen + 1);
            memcpy(tmp, s->str, s->slen);
            emit_bytes(out, tmp, s->slen + 1);
        } else {
            buf_printf(out, "%s:    ; %s\n", s->label, ty_str(s->ty));
            uint8_t *tmp = ar_alloc((size_t)s->ty->size);
            serialize(s->init, s->ty, tmp);
            emit_bytes(out, tmp, (size_t)s->ty->size);
        }
    }
    buf_free(&g_body);
}
