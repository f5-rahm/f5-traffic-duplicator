#!/usr/bin/env bash
# Teardown BIG-IP 17.1 Application Services
echo "=== Deleting TMOS 17.1 Application Services ==="
tmsh delete sys application service \
    app_171_udp_single \
    app_171_udp_lb \
    app_171_udp_failover \
    app_171_tcp_spray \
    app_171_v6_udp_single \
    app_171_v6_udp_lb \
    app_171_v6_udp_failover \
    app_171_v6_tcp_spray 2>/dev/null || true
echo "[+] 17.1 Cleanup complete."
