# Voyage bootmode: code semantics and empty reading

## Consumers

1. **Runtime handoff** — `dd_atags` (`boot/devicedata/devicedata.c`):
   - Reads `/proc/bootmode` from the live device root.
   - Fails unless the string is exactly `main`.
   - On success, writes ATAG_BOOTMODE with a **hardcoded** `"main"` (the check is the safety; the tag payload is not a copy of a free-form string).
2. **Install prepare** — `helper.c`: refuses when `ENTRY_PROFILE.identity_ready` is 0 (`dd_voyage_5_13_6`).
3. **Packaging** — `tools/voyage_profile.refuse_unless_installable`:
   - Requires `installable` / `identity_ready` / `device_confirmed`.
   - `_voyage_bootmode_gate`: if any of those is true, recorded bootmode must be exactly `main`.

## Empty `/proc/bootmode` + `root=/dev/mmcblk0p1` + running system

Proves the stock rootfs on p1 is up. Does **not** prove idme `system_bootmode == main`.
Lab126 publishes bootmode from idme via `boardid.c`; an empty proc file is an empty idme field at read time.

## 2026-11-12 dedicated probe (verified)

Report: 337 bytes, SHA-256 `eb98afc157f42877c40ea9032dd06ce23475dcb635c83a5a325c49645eb0292e`,
`generated: Thu Nov 12 06:16:17 UTC 2026`, `uid=0`, `bootmode: main`, `result: ok`,
`VOYAGE_PROBE_BOOTMODE_DONE`. Stored as `device_probe_bootmode` and `measured.bootmode=main`.
Historical empty reading in `device_probe_extra` is kept. This fills the bootmode gate only;
`installable` / `identity_ready` / `device_confirmed` stay false.

## What not to do

- Do not write `main` into the profile because the device “looks normal”.
- Do not ask the owner to `echo main > /proc/bootmode`.
- Do not treat cmdline `root=` as bootmode evidence.

## Minimal re-read (already shipped)

`tools/voyage-probe-bootmode.sh` — only `/proc/bootmode`, writes `/mnt/us/voyage-probe-bootmode.txt`.
Re-run after a cold boot / leaving diags if the owner wants a fresh reading. No kcore, no mem, no boot partitions, no modules, no Readom.
