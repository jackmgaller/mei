#define _DARWIN_C_SOURCE   /* realpath */
#define _DEFAULT_SOURCE
/* SDL3 platform layer: window, audio, input and the 60 Hz main loop.
 * The core only sees three things from here: a presented frame, queued audio
 * and pad input (see present(), queue_audio(), read_input()).
 *   mei [--no-boot] [--broadcast HOST:PORT | --no-broadcast] [--no-gateway] [--broadcast-noise BER] [cart.mei]
 *   (or drop a .mei file onto the window)
 * With build/system.mei next to the executable, the console boots the system ROM
 * (boot animation + shell, docs/SYSTEM.md); a cart argument is launched after the boot
 * animation unless --no-boot is given. Home (gamepad Guide button or F2) returns to it.
 * The broadcast tuner (docs/BROADCAST.md) listens to the MeiNet gateway, by default on
 * 127.0.0.1:9600; without one the console simply has no signal. The web build has none.
 * On the default local address the player starts the gateway itself (tools/meinet/meinet.py,
 * found next to build/) unless one is already running or --no-gateway is given; it stops with
 * the player and logs to build/meinet.log.
 * Gamepads come from SDL, plus XInput pads read directly over USB when built with libusb.
 * Keys: arrows d-pad, WASD stick, J/K/U/I = A/B/X/Y, Q/E = L/R, Enter = Start,
 *       Backspace or right Shift = Select,
 *       F2 home, F5 reset, F11 fullscreen, Esc quit. */
#define SDL_MAIN_USE_CALLBACKS 1
#include <SDL3/SDL.h>
#include <SDL3/SDL_main.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "mei.h"
#include "sysboot.h"

#ifdef __EMSCRIPTEN__
#include <emscripten.h>
#endif
#ifdef MEI_XINPUT_USB
#include "xinput_usb.h"
#endif
#ifndef __EMSCRIPTEN__
#include "bcnet.h"
#endif

#define TICK_NS (1000000000ull / MEI_FPS)
#define MAX_PADS 2

typedef struct {
    SDL_Window *window;
    SDL_Renderer *renderer;
    SDL_Texture *texture;
    SDL_AudioStream *audio;
    SDL_Gamepad *pads[MAX_PADS];
    Mei *mei;
    Uint64 last_ns, accum_ns;
    char title[96];
} App;

static App app;

/* ---- the three platform calls ---- */

static void present(const uint16_t *pixels) {
    SDL_UpdateTexture(app.texture, NULL, pixels, MEI_W * 2);
    SDL_SetRenderDrawColor(app.renderer, 0, 0, 0, 255);
    SDL_RenderClear(app.renderer);
    SDL_RenderTexture(app.renderer, app.texture, NULL, NULL);
    SDL_RenderPresent(app.renderer);
}

static void queue_audio(const int16_t *samples, int frames) {
    /* Keep latency bounded: if the device has fallen behind the 60 Hz clock,
     * drop this tick's audio rather than let the queue grow. */
    int queued = SDL_GetAudioStreamQueued(app.audio);
    if (queued > MEI_AUDIO_RATE * 4 / 8) return;   /* > 125 ms */
    SDL_PutAudioStreamData(app.audio, samples, frames * 4);
}

static float axis(Sint16 v) { return v < 0 ? v / 32768.0f : v / 32767.0f; }

static void read_input(MeiPadInput pads[MAX_PADS]) {
    memset(pads, 0, sizeof(MeiPadInput) * MAX_PADS);
    static const struct { SDL_GamepadButton b; uint32_t bit; } map[] = {
        {SDL_GAMEPAD_BUTTON_DPAD_UP, MEI_BTN_UP}, {SDL_GAMEPAD_BUTTON_DPAD_DOWN, MEI_BTN_DOWN},
        {SDL_GAMEPAD_BUTTON_DPAD_LEFT, MEI_BTN_LEFT}, {SDL_GAMEPAD_BUTTON_DPAD_RIGHT, MEI_BTN_RIGHT},
        {SDL_GAMEPAD_BUTTON_SOUTH, MEI_BTN_A}, {SDL_GAMEPAD_BUTTON_EAST, MEI_BTN_B},
        {SDL_GAMEPAD_BUTTON_WEST, MEI_BTN_X}, {SDL_GAMEPAD_BUTTON_NORTH, MEI_BTN_Y},
        {SDL_GAMEPAD_BUTTON_LEFT_SHOULDER, MEI_BTN_L}, {SDL_GAMEPAD_BUTTON_RIGHT_SHOULDER, MEI_BTN_R},
        {SDL_GAMEPAD_BUTTON_START, MEI_BTN_START}, {SDL_GAMEPAD_BUTTON_BACK, MEI_BTN_SELECT},
    };
    for (int p = 0; p < MAX_PADS; p++) {
        SDL_Gamepad *gp = app.pads[p];
        if (!gp) continue;
        for (size_t i = 0; i < SDL_arraysize(map); i++)
            if (SDL_GetGamepadButton(gp, map[i].b)) pads[p].buttons |= map[i].bit;
        pads[p].stick_x = axis(SDL_GetGamepadAxis(gp, SDL_GAMEPAD_AXIS_LEFTX));
        pads[p].stick_y = -axis(SDL_GetGamepadAxis(gp, SDL_GAMEPAD_AXIS_LEFTY));
    }

#ifdef MEI_XINPUT_USB
    /* XInput pads read directly over USB take the slots SDL gamepads leave free. */
    for (int p = 0, x = 0; p < MAX_PADS; p++) {
        if (app.pads[p]) continue;
        while (x < XUSB_MAX_PADS && !xusb_pad(x, &pads[p])) x++;
        x++;
    }
#endif

    /* Keyboard drives controller 1. */
    const bool *k = SDL_GetKeyboardState(NULL);
    static const struct { SDL_Scancode s; uint32_t bit; } keys[] = {
        {SDL_SCANCODE_UP, MEI_BTN_UP}, {SDL_SCANCODE_DOWN, MEI_BTN_DOWN},
        {SDL_SCANCODE_LEFT, MEI_BTN_LEFT}, {SDL_SCANCODE_RIGHT, MEI_BTN_RIGHT},
        {SDL_SCANCODE_J, MEI_BTN_A}, {SDL_SCANCODE_K, MEI_BTN_B},
        {SDL_SCANCODE_U, MEI_BTN_X}, {SDL_SCANCODE_I, MEI_BTN_Y},
        {SDL_SCANCODE_Q, MEI_BTN_L}, {SDL_SCANCODE_E, MEI_BTN_R},
        {SDL_SCANCODE_RETURN, MEI_BTN_START},
        {SDL_SCANCODE_BACKSPACE, MEI_BTN_SELECT}, {SDL_SCANCODE_RSHIFT, MEI_BTN_SELECT},
    };
    for (size_t i = 0; i < SDL_arraysize(keys); i++)
        if (k[keys[i].s]) pads[0].buttons |= keys[i].bit;
    /* WASD maps the stick to full deflection in eight directions. */
    int kx = k[SDL_SCANCODE_D] - k[SDL_SCANCODE_A], ky = k[SDL_SCANCODE_W] - k[SDL_SCANCODE_S];
    if (kx || ky) {
        float s = (kx && ky) ? 0.70710678f : 1.0f;
        pads[0].stick_x = kx * s;
        pads[0].stick_y = ky * s;
    }
}

/* Local wall-clock time for SYS_TIME / SYS_DATE. */
static void update_clock(void) {
    SDL_Time now;
    SDL_DateTime dt;
    if (SDL_GetCurrentTime(&now) && SDL_TimeToDateTime(now, &dt, true))
        mei_set_clock(app.mei, dt.year, dt.month, dt.day, dt.day_of_week, dt.hour, dt.minute, dt.second);
}

/* ---- cart loading and the system ROM ---- */

static SysCatalogue catalogue;
static uint8_t card_image[2][MEI_CARD_SIZE];   /* memory cards, persisted when they change */
static uint8_t *system_rom;
static size_t system_rom_len;
static int in_system;

#ifdef __EMSCRIPTEN__
#define PLATFORM_NAME "web"
EM_JS(void, js_fetch_cart, (const char *url), { Module.meiFetchCart(UTF8ToString(url)); });
EM_JS(void, js_save_config, (unsigned v), { try { localStorage.setItem("mei-config", String(v)); } catch (e) {} });
EM_JS(unsigned, js_load_config, (void), {
    try { return Number(localStorage.getItem("mei-config") || 0) >>> 0; } catch (e) { return 0; }
});
/* Memory cards live in localStorage as base64. */
EM_JS(void, js_load_card, (int slot, uint8_t *dst, int len), {
    try {
        const s = localStorage.getItem("mei-card" + (slot + 1));
        if (!s) return;
        const bin = atob(s);
        for (let i = 0; i < Math.min(len, bin.length); i++) HEAPU8[dst + i] = bin.charCodeAt(i);
    } catch (e) {}
});
EM_JS(void, js_save_card, (int slot, const uint8_t *src, int len), {
    try {
        let bin = "";
        for (let i = 0; i < len; i += 8192) bin += String.fromCharCode.apply(null, HEAPU8.subarray(src + i, src + Math.min(len, i + 8192)));
        localStorage.setItem("mei-card" + (slot + 1), btoa(bin));
    } catch (e) { console.warn("couldn't save memory card", e); }
});
#else
#define PLATFORM_NAME "desktop"
static char config_path[1024], card_path[2][1024];
#endif

static void debug_out(void *user, char c) { fputc(c, stdout); if (c == '\n') fflush(stdout); }

static void set_title(void) {
    const char *t = mei_cart_title(app.mei);
    snprintf(app.title, sizeof app.title, "%s%sMei", t, *t ? " - " : "");
    SDL_SetWindowTitle(app.window, app.title);
}

static int load_cart_bytes(const uint8_t *data, size_t len) {
    if (mei_load_cart(app.mei, data, len) != 0) {
        SDL_Log("not a valid cart (%zu bytes)", len);
        return -1;
    }
    SDL_ClearAudioStream(app.audio);
    set_title();
    return 0;
}

static int load_cart_file(const char *path) {
    size_t len = 0;
    void *data = SDL_LoadFile(path, &len);
    if (!data) { SDL_Log("%s: %s", path, SDL_GetError()); return -1; }
    int r = load_cart_bytes(data, len);
    SDL_free(data);
    if (r == 0) in_system = 0;
    return r;
}

static int boot_system(uint32_t autoboot, uint32_t flags) {
    if (!system_rom) return -1;
    size_t len;
    uint8_t *img = sys_build_image(system_rom, system_rom_len, &catalogue, autoboot, flags, PLATFORM_NAME, &len);
    if (!img) { SDL_Log("system ROM too large"); return -1; }
    int r = load_cart_bytes(img, len);
    free(img);
    in_system = r == 0;
    if (in_system) mei_set_privileged(app.mei, 1);   /* the system ROM manages every save */
    return r;
}

static void go_home(void) { boot_system(SYS_NO_AUTOBOOT, SYS_FLAG_RETURNING); }

static void launch(uint32_t index) {
    if (index >= (uint32_t)catalogue.count) return;
#ifdef __EMSCRIPTEN__
    js_fetch_cart(catalogue.carts[index].path);   /* calls back into web_load_cart */
#else
    load_cart_file(catalogue.carts[index].path);
#endif
}

static void load_config(void) {
#ifdef __EMSCRIPTEN__
    mei_set_config(app.mei, js_load_config());
#else
    char *pref = SDL_GetPrefPath("gallerdude", "Mei");
    if (!pref) return;
    snprintf(config_path, sizeof config_path, "%sconfig.txt", pref);
    SDL_free(pref);
    FILE *f = fopen(config_path, "r");
    unsigned v;
    if (f && fscanf(f, "%x", &v) == 1) mei_set_config(app.mei, v);
    if (f) fclose(f);
#endif
}

static void load_cards(void) {
    for (int s = 0; s < 2; s++) {
#ifdef __EMSCRIPTEN__
        js_load_card(s, card_image[s], MEI_CARD_SIZE);
#else
        char *pref = SDL_GetPrefPath("gallerdude", "Mei");
        if (!pref) return;
        snprintf(card_path[s], sizeof card_path[s], "%scard%d.mcd", pref, s + 1);
        SDL_free(pref);
        FILE *f = fopen(card_path[s], "rb");
        if (f) { fread(card_image[s], 1, MEI_CARD_SIZE, f); fclose(f); }
#endif
        mei_card_insert(app.mei, s, card_image[s]);
    }
}

static void save_cards_if_changed(void) {
    for (int s = 0; s < 2; s++) {
        if (!mei_card_dirty(app.mei, s)) continue;
#ifdef __EMSCRIPTEN__
        js_save_card(s, card_image[s], MEI_CARD_SIZE);
#else
        FILE *f = card_path[s][0] ? fopen(card_path[s], "wb") : NULL;
        if (f) { fwrite(card_image[s], 1, MEI_CARD_SIZE, f); fclose(f); }
        else SDL_Log("couldn't save memory card %d", s + 1);
#endif
    }
}

static void save_config_if_changed(void) {
    int dirty;
    uint32_t v = mei_config(app.mei, &dirty);
    if (!dirty) return;
#ifdef __EMSCRIPTEN__
    js_save_config(v);
#else
    FILE *f = config_path[0] ? fopen(config_path, "w") : NULL;
    if (f) { fprintf(f, "%08x\n", v); fclose(f); }
#endif
}

#ifdef __EMSCRIPTEN__
/* Called from the web page's file picker / drag-and-drop. */
EMSCRIPTEN_KEEPALIVE int web_load_cart(const uint8_t *data, int len) {
    int r = load_cart_bytes(data, (size_t)len);
    if (r == 0) in_system = 0;
    return r;
}
EMSCRIPTEN_KEEPALIVE void web_reset(void) { mei_reset(app.mei); SDL_ClearAudioStream(app.audio); }
EMSCRIPTEN_KEEPALIVE int web_catalogue_add(const char *title, int size, const char *url) {
    return sys_add(&catalogue, title, (uint32_t)size, url);
}
/* Keeps a copy of the system ROM and boots it; autoboot < 0 for none. */
EMSCRIPTEN_KEEPALIVE int web_boot_system(const uint8_t *data, int len, int autoboot) {
    free(system_rom);
    system_rom = malloc((size_t)len);
    memcpy(system_rom, data, (size_t)len);
    system_rom_len = (size_t)len;
    return boot_system(autoboot < 0 ? SYS_NO_AUTOBOOT : (uint32_t)autoboot, 0);
}
EMSCRIPTEN_KEEPALIVE void web_home(void) { go_home(); }
#endif

/* ---- SDL callbacks ---- */

SDL_AppResult SDL_AppInit(void **state, int argc, char **argv) {
    SDL_SetAppMetadata("Mei", "0.1", "com.gallerdude.mei");
    if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO | SDL_INIT_GAMEPAD)) {
        SDL_Log("SDL_Init: %s", SDL_GetError());
        return SDL_APP_FAILURE;
    }
    if (!SDL_CreateWindowAndRenderer("Mei", MEI_W * 3, MEI_H * 3, SDL_WINDOW_RESIZABLE, &app.window, &app.renderer)) {
        SDL_Log("window: %s", SDL_GetError());
        return SDL_APP_FAILURE;
    }
    SDL_SetRenderVSync(app.renderer, 1);
    SDL_SetRenderLogicalPresentation(app.renderer, MEI_W, MEI_H, SDL_LOGICAL_PRESENTATION_INTEGER_SCALE);
    /* VRAM pixels are R in bits 0-4, G 5-9, B 10-14: SDL's XBGR1555. */
    app.texture = SDL_CreateTexture(app.renderer, SDL_PIXELFORMAT_XBGR1555, SDL_TEXTUREACCESS_STREAMING, MEI_W, MEI_H);
    SDL_SetTextureScaleMode(app.texture, SDL_SCALEMODE_NEAREST);

    SDL_AudioSpec spec = {SDL_AUDIO_S16, 2, MEI_AUDIO_RATE};
    app.audio = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, NULL, NULL);
    if (app.audio) SDL_ResumeAudioStreamDevice(app.audio);
    else SDL_Log("audio: %s", SDL_GetError());

#ifdef MEI_XINPUT_USB
    if (xusb_start() != 0) SDL_Log("XInput USB support unavailable");
#endif
    app.mei = mei_create();
    mei_set_debug_output(app.mei, debug_out, NULL);
    load_config();
    load_cards();
    update_clock();
#ifndef __EMSCRIPTEN__
    /* the web page supplies the system ROM and catalogue through web_boot_system */
    const char *cart = NULL, *bc_addr = "127.0.0.1:9600";
    int no_boot = 0, gateway = 1;
    double bc_noise = 0;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--no-boot")) no_boot = 1;
        else if (!strcmp(argv[i], "--broadcast") && i + 1 < argc) bc_addr = argv[++i];
        else if (!strcmp(argv[i], "--no-broadcast")) bc_addr = NULL;
        else if (!strcmp(argv[i], "--no-gateway")) gateway = 0;
        else if (!strcmp(argv[i], "--broadcast-noise") && i + 1 < argc) bc_noise = SDL_atof(argv[++i]);
        else cart = argv[i];
    }
    if (bc_addr) {
        char host[256];
        int port = 9600;
        const char *colon = strrchr(bc_addr, ':');
        size_t hl = colon ? (size_t)(colon - bc_addr) : strlen(bc_addr);
        if (hl >= sizeof host) hl = sizeof host - 1;
        memcpy(host, bc_addr, hl);
        host[hl] = 0;
        if (colon) port = SDL_atoi(colon + 1);
        if (gateway && (!strcmp(host, "127.0.0.1") || !strcmp(host, "localhost"))) {
            const char *bp = SDL_GetBasePath();
            char script[1024], log[1024];
            snprintf(script, sizeof script, "%s../tools/meinet/meinet.py", bp ? bp : "");
            snprintf(log, sizeof log, "%smeinet.log", bp ? bp : "");
            if (bcnet_spawn_gateway(script, port, log)) SDL_Log("started the MeiNet gateway (log: %s)", log);
        }
        bcnet_start(host[0] ? host : "127.0.0.1", port);
    }
    if (bc_noise > 0) mei_broadcast_noise(app.mei, (uint32_t)(bc_noise * 1e6 + 0.5), 0);
    const char *base = SDL_GetBasePath();
    char path[1024];
    snprintf(path, sizeof path, "%ssystem.mei", base ? base : "");
    system_rom = SDL_LoadFile(path, &system_rom_len);
    snprintf(path, sizeof path, "%scarts", base ? base : "");
    sys_scan_dir(&catalogue, path, NULL);

    if (cart && (no_boot || !system_rom)) load_cart_file(cart);
    else if (cart) {
        char full[1024];
        int index = -1;
        if (realpath(cart, full)) {
            for (int i = 0; i < catalogue.count && index < 0; i++) {
                char other[1024];
                if (realpath(catalogue.carts[i].path, other) && !strcmp(other, full)) index = i;
            }
        }
        if (index < 0) {
            size_t len = 0;
            void *data = SDL_LoadFile(cart, &len);
            if (data) {
                char title[32];
                sys_cart_title(data, len, cart, title);
                index = sys_add(&catalogue, title, (uint32_t)len, cart);
                SDL_free(data);
            }
        }
        if (index < 0) load_cart_file(cart);
        else boot_system((uint32_t)index, 0);
    } else if (system_rom) boot_system(SYS_NO_AUTOBOOT, 0);
#endif
    app.last_ns = SDL_GetTicksNS();
    return SDL_APP_CONTINUE;
}

static void open_gamepad(SDL_JoystickID id) {
    for (int p = 0; p < MAX_PADS; p++)
        if (!app.pads[p]) { app.pads[p] = SDL_OpenGamepad(id); return; }
}

static void close_gamepad(SDL_JoystickID id) {
    for (int p = 0; p < MAX_PADS; p++)
        if (app.pads[p] && SDL_GetGamepadID(app.pads[p]) == id) {
            SDL_CloseGamepad(app.pads[p]);
            app.pads[p] = NULL;
        }
}

SDL_AppResult SDL_AppEvent(void *state, SDL_Event *e) {
    switch (e->type) {
    case SDL_EVENT_QUIT: return SDL_APP_SUCCESS;
    case SDL_EVENT_GAMEPAD_ADDED: open_gamepad(e->gdevice.which); break;
    case SDL_EVENT_GAMEPAD_REMOVED: close_gamepad(e->gdevice.which); break;
    case SDL_EVENT_DROP_FILE: if (e->drop.data) load_cart_file(e->drop.data); break;
    case SDL_EVENT_GAMEPAD_BUTTON_DOWN: if (e->gbutton.button == SDL_GAMEPAD_BUTTON_GUIDE) go_home(); break;
    case SDL_EVENT_KEY_DOWN:
        if (e->key.repeat) break;
        if (e->key.key == SDLK_ESCAPE) {
#ifndef __EMSCRIPTEN__
            return SDL_APP_SUCCESS;
#endif
        } else if (e->key.key == SDLK_F2) {
            go_home();
        } else if (e->key.key == SDLK_F5) {
            mei_reset(app.mei);
            SDL_ClearAudioStream(app.audio);
        } else if (e->key.key == SDLK_F11) {
            SDL_SetWindowFullscreen(app.window, !(SDL_GetWindowFlags(app.window) & SDL_WINDOW_FULLSCREEN));
        }
        break;
    }
    return SDL_APP_CONTINUE;
}

SDL_AppResult SDL_AppIterate(void *state) {
    Uint64 now = SDL_GetTicksNS();
    app.accum_ns += now - app.last_ns;
    app.last_ns = now;
    if (app.accum_ns > 4 * TICK_NS) app.accum_ns = TICK_NS;   /* after a stall, don't spiral */

    int ran = 0;
    while (app.accum_ns >= TICK_NS) {
        app.accum_ns -= TICK_NS;
        MeiPadInput pads[MAX_PADS];
        read_input(pads);
        for (int p = 0; p < MAX_PADS; p++) mei_set_pad(app.mei, p, &pads[p]);
        update_clock();
#ifndef __EMSCRIPTEN__
        bcnet_tick(app.mei);
#endif
        mei_run_frame(app.mei);
        uint32_t index;
        if (mei_launch_request(app.mei, &index) && in_system) launch(index);
        save_config_if_changed();
        save_cards_if_changed();
#ifdef MEI_XINPUT_USB
        if (xusb_home_pressed()) go_home();
#endif
        const int16_t *samples;
        int n = mei_audio(app.mei, &samples);
        if (app.audio && n > 0) queue_audio(samples, n);
        ran = 1;
    }
    if (ran) present(mei_display(app.mei));
#ifndef __EMSCRIPTEN__
    else SDL_Delay(1);   /* the browser paces us with requestAnimationFrame */
#endif
    return SDL_APP_CONTINUE;
}

void SDL_AppQuit(void *state, SDL_AppResult result) {
#ifdef MEI_XINPUT_USB
    xusb_stop();
#endif
#ifndef __EMSCRIPTEN__
    bcnet_stop();
#endif
    if (app.mei) mei_destroy(app.mei);
    SDL_free(system_rom);
}
