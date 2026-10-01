/* Mei disassembler. Output is valid assembler input that re-assembles (at the same pc)
 * to the same word: words the CPU rejects, or that carry bits the assembler cannot
 * express, come out as ".word 0x...". */
#include "asm.h"
#include "isa.h"

#include <stdio.h>

static void mem(char *out, size_t n, int base, int32_t off) {
    char sign = off < 0 ? '-' : '+';
    unsigned mag = off < 0 ? 0u - (unsigned)off : (unsigned)off;
    if (off == 0) snprintf(out, n, "[r%d]", base);
    else if (mag < 256) snprintf(out, n, "[r%d%c%u]", base, sign, mag);
    else snprintf(out, n, "[r%d%c0x%X]", base, sign, mag);
}

void mei_disasm(uint32_t w, uint32_t pc, char *buf, size_t n) {
    int op = (int)MEI_OPCODE(w), a = (int)MEI_FA(w), b = (int)MEI_FB(w), c = (int)MEI_FC(w);
    uint32_t imm = MEI_IMM18(w);
    int32_t simm = MEI_SEXT18(w);
    int low14 = (w & 0x3FFF) != 0;
    const MeiOpInfo *in = &mei_ops[op];
    const char *m = in->mnemonic;
    char ms[32];
    if (!m) goto word;
    switch (in->shape) {
    case SHAPE_NONE:
        if (MEI_IMM26(w)) snprintf(buf, n, "%s 0x%X", m, MEI_IMM26(w));
        else snprintf(buf, n, "%s", m);
        return;
    case SHAPE_SSS:
        if (low14) goto word;
        if (op == OP_ADD && !a && !b && !c) snprintf(buf, n, "nop");
        else if (op == OP_ADD && !c) snprintf(buf, n, "mov r%d, r%d", a, b);
        else snprintf(buf, n, "%s r%d, r%d, r%d", m, a, b, c);
        return;
    case SHAPE_SSI:
        if (op == OP_ANDI || op == OP_ORI || op == OP_XORI) snprintf(buf, n, "%s r%d, r%d, 0x%X", m, a, b, imm);
        else if (op >= OP_SHLI && op <= OP_SARI) {
            if (imm > 31) goto word;
            snprintf(buf, n, "%s r%d, r%d, %u", m, a, b, imm);
        } else snprintf(buf, n, "%s r%d, r%d, %d", m, a, b, simm);
        return;
    case SHAPE_SU:
        snprintf(buf, n, "%s r%d, 0x%X", m, a, MEI_IMM22(w));
        return;
    case SHAPE_SMEM:
        mem(ms, sizeof ms, b, simm);
        snprintf(buf, n, "%s r%d, %s", m, a, ms);
        return;
    case SHAPE_BRANCH:
        snprintf(buf, n, "%s r%d, r%d, 0x%X", m, a, b, pc + 4 + (uint32_t)simm * 4);
        return;
    case SHAPE_JUMP:
        snprintf(buf, n, "%s 0x%X", m, MEI_IMM26(w) << 2);
        return;
    case SHAPE_JREG:
        if (a || imm) goto word;  /* ignored fields set: legal but not expressible */
        if (op == OP_JR && b == 15) snprintf(buf, n, "ret");
        else snprintf(buf, n, "%s r%d", m, b);
        return;
    case SHAPE_VMEM:
        if (a > 7) goto word;
        mem(ms, sizeof ms, b, simm);
        snprintf(buf, n, "%s v%d, %s", m, a, ms);
        return;
    case SHAPE_VV:
        if (low14 || c || a > 7 || b > 7) goto word;
        snprintf(buf, n, "%s v%d, v%d", m, a, b);
        return;
    case SHAPE_SVLANE:
        if (b > 7 || imm > 3) goto word;
        snprintf(buf, n, "%s r%d, v%d, %u", m, a, b, imm);
        return;
    case SHAPE_VSLANE:
        if (a > 7 || imm > 3) goto word;
        snprintf(buf, n, "%s v%d, r%d, %u", m, a, b, imm);
        return;
    case SHAPE_VVV:
        if (low14 || a > 7 || b > 7 || c > 7) goto word;
        snprintf(buf, n, "%s v%d, v%d, v%d", m, a, b, c);
        return;
    case SHAPE_VVS:
        if (low14 || a > 7 || b > 7) goto word;
        snprintf(buf, n, "%s v%d, v%d, r%d", m, a, b, c);
        return;
    case SHAPE_SVV:
        if (low14 || b > 7 || c > 7) goto word;
        snprintf(buf, n, "%s r%d, v%d, v%d", m, a, b, c);
        return;
    }
word:
    snprintf(buf, n, ".word 0x%08X", w);
}
