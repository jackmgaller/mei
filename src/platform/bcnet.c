/* Desktop broadcast tuner (docs/BROADCAST.md, "Platforms"): receives the MeiNet gateway's
 * byte stream over a non-blocking TCP socket and passes it to the core, up to 16 bytes per
 * tick. Without a gateway it reports no carrier and retries quietly every 3 seconds. */
#define _DEFAULT_SOURCE
#define _DARWIN_C_SOURCE
#include "bcnet.h"

#include <stdio.h>
#include <string.h>

#ifdef _WIN32
int bcnet_start(const char *host, int port) { (void)host; (void)port; return -1; }
void bcnet_tick(Mei *m) { mei_broadcast_carrier(m, 0); }
void bcnet_stop(void) {}
int bcnet_spawn_gateway(const char *script, int port, const char *log) { (void)script; (void)port; (void)log; return 0; }
#else
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <poll.h>
#include <signal.h>
#include <spawn.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define RING 4096
#define BACKLOG_MAX 480       /* half a second: beyond this, drop the oldest bytes */
#define BACKLOG_KEEP 64
#define RETRY_NS 3000000000ll
#define SILENCE_NS 1000000000ll

static struct {
    int on;
    char host[256], port[16];
    int fd;                   /* -1: not connected */
    int connecting;
    long long retry_at, last_rx;
    uint8_t ring[RING];
    int head, count;
} net = {.fd = -1};

static void gateway_stop(void);

static long long now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (long long)ts.tv_sec * 1000000000ll + ts.tv_nsec;
}

static void disconnect(void) {
    if (net.fd >= 0) close(net.fd);
    net.fd = -1;
    net.connecting = 0;
    net.head = net.count = 0;
    net.retry_at = now_ns() + RETRY_NS;
}

static void try_connect(void) {
    struct addrinfo hints = {0}, *res = NULL;
    hints.ai_family = AF_UNSPEC;
    hints.ai_socktype = SOCK_STREAM;
    net.retry_at = now_ns() + RETRY_NS;
    if (getaddrinfo(net.host, net.port, &hints, &res) != 0 || !res) return;
    int fd = socket(res->ai_family, res->ai_socktype, res->ai_protocol);
    if (fd >= 0) {
        fcntl(fd, F_SETFL, fcntl(fd, F_GETFL) | O_NONBLOCK);
#ifdef SO_NOSIGPIPE
        int one = 1;
        setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &one, sizeof one);
#endif
        if (connect(fd, res->ai_addr, res->ai_addrlen) == 0 || errno == EINPROGRESS) {
            net.fd = fd;
            net.connecting = 1;
            net.last_rx = now_ns();
        } else close(fd);
    }
    freeaddrinfo(res);
}

int bcnet_start(const char *host, int port) {
    snprintf(net.host, sizeof net.host, "%s", host);
    snprintf(net.port, sizeof net.port, "%d", port);
    net.on = 1;
    net.retry_at = 0;
    return 0;
}

void bcnet_tick(Mei *m) {
    if (!net.on) { mei_broadcast_carrier(m, 0); return; }
    long long t = now_ns();
    if (net.fd < 0 && t >= net.retry_at) try_connect();
    if (net.fd >= 0 && net.connecting) {
        struct pollfd pfd = {net.fd, POLLOUT, 0};
        if (poll(&pfd, 1, 0) > 0) {
            int err = 0;
            socklen_t len = sizeof err;
            if (getsockopt(net.fd, SOL_SOCKET, SO_ERROR, &err, &len) == 0 && err == 0) {
                net.connecting = 0;
                net.last_rx = t - SILENCE_NS;   /* no carrier until bytes arrive */
            }
            else disconnect();
        } else if (t - net.last_rx > RETRY_NS) disconnect();   /* connect timed out */
    }
    if (net.fd >= 0 && !net.connecting) {
        for (;;) {
            uint8_t buf[1024];
            ssize_t n = recv(net.fd, buf, sizeof buf, 0);
            if (n > 0) {
                net.last_rx = t;
                for (ssize_t i = 0; i < n; i++) {
                    if (net.count == RING) { net.head = (net.head + 1) % RING; net.count--; }
                    net.ring[(net.head + net.count) % RING] = buf[i];
                    net.count++;
                }
                continue;
            }
            if (n == 0 || (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR)) disconnect();
            break;
        }
    }
    if (net.count > BACKLOG_MAX) {          /* after a stall: keep the latency bounded */
        int drop = net.count - BACKLOG_KEEP;
        net.head = (net.head + drop) % RING;
        net.count -= drop;
    }
    int carrier = net.fd >= 0 && !net.connecting && t - net.last_rx < SILENCE_NS;
    mei_broadcast_carrier(m, carrier);
    uint8_t out[MEI_BC_BYTES_PER_TICK];
    int n = 0;
    while (n < MEI_BC_BYTES_PER_TICK && net.count > 0) {
        out[n++] = net.ring[net.head];
        net.head = (net.head + 1) % RING;
        net.count--;
    }
    if (n) mei_broadcast_feed(m, out, n);
}

void bcnet_stop(void) {
    gateway_stop();
    if (net.fd >= 0) close(net.fd);
    net.fd = -1;
    net.on = 0;
}
#endif

#ifndef _WIN32
/* ---- the gateway as a child process ---- */

extern char **environ;
static pid_t gateway_pid;

/* Is something listening on 127.0.0.1:port? (a blocking connect to loopback answers at once) */
static int port_answers(int port) {
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) return 0;
    struct sockaddr_in a = {0};
    a.sin_family = AF_INET;
    a.sin_port = htons((uint16_t)port);
    a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    int ok = connect(fd, (struct sockaddr *)&a, sizeof a) == 0;
    close(fd);
    return ok;
}

int bcnet_spawn_gateway(const char *script, int port, const char *log) {
    if (access(script, R_OK) != 0 || port_answers(port)) return 0;
    char portstr[16];
    snprintf(portstr, sizeof portstr, "%d", port);
    char *argv[] = {"python3", (char *)script, "--port", portstr, "--exit-with-parent", NULL};
    posix_spawn_file_actions_t fa;
    posix_spawn_file_actions_init(&fa);
    posix_spawn_file_actions_addopen(&fa, 0, "/dev/null", O_RDONLY, 0);
    posix_spawn_file_actions_addopen(&fa, 1, log, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    posix_spawn_file_actions_adddup2(&fa, 1, 2);
    int rc = posix_spawnp(&gateway_pid, "python3", &fa, NULL, argv, environ);
    posix_spawn_file_actions_destroy(&fa);
    if (rc != 0) { gateway_pid = 0; return 0; }
    return 1;
}

static void gateway_stop(void) {
    if (gateway_pid > 0) {
        kill(gateway_pid, SIGTERM);
        waitpid(gateway_pid, NULL, 0);
        gateway_pid = 0;
    }
}
#endif
