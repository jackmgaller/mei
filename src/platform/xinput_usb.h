/* Optional direct-USB XInput controller support (desktop builds with libusb). */
#ifndef MEI_XINPUT_USB_H
#define MEI_XINPUT_USB_H

#include "mei.h"

#define XUSB_MAX_PADS 2

int xusb_start(void);                        /* 0 on success */
void xusb_stop(void);
int xusb_pad(int index, MeiPadInput *out);   /* 1 and fills *out if pad `index` is connected */
int xusb_home_pressed(void);                 /* 1 once after a Guide button press */

#endif
