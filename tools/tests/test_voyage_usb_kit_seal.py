#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression: USB kit SHA256SUMS must cover frozen docs; post-SUMS edits fail preflight."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEAL_MOD = ROOT / 'tools/voyage_usb_kit_seal.py'
SEAL_CLI = ROOT / 'tools/voyage-seal-usb-kit.py'
SPLIT = ROOT / 'tools/voyage-split-usb-kit-agent-store.py'
PACK = ROOT / 'tools/voyage-pack-usb-offline-experimental.py'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class VoyageUsbKitSeal(unittest.TestCase):
    def test_seal_module_and_cli_exist(self):
        self.assertTrue(SEAL_MOD.is_file())
        self.assertTrue(SEAL_CLI.is_file())
        text = SEAL_MOD.read_text()
        self.assertIn('write_sha256sums', text)
        self.assertIn('Do not mutate', text)
        # Order: install frozen docs, then sums, then preflight.
        i_docs = text.index('install_frozen_docs')
        i_sums = text.index('def write_sha256sums')
        i_pf = text.index('def run_host_preflight')
        self.assertLess(i_docs, i_sums)
        self.assertLess(i_sums, i_pf)

    def test_split_and_pack_accept_host_test_before_sums(self):
        split = SPLIT.read_text()
        pack = PACK.read_text()
        self.assertIn('--host-test-results', split)
        self.assertIn('--host-test-results', pack)
        self.assertIn('voyage_usb_kit_seal', split)
        self.assertIn('voyage_usb_kit_seal', pack)
        self.assertIn('Never rewrite HOST-TEST-RESULTS after this', split)
        self.assertIn('Do not rewrite HOST-TEST-RESULTS after this', pack)

    def test_post_sums_mutation_fails_preflight_reseal_fixes(self):
        import sys
        sys.path.insert(0, str(ROOT / 'tools'))
        from voyage_usb_kit_seal import seal_kit, sha_file

        with tempfile.TemporaryDirectory() as td:
            kit = Path(td) / 'kit'
            docs = kit / 'COPY-TO-KINDLE' / 'documents'
            docs.mkdir(parents=True)
            (kit / 'VOLUMES').mkdir()
            (kit / 'META').mkdir()
            entry = docs / 'VoyageExperimental-offline.sh'
            entry.write_text('#!/bin/sh\necho offline\n')
            entry.chmod(0o755)
            pay = b'payload-bytes-for-test'
            # One volume part
            (kit / 'VOLUMES' / 'readom-system-experimental-0.img.zst.part00').write_bytes(pay)
            audit = {
                'schema': 1,
                'offline_only': True,
                'entry': {
                    'name': 'VoyageExperimental-offline.sh',
                    'bytes': entry.stat().st_size,
                    'sha256': sha_file(entry),
                },
                'payload_system': {
                    'name': 'readom-system-experimental-0.img.zst',
                    'bytes': len(pay),
                    'sha256': sha(pay),
                },
                'fat_space_bytes': {
                    'free_before_copy_mib': 1.0,
                    'free_after_copy_mib': 1.0,
                },
            }
            (kit / 'AUDIT-MANIFEST.json').write_text(json.dumps(audit, indent=2) + '\n')
            (kit / 'EXPERIMENTAL-PRIVATE-NOT-RELEASE').write_text('private\n')
            (kit / 'META' / 'SPLIT-MANIFEST.json').write_text(json.dumps({
                'schema': 1,
                'entry': audit['entry'],
                'payload_system': audit['payload_system'],
                'volumes': ['readom-system-experimental-0.img.zst.part00'],
            }, indent=2) + '\n')
            # Minimal preflight matching production dual-layout checker
            (kit / 'HOST-PREFLIGHT.sh').write_text('''#!/bin/sh
set -eu
cd "$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
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
  echo "HOST-PREFLIGHT: missing payload" >&2
  exit 1
fi
export LAYOUT
python3 - <<'PY'
import hashlib, json, os
from pathlib import Path
root=Path('.')
def sha(p):
    h=hashlib.sha256(); h.update(p.read_bytes()); return h.hexdigest()
audit=json.loads((root/'AUDIT-MANIFEST.json').read_text())
assert audit.get('offline_only') is True
listed={}
for line in (root/'SHA256SUMS').read_text().splitlines():
    if not line.strip(): continue
    digest,name=line.split('  ',1)
    listed[name]=digest
for path in sorted(root.rglob('*')):
    if not path.is_file() or path.name=='SHA256SUMS': continue
    rel=path.relative_to(root).as_posix()
    assert rel in listed, 'missing from SHA256SUMS: '+rel
    assert sha(path)==listed[rel], 'SHA256SUMS mismatch: '+rel
print('HOST-PREFLIGHT: OK')
print('layout', os.environ['LAYOUT'])
print('free_before_copy_mib', audit['fat_space_bytes']['free_before_copy_mib'])
print('free_after_copy_mib', audit['fat_space_bytes']['free_after_copy_mib'])
PY
''')
            (kit / 'HOST-PREFLIGHT.sh').chmod(0o755)

            frozen = Path(td) / 'HOST-TEST-RESULTS.txt'
            frozen.write_text('PASS fake-host-tests round-1\n')
            evidence1 = Path(td) / 'evidence1.json'
            seal_kit(kit, {'HOST-TEST-RESULTS.txt': frozen},
                     run_preflight=True, evidence_out=evidence1)
            self.assertEqual(json.loads(evidence1.read_text())['host_preflight']['exit'], 0)

            # Post-SUMS mutation must break preflight (the t137u failure mode).
            (kit / 'HOST-TEST-RESULTS.txt').write_text('PASS fake-host-tests round-1\nMUTATED\n')
            bad = subprocess.run(['sh', 'HOST-PREFLIGHT.sh'], cwd=str(kit),
                                 capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn('SHA256SUMS mismatch', bad.stderr + bad.stdout)

            # Re-seal with frozen file restores exit 0 without touching payload parts.
            frozen2 = Path(td) / 'HOST-TEST-RESULTS-sealed.txt'
            frozen2.write_text('PASS fake-host-tests round-1\nsealed\n')
            evidence2 = Path(td) / 'evidence2.json'
            seal_kit(kit, {'HOST-TEST-RESULTS.txt': frozen2},
                     run_preflight=True, evidence_out=evidence2)
            self.assertEqual(json.loads(evidence2.read_text())['host_preflight']['exit'], 0)
            # Volume bytes unchanged
            self.assertEqual(
                (kit / 'VOLUMES' / 'readom-system-experimental-0.img.zst.part00').read_bytes(),
                pay)


if __name__ == '__main__':
    unittest.main()
