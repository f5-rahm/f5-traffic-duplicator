#!/usr/bin/env bash
# ==============================================================================
# Deploy Application Services for BIG-IP 17.5 (IPv4 & IPv6)
# ==============================================================================
set -e

echo "=== [BIG-IP 17.5] Deploying IPv4 Services ==="
tmsh create sys application service app_175_udp_single \
    template f5.traffic_duplication \
    variables add { \
        basic__addr { value 10.1.10.151 } \
        basic__port { value 514 } \
        basic__protocol { value UDP } \
        basic__numberofservers { value 1 } \
    } \
    tables add { \
        destinations__servers { \
            column-names { name addr1 port1 } \
            rows { \
                { row { s1 10.1.20.104 514 } } \
                { row { s2 10.1.20.105 514 } } \
                { row { s3 10.1.20.106 514 } } \
            } \
        } \
    }

tmsh create sys application service app_175_udp_lb \
    template f5.traffic_duplication \
    variables add { \
        basic__addr { value 10.1.10.152 } \
        basic__port { value 514 } \
        basic__protocol { value UDP } \
        basic__numberofservers { value 2 } \
    } \
    tables add { \
        destinations__servers { \
            column-names { name operationmode addr1 port1 addr2 port2 } \
            rows { \
                { row { tst_dst LoadBalance 10.1.20.104 514 10.1.20.105 514 } } \
            } \
        } \
    }

tmsh create sys application service app_175_udp_failover \
    template f5.traffic_duplication \
    lists add { \
        basic__monitor { value { /Common/gateway_icmp } } \
    } \
    variables add { \
        basic__addr { value 10.1.10.153 } \
        basic__port { value 514 } \
        basic__protocol { value UDP } \
        basic__numberofservers { value 2 } \
    } \
    tables add { \
        destinations__servers { \
            column-names { name operationmode addr1 port1 addr2 port2 } \
            rows { \
                { row { tst_dst_fail Failover 10.1.20.104 514 10.1.20.105 514 } } \
            } \
        } \
    }

tmsh create sys application service app_175_tcp_spray \
    template f5.traffic_duplication \
    variables add { \
        basic__addr { value 10.1.10.154 } \
        basic__port { value 9999 } \
        basic__protocol { value TCP } \
        basic__numberofservers { value 1 } \
    } \
    tables add { \
        destinations__servers { \
            column-names { name addr1 port1 } \
            rows { \
                { row { s1 10.1.20.104 9999 } } \
                { row { s2 10.1.20.105 9999 } } \
                { row { s3 10.1.20.106 9999 } } \
            } \
        } \
    }

echo "=== [BIG-IP 17.5] Deploying IPv6 Services ==="
tmsh create sys application service app_175_v6_udp_single \
    template f5.traffic_duplication \
    variables add { \
        basic__addr { value fd00:1:1:10::151 } \
        basic__port { value 514 } \
        basic__protocol { value UDP } \
        basic__numberofservers { value 1 } \
    } \
    tables add { \
        destinations__servers { \
            column-names { name addr1 port1 } \
            rows { \
                { row { s1 fd00:1:1:20::104 514 } } \
                { row { s2 fd00:1:1:20::105 514 } } \
                { row { s3 fd00:1:1:20::106 514 } } \
            } \
        } \
    }

tmsh create sys application service app_175_v6_udp_lb \
    template f5.traffic_duplication \
    variables add { \
        basic__addr { value fd00:1:1:10::152 } \
        basic__port { value 514 } \
        basic__protocol { value UDP } \
        basic__numberofservers { value 2 } \
    } \
    tables add { \
        destinations__servers { \
            column-names { name operationmode addr1 port1 addr2 port2 } \
            rows { \
                { row { tst_dst LoadBalance fd00:1:1:20::104 514 fd00:1:1:20::105 514 } } \
            } \
        } \
    }

tmsh create sys application service app_175_v6_udp_failover \
    template f5.traffic_duplication \
    lists add { \
        basic__monitor { value { /Common/gateway_icmp } } \
    } \
    variables add { \
        basic__addr { value fd00:1:1:10::153 } \
        basic__port { value 514 } \
        basic__protocol { value UDP } \
        basic__numberofservers { value 2 } \
    } \
    tables add { \
        destinations__servers { \
            column-names { name operationmode addr1 port1 addr2 port2 } \
            rows { \
                { row { tst_dst_fail Failover fd00:1:1:20::104 514 fd00:1:1:20::105 514 } } \
            } \
        } \
    }

tmsh create sys application service app_175_v6_tcp_spray \
    template f5.traffic_duplication \
    variables add { \
        basic__addr { value fd00:1:1:10::154 } \
        basic__port { value 9999 } \
        basic__protocol { value TCP } \
        basic__numberofservers { value 1 } \
    } \
    tables add { \
        destinations__servers { \
            column-names { name addr1 port1 } \
            rows { \
                { row { s1 fd00:1:1:20::104 9999 } } \
                { row { s2 fd00:1:1:20::105 9999 } } \
                { row { s3 fd00:1:1:20::106 9999 } } \
            } \
        } \
    }

echo "[+] BIG-IP 17.5 services deployed successfully."
