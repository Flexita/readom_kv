#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Assemble a private Voyage *USB offline* experimental kit (cloud only).

Layout (what the owner copies onto the Kindle drive):

  COPY-TO-KINDLE/documents/<EntryExperimental>.sh
  COPY-TO-KINDLE/documents/readom-system-<ver>.img.zst
  SHA256SUMS
  AUDIT-MANIFEST.json
  USB-OFFLINE-README.md
  HOST-PREFLIGHT.sh   (host-only structure/hash check; no Kindle action)
  EXPERIMENTAL-PRIVATE-NOT-RELEASE

Uses an already-built offline-only entry (--offline-only) so no private.invalid
URL is embedded. Does not authorize install, cleanup, or first boot.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

MIB = 1024 * 1024
RESERVE = 64 * MIB


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--entry-sh', type=Path, required=True,
                    help='built VoyageExperimental-*.sh (offline-only)')
    ap.add_argument('--payload-system-zst', type=Path, required=True)
    ap.add_argument('--payload-manifest', type=Path, required=True)
    ap.add_argument('--entry-build-result', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--entry-name', default='VoyageExperimental-offline.sh')
    ap.add_argument('--host-test-results', type=Path,
                    help='frozen HOST-TEST-RESULTS.txt; installed before final SHA256SUMS')
    ap.add_argument('--seal-evidence-out', type=Path,
                    help='optional seal evidence JSON (outside kit); enforces SUMS-last order')
    args = ap.parse_args()

    if platform.node() != 'lima-pw3' or os.geteuid() == 0:
        raise SystemExit('Run as non-root on lima-pw3')
    if args.output.exists():
        raise SystemExit('Refusing to overwrite %s' % args.output)
    if 'Experimental' not in args.entry_name and 'experimental' not in args.entry_name:
        raise SystemExit('entry name must contain Experimental')
    if args.entry_name == 'Readom.sh':
        raise SystemExit('refusing Readom.sh')

    manifest = json.loads(args.payload_manifest.read_text())
    entry_result = json.loads(args.entry_build_result.read_text())
    installer = entry_result.get('installer') or {}
    if not installer.get('offline_only'):
        raise SystemExit('entry is not offline_only; rebuild with --offline-only')
    if installer.get('payload_urls'):
        raise SystemExit('offline entry still embeds payload_urls: %r' % installer.get('payload_urls'))

    sys_name = manifest['files']['system']['name']
    sys_bytes = manifest['files']['system']['bytes']
    sys_sha = manifest['files']['system']['sha256']
    unpacked_sys = manifest['files']['system']['unpacked_bytes']
    unpacked_data = manifest['files']['data']['unpacked_bytes']
    if sha_file(args.payload_system_zst) != sys_sha:
        raise SystemExit('payload zst sha256 mismatch vs manifest')
    if args.payload_system_zst.stat().st_size != sys_bytes:
        raise SystemExit('payload zst size mismatch vs manifest')

    out = args.output
    docs = out / 'COPY-TO-KINDLE' / 'documents'
    docs.mkdir(parents=True)
    entry_dest = docs / args.entry_name
    payload_dest = docs / sys_name
    shutil.copyfile(args.entry_sh, entry_dest)
    entry_dest.chmod(entry_dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    shutil.copyfile(args.payload_system_zst, payload_dest)

    entry_bytes = entry_dest.stat().st_size
    entry_sha = sha_file(entry_dest)

    # Offline FAT budget (bytes). Data template is inside the entry, not a
    # separate documents file. Installer's check_space with payload already in
    # documents: p=0, peak ≈ system+data−payload + reserve of *additional* free.
    copy_set = entry_bytes + sys_bytes
    # Concurrent peak of our files on FAT during install:
    peak_occupied = max(sys_bytes + unpacked_sys, unpacked_sys + unpacked_data) + entry_bytes
    # Free space needed *after* the two documents files are already present:
    free_after_copy = unpacked_sys + unpacked_data - sys_bytes + RESERVE
    if free_after_copy < unpacked_sys + RESERVE:
        free_after_copy = unpacked_sys + RESERVE
    # Free space needed *before* copying the kit onto the drive:
    free_before_copy = free_after_copy + copy_set

    sums = []
    for path in sorted(out.rglob('*')):
        if path.is_file() and path.name != 'SHA256SUMS':
            rel = path.relative_to(out).as_posix()
            sums.append('%s  %s' % (sha_file(path), rel))
    # SHA256SUMS written after listing other files — recompute with itself excluded
    (out / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')

    audit = {
        'schema': 1,
        'kind': 'voyage-usb-offline-experimental-PRIVATE-NOT-RELEASE',
        'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'device_confirmed': False,
        'experimental_first_test': True,
        'install_authorized': False,
        'filler_cleanup_authorized': False,
        'first_boot_authorized': False,
        'offline_only': True,
        'payload_urls_embedded': [],
        'entry': {
            'name': args.entry_name,
            'bytes': entry_bytes,
            'sha256': entry_sha,
            'copy_to': 'documents/' + args.entry_name,
        },
        'payload_system': {
            'name': sys_name,
            'bytes': sys_bytes,
            'sha256': sys_sha,
            'unpacked_bytes': unpacked_sys,
            'copy_to': 'documents/' + sys_name,
        },
        'data_template': {
            'note': 'embedded inside the entry (readom-data-*.img.zst from build_payload); not a separate USB file',
            'unpacked_bytes': unpacked_data,
        },
        'fat_space_bytes': {
            'estimate': False,
            'formula_notes': [
                'copy_set = entry + compressed system zst (both in documents/)',
                'installer check_space with local payload: p=0; credits payload size when deleted after system write',
                'free_after_copy ≈ system + data − payload + INST_RESERVE(64MiB)',
                'free_before_copy = free_after_copy + copy_set',
                'dexopt writes into the data image after Android starts — not additional user-FAT install peak',
            ],
            'entry_bytes': entry_bytes,
            'compressed_system_bytes': sys_bytes,
            'copy_set_bytes': copy_set,
            'unpacked_system_bytes': unpacked_sys,
            'unpacked_data_bytes': unpacked_data,
            'reserve_bytes': RESERVE,
            'free_after_copy_bytes': free_after_copy,
            'free_before_copy_bytes': free_before_copy,
            'free_before_copy_mib': round(free_before_copy / MIB, 1),
            'free_after_copy_mib': round(free_after_copy / MIB, 1),
            'peak_our_files_occupied_bytes': peak_occupied,
            'dexopt_first_boot': {
                'estimate': True,
                'note': (
                    'WITH_DEXPREOPT=false: first Android boot compiles boot.art + apps '
                    'into /data. Not part of the FAT install peak above. 256 MiB guess '
                    'inside the 1024 MiB data image is heuristic only — unmeasured on Voyage.'
                ),
                'extra_data_headroom_guess_mib': 256,
            },
        },
        'do_not_overwrite': [
            'books / documents/*.azw* / documents/*.mobi / documents/*.pdf (except the two kit files)',
            'extensions/',
            'appreg.db',
            'jailbreak / Hotfix.bin (unless owner separately confirms)',
            'fill_disk (unless owner separately confirms)',
        ],
        'idempotent_retry': (
            'Power loss mid-install: tap the Experimental entry again; installer resumes '
            'from android/state. Half-copied documents payload: delete the partial '
            'readom-system-*.img.zst and recopy from this kit (exact name/size), then tap again. '
            'Do not rename with (1).'
        ),
        'recovery': (
            'Stock bootloader unchanged. Prefer: eject USB, reboot to stock, confirm library. '
            'If android/ images were written: from computer delete only android/system.img and '
            'android/data.img (not books). 40s power-hold is Voyage-unverified — do not treat as proven.'
        ),
    }
    (out / 'AUDIT-MANIFEST.json').write_text(json.dumps(audit, indent=2) + '\n')
    (out / 'EXPERIMENTAL-PRIVATE-NOT-RELEASE').write_text(
        'Private Voyage USB offline experimental kit.\n'
        'device_confirmed=false. Not a stable release. Not authorized for install until owner says so.\n'
        'Entry embeds offline_only=1; no download URL. Copy both files into documents/ exactly.\n'
    )
    (out / 'USB-OFFLINE-README.md').write_text('\n'.join([
        '# Voyage USB offline experimental kit (NOT daily-use)',
        '',
        '**device_confirmed=false.** Stock bootloader unchanged. No network download.',
        '',
        '## Copy exactly (Kindle drive)',
        '',
        '1. Connect Kindle by USB; open the Kindle drive.',
        '2. Copy **both** files into `documents/` (not drive root, not a subfolder):',
        '   - `documents/%s`' % args.entry_name,
        '   - `documents/%s`' % sys_name,
        '3. Names must match exactly (no `(1)`). Verify with SHA256SUMS if you want.',
        '4. Eject safely, unplug USB (charger OK). USB connected → E104.',
        '5. Only after **separate** owner authorization: tap the Experimental entry in the library.',
        '',
        '## Space (measured from this kit)',
        '',
        '- Free **before** copy onto drive: **≥ %d bytes (~%.1f MiB)**' % (
            free_before_copy, free_before_copy / MIB),
        '- Free **after** the two documents files are present: **≥ %d bytes (~%.1f MiB)**' % (
            free_after_copy, free_after_copy / MIB),
        '- First-boot dexopt: estimate only; needs room inside the data image after Android starts.',
        '',
        '## Host preflight (computer only)',
        '',
        '```',
        'sh HOST-PREFLIGHT.sh',
        '```',
        '',
        'Does not talk to a Kindle. Checks kit structure and hashes.',
        '',
        '## Do not touch',
        '',
        '- Books, jailbreak files, Hotfix.bin, fill_disk — unless you separately confirm.',
        '',
        '## Retry / recovery',
        '',
        audit['idempotent_retry'],
        '',
        audit['recovery'],
        '',
    ]) + '\n')

    preflight = out / 'HOST-PREFLIGHT.sh'
    # Dual layout: full kit has documents/<payload>; Agent Store split keeps
    # the payload in VOLUMES/*.part* + META/SPLIT-MANIFEST.json. The old full-
    # only preflight `test -f COPY-TO-KINDLE/documents/$PAY` exited 1 silently
    # on split kits.
    preflight.write_text(r'''#!/bin/sh
# Host-only structure/hash check for this kit. Does not access a Kindle.
# Supports (a) full COPY-TO-KINDLE/documents payload and (b) VOLUMES split.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
cd "$ROOT"
test -f EXPERIMENTAL-PRIVATE-NOT-RELEASE
test -f AUDIT-MANIFEST.json
test -f SHA256SUMS
ENTRY=$(python3 -c 'import json;print(json.load(open("AUDIT-MANIFEST.json"))["entry"]["name"])')
PAY=$(python3 -c 'import json;print(json.load(open("AUDIT-MANIFEST.json"))["payload_system"]["name"])')
test -f "COPY-TO-KINDLE/documents/$ENTRY"
test "$ENTRY" != "Readom.sh"
if [ -f "COPY-TO-KINDLE/documents/$PAY" ]; then
  LAYOUT=full
elif [ -d VOLUMES ] && [ -f META/SPLIT-MANIFEST.json ]; then
  LAYOUT=split
else
  echo "HOST-PREFLIGHT: missing payload (neither documents/$PAY nor VOLUMES+META)" >&2
  exit 1
fi
export LAYOUT
python3 - <<'PY'
import hashlib, json, os, sys
from pathlib import Path
root = Path('.')
audit = json.loads((root/'AUDIT-MANIFEST.json').read_text())
assert audit.get('offline_only') is True
assert audit.get('device_confirmed') is False
assert audit.get('payload_urls_embedded') == []
assert not audit.get('install_authorized')
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()
e = root/'COPY-TO-KINDLE/documents'/audit['entry']['name']
assert sha(e)==audit['entry']['sha256'], 'entry hash mismatch'
assert e.stat().st_size==audit['entry']['bytes']
layout = os.environ['LAYOUT']
pay_name = audit['payload_system']['name']
if layout == 'full':
    p = root/'COPY-TO-KINDLE/documents'/pay_name
    assert sha(p)==audit['payload_system']['sha256'], 'payload hash mismatch'
    assert p.stat().st_size==audit['payload_system']['bytes']
else:
    meta = json.loads((root/'META'/'SPLIT-MANIFEST.json').read_text())
    assert meta['payload_system']['sha256']==audit['payload_system']['sha256']
    assert meta['payload_system']['bytes']==audit['payload_system']['bytes']
    assert meta['entry']['sha256']==audit['entry']['sha256']
    parts = sorted((root/'VOLUMES').glob(pay_name + '.part*'))
    assert parts, 'no VOLUMES parts for '+pay_name
    h=hashlib.sha256(); total=0
    for part in parts:
        with open(part,'rb') as f:
            for b in iter(lambda:f.read(1<<20), b''):
                h.update(b); total += len(b)
    assert h.hexdigest()==audit['payload_system']['sha256'], 'reassembled volume hash mismatch'
    assert total==audit['payload_system']['bytes'], 'reassembled volume size mismatch'
listed={}
for line in (root/'SHA256SUMS').read_text().splitlines():
    if not line.strip(): continue
    digest, name = line.split('  ', 1)
    listed[name]=digest
for path in sorted(root.rglob('*')):
    if not path.is_file() or path.name=='SHA256SUMS': continue
    rel=path.relative_to(root).as_posix()
    assert rel in listed, 'missing from SHA256SUMS: '+rel
    assert sha(path)==listed[rel], 'SHA256SUMS mismatch: '+rel
print('HOST-PREFLIGHT: OK')
print('layout', layout)
print('free_before_copy_mib', audit['fat_space_bytes']['free_before_copy_mib'])
print('free_after_copy_mib', audit['fat_space_bytes']['free_after_copy_mib'])
PY
''' )
    preflight.chmod(0o755)

    # Final order: optional frozen host-test → SHA256SUMS → preflight.
    # Do not rewrite HOST-TEST-RESULTS after this; use voyage-seal-usb-kit.py.
    frozen = {}
    if args.host_test_results:
        frozen['HOST-TEST-RESULTS.txt'] = args.host_test_results
    if frozen or args.seal_evidence_out:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from voyage_usb_kit_seal import seal_kit
        evidence = seal_kit(
            out,
            frozen or None,
            run_preflight=True,
            evidence_out=args.seal_evidence_out,
        )
        seal_info = {
            'sha256sums_sha256': evidence['sha256sums_sha256'],
            'host_preflight_exit': evidence.get('host_preflight', {}).get('exit'),
        }
    else:
        sums = []
        for path in sorted(out.rglob('*')):
            if path.is_file() and path.name != 'SHA256SUMS':
                sums.append('%s  %s' % (sha_file(path), path.relative_to(out).as_posix()))
        (out / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
        subprocess.run(['sh', str(preflight)], check=True, cwd=str(out))
        seal_info = {'sha256sums_sha256': sha_file(out / 'SHA256SUMS')}

    print(json.dumps({
        'output': str(out),
        'entry': args.entry_name,
        'entry_sha256': entry_sha,
        'payload': sys_name,
        'payload_sha256': sys_sha,
        'free_before_copy_mib': audit['fat_space_bytes']['free_before_copy_mib'],
        'free_after_copy_mib': audit['fat_space_bytes']['free_after_copy_mib'],
        'offline_only': True,
        'seal': seal_info,
    }, indent=2))


if __name__ == '__main__':
    main()
