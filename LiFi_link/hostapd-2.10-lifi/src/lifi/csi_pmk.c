#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include "csi_pmk.h"
#include "common.h"  // for wpa_printf, os_memcmp etc.

#define PMK_LEN 32

int csi_generate_pmk(u8 *pmk_out)
{
    wpa_printf(MSG_INFO, "[lifi] Connecting to CSI PMK server at 127.0.0.1:9911");

    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        perror("[lifi] socket");
        return 0;
    }

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_port = htons(9911),
        .sin_addr.s_addr = inet_addr("127.0.0.1")
    };

    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("[lifi] connect");
        close(sock);
        return 0;
    }

    ssize_t r = read(sock, pmk_out, PMK_LEN);
    close(sock);

    if (r != PMK_LEN) {
        wpa_printf(MSG_ERROR, "[lifi] Failed to read PMK: only %zd bytes", r);
        return 0;
    }

    wpa_hexdump_key(MSG_INFO, "[lifi] PMK received", pmk_out, PMK_LEN);

    return 1;
}

