/* CPU and bus tests: one or more programs per instruction, built by encoding
 * words directly, plus faults, frame timing, system and input registers. */
#include "machine.h"
#include "isa.h"

#include <stdio.h>
#include <string.h>

static Mei *M;
static int checks, fails;
static const char *cur = "";

static void check(int line, const char *what, uint32_t got, uint32_t want) {
    checks++;
    if (got == want) return;
    fails++;
    printf("FAIL [%s] line %d: %s = 0x%08X (%d), want 0x%08X (%d)\n",
           cur, line, what, got, (int32_t)got, want, (int32_t)want);
}
#define EQ(got, want) check(__LINE__, #got, (uint32_t)(got), (uint32_t)(want))

/* ---- program builder ---- */
#define PROG_WORDS 0x2000
#define DATA_IDX   0x1000                     /* data area at ROM_BASE + 0x4000 */
#define DATA       (ROM_BASE + DATA_IDX * 4)
#define IO_HI      0x3FC0                     /* lui r, IO_HI -> 0xFF0000 */

static uint32_t P[PROG_WORDS];
static int N;
static int seen[64];

static void begin(const char *name) { cur = name; memset(P, 0, sizeof P); N = 0; }
static uint32_t here(void) { return ROM_BASE + 4u * (uint32_t)N; }
static uint32_t at(int idx) { return ROM_BASE + 4u * (uint32_t)idx; }
static void e(uint32_t w) { seen[MEI_OPCODE(w)] = 1; P[N++] = w; }
static void vdata(int k, int32_t x, int32_t y, int32_t z, int32_t w) {
    P[DATA_IDX + 4 * k] = (uint32_t)x; P[DATA_IDX + 4 * k + 1] = (uint32_t)y;
    P[DATA_IDX + 4 * k + 2] = (uint32_t)z; P[DATA_IDX + 4 * k + 3] = (uint32_t)w;
}

#define R(op, a, b, c)   MEI_ENC_R(OP_##op, a, b, c)
#define I(op, a, b, imm) MEI_ENC_I(OP_##op, a, b, imm)
#define U(op, a, imm)    MEI_ENC_U(OP_##op, a, imm)
#define J(op, addr)      MEI_ENC_J(OP_##op, (uint32_t)(addr) >> 2)
#define VSYNC            ((uint32_t)OP_VSYNC << 26)
#define FX(x)            ((int32_t)((x) * 65536))

static void li(int r, uint32_t v) {
    int32_t s = (int32_t)v;
    if (s >= -131072 && s <= 131071) { e(I(ADDI, r, 0, s)); return; }
    e(U(LUI, r, v >> 10));
    if (v & 0x3FF) e(I(ORI, r, r, v & 0x3FF));
}

static void load(void) {
    static uint8_t img[PROG_WORDS * 4];
    for (int i = 0; i < PROG_WORDS; i++) wr32(img + 4 * i, P[i]);
    EQ(mei_load_cart(M, img, sizeof img), 0);
}

static int cost(void) { return MEI_CYCLES_PER_FRAME - M->cycles; }

/* Ends the program with vsync, runs one tick, expects a clean presented frame. */
static void exec(void) {
    e(VSYNC);
    e(J(JMP, here()));
    load();
    EQ(mei_run_frame(M), 1);
    EQ(M->fault.kind, MEI_FAULT_NONE);
}

/* Runs the program and expects a fault at the last emitted instruction. */
#define FAULT(kind, addr) fault_last(__LINE__, kind, addr)
static void fault_last(int line, MeiFaultKind kind, uint32_t addr) {
    uint32_t pc = here() - 4;
    load();
    check(line, "presented", (uint32_t)mei_run_frame(M), 0);
    check(line, "fault.kind", M->fault.kind, kind);
    check(line, "fault.pc", M->fault.pc, pc);
    check(line, "fault.addr", M->fault.addr, addr);
    check(line, "pc", M->pc, pc);
}

/* ---- tests ---- */

static void test_encoding(void) {
    begin("encoding");
    EQ(MEI_ENC_I(OP_ADDI, 1, 0, 5), 0x40400005);
    e(0x40400005);
    exec();
    EQ(M->r[1], 5);
    EQ(cost(), 2);
}

static void test_reset_state(void) {
    begin("reset state");
    e(VSYNC);
    load();
    EQ(M->pc, ROM_BASE);
    EQ(M->r[14], RAM_BASE + RAM_SIZE);
    for (int i = 0; i < 16; i++) if (i != 14) EQ(M->r[i], 0);
    for (int i = 0; i < 8; i++) for (int j = 0; j < 4; j++) EQ(M->v[i][j], 0);
    EQ(M->frame, 0);
    EQ(M->fault.kind, MEI_FAULT_NONE);
}

/* R-format scalar op: r3 = r1 op r2. Also checks the cycle cost. */
#define ROP(op, b, c, want) rop(__LINE__, OP_##op, b, c, want)
static void rop(int line, int op, uint32_t b, uint32_t c, uint32_t want) {
    begin(mei_ops[op].mnemonic);
    li(1, b); li(2, c);
    int pre = N;
    e(MEI_ENC_R(op, 3, 1, 2));
    exec();
    check(line, "r3", M->r[3], want);
    check(line, "r1 unchanged", M->r[1], b);
    check(line, "cycles", (uint32_t)cost(), (uint32_t)(pre + mei_ops[op].cycles + 1));
}

/* I-format scalar op: r3 = r1 op imm18. */
#define IOP(op, b, imm, want) iop(__LINE__, OP_##op, b, imm, want)
static void iop(int line, int op, uint32_t b, uint32_t imm, uint32_t want) {
    begin(mei_ops[op].mnemonic);
    li(1, b);
    int pre = N;
    e(MEI_ENC_I(op, 3, 1, imm));
    exec();
    check(line, "r3", M->r[3], want);
    check(line, "cycles", (uint32_t)cost(), (uint32_t)(pre + mei_ops[op].cycles + 1));
}

#define MIN32 0x80000000u
#define NEG(x) ((uint32_t)-(int32_t)(x))

static void test_alu_r(void) {
    ROP(ADD, 0x7FFFFFFF, 1, MIN32);
    ROP(ADD, 5, NEG(7), NEG(2));
    ROP(SUB, 0, 1, 0xFFFFFFFF);
    ROP(SUB, MIN32, 1, 0x7FFFFFFF);
    ROP(MUL, 0x10000, 0x10000, 0);
    ROP(MUL, NEG(3), 7, NEG(21));
    ROP(MUL, 0x12345678, 0x9ABCDEF, 0x12345678u * 0x9ABCDEFu);
    ROP(DIV, 7, 2, 3);
    ROP(DIV, NEG(7), 2, NEG(3));
    ROP(DIV, 7, NEG(2), NEG(3));
    ROP(DIV, NEG(8), NEG(2), 4);
    ROP(DIV, 7, 0, 0);
    ROP(DIV, MIN32, NEG(1), MIN32);
    ROP(DIVU, 0xFFFFFFFF, 2, 0x7FFFFFFF);
    ROP(DIVU, MIN32, 0xFFFFFFFF, 0);
    ROP(DIVU, 5, 0, 0);
    ROP(REM, NEG(7), 2, NEG(1));
    ROP(REM, 7, NEG(2), 1);
    ROP(REM, NEG(7), NEG(2), NEG(1));
    ROP(REM, 7, 0, 0);
    ROP(REM, MIN32, NEG(1), 0);
    ROP(REMU, 0xFFFFFFFF, 10, 5);
    ROP(REMU, 5, 0, 0);
    ROP(AND, 0xF0F0F0F0, 0xFF00FF00, 0xF000F000);
    ROP(OR, 0xF0F0F0F0, 0xFF00FF00, 0xFFF0FFF0);
    ROP(XOR, 0xF0F0F0F0, 0xFF00FF00, 0x0FF00FF0);
    ROP(SHL, 1, 31, MIN32);
    ROP(SHL, 1, 33, 2);
    ROP(SHL, 0xFFFFFFFF, 32, 0xFFFFFFFF);
    ROP(SHR, MIN32, 31, 1);
    ROP(SHR, MIN32, 33, 0x40000000);
    ROP(SAR, MIN32, 31, 0xFFFFFFFF);
    ROP(SAR, MIN32, 36, 0xF8000000);
    ROP(SAR, NEG(16), 2, NEG(4));
    ROP(SAR, 0x40000000, 30, 1);
    ROP(SAR, NEG(1), 0, NEG(1));
    ROP(SLT, NEG(1), 1, 1);
    ROP(SLT, 1, NEG(1), 0);
    ROP(SLT, 5, 5, 0);
    ROP(SLTU, NEG(1), 1, 0);
    ROP(SLTU, 1, NEG(1), 1);
}

static void test_fixed(void) {
    ROP(FMUL, FX(1.5), FX(2), FX(3));
    ROP(FMUL, FX(-1.5), FX(1.5), FX(-2.25));
    ROP(FMUL, NEG(1), 1, NEG(1));            /* -2^-32 rounds down to -1 raw, not 0 */
    ROP(FMUL, NEG(0x8000), 1, NEG(1));
    ROP(FMUL, 0x8000, 1, 0);
    ROP(FMUL, FX(1), NEG(1), NEG(1));
    ROP(FMUL, 0x7FFFFFFF, 0x7FFFFFFF, (uint32_t)(((uint64_t)0x7FFFFFFF * 0x7FFFFFFF) >> 16));
    ROP(FDIV, FX(1), FX(2), FX(0.5));
    ROP(FDIV, FX(-3), FX(2), FX(-1.5));
    ROP(FDIV, NEG(1), FX(2), 0);             /* truncates toward zero */
    ROP(FDIV, 1, 3, 21845);
    ROP(FDIV, NEG(1), 3, NEG(21845));
    ROP(FDIV, FX(3), 0, 0);
    ROP(FDIV, 0x12345678, 1, 0x56780000);    /* overflow keeps the low 32 bits */
    ROP(FDIV, MIN32, NEG(1), 0);
}

static void test_alu_i(void) {
    IOP(ADDI, 0, 5, 5);
    IOP(ADDI, 10, 0x3FFFF, 9);               /* -1 */
    IOP(ADDI, 0, 0x1FFFF, 131071);
    IOP(ADDI, 0, 0x20000, NEG(131072));
    IOP(ANDI, 0xFFFFFFFF, 0x3FFFF, 0x3FFFF); /* zero-extended */
    IOP(ANDI, 0xFFFFFFFF, 0x20000, 0x20000);
    IOP(ORI, 0, 0x3FFFF, 0x3FFFF);
    IOP(ORI, MIN32, 0x20001, 0x80020001);
    IOP(XORI, 0xFFFFFFFF, 0x3FFFF, 0xFFFC0000);
    IOP(SHLI, 1, 33, 2);
    IOP(SHLI, 3, 4, 48);
    IOP(SHLI, 1, 0x3FFFF, MIN32);
    IOP(SHRI, MIN32, 4, 0x08000000);
    IOP(SHRI, 0xFFFFFFFF, 32, 0xFFFFFFFF);
    IOP(SARI, MIN32, 4, 0xF8000000);
    IOP(SARI, 0x70000000, 4, 0x07000000);
    IOP(SLTI, NEG(5), 0x3FFFC, 1);           /* -5 < -4 */
    IOP(SLTI, NEG(5), 0x3FFFA, 0);           /* -5 < -6 */
    IOP(SLTI, 0, 0x20000, 0);                /* 0 < -131072 */
    IOP(SLTI, NEG(131073), 0x20000, 1);
    IOP(SLTI, 5, 0x1FFFF, 1);

    begin("lui");
    e(U(LUI, 1, IO_HI));
    e(U(LUI, 2, 0x3FFFFF));
    e(U(LUI, 3, 0x123456 >> 10));
    e(I(ORI, 3, 3, 0x123456 & 0x3FF));
    exec();
    EQ(M->r[1], 0xFF0000);
    EQ(M->r[2], 0xFFFFFC00);
    EQ(M->r[3], 0x123456);
    EQ(cost(), 5);
}

static void test_r0(void) {
    begin("r0");
    e(I(ADDI, 0, 0, 5));
    e(R(ADD, 1, 0, 0));
    e(U(LUI, 0, 1));
    e(R(OR, 2, 0, 0));
    li(3, 0x1000); li(4, 7);
    e(I(SW, 4, 3, 0));
    e(I(LW, 0, 3, 0));
    e(R(ADD, 5, 0, 0));
    e(I(VSET, 1, 4, 0));
    e(I(VGET, 0, 1, 0));
    e(R(ADD, 6, 0, 0));
    e(I(ADDI, 7, 0, 3));
    e(R(ADD, 8, 7, 0));                      /* mov r8, r7 */
    e(R(ADD, 0, 0, 0));                      /* nop */
    exec();
    EQ(M->r[0], 0); EQ(M->r[1], 0); EQ(M->r[2], 0); EQ(M->r[5], 0); EQ(M->r[6], 0);
    EQ(M->r[8], 3);
}

static void test_memory(void) {
    begin("loads and stores");
    li(1, 0x1000);
    li(2, 0x80FF7F81);
    e(I(SW, 2, 1, 0));
    e(I(LB, 3, 1, 0));
    e(I(LBU, 4, 1, 0));
    e(I(LB, 5, 1, 1));
    e(I(LH, 6, 1, 0));
    e(I(LH, 7, 1, 2));
    e(I(LHU, 8, 1, 2));
    e(I(LW, 9, 1, 0));
    e(I(SB, 2, 1, 7));
    e(I(LW, 10, 1, 4));
    e(I(SH, 2, 1, 8));
    e(I(LW, 11, 1, 8));
    e(I(ADDI, 12, 1, 16));
    e(I(LW, 13, 12, -16));                   /* negative offset */
    e(I(SB, 2, 12, -1));                     /* 0x100F */
    exec();
    EQ(M->r[3], 0xFFFFFF81); EQ(M->r[4], 0x81); EQ(M->r[5], 0x7F);
    EQ(M->r[6], 0x7F81); EQ(M->r[7], 0xFFFF80FF); EQ(M->r[8], 0x80FF);
    EQ(M->r[9], 0x80FF7F81); EQ(M->r[10], 0x81000000); EQ(M->r[11], 0x7F81);
    EQ(M->r[13], 0x80FF7F81);
    EQ(M->ram[0x1000], 0x81); EQ(M->ram[0x1003], 0x80); EQ(M->ram[0x100F], 0x81);
    EQ(cost(), 3 + 14 * 2 + 1 + 1);

    begin("regions");
    e(U(LUI, 1, ROM_BASE >> 10));
    e(I(LW, 2, 1, 0));                       /* ROM: this program's first word */
    li(3, ROM_BASE + ROM_WINDOW - 4);
    e(I(LW, 4, 3, 0));                       /* last word of the ROM window: past the cart, 0 */
    e(U(LUI, 5, VRAM_BASE >> 10));
    li(6, 0x1234ABCD);
    e(I(SW, 6, 5, 0));
    e(I(LHU, 7, 5, 2));
    li(8, 0x4FFFFC);
    e(I(SW, 6, 8, 0));                       /* last VRAM word */
    li(9, 0x1FFFFC);
    e(I(SW, 6, 9, 0));                       /* last RAM word */
    e(I(LW, 10, 9, 0));
    exec();
    EQ(M->r[2], U(LUI, 1, ROM_BASE >> 10));
    EQ(M->r[4], 0);
    EQ(M->r[7], 0x1234);
    EQ(rd32(M->vram), 0x1234ABCD);
    EQ(rd32(M->vram + VRAM_SIZE - 4), 0x1234ABCD);
    EQ(M->r[10], 0x1234ABCD);
}

/* bxx r1, r2 over one instruction. */
#define BR(op, x, y, taken) br(__LINE__, OP_##op, x, y, taken)
static void br(int line, int op, uint32_t x, uint32_t y, int taken) {
    begin(mei_ops[op].mnemonic);
    li(1, x); li(2, y);
    int pre = N;
    e(MEI_ENC_I(op, 1, 2, 2));
    e(I(ADDI, 3, 0, 1));
    e(R(MUL, 5, 0, 0));
    e(I(ADDI, 4, 0, 1));
    exec();
    check(line, "skipped", M->r[3], taken ? 0 : 1);
    check(line, "r4", M->r[4], 1);
    check(line, "cycles", (uint32_t)cost(), (uint32_t)(pre + (taken ? 2 : 1 + 1 + 4) + 1 + 1));
}

static void test_branches(void) {
    BR(BEQ, 5, 5, 1);   BR(BEQ, 5, 6, 0);
    BR(BNE, 5, 6, 1);   BR(BNE, 5, 5, 0);
    BR(BLT, NEG(1), 1, 1); BR(BLT, 1, NEG(1), 0); BR(BLT, 3, 3, 0);
    BR(BGE, 1, NEG(1), 1); BR(BGE, 3, 3, 1); BR(BGE, NEG(1), 1, 0);
    BR(BLTU, 1, NEG(1), 1); BR(BLTU, NEG(1), 1, 0); BR(BLTU, 3, 3, 0);
    BR(BGEU, NEG(1), 1, 1); BR(BGEU, 3, 3, 1); BR(BGEU, 1, NEG(1), 0);

    begin("backward branch");
    li(1, 10);
    e(I(ADDI, 2, 2, 3));
    e(I(ADDI, 1, 1, -1));
    e(I(BNE, 1, 0, -3));
    exec();
    EQ(M->r[2], 30);
    EQ(cost(), 1 + 10 * 2 + 9 * 2 + 1 + 1);
}

static void test_jumps(void) {
    begin("call, callr, jr, jmp");
    uint32_t f = at(7), g = at(9), end = at(11);
    e(J(CALL, f));                           /* 0 */
    e(R(ADD, 2, 1, 0));                      /* 1 */
    e(U(LUI, 5, g >> 10));                   /* 2 */
    e(I(ORI, 5, 5, g & 0x3FF));              /* 3 */
    e(I(CALLR, 0, 5, 0));                    /* 4 */
    e(J(JMP, end));                          /* 5 */
    e(0);                                    /* 6: brk, never reached */
    e(I(ADDI, 1, 0, 42));                    /* 7: f */
    e(I(JR, 0, 15, 0));                      /* 8 */
    e(I(ADDI, 3, 0, 7));                     /* 9: g */
    e(I(JR, 5, 15, 0x123) | (9u << 14));     /* 10: junk a, c and imm are ignored */
    e(R(ADD, 6, 15, 0));                     /* 11: end */
    exec();
    EQ(M->r[1], 42); EQ(M->r[2], 42); EQ(M->r[3], 7);
    EQ(M->r[5], g);
    EQ(M->r[6], at(5));
    EQ(cost(), 2 + 1 + 2 + 1 + 1 + 1 + 2 + 1 + 2 + 2 + 1 + 1);

    begin("callr r15");
    uint32_t h = at(4);
    e(U(LUI, 15, h >> 10));
    e(I(ORI, 15, 15, h & 0x3FF));
    e(I(CALLR, 0, 15, 0));
    e(0);
    e(R(ADD, 7, 15, 0));
    exec();
    EQ(M->r[7], at(3));

    begin("vsync and brk ignore low bits");
    e(VSYNC | 0x123456);
    load();
    EQ(mei_run_frame(M), 1);
    begin("brk junk");
    e(0x00ABCDEF);
    FAULT(MEI_FAULT_BREAK, 0);

    begin("execute from RAM and VRAM");
    e(J(JMP, 0x100));
    load();
    wr32(M->ram + 0x100, I(ADDI, 1, 0, 9));
    wr32(M->ram + 0x104, J(JMP, VRAM_BASE + 0x8));
    wr32(M->vram + 0x8, I(ADDI, 2, 0, 11));
    wr32(M->vram + 0xC, VSYNC);
    EQ(mei_run_frame(M), 1);
    EQ(M->r[1], 9); EQ(M->r[2], 11);
    EQ(M->pc, VRAM_BASE + 0x10);
}

static void test_vector(void) {
    begin("vld vst vmov vget vset");
    vdata(0, 1, -2, 3, 0x7FFFFFFF);
    e(U(LUI, 9, DATA >> 10));
    li(8, 0x2000);
    e(I(VLD, 1, 9, 0));
    e(R(VMOV, 2, 1, 0));
    e(I(VST, 2, 8, 0));
    e(I(VGET, 1, 2, 3));
    e(I(VGET, 4, 2, 1));
    e(I(VSET, 3, 1, 2));
    e(I(VST, 3, 8, 16));
    exec();
    EQ(rd32(M->ram + 0x2000), 1); EQ(rd32(M->ram + 0x2004), NEG(2));
    EQ(rd32(M->ram + 0x2008), 3); EQ(rd32(M->ram + 0x200C), 0x7FFFFFFF);
    EQ(M->r[1], 0x7FFFFFFF); EQ(M->r[4], NEG(2));
    EQ(M->v[3][0], 0); EQ(M->v[3][2], 0x7FFFFFFF);
    EQ(rd32(M->ram + 0x2018), 0x7FFFFFFF);
    EQ(cost(), 1 + 1 + 4 + 1 + 4 + 1 + 1 + 1 + 4 + 1);

    begin("vadd vsub vmul vscale");
    vdata(0, 0x7FFFFFFF, 1, -5, 0);
    vdata(1, 1, 2, 3, 4);
    vdata(2, FX(1.5), FX(-1.5), -1, FX(2));
    vdata(3, FX(2), FX(1.5), 1, FX(0.5));
    e(U(LUI, 9, DATA >> 10));
    e(I(VLD, 1, 9, 0)); e(I(VLD, 2, 9, 16)); e(I(VLD, 3, 9, 32)); e(I(VLD, 4, 9, 48));
    e(R(VADD, 5, 1, 2));
    e(R(VSUB, 6, 1, 2));
    e(R(VMUL, 7, 3, 4));
    li(1, FX(2));
    e(R(VSCALE, 0, 3, 1));
    exec();
    int32_t add[4] = {INT32_MIN, 3, -2, 4}, sub[4] = {0x7FFFFFFE, -1, -8, -4};
    int32_t mul[4] = {FX(3), FX(-2.25), -1, FX(1)}, scl[4] = {FX(3), FX(-3), -2, FX(4)};
    for (int i = 0; i < 4; i++) {
        EQ(M->v[5][i], add[i]); EQ(M->v[6][i], sub[i]);
        EQ(M->v[7][i], mul[i]); EQ(M->v[0][i], scl[i]);
    }

    begin("vdot");
    vdata(0, FX(1), FX(2), FX(3), 0);
    vdata(1, FX(4), FX(5), FX(6), FX(7));
    vdata(2, FX(1), FX(2), FX(3), FX(1));
    vdata(3, -1, 0, 0, 0);
    vdata(4, 1, 0, 0, 0);
    vdata(5, 0x7FFFFFFF, 0x7FFFFFFF, 0x7FFFFFFF, 0x7FFFFFFF);
    e(U(LUI, 9, DATA >> 10));
    for (int k = 0; k < 6; k++) e(I(VLD, k, 9, 16 * k));
    e(R(VDOT, 1, 0, 1));
    e(R(VDOT, 2, 2, 1));
    e(R(VDOT, 3, 3, 4));
    e(R(VDOT, 4, 5, 5));
    exec();
    EQ(M->r[1], FX(32)); EQ(M->r[2], FX(39));
    EQ(M->r[3], NEG(1));                     /* rounds toward -inf */
    EQ(M->r[4], 0xFFFC0000);                 /* bits 16-47 of the exact sum */

    begin("vcross");
    vdata(0, FX(1), 0, 0, FX(5));
    vdata(1, 0, FX(1), 0, FX(7));
    vdata(2, FX(1), FX(2), FX(3), 0);
    vdata(3, FX(4), FX(5), FX(6), 0);
    e(U(LUI, 9, DATA >> 10));
    for (int k = 0; k < 4; k++) e(I(VLD, k, 9, 16 * k));
    e(R(VCROSS, 4, 0, 1));
    e(R(VCROSS, 2, 2, 3));                   /* in place */
    exec();
    EQ(M->v[4][0], 0); EQ(M->v[4][1], 0); EQ(M->v[4][2], FX(1)); EQ(M->v[4][3], 0);
    EQ(M->v[2][0], FX(-3)); EQ(M->v[2][1], FX(6)); EQ(M->v[2][2], FX(-3)); EQ(M->v[2][3], 0);

    begin("vxfm");
    vdata(0, FX(1), 0, 0, FX(10));
    vdata(1, 0, FX(1), 0, FX(20));
    vdata(2, 0, 0, FX(1), FX(30));
    vdata(3, 0, 0, 0, FX(1));
    vdata(4, FX(1), FX(2), FX(3), FX(1));
    e(U(LUI, 9, DATA >> 10));
    for (int k = 0; k < 4; k++) e(I(VLD, 4 + k, 9, 16 * k));
    e(I(VLD, 1, 9, 64));
    e(R(VXFM, 0, 1, 0));
    e(R(VXFM, 5, 1, 0));                     /* destination is a matrix row */
    e(R(VMOV, 3, 5, 0));
    for (int k = 0; k < 4; k++) e(I(VLD, 4 + k, 9, 16 * k));
    e(R(VXFM, 4, 4, 0));                     /* source and destination are row 0 */
    exec();
    int32_t want[4] = {FX(11), FX(22), FX(33), FX(1)};
    for (int i = 0; i < 4; i++) { EQ(M->v[0][i], want[i]); EQ(M->v[3][i], want[i]); }
    EQ(M->v[4][0], FX(101)); EQ(M->v[4][1], FX(200)); EQ(M->v[4][2], FX(300)); EQ(M->v[4][3], FX(10));

    begin("vproj");
    vdata(0, FX(1), FX(1), FX(0.5), FX(2));
    vdata(1, FX(5), FX(-3), FX(7), 0);
    vdata(2, -1, 1, 0, FX(3));
    vdata(3, FX(100), FX(100), 0, FX(1));
    vdata(4, FX(1), FX(1), FX(1), FX(-1));
    e(U(LUI, 9, DATA >> 10));
    for (int k = 0; k < 5; k++) e(I(VLD, k, 9, 16 * k));
    for (int k = 0; k < 5; k++) e(R(VPROJ, k, k, 0));
    exec();
    int32_t pr[5][4] = {
        {240, 60, FX(0.25), FX(2)},
        {160, 120, 0, 0},                    /* w = 0 */
        {159, 119, 0, FX(3)},                /* floor, not truncation */
        {1023, -1024, 0, FX(1)},             /* clamped */
        {0, 240, FX(-1), FX(-1)},            /* negative w */
    };
    for (int k = 0; k < 5; k++) for (int i = 0; i < 4; i++) EQ(M->v[k][i], pr[k][i]);
}

/* ---- geometry instructions: nclip, otz, clerp, vxp3 ---- */

/* r3 = op(r3, r1, r2): the first operand is also an input. */
#define GOP(op, a0, b, c, want) gop(__LINE__, OP_##op, a0, b, c, want)
static void gop(int line, int op, uint32_t a0, uint32_t b, uint32_t c, uint32_t want) {
    begin(mei_ops[op].mnemonic);
    li(3, a0); li(1, b); li(2, c);
    int pre = N;
    e(MEI_ENC_R(op, 3, 1, 2));
    exec();
    check(line, "r3", M->r[3], want);
    check(line, "r1 unchanged", M->r[1], b);
    check(line, "r2 unchanged", M->r[2], c);
    check(line, "cycles", (uint32_t)cost(), (uint32_t)(pre + mei_ops[op].cycles + 1));
}

static uint32_t PK(int32_t x, int32_t y) { return ((uint32_t)x & 0xFFFF) | ((uint32_t)y << 16); }

static uint32_t rng_state = 0x12345678;
static uint32_t rng(void) {
    rng_state ^= rng_state << 13; rng_state ^= rng_state >> 17; rng_state ^= rng_state << 5;
    return rng_state;
}

/* Runs `op r3, r1, r2` on n operand triples from the data area (3 words each) and
 * stores each r3 at RAM 0x10000 + 4i. */
static void gop_batch(int op, const uint32_t (*in)[3], int n) {
    begin(mei_ops[op].mnemonic);
    for (int i = 0; i < n; i++) for (int j = 0; j < 3; j++) P[DATA_IDX + 3 * i + j] = in[i][j];
    e(U(LUI, 9, DATA >> 10));
    li(8, 0x10000);
    for (int i = 0; i < n; i++) {
        e(I(LW, 3, 9, 12 * i)); e(I(LW, 1, 9, 12 * i + 4)); e(I(LW, 2, 9, 12 * i + 8));
        e(MEI_ENC_R(op, 3, 1, 2));
        e(I(SW, 3, 8, 4 * i));
    }
    exec();
}

static void test_geometry(void) {
    /* nclip: (x1-x0)(y2-y0) - (x2-x0)(y1-y0); counter-clockwise on screen is negative */
    GOP(NCLIP, PK(0, 0), PK(10, 0), PK(0, -10), NEG(100));
    GOP(NCLIP, PK(0, 0), PK(0, -10), PK(10, 0), 100);
    GOP(NCLIP, PK(10, 0), PK(0, -10), PK(0, 0), NEG(100));        /* rotation keeps the sign */
    GOP(NCLIP, PK(-1024, -1024), PK(1023, -1024), PK(-1024, 1023), 2047 * 2047);
    GOP(NCLIP, PK(5, 5), PK(9, -3), PK(13, -11), 0);              /* collinear */
    GOP(NCLIP, 0, 0x10000, 1, NEG(1));                            /* y is the high half */
    GOP(NCLIP, PK(-32768, -32768), PK(32767, -32768), PK(-32768, 32767), 0x7FFFFFFF);  /* saturates */
    GOP(NCLIP, PK(-32768, -32768), PK(-32768, 32767), PK(32767, -32768), MIN32);
    GOP(NCLIP, PK(32767, 32767), PK(-32768, 32767), PK(32767, -32768), 0x7FFFFFFF);

    begin("nclip operand aliasing and r0");
    li(1, PK(3, 4)); li(2, PK(-7, 9)); li(4, PK(20, -6));
    e(R(NCLIP, 1, 1, 2));                    /* p0 = p1: zero area */
    li(5, PK(3, 4));
    e(R(NCLIP, 5, 2, 4));
    li(6, 77);
    e(R(NCLIP, 0, 2, 4));                    /* discarded */
    e(R(NCLIP, 6, 0, 0));                    /* p1 = p2 = (0, 0) */
    exec();
    EQ(M->r[1], 0);
    EQ(M->r[5], 15);                         /* (-10)(-10) - (17)(5) */
    EQ(M->r[0], 0);
    EQ(M->r[6], 0);
    {   /* against the stdlib's scalar sequence, on vproj's clamped range */
        static uint32_t in[400][3];
        for (int i = 0; i < 400; i++)
            for (int j = 0; j < 3; j++) in[i][j] = PK((int32_t)(rng() % 2048) - 1024, (int32_t)(rng() % 2048) - 1024);
        gop_batch(OP_NCLIP, (const uint32_t (*)[3])in, 400);
        for (int i = 0; i < 400; i++) {
            int32_t x0 = (int16_t)in[i][0], y0 = (int32_t)in[i][0] >> 16;
            int32_t x1 = (int16_t)in[i][1], y1 = (int32_t)in[i][1] >> 16;
            int32_t x2 = (int16_t)in[i][2], y2 = (int32_t)in[i][2] >> 16;
            EQ(rd32(M->ram + 0x10000 + 4 * i), (uint32_t)((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)));
        }
    }

    /* otz: a = clamp(a + floor(b * c / 2^32), 0, 1023) */
    GOP(OTZ, 0, FX(10), FX(0.5), 5);
    GOP(OTZ, 3, FX(100), FX(1), 103);
    GOP(OTZ, 10, FX(-0.5), FX(1), 9);                             /* floor, not truncation */
    GOP(OTZ, 10, FX(0.5), FX(-1), 9);
    GOP(OTZ, 0, FX(-0.5), FX(-1), 0);                             /* 0.25 */
    GOP(OTZ, 0, 1, 1, 0);
    GOP(OTZ, 1, NEG(1), 1, 0);                                    /* -2^-32 rounds to -1 */
    GOP(OTZ, NEG(5), FX(1), FX(1), 0);                            /* clamped below */
    GOP(OTZ, 1000, FX(30), FX(1), 1023);                          /* clamped above */
    GOP(OTZ, 0, 0x7FFFFFFF, 0x7FFFFFFF, 1023);                    /* 64-bit product */
    GOP(OTZ, 0x7FFFFFFF, 0x7FFFFFFF, 0x7FFFFFFF, 1023);           /* no wrap in the sum */
    GOP(OTZ, MIN32, MIN32, MIN32, 0);
    GOP(OTZ, 0x7FFFFFFF, MIN32, 0x7FFFFFFF, 1023);
    GOP(OTZ, MIN32, 0x7FFFFFFF, 0x7FFFFFFF, 0);
    GOP(OTZ, 1023, 0, 0, 1023);
    GOP(OTZ, 1024, 0, 0, 1023);
    {   /* against the stdlib's fmul / sari 16 / add bias / clamp sequence */
        static uint32_t in[400][3];
        for (int i = 0; i < 400; i++) {
            in[i][0] = (uint32_t)((int32_t)(rng() % 64) - 32);         /* depth_bias */
            in[i][1] = rng() % (uint32_t)FX(400) - (uint32_t)FX(10);   /* sum of w minus n * near */
            in[i][2] = rng() % (uint32_t)FX(4);                        /* 1024 / (far - near) / n */
        }
        gop_batch(OP_OTZ, (const uint32_t (*)[3])in, 400);
        for (int i = 0; i < 400; i++) {
            int32_t f = (int32_t)(uint32_t)((uint64_t)((int64_t)(int32_t)in[i][1] * (int32_t)in[i][2]) >> 16);
            int32_t d = (f >> 16) + (int32_t)in[i][0];
            EQ(rd32(M->ram + 0x10000 + 4 * i), (uint32_t)(d < 0 ? 0 : d > 1023 ? 1023 : d));
        }
    }

    /* clerp: each byte a + floor((b - a) * t / 65536), t clamped to 0..65536 */
    GOP(CLERP, 0x00000000, 0x00FFFFFF, FX(0.5), 0x007F7F7F);
    GOP(CLERP, 0x00FFFFFF, 0x00000000, FX(0.5), 0x007F7F7F);      /* 255 - 127.5 rounds down */
    GOP(CLERP, 0x10203040, 0x50607080, 0, 0x10203040);
    GOP(CLERP, 0x10203040, 0x50607080, FX(1), 0x50607080);
    GOP(CLERP, 0x10203040, 0x50607080, FX(2), 0x50607080);        /* clamped */
    GOP(CLERP, 0x10203040, 0x50607080, NEG(1), 0x10203040);
    GOP(CLERP, 0x10203040, 0x50607080, MIN32, 0x10203040);
    GOP(CLERP, 0x10203040, 0x50607080, 0x7FFFFFFF, 0x50607080);
    GOP(CLERP, 0xFF0000FF, 0x00FF0000, FX(0.25), 0xBF3F00BF);     /* all four bytes */
    GOP(CLERP, 0x000000FF, 0x00000000, 1, 0x000000FE);            /* the smallest step down */
    GOP(CLERP, 0x00000000, 0x000000FF, 1, 0);                     /* ... and up */
    GOP(CLERP, 0x00000003, 0x00000000, 0x8000, 1);                /* 3 - 1.5 = 1.5 -> 1 */
    GOP(CLERP, 0x0000C8C8, 0x00000102, FX(0.75), 0x00003233);     /* uv midpoint style */
    {   /* against the stdlib's fog blend (amount 0..256, red-blue and green lanes) */
        static uint32_t in[400][3];
        for (int i = 0; i < 400; i++) {
            in[i][0] = rng() & 0xFFFFFF;
            in[i][1] = rng() & 0xFFFFFF;
            in[i][2] = (rng() % 257) << 8;
        }
        gop_batch(OP_CLERP, (const uint32_t (*)[3])in, 400);
        for (int i = 0; i < 400; i++) {
            uint32_t c = in[i][0], f = in[i][1], t = in[i][2] >> 8;
            uint32_t rb = ((c & 0xFF00FF) * (256 - t) + (f & 0xFF00FF) * t) >> 8 & 0xFF00FF;
            uint32_t g = ((c & 0xFF00) * (256 - t) + (f & 0xFF00) * t) >> 8 & 0xFF00;
            EQ(rd32(M->ram + 0x10000 + 4 * i), rb | g);
        }
    }

    /* vxp3: bit-exact with vxfm + vproj on lanes x, y and w; lane z is the packed position.
     * Random matrices and points (including w = 0, negative w and clamped results). Program
     * A transforms each point with vxfm and vproj, program B with vxp3 in several register
     * arrangements, including ones that overlap the matrix rows. */
    for (int round = 0; round < 60; round++) {
        int32_t mat[4][4], pt[3][4];
        for (int i = 0; i < 4; i++) for (int j = 0; j < 4; j++) {
            uint32_t r = rng();
            mat[i][j] = (round % 3 == 0) ? (int32_t)r                      /* anything */
                      : (int32_t)(r % (uint32_t)FX(8)) - FX(4);          /* camera-like */
        }
        for (int k = 0; k < 3; k++) for (int j = 0; j < 4; j++) {
            uint32_t r = rng();
            pt[k][j] = (round % 3 == 1) ? (int32_t)r : (int32_t)(r % (uint32_t)FX(200)) - FX(100);
            if (j == 3 && round % 3 != 1) pt[k][j] = FX(1);
        }
        if (round == 5) { for (int j = 0; j < 4; j++) mat[3][j] = 0; }   /* w = 0 */
        int32_t want[3][4];
        begin("vxp3 reference: vxfm + vproj");
        for (int i = 0; i < 4; i++) vdata(i, mat[i][0], mat[i][1], mat[i][2], mat[i][3]);
        for (int k = 0; k < 3; k++) vdata(4 + k, pt[k][0], pt[k][1], pt[k][2], pt[k][3]);
        e(U(LUI, 9, DATA >> 10));
        li(8, 0x10000);
        for (int i = 0; i < 4; i++) e(I(VLD, 4 + i, 9, 16 * i));
        for (int k = 0; k < 3; k++) {
            e(I(VLD, 0, 9, 64 + 16 * k));
            e(R(VXFM, 1, 0, 0));
            e(R(VPROJ, 2, 1, 0));
            e(I(VST, 2, 8, 16 * k));
        }
        exec();
        for (int k = 0; k < 3; k++) for (int i = 0; i < 4; i++) want[k][i] = (int32_t)rd32(M->ram + 0x10000 + 16 * k + 4 * i);
        if (round == 5) EQ(want[0][0], 160);
        /* (destination, source) pairs; sources are loaded first, then the matrix rows that
         * do not overlap them (a source in v4/v5 is also a matrix row: give that row the
         * point's value, so the reference matches) */
        static const int pairs[][2] = {{0, 0}, {1, 1}, {0, 1}, {1, 0}, {3, 0}, {5, 0}, {0, 3}};
        for (size_t pi = 0; pi < sizeof pairs / sizeof *pairs; pi++) {
            int da = pairs[pi][0], sb = pairs[pi][1];
            int ok = 1;
            for (int k = 0; k < 3; k++) if (sb + k >= 4) ok = 0;
            if (sb == 3) {   /* source v3, v4, v5: rows 0 and 1 are the second and third points */
                int32_t m2[4][4];
                memcpy(m2, mat, sizeof m2);
                for (int j = 0; j < 4; j++) { m2[0][j] = pt[1][j]; m2[1][j] = pt[2][j]; }
                begin("vxp3 reference with the points as rows");
                for (int i = 0; i < 4; i++) vdata(i, m2[i][0], m2[i][1], m2[i][2], m2[i][3]);
                for (int k = 0; k < 3; k++) vdata(4 + k, pt[k][0], pt[k][1], pt[k][2], pt[k][3]);
                e(U(LUI, 9, DATA >> 10));
                li(8, 0x10000);
                for (int i = 0; i < 4; i++) e(I(VLD, 4 + i, 9, 16 * i));
                for (int k = 0; k < 3; k++) {
                    e(I(VLD, 0, 9, 64 + 16 * k)); e(R(VXFM, 1, 0, 0)); e(R(VPROJ, 2, 1, 0)); e(I(VST, 2, 8, 16 * k));
                }
                exec();
                for (int k = 0; k < 3; k++) for (int i = 0; i < 4; i++) want[k][i] = (int32_t)rd32(M->ram + 0x10000 + 16 * k + 4 * i);
                ok = 1;
            }
            if (!ok) continue;
            begin("vxp3");
            for (int i = 0; i < 4; i++) vdata(i, mat[i][0], mat[i][1], mat[i][2], mat[i][3]);
            for (int k = 0; k < 3; k++) vdata(4 + k, pt[k][0], pt[k][1], pt[k][2], pt[k][3]);
            e(U(LUI, 9, DATA >> 10));
            li(8, 0x10000);
            for (int i = 0; i < 4; i++) e(I(VLD, 4 + i, 9, 16 * i));
            for (int k = 0; k < 3; k++) e(I(VLD, sb + k, 9, 64 + 16 * k));
            e(R(VXP3, da, sb, 0));
            for (int k = 0; k < 3; k++) e(I(VST, da + k, 8, 16 * k));
            exec();
            EQ(cost(), 1 + 1 + 7 * 4 + 23 + 3 * 4 + 1);   /* lui, addi, 7 vld, vxp3, 3 vst, vsync */
            for (int k = 0; k < 3; k++) {
                for (int i = 0; i < 4; i++) {
                    uint32_t got = rd32(M->ram + 0x10000 + 16 * k + 4 * i);
                    uint32_t exp = i == 2 ? PK(want[k][0], want[k][1]) : (uint32_t)want[k][i];
                    check(__LINE__, "vxp3 lane", got, exp);
                }
            }
            /* registers outside the destination are untouched */
            for (int r = 0; r < 8; r++) {
                if (r >= da && r < da + 3) continue;
                int32_t exp[4] = {0, 0, 0, 0};
                if (r >= sb && r < sb + 3) memcpy(exp, pt[r - sb], sizeof exp);
                else if (r >= 4) memcpy(exp, mat[r - 4], sizeof exp);
                for (int i = 0; i < 4; i++) check(__LINE__, "untouched", (uint32_t)M->v[r][i], (uint32_t)exp[i]);
            }
        }
    }

    begin("vxp3 ignores c");
    e(R(VXP3, 0, 0, 7));
    exec();

    begin("vxp3 a = 5 writes v5-v7");
    li(1, FX(1));
    e(I(VSET, 0, 1, 3)); e(I(VSET, 1, 1, 3)); e(I(VSET, 2, 1, 3));    /* w = 1, matrix all zero */
    e(R(VXP3, 5, 0, 0));
    exec();
    for (int r = 5; r < 8; r++) { EQ(M->v[r][0], 160); EQ(M->v[r][1], 120); EQ(M->v[r][2], PK(160, 120)); EQ(M->v[r][3], 0); }
}

/* One instruction of each non-control opcode in isolation, against the cycle table. */
static void test_cycle_table(void) {
    for (int op = 0; op < 64; op++) {
        const MeiOpInfo *info = &mei_ops[op];
        if (!info->mnemonic || op == OP_BRK || op == OP_VSYNC) continue;
        if (info->shape == SHAPE_BRANCH || info->shape == SHAPE_JUMP || info->shape == SHAPE_JREG) continue;
        int store = op == OP_SB || op == OP_SH || op == OP_SW || op == OP_VST;
        uint32_t w;
        switch (info->shape) {
        case SHAPE_SSI:    w = MEI_ENC_I(op, 1, 2, 5); break;
        case SHAPE_SU:     w = MEI_ENC_U(op, 1, 5); break;
        case SHAPE_SMEM: case SHAPE_VMEM: w = MEI_ENC_I(op, 1, store ? 8 : 9, 0); break;
        case SHAPE_VV: case SHAPE_VV3: w = MEI_ENC_R(op, 1, 2, 0); break;
        case SHAPE_SVLANE: case SHAPE_VSLANE: w = MEI_ENC_I(op, 1, 2, 1); break;
        default:           w = MEI_ENC_R(op, 1, 2, 3); break;
        }
        begin(info->mnemonic);
        e(U(LUI, 9, DATA >> 10));
        e(I(ADDI, 8, 0, 0x1000));
        e(w);
        exec();
        EQ(cost(), 2 + info->cycles + 1);
    }
}

static void test_faults(void) {
    begin("brk"); e(I(ADDI, 1, 0, 1)); e(0); FAULT(MEI_FAULT_BREAK, 0);
    EQ(M->r[1], 1);
    EQ(mei_run_frame(M), 0);                 /* stays halted */
    EQ(M->frame, 1);
    EQ(M->pc, at(1));
    EQ(mei_display(M) == M->error_screen, 1);
    const int16_t *s;
    int n = mei_audio(M, &s);
    EQ(n == 367 || n == 368, 1);
    int silent = 1;
    for (int i = 0; i < 2 * n; i++) silent &= s[i] == 0;
    EQ(silent, 1);

    begin("all-zeros word in RAM"); e(J(JMP, 0x800));
    load();
    EQ(mei_run_frame(M), 0);
    EQ(M->fault.kind, MEI_FAULT_BREAK); EQ(M->fault.pc, 0x800);

    begin("all-ones word"); e(0xFFFFFFFF); FAULT(MEI_FAULT_ILLEGAL, 0);
    int reserved[] = {0x3F};               /* 0x19-0x1B and 0x1F are the geometry instructions */
    for (int i = 0; i < 1; i++) {
        begin("reserved opcode"); e(I(ADDI, 1, 0, 1)); e((uint32_t)reserved[i] << 26);
        FAULT(MEI_FAULT_ILLEGAL, 0);
    }
    begin("R low bits"); e(R(ADD, 1, 2, 3) | 1); FAULT(MEI_FAULT_ILLEGAL, 0);
    begin("R low bits"); e(R(FMUL, 1, 2, 3) | 0x2000); FAULT(MEI_FAULT_ILLEGAL, 0);
    begin("R low bits"); e(R(VADD, 1, 2, 3) | 0x10); FAULT(MEI_FAULT_ILLEGAL, 0);
    begin("R low bits"); e(R(VPROJ, 1, 2, 0) | 0x100); FAULT(MEI_FAULT_ILLEGAL, 0);
    uint32_t geo_low[] = {R(NCLIP, 1, 2, 3) | 1, R(OTZ, 1, 2, 3) | 0x2000, R(CLERP, 1, 2, 3) | 0x40, R(VXP3, 0, 0, 0) | 8};
    for (size_t i = 0; i < sizeof geo_low / sizeof *geo_low; i++) {
        begin("R low bits (geometry)"); e(I(ADDI, 1, 0, 1)); e(geo_low[i]); FAULT(MEI_FAULT_ILLEGAL, 0);
        EQ(M->r[1], 1);
    }
    for (int f = 6; f < 16; f++) {
        begin("vxp3 a field above 5"); e(R(VXP3, f, 0, 0)); FAULT(MEI_FAULT_ILLEGAL, 0);
        begin("vxp3 b field above 5"); e(R(VXP3, 0, f, 0)); FAULT(MEI_FAULT_ILLEGAL, 0);
    }
    begin("vxp3 fault leaves the registers alone");
    li(1, 55); e(I(VSET, 6, 1, 0)); e(R(VXP3, 6, 0, 0)); FAULT(MEI_FAULT_ILLEGAL, 0);
    EQ(M->v[6][0], 55); EQ(M->v[7][0], 0);
    uint32_t badv[] = {
        R(VADD, 8, 1, 2), R(VADD, 1, 9, 2), R(VADD, 1, 2, 15), I(VLD, 8, 0, 0), I(VST, 12, 0, 0),
        R(VMOV, 1, 8, 0), I(VGET, 1, 8, 0), I(VSET, 8, 1, 0), R(VSCALE, 9, 1, 2), R(VDOT, 1, 8, 2),
        R(VCROSS, 1, 2, 10), R(VXFM, 8, 1, 0), R(VPROJ, 1, 11, 0), I(VGET, 1, 1, 4), I(VSET, 1, 1, 0x3FFFF),
    };
    for (size_t i = 0; i < sizeof badv / sizeof *badv; i++) {
        begin("bad vector field"); e(badv[i]); FAULT(MEI_FAULT_ILLEGAL, 0);
    }
    begin("scalar fields 8-15 are fine in the scalar geometry ops");
    e(R(NCLIP, 15, 13, 9)); e(R(OTZ, 12, 8, 11)); e(R(CLERP, 10, 14, 13));
    exec();
    begin("scalar fields 8-15 are fine in vector ops");
    e(R(VSCALE, 1, 2, 9)); e(R(VDOT, 13, 1, 2)); e(I(VGET, 12, 1, 3)); e(I(VSET, 1, 15, 3));
    exec();

    begin("misaligned"); li(1, 0x1001); e(I(LH, 2, 1, 0)); FAULT(MEI_FAULT_MISALIGNED, 0x1001);
    begin("misaligned"); li(1, 0x1001); e(I(LHU, 2, 1, 0)); FAULT(MEI_FAULT_MISALIGNED, 0x1001);
    begin("misaligned"); li(1, 0x1002); e(I(LW, 2, 1, 0)); FAULT(MEI_FAULT_MISALIGNED, 0x1002);
    begin("misaligned"); li(1, 0x1003); e(I(SH, 2, 1, 0)); FAULT(MEI_FAULT_MISALIGNED, 0x1003);
    begin("misaligned"); li(1, 0x1000); e(I(SW, 2, 1, 1)); FAULT(MEI_FAULT_MISALIGNED, 0x1001);
    begin("misaligned"); li(1, 0x1002); e(I(VLD, 2, 1, 0)); FAULT(MEI_FAULT_MISALIGNED, 0x1002);
    begin("misaligned"); li(1, 0x1006); e(I(VST, 2, 1, 0)); FAULT(MEI_FAULT_MISALIGNED, 0x1006);
    begin("misaligned"); li(1, 0x1002); e(I(JR, 0, 1, 0)); FAULT(MEI_FAULT_MISALIGNED, 0x1002);
    begin("vld on 4-byte boundary");
    li(1, 0x1004); e(I(VLD, 2, 1, 0)); e(I(VST, 2, 1, 4)); e(I(LB, 3, 1, 1)); e(I(SB, 3, 1, 3));
    exec();

    begin("unmapped read"); li(1, 0x500000); e(I(LW, 2, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, 0x500000);
    begin("unmapped write"); li(1, 0x600000); e(I(SW, 2, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, 0x600000);
    begin("unmapped write8"); li(1, 0xFEFFFF); e(I(SB, 2, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, 0xFEFFFF);
    begin("bit 24 set"); li(1, 0x1000000); e(I(LW, 2, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, 0x1000000);
    begin("old ROM base"); li(1, 0x200000); e(I(LW, 2, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, 0x200000);
    begin("below the ROM window"); li(1, ROM_BASE - 4); e(I(LW, 2, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, ROM_BASE - 4);
    begin("past the ROM window"); li(1, ROM_BASE + ROM_WINDOW); e(I(LBU, 2, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, ROM_BASE + ROM_WINDOW);
    begin("vld off the ROM window"); li(1, ROM_BASE + ROM_WINDOW - 8); e(I(VLD, 2, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, ROM_BASE + ROM_WINDOW);
    begin("jr past the ROM window"); li(1, ROM_BASE + ROM_WINDOW); e(I(JR, 0, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, ROM_BASE + ROM_WINDOW);
    begin("bit 31 set"); e(I(LBU, 2, 0, -4)); FAULT(MEI_FAULT_UNMAPPED, 0xFFFFFFFC);
    begin("past I/O"); li(1, 0xFF0800); e(I(LW, 2, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, 0xFF0800);
    begin("past broadcast"); li(1, 0xFF0648); e(I(LW, 2, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, 0xFF0648);
    begin("vld into gap"); li(1, 0x4FFFF8); e(I(VLD, 2, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, 0x500000);
    begin("unmapped jmp"); e(I(ADDI, 1, 0, 1)); e(J(JMP, 0x500000)); FAULT(MEI_FAULT_UNMAPPED, 0x500000);
    begin("unmapped call"); e(J(CALL, 0xFF0000)); FAULT(MEI_FAULT_UNMAPPED, 0xFF0000);
    EQ(M->r[15], 0);
    begin("unmapped callr"); li(1, 0x700000); e(I(CALLR, 0, 1, 0)); FAULT(MEI_FAULT_UNMAPPED, 0x700000);
    EQ(M->r[15], 0);
    begin("unmapped branch");
    e(J(JMP, 0x100));
    load();
    wr32(M->ram + 0x100, I(BEQ, 0, 0, -0x80));
    EQ(mei_run_frame(M), 0);
    EQ(M->fault.kind, MEI_FAULT_UNMAPPED); EQ(M->fault.pc, 0x100); EQ(M->fault.addr, 0xFFFFFF04);
    begin("run off the end of VRAM");
    e(J(JMP, 0x4FFFFC));
    load();
    wr32(M->vram + VRAM_SIZE - 4, I(ADDI, 1, 0, 1));
    EQ(mei_run_frame(M), 0);
    EQ(M->fault.kind, MEI_FAULT_UNMAPPED); EQ(M->fault.pc, 0x500000); EQ(M->fault.addr, 0x500000);
    EQ(M->r[1], 1);

    begin("ROM write"); e(U(LUI, 1, ROM_BASE >> 10)); e(I(SW, 1, 1, 0)); FAULT(MEI_FAULT_READ_ONLY, ROM_BASE);
    begin("ROM write8"); li(1, ROM_BASE + ROM_WINDOW - 1); e(I(SB, 1, 1, 0)); FAULT(MEI_FAULT_READ_ONLY, ROM_BASE + ROM_WINDOW - 1);
    begin("ROM vst"); e(U(LUI, 1, ROM_BASE >> 10)); e(I(VST, 1, 1, 0x100)); FAULT(MEI_FAULT_READ_ONLY, ROM_BASE + 0x100);

    /* I/O */
    uint32_t width[] = {I(LB, 1, 9, 0x300), I(LBU, 1, 9, 0x300), I(LH, 1, 9, 0x200), I(LHU, 1, 9, 0x8),
                        I(SB, 1, 9, 0x30C), I(SH, 1, 9, 0x8), I(LB, 1, 9, 0x11C)};
    for (size_t i = 0; i < sizeof width / sizeof *width; i++) {
        begin("bad I/O width"); e(U(LUI, 9, IO_HI)); e(width[i]);
        FAULT(MEI_FAULT_IO_WIDTH, 0xFF0000 + MEI_IMM18(width[i]));
    }
    uint32_t unlisted[] = {0x30, 0x34, 0xFC, 0x11C, 0x1FC, 0x218, 0x2FC, 0x320, 0x3FC};
    for (size_t i = 0; i < sizeof unlisted / sizeof *unlisted; i++) {
        begin("unlisted I/O read"); e(U(LUI, 9, IO_HI)); e(I(LW, 1, 9, unlisted[i]));
        FAULT(MEI_FAULT_UNMAPPED, 0xFF0000 + unlisted[i]);
        begin("unlisted I/O write"); e(U(LUI, 9, IO_HI)); e(I(SW, 1, 9, unlisted[i]));
        FAULT(MEI_FAULT_UNMAPPED, 0xFF0000 + unlisted[i]);
    }
    uint32_t ro[] = {IO_GPU_STATUS, IO_GPU_BACK, IO_GPU_LOAD, IO_GPU_TICKS, IO_GPU_LAG, IO_PAD1, IO_PAD2, IO_STICK1_X, IO_STICK1_Y,
                     IO_STICK2_X, IO_STICK2_Y, IO_SYS_FRAME, IO_SYS_CYCLES, IO_AUDIO + 0xE0 + IO_AUD_POS};
    for (size_t i = 0; i < sizeof ro / sizeof *ro; i++) {
        begin("read-only I/O write"); e(U(LUI, 9, IO_HI)); e(I(SW, 1, 9, ro[i]));
        FAULT(MEI_FAULT_READ_ONLY, 0xFF0000 + ro[i]);
    }
    begin("GPU_DRAW list fault reports the sw");
    e(U(LUI, 9, IO_HI)); li(1, 0x500000); e(I(ADDI, 2, 0, 1)); e(I(SW, 1, 9, IO_GPU_DRAW));
    uint32_t sw_pc = here() - 4;
    e(I(ADDI, 3, 0, 1));
    load();
    EQ(mei_run_frame(M), 0);
    EQ(M->fault.kind, MEI_FAULT_UNMAPPED);
    EQ(M->fault.pc, sw_pc);
    EQ(M->r[3], 0);

    begin("fault leaves state alone");
    li(1, 77); e(R(ADD, 1, 1, 1) | 4);
    FAULT(MEI_FAULT_ILLEGAL, 0);
    EQ(M->r[1], 77);
    EQ(cost(), 1);
}

static void test_vsync_and_overrun(void) {
    begin("vsync ends the tick");
    e(I(ADDI, 1, 0, 1));
    e(VSYNC);
    e(I(ADDI, 2, 0, 1));
    e(VSYNC);
    e(J(JMP, here()));
    load();
    EQ(mei_run_frame(M), 1);
    EQ(M->r[1], 1); EQ(M->r[2], 0); EQ(M->pc, at(2)); EQ(cost(), 2); EQ(M->frame, 1);
    EQ(mei_run_frame(M), 1);
    EQ(M->r[2], 1); EQ(M->pc, at(4)); EQ(cost(), 2); EQ(M->frame, 2);
    EQ(mei_run_frame(M), 0);                 /* jmp-to-self never reaches vsync */
    EQ(M->frame, 3);

    begin("overrun");
    const int spin = MEI_CYCLES_PER_FRAME * 2 / 5;   /* 3 cycles a pass: 1.2 budgets */
    li(1, spin);
    int loop = N;
    e(I(ADDI, 1, 1, -1));
    e(I(BNE, 1, 0, loop - (N + 1)));
    e(I(ADDI, 2, 0, 1));
    e(VSYNC);
    e(J(JMP, here()));
    load();
    const uint16_t *front = mei_display(M);
    EQ(mei_run_frame(M), 0);
    EQ(M->r[2], 0);
    EQ(M->cycles <= 0 && M->cycles >= -1, 1);
    EQ(mei_display(M) == front, 1);          /* previous picture repeats */
    int used1 = cost();
    EQ(M->frame, 1);
    EQ(mei_run_frame(M), 1);                 /* resumes with a fresh budget */
    EQ(M->r[2], 1);
    EQ(M->r[1], 0);
    EQ(cost(), (2 + spin + (spin - 1) * 2 + 1 + 1 + 1) - used1);
    EQ(M->frame, 2);
}

static uint32_t xorshift(uint32_t x) { x ^= x << 13; x ^= x >> 17; x ^= x << 5; return x; }

static char dbg[64];
static int ndbg;
static void dbg_fn(void *user, char c) { (void)user; if (ndbg < 63) dbg[ndbg++] = c; }

static void test_system_regs(void) {
    begin("CYCLES");
    e(U(LUI, 9, IO_HI));
    e(I(LW, 1, 9, IO_SYS_CYCLES));
    for (int i = 0; i < 10; i++) e(R(ADD, 0, 0, 0));
    e(I(LW, 2, 9, IO_SYS_CYCLES));
    exec();
    EQ(M->r[1], MEI_CYCLES_PER_FRAME - 1);
    EQ(M->r[2], MEI_CYCLES_PER_FRAME - 1 - 2 - 10);

    begin("FRAME");
    e(U(LUI, 9, IO_HI));
    e(I(LW, 1, 9, IO_SYS_FRAME));
    e(VSYNC);
    e(J(JMP, at(1)));
    load();
    EQ(mei_run_frame(M), 1); EQ(M->r[1], 0);
    EQ(mei_run_frame(M), 1); EQ(M->r[1], 1);
    EQ(mei_run_frame(M), 1); EQ(M->r[1], 2);
    EQ(M->frame, 3);

    begin("RAND");
    e(U(LUI, 9, IO_HI));
    e(I(LW, 1, 9, IO_SYS_RAND));
    e(I(LW, 2, 9, IO_SYS_RAND));
    e(I(ADDI, 3, 0, 1));
    e(I(SW, 3, 9, IO_SYS_RAND));
    e(I(LW, 4, 9, IO_SYS_RAND));
    e(I(SW, 0, 9, IO_SYS_RAND));
    e(I(LW, 5, 9, IO_SYS_RAND));
    exec();
    uint32_t x1 = xorshift(0x4D454921);
    EQ(M->r[1], x1); EQ(M->r[2], xorshift(x1)); EQ(M->r[4], 270369); EQ(M->r[5], x1);

    begin("DEBUG and write-only reads");
    e(U(LUI, 9, IO_HI));
    e(I(ADDI, 1, 0, 'H'));
    e(I(SW, 1, 9, IO_SYS_DEBUG));
    e(I(ADDI, 1, 0, 0x100 | 'i'));           /* only the low 8 bits print */
    e(I(SW, 1, 9, IO_SYS_DEBUG));
    e(I(ADDI, 2, 0, 5)); e(I(ADDI, 3, 0, 5)); e(I(ADDI, 4, 0, 5));
    e(I(LW, 2, 9, IO_SYS_DEBUG));
    e(I(LW, 3, 9, IO_GPU_DRAW));
    e(I(LW, 4, 9, IO_GPU_CLEAR));
    load();
    mei_set_debug_output(M, dbg_fn, NULL);
    ndbg = 0;
    EQ(mei_run_frame(M), 0);
    EQ(M->fault.kind, MEI_FAULT_BREAK);
    dbg[ndbg] = 0;
    EQ(strcmp(dbg, "Hi"), 0);
    EQ(M->r[2], 0); EQ(M->r[3], 0); EQ(M->r[4], 0);
    mei_set_debug_output(M, NULL, NULL);
    load();
    EQ(mei_run_frame(M), 0);                 /* no sink: DEBUG writes are dropped */
    EQ(M->fault.kind, MEI_FAULT_BREAK);

    begin("GPU and audio registers");
    e(U(LUI, 9, IO_HI));
    e(I(ADDI, 1, 0, 1));
    e(I(SW, 1, 9, IO_GPU_CTRL));
    e(I(LW, 2, 9, IO_GPU_CTRL));
    e(I(LW, 3, 9, IO_GPU_BACK));
    e(I(LW, 4, 9, IO_GPU_STATUS));
    for (int ch = 0; ch < 8; ch += 7)
        for (int r = 0; r <= IO_AUD_POS; r += 4) {
            e(I(LW, 5, 9, IO_AUDIO + ch * 0x20 + r));
            if (r != IO_AUD_POS && r != IO_AUD_CTRL) e(I(SW, 0, 9, IO_AUDIO + ch * 0x20 + r));
        }
    exec();
    EQ(M->r[2], 1);
    EQ(M->r[3] == FB_A_ADDR || M->r[3] == FB_B_ADDR, 1);
    EQ(M->r[4], 0);
}

static void test_input(void) {
    begin("input latch");
    e(U(LUI, 9, IO_HI));
    e(I(LW, 1, 9, IO_PAD1));
    e(I(LW, 2, 9, IO_STICK1_X));
    e(I(LW, 3, 9, IO_STICK1_Y));
    e(I(LW, 4, 9, IO_PAD2));
    e(I(LW, 5, 9, IO_STICK2_X));
    e(I(LW, 6, 9, IO_STICK2_Y));
    e(VSYNC);
    e(J(JMP, at(1)));
    load();
    MeiPadInput p1 = {MEI_BTN_UP | MEI_BTN_START, 0.6f, 0}, p2 = {MEI_BTN_A, 0.1f, -0.1f};
    mei_set_pad(M, 0, &p1);
    mei_set_pad(M, 1, &p2);
    EQ(mei_run_frame(M), 1);
    for (int i = 1; i <= 6; i++) EQ(M->r[i], 0);    /* nothing latched before the first vsync */
    EQ(mei_run_frame(M), 1);
    EQ(M->r[1], 0x401); EQ(M->r[2], 32768); EQ(M->r[3], 0);
    EQ(M->r[4], MEI_BTN_A); EQ(M->r[5], 0); EQ(M->r[6], 0);

    struct { float x, y; int32_t wx, wy; } st[] = {
        {0, 0, 0, 0}, {0.2f, 0, 0, 0}, {0, -0.19f, 0, 0},
        {1, 0, 65536, 0}, {-1, 0, -65536, 0}, {0, 1, 0, 65536}, {0, -1, 0, -65536},
        {1, 1, 46341, 46341}, {-1, -1, -46341, -46341}, {2.5f, 0, 65536, 0},
        {0.6f, 0, 32768, 0}, {0, -0.6f, 0, -32768},
    };
    for (size_t i = 0; i < sizeof st / sizeof *st; i++) {
        MeiPadInput p = {0, st[i].x, st[i].y};
        mei_set_pad(M, 0, &p);
        mei_run_frame(M);
        EQ(M->pad_stick[0][0], st[i].wx);
        EQ(M->pad_stick[0][1], st[i].wy);
    }
}

static void test_api(void) {
    begin("api");
    Mei *m = mei_create();
    EQ(mei_fault(m)->kind, MEI_FAULT_NO_CART);
    EQ(mei_run_frame(m), 0);
    EQ(mei_display(m) == m->error_screen, 1);
    EQ(strcmp(mei_cart_title(m), ""), 0);
    static uint8_t big[MEI_ROM_MAX + 1];
    EQ(mei_load_cart(m, big, MEI_ROM_MAX + 1), (uint32_t)-1);
    EQ(mei_load_cart(m, big, 0), (uint32_t)-1);
    EQ(mei_fault(m)->kind, MEI_FAULT_NO_CART);
    EQ(mei_load_cart(m, big, MEI_ROM_MAX), 0);
    EQ(mei_fault(m)->kind, MEI_FAULT_NONE);
    EQ(mei_run_frame(m), 0);                 /* all-zeros ROM: brk */
    EQ(mei_fault(m)->kind, MEI_FAULT_BREAK);
    EQ(mei_load_cart(m, big, MEI_ROM_MAX + 1), (uint32_t)-1);   /* a rejected cart leaves the last one */
    EQ(m->rom_len, MEI_ROM_MAX);

    uint8_t hdr[64] = {0};
    wr32(hdr, VSYNC);
    memcpy(hdr + 4, "MEI1", 4);
    memcpy(hdr + 8, "Test Cart", 9);
    EQ(mei_load_cart(m, hdr, sizeof hdr), 0);
    EQ(strcmp(mei_cart_title(m), "Test Cart"), 0);
    memset(hdr + 8, 'x', 32);
    EQ(mei_load_cart(m, hdr, sizeof hdr), 0);
    EQ(strlen(mei_cart_title(m)), 32);
    memcpy(hdr + 4, "MEI2", 4);
    EQ(mei_load_cart(m, hdr, sizeof hdr), 0);
    EQ(strcmp(mei_cart_title(m), ""), 0);
    EQ(mei_run_frame(m), 1);
    mei_destroy(m);

    begin("reset");
    li(1, 0x1000); li(2, 99);
    e(I(SW, 2, 1, 0));
    e(I(ADDI, 14, 0, 4));
    e(I(VSET, 3, 2, 1));
    e(0);
    load();
    EQ(mei_run_frame(M), 0);
    EQ(M->fault.kind, MEI_FAULT_BREAK);
    mei_reset(M);
    EQ(M->fault.kind, MEI_FAULT_NONE);
    EQ(M->ram[0x1000], 0); EQ(M->r[14], RAM_BASE + RAM_SIZE); EQ(M->r[2], 0); EQ(M->v[3][1], 0);
    EQ(M->pc, ROM_BASE); EQ(M->frame, 0);
    EQ(mei_run_frame(M), 0);
    EQ(M->ram[0x1000], 99);

    const char *names[] = {"Break", "Illegal instruction", "Misaligned access", "Unmapped address",
                           "Read-only write", "Bad I/O width", "Bad packet list", "No cart"};
    for (int k = MEI_FAULT_BREAK; k <= MEI_FAULT_NO_CART; k++)
        EQ(strcmp(mei_fault_name((MeiFaultKind)k), names[k - 1]), 0);
}

static void test_coverage(void) {
    cur = "coverage";
    int n = 0;
    for (int op = 0; op < 64; op++) {
        if (!mei_ops[op].mnemonic) continue;
        n++;
        if (!seen[op]) { fails++; printf("FAIL [coverage] opcode %02X (%s) never tested\n", op, mei_ops[op].mnemonic); }
    }
    EQ(n, 63);
}

int main(void) {
    M = mei_create();
    test_encoding();
    test_reset_state();
    test_alu_r();
    test_fixed();
    test_alu_i();
    test_r0();
    test_memory();
    test_branches();
    test_jumps();
    test_vector();
    test_geometry();
    test_cycle_table();
    test_faults();
    test_vsync_and_overrun();
    test_system_regs();
    test_input();
    test_api();
    test_coverage();
    mei_destroy(M);
    printf("test_cpu: %d checks, %d failed\n", checks, fails);
    return fails != 0;
}
