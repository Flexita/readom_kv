#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Split a full USB offline kit so each file is <128MiB for Agent Store.

Does not change payload bytes: only cuts the system .zst into VOLUMES parts and
rewrites META/SPLIT-MANIFEST.json, HOST-PREFLIGHT (dual layout), SHA256SUMS.
Re-run after replacing only the entry script.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
from pathlib import Path

MIB = 1024 * 1024
# Default 4 MiB: CopyFromBox on Mac has failed at 48 MiB; 4 MiB parts succeed
# with the regular tool. Still well under the Agent Store 128 MiB/file limit.
DEFAULT_PART = 4 * MIB


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--full-kit', type=Path, required=True,
                    help='kit with COPY-TO-KINDLE/documents/{entry,payload}')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--entry-sh', type=Path,
                    help='optional replacement entry (new rebuild); keeps payload')
    ap.add_argument('--part-bytes', type=int, default=DEFAULT_PART,
                    help='volume size in bytes (default 4 MiB for CopyFromBox)')
    ap.add_argument('--host-test-results', type=Path,
                    help='frozen HOST-TEST-RESULTS.txt; installed before final SHA256SUMS')
    ap.add_argument('--doc', action='append', default=[],
                    help='REL_IN_KIT=SOURCE_PATH installed before final SHA256SUMS')
    ap.add_argument('--seal-evidence-out', type=Path,
                    help='if set, seal via voyage_usb_kit_seal (SUMS last + preflight)')
    args = ap.parse_args()
    if args.part_bytes < MIB or args.part_bytes >= 128 * MIB:
        raise SystemExit('--part-bytes must be in [1MiB, 128MiB)')
    part_size = args.part_bytes

    src = args.full_kit
    audit = json.loads((src / 'AUDIT-MANIFEST.json').read_text())
    entry_name = audit['entry']['name']
    pay_name = audit['payload_system']['name']
    src_entry = src / 'COPY-TO-KINDLE' / 'documents' / entry_name
    src_pay = src / 'COPY-TO-KINDLE' / 'documents' / pay_name
    if not src_entry.is_file():
        raise SystemExit('missing entry in full kit')
    if not src_pay.is_file():
        raise SystemExit('full kit missing reassembled payload (needed once to split)')

    if args.output.exists():
        raise SystemExit('refusing to overwrite %s' % args.output)
    out = args.output
    docs = out / 'COPY-TO-KINDLE' / 'documents'
    docs.mkdir(parents=True)
    (out / 'VOLUMES').mkdir()
    (out / 'META').mkdir()

    entry_src = args.entry_sh if args.entry_sh else src_entry
    entry_dest = docs / entry_name
    shutil.copyfile(entry_src, entry_dest)
    try:
        entry_dest.chmod(entry_dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        # Agent Store and some mounts ignore mode bits; content hash still holds.
        pass

    # Split payload
    with src_pay.open('rb') as inf:
        idx = 0
        while True:
            chunk = inf.read(part_size)
            if not chunk:
                break
            part = out / 'VOLUMES' / ('%s.part%02d' % (pay_name, idx))
            part.write_bytes(chunk)
            idx += 1
            if idx > 99:
                raise SystemExit('too many parts')

    entry_sha = sha_file(entry_dest)
    entry_bytes = entry_dest.stat().st_size
    pay_sha = sha_file(src_pay)
    pay_bytes = src_pay.stat().st_size
    if pay_sha != audit['payload_system']['sha256'] or pay_bytes != audit['payload_system']['bytes']:
        raise SystemExit('payload hash/size drift vs AUDIT-MANIFEST')

    audit = dict(audit)
    audit['entry'] = dict(audit['entry'])
    audit['entry']['sha256'] = entry_sha
    audit['entry']['bytes'] = entry_bytes
    if 'fat_space_bytes' in audit:
        fat = dict(audit['fat_space_bytes'])
        fat['entry_bytes'] = entry_bytes
        copy_set = entry_bytes + pay_bytes
        fat['copy_set_bytes'] = copy_set
        # Keep free_after; recompute free_before from new entry size.
        free_after = fat.get('free_after_copy_bytes')
        if free_after is not None:
            fat['free_before_copy_bytes'] = free_after + copy_set
            fat['free_before_copy_mib'] = round(fat['free_before_copy_bytes'] / MIB, 1)
        audit['fat_space_bytes'] = fat

    (out / 'AUDIT-MANIFEST.json').write_text(json.dumps(audit, indent=2) + '\n')
    split_meta = {
        'schema': 1,
        'kind': 'voyage-usb-offline-agent-store-split',
        'part_bytes_max': part_size,
        'entry': audit['entry'],
        'payload_system': audit['payload_system'],
        'fat_space_bytes': audit.get('fat_space_bytes'),
        'volumes': sorted(p.name for p in (out / 'VOLUMES').iterdir()),
    }
    (out / 'META' / 'SPLIT-MANIFEST.json').write_text(json.dumps(split_meta, indent=2) + '\n')

    for name in ('EXPERIMENTAL-PRIVATE-NOT-RELEASE', 'USB-OFFLINE-README.md'):
        src_f = src / name
        if src_f.is_file():
            shutil.copyfile(src_f, out / name)

    (out / 'HOST-PREFLIGHT.sh').write_text(r'''#!/bin/sh
# Host-only structure/hash check. Supports full documents/ payload or VOLUMES split.
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
import hashlib, json, os
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
''')
    try:
        (out / 'HOST-PREFLIGHT.sh').chmod(0o755)
    except OSError:
        pass

    # REASSEMBLE script
    (out / 'REASSEMBLE-ON-HOST.sh').write_text('''#!/bin/sh
# Reassemble the system payload on a normal filesystem (NOT inside Agent Store).
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
PAY=%(pay)s
ENTRY=%(entry)s
OUTDIR=${1:-"$PWD/voyage-usb-offline-reassembled"}
mkdir -p "$OUTDIR/documents"
test -f "$ROOT/META/SPLIT-MANIFEST.json"
test -f "$ROOT/COPY-TO-KINDLE/documents/$ENTRY"
cp -f "$ROOT/COPY-TO-KINDLE/documents/$ENTRY" "$OUTDIR/documents/"
cat "$ROOT"/VOLUMES/${PAY}.part* > "$OUTDIR/documents/$PAY"
python3 -c "
import hashlib, json, sys
from pathlib import Path
root=Path(sys.argv[1]); out=Path(sys.argv[2])
meta=json.loads((root/'META/SPLIT-MANIFEST.json').read_text())
pay=out/'documents'/meta['payload_system']['name']
h=hashlib.sha256()
with open(pay,'rb') as f:
    for b in iter(lambda:f.read(1<<20), b''): h.update(b)
assert h.hexdigest()==meta['payload_system']['sha256'], 'reassembled hash mismatch'
assert pay.stat().st_size==meta['payload_system']['bytes']
print('REASSEMBLE-ON-HOST: OK')
print('documents_dir', out/'documents')
print('entry', meta['entry']['name'], meta['entry']['sha256'])
print('payload', meta['payload_system']['name'], meta['payload_system']['sha256'])
" "$ROOT" "$OUTDIR"
echo "Copy both files from $OUTDIR/documents/ into the Kindle drive documents/ folder."
''' % {'pay': pay_name, 'entry': entry_name})
    try:
        (out / 'REASSEMBLE-ON-HOST.sh').chmod(0o755)
    except OSError:
        pass

    readme = out / 'USB-OFFLINE-README.md'
    if not readme.is_file():
        shutil.copyfile(src / 'USB-OFFLINE-README.md', readme)
    note = (
        '\n## Agent Store split layout\n\n'
        'Payload is in `VOLUMES/*.part*` (<128MiB each). Run `sh REASSEMBLE-ON-HOST.sh` '
        'on a normal filesystem, then copy both files into Kindle `documents/`.\n'
        '`sh HOST-PREFLIGHT.sh` works on this split layout without reassembling.\n'
    )
    text = readme.read_text()
    if 'Agent Store split layout' not in text:
        readme.write_text(text.rstrip() + '\n' + note)

    marker = out / 'EXPERIMENTAL-PRIVATE-NOT-RELEASE'
    if not marker.is_file():
        marker.write_text(
            'Private Voyage USB offline experimental kit (Agent Store split).\n'
            'device_confirmed=false. Reassemble payload before copying to Kindle.\n'
        )

    frozen: dict = {}
    if args.host_test_results:
        frozen['HOST-TEST-RESULTS.txt'] = args.host_test_results
    for item in args.doc:
        if '=' not in item:
            raise SystemExit('--doc needs REL=SOURCE, got %r' % item)
        rel, src = item.split('=', 1)
        frozen[rel] = Path(src)

    # Final mutation order: frozen docs (if any) → SHA256SUMS → preflight.
    # Never rewrite HOST-TEST-RESULTS after this; re-seal with voyage-seal-usb-kit.py.
    if args.seal_evidence_out or frozen:
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
            'frozen_docs_installed': evidence.get('frozen_docs_installed'),
        }
    else:
        sums = []
        for path in sorted(out.rglob('*')):
            if path.is_file() and path.name != 'SHA256SUMS':
                sums.append('%s  %s' % (sha_file(path), path.relative_to(out).as_posix()))
        (out / 'SHA256SUMS').write_text('\n'.join(sums) + '\n')
        import subprocess
        subprocess.run(['sh', str(out / 'HOST-PREFLIGHT.sh')], check=True, cwd=str(out))
        seal_info = {'sha256sums_sha256': sha_file(out / 'SHA256SUMS')}

    print(json.dumps({
        'output': str(out),
        'entry_sha256': entry_sha,
        'entry_bytes': entry_bytes,
        'payload_sha256': pay_sha,
        'payload_bytes': pay_bytes,
        'volumes': split_meta['volumes'],
        'seal': seal_info,
    }, indent=2))


if __name__ == '__main__':
    main()
