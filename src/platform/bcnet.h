/* Desktop broadcast tuner: the MeiNet gateway's stream over TCP (docs/BROADCAST.md). */
#ifndef MEI_BCNET_H
#define MEI_BCNET_H

#include "mei.h"

int bcnet_start(const char *host, int port);   /* connects lazily; retries every 3 s */
void bcnet_tick(Mei *m);                        /* once per tick, before mei_run_frame */
void bcnet_stop(void);

#endif
