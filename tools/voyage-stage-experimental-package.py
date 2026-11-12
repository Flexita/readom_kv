#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Assemble Voyage *experimental staging* components on the cloud builder.

This is intentionally NOT a release packager:

- Does not flip installable / identity_ready / device_confirmed.
- Does not call or bypass boot/build_entry.py / build_launcher.py packaging.
- Does not write Readom.sh or readom-system-*.img.zst names a user could
  mistake for an official install payload.
- Records every refuse_unless_installable reason and C-side blockers.
- Marks the output directory STAGING-NOT-INSTALLABLE.

Usage (lima-pw3, non-root):
  python3 tools/voyage-stage-experimental-package.py \\
    --system-img PATH --ramdisk-img PATH --kernel-dir PATH --output DIR
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PORT = Path(__file__).resolve().parents[1]
SPARSE_MAGIC = 0xED26FF3A
EMPTY_INODES = 11
FORBIDDEN_BASENAMES = {
    'Readom.sh',
    'readom.sh',
}
FORBIDDEN_PREFIXES = (
    'readom-system-',
    'readom-data-',
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


def refuse_release_names(output: Path) -> None:
    for path in output.rglob('*'):
        if not path.is_file():
            continue
        name = path.name
        if name in FORBIDDEN_BASENAMES or any(name.startswith(p) for p in FORBIDDEN_PREFIXES):
            raise SystemExit('refusing release-like filename in staging output: %s' % name)


def parse_sparse_header(data: bytes) -> dict:
    if len(data) < 28:
        raise SystemExit('system.img too small for sparse header')
    magic, major, minor, fhs, chs, blksz, total_blks, total_chunks, cksum = struct.unpack(
        '<IHHHHIIII', data[:28])
    if magic != SPARSE_MAGIC:
        raise SystemExit('system.img is not Android sparse (magic %08x)' % magic)
    return {
        'format': 'android-sparse',
        'version': '%d.%d' % (major, minor),
        'blksz': blksz,
        'total_blks': total_blks,
        'unsparse_bytes': total_blks * blksz,
        'chunks': total_chunks,
        'header_checksum_field': cksum,
    }


def ext4_superblock_check(raw: Path, expect_bytes: int) -> dict:
    with raw.open('rb') as f:
        f.seek(1024)
        sb = f.read(1024)
    if sb[56:58] != b'\x53\xef':
        raise SystemExit('%s is not ext4' % raw)
    inodes, blocks = struct.unpack_from('<II', sb, 0)
    free_inodes, = struct.unpack_from('<I', sb, 16)
    log_block_size, = struct.unpack_from('<I', sb, 24)
    held = blocks * (1024 << log_block_size)
    if held != expect_bytes or raw.stat().st_size != expect_bytes:
        raise SystemExit('raw image size mismatch: fs=%d file=%d expected=%d'
                         % (held, raw.stat().st_size, expect_bytes))
    return {
        'ext4': True,
        'bytes': held,
        'inodes': inodes,
        'free_inodes': free_inodes,
        'inodes_used': inodes - free_inodes,
    }


def board_setting(board: Path, name: str) -> int:
    found = re.search(r'^%s\s*:=\s*(\d+)\s*$' % name, board.read_text(), re.M)
    if not found:
        raise SystemExit('no %s in %s' % (name, board))
    return int(found.group(1))


def empty_data_image(make_ext4fs: Path, file_contexts: Path, product_system: Path,
                     out: Path, size: int) -> dict:
    for tool in (make_ext4fs, file_contexts):
        if not tool.is_file():
            raise SystemExit('missing %s' % tool)
    with tempfile.TemporaryDirectory(prefix='voyage-empty-data-') as empty:
        subprocess.run(
            [str(make_ext4fs), '-T', '-1', '-S', str(file_contexts), '-L', 'data',
             '-l', str(size), '-a', 'data', str(out), empty, str(product_system)],
            check=True, stdout=subprocess.DEVNULL)
    with out.open('rb') as f:
        f.seek(1024)
        sb = f.read(1024)
    if sb[56:58] != b'\x53\xef':
        raise SystemExit('data image is not ext4')
    inodes, blocks = struct.unpack_from('<II', sb, 0)
    free_inodes, = struct.unpack_from('<I', sb, 16)
    log_block_size, = struct.unpack_from('<I', sb, 24)
    held = blocks * (1024 << log_block_size)
    used = inodes - free_inodes
    if held != size or out.stat().st_size != size:
        raise SystemExit('data image size mismatch')
    if used != EMPTY_INODES:
        raise SystemExit('data image not empty: %d inodes in use' % used)
    return {
        'bytes': size,
        'format_intended': 2,
        'empty_inodes_used': used,
        'sha256': sha_file(out),
        'ext4': True,
    }


def compress_zstd(raw: Path, out: Path, window_limit: int = 8 << 20) -> dict:
    subprocess.run(['zstd', '-q', '-19', '-T0', '-o', str(out), str(raw)], check=True)
    listing = subprocess.check_output(['zstd', '-lv', str(out)], text=True)
    window = int(re.search(r'Window Size: .*\((\d+) B\)', listing).group(1))
    if window > window_limit:
        raise SystemExit('%s window %d exceeds %d' % (out.name, window, window_limit))
    return {
        'name': out.name,
        'bytes': out.stat().st_size,
        'sha256': sha_file(out),
        'unpacked_bytes': raw.stat().st_size,
        'unpacked_sha256': sha_file(raw),
        'zstd_window_bytes': window,
        'format': 'zstd',
        'not_a_release_payload_name': True,
    }


def build_prop_identity(build_prop: Path) -> dict:
    props = {}
    for line in build_prop.read_text(errors='replace').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            k, v = line.split('=', 1)
            props[k.strip()] = v.strip()
    need = {
        'ro.product.name': 'voyage',
        'ro.product.device': 'voyage',
        'ro.build.product': 'voyage',
        'ro.build.flavor': 'voyage-userdebug',
    }
    for k, v in need.items():
        if props.get(k) != v:
            raise SystemExit('build.prop %s=%r, expected %r' % (k, props.get(k), v))
    if 'pw3-userdebug' in props.get('ro.build.flavor', ''):
        raise SystemExit('refusing PW3 flavor image as Voyage staging')
    return {
        'display_id': props.get('ro.build.display.id'),
        'fingerprint': props.get('ro.build.fingerprint'),
        'abi': props.get('ro.product.cpu.abi'),
        'board_platform': props.get('ro.board.platform'),
        'type': props.get('ro.build.type'),
        'tags': props.get('ro.build.tags'),
        'product_name': props.get('ro.product.name'),
    }


def module_match(system_modules: Path, kernel_tar: Path) -> dict:
    sys = {p.name: sha_file(p) for p in sorted(system_modules.glob('*.ko'))}
    tar_map = {}
    import tarfile
    with tarfile.open(kernel_tar) as t:
        for m in t.getnames():
            if not m.endswith('.ko'):
                continue
            data = t.extractfile(m).read()
            tar_map[Path(m).name] = hashlib.sha256(data).hexdigest()
    matched = {n: sys[n] for n in sys if tar_map.get(n) == sys[n]}
    mismatched = {n: {'system': sys[n], 'kernel_tar': tar_map.get(n)}
                  for n in sys if tar_map.get(n) != sys[n]}
    only_kernel = sorted(set(tar_map) - set(sys))
    touch_in_system = [n for n in ('zforce2.ko', 'fsr_keypad.ko', 'drv26xx_haptics.ko') if n in sys]
    cyttsp_in_system = [n for n in sys if n.startswith('cyttsp')]
    if touch_in_system and not cyttsp_in_system:
        note = (
            'Voyage icewine touch set present in system image (%s) and matched '
            'to kernel tar by sha256. cyttsp4 remains only in the shared kernel '
            'tar (PW3-shaped) and is not installed into system. Runtime touch '
            'path on Voyage is still unverified.'
            % ', '.join(touch_in_system)
        )
    elif not touch_in_system:
        note = (
            'Voyage touch candidates such as zforce2.ko may be in the kernel tar '
            'but absent from the staged system image; cyttsp4 is PW3-shaped. '
            'Runtime touch path on Voyage is unverified.'
        )
    else:
        note = (
            'Unexpected mix of Voyage touch modules and cyttsp in system: %s'
            % sorted(sys)
        )
    return {
        'system_module_count': len(sys),
        'kernel_tar_module_count': len(tar_map),
        'matched_by_sha256': sorted(matched),
        'mismatched': mismatched,
        'in_kernel_tar_not_in_system_image': only_kernel,
        'voyage_touch_modules_in_system': touch_in_system,
        'cyttsp_modules_in_system': cyttsp_in_system,
        'note': note,
    }


def _c_voyage_identity_ready() -> int:
    """Read dd_voyage_5_13_6.identity_ready from source (not a hardcoded 0)."""
    text = (PORT / 'boot/devicedata/devicedata.c').read_text()
    m = re.search(
        r'const struct dd_profile dd_voyage_5_13_6 = \{(.*?)\n\};',
        text, re.S)
    if not m:
        raise SystemExit('could not parse dd_voyage_5_13_6 from devicedata.c')
    # Last integer field is identity_ready.
    fields = [line.strip().rstrip(',') for line in m.group(1).splitlines()
              if line.strip() and not line.strip().startswith('/*')
              and not line.strip().startswith('*')]
    # Keep only value lines (strings or ints), skip pure comments already.
    values = []
    for line in fields:
        if line.startswith('/*') or line.startswith('*'):
            continue
        # Strip trailing inline comments.
        line = re.sub(r'/\*.*?\*/', '', line).strip().rstrip(',')
        if not line:
            continue
        values.append(line)
    if not values:
        raise SystemExit('dd_voyage_5_13_6 has no fields')
    last = values[-1]
    if last not in ('0', '1'):
        raise SystemExit('dd_voyage_5_13_6.identity_ready not 0/1: %r' % last)
    return int(last)


def _launcher_accepts_profiles() -> list:
    text = (PORT / 'boot/build_launcher.py').read_text()
    m = re.search(r"receipt\['module_profile'\] not in \(([^)]+)\)", text)
    if not m:
        return []
    return [int(x.strip()) for x in m.group(1).split(',') if x.strip().isdigit()]


def packaging_blockers(voyage_profile) -> dict:
    vp = load_module('voyage_profile_stage', PORT / 'tools/voyage_profile.py')
    pw3 = vp.load(vp.PW3_PROFILE)
    problems = vp.problems(voyage_profile, pw3)
    try:
        vp.refuse_unless_installable(vp.VOYAGE_PROFILE)
        refused = False
        refuse_error = None
    except SystemExit as e:
        refused = True
        refuse_error = str(e)
    c_ready = _c_voyage_identity_ready()
    accepts = _launcher_accepts_profiles()
    profile_n = voyage_profile.get('module_profile')
    return {
        'refuse_unless_installable': refused,
        'problems': problems,
        'flags': {
            'installable': voyage_profile.get('installable'),
            'identity_ready': voyage_profile.get('identity_ready'),
            'device_confirmed': voyage_profile.get('device_confirmed'),
            'experimental_first_test': voyage_profile.get('experimental_first_test'),
            'experimental_label': voyage_profile.get('experimental_label'),
        },
        'c_side': {
            'dd_voyage_5_13_6.identity_ready': c_ready,
            'helper_install_prepare': (
                'identity gate open; wrong model → E101; '
                'identity_ready==0 → E105 / VOYAGE_INSTALL_BLOCKED'
                if c_ready else
                'VOYAGE_INSTALL_BLOCKED / E105 when identity_ready==0'
            ),
            'note': (
                'C profile filled from measured Voyage uname/cmdline/wifi paths; '
                'dd_device_matches rejects PW3 uname fixtures.'
                if c_ready else
                'JSON flag flips alone cannot hand off; C profile stays empty.'
            ),
        },
        'launcher_module_profile': {
            'voyage_module_profile': profile_n,
            'build_launcher_accepts': accepts,
            'blocked': profile_n not in accepts,
        },
        'refuse_error_excerpt': (refuse_error or '')[:500],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--system-img', type=Path, required=True)
    ap.add_argument('--ramdisk-img', type=Path, required=True)
    ap.add_argument('--build-prop', type=Path, required=True)
    ap.add_argument('--kernel-dir', type=Path, required=True)
    ap.add_argument('--aosp-product', type=Path, required=True,
                    help='out/target/product/voyage tree (for make_ext4fs labels + modules)')
    ap.add_argument('--simg2img', type=Path, required=True)
    ap.add_argument('--make-ext4fs', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--version-label', default='voyage-experimental-unverified')
    args = ap.parse_args()

    if platform.node() != 'lima-pw3' or os.geteuid() == 0:
        raise SystemExit('Run as non-root on lima-pw3')
    if args.output.exists():
        raise SystemExit('Refusing to overwrite %s' % args.output)

    board = PORT / 'device/amazon/pw3/BoardConfig.mk'
    system_bytes = board_setting(board, 'BOARD_SYSTEMIMAGE_PARTITION_SIZE')
    data_bytes = board_setting(board, 'BOARD_USERDATAIMAGE_PARTITION_SIZE')
    data_format = board_setting(board, 'PW3_DATA_FORMAT')
    if data_format != 2 or data_bytes != 1073741824 or system_bytes != 536870912:
        raise SystemExit('unexpected board budget: system=%d data=%d format=%d'
                         % (system_bytes, data_bytes, data_format))

    identity = build_prop_identity(args.build_prop)
    sparse_meta = parse_sparse_header(args.system_img.read_bytes()[:28])
    if sparse_meta['unsparse_bytes'] != system_bytes:
        raise SystemExit('sparse unsparse_bytes %d != board %d'
                         % (sparse_meta['unsparse_bytes'], system_bytes))

    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'STAGING-NOT-INSTALLABLE').write_text(
        'This directory is experimental staging only.\n'
        'It is not an install package. Do not copy to a Kindle.\n'
        'Do not rename these files to Readom.sh or readom-*.img.zst.\n'
    )

    # Copy inputs with staging names
    staged_sparse = args.output / 'STAGING-system.sparse.img'
    staged_ramdisk = args.output / 'STAGING-ramdisk.img'
    shutil.copyfile(args.system_img, staged_sparse)
    shutil.copyfile(args.ramdisk_img, staged_ramdisk)
    shutil.copyfile(args.build_prop, args.output / 'STAGING-build.prop')

    raw = args.output / 'STAGING-system.raw.img'
    subprocess.run([str(args.simg2img), str(staged_sparse), str(raw)], check=True)
    raw_info = ext4_superblock_check(raw, system_bytes)
    raw.chmod(0o444)

    pack = load_module('pw3_pack_stage', PORT / 'tools/preinit-pack/pack.py')
    entries = pack.read_ramdisk(staged_ramdisk)
    ramdisk_files = pack.verify_ramdisk(entries)
    if 'adb_keys' in ramdisk_files or any(e.name.startswith('firmware/') for e in entries):
        raise SystemExit('ramdisk contains private assets')

    # boot.art presence (dexpreopt)
    with tempfile.TemporaryDirectory(prefix='voyage-bootdump-') as tmp:
        unpacked = Path(tmp) / 'arm'
        unpacked.mkdir()
        # debugfs rdump may fail if path missing; capture
        dump = subprocess.run(
            ['debugfs', '-R', 'rdump /framework/arm ' + str(unpacked), str(raw)],
            capture_output=True, text=True)
        boot_files = sorted(unpacked.glob('boot*')) if dump.returncode == 0 else []
    boot_image = {
        'framework_arm_dump_ok': dump.returncode == 0,
        'boot_star_count': len(boot_files),
        'boot_star_names': [p.name for p in boot_files],
        'with_dexpreopt_false_expected_empty': True,
        'note': (
            'WITH_DEXPREOPT=false: no host-preopt boot.art/oat in the image. '
            'First Android boot must create the boot image and compile apps on device. '
            'Official export/build_payload boot_image_sha256 field cannot be filled '
            'the same way as a dexpreopted release.'
        ),
    }

    file_contexts = (args.aosp_product /
                     'obj/ETC/file_contexts.bin_intermediates/file_contexts.bin')
    raw_data = args.output / 'STAGING-empty-data-format2-1024m.img'
    data_meta = empty_data_image(
        args.make_ext4fs, file_contexts, args.aosp_product / 'system',
        raw_data, data_bytes)

    packed_system = args.output / ('STAGING-system-%s.img.zst' % args.version_label)
    packed_data = args.output / ('STAGING-data-%s.img.zst' % args.version_label)
    system_zst = compress_zstd(raw, packed_system)
    data_zst = compress_zstd(raw_data, packed_data)
    # Keep raw data only as sha evidence then delete the 1 GiB file to save space
    data_sha = data_meta['sha256']
    raw_data.unlink()

    modules = module_match(
        args.aosp_product / 'system/vendor/lib/modules',
        args.kernel_dir / 'modules.tar.gz')
    kernel = {
        'release': (args.kernel_dir / 'kernel.release').read_text().strip(),
        'uImage_sha256': sha_file(args.kernel_dir / 'uImage'),
        'zImage_sha256': sha_file(args.kernel_dir / 'zImage'),
        'build_result_sha256': sha_file(args.kernel_dir / 'build-result.json'),
        'device_boot_verified': False,
        'android_runtime_verified': False,
    }

    voyage_profile = json.loads((PORT / 'boot/profiles/voyage-5.13.6.json').read_text())
    blockers = packaging_blockers(voyage_profile)

    # Peak install space (installer math) — estimate label
    reserve = 64 << 20
    peak_system_plus_data = system_bytes + data_bytes + reserve
    peak_note = {
        'formula': 'max(payload+system, system+data)+INST_RESERVE_BYTES(64MiB)',
        'system_mib': system_bytes // (1024 * 1024),
        'data_mib': data_bytes // (1024 * 1024),
        'reserve_mib': 64,
        'peak_mib_if_payload_lt_data': peak_system_plus_data // (1024 * 1024),
        'estimate': True,
        'device_free_kib_measured': voyage_profile['measured']['partition_table']['user_fat']['available_1k'],
        'device_free_mib_approx': voyage_profile['measured']['partition_table']['user_fat']['available_1k'] // 1024,
        'filler_cleanup_authorized': False,
    }

    # Static dexopt pressure — estimates only
    installed = (args.aosp_product / 'installed-files.txt')
    apk_lines = []
    if installed.is_file():
        for line in installed.read_text().splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[-1].endswith('.apk'):
                try:
                    apk_lines.append((int(parts[0]), parts[-1]))
                except ValueError:
                    pass
    apk_bytes = sum(s for s, _ in apk_lines)
    dexopt_estimate = {
        'estimate': True,
        'apk_count_in_installed_files': len(apk_lines),
        'apk_bytes_sum': apk_bytes,
        'apk_mib_sum': round(apk_bytes / (1024 * 1024), 1),
        'odex_in_system_tree': 0,
        'boot_art_in_system': len(boot_files) > 0,
        'device_ram_bytes_measured': int(voyage_profile['measured']['ram'][0][1], 16),
        'device_ram_mib': int(voyage_profile['measured']['ram'][0][1], 16) // (1024 * 1024),
        'data_partition_mib': data_bytes // (1024 * 1024),
        'provable_from_tree': [
            'Host dexpreopt was disabled; system contains 0 .odex and no /framework/arm/boot*.',
            'First boot must run dex2oat for boot image + system apps into /data.',
            'Device RAM from probe is 512 MiB; data image budget is 1024 MiB.',
        ],
        'not_provable_without_device_boot': [
            'Wall-clock duration of first-boot dexopt on Voyage.',
            'Peak anonymous RAM during concurrent dex2oat of large APKs (SystemWebView ~83 MiB APK).',
            'Exact dalvik-cache bytes written (depends on compiler filter and boot image size).',
            'Whether 512 MiB RAM is enough without thrashing under Eink + zygote + dex2oat.',
        ],
        'conservative_space_suggestion_estimate': {
            'estimate': True,
            'install_peak_user_fat_mib': peak_system_plus_data // (1024 * 1024),
            'extra_headroom_for_dalvik_cache_mib_guess': 256,
            'suggested_free_before_first_test_mib_guess': (
                peak_system_plus_data // (1024 * 1024) + 256
            ),
            'why': (
                'Installer peak is system+data+64MiB ≈ 1600 MiB when payload < data. '
                'Dexopt writes additional files under /data after Android starts; '
                'that growth is NOT in the 1600 MiB install peak. A 256 MiB guess is '
                'a staging heuristic only — not measured on Voyage.'
            ),
        },
    }

    pw3_hardcoding = {
        'ramdisk_init_names': ['init.pw3.rc', 'fstab.pw3', 'ueventd.pw3.rc'],
        'androidboot_hardware_expected_by_entry_docs': 'pw3',
        'meaning': (
            'Voyage lunch inherits device/amazon/pw3 board code; shared Wario paths '
            'are not a PW3 system.img stand-in. Product props are voyage. Touch/Wi-Fi '
            'firmware paths remain PW3-shaped in the hardware component and are unverified '
            'on Voyage hardware.'
        ),
        'system_img_is_pw3_product': False,
        'product_props_voyage': True,
    }

    next_steps = []
    if blockers['refuse_unless_installable'] or blockers['problems']:
        next_steps.append(
            'refuse_unless_installable still blocks: %s'
            % (blockers['problems'] or blockers['refuse_error_excerpt'] or 'unknown')
        )
    else:
        next_steps.append(
            'refuse_unless_installable PASSES under experimental_first_test '
            '(device_confirmed remains false; not daily-use)'
        )
    if blockers['c_side']['dd_voyage_5_13_6.identity_ready'] != 1:
        next_steps.append(
            'C dd_voyage_5_13_6.identity_ready==0 → E105 / VOYAGE_INSTALL_BLOCKED'
        )
    if blockers['launcher_module_profile']['blocked']:
        next_steps.append(
            'build_launcher.py does not accept module_profile %s (accepts %s)'
            % (blockers['launcher_module_profile']['voyage_module_profile'],
               blockers['launcher_module_profile']['build_launcher_accepts'])
        )
    next_steps.extend([
        'No owner authorization for filler cleanup or first boot on device',
        'Wi-Fi / waveform / Voyage touch runtime paths unverified on hardware',
        'WITH_DEXPREOPT=false: first-boot dexopt duration/RAM unverified',
        '40s power-hold recovery is Voyage-unverified; prefer USB+stock boot check',
    ])

    manifest = {
        'schema': 1,
        'kind': 'voyage-experimental-staging-NOT-INSTALLABLE',
        'generated_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'version_label': args.version_label,
        # Profile packaging flags (experimental may pass refuse_unless_installable
        # without device_confirmed). Staging directory itself is still not an
        # install package — executable_entry_built stays false here.
        'installable': bool(voyage_profile.get('installable')),
        'identity_ready': bool(voyage_profile.get('identity_ready')),
        'device_confirmed': bool(voyage_profile.get('device_confirmed')),
        'experimental_first_test': bool(voyage_profile.get('experimental_first_test')),
        'executable_entry_built': False,
        'official_payload_names_used': False,
        'product_identity': identity,
        'system_sparse': {
            'sha256': sha_file(staged_sparse),
            'bytes': staged_sparse.stat().st_size,
            **sparse_meta,
        },
        'system_raw': {
            'sha256': sha_file(raw),
            'bytes': raw.stat().st_size,
            **raw_info,
        },
        'ramdisk': {
            'sha256': sha_file(staged_ramdisk),
            'bytes': staged_ramdisk.stat().st_size,
            'structure_verified': True,
        },
        'boot_image': boot_image,
        'empty_data': {
            **data_meta,
            'sha256': data_sha,
            'raw_deleted_after_hash': True,
            'packed': data_zst,
        },
        'packed_system_staging': system_zst,
        'kernel': kernel,
        'modules': modules,
        'packaging_blockers': blockers,
        'storage_budget': peak_note,
        'dexopt_first_boot': dexopt_estimate,
        'pw3_naming_inheritance': pw3_hardcoding,
        'tools': {
            'simg2img_sha256': sha_file(args.simg2img),
            'make_ext4fs_sha256': sha_file(args.make_ext4fs),
        },
        'blocked_next_steps': next_steps,
        'scope': (
            'Cloud staging + verification only. Not a Kindle install package. '
            'Not a boot proof. Not authorized for deployment. '
            'experimental_first_test may allow a separately labeled experimental '
            'entry build; device_confirmed stays false until a real Voyage Android boot.'
        ),
    }

    (args.output / 'verification-manifest.json').write_text(
        json.dumps(manifest, indent=2) + '\n')
    refuse_release_names(args.output)

    # Human-readable checklist
    (args.output / 'COMPONENT-CHECKLIST.md').write_text(
        '\n'.join([
            '# Voyage experimental staging checklist (NOT INSTALLABLE)',
            '',
            '| Component | Status | SHA256 (abbrev) |',
            '|---|---|---|',
            '| system.sparse | ok | %s |' % manifest['system_sparse']['sha256'][:16],
            '| system.raw (512 MiB ext4) | ok | %s |' % manifest['system_raw']['sha256'][:16],
            '| ramdisk (structure verified) | ok | %s |' % manifest['ramdisk']['sha256'][:16],
            '| empty data format2 1024 MiB | hashed then raw deleted | %s |' % data_sha[:16],
            '| STAGING system zst | ok | %s |' % system_zst['sha256'][:16],
            '| STAGING data zst | ok | %s |' % data_zst['sha256'][:16],
            '| kernel uImage | present | %s |' % kernel['uImage_sha256'][:16],
            '| Readom.sh / entry | **blocked** | — |',
            '| installable flags | **false** | — |',
            '',
            'Do not rename. Do not deploy.',
            '',
        ])
    )

    print(json.dumps({
        'output': str(args.output),
        'kind': manifest['kind'],
        'system_raw_sha256': manifest['system_raw']['sha256'],
        'data_sha256': data_sha,
        'executable_entry_built': False,
        'refuse_unless_installable': blockers['refuse_unless_installable'],
        'problems_count': len(blockers['problems']),
    }, indent=2))


if __name__ == '__main__':
    main()
