/* Assembler and disassembler tests. Exit status is nonzero on any failure. */
#include "asm.h"
#include "isa.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int checks, failures;

#define CHECK(cond, ...) do { \
    checks++; \
    if (!(cond)) { failures++; printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); printf("\n"); } \
} while (0)

static uint32_t rd32(const MeiAsmResult *r, uint32_t addr) {
    uint32_t o = addr - 0x200000;
    if (o + 4 > r->rom_len) return 0xDEADBEEF;
    return r->rom[o] | r->rom[o + 1] << 8 | r->rom[o + 2] << 16 | (uint32_t)r->rom[o + 3] << 24;
}

static int assemble(const char *src, MeiAsmResult *r) {
    int rc = mei_assemble(src, "test.s", r);
    if (rc) printf("  (assembling \"%.60s\": %s)\n", src, r->error);
    return rc == 0;
}

/* Assembles src (at 0x200000) and compares the ROM with the expected words. */
static void expect_words_(const char *src, const uint32_t *w, size_t n, int line) {
    MeiAsmResult r;
    checks++;
    if (!assemble(src, &r)) { failures++; printf("FAIL line %d: assembly failed\n", line); return; }
    int bad = r.rom_len != n * 4;
    for (size_t i = 0; !bad && i < n; i++) bad = rd32(&r, 0x200000 + 4 * (uint32_t)i) != w[i];
    if (bad) {
        failures++;
        printf("FAIL line %d: \"%s\"\n  expected", line, src);
        for (size_t i = 0; i < n; i++) printf(" %08X", w[i]);
        printf("\n  got     ");
        for (size_t i = 0; i + 4 <= r.rom_len; i += 4) printf(" %08X", rd32(&r, 0x200000 + (uint32_t)i));
        printf(" (%zu bytes)\n", r.rom_len);
    }
    mei_asm_free(&r);
}
#define EXPECT(src, ...) do { const uint32_t w_[] = {__VA_ARGS__}; expect_words_(src, w_, sizeof w_ / 4, __LINE__); } while (0)

static void expect_error_(const char *src, const char *want, int line) {
    MeiAsmResult r;
    checks++;
    int rc = mei_assemble(src, "test.s", &r);
    if (rc == 0) { failures++; printf("FAIL line %d: \"%s\" assembled, expected error \"%s\"\n", line, src, want); mei_asm_free(&r); return; }
    if (!strstr(r.error, want)) { failures++; printf("FAIL line %d: error \"%s\" lacks \"%s\"\n", line, r.error, want); }
}
#define EXPECT_ERROR(src, want) expect_error_(src, want, __LINE__)

static uint32_t sym(const MeiAsmResult *r, const char *name) {
    uint32_t v = 0xDEADBEEF;
    if (!mei_asm_find_symbol(r, name, &v)) printf("  (symbol %s missing)\n", name);
    return v;
}

static void test_basics(void) {
    EXPECT("addi r1, r0, 5", 0x40400005);
    EXPECT("lui r1, 0x3FC0", MEI_ENC_U(OP_LUI, 1, 0x3FC0));
    CHECK((0x3FC0u << 10) == 0xFF0000u, "lui base");
    EXPECT("lui r1, hi(0xFF0000)", MEI_ENC_U(OP_LUI, 1, 0x3FC0));
    EXPECT("ADDI R1, R0, 5  ; case-insensitive mnemonics and registers", 0x40400005);
    EXPECT("addi sp, sp, -16 // C++ comment\n add ra, r0, r0", MEI_ENC_I(OP_ADDI, 14, 14, -16), MEI_ENC_R(OP_ADD, 15, 0, 0));
}

/* Every mnemonic in the table, with distinctive fields. */
static void test_every_mnemonic(void) {
    int count = 0;
    for (int op = 0; op < 64; op++) {
        const MeiOpInfo *in = &mei_ops[op];
        if (!in->mnemonic) continue;
        char src[128];
        uint32_t want = 0;
        const char *m = in->mnemonic;
        switch (in->shape) {
        case SHAPE_NONE: snprintf(src, sizeof src, "%s", m); want = MEI_ENC_J(op, 0); break;
        case SHAPE_SSS: snprintf(src, sizeof src, "%s r3, r5, r7", m); want = MEI_ENC_R(op, 3, 5, 7); break;
        case SHAPE_SSI:
            if (op == OP_ANDI || op == OP_ORI || op == OP_XORI) snprintf(src, sizeof src, "%s r3, r5, 0x2ABCD", m), want = MEI_ENC_I(op, 3, 5, 0x2ABCD);
            else if (op >= OP_SHLI && op <= OP_SARI) snprintf(src, sizeof src, "%s r3, r5, 13", m), want = MEI_ENC_I(op, 3, 5, 13);
            else snprintf(src, sizeof src, "%s r3, r5, -1234", m), want = MEI_ENC_I(op, 3, 5, -1234);
            break;
        case SHAPE_SU: snprintf(src, sizeof src, "%s r3, 0x12345", m); want = MEI_ENC_U(op, 3, 0x12345); break;
        case SHAPE_SMEM: snprintf(src, sizeof src, "%s r3, [r5-8]", m); want = MEI_ENC_I(op, 3, 5, -8); break;
        case SHAPE_BRANCH: snprintf(src, sizeof src, "%s r3, r5, 0x20002C", m); want = MEI_ENC_I(op, 3, 5, 10); break;
        case SHAPE_JUMP: snprintf(src, sizeof src, "%s 0x200400", m); want = MEI_ENC_J(op, 0x200400 >> 2); break;
        case SHAPE_JREG: snprintf(src, sizeof src, "%s r5", m); want = MEI_ENC_I(op, 0, 5, 0); break;
        case SHAPE_VMEM: snprintf(src, sizeof src, "%s v1, [r5+32]", m); want = MEI_ENC_I(op, 1, 5, 32); break;
        case SHAPE_VV: snprintf(src, sizeof src, "%s v1, v2", m); want = MEI_ENC_R(op, 1, 2, 0); break;
        case SHAPE_SVLANE: snprintf(src, sizeof src, "%s r3, v2, 3", m); want = MEI_ENC_I(op, 3, 2, 3); break;
        case SHAPE_VSLANE: snprintf(src, sizeof src, "%s v1, r5, 2", m); want = MEI_ENC_I(op, 1, 5, 2); break;
        case SHAPE_VVV: snprintf(src, sizeof src, "%s v1, v2, v6", m); want = MEI_ENC_R(op, 1, 2, 6); break;
        case SHAPE_VVS: snprintf(src, sizeof src, "%s v1, v2, r7", m); want = MEI_ENC_R(op, 1, 2, 7); break;
        case SHAPE_SVV: snprintf(src, sizeof src, "%s r3, v2, v6", m); want = MEI_ENC_R(op, 3, 2, 6); break;
        }
        EXPECT(src, want);
        count++;
    }
    CHECK(count == 59, "expected 59 mnemonics, table has %d", count);
}

static void test_shorthands(void) {
    EXPECT("nop", MEI_ENC_R(OP_ADD, 0, 0, 0));
    EXPECT("mov r4, r9", MEI_ENC_R(OP_ADD, 4, 9, 0));
    EXPECT("ret", MEI_ENC_I(OP_JR, 0, 15, 0));
    EXPECT("neg r2, r3", MEI_ENC_R(OP_SUB, 2, 0, 3));
    EXPECT("not r2, r3", MEI_ENC_R(OP_SUB, 2, 0, 3), MEI_ENC_I(OP_ADDI, 2, 2, -1));
    EXPECT("b 0x200100", MEI_ENC_J(OP_JMP, 0x200100 >> 2));
    EXPECT("bgt r1, r2, 0x200004", MEI_ENC_I(OP_BLT, 2, 1, 0));
    EXPECT("ble r1, r2, 0x200004", MEI_ENC_I(OP_BGE, 2, 1, 0));
    EXPECT("bgtu r1, r2, 0x200004", MEI_ENC_I(OP_BLTU, 2, 1, 0));
    EXPECT("bleu r1, r2, 0x200004", MEI_ENC_I(OP_BGEU, 2, 1, 0));
    EXPECT("beqz r6, 0x200000", MEI_ENC_I(OP_BEQ, 6, 0, -1));
    EXPECT("bnez r6, 0x200008", MEI_ENC_I(OP_BNE, 6, 0, 1));
    EXPECT("push r9", MEI_ENC_I(OP_ADDI, 14, 14, -4), MEI_ENC_I(OP_SW, 9, 14, 0));
    EXPECT("pop r9", MEI_ENC_I(OP_LW, 9, 14, 0), MEI_ENC_I(OP_ADDI, 14, 14, 4));
    EXPECT("la r1, 5", MEI_ENC_U(OP_LUI, 1, 0), MEI_ENC_I(OP_ORI, 1, 1, 5));
    /* li sizes */
    EXPECT("li r1, 5", MEI_ENC_I(OP_ADDI, 1, 0, 5));
    EXPECT("li r1, -131072", MEI_ENC_I(OP_ADDI, 1, 0, -131072));
    EXPECT("li r1, 131071", MEI_ENC_I(OP_ADDI, 1, 0, 131071));
    EXPECT("li r1, 131072", MEI_ENC_U(OP_LUI, 1, 128), MEI_ENC_I(OP_ORI, 1, 1, 0));
    EXPECT("li r1, 0xFF030C", MEI_ENC_U(OP_LUI, 1, 0x3FC0), MEI_ENC_I(OP_ORI, 1, 1, 0x30C));
    EXPECT("li r1, 0xFFFFFFFF", MEI_ENC_I(OP_ADDI, 1, 0, -1));
    EXPECT("li r1, -2147483648", MEI_ENC_U(OP_LUI, 1, 0x200000), MEI_ENC_I(OP_ORI, 1, 1, 0));
    EXPECT("li r1, 1.5", MEI_ENC_I(OP_ADDI, 1, 0, 98304));
    EXPECT("li r1, 2.5", MEI_ENC_U(OP_LUI, 1, 160), MEI_ENC_I(OP_ORI, 1, 1, 0));
    /* forward reference: always two words, even though the value turns out small */
    EXPECT("li r1, LATER\nhere: .word here\nLATER = 7",
           MEI_ENC_U(OP_LUI, 1, 0), MEI_ENC_I(OP_ORI, 1, 1, 7), 0x200008);
    EXPECT("li r2, end\nend:", MEI_ENC_U(OP_LUI, 2, 0x200008 >> 10), MEI_ENC_I(OP_ORI, 2, 2, 0x200008 & 0x3FF));
    EXPECT("K = 100\nli r1, K", MEI_ENC_I(OP_ADDI, 1, 0, 100));
}

static void test_branches_and_labels(void) {
    EXPECT("top: nop\n beq r1, r2, top\n bne r1, r2, fwd\n nop\nfwd: nop\n jmp top\n call fwd",
           MEI_ENC_R(OP_ADD, 0, 0, 0), MEI_ENC_I(OP_BEQ, 1, 2, -2), MEI_ENC_I(OP_BNE, 1, 2, 1),
           MEI_ENC_R(OP_ADD, 0, 0, 0), MEI_ENC_R(OP_ADD, 0, 0, 0),
           MEI_ENC_J(OP_JMP, 0x200000 >> 2), MEI_ENC_J(OP_CALL, 0x200010 >> 2));
    EXPECT("self: beq r0, r0, self", MEI_ENC_I(OP_BEQ, 0, 0, -1));
    EXPECT("beq r0, r0, .+4", MEI_ENC_I(OP_BEQ, 0, 0, 0));
    /* local labels: each global label opens a new scope */
    const char *src =
        "f1:  addi r1, r1, -1\n"
        ".loop: bnez r1, .loop\n"
        "     ret\n"
        "f2:\n"
        ".loop: addi r2, r2, -1 ; same name, different scope\n"
        "     bnez r2, .loop\n"
        "     beqz r0, f1.loop\n";
    EXPECT(src, MEI_ENC_I(OP_ADDI, 1, 1, -1), MEI_ENC_I(OP_BNE, 1, 0, -1), MEI_ENC_I(OP_JR, 0, 15, 0),
           MEI_ENC_I(OP_ADDI, 2, 2, -1), MEI_ENC_I(OP_BNE, 2, 0, -2), MEI_ENC_I(OP_BEQ, 0, 0, -5));
    MeiAsmResult r;
    if (assemble(src, &r)) {
        CHECK(sym(&r, "f1.loop") == 0x200004 && sym(&r, "f2.loop") == 0x20000C, "local label symbols");
        for (size_t i = 1; i < r.symbol_count; i++) CHECK(r.symbols[i - 1].value <= r.symbols[i].value, "symbols sorted");
        mei_asm_free(&r);
    }
    /* long branches at the edge of the range */
    EXPECT("beq r1, r2, 0x200004 + 131071*4", MEI_ENC_I(OP_BEQ, 1, 2, 131071));
    EXPECT("beq r1, r2, 0x200004 - 131072*4", MEI_ENC_I(OP_BEQ, 1, 2, -131072));
    EXPECT("x: lw r1, [r2]\n sw r1, [r3+x-0x200000+12]\n lb r1, [0x100]\n lbu r2, [-4]\n vld v7, [sp-16]",
           MEI_ENC_I(OP_LW, 1, 2, 0), MEI_ENC_I(OP_SW, 1, 3, 12), MEI_ENC_I(OP_LB, 1, 0, 0x100),
           MEI_ENC_I(OP_LBU, 2, 0, -4), MEI_ENC_I(OP_VLD, 7, 14, -16));
}

static void test_expressions(void) {
    EXPECT(".word 1+2*3, (1+2)*3, 1<<4|1, ~0, -5, 0x10 & 0x1F ^ 3, 7%4, 100/7, 10-2-3",
           7, 9, 17, 0xFFFFFFFF, (uint32_t)-5, 0x13, 3, 14, 5);
    EXPECT(".word 'A', '\\n', '\\'', '\\x41', 0b101, 0x1_0000, -8>>1, 1 << 31",
           65, 10, 39, 0x41, 5, 0x10000, (uint32_t)-4, 0x80000000);
    EXPECT(".word 1.5, -0.25, 0.1, 1.0, 3.14159, -1.5 * 2, 32767.99998",
           98304, (uint32_t)-16384, 6554, 65536, 205887, (uint32_t)-196608, 0x7FFFFFFF);
    EXPECT(".word hi(0xFF030C), lo(0xFF030C), hi(-1), .", 0x3FC0, 0x30C, 0x3FFFFF, 0x20000C);
    EXPECT("A = 3\nB = A * A + 1\n.equ C, B << 2\n.word A, B, C, D\nD = C + 1", 3, 10, 40, 41);
}

static void test_directives(void) {
    EXPECT(".byte 1, 2, 0xFF, -1\n.half 0x1234, -2\n.align 4\n.word 0xCAFEBABE",
           0xFFFF0201, 0xFFFE1234, 0xCAFEBABE);
    EXPECT(".ascii \"ab\"\n.asciz \"c\\n\"\n.byte \"x\", 0, 0", 0x0A636261, 0x7800);
    EXPECT(".space 3, 0xAA\n.byte 1\n.space 4", 0x01AAAAAA, 0);
    EXPECT(".word 1\n.org 0x20000C\n.word 2", 1, 0, 0, 2);
    EXPECT(".byte 1\n.align 8\n.word 2", 1, 0, 2);
    EXPECT(".fixed 1, 0.5, -1.25, 1/3, 2*1.5, -(0.5+0.25)",
           65536, 32768, (uint32_t)-81920, 21845, 196608, (uint32_t)-49152);

    MeiAsmResult r;
    const char *src =
        ".section ram\n"
        "counter: .space 4\n"
        ".align 16\n"
        "buf: .zero 100\n"
        ".section rom\n"
        "code: lw r1, [counter]\n"
        ".section ram\n"
        "after:\n"
        ".org 0x1000\n"
        "high: .space 8\n";
    if (assemble(src, &r)) {
        CHECK(sym(&r, "counter") == 0x100 && sym(&r, "buf") == 0x110 && sym(&r, "after") == 0x174 &&
              sym(&r, "high") == 0x1000 && sym(&r, "code") == 0x200000, "ram labels");
        CHECK(r.ram_used == 0x1008, "ram_used = 0x%X", r.ram_used);
        CHECK(r.rom_len == 4 && rd32(&r, 0x200000) == MEI_ENC_I(OP_LW, 1, 0, 0x100), "rom from ram section test");
        mei_asm_free(&r);
    }
    if (assemble("nop", &r)) { CHECK(r.ram_used == 0x100, "default ram_used"); mei_asm_free(&r); }

    /* .cart header */
    if (assemble(".cart \"Hello\", start\nstart: nop", &r)) {
        CHECK(r.rom_len == 60, "cart length %zu", r.rom_len);
        CHECK(rd32(&r, 0x200000) == MEI_ENC_J(OP_JMP, 0x200038 >> 2), "cart jmp");
        CHECK(!memcmp(r.rom + 4, "MEI1Hello\0\0", 11), "cart magic/title");
        int zero = 1;
        for (int i = 13; i < 56; i++) zero &= r.rom[i] == 0;
        CHECK(zero, "title NUL padded, no cart ID");
        mei_asm_free(&r);
    }
    if (assemble(".cart \"T\"\n.word 7", &r)) {
        CHECK(rd32(&r, 0x200000) == MEI_ENC_J(OP_JMP, 0x200038 >> 2) && rd32(&r, 0x200038) == 7, "cart default entry");
        mei_asm_free(&r);
    }
    /* cart IDs: bytes 40-55, NUL padded */
    if (assemble(".cart \"Lantern Lake\", start, \"LANTERN-LAKE\"\n.word 1\nstart: nop", &r)) {
        CHECK(rd32(&r, 0x200000) == MEI_ENC_J(OP_JMP, 0x20003C >> 2), "cart id: entry");
        CHECK(!memcmp(r.rom + 40, "LANTERN-LAKE\0\0\0\0", 16), "cart id bytes");
        CHECK(!memcmp(r.rom + 8, "Lantern Lake\0", 13), "cart id: title");
        mei_asm_free(&r);
    }
    if (assemble(".cart \"T\", , \"ABCDEFGHIJKLMNOP\"\n.word 7", &r)) {
        CHECK(rd32(&r, 0x200000) == MEI_ENC_J(OP_JMP, 0x200038 >> 2) && rd32(&r, 0x200038) == 7, "cart id, default entry");
        CHECK(!memcmp(r.rom + 40, "ABCDEFGHIJKLMNOP", 16), "16-character cart id");
        mei_asm_free(&r);
    }
    if (assemble(".cart \"T\", \"ID-1\"\n.word 7", &r)) {
        CHECK(rd32(&r, 0x200038) == 7 && !memcmp(r.rom + 40, "ID-1\0", 5), "cart id without entry");
        mei_asm_free(&r);
    }
    EXPECT_ERROR(".cart \"T\", , \"ABCDEFGHIJKLMNOPQ\"", "cart ID is longer than 16 characters");
    EXPECT_ERROR(".cart \"T\", , \"tab\there\"", "cart ID must be printable ASCII");
    EXPECT_ERROR(".cart \"T\", , \"\"", "the cart ID is empty");

    /* .include and .incbin, relative to the including file */
    if (system("mkdir -p build/tests/asmfiles")) {}
    FILE *f = fopen("build/tests/asmfiles/inc.s", "w");
    if (!f) { CHECK(0, "cannot create build/tests/asmfiles (run from the project root)"); return; }
    fputs("INCLUDED = 42\nincl: .word INCLUDED\n", f);
    fclose(f);
    f = fopen("build/tests/asmfiles/data.bin", "wb");
    fwrite("\x01\x02\x03\x04\x05\x06\x07\x08", 1, 8, f);
    fclose(f);
    const char *isrc = ".include \"inc.s\"\n.incbin \"data.bin\"\n.incbin \"data.bin\", 2, 4\n.incbin \"data.bin\", 6\n.word INCLUDED";
    if (mei_assemble(isrc, "build/tests/asmfiles/main.s", &r) == 0) {
        CHECK(r.rom_len == 22 && rd32(&r, 0x200000) == 42 && rd32(&r, 0x200004) == 0x04030201 &&
              rd32(&r, 0x200008) == 0x08070605 && rd32(&r, 0x20000C) == 0x06050403 &&
              rd32(&r, 0x200010) == 0x002A0807 && sym(&r, "incl") == 0x200000, "include/incbin");
        mei_asm_free(&r);
    } else {
        CHECK(0, "include/incbin: %s", r.error);
    }
    f = fopen("build/tests/asmfiles/bad.s", "w");
    fputs("nop\n\n  frob r1\n", f);
    fclose(f);
    if (mei_assemble("nop\n.include \"bad.s\"", "build/tests/asmfiles/main.s", &r) == 0) { CHECK(0, "bad include assembled"); mei_asm_free(&r); }
    else CHECK(!strcmp(r.error, "build/tests/asmfiles/bad.s:3: unknown instruction 'frob'"), "include error location: %s", r.error);

    /* listing */
    MeiAsmOptions o = {1};
    if (mei_assemble_opts("start: li r1, 0x123456 ; big\n.byte 1,2,3,4,5\n", "t.s", &o, &r) == 0) {
        CHECK(r.listing && strstr(r.listing, "200000  6040048D     start: li r1, 0x123456 ; big") &&
              strstr(r.listing, "200004  48440056") && strstr(r.listing, "200008  01 02 03 04"),
              "listing:\n%s", r.listing ? r.listing : "(null)");
        mei_asm_free(&r);
    }
}

static void test_errors(void) {
    EXPECT_ERROR("nop\nnop\nfoo r1", "test.s:3: unknown instruction 'foo'");
    EXPECT_ERROR("jmp nowhere", "test.s:1: undefined symbol 'nowhere'");
    EXPECT_ERROR("addi r1, r0, 131072", "immediate 131072 out of range");
    EXPECT_ERROR("addi r1, r0, -131073", "out of range");
    EXPECT_ERROR("andi r1, r1, -4", "unsigned immediate -4 out of range");
    EXPECT_ERROR("ori r1, r1, 0x40000", "out of range");
    EXPECT_ERROR("shli r1, r1, 32", "shift amount 32 out of range");
    EXPECT_ERROR("vget r1, v1, 4", "lane 4 out of range");
    EXPECT_ERROR("add r1, r2, r16", "bad scalar register 'r16'");
    EXPECT_ERROR("vadd v1, v2, v8", "bad vector register 'v8'");
    EXPECT_ERROR("vadd v1, v2, r3", "bad vector register 'r3'");
    EXPECT_ERROR("add r1, r2", "expected ','");
    EXPECT_ERROR("add r1, r2, r3, r4", "unexpected ', r4'");
    EXPECT_ERROR("beq r1, r2, 0x200002", "not word-aligned");
    EXPECT_ERROR("beq r1, r2, 0x200004 + 131072*4", "out of range");
    EXPECT_ERROR("jmp 0x200002", "not word-aligned");
    EXPECT_ERROR("jmp 0x10000000", "out of range");
    EXPECT_ERROR("lw r1, [0xFF0000]", "absolute address");
    EXPECT_ERROR("lw r1, [r2+0x20000]", "memory offset");
    EXPECT_ERROR("x: nop\nx: nop", "test.s:2: duplicate symbol 'x'");
    EXPECT_ERROR(".word 1/0", "division by zero");
    EXPECT_ERROR(".word 0x100000000", "number too large");
    EXPECT_ERROR(".byte 256", "value 256 out of range");
    EXPECT_ERROR(".foo", "unknown directive '.foo'");
    EXPECT_ERROR(".loop: nop", "has no preceding global label");
    EXPECT_ERROR("nop\n.cart \"x\"", ".cart must come first");
    EXPECT_ERROR(".cart \"0123456789012345678901234567890123\"", "longer than 32");
    EXPECT_ERROR(".section ram\n.word 1", "not allowed in the ram section");
    EXPECT_ERROR(".section ram\nnop", "not allowed in the ram section");
    EXPECT_ERROR(".section ram\n.space 4, 1", "fill value not allowed");
    EXPECT_ERROR(".word 1\n.org 0x200000", "moves backwards");
    EXPECT_ERROR(".space N\nN = 4", "must not depend on symbols defined later");
    EXPECT_ERROR(".byte 1\nnop", "misaligned");
    EXPECT_ERROR(".ascii \"abc", "unterminated string");
    EXPECT_ERROR(".include \"no-such-file.s\"", "cannot open");
    EXPECT_ERROR("r1 = 5", "register name");
    EXPECT_ERROR("addi r1, r0, r2", "register 'r2' not allowed in an expression");
    EXPECT_ERROR(".space 0x200001", "ROM is full");
    EXPECT_ERROR("li r1, 0x100000000", "number too large");
    EXPECT_ERROR("li r1, 0xFFFFFFFF + 1", "constant 4294967296 out of range");
}

/* Disassemble -> reassemble at the same pc must reproduce every word. */
static uint32_t rng = 0x12345678;
static uint32_t rnd(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }

static void roundtrip(const uint32_t *words, size_t n, const char *what) {
    size_t cap = n * 64 + 64, len = 0;
    char *src = malloc(cap);
    for (size_t i = 0; i < n; i++) {
        char line[64];
        mei_disasm(words[i], 0x200000 + 4 * (uint32_t)i, line, sizeof line);
        len += (size_t)snprintf(src + len, cap - len, "%s\n", line);
    }
    MeiAsmResult r;
    checks++;
    if (mei_assemble(src, "roundtrip.s", &r) != 0) {
        failures++;
        printf("FAIL roundtrip (%s): %s\n", what, r.error);
    } else {
        int bad = 0;
        for (size_t i = 0; i < n && bad < 5; i++) {
            uint32_t got = rd32(&r, 0x200000 + 4 * (uint32_t)i);
            if (got != words[i]) {
                char line[64];
                mei_disasm(words[i], 0x200000 + 4 * (uint32_t)i, line, sizeof line);
                printf("FAIL roundtrip (%s): %08X -> \"%s\" -> %08X\n", what, words[i], line, got);
                bad++;
            }
        }
        if (bad) failures++;
        mei_asm_free(&r);
    }
    free(src);
}

static void test_roundtrip(void) {
    enum { PER_OP = 200 };
    uint32_t *w = malloc(64 * PER_OP * sizeof *w);
    size_t n = 0;
    int as_word = 0;
    for (int op = 0; op < 64; op++) {
        const MeiOpInfo *in = &mei_ops[op];
        if (!in->mnemonic) continue;
        for (int k = 0; k < PER_OP; k++) {
            uint32_t a = rnd() & 15, b = rnd() & 15, c = rnd() & 15, va = a & 7, vb = b & 7, vc = c & 7;
            uint32_t imm = rnd(), x;
            switch (in->shape) {
            case SHAPE_NONE: x = MEI_ENC_J(op, k & 1 ? imm : 0); break;
            case SHAPE_SSS: x = MEI_ENC_R(op, a, b, k < 8 ? 0 : c); break;
            case SHAPE_SSI: x = MEI_ENC_I(op, a, b, op >= OP_SHLI && op <= OP_SARI ? imm & 31 : imm); break;
            case SHAPE_SU: x = MEI_ENC_U(op, a, imm); break;
            case SHAPE_SMEM: case SHAPE_BRANCH: x = MEI_ENC_I(op, a, b, imm); break;
            case SHAPE_JUMP: x = MEI_ENC_J(op, imm); break;
            case SHAPE_JREG: x = MEI_ENC_I(op, 0, b, 0); break;
            case SHAPE_VMEM: x = MEI_ENC_I(op, va, b, imm); break;
            case SHAPE_VV: x = MEI_ENC_R(op, va, vb, 0); break;
            case SHAPE_SVLANE: x = MEI_ENC_I(op, a, vb, imm & 3); break;
            case SHAPE_VSLANE: x = MEI_ENC_I(op, va, b, imm & 3); break;
            case SHAPE_VVV: x = MEI_ENC_R(op, va, vb, vc); break;
            case SHAPE_VVS: x = MEI_ENC_R(op, va, vb, c); break;
            default: x = MEI_ENC_R(op, a, vb, vc); break;
            }
            char line[64];
            mei_disasm(x, 0x200000 + 4 * (uint32_t)n, line, sizeof line);
            if (line[0] == '.') { as_word++; printf("  legal word %08X disassembled as %s\n", x, line); }
            w[n++] = x;
        }
    }
    CHECK(as_word == 0, "%d legal words came out as .word", as_word);
    roundtrip(w, n, "legal opcodes");
    free(w);

    enum { RANDOM = 100000 };
    w = malloc(RANDOM * sizeof *w);
    for (size_t i = 0; i < RANDOM; i++) w[i] = rnd();
    w[0] = 0, w[1] = 0xFFFFFFFF, w[2] = MEI_ENC_I(OP_JR, 3, 15, 0), w[3] = MEI_ENC_R(OP_ADD, 1, 2, 3) | 1;
    w[4] = MEI_ENC_I(OP_SHLI, 1, 1, 32), w[5] = MEI_ENC_R(OP_VMOV, 9, 1, 0), w[6] = MEI_ENC_I(OP_VGET, 1, 1, 4);
    roundtrip(w, RANDOM, "random words");
    char buf[64];
    mei_disasm(0xFFFFFFFF, 0x200000, buf, sizeof buf);
    CHECK(!strcmp(buf, ".word 0xFFFFFFFF"), "all-ones: %s", buf);
    mei_disasm(0x40400005, 0x200000, buf, sizeof buf);
    CHECK(!strcmp(buf, "addi r1, r0, 5"), "worked example disasm: %s", buf);
    mei_disasm(MEI_ENC_I(OP_BEQ, 1, 2, 3), 0x200000, buf, sizeof buf);
    CHECK(!strcmp(buf, "beq r1, r2, 0x200010"), "branch disasm: %s", buf);
    mei_disasm(MEI_ENC_I(OP_SW, 3, 14, -8), 0x200000, buf, sizeof buf);
    CHECK(!strcmp(buf, "sw r3, [r14-8]"), "mem disasm: %s", buf);
    free(w);
}

int main(void) {
    test_basics();
    test_every_mnemonic();
    test_shorthands();
    test_branches_and_labels();
    test_expressions();
    test_directives();
    test_errors();
    test_roundtrip();
    printf("test_asm: %d checks, %d failures\n", checks, failures);
    return failures != 0;
}
