/* Desktop broadcast tuner: the MeiNet gateway's stream over TCP (docs/BROADCAST.md). */
#ifndef MEI_BCNET_H
#define MEI_BCNET_H

#include "mei.h"

int bcnet_start(const char *host, int port);   /* connects lazily; retries every 3 s */
void bcnet_tick(Mei *m);                        /* once per tick, before mei_run_frame */
void bcnet_stop(void);   /* also stops a gateway started by bcnet_spawn_gateway */

/* Starts the MeiNet gateway (python3 script --port N) as a child process unless something
 * already answers on 127.0.0.1:port. Its output goes to log. Returns 1 if started. */
int bcnet_spawn_gateway(const char *script, int port, const char *log);

#endif
