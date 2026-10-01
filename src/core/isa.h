/* Mei instruction set: opcodes, formats, operand shapes and cycle costs.
 * Shared by the CPU, assembler and disassembler. See docs/spec-v0.1.txt. */
#ifndef MEI_ISA_H
#define MEI_ISA_H

#include <stdint.h>

enum {
    OP_BRK = 0x00,
    OP_ADD = 0x01, OP_SUB, OP_MUL, OP_DIV, OP_DIVU, OP_REM, OP_REMU,
    OP_AND, OP_OR, OP_XOR, OP_SHL, OP_SHR, OP_SAR, OP_SLT, OP_SLTU,
    OP_ADDI = 0x10, OP_ANDI, OP_ORI, OP_XORI, OP_SHLI, OP_SHRI, OP_SARI, OP_SLTI,
    OP_LUI = 0x18,
    /* 0x19-0x1B reserved */
    OP_FMUL = 0x1C, OP_FDIV = 0x1D, OP_VSYNC = 0x1E,
    /* 0x1F reserved */
    OP_LB = 0x20, OP_LBU, OP_LH, OP_LHU, OP_LW, OP_SB, OP_SH, OP_SW,
    OP_BEQ = 0x28, OP_BNE, OP_BLT, OP_BGE, OP_BLTU, OP_BGEU,
    OP_JMP = 0x2E, OP_CALL, OP_JR, OP_CALLR,
    OP_VLD = 0x32, OP_VST, OP_VMOV, OP_VGET, OP_VSET, OP_VADD, OP_VSUB,
    OP_VMUL, OP_VSCALE, OP_VDOT, OP_VCROSS, OP_VXFM, OP_VPROJ,
    /* 0x3F reserved */
};

/* Encoding formats. */
typedef enum { FMT_NONE, FMT_R, FMT_I, FMT_U, FMT_J } MeiFormat;

/* Operand shapes, i.e. the assembly syntax of each instruction.
 * s = scalar register, v = vector register. */
typedef enum {
    SHAPE_NONE,      /* brk, vsync                         */
    SHAPE_SSS,       /* add a, b, c        (R)             */
    SHAPE_SSI,       /* addi a, b, imm     (I)             */
    SHAPE_SU,        /* lui a, imm22       (U)             */
    SHAPE_SMEM,      /* lw a, [b+imm]      (I)             */
    SHAPE_BRANCH,    /* beq a, b, label    (I, pc-relative) */
    SHAPE_JUMP,      /* jmp label          (J, absolute)    */
    SHAPE_JREG,      /* jr b               (I, b only)      */
    SHAPE_VMEM,      /* vld va, [b+imm]    (I)             */
    SHAPE_VV,        /* vmov va, vb        (R, c = 0)      */
    SHAPE_SVLANE,    /* vget a, vb, lane   (I)             */
    SHAPE_VSLANE,    /* vset va, b, lane   (I)             */
    SHAPE_VVV,       /* vadd va, vb, vc    (R)             */
    SHAPE_VVS,       /* vscale va, vb, c   (R)             */
    SHAPE_SVV,       /* vdot a, vb, vc     (R)             */
} MeiShape;

typedef struct {
    const char *mnemonic;   /* NULL for reserved opcodes */
    MeiFormat format;
    MeiShape shape;
    int cycles;             /* branches: cost when not taken; taken costs +1 */
} MeiOpInfo;

/* Indexed by opcode (0..63). Defined in isa.c. */
extern const MeiOpInfo mei_ops[64];

/* Field helpers. */
#define MEI_OPCODE(w)  ((uint32_t)(w) >> 26)
#define MEI_FA(w)      (((uint32_t)(w) >> 22) & 0xF)
#define MEI_FB(w)      (((uint32_t)(w) >> 18) & 0xF)
#define MEI_FC(w)      (((uint32_t)(w) >> 14) & 0xF)
#define MEI_IMM18(w)   ((uint32_t)(w) & 0x3FFFF)
#define MEI_IMM22(w)   ((uint32_t)(w) & 0x3FFFFF)
#define MEI_IMM26(w)   ((uint32_t)(w) & 0x3FFFFFF)
#define MEI_SEXT18(x)  ((int32_t)((uint32_t)(x) << 14) >> 14)

#define MEI_ENC_R(op, a, b, c)  (((uint32_t)(op) << 26) | ((uint32_t)(a) << 22) | ((uint32_t)(b) << 18) | ((uint32_t)(c) << 14))
#define MEI_ENC_I(op, a, b, imm) (((uint32_t)(op) << 26) | ((uint32_t)(a) << 22) | ((uint32_t)(b) << 18) | ((uint32_t)(imm) & 0x3FFFF))
#define MEI_ENC_U(op, a, imm)   (((uint32_t)(op) << 26) | ((uint32_t)(a) << 22) | ((uint32_t)(imm) & 0x3FFFFF))
#define MEI_ENC_J(op, imm)      (((uint32_t)(op) << 26) | ((uint32_t)(imm) & 0x3FFFFFF))

#endif
