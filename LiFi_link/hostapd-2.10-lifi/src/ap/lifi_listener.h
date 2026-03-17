#ifndef LIFI_LISTENER_H
#define LIFI_LISTENER_H

#include "ap/hostapd.h"

static u8 cached_addr[ETH_ALEN];
static char cached_passphrase[64];
static int cached_valid = 0;

int lifi_listener_init(struct hostapd_data *hapd);
void lifi_listener_deinit(struct hostapd_data *hapd);

#endif
