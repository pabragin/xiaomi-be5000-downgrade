# Xiaomi BE5000: my 1.0.91 to 1.0.53 downgrade over Mac Ethernet

Русская версия: [POST.md](POST.md).

My goal was to downgrade a Xiaomi BE5000 from 1.0.91 to 1.0.53 without a
USB-to-TTL adapter. The recovery procedure has two stages: serve 1.0.91 and
interrupt its write to clear both system copies, then serve 1.0.53. This is a
risky method also described in [this forum thread](https://www.right.com.cn/forum/thread-8470335-1-1.html),
not a guaranteed procedure.

Both original images are available directly from Xiaomi's CDN:
[1.0.91](https://cdn.cnbj1.fds.api.mi-img.com/xiaoqiang/rom/rd18/miwifi_rd18_firmware_05f43_1.0.91.bin)
and [1.0.53](https://cdn.cnbj1.fds.api.mi-img.com/xiaoqiang/rom/rd18/miwifi_rd18_firmware_6c571_1.0.53.bin).
The helper downloads the selected version and verifies its size and SHA-256.

For cleanup, start recovery with `--firmware 1.0.91`. After TFTP reaches 100%,
wait about 10 seconds and unplug the router. Run recovery with 1.0.91 again,
wait for 100%, wait about 20 seconds, and unplug once more. Then start recovery
with `--firmware 1.0.53` and let installation finish. If the LED turns steady
yellow immediately after the 1.0.53 transfer, cleanup likely did not finish;
repeat the 1.0.91 cycles. See [README.en.md](README.en.md) for commands, OS
instructions, and caveats.

The earlier log excerpts show a complete 1.0.53 TFTP transfer, but 100% alone
does not prove the image was installed. MAC addresses in the published logs
are redacted. Interrupting power during a flash write can make the router
unbootable and require UART or a flash programmer.

The helper only serves Xiaomi's signed stock image; it does not write flash or
bypass rollback checks. Full instructions and anonymized logs are in
[README.en.md](README.en.md) and [LOG_EXAMPLE.md](LOG_EXAMPLE.md).
