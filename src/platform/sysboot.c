#include "sysboot.h"

#include <stdlib.h>
#include <string.h>
#ifndef __EMSCRIPTEN__
#include <dirent.h>
#include <stdio.h>
#endif

static void wr32le(uint8_t *p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24); }

void sys_cart_title(const uint8_t *data, size_t len, const char *fallback, char out[32]) {
    memset(out, 0, 32);
    if (len >= 40 && memcmp(data + 4, "MEI1", 4) == 0 && data[8]) {
        memcpy(out, data + 8, 31);
        return;
    }
    /* file name without directory or extension */
    const char *base = strrchr(fallback, '/');
    base = base ? base + 1 : fallback;
    size_t n = strcspn(base, ".");
    if (n > 31) n = 31;
    memcpy(out, base, n);
}

int sys_add(SysCatalogue *c, const char *title, uint32_t size, const char *path) {
    if (c->count >= SYS_MAX_CARTS) return -1;
    SysCart *e = &c->carts[c->count];
    memset(e, 0, sizeof *e);
    strncpy(e->title, title, sizeof e->title - 1);
    e->size = size;
    strncpy(e->path, path, sizeof e->path - 1);
    return c->count++;
}

int sys_find_path(const SysCatalogue *c, const char *path) {
    for (int i = 0; i < c->count; i++)
        if (strcmp(c->carts[i].path, path) == 0) return i;
    return -1;
}

#ifndef __EMSCRIPTEN__
static int by_title(const void *a, const void *b) { return strcmp(((const SysCart *)a)->title, ((const SysCart *)b)->title); }

int sys_scan_dir(SysCatalogue *c, const char *dir, const char *skip) {
    DIR *d = opendir(dir);
    if (!d) return 0;
    int first = c->count;
    struct dirent *ent;
    while ((ent = readdir(d))) {
        size_t n = strlen(ent->d_name);
        if (n < 5 || strcmp(ent->d_name + n - 4, ".mei") != 0) continue;
        if (skip && strcmp(ent->d_name, skip) == 0) continue;
        char path[512];
        snprintf(path, sizeof path, "%s/%s", dir, ent->d_name);
        FILE *f = fopen(path, "rb");
        if (!f) continue;
        uint8_t head[40] = {0};
        size_t got = fread(head, 1, sizeof head, f);
        fseek(f, 0, SEEK_END);
        long size = ftell(f);
        fclose(f);
        if (size <= 0 || size > MEI_ROM_MAX) continue;
        char title[32];
        sys_cart_title(head, got, ent->d_name, title);
        if (sys_add(c, title, (uint32_t)size, path) < 0) break;
    }
    closedir(d);
    qsort(c->carts + first, (size_t)(c->count - first), sizeof(SysCart), by_title);
    return c->count - first;
}
#endif

uint8_t *sys_build_image(const uint8_t *rom, size_t len, const SysCatalogue *c,
                         uint32_t autoboot, uint32_t flags, const char *platform, size_t *out_len) {
    if (len > SYS_ROM_MAX) return NULL;
    size_t total = SYS_IMAGE_SIZE;
    uint8_t *img = calloc(1, total);
    if (!img) return NULL;
    memcpy(img, rom, len);
    uint8_t *cat = img + (SYS_CATALOGUE_ADDR - MEI_ROM_BASE);
    int n = c ? c->count : 0;
    memcpy(cat, "CATL", 4);
    wr32le(cat + 4, (uint32_t)n);
    wr32le(cat + 8, autoboot);
    wr32le(cat + 12, flags);
    if (platform) strncpy((char *)cat + 16, platform, 15);
    for (int i = 0; i < n; i++) {
        uint8_t *e = cat + 32 + i * 64;
        memcpy(e, c->carts[i].title, 32);
        wr32le(e + 32, c->carts[i].size);
    }
    *out_len = total;
    return img;
}
