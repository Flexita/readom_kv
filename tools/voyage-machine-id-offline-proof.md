# Voyage machine_id: offline proof (no device memory access)

## Proven without runtime measurement

| Claim | Evidence |
|---|---|
| Board family | GPL `imx60_wario_defconfig` / `CONFIG_MACH_MX6SL_WARIO=y` |
| Numeric MACH_TYPE | Amazon mach-types + kernel `machine_desc.nr` in matching 5.13.6 `Image` → **4091** |
| Role in boot chain | Bootloader passes machine_id in r1; ATAGs are a separate tagged list and do not encode this number as a tag |
| Profile field | `machine: 4091` is a **build pin**; `measured.machine_id` stays null until a reviewed userspace readout exists |

## Not required for compile gates

Inventing `measured.machine_id=4091` is refused. Opening installable still needs real Voyage boot evidence, not a filled field.

## If a future runtime check is authorized

Only after risk review. Allowed shape: a script that prints **one decimal integer** from an already-documented, non-privileged interface if the stock kernel exposes one. Disallowed without new approval: `/proc/kcore`, `/dev/mem`, boot partitions, raw ATAG dumps, module loads, running Readom.
