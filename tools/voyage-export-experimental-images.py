#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Export a Voyage *experimental* AOSP image tree for private packaging.

Unlike tools/export-aosp-images.py this path:

- Targets product ``voyage`` (never packs a PW3 system.img as Voyage).
- Does not require the official aosp-system-job.json receipt (cloud
  experimental builds are not started by run-aosp-build-job.sh).
- Allows WITH_DEXPREOPT=false images that have zero /framework/arm/boot*
  files, and records that fact honestly in build-result.json.
- Marks the export experimental / not a release / not device_confirmed.

It still refuses private ramdisk assets and produces the same file layout
build_payload.py / build_entry.py consume (system.raw.img + build-result.json).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--product', type=Path, required=True,
                    help='out/target/product/voyage')
    ap.add_argument('--simg2img', type=Path, required=True)
    ap.add_argument('--kernel-receipt', type=Path, required=True,
                    help='android-core-kernel-voyage/build-result.json')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--label', default='voyage-experimental-unverified')
    args = ap.parse_args()

    if platform.node() != 'lima-pw3' or os.geteuid() == 0:
        raise SystemExit('Run as non-root on lima-pw3')
    if args.output.exists():
        raise SystemExit('Refusing to overwrite %s' % args.output)

    product = args.product.resolve()
    port = Path(__file__).resolve().parents[1]
    for name in ('system.img', 'ramdisk.img'):
        if not (product / name).is_file():
            raise SystemExit('missing %s' % (product / name))

    build_prop = (product / 'system/build.prop').read_text(errors='replace')
    if 'ro.product.device=voyage' not in build_prop and 'ro.product.name=voyage' not in build_prop:
        raise SystemExit('product tree is not voyage (build.prop identity)')

    pack = load_module('pw3_pack_voyage_exp', port / 'tools/preinit-pack/pack.py')
    entries = pack.read_ramdisk(product / 'ramdisk.img')
    ramdisk = pack.verify_ramdisk(entries)
    if 'adb_keys' in ramdisk or any(e.name.startswith('firmware/') for e in entries):
        raise SystemExit('Public build contains a private ramdisk asset')

    modules_dir = product / 'system/vendor/lib/modules'
    kos = sorted(modules_dir.glob('*.ko')) if modules_dir.is_dir() else []
    ko_names = [p.name for p in kos]
    for required in ('zforce2.ko', 'fsr_keypad.ko', 'drv26xx_haptics.ko',
                     'ath6kl_sdio.ko', 'cfg80211.ko', 'mxc_epdc_fb.ko'):
        if required not in ko_names:
            raise SystemExit('voyage export missing expected module %s (have %s)'
                             % (required, ko_names))
    if any(n.startswith('cyttsp') for n in ko_names):
        raise SystemExit('voyage export must not ship cyttsp (PW3 touch) modules: %s'
                         % [n for n in ko_names if n.startswith('cyttsp')])

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.voyage-exp-export-',
                                     dir=args.output.parent) as temp:
        stage = Path(temp) / 'images'
        stage.mkdir()
        records = {}
        for name in ('system.img', 'ramdisk.img'):
            original = product / name
            digest = sha_file(original)
            shutil.copyfile(original, stage / name)
            if sha_file(stage / name) != digest:
                raise SystemExit('Image copy mismatch: ' + name)
            records[name] = {'bytes': original.stat().st_size, 'sha256': digest}

        subprocess.run([str(args.simg2img), str(stage / 'system.img'),
                        str(stage / 'system.raw.img')], check=True)
        raw = stage / 'system.raw.img'
        pack.ext4_info(raw)
        records[raw.name] = {'bytes': raw.stat().st_size, 'sha256': sha_file(raw)}
        raw.chmod(0o444)

        unpacked = Path(temp) / 'boot'
        unpacked.mkdir()
        dump = subprocess.run(
            ['debugfs', '-R', 'rdump /framework/arm ' + str(unpacked), str(raw)],
            capture_output=True, text=True)
        boot_files = sorted((unpacked / 'arm').glob('boot*')) if dump.returncode == 0 else []
        boot_image = hashlib.sha256()
        for path in boot_files:
            boot_image.update(('%s %s\n' % (path.name, sha_file(path))).encode())
        # Empty digest is intentional when WITH_DEXPREOPT=false: first boot
        # must create the boot image on device. Do not invent boot.art bytes.
        boot_sha = boot_image.hexdigest()

        built_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        result = {
            'schema': 1,
            'kind': 'voyage-experimental-export-NOT-RELEASE',
            'label': args.label,
            'experimental': True,
            'device_confirmed': False,
            'built_utc': built_utc,
            'build_completed': True,
            'build_log_sha256': None,
            'kernel_receipt_sha256': sha_file(args.kernel_receipt),
            'files': records,
            'boot_image': {
                'files': len(boot_files),
                'sha256': boot_sha,
                'with_dexpreopt': False,
                'note': (
                    'Zero boot* files expected under WITH_DEXPREOPT=false. '
                    'First Android boot must create boot.art and compile apps '
                    'on device. This is not a dexpreopted release export.'
                ),
            },
            'variant': 'userdebug',
            'installclean': None,
            'build_datetime': None,
            'build_version': args.label,
            'scope': (
                'Voyage experimental private packaging only. Not installable '
                'firmware, not a device boot proof, not a public release.'
            ),
            'private_firmware_injected': False,
            'ramdisk_structure_verified': True,
            'product': 'voyage',
            'system_modules': ko_names,
            'voyage_touch_modules_present': [
                n for n in ('zforce2.ko', 'fsr_keypad.ko', 'drv26xx_haptics.ko')
                if n in ko_names
            ],
        }
        (stage / 'build-result.json').write_text(json.dumps(result, indent=2) + '\n')
        (stage / 'EXPERIMENTAL-NOT-RELEASE').write_text(
            'This export is private experimental packaging for Voyage.\n'
            'device_confirmed is false. Do not treat as a stable release.\n'
        )
        stage.rename(args.output)

    print(json.dumps({
        'output': str(args.output),
        'system_raw_sha256': records['system.raw.img']['sha256'],
        'boot_image_files': len(boot_files),
        'modules': ko_names,
    }, indent=2))


if __name__ == '__main__':
    main()
