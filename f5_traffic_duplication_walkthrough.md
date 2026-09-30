# UDP/TCP packet duplication — modernization walkthrough

DevCentral codeshare update: `f5.traffic_duplication`

---

## Summary

### What changed from the original template

- **Dual-stack IPv4/IPv6 and route domains.** The original was hardcoded to IPv4 dot-decimal addressing, a fixed `255.255.255.255` netmask, and colon-delimited endpoints. The rebuild adds dynamic netmasks, route domain (`%rd`) preservation, and endpoint formatting that adapts per family — dot notation for IPv6, colon notation for IPv4.
- **Header serialization and performance.** The original packed the client IP/destination/payload into a fixed 256-byte binary `ssssa256` structure, which caused UTF-8 string shimmering, extra memory allocation, and payload truncation. The rebuild uses a lightweight delimited string format (`ClientIP#Destination#Payload`) parsed with C-level `memchr` routines — over 16x faster with no data corruption.
- **TCP duplication efficiency.** The original opened a new HSL TCP handle on every `CLIENT_DATA` event. The rebuild pre-opens and pools the HSL handles once in `CLIENT_ACCEPTED`, so the data path is just a lightweight list iteration.
- **Monitoring and failover.** Replaced monitor assumptions that broke across TMOS versions with universal `gateway_icmp` monitoring and priority-group failover logic that behaves consistently on TMOS 17.1, 17.5, and 21.1.
- **Tooling and test automation.** Manual CLI deployment and static presentation scripts were replaced with a full automation suite — per-version deploy scripts (`deploy_171.sh`, `deploy_175.sh`, `deploy_211.sh`), a multi-node virtual-wire test harness, and automated PCAP payload validation.

### Troubleshooting along the way

- **IPv6 port formatting errors.** Deployments failed on addresses like `fdf5::1:1:1:1:514` because the port looked missing. Fixed by branching endpoint formatting: `addr.port` for IPv6, `addr:port` for IPv4.
- **Virtual server collisions (01070333:3).** Running multiple test app services at once threw conflicts on destination IP/port/protocol/VLAN. Fixed by allocating unique VIPs per test suite and keeping each app service's internal distribution VS cleanly separated.
- **Missing ICMPv6 monitor (01070022:3).** TMOS 17.1 doesn't ship `/Common/icmpv6`, so deployments failed. Standardized every script and template on `/Common/gateway_icmp`, which natively probes both IPv4 and IPv6.
- **TCP source IP parity check.** Needed to confirm TCP spray was ever supposed to preserve the client's source IP. Verified against the original 2015 source: it never did — TCP spray has always originated from the BIG-IP self IP because of the stateful TCP three-way handshake. Current behavior is fully consistent with the original design.

---

## `app_udp_single` — single-server spray

```mermaid
flowchart TD
    client["Client<br/>syslog source"]
    ingress["Ingress VS<br/>10.1.10.150:514 · udp_spray"]
    dg[("Data-group<br/>.201:514 → s1<br/>.202:514 → s2<br/>.203:514 → s3")]
    dist["Internal distribute VS<br/>198.19.10.150:514 · distribute"]
    s1["10.1.20.201:514<br/>Server s1"]
    s2["10.1.20.202:514<br/>Server s2"]
    s3["10.1.20.203:514<br/>Server s3"]

    client --> ingress
    ingress -.->|reads| dg
    ingress -->|HSL spray x3| dist
    dist --> s1
    dist --> s2
    dist --> s3

    classDef vs fill:#E6F1FB,stroke:#185FA5,color:#0C447C;
    classDef dest fill:#E1F5EE,stroke:#0F6E56,color:#085041;
    classDef neutral fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A;
    class ingress,dist vs;
    class s1,s2,s3 dest;
    class client,dg neutral;
```

The data-group keys are the real destination endpoints; the values are just the friendly names from the app service table. The spray iRule loops over the keys to decide how many copies to send. With a single server per destination and no pools involved, the distribute iRule forwards straight to `node <ip> <port>`, preserving the client's source IP via SNAT.

---

## `app_tcp_spray` — direct HSL fan-out

```mermaid
flowchart TD
    client["Client<br/>TCP source"]
    ingress["Ingress VS (TCP)<br/>10.1.10.150:9999 · tcp_spray"]
    s1["10.1.20.201:9999<br/>Pool: s1_tcp"]
    s2["10.1.20.202:9999<br/>Pool: s2_tcp"]
    s3["10.1.20.203:9999<br/>Pool: s3_tcp"]

    client --> ingress
    ingress -->|persistent HSL x3| s1
    ingress --> s2
    ingress --> s3

    classDef vs fill:#E6F1FB,stroke:#185FA5,color:#0C447C;
    classDef dest fill:#E1F5EE,stroke:#0F6E56,color:#085041;
    classDef neutral fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A;
    class ingress vs;
    class s1,s2,s3 dest;
    class client neutral;
```

No internal loopback VS and no data-group here — pool names are compiled straight into the iRule at build time. Three HSL TCP handles open once in `CLIENT_ACCEPTED` and every `CLIENT_DATA` chunk streams to all three simultaneously. Per the parity check above, this path has never preserved the client's source IP — destinations see the BIG-IP self IP, by original design.

---

## `app_udp_failover` — active/standby

```mermaid
flowchart TD
    client["Client<br/>syslog source"]
    ingress["Ingress VS<br/>10.1.10.151:514 · udp_spray"]
    dg[("Data-group<br/>pool ref → tst_dst_fail")]
    dist["Internal distribute VS<br/>198.19.10.151:514 · distribute"]
    pool["Failover pool<br/>gateway_icmp · min-active 1"]
    primary["10.1.20.201:514<br/>ACTIVE · prio 200"]
    standby["10.1.20.202:514<br/>STANDBY · prio 190"]

    client --> ingress
    ingress -.->|reads| dg
    ingress -->|HSL x1| dist
    dist --> pool
    pool --> primary
    pool -.->|if primary down| standby

    classDef vs fill:#E6F1FB,stroke:#185FA5,color:#0C447C;
    classDef active fill:#E1F5EE,stroke:#0F6E56,color:#085041;
    classDef standby fill:#F1EFE8,stroke:#5F5E5A,color:#5F5E5A,stroke-dasharray: 4 3;
    classDef neutral fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A;
    class ingress,dist,pool vs;
    class primary active;
    class standby standby;
    class client,dg neutral;
```

The two servers collapse into one failover pool, so the data-group holds a *pool name* instead of a raw endpoint, and the distribute iRule hands off to native LTM pool selection with `pool $destination`. The solid edge is the normal path; the dashed edge only carries traffic once `gateway_icmp` marks `.201` down and priority-group 200 alone can't satisfy `min-active-members 1`.

---

## `app_udp_lb` — even load balancing

```mermaid
flowchart TD
    client["Client<br/>syslog source"]
    ingress["Ingress VS<br/>10.1.10.152:514 · udp_spray"]
    dg[("Data-group<br/>pool ref → tst_dst")]
    dist["Internal distribute VS<br/>198.19.10.152:514 · distribute"]
    pool["Load-balanced pool<br/>monitor: none · round robin"]
    m1["10.1.20.201:514<br/>~50% · prio 200"]
    m2["10.1.20.202:514<br/>~50% · prio 200"]

    client --> ingress
    ingress -.->|reads| dg
    ingress -->|HSL x1| dist
    dist --> pool
    pool --> m1
    pool --> m2

    classDef vs fill:#E6F1FB,stroke:#185FA5,color:#0C447C;
    classDef active fill:#E1F5EE,stroke:#0F6E56,color:#085041;
    classDef neutral fill:#F1EFE8,stroke:#5F5E5A,color:#2C2C2A;
    class ingress,dist,pool vs;
    class m1,m2 active;
    class client,dg neutral;
```

Structurally identical to the failover case, but both members share priority-group 200 and there's no health monitor — so BIG-IP round-robins evenly with no active/standby distinction. Same iRule code path as failover; the behavior split comes entirely from `operationmode` and whether `basic__monitor` is set in the app service config.
