/* Direct-USB reader for XInput (Xbox 360 protocol) controllers, via libusb.
 * macOS has no driver for these (interface class 255, subclass 93, protocol 1),
 * so SDL never sees them; many third-party pads such as the 8BitDo Ultimate 2C
 * only speak XInput over a cable. A background thread finds such devices,
 * claims them and decodes their 20-byte input reports. */
#include "xinput_usb.h"

#include <libusb.h>
#include <pthread.h>
#include <string.h>
#include <unistd.h>

typedef struct {
    libusb_device_handle *handle;
    int iface;
    unsigned char in_ep, out_ep;
    MeiPadInput state;
    int guide;
} XPad;

static libusb_context *ctx;
static pthread_t thread;
static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static volatile int running;
static XPad pads[XUSB_MAX_PADS];
static volatile int home_pressed;   /* Guide button went down */

static int is_xinput(const struct libusb_interface_descriptor *id) {
    return id->bInterfaceClass == 255 && id->bInterfaceSubClass == 93 && id->bInterfaceProtocol == 1;
}

static int already_open(libusb_device *dev) {
    for (int i = 0; i < XUSB_MAX_PADS; i++)
        if (pads[i].handle && libusb_get_device(pads[i].handle) == dev) return 1;
    return 0;
}

/* Lights the player LED (Xbox 360 LED command; patterns 6-9 = players 1-4). */
static void set_led(XPad *p, int player) {
    if (!p->out_ep) return;
    unsigned char cmd[3] = {0x01, 0x03, (unsigned char)(6 + player)};
    int sent;
    libusb_interrupt_transfer(p->handle, p->out_ep, cmd, sizeof cmd, &sent, 100);
}

static void scan(void) {
    libusb_device **list;
    ssize_t n = libusb_get_device_list(ctx, &list);
    for (ssize_t i = 0; i < n; i++) {
        int slot = -1;
        for (int s = 0; s < XUSB_MAX_PADS; s++) if (!pads[s].handle) { slot = s; break; }
        if (slot < 0) break;
        if (already_open(list[i])) continue;
        struct libusb_config_descriptor *cfg;
        if (libusb_get_active_config_descriptor(list[i], &cfg) != 0) continue;
        for (int f = 0; f < cfg->bNumInterfaces; f++) {
            const struct libusb_interface_descriptor *id = &cfg->interface[f].altsetting[0];
            if (!is_xinput(id)) continue;
            XPad p = {0};
            for (int e = 0; e < id->bNumEndpoints; e++) {
                const struct libusb_endpoint_descriptor *ep = &id->endpoint[e];
                if ((ep->bmAttributes & 3) != LIBUSB_TRANSFER_TYPE_INTERRUPT) continue;
                if (ep->bEndpointAddress & 0x80) { if (!p.in_ep) p.in_ep = ep->bEndpointAddress; }
                else if (!p.out_ep) p.out_ep = ep->bEndpointAddress;
            }
            if (!p.in_ep || libusb_open(list[i], &p.handle) != 0) break;
            libusb_set_auto_detach_kernel_driver(p.handle, 1);
            p.iface = id->bInterfaceNumber;
            if (libusb_claim_interface(p.handle, p.iface) != 0) { libusb_close(p.handle); break; }
            set_led(&p, slot);
            pthread_mutex_lock(&lock);
            pads[slot] = p;
            pthread_mutex_unlock(&lock);
            break;   /* first XInput interface only; wireless receivers expose more */
        }
        libusb_free_config_descriptor(cfg);
    }
    libusb_free_device_list(list, 1);
}

static float stick(const unsigned char *b) {
    int16_t v = (int16_t)(b[0] | b[1] << 8);
    return v < 0 ? v / 32768.0f : v / 32767.0f;
}

/* Xbox 360 input report: bytes 2-3 buttons, 6-9 left stick (y up = positive). */
static void decode(const unsigned char *r, MeiPadInput *out) {
    static const struct { uint16_t mask; uint32_t bit; } map[] = {
        {0x0001, MEI_BTN_UP}, {0x0002, MEI_BTN_DOWN}, {0x0004, MEI_BTN_LEFT}, {0x0008, MEI_BTN_RIGHT},
        {0x0010, MEI_BTN_START}, {0x0020, MEI_BTN_SELECT}, {0x0100, MEI_BTN_L}, {0x0200, MEI_BTN_R},
        {0x1000, MEI_BTN_A}, {0x2000, MEI_BTN_B}, {0x4000, MEI_BTN_X}, {0x8000, MEI_BTN_Y},
    };
    uint16_t raw = (uint16_t)(r[2] | r[3] << 8);
    out->buttons = 0;
    for (size_t i = 0; i < sizeof map / sizeof map[0]; i++)
        if (raw & map[i].mask) out->buttons |= map[i].bit;
    out->stick_x = stick(r + 6);
    out->stick_y = stick(r + 8);
}

static void drop(int s) {
    pthread_mutex_lock(&lock);
    libusb_device_handle *h = pads[s].handle;
    int iface = pads[s].iface;
    memset(&pads[s], 0, sizeof pads[s]);
    pthread_mutex_unlock(&lock);
    libusb_release_interface(h, iface);
    libusb_close(h);
}

static void *run(void *arg) {
    int since_scan = 1000;
    while (running) {
        if (since_scan >= 1000) { scan(); since_scan = 0; }   /* look for new pads about once a second */
        int any = 0;
        for (int s = 0; s < XUSB_MAX_PADS; s++) {
            if (!pads[s].handle) continue;
            any = 1;
            unsigned char buf[32];
            int got, r = libusb_interrupt_transfer(pads[s].handle, pads[s].in_ep, buf, sizeof buf, &got, 4);
            if (r == 0 && got >= 14 && buf[0] == 0x00) {
                MeiPadInput in;
                decode(buf, &in);
                int guide = (buf[3] & 0x04) != 0;
                if (guide && !pads[s].guide) home_pressed = 1;
                pads[s].guide = guide;
                pthread_mutex_lock(&lock);
                pads[s].state = in;
                pthread_mutex_unlock(&lock);
            } else if (r != 0 && r != LIBUSB_ERROR_TIMEOUT && r != LIBUSB_ERROR_OVERFLOW) {
                drop(s);   /* unplugged */
            }
            since_scan += 4;
        }
        if (!any) { usleep(10000); since_scan += 10; }
    }
    for (int s = 0; s < XUSB_MAX_PADS; s++) if (pads[s].handle) drop(s);
    return NULL;
}

int xusb_start(void) {
    if (libusb_init(&ctx) != 0) return -1;
    running = 1;
    if (pthread_create(&thread, NULL, run, NULL) != 0) { running = 0; libusb_exit(ctx); return -1; }
    return 0;
}

void xusb_stop(void) {
    if (!running) return;
    running = 0;
    pthread_join(thread, NULL);
    libusb_exit(ctx);
}

int xusb_pad(int index, MeiPadInput *out) {
    if (index < 0 || index >= XUSB_MAX_PADS) return 0;
    pthread_mutex_lock(&lock);
    int present = pads[index].handle != NULL;
    if (present) *out = pads[index].state;
    pthread_mutex_unlock(&lock);
    return present;
}

int xusb_home_pressed(void) {
    int h = home_pressed;
    home_pressed = 0;
    return h;
}
