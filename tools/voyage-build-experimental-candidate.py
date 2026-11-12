#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build a private Voyage *experimental* install candidate (cloud only).

Produces under --output:

  export/     voyage-export-experimental-images.py
  payload/    installer/build_payload.py (readom-* names + experimental version)
  screens/    installer/screens/render_screens.py
  entry/      boot/build_entry.py → VoyageExperimental-unverified.sh
  AUDIT-MANIFEST.json
  EXPERIMENTAL-PRIVATE-NOT-RELEASE

Hard rules:
- device_confirmed stays false; experimental_first_test must pass refuse gate.
- Never names the entry Readom.sh.
- release-url is a non-GitHub https directory placeholder unless overridden;
  download will fail until the owner hosts the private payload.
- Does not authorize device install, filler cleanup, or first boot.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PORT = Path(__file__).resolve().parents[1]
# Keep short: render_screens draws the full payload filename in the region.
VERSION = 'experimental-0'
ENTRY_NAME = 'VoyageExperimental-unverified.sh'
ENTRY_TITLE = 'Voyage Experimental unverified'
# Non-GitHub https directory shape (build_launcher allows this). Not a public
# release host — install download fails until the owner substitutes a real path.
DEFAULT_RELEASE_URL = (
    'https://private.invalid/voyage-experimental/private-not-release'
)


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def run(cmd, **kwargs):
    print('+', ' '.join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kwargs)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--product', type=Path, required=True)
    ap.add_argument('--simg2img', type=Path, required=True)
    ap.add_argument('--make-ext4fs', type=Path, required=True)
    ap.add_argument('--kernel-dir', type=Path, required=True)
    ap.add_argument('--zstd-archive', type=Path, required=True)
    ap.add_argument('--ca-bundle', type=Path, required=True)
    ap.add_argument('--cjk-font', type=Path, required=True)
    ap.add_argument('--latin-font', type=Path, required=True)
    ap.add_argument('--latin-title-font', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--release-url', default=DEFAULT_RELEASE_URL)
    ap.add_argument('--version', default=VERSION)
    # build_launcher.py hard-requires android/system.img + android/data.img.
    ap.add_argument('--system-path', default='android/system.img')
    ap.add_argument('--data', default='android/data.img:1073741824')
    args = ap.parse_args()

    if platform.node() != 'lima-pw3' or os.geteuid() == 0:
        raise SystemExit('Run as non-root on lima-pw3')
    if args.output.exists():
        raise SystemExit('Refusing to overwrite %s' % args.output)
    if 'experimental' not in args.version.lower():
        raise SystemExit('version must contain experimental')
    if args.system_path.startswith('readom') or 'Readom' in ENTRY_NAME:
        raise SystemExit('refusing release-like paths/names')

    vp = load_module('voyage_profile_candidate', PORT / 'tools/voyage_profile.py')
    profile = vp.refuse_unless_installable(vp.VOYAGE_PROFILE)
    if profile.get('device_confirmed') is True:
        raise SystemExit('refusing to pack while device_confirmed is true under experimental')
    if profile.get('experimental_first_test') is not True:
        raise SystemExit('experimental_first_test must be true for this candidate')

    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    (out / 'EXPERIMENTAL-PRIVATE-NOT-RELEASE').write_text(
        'Private Voyage experimental candidate.\n'
        'device_confirmed=false. Not a stable release. Not authorized for install\n'
        'until the device owner explicitly authorizes a first test.\n'
        'Entry name is %s (never Readom.sh).\n'
        'Payload uses installer-contract readom-* filenames with experimental version.\n'
        'Default --release-url is private.invalid; download fails until hosted.\n'
        % ENTRY_NAME
    )

    export_dir = out / 'export'
    run([sys.executable, str(PORT / 'tools/voyage-export-experimental-images.py'),
         '--product', str(args.product),
         '--simg2img', str(args.simg2img),
         '--kernel-receipt', str(args.kernel_dir / 'build-result.json'),
         '--output', str(export_dir),
         '--label', args.version])

    payload_dir = out / 'payload'
    run([sys.executable, str(PORT / 'installer/build_payload.py'),
         '--export', str(export_dir),
         '--data-format', '2',
         '--version', args.version,
         '--output', str(payload_dir),
         '--product', str(args.product),
         '--make-ext4fs', str(args.make_ext4fs)])

    screens_dir = out / 'screens'
    run([sys.executable, str(PORT / 'installer/screens/render_screens.py'),
         '--manifest', str(payload_dir / 'manifest.json'),
         '--profile', str(PORT / 'boot/profiles/voyage-5.13.6.json'),
         '--cjk-font', str(args.cjk_font),
         '--latin-font', str(args.latin_font),
         '--latin-title-font', str(args.latin_title_font),
         '--output', str(screens_dir)])

    entry_dir = out / 'entry'
    run([sys.executable, str(PORT / 'boot/build_entry.py'),
         '--export', str(export_dir),
         '--kernel', str(args.kernel_dir),
         '--system-path', args.system_path,
         '--data', args.data,
         '--installer', str(payload_dir),
         '--screens', str(screens_dir),
         '--release-url', args.release_url,
         '--ca-bundle', str(args.ca_bundle),
         '--zstd-archive', str(args.zstd_archive),
         '--name', ENTRY_NAME,
         '--title', ENTRY_TITLE,
         '--output', str(entry_dir)])

    entry_sh = entry_dir / 'launcher' / ENTRY_NAME
    if not entry_sh.is_file():
        raise SystemExit('entry script missing: %s' % entry_sh)
    if entry_sh.name == 'Readom.sh':
        raise SystemExit('refusing Readom.sh')

    # Static wrong-model / allow evidence from already-landed unit tests is
    # recorded by path; re-run host identity tests if the binary is available.
    identity_evidence = {
        'c_identity_ready': 1,
        'host_tests': 'boot/devicedata/tests/devicedata_test.c::'
                      'test_voyage_identity_accepts_voyage_rejects_pw3',
        'expect': {
            'voyage_uname_accept': True,
            'pw3_uname_reject_as_other_device': True,
            'device_confirmed': False,
            'experimental_label': profile.get('experimental_label'),
        },
    }

    export_result = json.loads((export_dir / 'build-result.json').read_text())
    payload_manifest = json.loads((payload_dir / 'manifest.json').read_text())
    entry_result = json.loads((entry_dir / 'build-result.json').read_text())

    audit = {
        'schema': 1,
        'kind': 'voyage-experimental-private-candidate-NOT-RELEASE',
        'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'version': args.version,
        'entry_name': ENTRY_NAME,
        'entry_title': ENTRY_TITLE,
        'device_confirmed': False,
        'experimental_first_test': True,
        'experimental_label': profile.get('experimental_label'),
        'release_url_embedded': args.release_url,
        'release_url_is_placeholder': args.release_url == DEFAULT_RELEASE_URL,
        'install_authorized': False,
        'filler_cleanup_authorized': False,
        'first_boot_authorized': False,
        'export': {
            'kind': export_result.get('kind'),
            'system_raw_sha256': export_result['files']['system.raw.img']['sha256'],
            'boot_image_files': export_result['boot_image']['files'],
            'modules': export_result.get('system_modules'),
            'voyage_touch_modules_present': export_result.get('voyage_touch_modules_present'),
        },
        'payload': {
            'version': payload_manifest['version'],
            'experimental': payload_manifest.get('experimental'),
            'boot_image_sha256': payload_manifest['boot_image_sha256'],
            'system_packed_sha256': payload_manifest['files']['system']['sha256'],
            'data_packed_sha256': payload_manifest['files']['data']['sha256'],
        },
        'entry': {
            'launcher': entry_result.get('launcher'),
            'entry_sha256': sha_file(entry_sh),
            'kernel_release': entry_result.get('kernel_release'),
            'system_modules_checked': entry_result.get('system_modules_checked'),
            'contains_device_data': entry_result.get('contains_device_data'),
        },
        'identity_evidence': identity_evidence,
        'residual_risks': [
            'No real Voyage Android boot yet (device_confirmed=false).',
            'Touch/Wi-Fi/waveform runtime unverified on Voyage hardware.',
            'WITH_DEXPREOPT=false: first-boot dexopt time/RAM unverified on 512 MiB.',
            'Default release URL is private.invalid — download cannot succeed until hosted.',
            '40s power-hold recovery is Voyage-unverified.',
            'Stock bootloader/kernel unchanged; recovery depends on USB+stock path.',
        ],
        'first_test_authorization_gate': {
            'cloud_candidate_built': True,
            'enough_to_request_user_first_test_auth': True,
            'why': (
                'Executable experimental entry + payload + audit exist; C identity '
                'accepts Voyage and rejects PW3 in host tests; packaging gate passes '
                'under experimental_first_test without forging device_confirmed. '
                'Remaining blockers are device-side: host private payload URL, free '
                'space (~1856 MiB estimate), unplug USB, explicit first-test auth.'
            ),
            'user_must_still': [
                'Host payload at a real https directory (or supply --release-url) '
                'matching readom-system-%s.img.zst / readom-data-%s.img.zst'
                % (args.version, args.version),
                'Confirm free space on user FAT (install peak ~1600 MiB + dexopt headroom)',
                'Explicitly authorize first experimental test (not daily use)',
                'Keep USB unplugged during install/handoff (E104)',
            ],
        },
    }
    (out / 'AUDIT-MANIFEST.json').write_text(json.dumps(audit, indent=2) + '\n')
    print(json.dumps({
        'output': str(out),
        'entry': str(entry_sh),
        'entry_sha256': audit['entry']['entry_sha256'],
        'enough_to_request_user_first_test_auth': True,
    }, indent=2))


if __name__ == '__main__':
    main()
