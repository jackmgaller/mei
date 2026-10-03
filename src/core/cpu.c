/* CPU interpreter: decode, execute, cycle accounting. */
#include "machine.h"
#include "isa.h"

void cpu_reset(Mei *m) {
    for (int i = 0; i < 16; i++) m->r[i] = 0;
    for (int i = 0; i < 8; i++)
        for (int j = 0; j < 4; j++) m->v[i][j] = 0;
    m->pc = ROM_BASE;
    m->r[14] = RAM_BASE + RAM_SIZE;   /* the stack grows down from the top of RAM */
    m->cycles = 0;
    m->vsync_hit = 0;
}

/* Arithmetic shifts written out, since >> on negative values is implementation-defined. */
static uint32_t sar32(uint32_t x, unsigned n) {
    n &= 31;
    return (x & 0x80000000u) ? ~(~x >> n) : x >> n;
}

static int64_t sar64(int64_t x, unsigned n) {
    uint64_t u = (uint64_t)x;
    return (int64_t)(x < 0 ? ~(~u >> n) : u >> n);
}

/* 16.16 multiply: 64-bit product, shift right 16 rounding toward -inf, low 32 bits. */
static int32_t fx_mul(int32_t a, int32_t b) {
    return (int32_t)(uint32_t)sar64((int64_t)a * b, 16);
}

/* Four-lane dot product. The sum is accumulated modulo 2^64; only bits 16-47
 * survive into the result, so the wrap is harmless and deterministic. */
static int32_t fx_dot(const int32_t *a, const int32_t *b) {
    uint64_t s = 0;
    for (int i = 0; i < 4; i++) s += (uint64_t)((int64_t)a[i] * b[i]);
    return (int32_t)(uint32_t)sar64((int64_t)s, 16);
}

/* (n << 16) / d, truncated toward zero, low 32 bits; 0 when d = 0. */
static int32_t fx_div(int32_t n, int32_t d) {
    if (d == 0) return 0;
    return (int32_t)(uint32_t)((int64_t)n * 65536 / d);
}

static int64_t floor_div(int64_t n, int64_t d) {
    if (d == 0) return 0;
    int64_t q = n / d;
    if (n % d != 0 && (n < 0) != (d < 0)) q--;
    return q;
}

static int32_t clamp_screen(int64_t v) {
    return v < -1024 ? -1024 : v > 1023 ? 1023 : (int32_t)v;
}

static int64_t clamp64(int64_t v, int64_t lo, int64_t hi) { return v < lo ? lo : v > hi ? hi : v; }

/* vproj: perspective divide of in (x, y, z, w) to screen coordinates. */
static void project(const int32_t *in, int32_t *out) {
    int32_t x = in[0], y = in[1], z = in[2], w = in[3];
    out[0] = clamp_screen(160 + floor_div((int64_t)160 * x, w));
    out[1] = clamp_screen(120 + floor_div((int64_t)-120 * y, w));
    out[2] = fx_div(z, w);
    out[3] = w;
}

/* ---- geometry instructions (docs/DECISIONS.md, "Geometry instructions") ----
 * A packed screen position holds x in bits 0-15 and y in bits 16-31, both signed:
 * the vertex word of a GPU packet. */
static int32_t px_x(uint32_t p) { return (int32_t)(int16_t)(uint16_t)(p & 0xFFFF); }
static int32_t px_y(uint32_t p) { return (int32_t)sar32(p, 16); }

/* nclip: (x1-x0)(y2-y0) - (x2-x0)(y1-y0), exact in 64 bits, saturated to 32. */
static uint32_t nclip(uint32_t p0, uint32_t p1, uint32_t p2) {
    int64_t x0 = px_x(p0), y0 = px_y(p0);
    int64_t v = (px_x(p1) - x0) * (px_y(p2) - y0) - (px_x(p2) - x0) * (px_y(p1) - y0);
    return (uint32_t)(int32_t)clamp64(v, INT32_MIN, INT32_MAX);
}

/* otz: bias + floor(depth * scale / 2^32), clamped to the ordering table 0..1023. */
static uint32_t otz(uint32_t bias, int32_t depth, int32_t scale) {
    return (uint32_t)clamp64((int64_t)(int32_t)bias + sar64((int64_t)depth * scale, 32), 0, 1023);
}

/* clerp: each byte moves from a toward b by t (16.16, clamped to 0..1), rounding down. */
static uint32_t clerp(uint32_t a, uint32_t b, int32_t t) {
    int64_t f = clamp64(t, 0, 65536);
    uint32_t r = 0;
    for (int i = 0; i < 32; i += 8) {
        int64_t x = (a >> i) & 255, y = (b >> i) & 255;
        r |= (uint32_t)(x + sar64((y - x) * f, 16)) << i;
    }
    return r;
}

/* Decode-time legality: reserved opcodes, R-format must-be-zero bits,
 * vector register fields above 7 (above 5 for vxp3), vget/vset lanes above 3. */
static int legal(uint32_t w) {
    const MeiOpInfo *info = &mei_ops[MEI_OPCODE(w)];
    if (!info->mnemonic) return 0;
    if (info->format == FMT_R && (w & 0x3FFF)) return 0;
    uint32_t a = MEI_FA(w), b = MEI_FB(w), c = MEI_FC(w), imm = MEI_IMM18(w);
    switch (info->shape) {
    case SHAPE_VMEM:   return a < 8;
    case SHAPE_VV:     return a < 8 && b < 8;
    case SHAPE_SVLANE: return b < 8 && imm < 4;
    case SHAPE_VSLANE: return a < 8 && imm < 4;
    case SHAPE_VVV:    return a < 8 && b < 8 && c < 8;
    case SHAPE_VVS:    return a < 8 && b < 8;
    case SHAPE_SVV:    return b < 8 && c < 8;
    case SHAPE_VV3:    return a < 6 && b < 6;
    default:           return 1;
    }
}

/* Validates a control-transfer target so the fault is reported at the jump. */
static int target_ok(Mei *m, uint32_t target) {
    uint32_t dummy;
    return bus_fetch(m, target, &dummy) == 0;
}

void cpu_run(Mei *m) {
    uint32_t *r = m->r;
    while (m->cycles > 0 && !m->fault.kind && !m->vsync_hit) {
        uint32_t w, t;
        if (bus_fetch(m, m->pc, &w)) return;
        uint32_t op = MEI_OPCODE(w);
        if (!legal(w)) { mei_raise(m, MEI_FAULT_ILLEGAL, 0); return; }

        uint32_t a = MEI_FA(w), b = MEI_FB(w), c = MEI_FC(w);
        uint32_t imm = MEI_IMM18(w), simm = (uint32_t)MEI_SEXT18(w);
        uint32_t ea = r[b] + simm;               /* memory operand address */
        uint32_t next = m->pc + 4;
        uint32_t branch = next + (simm << 2);
        int cost = mei_ops[op].cycles;
        int32_t sb = (int32_t)r[b], sc = (int32_t)r[c];
        int32_t *va = m->v[a & 7], *vb = m->v[b & 7], *vc = m->v[c & 7];
        int32_t tmp[4];

        switch (op) {
        case OP_BRK: mei_raise(m, MEI_FAULT_BREAK, 0); return;

        case OP_ADD:  r[a] = r[b] + r[c]; break;
        case OP_SUB:  r[a] = r[b] - r[c]; break;
        case OP_MUL:  r[a] = r[b] * r[c]; break;
        case OP_DIV:
            r[a] = sc == 0 ? 0 : (sb == INT32_MIN && sc == -1) ? r[b] : (uint32_t)(sb / sc);
            break;
        case OP_DIVU: r[a] = r[c] ? r[b] / r[c] : 0; break;
        case OP_REM:
            r[a] = (sc == 0 || sc == -1) ? 0 : (uint32_t)(sb % sc);
            break;
        case OP_REMU: r[a] = r[c] ? r[b] % r[c] : 0; break;
        case OP_AND:  r[a] = r[b] & r[c]; break;
        case OP_OR:   r[a] = r[b] | r[c]; break;
        case OP_XOR:  r[a] = r[b] ^ r[c]; break;
        case OP_SHL:  r[a] = r[b] << (r[c] & 31); break;
        case OP_SHR:  r[a] = r[b] >> (r[c] & 31); break;
        case OP_SAR:  r[a] = sar32(r[b], r[c]); break;
        case OP_SLT:  r[a] = sb < sc; break;
        case OP_SLTU: r[a] = r[b] < r[c]; break;

        case OP_ADDI: r[a] = r[b] + simm; break;
        case OP_ANDI: r[a] = r[b] & imm; break;
        case OP_ORI:  r[a] = r[b] | imm; break;
        case OP_XORI: r[a] = r[b] ^ imm; break;
        case OP_SHLI: r[a] = r[b] << (imm & 31); break;
        case OP_SHRI: r[a] = r[b] >> (imm & 31); break;
        case OP_SARI: r[a] = sar32(r[b], imm); break;
        case OP_SLTI: r[a] = sb < (int32_t)simm; break;
        case OP_LUI:  r[a] = MEI_IMM22(w) << 10; break;

        case OP_FMUL:  r[a] = (uint32_t)fx_mul(sb, sc); break;
        case OP_FDIV:  r[a] = (uint32_t)fx_div(sb, sc); break;
        case OP_VSYNC: m->vsync_hit = 1; break;

        case OP_NCLIP: r[a] = nclip(r[a], r[b], r[c]); break;
        case OP_OTZ:   r[a] = otz(r[a], sb, sc); break;
        case OP_CLERP: r[a] = clerp(r[a], r[b], sc); break;
        case OP_VXP3: {
            /* vxfm then vproj on vb..vb+2 into va..va+2, all read before any is written;
             * lane z holds the packed screen position instead of z / w. */
            int32_t xf[4], out[3][4];
            for (int k = 0; k < 3; k++) {
                for (int i = 0; i < 4; i++) xf[i] = fx_dot(m->v[4 + i], m->v[b + k]);
                project(xf, out[k]);
                out[k][2] = (int32_t)(((uint32_t)out[k][0] & 0xFFFF) | ((uint32_t)out[k][1] << 16));
            }
            for (int k = 0; k < 3; k++)
                for (int i = 0; i < 4; i++) m->v[a + k][i] = out[k][i];
            break;
        }

        case OP_LB:  if (bus_read8(m, ea, &t, 1)) return;  r[a] = t; break;
        case OP_LBU: if (bus_read8(m, ea, &t, 0)) return;  r[a] = t; break;
        case OP_LH:  if (bus_read16(m, ea, &t, 1)) return; r[a] = t; break;
        case OP_LHU: if (bus_read16(m, ea, &t, 0)) return; r[a] = t; break;
        case OP_LW:  if (bus_read32(m, ea, &t)) return;    r[a] = t; break;
        case OP_SB:  if (bus_write8(m, ea, r[a])) return; break;
        case OP_SH:  if (bus_write16(m, ea, r[a])) return; break;
        case OP_SW:  if (bus_write32(m, ea, r[a])) return; break;

        case OP_BEQ: case OP_BNE: case OP_BLT: case OP_BGE: case OP_BLTU: case OP_BGEU: {
            int32_t x = (int32_t)r[a], y = (int32_t)r[b];
            int taken = op == OP_BEQ  ? r[a] == r[b] : op == OP_BNE  ? r[a] != r[b]
                      : op == OP_BLT  ? x < y        : op == OP_BGE  ? x >= y
                      : op == OP_BLTU ? r[a] < r[b]  : r[a] >= r[b];
            if (taken) {
                if (!target_ok(m, branch)) return;
                next = branch;
                cost++;
            }
            break;
        }
        case OP_JMP: case OP_CALL:
            t = MEI_IMM26(w) << 2;
            if (!target_ok(m, t)) return;
            if (op == OP_CALL) r[15] = next;
            next = t;
            break;
        case OP_JR: case OP_CALLR:
            t = r[b];
            if (!target_ok(m, t)) return;
            if (op == OP_CALLR) r[15] = next;
            next = t;
            break;

        case OP_VLD:
            for (int i = 0; i < 4; i++) {
                if (bus_read32(m, ea + 4 * i, &t)) return;
                tmp[i] = (int32_t)t;
            }
            for (int i = 0; i < 4; i++) va[i] = tmp[i];
            break;
        case OP_VST:
            for (int i = 0; i < 4; i++)
                if (bus_write32(m, ea + 4 * i, (uint32_t)va[i])) return;
            break;
        case OP_VMOV: for (int i = 0; i < 4; i++) va[i] = vb[i]; break;
        case OP_VGET: r[a] = (uint32_t)vb[imm]; break;
        case OP_VSET: va[imm] = (int32_t)r[b]; break;
        case OP_VADD: for (int i = 0; i < 4; i++) va[i] = (int32_t)((uint32_t)vb[i] + (uint32_t)vc[i]); break;
        case OP_VSUB: for (int i = 0; i < 4; i++) va[i] = (int32_t)((uint32_t)vb[i] - (uint32_t)vc[i]); break;
        case OP_VMUL: for (int i = 0; i < 4; i++) va[i] = fx_mul(vb[i], vc[i]); break;
        case OP_VSCALE: for (int i = 0; i < 4; i++) va[i] = fx_mul(vb[i], sc); break;
        case OP_VDOT: r[a] = (uint32_t)fx_dot(vb, vc); break;
        case OP_VCROSS: {
            int64_t x = (int64_t)vb[1] * vc[2] - (int64_t)vb[2] * vc[1];
            int64_t y = (int64_t)vb[2] * vc[0] - (int64_t)vb[0] * vc[2];
            int64_t z = (int64_t)vb[0] * vc[1] - (int64_t)vb[1] * vc[0];
            va[0] = (int32_t)(uint32_t)sar64(x, 16);
            va[1] = (int32_t)(uint32_t)sar64(y, 16);
            va[2] = (int32_t)(uint32_t)sar64(z, 16);
            va[3] = 0;
            break;
        }
        case OP_VXFM:
            for (int i = 0; i < 4; i++) tmp[i] = fx_dot(m->v[4 + i], vb);
            for (int i = 0; i < 4; i++) va[i] = tmp[i];
            break;
        case OP_VPROJ:
            project(vb, tmp);
            for (int i = 0; i < 4; i++) va[i] = tmp[i];
            break;
        }
        r[0] = 0;
        m->pc = next;
        m->cycles -= cost;
    }
}
