# Обезличенные фрагменты журнала / Anonymized log excerpts

Это фрагменты одной из прежних попыток восстановления Xiaomi BE5000 с образом 1.0.53, а не полный двухэтапный процесс из инструкции. MAC-адреса заменены на
`[MAC скрыт]`; интервалы между попытками сокращены. Последняя строка API
показывает результат проверки после загрузки роутера.

These are excerpts from an earlier Xiaomi BE5000 recovery attempt using the 1.0.53 image, not the complete two-stage process in the guide. MAC addresses were
redacted, and the gaps between attempts were shortened. The final API fields
show the version verified after the router booted.

```text
01:11:48 Verified Xiaomi BE5000 1.0.53 image: 31,069,192 bytes, SHA-256 cdc567abd5b9d4ff10adb02ee9592575640e5607135a4588f05e7bdc2cab17d0
01:11:48 Added temporary 192.168.31.100/24 alias on en8
01:11:48 TFTP listening on 192.168.31.100:69
01:11:48 DHCP listening on en8:67; offering 192.168.31.111
01:11:48 DHCP DISCOVER -> OFFER 192.168.31.111 to [MAC скрыт] (0.0.0.0)
01:11:48 DHCP REQUEST -> ACK 192.168.31.111 to [MAC скрыт] (0.0.0.0)
01:11:48 TFTP RRQ 'miwifi_rd18_firmware_6c571_1.0.53.bin' from 192.168.31.111 options={'timeout': '50', 'blksize': '1468'}
01:11:53 TFTP 10% (3,107,756/31,069,192 bytes)
01:12:19 TFTP 60% (18,642,132/31,069,192 bytes)
01:12:40 TFTP 100% (31,069,192/31,069,192 bytes)
01:12:40 TFTP transfer complete: 31,069,192 bytes. Waiting for router verification.
```

Позже были повторные запросы и незавершённые передачи. Этот лог сам по себе
не доказывает запись прошивки:

```text
01:46:09 DHCP DISCOVER -> OFFER 192.168.31.111 to [MAC скрыт] (0.0.0.0)
01:46:09 DHCP REQUEST -> ACK 192.168.31.111 to [MAC скрыт] (0.0.0.0)
01:46:09 TFTP RRQ 'miwifi_rd18_firmware_6c571_1.0.53.bin' from 192.168.31.111 options={'timeout': '50', 'blksize': '1468'}
01:46:35 TFTP stopped after 1,073,108 of 31,069,192 bytes
```

После окончательной загрузки проверка локального API показала:

```text
hardware: RD18 (internal platform identifier)
romversion: 1.0.53
```
