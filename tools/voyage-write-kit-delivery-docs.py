#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate DELIVERY.md / SEAL.md / CHANGE-AUDIT from kit AUDIT + git HEAD.

Avoids hardcoding Cypress baseline commit or stale free-space bytes.
Space figures come from AUDIT-MANIFEST.json (pack/split), not literals.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CYPRESS_TOUCH_OK = (
    '1be5457d8b8cd7be83aec6756a2a70f6cbe88829e55d0f5a03232ced527ebacc'
)


def git_head(repo: Path) -> str:
    return subprocess.check_output(
        ['git', '-C', str(repo), 'rev-parse', '--short', 'HEAD'],
        text=True,
    ).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--kit', type=Path, required=True)
    ap.add_argument('--repo', type=Path, required=True)
    ap.add_argument('--system-raw-sha256', required=True)
    ap.add_argument('--label', default='pagepress-als')
    ap.add_argument('--baseline-cypress-sha256', default=CYPRESS_TOUCH_OK)
    args = ap.parse_args()

    kit = args.kit
    audit = json.loads((kit / 'AUDIT-MANIFEST.json').read_text())
    fat = audit['fat_space_bytes']
    entry = audit['entry']
    payload = audit['payload_system']
    commit = git_head(args.repo)
    utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    free_before = fat['free_before_copy_bytes']
    free_after = fat['free_after_copy_bytes']
    reserve = fat['reserve_bytes']
    # Same-size in-place upgrade: documents already hold matching zst+entry;
    # installer credits payload; still keep INST_RESERVE on free_after.
    inplace_min = free_after

    (kit / 'DELIVERY.md').write_text(f"""# Private Agent Store — Voyage **PagePress + ALS** kit ({args.label})

**Not a release. Not a claim that PagePress or auto-brightness work on device.**
Agent does not install/start/reboot the Kindle. Host tests ≠ device success.

## Provenance
- Work commit (this delivery): `{commit}`
- system.raw: `{args.system_raw_sha256}`
- Baseline Cypress touch-OK (user-confirmed; do not treat as this kit): `{args.baseline_cypress_sha256}`

## Kit
`{kit.name}/`

## Hashes
| Artifact | sha256 | bytes |
|---|---|---|
| system.raw | `{args.system_raw_sha256}` | 536870912 |
| payload zst | `{payload['sha256']}` | {payload['bytes']} |
| entry | `{entry['sha256']}` | {entry['bytes']} |

## Space (from AUDIT-MANIFEST.json — not hardcoded)
First copy onto an empty documents/ pair (entry + compressed system):
- Free **before** copy: **≥ {free_before} B (~{fat['free_before_copy_mib']} MiB)**
- Free **after** the two documents files: **≥ {free_after} B (~{fat['free_after_copy_mib']} MiB)**
- `INST_RESERVE` = {reserve} B (64 MiB)

Same-size in-place upgrade (documents already hold this exact entry+payload):
- Free needed ≈ **≥ {inplace_min} B (~{fat['free_after_copy_mib']} MiB)** (payload credited after system write + reserve)

## What this incremental adds (vs Cypress touch kit)
1. PagePress: post-insmod DAC/restorecon on `/dev/keypad`; oneshot `KEYPAD_IOCTL_EVENT_ENABLE`; `VOLUME_*` kl
2. ALS: `/dev/als` DAC/restorecon; `sensors.pw3` real lux; HIDL + voyage auto-brightness overlay
3. ueventd: initramfs `/ueventd.pw3.rc` **and** `/vendor/ueventd.rc` (+ fragment) carry keypad/als 0660
4. BootReport: `devnode` mode/uid/gid + `pagepress_enable` / `als_lux` status (de-identified)

## Explicitly unverified
PagePress keys, ALS lux/auto-brightness on hardware, haptics feel.

Generated: {utc}
""")

    (kit / 'SEAL.md').write_text(f"""# SEAL — {kit.name}

Private experimental kit. Not a release. Not device-confirmed for PagePress/ALS.

## Provenance
- git HEAD (short): `{commit}`
- system.raw sha256: `{args.system_raw_sha256}`
- payload zst sha256: `{payload['sha256']}` ({payload['bytes']} bytes)
- entry sha256: `{entry['sha256']}` ({entry['bytes']} bytes)
- data_format: 2 · offline_only: true
- Cypress touch baseline (not this kit): `{args.baseline_cypress_sha256}`

## Seal order
Frozen docs → SHA256SUMS → HOST-PREFLIGHT. Re-seal after any doc mutation.

## Observation fields (owner-run only)
- `devnode path=/dev/keypad|als kind=chr mode=… uid=… gid=…`
- `pagepress_enable status=ok|errno=N|open_errno=N|unset`
- `als_lux status=…` · Settings auto-brightness toggle (unverified)

## Forbidden claims
Do not claim PagePress or auto-brightness fixed until owner device report confirms.

Generated: {utc}
""")

    (kit / 'CHANGE-AUDIT-vs-cypress.md').write_text(f"""# Change audit vs user-confirmed Cypress kit

Baseline system.raw `{args.baseline_cypress_sha256}` (touch OK).
This kit system.raw `{args.system_raw_sha256}` · git `{commit}`.

## Node creation → ueventd → label → callers (t175u)

| Stage | Where | What |
|---|---|---|
| Create | `fsr_keypad.ko` / `als_max44009.ko` misc_register | `/dev/keypad`, `/dev/als` |
| Early ueventd | **entry** public-initramfs `/ueventd.pw3.rc` | DAC 0660 system (parsed at early-init) |
| Vendor ueventd | **system** `/vendor/ueventd.rc` (+ fragment) | Same DAC; path ueventd.cpp always tries |
| Labels | entry `nonplat_file_contexts` + `file_contexts.bin` | keypad→`input_device`, als→`sensors_device` |
| Post-insmod | `init.voyage.hardware.rc` | `chmod 0660` + `chown system` + `restorecon` (not 666) |
| PagePress | `pw3_fsr_enable` domain | `ioctl` EVENT_ENABLE; `sys.pw3.fsr.enable` |
| ALS | `hal_sensors_default` | `sensors_device` rw → real `ALS_IOCTL_GET_LUX` |

Independent system-only greps of vendor CIL will not show filecons (non-Treble product keeps `nonplat_file_contexts` on the **initramfs root**). Verify filecons in the entry public-initramfs, not only in `nonplat_sepolicy.cil`.

## Added vs Cypress system.raw
- `bin/pw3-fsr-enable`, sensors HAL/HIDL, `als_max44009.ko`, `fsr_keypad.kl`, light permission
- `/vendor/ueventd.rc` with keypad/als (fragment also updated)
- framework-res auto-brightness overlay; `ro.hardware.sensors=pw3`

## Not verified on device
Keys / auto-brightness / haptics. Host packaging only.

Generated: {utc}
""")

    print(json.dumps({
        'commit': commit,
        'system_raw_sha256': args.system_raw_sha256,
        'free_before_copy_bytes': free_before,
        'free_after_copy_bytes': free_after,
        'entry_sha256': entry['sha256'],
        'payload_sha256': payload['sha256'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
