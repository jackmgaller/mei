/* Compiler-library integration: a virtual filesystem and repeated success/error recovery.
 * The normal language fixtures each start a fresh process; this catches stale compiler state. */
#include "lang.h"
#include "machine.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

int main(void) {
    uint8_t *reference = NULL;
    size_t reference_len = 0;
    Mei *machine = mei_create();
    CHECK(machine != NULL, "create virtual machine");
    if (!machine) return 1;
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
