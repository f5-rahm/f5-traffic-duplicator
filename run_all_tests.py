#!/usr/bin/env python3
"""
Master Automated Test Runner for F5 BIG-IP Traffic Duplication Matrix
Supports IPv4 & IPv6 Dual-Stack testing across TMOS 17.1, 17.5, and 21.1.
Generates comprehensive linked Markdown reports.

Usage Examples:
  # Run all IPv4 tests (default):
  sudo python3 run_all_tests.py --interface ens7

  # Run all IPv6 tests:
  sudo python3 run_all_tests.py -6 --interface ens7
  # or:
  sudo python3 run_all_tests.py --ip-version 6 --interface ens7

  # Run both IPv4 and IPv6 matrix (all 24 tests):
  sudo python3 run_all_tests.py --ip-version all --interface ens7

  # Run only TMOS 17.5 IPv6 tests:
  sudo python3 run_all_tests.py -6 --version 17.5 --interface ens7

  # Run only IPv6 tests:
  sudo python3 run_all_tests.py -6 --interface ens7

  # Run specific ad-hoc test:
  sudo python3 run_all_tests.py --vip fd00:1:1:10::151 --dests fd00:1:1:20::104,fd00:1:1:20::105,fd00:1:1:20::106 --interface ens7
"""

import argparse
import datetime
import ipaddress
import os
import platform
import socket
import struct
import sys
import threading
import time
import uuid

# Terminal Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"


def is_ipv6(addr: str) -> bool:
    """Returns True if the given IP address string is IPv6."""
    try:
        return ipaddress.ip_address(addr.strip()).version == 6
    except ValueError:
        return ":" in addr


def get_addr_family(addr: str) -> int:
    """Returns socket.AF_INET6 or socket.AF_INET based on the IP address string."""
    return socket.AF_INET6 if is_ipv6(addr) else socket.AF_INET


def normalize_ip(addr: str) -> str:
    """Normalizes IPv4 and IPv6 addresses into standard canonical string representation."""
    try:
        return str(ipaddress.ip_address(addr.strip()))
    except ValueError:
        return addr.strip()


# Master Test Matrix Definition (IPv4: IDs 1-12 | IPv6: IDs 13-24)
TEST_MATRIX_IPV4 = [
    # --- TMOS 17.1 IPv4 ---
    {
        "id": 1,
        "ip_version": "IPv4",
        "version": "17.1",
        "service_name": "app_171_udp_single",
        "test_type": "udp_duplication",
        "title": "UDP 1-to-3 Duplication",
        "vip": "10.1.10.111",
        "port": 514,
        "proto": "UDP",
        "dests": ["10.1.20.101", "10.1.20.102", "10.1.20.103"],
        "count": 5,
        "desc": "Validates 1-to-3 UDP packet replication with client IP preservation.",
    },
    {
        "id": 2,
        "ip_version": "IPv4",
        "version": "17.1",
        "service_name": "app_171_udp_lb",
        "test_type": "udp_loadbalance",
        "title": "UDP Load Balancing",
        "vip": "10.1.10.112",
        "port": 514,
        "proto": "UDP",
        "dests": ["10.1.20.101", "10.1.20.102"],
        "count": 20,
        "desc": "Validates round-robin distribution across pool members in LoadBalance mode.",
    },
    {
        "id": 3,
        "ip_version": "IPv4",
        "version": "17.1",
        "service_name": "app_171_udp_failover",
        "test_type": "udp_failover",
        "title": "UDP Priority Failover",
        "vip": "10.1.10.113",
        "port": 514,
        "proto": "UDP",
        "dests": ["10.1.20.101", "10.1.20.102"],
        "primary_ip": "10.1.20.101",
        "count": 20,
        "desc": "Validates priority group dispatch to active primary (10.1.20.101) with gateway_icmp.",
    },
    {
        "id": 4,
        "ip_version": "IPv4",
        "version": "17.1",
        "service_name": "app_171_tcp_spray",
        "test_type": "tcp_duplication",
        "title": "TCP Stream Duplication",
        "vip": "10.1.10.114",
        "port": 9999,
        "proto": "TCP",
        "dests": ["10.1.20.101", "10.1.20.102", "10.1.20.103"],
        "count": 5,
        "desc": "Validates TCP connection handling and stream cloning across 3 destination sockets.",
    },

    # --- TMOS 17.5 IPv4 ---
    {
        "id": 5,
        "ip_version": "IPv4",
        "version": "17.5",
        "service_name": "app_175_udp_single",
        "test_type": "udp_duplication",
        "title": "UDP 1-to-3 Duplication",
        "vip": "10.1.10.151",
        "port": 514,
        "proto": "UDP",
        "dests": ["10.1.20.104", "10.1.20.105", "10.1.20.106"],
        "count": 5,
        "desc": "Validates 1-to-3 UDP packet replication with client IP preservation.",
    },
    {
        "id": 6,
        "ip_version": "IPv4",
        "version": "17.5",
        "service_name": "app_175_udp_lb",
        "test_type": "udp_loadbalance",
        "title": "UDP Load Balancing",
        "vip": "10.1.10.152",
        "port": 514,
        "proto": "UDP",
        "dests": ["10.1.20.104", "10.1.20.105"],
        "count": 20,
        "desc": "Validates round-robin distribution across pool members in LoadBalance mode.",
    },
    {
        "id": 7,
        "ip_version": "IPv4",
        "version": "17.5",
        "service_name": "app_175_udp_failover",
        "test_type": "udp_failover",
        "title": "UDP Priority Failover",
        "vip": "10.1.10.153",
        "port": 514,
        "proto": "UDP",
        "dests": ["10.1.20.104", "10.1.20.105"],
        "primary_ip": "10.1.20.104",
        "count": 20,
        "desc": "Validates priority group dispatch to active primary (10.1.20.104) with gateway_icmp.",
    },
    {
        "id": 8,
        "ip_version": "IPv4",
        "version": "17.5",
        "service_name": "app_175_tcp_spray",
        "test_type": "tcp_duplication",
        "title": "TCP Stream Duplication",
        "vip": "10.1.10.154",
        "port": 9999,
        "proto": "TCP",
        "dests": ["10.1.20.104", "10.1.20.105", "10.1.20.106"],
        "count": 5,
        "desc": "Validates TCP connection handling and stream cloning across 3 destination sockets.",
    },

    # --- TMOS 21.1 IPv4 ---
    {
        "id": 9,
        "ip_version": "IPv4",
        "version": "21.1",
        "service_name": "app_211_udp_single",
        "test_type": "udp_duplication",
        "title": "UDP 1-to-3 Duplication",
        "vip": "10.1.10.201",
        "port": 514,
        "proto": "UDP",
        "dests": ["10.1.20.107", "10.1.20.108", "10.1.20.109"],
        "count": 5,
        "desc": "Validates 1-to-3 UDP packet replication with client IP preservation.",
    },
    {
        "id": 10,
        "ip_version": "IPv4",
        "version": "21.1",
        "service_name": "app_211_udp_lb",
        "test_type": "udp_loadbalance",
        "title": "UDP Load Balancing",
        "vip": "10.1.10.202",
        "port": 514,
        "proto": "UDP",
        "dests": ["10.1.20.107", "10.1.20.108"],
        "count": 20,
        "desc": "Validates round-robin distribution across pool members in LoadBalance mode.",
    },
    {
        "id": 11,
        "ip_version": "IPv4",
        "version": "21.1",
        "service_name": "app_211_udp_failover",
        "test_type": "udp_failover",
        "title": "UDP Priority Failover",
        "vip": "10.1.10.203",
        "port": 514,
        "proto": "UDP",
        "dests": ["10.1.20.107", "10.1.20.108"],
        "primary_ip": "10.1.20.107",
        "count": 20,
        "desc": "Validates priority group dispatch to active primary (10.1.20.107) with gateway_icmp.",
    },
    {
        "id": 12,
        "ip_version": "IPv4",
        "version": "21.1",
        "service_name": "app_211_tcp_spray",
        "test_type": "tcp_duplication",
        "title": "TCP Stream Duplication",
        "vip": "10.1.10.204",
        "port": 9999,
        "proto": "TCP",
        "dests": ["10.1.20.107", "10.1.20.108", "10.1.20.109"],
        "count": 5,
        "desc": "Validates TCP connection handling and stream cloning across 3 destination sockets.",
    },
]

TEST_MATRIX_IPV6 = [
    # --- TMOS 17.1 IPv6 ---
    {
        "id": 13,
        "ip_version": "IPv6",
        "version": "17.1",
        "service_name": "app_171_v6_udp_single",
        "test_type": "udp_duplication",
        "title": "IPv6 UDP 1-to-3 Duplication",
        "vip": "fd00:1:1:10::111",
        "port": 514,
        "proto": "UDP",
        "dests": ["fd00:1:1:20::101", "fd00:1:1:20::102", "fd00:1:1:20::103"],
        "count": 5,
        "desc": "Validates IPv6 1-to-3 UDP packet replication with client IP preservation.",
    },
    {
        "id": 14,
        "ip_version": "IPv6",
        "version": "17.1",
        "service_name": "app_171_v6_udp_lb",
        "test_type": "udp_loadbalance",
        "title": "IPv6 UDP Load Balancing",
        "vip": "fd00:1:1:10::112",
        "port": 514,
        "proto": "UDP",
        "dests": ["fd00:1:1:20::101", "fd00:1:1:20::102"],
        "count": 20,
        "desc": "Validates IPv6 round-robin distribution across pool members in LoadBalance mode.",
    },
    {
        "id": 15,
        "ip_version": "IPv6",
        "version": "17.1",
        "service_name": "app_171_v6_udp_failover",
        "test_type": "udp_failover",
        "title": "IPv6 UDP Priority Failover",
        "vip": "fd00:1:1:10::113",
        "port": 514,
        "proto": "UDP",
        "dests": ["fd00:1:1:20::101", "fd00:1:1:20::102"],
        "primary_ip": "fd00:1:1:20::101",
        "count": 20,
        "desc": "Validates IPv6 priority group dispatch to active primary with health monitoring.",
    },
    {
        "id": 16,
        "ip_version": "IPv6",
        "version": "17.1",
        "service_name": "app_171_v6_tcp_spray",
        "test_type": "tcp_duplication",
        "title": "IPv6 TCP Stream Duplication",
        "vip": "fd00:1:1:10::114",
        "port": 9999,
        "proto": "TCP",
        "dests": ["fd00:1:1:20::101", "fd00:1:1:20::102", "fd00:1:1:20::103"],
        "count": 5,
        "desc": "Validates IPv6 TCP connection handling and stream cloning across 3 destination sockets.",
    },

    # --- TMOS 17.5 IPv6 ---
    {
        "id": 17,
        "ip_version": "IPv6",
        "version": "17.5",
        "service_name": "app_175_v6_udp_single",
        "test_type": "udp_duplication",
        "title": "IPv6 UDP 1-to-3 Duplication",
        "vip": "fd00:1:1:10::151",
        "port": 514,
        "proto": "UDP",
        "dests": ["fd00:1:1:20::104", "fd00:1:1:20::105", "fd00:1:1:20::106"],
        "count": 5,
        "desc": "Validates IPv6 1-to-3 UDP packet replication with client IP preservation.",
    },
    {
        "id": 18,
        "ip_version": "IPv6",
        "version": "17.5",
        "service_name": "app_175_v6_udp_lb",
        "test_type": "udp_loadbalance",
        "title": "IPv6 UDP Load Balancing",
        "vip": "fd00:1:1:10::152",
        "port": 514,
        "proto": "UDP",
        "dests": ["fd00:1:1:20::104", "fd00:1:1:20::105"],
        "count": 20,
        "desc": "Validates IPv6 round-robin distribution across pool members in LoadBalance mode.",
    },
    {
        "id": 19,
        "ip_version": "IPv6",
        "version": "17.5",
        "service_name": "app_175_v6_udp_failover",
        "test_type": "udp_failover",
        "title": "IPv6 UDP Priority Failover",
        "vip": "fd00:1:1:10::153",
        "port": 514,
        "proto": "UDP",
        "dests": ["fd00:1:1:20::104", "fd00:1:1:20::105"],
        "primary_ip": "fd00:1:1:20::104",
        "count": 20,
        "desc": "Validates IPv6 priority group dispatch to active primary with health monitoring.",
    },
    {
        "id": 20,
        "ip_version": "IPv6",
        "version": "17.5",
        "service_name": "app_175_v6_tcp_spray",
        "test_type": "tcp_duplication",
        "title": "IPv6 TCP Stream Duplication",
        "vip": "fd00:1:1:10::154",
        "port": 9999,
        "proto": "TCP",
        "dests": ["fd00:1:1:20::104", "fd00:1:1:20::105", "fd00:1:1:20::106"],
        "count": 5,
        "desc": "Validates IPv6 TCP connection handling and stream cloning across 3 destination sockets.",
    },

    # --- TMOS 21.1 IPv6 ---
    {
        "id": 21,
        "ip_version": "IPv6",
        "version": "21.1",
        "service_name": "app_211_v6_udp_single",
        "test_type": "udp_duplication",
        "title": "IPv6 UDP 1-to-3 Duplication",
        "vip": "fd00:1:1:10::201",
        "port": 514,
        "proto": "UDP",
        "dests": ["fd00:1:1:20::107", "fd00:1:1:20::108", "fd00:1:1:20::109"],
        "count": 5,
        "desc": "Validates IPv6 1-to-3 UDP packet replication with client IP preservation.",
    },
    {
        "id": 22,
        "ip_version": "IPv6",
        "version": "21.1",
        "service_name": "app_211_v6_udp_lb",
        "test_type": "udp_loadbalance",
        "title": "IPv6 UDP Load Balancing",
        "vip": "fd00:1:1:10::202",
        "port": 514,
        "proto": "UDP",
        "dests": ["fd00:1:1:20::107", "fd00:1:1:20::108"],
        "count": 20,
        "desc": "Validates IPv6 round-robin distribution across pool members in LoadBalance mode.",
    },
    {
        "id": 23,
        "ip_version": "IPv6",
        "version": "21.1",
        "service_name": "app_211_v6_udp_failover",
        "test_type": "udp_failover",
        "title": "IPv6 UDP Priority Failover",
        "vip": "fd00:1:1:10::203",
        "port": 514,
        "proto": "UDP",
        "dests": ["fd00:1:1:20::107", "fd00:1:1:20::108"],
        "primary_ip": "fd00:1:1:20::107",
        "count": 20,
        "desc": "Validates IPv6 priority group dispatch to active primary with health monitoring.",
    },
    {
        "id": 24,
        "ip_version": "IPv6",
        "version": "21.1",
        "service_name": "app_211_v6_tcp_spray",
        "test_type": "tcp_duplication",
        "title": "IPv6 TCP Stream Duplication",
        "vip": "fd00:1:1:10::204",
        "port": 9999,
        "proto": "TCP",
        "dests": ["fd00:1:1:20::107", "fd00:1:1:20::108", "fd00:1:1:20::109"],
        "count": 5,
        "desc": "Validates IPv6 TCP connection handling and stream cloning across 3 destination sockets.",
    },
]


class PacketCapture(threading.Thread):
    """Background sniffer using Linux AF_PACKET to capture and index IPv4 & IPv6 packets."""

    def __init__(self, interface: str, target_ports: list, target_ips: list):
        super().__init__(daemon=True)
        self.interface = interface
        self.target_ports = target_ports
        # Canonical normalization for matching regardless of IPv6 address representation
        self.target_ips = set(normalize_ip(ip) for ip in target_ips if ip)
        self.stop_event = threading.Event()
        self.captured_packets = []
        self.lock = threading.Lock()
        self.ready_event = threading.Event()

    def run(self):
        ETH_P_ALL = 0x0003
        ETH_P_IP = 0x0800
        ETH_P_IPV6 = 0x86DD

        try:
            sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_ALL))
            if self.interface:
                sock.bind((self.interface, 0))
            sock.settimeout(0.5)
            self.ready_event.set()
        except Exception as e:
            print(f"{RED}[ERROR] PacketCapture socket initialization failed: {e}{RESET}")
            self.ready_event.set()
            return

        while not self.stop_event.is_set():
            try:
                frame = sock.recvfrom(65535)[0]
                if len(frame) < 14:
                    continue

                eth_proto = struct.unpack("!H", frame[12:14])[0]

                # IPv4 Decoding
                if eth_proto == ETH_P_IP:
                    if len(frame) < 34:
                        continue
                    ip_start = 14
                    ip_ver_ihl = frame[ip_start]
                    ihl = (ip_ver_ihl & 0x0F) * 4
                    if len(frame) < ip_start + ihl + 8:
                        continue
                    ip_proto = frame[ip_start + 9]
                    src_ip = socket.inet_ntoa(frame[ip_start + 12 : ip_start + 16])
                    raw_dst_ip = socket.inet_ntoa(frame[ip_start + 16 : ip_start + 20])
                    dst_ip = normalize_ip(raw_dst_ip)
                    l4_start = ip_start + ihl

                # IPv6 Decoding
                elif eth_proto == ETH_P_IPV6:
                    if len(frame) < 54:
                        continue
                    ip_start = 14
                    ip_proto = frame[ip_start + 6]
                    src_ip = socket.inet_ntop(socket.AF_INET6, frame[ip_start + 8 : ip_start + 24])
                    raw_dst_ip = socket.inet_ntop(socket.AF_INET6, frame[ip_start + 24 : ip_start + 40])
                    dst_ip = normalize_ip(raw_dst_ip)
                    l4_start = ip_start + 40

                    # Traverse IPv6 extension headers if present
                    ext_headers = {0, 43, 44, 51, 60}
                    while ip_proto in ext_headers and len(frame) >= l4_start + 8:
                        if ip_proto == 44:  # Fragment Header (8 bytes)
                            ip_proto = frame[l4_start]
                            l4_start += 8
                        else:
                            next_hdr = frame[l4_start]
                            hdr_ext_len = (frame[l4_start + 1] + 1) * 8
                            ip_proto = next_hdr
                            l4_start += hdr_ext_len
                else:
                    continue

                if self.target_ips and dst_ip not in self.target_ips:
                    continue

                # UDP (17)
                if ip_proto == 17:
                    if len(frame) < l4_start + 8:
                        continue
                    src_port, dst_port, udp_len = struct.unpack("!HHH", frame[l4_start : l4_start + 6])
                    if dst_port in self.target_ports:
                        payload = frame[l4_start + 8 : l4_start + udp_len]
                        with self.lock:
                            self.captured_packets.append({
                                "proto": "UDP",
                                "src_ip": src_ip,
                                "src_port": src_port,
                                "dst_ip": dst_ip,
                                "dst_port": dst_port,
                                "payload": payload,
                                "timestamp": time.time(),
                            })

                # TCP (6)
                elif ip_proto == 6:
                    if len(frame) < l4_start + 20:
                        continue
                    src_port, dst_port = struct.unpack("!HH", frame[l4_start : l4_start + 4])
                    if dst_port in self.target_ports:
                        tcp_data_offset = (frame[l4_start + 12] >> 4) * 4
                        payload = frame[l4_start + tcp_data_offset :]
                        if payload:
                            with self.lock:
                                self.captured_packets.append({
                                    "proto": "TCP",
                                    "src_ip": src_ip,
                                    "src_port": src_port,
                                    "dst_ip": dst_ip,
                                    "dst_port": dst_port,
                                    "payload": payload,
                                    "timestamp": time.time(),
                                })
            except socket.timeout:
                continue
            except Exception:
                break

        sock.close()

    def get_matches(self, token: str):
        token_bytes = token.encode("utf-8")
        matches = []
        with self.lock:
            for p in self.captured_packets:
                if token_bytes in p["payload"]:
                    matches.append(p)
        return matches

    def clear(self):
        with self.lock:
            self.captured_packets.clear()

    def stop(self):
        self.stop_event.set()


class TcpServerListener(threading.Thread):
    """Listens on IPv4 or IPv6 destination IP/port to complete handshakes with BIG-IP and consume data."""

    def __init__(self, bind_ip: str, port: int):
        super().__init__(daemon=True)
        self.bind_ip = bind_ip
        self.port = port
        self.stop_event = threading.Event()
        self.server_sock = None
        self.family = get_addr_family(bind_ip)

    def run(self):
        try:
            self.server_sock = socket.socket(self.family, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except Exception:
                    pass
            if self.family == socket.AF_INET6:
                self.server_sock.bind((self.bind_ip, self.port, 0, 0))
            else:
                self.server_sock.bind((self.bind_ip, self.port))
            self.server_sock.listen(10)
            self.server_sock.settimeout(0.5)
        except Exception:
            return

        while not self.stop_event.is_set():
            try:
                client_sock, _ = self.server_sock.accept()
                t = threading.Thread(target=self._sink_client, args=(client_sock,), daemon=True)
                t.start()
            except socket.timeout:
                continue
            except Exception:
                break

        if self.server_sock:
            self.server_sock.close()

    def _sink_client(self, client_sock):
        client_sock.settimeout(1.0)
        try:
            while not self.stop_event.is_set():
                data = client_sock.recv(65535)
                if not data:
                    break
        except Exception:
            pass
        finally:
            client_sock.close()

    def stop(self):
        self.stop_event.set()


def execute_test(test_cfg: dict, interface: str) -> dict:
    """Executes a single test case (IPv4 or IPv6) and returns detailed log and metrics."""
    test_id = test_cfg["id"]
    test_type = test_cfg["test_type"]
    vip = test_cfg["vip"]
    port = test_cfg["port"]
    dests = [normalize_ip(d) for d in test_cfg["dests"]]
    count = test_cfg["count"]
    family = get_addr_family(vip)

    log_entries = []
    sniffer = PacketCapture(interface, [port], dests)
    sniffer.start()
    sniffer.ready_event.wait(timeout=2.0)

    tcp_servers = []
    t_start = time.time()
    passed = False
    expected_copies = 0
    received_copies = 0
    distribution = {}

    try:
        # 1. UDP Duplication
        if test_type == "udp_duplication":
            expected_copies = count * len(dests)
            sock = socket.socket(family, socket.SOCK_DGRAM)
            all_match = True

            for i in range(1, count + 1):
                token = f"TOKEN-{uuid.uuid4().hex[:8]}"
                msg = f"<13>1 {datetime.datetime.now(datetime.timezone.utc).isoformat()} test-host app {token} Duplication test packet #{i:02d}"
                sock.sendto(msg.encode("utf-8"), (vip, port))
                time.sleep(0.05)

                matches = sniffer.get_matches(token)
                found = [m["dst_ip"] for m in matches]
                received_copies += len(matches)
                status = "PASS" if len(matches) == len(dests) else "FAIL"
                if len(matches) != len(dests):
                    all_match = False

                for m in matches:
                    distribution[m["dst_ip"]] = distribution.get(m["dst_ip"], 0) + 1

                log_entries.append(f"  Packet #{i:02d} [{token}] -> Received {len(matches)}/{len(dests)} copies {found} [{status}]")

            sock.close()
            passed = all_match and (received_copies == expected_copies)

        # 2. UDP Load Balancing
        elif test_type == "udp_loadbalance":
            expected_copies = count
            token_prefix = f"LB-{uuid.uuid4().hex[:6]}"
            sock = socket.socket(family, socket.SOCK_DGRAM)

            for i in range(1, count + 1):
                token = f"{token_prefix}-{i:03d}"
                msg = f"<14>1 {datetime.datetime.now(datetime.timezone.utc).isoformat()} test-host app {token} Load balance verification #{i:02d}"
                sock.sendto(msg.encode("utf-8"), (vip, port))
                time.sleep(0.02)

            sock.close()
            time.sleep(0.3)

            matches = sniffer.get_matches(token_prefix)
            received_copies = len(matches)

            for m in matches:
                distribution[m["dst_ip"]] = distribution.get(m["dst_ip"], 0) + 1

            active_dests = [d for d in dests if distribution.get(d, 0) > 0]
            passed = (received_copies >= count) and (len(active_dests) > 1)

            for d in dests:
                cnt = distribution.get(d, 0)
                pct = (cnt / received_copies * 100.0) if received_copies > 0 else 0
                log_entries.append(f"  Destination {d:<35} : {cnt:2d} packets ({pct:5.1f}%)")

        # 3. UDP Failover
        elif test_type == "udp_failover":
            expected_copies = count
            primary_ip = normalize_ip(test_cfg.get("primary_ip", dests[0]))
            token_prefix = f"FO-{uuid.uuid4().hex[:6]}"
            sock = socket.socket(family, socket.SOCK_DGRAM)

            for i in range(1, count + 1):
                token = f"{token_prefix}-{i:03d}"
                msg = f"<14>1 {datetime.datetime.now(datetime.timezone.utc).isoformat()} test-host app {token} Failover test #{i:02d}"
                sock.sendto(msg.encode("utf-8"), (vip, port))
                time.sleep(0.02)

            sock.close()
            time.sleep(0.3)

            matches = sniffer.get_matches(token_prefix)
            received_copies = len(matches)

            for m in matches:
                distribution[m["dst_ip"]] = distribution.get(m["dst_ip"], 0) + 1

            primary_cnt = distribution.get(primary_ip, 0)
            passed = (primary_cnt == count)

            log_entries.append(f"  Primary Server ({primary_ip}) : {primary_cnt}/{count} packets (100% via Priority Group)")
            for d in dests:
                if d != primary_ip:
                    log_entries.append(f"  Standby Server ({d}) : {distribution.get(d, 0)} packets")

        # 4. TCP Duplication
        elif test_type == "tcp_duplication":
            expected_copies = count * len(dests)
            for ip in dests:
                srv = TcpServerListener(ip, port)
                srv.start()
                tcp_servers.append(srv)

            time.sleep(0.5)
            all_match = True

            try:
                sock = socket.socket(family, socket.SOCK_STREAM)
                sock.settimeout(3.0)
                sock.connect((vip, port))
                log_entries.append(f"  Connected to TCP VIP {vip}:{port} successfully.")

                for i in range(1, count + 1):
                    token = f"TCP-{uuid.uuid4().hex[:8]}"
                    msg = f"DATA: {token} TCP Stream payload message #{i:02d}\n"
                    sock.sendall(msg.encode("utf-8"))
                    time.sleep(0.15)

                    matches = sniffer.get_matches(token)
                    found = [m["dst_ip"] for m in matches]
                    received_copies += len(matches)
                    status = "PASS" if len(matches) == len(dests) else "FAIL"
                    if len(matches) != len(dests):
                        all_match = False

                    for m in matches:
                        distribution[m["dst_ip"]] = distribution.get(m["dst_ip"], 0) + 1

                    log_entries.append(f"  Stream Msg #{i:02d} [{token}] -> Received {len(matches)}/{len(dests)} copies {found} [{status}]")

                sock.close()
                passed = all_match and (received_copies == expected_copies)
            except Exception as e:
                log_entries.append(f"  TCP Connection Failed: {e}")
                passed = False

    finally:
        sniffer.stop()
        for srv in tcp_servers:
            srv.stop()

    duration = time.time() - t_start

    return {
        **test_cfg,
        "dests": dests,
        "passed": passed,
        "sent": count,
        "expected_copies": expected_copies,
        "received_copies": received_copies,
        "distribution": distribution,
        "duration": duration,
        "log_entries": log_entries,
    }


def generate_markdown_report(results: list, output_file: str, total_duration: float, interface: str, ip_ver_filter: str):
    """Renders comprehensive Markdown test report with top summary table and individual logs."""
    total_tests = len(results)
    passed_tests = sum(1 for r in results if r["passed"])
    pass_rate = (passed_tests / total_tests * 100.0) if total_tests > 0 else 0
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    md = []
    md.append("# F5 BIG-IP Traffic Duplication Test Matrix Report")
    md.append("")
    md.append(f"> **Generated on**: `{timestamp}` | **Sniff Interface**: `{interface}` | **IP Version Mode**: `{ip_ver_filter}` | **Total Execution Time**: `{total_duration:.2f}s`  ")
    md.append(f"> **Overall Result**: **`{passed_tests}/{total_tests} Tests Passed ({pass_rate:.1f}%)`**")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 1. Master Execution Summary")
    md.append("")
    md.append("| # | Family | Version | Service Name | Test Scenario | Target VIP | Protocol | Sent | Expected | Received | Status | Details |")
    md.append("| :-: | :---: | :--- | :--- | :--- | :--- | :--- | :-: | :-: | :-: | :--- | :--- |")

    for r in results:
        status_badge = "🟢 **PASS**" if r["passed"] else "🔴 **FAIL**"
        anchor_link = f"[View Log](#test-{r['id']}-{r['service_name'].replace('_', '-')})"
        exp_str = f">={r['expected_copies']}" if r["test_type"] == "udp_loadbalance" else str(r["expected_copies"])
        fam_badge = f"`{r.get('ip_version', 'IP')}`"
        md.append(f"| {r['id']} | {fam_badge} | **TMOS {r['version']}** | `{r['service_name']}` | {r['title']} | `{r['vip']}:{r['port']}` | `{r['proto']}` | {r['sent']} | {exp_str} | {r['received_copies']} | {status_badge} | {anchor_link} |")

    md.append("")
    md.append("---")
    md.append("")
    md.append("## 2. Detailed Test Results & Execution Logs")
    md.append("")

    for r in results:
        anchor_id = f"test-{r['id']}-{r['service_name'].replace('_', '-')}"
        status_text = "PASS" if r["passed"] else "FAIL"

        md.append(f"### <a id=\"{anchor_id}\"></a>Test #{r['id']}: TMOS {r['version']} ({r.get('ip_version', 'IP')}) - `{r['service_name']}`")
        md.append("")
        md.append(f"**Scenario**: {r['title']}  ")
        md.append(f"**Description**: {r['desc']}  ")
        md.append(f"**VIP Endpoint**: `{r['vip']}:{r['port']}` (`{r['proto']}`)  ")
        md.append(f"**Destination Pool**: `{', '.join(r['dests'])}`  ")
        md.append(f"**Execution Status**: **`{status_text}`** ({r['duration']:.2f}s)  ")
        md.append("")
        md.append("**Destination Distribution Table:**")
        md.append("")
        md.append("| Destination IP | Packets Received | Distribution % | Graph |")
        md.append("| :--- | :-: | :-: | :--- |")

        for d in r["dests"]:
            cnt = r["distribution"].get(d, 0)
            total = r["received_copies"]
            pct = (cnt / total * 100.0) if total > 0 else 0
            bar = "█" * int(pct / 10)
            md.append(f"| `{d}` | {cnt} | {pct:.1f}% | `{bar}` |")

        md.append("")
        md.append("**Execution Log Output:**")
        md.append("```text")
        for line in r["log_entries"]:
            md.append(line)
        md.append("```")
        md.append("")
        md.append("[▲ Back to Summary Table](#1-master-execution-summary)")
        md.append("")
        md.append("---")
        md.append("")

    content = "\n".join(md)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(description="Master Automated Test Runner for F5 BIG-IP Traffic Duplication Matrix (IPv4 & IPv6)")
    parser.add_argument("--interface", "-i", default="ens7", help="Server traffic network interface (default: ens7)")
    parser.add_argument("--ip-version", "-ip", choices=["4", "6", "all", "ipv4", "ipv6", "both"], default="4", help="Filter by IP address family (4, 6, all; default: 4)")
    parser.add_argument("-4", "--ipv4", action="store_true", help="Shortcut to run IPv4 test suite")
    parser.add_argument("-6", "--ipv6", action="store_true", help="Shortcut to run IPv6 test suite")
    parser.add_argument("--version", "-v", choices=["17.1", "17.5", "21.1", "all"], default="all", help="Filter by BIG-IP TMOS version")
    parser.add_argument("--test-id", "-t", type=int, help="Run specific test by ID (1-24)")
    parser.add_argument("--output", "-o", default="test_results.md", help="Output Markdown report path (default: test_results.md)")

    # Ad-hoc custom test flags
    parser.add_argument("--vip", help="Ad-hoc test: Custom VIP IP (IPv4 or IPv6)")
    parser.add_argument("--dests", help="Ad-hoc test: Comma-separated destination IPs (IPv4 or IPv6)")
    parser.add_argument("--port", type=int, default=514, help="Ad-hoc test: Port number (default: 514)")
    parser.add_argument("--proto", choices=["UDP", "TCP"], default="UDP", help="Ad-hoc test: Protocol (default: UDP)")
    parser.add_argument("--test-type", choices=["udp_duplication", "udp_loadbalance", "udp_failover", "tcp_duplication"], default="udp_duplication", help="Ad-hoc test type")
    parser.add_argument("--count", "-c", type=int, default=5, help="Number of packets for test")
    args = parser.parse_args()

    if os.geteuid() != 0 if hasattr(os, "geteuid") else False:
        print(f"{RED}[ERROR] Root privileges required for AF_PACKET raw frame capture. Please run with sudo.{RESET}")
        sys.exit(1)

    # Resolve IP Version filter
    ip_filter = args.ip_version.lower()
    if args.ipv6:
        ip_filter = "6"
    elif args.ipv4:
        ip_filter = "4"

    if ip_filter in ["4", "ipv4"]:
        candidate_tests = TEST_MATRIX_IPV4
        ip_label = "IPv4 (1-12)"
    elif ip_filter in ["6", "ipv6"]:
        candidate_tests = TEST_MATRIX_IPV6
        ip_label = "IPv6 (13-24)"
    else:
        candidate_tests = TEST_MATRIX_IPV4 + TEST_MATRIX_IPV6
        ip_label = "Dual-Stack (IPv4 & IPv6, 1-24)"

    # Handle ad-hoc test case override
    if args.vip:
        dests_list = [d.strip() for d in (args.dests or "").split(",") if d.strip()]
        if not dests_list:
            print(f"{RED}[ERROR] When specifying --vip, --dests must also be provided.{RESET}")
            sys.exit(1)

        vip_v6 = is_ipv6(args.vip)
        candidate_tests = [{
            "id": 99,
            "ip_version": "IPv6" if vip_v6 else "IPv4",
            "version": "Custom",
            "service_name": "custom_adhoc_test",
            "test_type": args.test_type,
            "title": f"Custom {'IPv6' if vip_v6 else 'IPv4'} {args.test_type.replace('_', ' ').title()}",
            "vip": args.vip,
            "port": args.port,
            "proto": args.proto,
            "dests": dests_list,
            "count": args.count,
            "desc": f"Custom ad-hoc verification against VIP {args.vip}:{args.port}.",
        }]
        ip_label = f"Ad-Hoc Custom ({'IPv6' if vip_v6 else 'IPv4'})"

    # Filter tests by version / test_id
    selected_tests = candidate_tests
    if args.version != "all" and not args.vip:
        selected_tests = [t for t in selected_tests if t["version"] == args.version]
    if args.test_id and not args.vip:
        selected_tests = [t for t in selected_tests if t["id"] == args.test_id]

    if not selected_tests:
        print(f"{YELLOW}[WARNING] No tests matched the specified filters (Version: {args.version}, IP: {ip_filter}, Test-ID: {args.test_id}).{RESET}")
        sys.exit(0)

    print(f"\n{BOLD}{CYAN}==========================================================================={RESET}")
    print(f"{BOLD}   F5 BIG-IP TRAFFIC DUPLICATION MASTER TEST RUNNER (IPv4 & IPv6){RESET}")
    print(f"{BOLD}{CYAN}==========================================================================={RESET}")
    print(f"  Sniff Interface : {args.interface}")
    print(f"  IP Stack Mode   : {ip_label}")
    print(f"  Target Versions : {args.version}")
    print(f"  Total Tests     : {len(selected_tests)}")
    print(f"  Output Report   : {args.output}\n")

    results = []
    t_global_start = time.time()

    for idx, test_cfg in enumerate(selected_tests, 1):
        print(f"{BOLD}[{idx:02d}/{len(selected_tests):02d}] Running Test #{test_cfg['id']}: TMOS {test_cfg['version']} ({test_cfg.get('ip_version', 'IP')}) - {test_cfg['service_name']} ({test_cfg['title']})...{RESET}")
        res = execute_test(test_cfg, args.interface)
        results.append(res)

        status = f"{GREEN}PASS{RESET}" if res["passed"] else f"{RED}FAIL{RESET}"
        print(f"      -> Status: {status} (Sent: {res['sent']}, Recv: {res['received_copies']}, Duration: {res['duration']:.2f}s)\n")

    t_global_end = time.time()
    total_duration = t_global_end - t_global_start

    # Generate Markdown Report
    generate_markdown_report(results, args.output, total_duration, args.interface, ip_label)

    # Summary Console Output
    total_pass = sum(1 for r in results if r["passed"])
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}                    EXECUTION MATRIX SUMMARY REPORT{RESET}")
    print(f"{BOLD}{'='*80}{RESET}")
    print(f"{'#':<3} | {'Fam':<4} | {'Version':<8} | {'Service Name':<23} | {'VIP':<20} | {'Recv/Exp':<10} | {'Status':<6}")
    print(f"{'-'*80}")
    for r in results:
        st = f"{GREEN}PASS{RESET}" if r["passed"] else f"{RED}FAIL{RESET}"
        exp = f">={r['expected_copies']}" if r["test_type"] == "udp_loadbalance" else str(r["expected_copies"])
        recv_str = f"{r['received_copies']}/{exp}"
        fam = r.get("ip_version", "IP")
        print(f"{r['id']:<3} | {fam:<4} | TMOS {r['version']:<3} | {r['service_name']:<23} | {r['vip']:<20} | {recv_str:<10} | {st}")
    print(f"{'='*80}")
    summary_color = GREEN if total_pass == len(results) else RED
    print(f"{BOLD}Final Verdict: {summary_color}{total_pass}/{len(results)} Tests Passed{RESET} ({total_duration:.2f}s total)")
    print(f"Detailed Markdown Report written to: {BOLD}{args.output}{RESET}\n")


if __name__ == "__main__":
    main()
