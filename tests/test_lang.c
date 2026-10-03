/* Compiler-library integration: a virtual filesystem and repeated success/error recovery.
 * The normal language fixtures each start a fresh process; this catches stale compiler state.
 * Also large ROM data: a 40 MB embed (made here, not committed) and the ROM limit errors. */
#define _POSIX_C_SOURCE 200809L
#define _DARWIN_C_SOURCE   /* ru_maxrss on macOS */
#include "lang.h"
#include "machine.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/resource.h>
#include <time.h>

static int checks, failures;
#define CHECK(condition, ...) do { checks++; if (!(condition)) { failures++; \
    printf("FAIL %s:%d: ", __FILE__, __LINE__); printf(__VA_ARGS__); putchar('\n'); } } while (0)

static const char module_source[] =
    "struct Cell { amount: fixed16, flags: bits { ready, a, b, c, d, e, f, g, high } }\n"
    "var calls: s32\n"
    "const LABELS: [2]*u8 = [\"one\", \"two\"]\n"
    "private fn secret() -> s32 { return 1234 }\n"
    "fn tick(cell: *Cell) { cell.amount += 0.25; cell.flags.ready = false; calls += 1 }\n";
static const char good_source[] =
    "import \"cells.akr\" as m\n"
    "import \"./cells.akr\" as second\n"
    "var answer: s32\n"
    "var values: [3]fixed16\n"
    "fn total(xs: []const fixed16) -> s32 {\n"
    "    var result: s32\n"
    "    for i in 0..len(xs) { result += bits(xs[i]) }\n"
    "    return result\n"
    "}\n"
    "fn init() {\n"
    "    var cell = m.Cell { amount: 1.5, flags: bits { ready: true, high: true } }\n"
    "    (&cell).tick()\n"
    "    values[0] = cell.amount\n"
    "    values[1] = -0.5\n"
    "    answer = values.total() + m.calls + second.calls\n"
    "    if cell.flags.ready || !cell.flags.high { answer = -1 }\n"
    "    if m.LABELS[0][0] != 'o' || second.LABELS[1][0] != 't' { answer = -2 }\n"
    "}\n";
static const char bad_source[] =
    "import \"cells.akr\" as m\n"
    "fn init() { m.secret() }\n";

typedef struct { int bad; int reads; } Files;
static int read_virtual(void *user, const char *path, char **data, size_t *len) {
    Files *files = user;
    files->reads++;
    const char *text;
    if (!strcmp(path, "virtual/main.akr")) text = files->bad ? bad_source : good_source;
    else if (!strcmp(path, "virtual/cells.akr")) text = module_source;
    else return -1;
    *len = strlen(text);
    *data = malloc(*len);
    if (!*data) return -1;
    memcpy(*data, text, *len);
    return 0;
}

/* ---- large ROM data ---- */

#define WORLD_SIZE (40u << 20)
static uint8_t world_byte(uint32_t i) { return (uint8_t)(i ^ (i >> 8) ^ (i >> 16) ^ (i >> 24)); }

static const char *big_source;
static int read_big(void *user, const char *path, char **data, size_t *len) {
    (void)user;
    size_t n;
    if (!strcmp(path, "big/main.akr")) {
        *len = strlen(big_source);
        if (!(*data = malloc(*len))) return -1;
        memcpy(*data, big_source, *len);
        return 0;
    }
    if (!strcmp(path, "big/world.bin")) n = WORLD_SIZE;
    else if (!strcmp(path, "big/huge.bin")) n = MEI_ROM_MAX + 1;   /* zeros */
    else return -1;
    if (!(*data = calloc(n, 1))) return -1;
    if (n == WORLD_SIZE) for (uint32_t i = 0; i < n; i++) (*data)[i] = (char)world_byte(i);
    *len = n;
    return 0;
}

static double peak_mb(void) {
    struct rusage u;
    getrusage(RUSAGE_SELF, &u);
#ifdef __APPLE__
    return u.ru_maxrss / 1048576.0;   /* bytes */
#else
    return u.ru_maxrss / 1024.0;      /* kilobytes */
#endif
}

static double now_s(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec + t.tv_nsec / 1e9;
}

static uint32_t ram32(Mei *m, uint32_t a) {
    const uint8_t *p = m->ram + a;
    return p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
}

static void test_big_data(Mei *machine) {
    char error[2048];
    MeiCompileOptions options = {.no_stdlib = 1, .read_file = read_big};
    MeiAsmResult result;

    /* a 40 MB embed (and two ranges of the same file): compile time and memory in proportion
       to the file. Memory is the file as read plus the 43 MB ROM image, about 83 MB; with the
       embed written out as .word text it was about 2.3 s and 200 MB more. */
    big_source =
        "embed WORLD: u8 = \"world.bin\"\n"
        "embed TYPED: [3000000]u8 = \"world.bin\", 38943040\n"   /* over 2 MB: ROM data, no RAM limit */
        "embed TAIL: u32 = \"world.bin\", 41943036, 4\n"
        "var got: [4]u32\n"
        "fn init() {\n"
        "    var i = 41943000\n"
        "    while i < 41943039 { i += 1 }\n"
        "    got[0] = WORLD[41943039] as u32\n"
        "    got[1] = WORLD[i - 1000000] as u32\n"
        "    got[2] = TAIL[0]\n"
        "    got[3] = TYPED[0][i - 38943047] as u32\n"
        "}\n";
    double mem0 = peak_mb(), t0 = now_s();
    int rc = meic_compile("big/main.akr", &options, &result, error, sizeof error);
    double secs = now_s() - t0, grew = peak_mb() - mem0;
    CHECK(rc == 0, "40 MB embed compiles: %s", error);
    if (rc == 0) {
        printf("test_lang: 40 MB embed compiled in %.3f s, peak memory grew %.0f MB\n", secs, grew);
        CHECK(secs < 1.0, "40 MB embed: %.3f s, expected under 1 s", secs);
        CHECK(grew < 100.0, "40 MB embed: memory grew %.0f MB, expected under 100 MB", grew);
        CHECK(result.rom_len > (size_t)WORLD_SIZE + 3000004, "all three embeds in the ROM: %zu bytes", result.rom_len);
        uint32_t got = 0;
        int found = mei_asm_find_symbol(&result, "G_got", &got);
        CHECK(found, "G_got in the symbols");
        CHECK(mei_load_cart(machine, result.rom, result.rom_len) == 0, "load the 40 MB embed cart");
        mei_run_frame(machine);
        CHECK(mei_fault(machine)->kind == MEI_FAULT_NONE, "the 40 MB embed cart must not fault");
        if (found) {
            uint32_t last = WORLD_SIZE - 1;
            CHECK(ram32(machine, got) == world_byte(last), "last byte: %u", ram32(machine, got));
            CHECK(ram32(machine, got + 4) == world_byte(last - 1000000), "far byte: %u", ram32(machine, got + 4));
            uint32_t tail = world_byte(last - 3) | world_byte(last - 2) << 8 | world_byte(last - 1) << 16 |
                            (uint32_t)world_byte(last) << 24;
            CHECK(ram32(machine, got + 8) == tail, "last word of a ranged embed: %08X", ram32(machine, got + 8));
            CHECK(ram32(machine, got + 12) == world_byte(last - 7), "typed embed: %u", ram32(machine, got + 12));
        }
    }
    mei_asm_free(&result);

    /* the cart ROM limit: one embed over it, and embeds that only together are */
    big_source = "embed HUGE: u8 = \"huge.bin\"\nfn init() { let x = HUGE[0] }\n";
    CHECK(meic_compile("big/main.akr", &options, &result, error, sizeof error) == -1 &&
          strstr(error, "embed 'HUGE' is 67108865 bytes, more than the 64 MB cart ROM limit"), "embed over the ROM: %s", error);
    mei_asm_free(&result);
    big_source = "embed A: u8 = \"world.bin\"\nembed B: u8 = \"world.bin\", 0, 30000000\n"
                 "fn init() { let x = A[0] + B[0] }\n";
    CHECK(meic_compile("big/main.akr", &options, &result, error, sizeof error) == -1 &&
          strstr(error, "error: the cart is larger than the 64 MB cart ROM limit"), "embeds over the ROM: %s", error);
    mei_asm_free(&result);
}

int main(void) {
    uint8_t *reference = NULL;
    size_t reference_len = 0;
    Mei *machine = mei_create();
    CHECK(machine != NULL, "create virtual machine");
    if (!machine) return 1;
    test_big_data(machine);
    for (int round = 0; round < 32; round++) {
        Files files = {.bad = 1};
        char error[2048], *assembly = NULL, *warnings = NULL;
        MeiCompileOptions options = {.no_stdlib = 1, .read_file = read_virtual, .user = &files,
                                      .asm_text = &assembly, .warnings = &warnings};
        MeiAsmResult result;
        CHECK(meic_compile("virtual/main.akr", &options, &result, error, sizeof error) == -1,
              "round %d: private access must fail", round);
        CHECK(strstr(error, "private") != NULL, "round %d: diagnostic: %s", round, error);
        mei_asm_free(&result); free(assembly); free(warnings);
        assembly = warnings = NULL;
        files.bad = 0; files.reads = 0;
        int rc = meic_compile("virtual/main.akr", &options, &result, error, sizeof error);
        CHECK(rc == 0, "round %d: recovery compile: %s", round, error);
        if (rc != 0) { mei_asm_free(&result); free(assembly); free(warnings); continue; }
        CHECK(files.reads >= 2, "round %d: file-reader callback invoked", round);
        CHECK(assembly != NULL && warnings == NULL, "round %d: assembly/warning outputs", round);
        if (!reference) {
            reference_len = result.rom_len;
            reference = malloc(reference_len);
            CHECK(reference != NULL, "save reference ROM");
            if (reference) memcpy(reference, result.rom, reference_len);
        } else {
            CHECK(result.rom_len == reference_len && memcmp(result.rom, reference, reference_len) == 0,
                  "round %d: module/type state must reset to identical ROM", round);
        }
        uint32_t answer = 0;
        int found = mei_asm_find_symbol(&result, "G_answer", &answer);
        CHECK(found && answer <= RAM_SIZE - 4, "round %d: result global in RAM", round);
        CHECK(mei_load_cart(machine, result.rom, result.rom_len) == 0, "round %d: load ROM", round);
        mei_run_frame(machine);
        CHECK(mei_fault(machine)->kind == MEI_FAULT_NONE, "round %d: execution must not fault", round);
        if (found && answer <= RAM_SIZE - 4) {
            const uint8_t *p = machine->ram + answer;
            uint32_t value = p[0] | (uint32_t)p[1] << 8 | (uint32_t)p[2] << 16 | (uint32_t)p[3] << 24;
            CHECK(value == 5122, "round %d: all five features/shared module state: %u", round, value);
        }
        mei_asm_free(&result); free(assembly); free(warnings);
    }
    free(reference);
    mei_destroy(machine);
    printf("test_lang: %d checks, %d failures\n", checks, failures);
    return failures != 0;
}
