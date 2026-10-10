# Xiaomi BE5000 (RD18): stock 1.0.53 recovery over Ethernet

Русская инструкция: [README.md](README.md).

This repository contains a Python DHCP/TFTP recovery server for **macOS,
Linux, and Windows**. It serves Xiaomi's signed RD18 firmware 1.0.53 to the
router's recovery bootloader. The script does not write flash directly or
bypass rollback checks. A completed TFTP transfer alone does not prove that
the router installed 1.0.53. The documented downgrade is one real case, not
a guaranteed procedure for every BE5000.
Python 3.8 or newer is required. The RD18 transfer was hardware-tested on
macOS; Linux and Windows have only been checked at the code level so far.

## Quick downgrade sequence

This is the sequence that worked on one RD18. The helper serves firmware
**1.0.53** on every recovery cycle below.

1. Prepare the connection and start `recover.py` as described below. Connect
   the cable to the router's first Ethernet port (LAN1).
2. Power on the router while holding Reset. Release Reset when the LED starts
   blinking yellow. Wait for `TFTP transfer complete` and 100% progress.
3. If the LED is still off after the transfer, wait about **10 seconds** and
   unplug the router.
4. Enter Reset recovery again and wait for the 1.0.53 transfer to complete.
   If the LED is still off, wait about **20 seconds after 100%** and unplug
   the router again.
5. Enter Reset recovery once more, let the full 1.0.53 transfer finish, and
   leave the router powered on to boot. After a successful downgrade, the
   status LED may not turn yellow immediately. Verify `romversion` through
   the API below.

Power interruptions after TFTP are a risky step from one personal attempt,
not a guaranteed procedure: the router may still be checking or writing the
image. It can fail to boot and require UART or a flash programmer. The sequence
was inspired by [this forum thread](https://www.right.com.cn/forum/thread-8470335-1-1.html).

Files: `recover.py` is the only program; [POST.md](POST.md) and
[POST.en.md](POST.en.md) document the original attempt in Russian and English;
[LOG_EXAMPLE.md](LOG_EXAMPLE.md) contains an anonymized log excerpt.

The firmware binary is not stored in this repository. If it is absent,
`recover.py` downloads it from [Xiaomi's firmware server](https://cdn.cnbj1.fds.api.mi-img.com/xiaoqiang/rom/rd18/miwifi_rd18_firmware_6c571_1.0.53.bin)
before starting DHCP/TFTP. It verifies the expected size (`31,069,192` bytes)
and SHA-256 (`cdc567abd5b9d4ff10adb02ee9592575640e5607135a4588f05e7bdc2cab17d0`).
Download ahead of time with `python3 recover.py --download-only` (Windows:
`py -3 recover.py --download-only`). Internet is no longer needed afterward.

## 1. Prepare the connection

Clone this repository or download its ZIP from GitHub:

```sh
git clone https://github.com/pabragin/xiaomi-be5000-downgrade.git
cd xiaomi-be5000-downgrade
```

Connect the computer directly to the **first Ethernet port (LAN1)** of the
RD18. This is the port used in the successful attempt. Disconnect the router's
WAN cable and other clients. Recovery uses Ethernet, not the router's Wi-Fi.
Make sure no other DHCP or TFTP server is using UDP ports 67 or 69. On
macOS/Linux, inspect them with `sudo lsof -nP -iUDP:67 -iUDP:69`.

## 2. Start the server

**macOS:** Find the Ethernet interface with `networksetup -listallhardwareports`.
The USB Ethernet adapter in the original attempt was `en8`:

```sh
sudo /usr/bin/python3 recover.py --interface en8
```

**Linux:** Find the interface with `ip -br link` and substitute its name:

```sh
sudo python3 recover.py --interface enp3s0
```

On macOS/Linux the script adds `192.168.31.100/24` temporarily and removes
it when stopped.

**Windows (experimental, not hardware-tested):** Use Python 3.8+ and an
Administrator PowerShell. Download the firmware while internet is available:

```powershell
py -3 recover.py --download-only
```

Manually set the Ethernet adapter to IPv4 `192.168.31.100`, mask
`255.255.255.0`, with no gateway. Disable Wi-Fi and other adapters before
starting the server, so DHCP broadcasts use the cable to the router. Find
the adapter name with `Get-NetAdapter`, then substitute it below:

```powershell
py -3 recover.py --interface "Ethernet"
```

Allow Python on the private network if Windows Firewall asks. Restore the
adapter's usual IPv4 settings when finished. Windows cannot use the same
macOS/Linux interface binding or automatic address setup in this script, so
check its logs carefully.

## 3. Enter recovery mode and verify

Wait for both `TFTP listening` and `DHCP listening`. Remove power from the
RD18. Hold Reset while reconnecting power; release it when the status LED
starts blinking yellow/orange. Look for `DHCP DISCOVER`, `TFTP RRQ`, progress
to 100%, and `TFTP transfer complete`. Repeated DHCP requests without a
completed transfer mean the router has not received the entire file.

After the final TFTP attempt, leave the router powered on so it can verify
and install the image. Verify the result at `http://192.168.31.1/` or:

```sh
curl -fsS 'http://192.168.31.1/cgi-bin/luci/api/xqsystem/init_info'
```

Look for `hardware: RD18` and `romversion: 1.0.53`. Stop the server with
`Ctrl+C`.

The script recognizes the recovery bootloader by its DHCP `tclinux.bin`
bootfile field and locks onto that client's MAC address. If detection fails,
you may supply `--router-mac MAC_ADDRESS` using the bootloader MAC as six
colon-separated hexadecimal pairs. Redact MAC addresses before sharing logs.

## What happened in the original 1.0.91 downgrade

The first TFTP transfer reached 100%, but the router remained on 1.0.91.
During subsequent attempts the router fully received the image while its
status LED remained off. Power was interrupted several times in that state:
approximately 10 seconds after one completed transfer and about 20 seconds
after another. A further Reset recovery transfer was then allowed to finish
and boot; its API reported 1.0.53.

Those timings and the exact number of attempts were not recorded precisely.
An unlit LED does **not** reveal whether the router is verifying or writing
flash. Cutting power even after TFTP completes can leave it unable to boot
and may require UART or a flash programmer to recover. Treat this as a case
report, not a guaranteed timing recipe.
