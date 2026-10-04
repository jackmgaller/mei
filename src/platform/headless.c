/* Headless runner for tests and debugging.
 *   mei-headless cart.mei [--frames N] [--dump out.ppm] [--pad1 HEX] [--input F:HEX,F:HEX...]
 *                [--wav out.wav] [--system-carts DIR] [--config HEX] [--time HH:MM[:SS]]
 *                [--date YYYY-MM-DD] [--card1 FILE] [--card2 FILE] [--quiet]
 *                [--dump-every N PREFIX] [--dump-from F] [--gpu-stats out.csv]
 * Prints the cart's debug console to stdout. Exit status: 0 ok, 2 fault, 1 usage/IO error.
 * --input changes controller 1's buttons from frame F on (e.g. 0:0,120:400,124:0).
 * --system-carts treats the cart as the system ROM and appends a catalogue of the .mei files in DIR;
 * SYS_LAUNCH requests then load the chosen cart, as the real front ends do.
 * The clock is simulated for determinism: it starts at --time/--date (default 12:00:00 on
 * 2026-01-01) and advances one second every 60 ticks (wrapping at midnight, date fixed).
 * --card1/--card2 insert memory card files (blank if missing), saved back at exit if changed.
 * With --system-carts the system ROM gets the system card commands until a cart launches.
 * --dump-every N PREFIX also writes the screen every N ticks (from tick --dump-from F, default 0)
 * to PREFIX_00012.ppm etc. (the tick number), for frame sequences and contact sheets.
 * --gpu-stats writes one CSV row per presented frame: CPU cycles, triangles, pixels filled
 * by kind (flat/Gouraud x untextured/textured x opaque/semi-transparent), the modelled GPU
 * cycles (docs/DECISIONS.md, "GPU budget"), the ticks the frame took (1 = on time) and how
 * many of them it waited for the GPU (gpu_lag), then the depth and perspective work
 * (docs/RENDERING.md): pixels depth-tested and of those failed, GPU_ZCLEARs, triangles charged
 * the reciprocal setup, pixels drawn perspective-correct and perspective divides.
 * tools/mei_gpustats.py summarises them.
 * --broadcast FILE replays a recorded broadcast (docs/BROADCAST.md) at exactly 16 bytes per tick
 * from tick 0, with the carrier on until the file ends; --broadcast-noise BER adds bit errors
 * (deterministic: errors per million bits, seed 0x4D454E4F). */
#include "mei.h"
#include "sysboot.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void debug_out(void *user, char c) { fputc(c, stdout); }

static int write_ppm(const char *path, const uint16_t *px) {
    FILE *f = fopen(path, "wb");
    if (!f) return -1;
    fprintf(f, "P6\n%d %d\n255\n", MEI_W, MEI_H);
    for (int i = 0; i < MEI_W * MEI_H; i++) {
        uint16_t p = px[i];
        unsigned char rgb[3] = {
            (unsigned char)(((p & 31) << 3) | ((p & 31) >> 2)),
            (unsigned char)((((p >> 5) & 31) << 3) | (((p >> 5) & 31) >> 2)),
            (unsigned char)((((p >> 10) & 31) << 3) | (((p >> 10) & 31) >> 2)),
        };
        fwrite(rgb, 1, 3, f);
    }
    fclose(f);
    return 0;
}

static void put32(FILE *f, uint32_t v) { fputc(v & 255, f); fputc(v >> 8 & 255, f); fputc(v >> 16 & 255, f); fputc(v >> 24 & 255, f); }
static void put16(FILE *f, uint32_t v) { fputc(v & 255, f); fputc(v >> 8 & 255, f); }

static void wav_header(FILE *f, uint32_t frames) {
    fseek(f, 0, SEEK_SET);
    fwrite("RIFF", 1, 4, f); put32(f, 36 + frames * 4); fwrite("WAVEfmt ", 1, 8, f);
    put32(f, 16); put16(f, 1); put16(f, 2); put32(f, MEI_AUDIO_RATE); put32(f, MEI_AUDIO_RATE * 4);
    put16(f, 4); put16(f, 16); fwrite("data", 1, 4, f); put32(f, frames * 4);
}

/* Reads up to one byte more than the largest cart, so mei_load_cart rejects an oversized one. */
static uint8_t *read_file(const char *path, size_t *len) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);
    size_t n = size < 0 ? 0 : size > (long)MEI_ROM_MAX ? MEI_ROM_MAX + 1 : (size_t)size;
    uint8_t *buf = malloc(n ? n : 1);
    *len = buf ? fread(buf, 1, n, f) : 0;
    fclose(f);
    return buf;
}

#define MAX_EVENTS 256

static int weekday(int y, int m, int d) {   /* 0 = Sunday (Sakamoto) */
    static const int t[] = {0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4};
    if (m < 3) y -= 1;
    return (y + y / 4 - y / 100 + y / 400 + t[m - 1] + d) % 7;
}

int main(int argc, char **argv) {
    const char *cart = NULL, *dump = NULL, *wav = NULL, *sysdir = NULL, *seq = NULL, *gstats_path = NULL;
    const char *bc_path = NULL;
    double bc_noise = 0;
    long frames = 1, seq_every = 0, seq_from = 0;
    unsigned pad1 = 0, config = 0;
    int quiet = 0, have_config = 0, nev = 0;
    int year = 2026, month = 1, day = 1, hh = 12, mm = 0, ss = 0;
    const char *card_path[2] = {NULL, NULL};
    static uint8_t card_img[2][MEI_CARD_SIZE];
    struct { long frame; unsigned buttons; } ev[MAX_EVENTS];
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--frames") && i + 1 < argc) frames = strtol(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "--dump") && i + 1 < argc) dump = argv[++i];
        else if (!strcmp(argv[i], "--wav") && i + 1 < argc) wav = argv[++i];
        else if (!strcmp(argv[i], "--pad1") && i + 1 < argc) pad1 = (unsigned)strtoul(argv[++i], NULL, 16);
        else if (!strcmp(argv[i], "--system-carts") && i + 1 < argc) sysdir = argv[++i];
        else if (!strcmp(argv[i], "--config") && i + 1 < argc) { config = (unsigned)strtoul(argv[++i], NULL, 16); have_config = 1; }
        else if (!strcmp(argv[i], "--input") && i + 1 < argc) {
            for (char *s = argv[++i]; *s && nev < MAX_EVENTS; ) {
                ev[nev].frame = strtol(s, &s, 10);
                if (*s == ':') s++;
                ev[nev++].buttons = (unsigned)strtoul(s, &s, 16);
                if (*s == ',') s++;
            }
        }
        else if (!strcmp(argv[i], "--time") && i + 1 < argc) sscanf(argv[++i], "%d:%d:%d", &hh, &mm, &ss);
        else if (!strcmp(argv[i], "--date") && i + 1 < argc) sscanf(argv[++i], "%d-%d-%d", &year, &month, &day);
        else if (!strcmp(argv[i], "--card1") && i + 1 < argc) card_path[0] = argv[++i];
        else if (!strcmp(argv[i], "--card2") && i + 1 < argc) card_path[1] = argv[++i];
        else if (!strcmp(argv[i], "--quiet")) quiet = 1;
        else if (!strcmp(argv[i], "--dump-every") && i + 2 < argc) { seq_every = strtol(argv[++i], NULL, 0); seq = argv[++i]; }
        else if (!strcmp(argv[i], "--dump-from") && i + 1 < argc) seq_from = strtol(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "--gpu-stats") && i + 1 < argc) gstats_path = argv[++i];
        else if (!strcmp(argv[i], "--broadcast") && i + 1 < argc) bc_path = argv[++i];
        else if (!strcmp(argv[i], "--broadcast-noise") && i + 1 < argc) bc_noise = strtod(argv[++i], NULL);
        else if (argv[i][0] != '-' && !cart) cart = argv[i];
        else { cart = NULL; break; }
    }
    if (!cart) {
        fprintf(stderr, "usage: mei-headless cart.mei [--frames N] [--dump out.ppm] [--pad1 HEX] [--input F:HEX,...]\n"
                        "                    [--wav out.wav] [--system-carts DIR] [--config HEX]\n"
                        "                    [--time HH:MM[:SS]] [--date YYYY-MM-DD] [--card1 FILE] [--card2 FILE]\n"
                        "                    [--quiet] [--dump-every N PREFIX] [--dump-from F]\n"
                        "                    [--gpu-stats out.csv] [--broadcast FILE] [--broadcast-noise BER]\n");
        return 1;
    }

    size_t len;
    uint8_t *data = read_file(cart, &len);
    if (!data) { perror(cart); return 1; }

    static SysCatalogue cat;
    if (sysdir) {
        const char *base = strrchr(cart, '/');
        sys_scan_dir(&cat, sysdir, base ? base + 1 : cart);
        size_t img_len;
        uint8_t *img = sys_build_image(data, len, &cat, SYS_NO_AUTOBOOT, 0, "headless", &img_len);
        if (!img) { fprintf(stderr, "%s: system ROM larger than 0x%X bytes\n", cart, SYS_ROM_MAX); return 1; }
        free(data);
        data = img;
        len = img_len;
    }

    Mei *m = mei_create();
    if (!quiet) mei_set_debug_output(m, debug_out, NULL);
    if (have_config) mei_set_config(m, config);
    long start_secs = hh * 3600L + mm * 60L + ss;
    int wd = weekday(year, month, day);
    mei_set_clock(m, year, month, day, wd, hh, mm, ss);
    for (int s = 0; s < 2; s++) {
        if (!card_path[s]) continue;
        FILE *cf = fopen(card_path[s], "rb");
        if (cf) { fread(card_img[s], 1, MEI_CARD_SIZE, cf); fclose(cf); }
        mei_card_insert(m, s, card_img[s]);
    }
    uint8_t *bc = NULL;
    long bc_len = 0;
    if (bc_path) {
        FILE *bf = fopen(bc_path, "rb");
        if (!bf) { perror(bc_path); return 1; }
        fseek(bf, 0, SEEK_END);
        bc_len = ftell(bf);
        fseek(bf, 0, SEEK_SET);
        bc = malloc(bc_len > 0 ? (size_t)bc_len : 1);
        if (bc_len > 0 && fread(bc, 1, (size_t)bc_len, bf) != (size_t)bc_len) { perror(bc_path); return 1; }
        fclose(bf);
    }
    if (bc_noise > 0) mei_broadcast_noise(m, (uint32_t)(bc_noise * 1e6 + 0.5), 0);
    if (mei_load_cart(m, data, len) != 0) { fprintf(stderr, "%s: not a valid cart (%zu bytes)\n", cart, len); return 1; }
    if (sysdir) mei_set_privileged(m, 1);

    FILE *wf = NULL;
    uint32_t wav_frames = 0;
    if (wav) {
        wf = fopen(wav, "wb");
        if (!wf) { perror(wav); return 1; }
        wav_header(wf, 0);
    }

    FILE *gs = NULL;
    if (gstats_path) {
        gs = fopen(gstats_path, "w");
        if (!gs) { perror(gstats_path); return 1; }
        fprintf(gs, "tick,cpu_cycles,tris,tris_empty,tris_dropped,clears,lists,"
                    "px_flat,px_gouraud,px_tex,px_tex_gouraud,px_semi_flat,px_semi_gouraud,px_semi_tex,px_semi_tex_gouraud,"
                    "gpu_cycles,ticks,gpu_lag,px_ztest,px_zfail,zclears,tris_recip,px_persp,persp_divs\n");
    }
    MeiPadInput in = {pad1, 0, 0};
    long presented = 0;
    for (long i = 0; i < frames; i++) {
        for (int e = 0; e < nev; e++) if (ev[e].frame == i) in.buttons = ev[e].buttons;
        mei_set_pad(m, 0, &in);
        long now = (start_secs + i / 60) % 86400;
        mei_set_clock(m, year, month, day, wd, (int)(now / 3600), (int)(now / 60 % 60), (int)(now % 60));
        if (bc) {
            long at = i * MEI_BC_BYTES_PER_TICK;
            mei_broadcast_carrier(m, at < bc_len);
            if (at < bc_len) mei_broadcast_feed(m, bc + at, (int)(bc_len - at < MEI_BC_BYTES_PER_TICK ? bc_len - at : MEI_BC_BYTES_PER_TICK));
        }
        int shown = mei_run_frame(m);
        presented += shown;
        if (gs && shown) {
            const MeiGpuStats *g = mei_gpu_stats(m);
            fprintf(gs, "%ld,%u,%u,%u,%u,%u,%u", i, g->cpu_cycles, g->tris, g->tris_empty, g->tris_dropped, g->clears, g->lists);
            for (int k = 0; k < 8; k++) fprintf(gs, ",%u", g->px[k]);
            fprintf(gs, ",%u,%u,%u", g->gpu_cycles, g->ticks, g->gpu_lag);
            fprintf(gs, ",%u,%u,%u,%u,%u,%u\n", g->px_ztest, g->px_zfail, g->zclears, g->tris_recip, g->px_persp, g->persp_divs);
        }
        if (wf) {
            const int16_t *s;
            int n = mei_audio(m, &s);
            for (int k = 0; k < n * 2; k++) put16(wf, (uint16_t)s[k]);
            wav_frames += (uint32_t)n;
        }
        if (seq && seq_every > 0 && i >= seq_from && (i - seq_from) % seq_every == 0) {
            char fn[1024];
            snprintf(fn, sizeof fn, "%s_%05ld.ppm", seq, i);
            if (write_ppm(fn, mei_display(m)) != 0) { perror(fn); return 1; }
        }
        if (mei_fault(m)->kind) break;
        uint32_t idx;
        if (mei_launch_request(m, &idx)) {
            if (!sysdir || idx >= (uint32_t)cat.count) { fprintf(stderr, "frame %ld: SYS_LAUNCH %u ignored\n", i, idx); continue; }
            size_t clen;
            uint8_t *c = read_file(cat.carts[idx].path, &clen);
            if (!quiet) fprintf(stderr, "frame %ld: launching %s\n", i, cat.carts[idx].path);
            if (!c || mei_load_cart(m, c, clen) != 0) { fprintf(stderr, "can't load %s\n", cat.carts[idx].path); return 1; }
            free(c);
        }
    }
    fflush(stdout);
    for (int s = 0; s < 2; s++) {
        if (!card_path[s] || !mei_card_dirty(m, s)) continue;
        FILE *cf = fopen(card_path[s], "wb");
        if (!cf || fwrite(card_img[s], 1, MEI_CARD_SIZE, cf) != MEI_CARD_SIZE) { perror(card_path[s]); return 1; }
        fclose(cf);
        if (!quiet) fprintf(stderr, "saved %s\n", card_path[s]);
    }
    if (wf) { wav_header(wf, wav_frames); fclose(wf); }
    if (gs) fclose(gs);
    if (dump && write_ppm(dump, mei_display(m)) != 0) { perror(dump); return 1; }

    const MeiFault *fl = mei_fault(m);
    if (fl->kind) {
        fprintf(stderr, "fault: %s at pc=0x%08X addr=0x%08X\n", mei_fault_name(fl->kind), fl->pc, fl->addr);
        return 2;
    }
    int dirty;
    uint32_t cfg = mei_config(m, &dirty);
    if (!quiet) fprintf(stderr, "ran %ld ticks, %ld presented\n", frames, presented);
    if (!quiet && (dirty || have_config)) fprintf(stderr, "SYS_CONFIG = 0x%08X\n", cfg);
    mei_destroy(m);
    return 0;
}
