#include "utils/includes.h"
#include "utils/common.h"
#include "utils/eloop.h"
#include "ap/hostapd.h"
#include "ap/sta_info.h"
#include "common/ieee802_11_defs.h"
#include "wpa_auth.h"

#define MAX_LINE 256
#define LIFI_PORT 7789
#define LIFI_BIND_IP "127.0.0.1"

//read command
static void lifi_handle_line(struct hostapd_data *hapd, char *line)
{
    char *cmd  = strtok(line, " ");
    char *mac  = strtok(NULL, " ");
    char *pass = strtok(NULL, "\n");

    wpa_printf(MSG_INFO, "[lifi] cmd=%s mac=%s pass=%s",
               cmd?cmd:"(null)", mac?mac:"(null)", pass?pass:"(null)");

    if (!cmd || !mac || !pass || os_strcmp(cmd, "setptk") != 0) {
        wpa_printf(MSG_ERROR, "[lifi] bad cmd format");
        return;
    }

    u8 addr[ETH_ALEN];
    if (hwaddr_aton(mac, addr)) {
        wpa_printf(MSG_ERROR, "[lifi] bad mac: %s", mac);
        return;
    }

    struct sta_info *sta = ap_get_sta(hapd, addr);
    if (!sta) {
        wpa_printf(MSG_ERROR, "[lifi] STA not found: " MACSTR, MAC2STR(addr));
        wpa_printf(MSG_INFO, "[lifi] caching PMK until STA associates");

	os_memcpy(cached_addr, addr, ETH_ALEN);
	os_strlcpy(cached_passphrase, pass, sizeof(cached_passphrase));
    	cached_valid = 1;
      	return;
    }

    if (!sta->wpa_sm) {
        wpa_printf(MSG_ERROR, "[lifi] STA has no wpa_sm (not authed)");
        return;
    }
    wpa_printf(MSG_INFO, "[lifi] STA found");
    size_t plen = os_strlen(pass);

    if (plen < 8 || plen > 63) {
        wpa_printf(MSG_ERROR, "[lifi] pass len invalid=%zu (8..63)", plen);
        return;
    }

    if (!hapd->conf || hapd->conf->ssid.ssid_len == 0) {
        wpa_printf(MSG_ERROR, "[lifi] missing SSID");
        return;
    }
    //finish reading msg

    //change pmk
    u8 pmk[PMK_LEN];
    pbkdf2_sha1(pass,
                (const char*)hapd->conf->ssid.ssid,
                hapd->conf->ssid.ssid_len,
                4096, (const char*)hapd->conf->ssid.wpa_psk->psk, PMK_LEN);
    wpa_hexdump_key(MSG_DEBUG, "[lifi] PMK_changed", hapd->conf->ssid.wpa_psk->psk, PMK_LEN);
    wpa_printf(MSG_DEBUG, "[lifi] PMK_new %s, soon reauth", hapd->conf->ssid.wpa_psk->psk);
    // Use WPA_REAUTH_EAPOL instead of WPA_REAUTH to prevent removing PTK
    // before handshake. This allows STA to receive msg 1/4 on the existing
    // encrypted link and send msg 2/4 encrypted with the old TK.
    // The old PTK will be replaced after msg 4/4 completes.
    wpa_auth_sm_event(sta->wpa_sm, WPA_REAUTH_EAPOL);
}

static void lifi_read_cb(int sock, void *eloop_ctx, void *sock_ctx)
{
    (void)eloop_ctx;
    struct lifi_ctx *ctx = sock_ctx;

    int cfd = accept(ctx->fd, NULL, NULL);
    if (cfd < 0) {
        wpa_printf(MSG_ERROR, "[lifi] accept: %s", strerror(errno));
        return;
    }

    char buf[MAX_LINE];
    ssize_t n = recv(cfd, buf, sizeof(buf) - 1, 0);
    if (n > 0) {
        buf[n] = '\0';
        wpa_printf(MSG_INFO, "[lifi] recv: %s", buf);
        lifi_handle_line(ctx->hapd, buf);
    }
    close(cfd);
}

int lifi_listener_init(struct hostapd_data *hapd)
{
    static int g_started = 0;
    if (g_started) {
        wpa_printf(MSG_INFO, "[lifi] listener already started");
        return 0;
    }

    struct lifi_ctx *ctx = os_zalloc(sizeof(*ctx));
    if (!ctx) return -1;
    ctx->hapd = hapd;

    int fd = socket(AF_INET, SOCK_STREAM | SOCK_NONBLOCK, 0);
    if (fd < 0) {
        wpa_printf(MSG_ERROR, "[lifi] socket: %s", strerror(errno));
        os_free(ctx);
        return -1;
    }

    int on = 1;
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on));

    struct sockaddr_in sin;
    os_memset(&sin, 0, sizeof(sin));
    sin.sin_family = AF_INET;
    sin.sin_port   = htons(LIFI_PORT);
    if (inet_pton(AF_INET, LIFI_BIND_IP, &sin.sin_addr) != 1) {
        wpa_printf(MSG_ERROR, "[lifi] inet_pton failed for %s", LIFI_BIND_IP);
        close(fd);
        os_free(ctx);
        return -1;
    }

    if (bind(fd, (struct sockaddr*)&sin, sizeof(sin)) < 0) {
        wpa_printf(MSG_ERROR, "[lifi] bind %s:%d: %s",
                   LIFI_BIND_IP, LIFI_PORT, strerror(errno));
        close(fd);
        os_free(ctx);
        return -1;
    }
    
    if (listen(fd, 8) < 0) {
        wpa_printf(MSG_ERROR, "[lifi] listen: %s", strerror(errno));
        close(fd);
        os_free(ctx);
        return -1;
    }

    ctx->fd = fd;

    if (eloop_register_read_sock(fd, lifi_read_cb, hapd, ctx) < 0) {
        wpa_printf(MSG_ERROR, "[lifi] eloop_register_read_sock failed");
        close(fd);
        os_free(ctx);
        return -1;
    }

    hapd->lifi_priv = ctx;
    g_started = 1;

    wpa_printf(MSG_INFO, "[lifi] TCP listener on %s:%d", LIFI_BIND_IP, LIFI_PORT);
    return 0;
}

void lifi_listener_deinit(struct hostapd_data *hapd)
{
    struct lifi_ctx *ctx = hapd ? (struct lifi_ctx *)hapd->lifi_priv : NULL;
    if (!ctx) return;
    eloop_unregister_read_sock(ctx->fd);
    close(ctx->fd);
    os_free(ctx);
    hapd->lifi_priv = NULL;
}


