#!/usr/bin/env bash
# Update DuckDNS A record for lumc-dodoma → this VM's public IP.
# Requires DUCKDNS_TOKEN in environment or .env.production
set -euo pipefail
DOMAIN="${DUCKDNS_DOMAIN:-lumc-dodoma}"
TOKEN="${DUCKDNS_TOKEN:?Set DUCKDNS_TOKEN}"
echo url="https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=" | curl -k -o /tmp/duckdns.log -K -
cat /tmp/duckdns.log
echo
