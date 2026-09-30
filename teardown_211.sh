#!/usr/bin/env bash
# Teardown BIG-IP 21.1 Application Services
echo "=== Deleting TMOS 21.1 Application Services ==="
tmsh delete sys application service \
    app_211_udp_single \
    app_211_udp_lb \
    app_211_udp_failover \
    app_211_tcp_spray \
    app_211_v6_udp_single \
    app_211_v6_udp_lb \
    app_211_v6_udp_failover \
    app_211_v6_tcp_spray 2>/dev/null || true
echo "[+] 21.1 Cleanup complete."
