/* Booting the system ROM: building the cart catalogue it reads at 0x3F0000
 * (see docs/SYSTEM.md). Shared by the desktop, web and headless front ends. */
#ifndef MEI_SYSBOOT_H
#define MEI_SYSBOOT_H

#include <stddef.h>
#include <stdint.h>

#define SYS_CATALOGUE_ADDR   0x3F0000u
#define SYS_ROM_MAX          0x1F0000u
#define SYS_MAX_CARTS        512
#define SYS_NO_AUTOBOOT      0xFFFFFFFFu
#define SYS_FLAG_SKIP_BOOT   1u
#define SYS_FLAG_RETURNING   2u

typedef struct {
    char title[32];
    uint32_t size;
    char path[512];      /* file path, or URL on the web */
} SysCart;

typedef struct {
    SysCart carts[SYS_MAX_CARTS];
    int count;
} SysCatalogue;

/* Reads the title from a cart's MEI1 header, falling back to `fallback`. */
void sys_cart_title(const uint8_t *data, size_t len, const char *fallback, char out[32]);

/* Adds an entry; returns its index or -1 when full. */
int sys_add(SysCatalogue *c, const char *title, uint32_t size, const char *path);

/* Adds every *.mei file in `dir` (sorted by title). Returns the number added.
 * `skip` (may be NULL) is a file name to leave out, e.g. the system ROM itself. */
int sys_scan_dir(SysCatalogue *c, const char *dir, const char *skip);

/* Index of the entry whose path is `path`, or -1. */
int sys_find_path(const SysCatalogue *c, const char *path);

/* Builds a full 2 MB ROM image: the system ROM followed by the catalogue.
 * Returns a malloc'd buffer (caller frees) or NULL if the system ROM is too big. */
uint8_t *sys_build_image(const uint8_t *rom, size_t len, const SysCatalogue *c,
                         uint32_t autoboot, uint32_t flags, const char *platform, size_t *out_len);

#endif
