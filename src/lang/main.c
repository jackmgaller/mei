/* meic: the Mei language compiler.
 *   meic game.akr [-o game.mei] [-S game.s] [--sym game.sym] [--title T] [--no-stdlib] [--release]
 *        [-g] [--trap-div] [--trap-fmul]   (run-time checks: see docs/LANGUAGE.md) 
 * The standard library is found through $MEI_STDLIB, else <dir of meic>/../stdlib. */
#define _DEFAULT_SOURCE 1
#define _XOPEN_SOURCE 700
#include "lang.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <unistd.h>

static void usage(void) {
    fprintf(stderr, "usage: meic game.akr [-o game.mei] [-S game.s] [--sym game.sym] [--title TITLE] [--no-stdlib] [--release]\n"
                    "            [-g] [--trap-div] [--trap-fmul]\n");
    exit(1);
}

/* Finds the executable: argv[0] if it contains a slash, else the first match on $PATH. */
static int find_exe(const char *argv0, char *out) {
    if (strchr(argv0, '/')) return realpath(argv0, out) != NULL;
    const char *path = getenv("PATH");
    while (path && *path) {
        const char *end = strchr(path, ':');
        size_t n = end ? (size_t)(end - path) : strlen(path);
        char cand[PATH_MAX];
        snprintf(cand, sizeof cand, "%.*s/%s", (int)n, path, argv0);
        if (access(cand, X_OK) == 0 && realpath(cand, out)) return 1;
        path = end ? end + 1 : NULL;
    }
    return 0;
}

static char *exe_stdlib_dir(const char *argv0) {
    char buf[PATH_MAX];
    if (!find_exe(argv0, buf)) snprintf(buf, sizeof buf, "%s", argv0);
    char *slash = strrchr(buf, '/');
    if (!slash) return strdup("../stdlib");
    *slash = 0;
    size_t n = strlen(buf) + 16;
    char *r = malloc(n);
    snprintf(r, n, "%s/../stdlib", buf);
    return r;
}

static int write_file(const char *path, const void *data, size_t len) {
    FILE *f = fopen(path, "wb");
    if (!f) { perror(path); return -1; }
    fwrite(data, 1, len, f);
    if (fclose(f) != 0) { perror(path); return -1; }
    return 0;
}

int main(int argc, char **argv) {
    const char *in = NULL, *out = NULL, *asm_out = NULL, *sym_out = NULL;
    MeiCompileOptions opt = {0};
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-o") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "-S") && i + 1 < argc) asm_out = argv[++i];
        else if (!strcmp(argv[i], "--sym") && i + 1 < argc) sym_out = argv[++i];
        else if (!strcmp(argv[i], "--title") && i + 1 < argc) opt.title = argv[++i];
        else if (!strcmp(argv[i], "--no-stdlib")) opt.no_stdlib = 1;
        else if (!strcmp(argv[i], "--release")) opt.no_asserts = 1;
        else if (!strcmp(argv[i], "-g")) opt.debug |= MEI_CHECK_BOUNDS;
        else if (!strcmp(argv[i], "--trap-div")) opt.debug |= MEI_CHECK_BOUNDS | MEI_CHECK_DIV;
        else if (!strcmp(argv[i], "--trap-fmul")) opt.debug |= MEI_CHECK_BOUNDS | MEI_CHECK_FMUL;
        else if (argv[i][0] == '-' ) usage();
        else if (!in) in = argv[i];
        else usage();
    }
    if (!in) usage();
    char *defout = NULL;
    if (!out) {
        size_t n = strlen(in);
        defout = malloc(n + 8);
        strcpy(defout, in);
        char *dot = strrchr(defout, '.');
        char *slash = strrchr(defout, '/');
        if (dot && (!slash || dot > slash)) *dot = 0;
        strcat(defout, ".mei");
        out = defout;
    }
    const char *env = getenv("MEI_STDLIB");
    char *dir = NULL;
    if (!env || !*env) { dir = exe_stdlib_dir(argv[0]); opt.stdlib_dir = dir; }
    char *text = NULL;
    if (asm_out) opt.asm_text = &text;
    char *warnings = NULL;
    opt.warnings = &warnings;
    MeiAsmResult res;
    char err[2048];
    int rc = meic_compile(in, &opt, &res, err, sizeof err);
    if (asm_out && text) write_file(asm_out, text, strlen(text));
    free(text);
    if (warnings) fprintf(stderr, "%s\n", warnings);
    free(warnings);
    if (rc != 0) {
        fprintf(stderr, "%s\n", err);
        return 1;
    }
    int status = 0;
    if (write_file(out, res.rom, res.rom_len) != 0) status = 1;
    if (sym_out) {
        FILE *f = fopen(sym_out, "w");
        if (!f) { perror(sym_out); status = 1; }
        else {
            for (size_t i = 0; i < res.symbol_count; i++) fprintf(f, "%06X %s\n", res.symbols[i].value, res.symbols[i].name);
            fclose(f);
        }
    }
    mei_asm_free(&res);
    free(dir);
    free(defout);
    return status;
}
