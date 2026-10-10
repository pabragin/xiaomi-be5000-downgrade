#!/usr/bin/env python3
"""Serve a Xiaomi RD18 1.0.53 recovery image over isolated Ethernet DHCP/TFTP.

This only transfers the signed image. The router's bootloader decides whether
to accept and flash it. See README.md for macOS, Linux, and Windows setup.
"""

import argparse
import errno
import hashlib
import os
import platform
import re
import signal
import socket
import struct
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path


SERVER_IP = "192.168.31.100"
CLIENT_IP = "192.168.31.111"
MASK = "255.255.255.0"
FILENAME = "miwifi_rd18_firmware_6c571_1.0.53.bin"
FIRMWARE_URL = "https://cdn.cnbj1.fds.api.mi-img.com/xiaoqiang/rom/rd18/" + FILENAME
SHA256 = "cdc567abd5b9d4ff10adb02ee9592575640e5607135a4588f05e7bdc2cab17d0"
IMAGE_SIZE = 31069192
SYSTEM = platform.system()
IP_BOUND_IF = 25  # macOS <netinet/in.h>
IP_PKTINFO = 26 if SYSTEM == "Darwin" else 8  # macOS / Linux
MAGIC = b"\x63\x82\x53\x63"
STOP = threading.Event()


def log(message):
    print(time.strftime("%H:%M:%S"), message, flush=True)


def ip_bytes(address):
    return socket.inet_aton(address)


def bind_interface(sock, interface):
    if SYSTEM == "Darwin":
        sock.setsockopt(socket.IPPROTO_IP, IP_BOUND_IF, socket.if_nametoindex(interface))
    elif SYSTEM == "Linux":
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BINDTODEVICE, interface.encode() + b"\0")


def send_dhcp_reply(sock, interface, packet, destination):
    if SYSTEM == "Windows":
        # Windows Python sockets have no sendmsg(). Use the isolated Ethernet
        # link with a static SERVER_IP so the route selects that interface.
        sock.sendto(packet, (destination, 68))
        return
    packet_info = struct.pack(
        "=I4s4s", socket.if_nametoindex(interface), ip_bytes(SERVER_IP), b"\0" * 4
    )
    sock.sendmsg(
        [packet], [(socket.IPPROTO_IP, IP_PKTINFO, packet_info)],
        0, (destination, 68),
    )


def parse_options(data):
    result = {}
    if len(data) < 240 or data[236:240] != MAGIC:
        return result
    index = 240
    while index < len(data):
        code = data[index]
        index += 1
        if code == 255:
            break
        if code == 0:
            continue
        if index >= len(data):
            break
        length = data[index]
        index += 1
        if index + length > len(data):
            break
        result[code] = data[index:index + length]
        index += length
    return result


def dhcp_reply(request, kind):
    # RFC 2131 BOOTP fixed header, followed by DHCP options.
    xid = request[4:8]
    chaddr = request[28:44]
    bootfile = FILENAME.encode("ascii").ljust(128, b"\0")
    fixed = struct.pack(
        "!BBBB4sHH4s4s4s4s16s64s128s",
        2, 1, 6, 0, xid, 0, 0x8000,
        b"\0" * 4, ip_bytes(CLIENT_IP), ip_bytes(SERVER_IP), b"\0" * 4,
        chaddr, b"\0" * 64, bootfile,
    )
    options = bytearray(MAGIC)
    for code, value in (
        (53, bytes([kind])),              # DHCPOFFER=2 or DHCPACK=5
        (54, ip_bytes(SERVER_IP)),        # server identifier
        (1, ip_bytes(MASK)),              # subnet mask
        (3, ip_bytes(SERVER_IP)),         # router
        (6, ip_bytes(SERVER_IP)),         # DNS (not used in recovery)
        (51, struct.pack("!I", 600)),    # lease time
        (66, SERVER_IP.encode("ascii")), # TFTP server name
        (67, FILENAME.encode("ascii")),  # bootfile name
    ):
        options.extend((code, len(value)))
        options.extend(value)
    options.append(255)
    return fixed + bytes(options)


def dhcp_server(interface, expected_mac):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    bind_interface(sock, interface)
    sock.bind(("0.0.0.0", 67))
    sock.settimeout(1)
    log(f"DHCP listening on {interface}:67; offering {CLIENT_IP}")
    recovery_mac = expected_mac
    try:
        while not STOP.is_set():
            try:
                data, source = sock.recvfrom(2048)
            except socket.timeout:
                continue
            if len(data) < 240 or data[0] != 1:
                continue
            options = parse_options(data)
            kind = options.get(53, b"\0")[:1]
            mac = ":".join(f"{byte:02x}" for byte in data[28:34])
            bootfile = data[108:236].split(b"\0", 1)[0]
            if recovery_mac is None:
                if bootfile != b"tclinux.bin":
                    log(f"DHCP from {mac} without RD18 recovery bootfile; ignored")
                    continue
                recovery_mac = mac
                log(f"Recovery client locked to {recovery_mac}")
            elif mac != recovery_mac:
                log(f"DHCP from other device {mac}; ignored")
                continue
            if kind == b"\x01":
                response_kind, label = 2, "DISCOVER -> OFFER"
            elif kind == b"\x03":
                response_kind, label = 5, "REQUEST -> ACK"
            else:
                log(f"DHCP type {kind.hex()} from {mac}; ignored")
                continue
            log(f"DHCP {label} {CLIENT_IP} to {mac} ({source[0]})")
            # Receive broadcasts on 0.0.0.0, then send from the recovery
            # interface where the platform supports source-address control.
            reply = dhcp_reply(data, response_kind)
            try:
                send_dhcp_reply(sock, interface, reply, "255.255.255.255")
            except OSError as error:
                if error.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH):
                    try:
                        send_dhcp_reply(sock, interface, reply, "192.168.31.255")
                        log(f"DHCP reply sent via {interface} subnet broadcast")
                    except OSError as fallback_error:
                        log(f"Ethernet route not ready ({fallback_error}); waiting for the next DHCP request")
                    continue
                raise
    finally:
        sock.close()


def parse_rrq(packet):
    if len(packet) < 4 or packet[:2] != b"\0\x01":
        raise ValueError("not a TFTP read request")
    fields = packet[2:].split(b"\0")
    if len(fields) < 3 or not fields[0] or fields[1].lower() != b"octet":
        raise ValueError("invalid filename or transfer mode")
    name = fields[0].decode("ascii", "replace")
    options = {}
    for i in range(2, len(fields) - 1, 2):
        if fields[i] and i + 1 < len(fields):
            options[fields[i].decode("ascii", "replace").lower()] = fields[i + 1].decode("ascii", "replace")
    return name, options


def permitted_filename(name):
    return name == FILENAME or bool(re.fullmatch(r"C0A81F[0-9A-Fa-f]{2}\.img", name))


def send_error(sock, peer, message):
    sock.sendto(b"\0\x05\0\x01" + message.encode("ascii") + b"\0", peer)


def tftp_transfer(interface, image, peer, options, cancel=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bind_interface(sock, interface)
    sock.bind((SERVER_IP, 0))
    sock.settimeout(3)
    block_size = 512
    accepted = {}
    if "blksize" in options:
        try:
            block_size = max(8, min(int(options["blksize"]), 1468))
            accepted["blksize"] = str(block_size)
        except ValueError:
            pass
    if "tsize" in options:
        accepted["tsize"] = str(image.stat().st_size)
    if "timeout" in options:
        accepted["timeout"] = options["timeout"]
    try:
        if accepted:
            payload = b"\0\x06" + b"".join(
                key.encode() + b"\0" + value.encode() + b"\0"
                for key, value in accepted.items()
            )
            if not exchange(sock, peer, payload, 0, cancel):
                log("TFTP client did not acknowledge options")
                return
        total = image.stat().st_size
        sent = 0
        milestone = 10
        with image.open("rb") as stream:
            block = 1
            while not STOP.is_set() and not (cancel and cancel.is_set()):
                chunk = stream.read(block_size)
                packet = struct.pack("!HH", 3, block & 0xFFFF) + chunk
                if not exchange(sock, peer, packet, block & 0xFFFF, cancel):
                    log(f"TFTP stopped after {sent:,} of {total:,} bytes")
                    return
                sent += len(chunk)
                percent = sent * 100 // total
                if percent >= milestone:
                    log(f"TFTP {percent}% ({sent:,}/{total:,} bytes)")
                    milestone += 10
                if len(chunk) < block_size:
                    log(f"TFTP transfer complete: {sent:,} bytes. Waiting for router verification.")
                    return
                block += 1
    finally:
        sock.close()


def exchange(sock, peer, packet, expected_ack, cancel=None):
    for _ in range(8):
        if STOP.is_set() or (cancel and cancel.is_set()):
            return False
        sock.sendto(packet, peer)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                reply, source = sock.recvfrom(2048)
            except socket.timeout:
                break
            if source != peer:
                continue
            if cancel and cancel.is_set():
                return False
            if len(reply) >= 4 and reply[:2] == b"\0\x04":
                ack = struct.unpack("!H", reply[2:4])[0]
                if ack == expected_ack:
                    return True
                if ack == ((expected_ack - 1) & 0xFFFF):
                    continue
            elif len(reply) >= 4 and reply[:2] == b"\0\x05":
                log("TFTP client error: " + reply[4:].split(b"\0")[0].decode("ascii", "replace"))
                return False
    return False


def tftp_server(interface, image):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    bind_interface(sock, interface)
    sock.bind((SERVER_IP, 69))
    sock.settimeout(1)
    log(f"TFTP listening on {SERVER_IP}:69")
    active_transfer = None
    try:
        while not STOP.is_set():
            try:
                packet, peer = sock.recvfrom(2048)
            except socket.timeout:
                continue
            if peer[0] != CLIENT_IP:
                log(f"TFTP request from unexpected address {peer[0]}; ignored")
                continue
            try:
                name, options = parse_rrq(packet)
            except ValueError as error:
                log(f"TFTP invalid request: {error}")
                continue
            log(f"TFTP RRQ {name!r} from {peer[0]} options={options}")
            if not permitted_filename(name):
                log("TFTP filename not recognized for RD18; no image sent")
                send_error(sock, peer, "Unexpected recovery filename")
                continue
            if active_transfer is not None:
                active_transfer.set()
            active_transfer = threading.Event()
            thread = threading.Thread(target=tftp_transfer, args=(interface, image, peer, options, active_transfer), daemon=True)
            thread.start()
    finally:
        sock.close()


def ensure_alias(interface):
    if SYSTEM == "Windows":
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.bind((SERVER_IP, 0))
        except OSError as error:
            raise SystemExit(
                f"Set Ethernet adapter '{interface}' to static {SERVER_IP}/24 before starting: {error}"
            ) from error
        finally:
            probe.close()
        log(f"Using manually configured {SERVER_IP}/24 on {interface}")
        return False
    if SYSTEM == "Darwin":
        output = subprocess.check_output(["ifconfig", interface], text=True)
        if re.search(r"\binet " + re.escape(SERVER_IP) + r"\b", output):
            log(f"{SERVER_IP} already assigned to {interface}; leaving it in place on exit")
            return False
        subprocess.check_call(["ifconfig", interface, "alias", SERVER_IP, "netmask", MASK])
    else:
        output = subprocess.check_output(["ip", "-o", "-4", "addr", "show", "dev", interface], text=True)
        if f"inet {SERVER_IP}/24" in output:
            log(f"{SERVER_IP}/24 already assigned to {interface}; leaving it in place on exit")
            return False
        subprocess.check_call(["ip", "address", "add", f"{SERVER_IP}/24", "dev", interface])
    log(f"Added temporary {SERVER_IP}/24 address on {interface}")
    return True


def remove_alias(interface):
    if SYSTEM == "Darwin":
        subprocess.check_call(["ifconfig", interface, "-alias", SERVER_IP])
    elif SYSTEM == "Linux":
        subprocess.check_call(["ip", "address", "del", f"{SERVER_IP}/24", "dev", interface])
    log(f"Removed temporary {SERVER_IP} address")


def check_link(interface):
    if SYSTEM == "Darwin":
        details = subprocess.check_output(["ifconfig", interface], text=True)
        if "status: active" not in details:
            log(f"{interface} has no Ethernet link yet; waiting for the router to power on")
    elif SYSTEM == "Linux":
        socket.if_nametoindex(interface)
        carrier = Path("/sys/class/net") / interface / "carrier"
        if carrier.exists() and carrier.read_text().strip() != "1":
            log(f"{interface} has no Ethernet link yet; waiting for the router to power on")


def verify_image(image):
    digest = hashlib.sha256()
    with image.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != SHA256 or image.stat().st_size != IMAGE_SIZE:
        raise SystemExit("Firmware hash or size mismatch; refusing to serve it")
    log(f"Verified RD18 1.0.53 image: {image.stat().st_size:,} bytes, SHA-256 {SHA256}")


def download_image(image):
    log(f"Firmware not found; downloading official RD18 1.0.53 image from {FIRMWARE_URL}")
    temporary = None
    try:
        with urllib.request.urlopen(FIRMWARE_URL, timeout=30) as response:
            with tempfile.NamedTemporaryFile(dir=image.parent, prefix=FILENAME + ".", suffix=".part", delete=False) as output:
                temporary = Path(output.name)
                digest = hashlib.sha256()
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > IMAGE_SIZE:
                        raise ValueError("download exceeds expected firmware size")
                    digest.update(chunk)
                    output.write(chunk)
        if size != IMAGE_SIZE or digest.hexdigest() != SHA256:
            raise ValueError("downloaded firmware size or SHA-256 does not match")
        os.chmod(temporary, 0o644)
        os.replace(temporary, image)
        log("Official firmware downloaded and verified")
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interface", help="Ethernet interface connected directly to BE5000")
    parser.add_argument("--router-mac", help="Optional recovery-mode MAC if automatic detection fails")
    parser.add_argument("--download-only", action="store_true", help="Download and verify the official image, then exit")
    args = parser.parse_args()
    if SYSTEM not in ("Darwin", "Linux", "Windows"):
        raise SystemExit(f"Unsupported operating system: {SYSTEM}")
    image = Path(__file__).resolve().parent / FILENAME
    if not image.exists():
        download_image(image)
    verify_image(image)
    if args.download_only:
        return
    if not args.interface:
        parser.error("--interface is required unless --download-only is used")
    if SYSTEM != "Windows" and os.geteuid() != 0:
        raise SystemExit("Run with sudo so DHCP/TFTP can use UDP ports 67 and 69")
    expected_mac = args.router_mac.lower() if args.router_mac else None
    if expected_mac and not re.fullmatch(r"[0-9a-f]{2}(:[0-9a-f]{2}){5}", expected_mac):
        parser.error("--router-mac must contain six hexadecimal octets separated by colons")
    interface = args.interface
    check_link(interface)
    added = ensure_alias(interface)
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda _s, _f: STOP.set())
    def thread_error(details):
        log(f"Server error in {details.thread.name}: {details.exc_value}")
        STOP.set()
    threading.excepthook = thread_error
    try:
        dhcp_thread = threading.Thread(target=dhcp_server, args=(interface, expected_mac), name="DHCP", daemon=True)
        dhcp_thread.start()
        tftp_server(interface, image)
    finally:
        STOP.set()
        if added:
            remove_alias(interface)


if __name__ == "__main__":
    main()
