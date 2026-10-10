# Xiaomi BE5000: downgrade stock firmware to 1.0.53 over Ethernet

Русская инструкция: [README.md](README.md).

This repository contains a DHCP/TFTP server for **macOS, Linux, and Windows**.
It serves Xiaomi's signed stock firmware to the BE5000 recovery bootloader.
The script does not write flash directly or bypass rollback checks. It has
been hardware-tested on a BE5000 with macOS; Linux and Windows are code-tested
only. Python 3.8 or newer is required.

## Quick downgrade sequence

This sequence follows a BE5000 owner's reported 1.0.88 → 1.0.53 downgrade and
the [detailed BE5000 method report](https://www.right.com.cn/forum/thread-8470335-1-1.html).
The original report's router was on 1.0.87, so its author first upgraded to
1.0.91. In the case documented here, the router already ran 1.0.91, so the
cleanup cycles started with that version. Both cases then use two interrupted
1.0.91 writes followed by a 1.0.53 install through stock recovery. The original
report also includes LED observations and approximate timings. Interrupting a
flash write is risky and may require UART or a flash programmer.

1. Connect the computer by Ethernet cable to the router's **first Ethernet
   port (LAN1)** and choose one file-serving option:
   `recover.py` (macOS/Linux/Windows) or Xiaomi's official
   [MiWiFi Repair Tool](https://cdn.cnbj1.fds.api.mi-img.com/xiaoqiang/tools/MIWIFIRepairTool.x86.zip)
   (Windows). Do not run both at once. Select image **1.0.91**.
2. Start the selected server/tool and choose the 1.0.91 image. Hold Reset while
   powering on; release it when the LED starts blinking yellow. Wait for 100%
   transfer. With `recover.py`, also wait for `TFTP transfer complete`.
3. After the first 1.0.91 transfer, wait about **10 seconds** and unplug the
   router. Enter Reset recovery again with the same 1.0.91 image and wait for
   100%.
4. After the second transfer, wait about **20 seconds** and unplug it again.
   These are the timings from our attempt; they are approximate and may differ
   from other reports.
5. End the current attempt and switch to the 1.0.53 image. With `recover.py`,
   stop and restart the server using
   `sudo python3 recover.py --interface INTERFACE --firmware 1.0.53`; in
   MiWiFi Repair Tool, select 1.0.53. Enter Reset recovery, wait for 100%, and
   let installation finish and the router boot. Verify `romversion: 1.0.53`
   through the API.
6. If the LED turns steady yellow immediately after the **1.0.53** transfer
   reaches 100%, system partition cleanup likely did not finish. Return to
   steps 2–4 with the 1.0.91 image, then repeat step 5.

A 100% TFTP transfer confirms only that the file was sent. It does not confirm
that partitions were cleared or firmware was installed. LED behavior and power
interruption timings are observations from our case, not guarantees.

MiWiFi Repair Tool is Xiaomi's Windows recovery utility and serves the recovery
file itself. On macOS and Linux, use `recover.py` or another DHCP/TFTP server
configured for the recovery bootloader. Both options use the same official
firmware images and the same recovery sequence.

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

### Alternative: Xiaomi MiWiFi Repair Tool

Download [Xiaomi's official MiWiFi Repair Tool](https://cdn.cnbj1.fds.api.mi-img.com/xiaoqiang/tools/MIWIFIRepairTool.x86.zip)
and extract it on Windows. Connect the computer to LAN1, set the Ethernet
adapter to `192.168.31.100/24`, and disable Wi-Fi. Select the required official
image in the tool and start recovery. Select 1.0.91 for both cleanup cycles,
then select 1.0.53 in a separate attempt. The tool replaces `recover.py` only
as the file-serving method. This tool and procedure are described in the linked
forum reports, but this combination has not been independently tested by this
repository's author.

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
