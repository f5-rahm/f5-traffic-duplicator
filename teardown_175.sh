#!/usr/bin/env bash
# Teardown BIG-IP 17.5 Application Services
echo "=== Deleting TMOS 17.5 Application Services ==="
tmsh delete sys application service \
    app_175_udp_single \
    app_175_udp_lb \
    app_175_udp_failover \
    app_175_tcp_spray \
    app_175_v6_udp_single \
    app_175_v6_udp_lb \
    app_175_v6_udp_failover \
    app_175_v6_tcp_spray 2>/dev/null || true
echo "[+] 17.5 Cleanup complete."
