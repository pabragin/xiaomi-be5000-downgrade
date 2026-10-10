# Xiaomi BE5000: my 1.0.91 to 1.0.53 downgrade over Mac Ethernet

Русская версия: [POST.md](POST.md).

I returned my Xiaomi BE5000 from stock firmware 1.0.91 to 1.0.53
without a USB-to-TTL adapter. This is a report of **one device**, not a
guaranteed downgrade procedure: the bootloader decides whether it accepts
an older signed image.

I used a Mac, a direct Ethernet cable to the router's **first port (LAN1)**,
and the Python DHCP/TFTP helper in this repository. I disconnected the
router's WAN cable and other clients. The script obtains the stock image
[directly from Xiaomi](https://cdn.cnbj1.fds.api.mi-img.com/xiaoqiang/rom/rd18/miwifi_rd18_firmware_6c571_1.0.53.bin)
when needed, then verifies its size (31,069,192 bytes) and SHA-256
(`cdc567abd5b9d4ff10adb02ee9592575640e5607135a4588f05e7bdc2cab17d0`).

The Mac's USB Ethernet interface was `en8`. I started the server with:

```sh
sudo /usr/bin/python3 recover.py --interface en8
```

The script added `192.168.31.100` temporarily and started DHCP/TFTP.
I powered the router on while holding Reset and released it when the yellow
LED started blinking. The log showed `DHCP DISCOVER`, `TFTP RRQ`, and transfer
progress to `TFTP transfer complete`.

The first completed TFTP transfer did **not** change the version: the router
still had 1.0.91. In later attempts the transfer finished while the status
LED remained off. I interrupted power several times in that state, roughly
10 seconds after one completed transfer and about 20 seconds after another.
Then I ran Reset recovery with 1.0.53 again and let the router boot. Its local
API at `http://192.168.31.1/cgi-bin/luci/api/xqsystem/init_info` reported
`romversion: 1.0.53` (the internal `hardware` field may report `RD18`).

Those timings and the number of attempts were approximate. An unlit LED
does not show whether the router is checking or writing flash. Cutting power
after TFTP finishes can still leave the router unbootable and require UART
or a flash programmer. The helper only serves the signed stock image; it
does not write flash or bypass rollback checks. Full setup instructions are
in [README.en.md](README.en.md), with anonymized logs in
[LOG_EXAMPLE.md](LOG_EXAMPLE.md).
