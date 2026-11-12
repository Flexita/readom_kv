#!/usr/bin/env python3
"""Materialize a pinned compiler once; never rewrite files used by live builds.

Accepts either:
  1) the unpublished project archive pinned by cross_compiler.archive_sha256, or
  2) a preinstalled tree whose .pw3-toolchain-revision matches cross_compiler.revision
     (public AOSP git checkout of that revision). Archive bytes are not reconstructible
     from googlesource/git-archive alone; revision mode is for hosts that lack the
     original lima archive file.
"""
import hashlib
import json
import os
import sys
import tarfile
from pathlib import Path

lock = json.loads(Path('/mnt/port/source-lock.json').read_text())['cross_compiler']
expected_archive = lock['archive_sha256']
expected_revision = lock['revision']
archive_arg, target = map(Path, sys.argv[1:3])
gcc = target / 'bin' / 'arm-linux-androidkernel-gcc'
rev_marker = target / '.pw3-toolchain-revision'
arch_marker = target / '.pw3-toolchain-archive-sha256'


def revision_ok() -> bool:
    return (
        rev_marker.is_file()
        and rev_marker.read_text().strip() == expected_revision
        and gcc.is_file()
    )


# Path "-" means: no archive; require a revision-matched preinstall.
if str(archive_arg) == '-' or not archive_arg.is_file():
    if revision_ok():
        sys.exit(0)
    raise SystemExit(
        'Compiler archive missing and toolchain is not revision-matched. '
        'Place source-lock cross_compiler archive at the path build-kernel expects, '
        'or run tools/materialize-cross-compiler-from-git.sh'
    )

digest = hashlib.sha256(archive_arg.read_bytes()).hexdigest()
if digest != expected_archive:
    # Fall back only when a public revision-matched tree is already installed.
    if revision_ok():
        sys.exit(0)
    raise SystemExit(
        'Compiler archive checksum mismatch (and no revision-matched toolchain). '
        f'got={digest} expected={expected_archive}'
    )

if arch_marker.exists():
    if arch_marker.read_text().strip() != expected_archive:
        raise SystemExit('Existing compiler pin differs; choose a new toolchain directory.')
    sys.exit(0)
target.mkdir(parents=True, exist_ok=True)
populated = any(target.iterdir())
with tarfile.open(archive_arg) as tar:
    for member in tar.getmembers():
        path = Path(member.name)
        if path.is_absolute() or '..' in path.parts:
            raise SystemExit('Unsafe compiler archive path')
        if member.issym() or member.islnk():
            link = Path(member.linkname)
            resolved = (target / path.parent / link).resolve()
            if target.resolve() not in resolved.parents:
                raise SystemExit('Compiler archive link leaves its tree')
        if member.isdev() or member.isfifo():
            raise SystemExit('Unexpected special compiler archive entry')
    if not populated:
        tar.extractall(target)
    # Adopt an existing project compiler only after verifying actual bytes and
    # symlinks. Verification is read-only even while another build is active.
    for member in tar.getmembers():
        path = target / member.name
        if member.isfile():
            if (
                not path.is_file()
                or hashlib.sha256(path.read_bytes()).digest()
                != hashlib.sha256(tar.extractfile(member).read()).digest()
            ):
                raise SystemExit('Existing compiler file differs: ' + member.name)
        elif member.issym():
            if not path.is_symlink() or os.readlink(path) != member.linkname:
                raise SystemExit('Existing compiler symlink differs: ' + member.name)
arch_marker.write_text(expected_archive + '\n')
