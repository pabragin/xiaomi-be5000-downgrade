# Xiaomi BE5000: downgrade stock firmware to 1.0.53 over Ethernet

Русская инструкция: [README.md](README.md).

This repository contains a DHCP/TFTP server for **macOS, Linux, and Windows**.
It serves Xiaomi's signed stock firmware to the BE5000 recovery bootloader.
The script does not write flash directly or bypass rollback checks. It has
been hardware-tested on a BE5000 with macOS; Linux and Windows are code-tested
only. Python 3.8 or newer is required.

## Quick downgrade sequence

This sequence follows the reported BE5000 1.0.91 case and [the forum method](https://www.right.com.cn/forum/thread-8470335-1-1.html).
It intentionally interrupts firmware writes to clear both system copies.
This can leave the router unbootable and require UART or a flash programmer.

1. Prepare the computer and cable as described below. Connect to the router's
   **first Ethernet port (LAN1)**. If the BE5000 currently runs 1.0.91, start
   the helper with that same image:
   `sudo python3 recover.py --interface INTERFACE --firmware 1.0.91`.
2. Hold Reset while powering on; release it when the LED starts blinking
   yellow. Wait for 100% and `TFTP transfer complete`.
3. During the **1.0.91** cleanup cycle, wait about **10 seconds** after the
   full transfer and unplug the router. Enter recovery again, serve 1.0.91,
   wait for 100%, then wait about **20 seconds** and unplug again. These times
   are approximate.
4. Repeat the 1.0.91 recovery cycle as needed. If, after a 1.0.53 transfer
   reaches 100%, the LED immediately turns steady yellow, the system partition
   cleanup likely did not finish; repeat the cleanup cycles in steps 2–4 with
   the 1.0.91 image.
5. Once cleanup is complete, stop the server and restart it with
   `--firmware 1.0.53`. Enter Reset recovery and let the full transfer and
   installation finish. Verify `romversion: 1.0.53` through the API.

A 100% TFTP transfer confirms only that the file was sent. It does not confirm
that partitions were cleared or firmware was installed. LED behavior and power
interruption timings are observations from specific attempts, not guarantees.

Files: `recover.py` is the only program; [POST.md](POST.md) and
[POST.en.md](POST.en.md) document the original attempt in Russian and English;
[LOG_EXAMPLE.md](LOG_EXAMPLE.md) contains an anonymized log excerpt.

The firmware binary is not stored in this repository. If it is absent,
`recover.py` downloads the selected official image before starting DHCP/TFTP:
[1.0.91](https://cdn.cnbj1.fds.api.mi-img.com/xiaoqiang/rom/rd18/miwifi_rd18_firmware_05f43_1.0.91.bin)
and [1.0.53](https://cdn.cnbj1.fds.api.mi-img.com/xiaoqiang/rom/rd18/miwifi_rd18_firmware_6c571_1.0.53.bin).
The script verifies each image's pinned size and SHA-256. Download both first with
`python3 recover.py --firmware 1.0.91 --download-only` and
`python3 recover.py --firmware 1.0.53 --download-only` (Windows: replace
`python3` with `py -3`). Internet is not needed during recovery.

## 1. Prepare the connection

Clone this repository or download its ZIP from GitHub:

```sh
git clone https://github.com/pabragin/xiaomi-be5000-downgrade.git
cd xiaomi-be5000-downgrade
```

Connect the computer directly to the **first Ethernet port (LAN1)** of the
Xiaomi BE5000. This is the port used in the successful attempt. Disconnect the router's
WAN cable and other clients. Recovery uses Ethernet, not the router's Wi-Fi.
Make sure no other DHCP or TFTP server is using UDP ports 67 or 69. On
macOS/Linux, inspect them with `sudo lsof -nP -iUDP:67 -iUDP:69`.

## 2. Start the server

**macOS:** Find the Ethernet interface with `networksetup -listallhardwareports`.
The USB Ethernet adapter in the original attempt was `en8`:

```sh
sudo /usr/bin/python3 recover.py --interface en8 --firmware 1.0.91
```

**Linux:** Find the interface with `ip -br link` and substitute its name:

```sh
sudo python3 recover.py --interface enp3s0 --firmware 1.0.91
```

On macOS/Linux the script adds `192.168.31.100/24` temporarily and removes
it when stopped.

**Windows (experimental, not hardware-tested):** Use Python 3.8+ and an
Administrator PowerShell. Download the firmware while internet is available:

```powershell
py -3 recover.py --firmware 1.0.91 --download-only
py -3 recover.py --firmware 1.0.53 --download-only
```

Manually set the Ethernet adapter to IPv4 `192.168.31.100`, mask
`255.255.255.0`, with no gateway. Disable Wi-Fi and other adapters before
starting the server, so DHCP broadcasts use the cable to the router. Find
the adapter name with `Get-NetAdapter`, then substitute it below:

```powershell
py -3 recover.py --interface "Ethernet" --firmware 1.0.91
```

Allow Python on the private network if Windows Firewall asks. Restore the
adapter's usual IPv4 settings when finished. Windows cannot use the same
macOS/Linux interface binding or automatic address setup in this script, so
check its logs carefully.

## 3. Run recovery and verify

Use `--firmware 1.0.91` for the partition cleanup stage. Stop the server and
restart it with `--firmware 1.0.53` for the downgrade. For example on macOS:

```sh
sudo /usr/bin/python3 recover.py --interface en8 --firmware 1.0.91
sudo /usr/bin/python3 recover.py --interface en8 --firmware 1.0.53
```

For each cycle, wait for `TFTP listening` and `DHCP listening`, then power on
while holding Reset and release when the LED blinks yellow. Wait for
`TFTP transfer complete` and 100%. Apply the power interruptions in steps 2–4
to the 1.0.91 cleanup cycle. If the LED turns steady yellow after the 1.0.53
transfer reaches 100%, repeat the 1.0.91 cleanup cycle, then retry 1.0.53.

Verify the result at `http://192.168.31.1/` or:

```sh
curl -fsS 'http://192.168.31.1/cgi-bin/luci/api/xqsystem/init_info'
```

Confirm `romversion: 1.0.53`. The internal `hardware` field may show the
platform identifier `RD18`. Stop the server with `Ctrl+C`.

The script recognizes the recovery bootloader by its DHCP `tclinux.bin`
bootfile field and locks onto that client's MAC address. If detection fails,
you may supply `--router-mac MAC_ADDRESS` using the bootloader MAC as six
colon-separated hexadecimal pairs. Redact MAC addresses before sharing logs.
