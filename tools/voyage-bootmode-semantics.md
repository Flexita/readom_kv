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

## What not to do

- Do not write `main` into the profile because the device “looks normal”.
- Do not ask the owner to `echo main > /proc/bootmode`.
- Do not treat cmdline `root=` as bootmode evidence.

## Minimal re-read (already shipped)

`tools/voyage-probe-bootmode.sh` — only `/proc/bootmode`, writes `/mnt/us/voyage-probe-bootmode.txt`.
Re-run after a cold boot / leaving diags if the owner wants a fresh reading. No kcore, no mem, no boot partitions, no modules, no Readom.
