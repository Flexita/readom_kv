# SPDX-License-Identifier: Apache-2.0
"""Seal a Voyage USB offline kit: freeze docs, write SHA256SUMS last, preflight.

Order is intentional and fail-closed:

  1. Optional frozen docs (HOST-TEST-RESULTS, UPGRADE-PLAN, …) are installed
  2. SHA256SUMS is generated over every other file
  3. HOST-PREFLIGHT.sh is run (must exit 0)
  4. Nothing in this module mutates kit files after step 2

Callers that rewrite HOST-TEST-RESULTS (or any listed file) after sealing
invalidate the kit; re-run this tool instead of hand-editing SHA256SUMS.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

MIB = 1024 * 1024


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def install_frozen_docs(kit: Path, docs: dict[str, Path]) -> list[str]:
    """Copy frozen files into kit *before* SHA256SUMS. Returns installed relative paths."""
    installed = []
    for rel, src in sorted(docs.items()):
        if not src.is_file():
            raise SystemExit('frozen doc missing: %s' % src)
        dest = kit / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        installed.append(rel)
    return installed


def write_sha256sums(kit: Path) -> Path:
    """Write SHA256SUMS as the last content mutation for this seal."""
    sums = []
    for path in sorted(kit.rglob('*')):
        if path.is_file() and path.name != 'SHA256SUMS':
            sums.append('%s  %s' % (sha_file(path), path.relative_to(kit).as_posix()))
    out = kit / 'SHA256SUMS'
    out.write_text('\n'.join(sums) + '\n')
    return out


def run_host_preflight(kit: Path) -> dict:
    pre = kit / 'HOST-PREFLIGHT.sh'
    if not pre.is_file():
        raise SystemExit('HOST-PREFLIGHT.sh missing in %s' % kit)
    proc = subprocess.run(
        ['sh', str(pre)], cwd=str(kit), capture_output=True, text=True)
    return {
        'exit': proc.returncode,
        'stdout': proc.stdout,
        'stderr': proc.stderr,
    }


def run_reassemble(kit: Path, outdir: Path) -> dict:
    script = kit / 'REASSEMBLE-ON-HOST.sh'
    if not script.is_file():
        raise SystemExit('REASSEMBLE-ON-HOST.sh missing (full kits without split skip this)')
    if outdir.exists():
        raise SystemExit('refusing to overwrite reassemble outdir %s' % outdir)
    proc = subprocess.run(
        ['sh', str(script), str(outdir)], cwd=str(kit), capture_output=True, text=True)
    result = {'exit': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}
    if proc.returncode == 0:
        audit = json.loads((kit / 'AUDIT-MANIFEST.json').read_text())
        pay_name = audit['payload_system']['name']
        entry_name = audit['entry']['name']
        pay = outdir / 'documents' / pay_name
        entry = outdir / 'documents' / entry_name
        result['payload_sha256'] = sha_file(pay)
        result['entry_sha256'] = sha_file(entry)
        result['payload_expected'] = audit['payload_system']['sha256']
        result['entry_expected'] = audit['entry']['sha256']
        if result['payload_sha256'] != result['payload_expected']:
            raise SystemExit('reassembled payload sha mismatch')
        if result['entry_sha256'] != result['entry_expected']:
            raise SystemExit('reassembled entry sha mismatch')
    return result


def seal_kit(
    kit: Path,
    frozen_docs: dict[str, Path] | None = None,
    *,
    run_preflight: bool = True,
    reassemble_outdir: Path | None = None,
    evidence_out: Path | None = None,
) -> dict:
    """Install frozen docs (optional), write SHA256SUMS last, verify.

    After this returns successfully, do not edit any kit file other than by
    calling seal_kit again.
    """
    kit = kit.resolve()
    if not kit.is_dir():
        raise SystemExit('kit not a directory: %s' % kit)
    if not (kit / 'AUDIT-MANIFEST.json').is_file():
        raise SystemExit('AUDIT-MANIFEST.json missing')

    installed = []
    if frozen_docs:
        installed = install_frozen_docs(kit, frozen_docs)

    sums_path = write_sha256sums(kit)
    sums_sha = sha_file(sums_path)

    evidence = {
        'schema': 1,
        'kind': 'voyage-usb-kit-seal-evidence',
        'kit': str(kit),
        'frozen_docs_installed': installed,
        'sha256sums_sha256': sums_sha,
        'note': (
            'SHA256SUMS written after frozen docs; HOST-PREFLIGHT must pass. '
            'Do not mutate listed files afterward — re-seal instead.'
        ),
    }

    if run_preflight:
        pf = run_host_preflight(kit)
        evidence['host_preflight'] = {'exit': pf['exit'], 'stdout': pf['stdout'].strip()}
        if pf['exit'] != 0:
            raise SystemExit('HOST-PREFLIGHT exit %d\n%s\n%s' % (
                pf['exit'], pf['stdout'], pf['stderr']))

    if reassemble_outdir is not None:
        evidence['reassemble'] = run_reassemble(kit, reassemble_outdir)
        if evidence['reassemble']['exit'] != 0:
            raise SystemExit('REASSEMBLE exit %d\n%s\n%s' % (
                evidence['reassemble']['exit'],
                evidence['reassemble']['stdout'],
                evidence['reassemble']['stderr']))

    # Oversize check (Agent Store)
    overs = []
    for path in kit.rglob('*'):
        if path.is_file() and path.stat().st_size >= 128 * MIB:
            overs.append(path.relative_to(kit).as_posix())
    evidence['files_over_128mib'] = overs
    if overs:
        raise SystemExit('files >=128MiB: %s' % overs)

    if evidence_out is not None:
        # Evidence is *outside* the kit so it does not disturb SHA256SUMS.
        evidence_out.parent.mkdir(parents=True, exist_ok=True)
        evidence_out.write_text(json.dumps(evidence, indent=2) + '\n')

    return evidence
