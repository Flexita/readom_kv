# SPDX-License-Identifier: Apache-2.0
"""Refuse to build an installable entry until the device profile is measured.

QEMU (module_profile 2) is not a device and is left alone. Every other profile
has to say installable, and a Voyage profile (module_profile 3) also has to
carry a device reading that is not the Paperwhite 3 handoff record.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VOYAGE_PROFILE = ROOT / 'boot/profiles/voyage-5.13.6.json'
PW3_PROFILE = ROOT / 'boot/profiles/pw3-5.16.2.1.1.json'
# The stock display binary the PW3 entry pins. It is not a Voyage measurement.
PW3_EIPS_SHA256 = '73eb0d2532f9c899e98fb8feacb7a085ab0652f628f1c2c7b2e2d1cefae3f4ae'
# Keys that must be real device readings (or offline hashes of the matching
# stock Image). machine_id is not in this list: the ARM MACH_TYPE is not
# published by any ordinary proc file, and inventing a /proc reading of it
# would be false. See docs/design/voyage-port.md.
MEASURED_KEYS = (
    'eips_sha256', 'eips_bytes', 'uname_release', 'uname_version',
    'stock_cmdline', 'ram', 'partition_table', 'stock_functions',
)


def load(path):
    return json.loads(Path(path).read_text())


# Values the Voyage GPL member states on its own. A later device reading that
# matches them is evidence, not a copied Paperwhite measurement, and must not
# be rejected just because the PW3 profile contains the same number.
# mach-types in the Voyage member names mx6sl_wario as 4091. Makefile says 3.0.35.
SOURCE_SHARED_MACHINE_ID = 4091
SOURCE_SHARED_KERNEL_RELEASE = '3.0.35-lab126'


def _copied_pw3_handoff(profile, pw3):
    """Reject a Voyage profile that pastes PW3-only device readings.

    Machine id, the stock kernel release and a RAM map are not in this list.
    Forbidding a value the Voyage sources already state, or a map a device
    really reports, would force a fake difference. The readings that are
    refused are the ones taken off the Paperwhite: its eips binary, its uname
    build stamp, its command line and its kernel function bodies.
    """
    if profile.get('module_profile') != 3:
        return []
    measured = profile.get('measured') or {}
    found = []
    if measured.get('eips_sha256') == PW3_EIPS_SHA256:
        found.append('measured.eips_sha256 is the Paperwhite 3 display binary')
    if (measured.get('uname_version') and pw3.get('stock_kernel_version')
            and measured.get('uname_version') == pw3.get('stock_kernel_version')):
        found.append('measured.uname_version is the Paperwhite 3 uname string')
    cmdline = pw3.get('cmdline_base')
    if measured.get('stock_cmdline') and cmdline and measured.get('stock_cmdline') == cmdline:
        found.append('measured.stock_cmdline is the Paperwhite 3 command line')
    funcs = measured.get('stock_functions')
    pw3_funcs = pw3.get('stock_functions')
    if isinstance(funcs, dict) and isinstance(pw3_funcs, dict) and funcs == pw3_funcs:
        found.append('measured.stock_functions is the Paperwhite 3 function record')
    return found


def _voyage_machine_pin(profile):
    """Voyage MACH_TYPE is a source-proven build pin, not a /proc reading.

    Consumers: TARGET_MACHINE in the handoff module (native_init compares
    __machine_arch_type; transition.S loads it into r1 for the new kernel).
    ATAGs do not carry this number. The matching stock Image's machine_desc.nr
    and the GPL mach-types / defconfig already prove 4091.
    """
    if profile.get('module_profile') != 3:
        return []
    found = []
    measured = profile.get('measured') or {}
    if measured.get('machine_id') is not None:
        found.append(
            'measured.machine_id must stay null: no ordinary proc publishes only '
            'the ARM MACH_TYPE (do not invent a reading)')
    machine = profile.get('machine')
    source = profile.get('source') or {}
    stock_nr = source.get('stock_machine_desc_nr')
    if machine != SOURCE_SHARED_MACHINE_ID:
        found.append('machine is not the Voyage Wario MACH_TYPE 4091')
    if stock_nr != SOURCE_SHARED_MACHINE_ID:
        found.append('source.stock_machine_desc_nr does not prove MACH_TYPE 4091')
    return found


def problems(profile, pw3=None):
    """Why this profile must not be built into an entry someone can install."""
    if profile.get('module_profile') == 2:
        return []
    found = []
    if profile.get('installable') is not True:
        found.append('installable is not true')
    if profile.get('identity_ready') is not True:
        found.append('identity_ready is not true')
    if profile.get('device_confirmed') is not True:
        found.append('device_confirmed is not true')
    measured = profile.get('measured')
    if not isinstance(measured, dict):
        found.append('measured is missing')
        measured = {}
    for key in MEASURED_KEYS:
        if not measured.get(key):
            found.append('measured.%s is empty' % key)
    cmdline = measured.get('stock_cmdline')
    if isinstance(cmdline, str) and '[redacted]' in cmdline:
        found.append('measured.stock_cmdline contains a redacted value')
    found.extend(_voyage_machine_pin(profile))
    if pw3 is not None:
        found.extend(_copied_pw3_handoff(profile, pw3))
    return found


def refuse_unless_installable(path):
    """Exit unless `path` is a measured device profile. Returns the profile."""
    profile = load(path)
    pw3 = load(PW3_PROFILE) if PW3_PROFILE.is_file() else None
    found = problems(profile, pw3)
    if found:
        raise SystemExit(
            'refusing to build an installable entry from %s:\n%s'
            % (path, '\n'.join('  ' + item for item in found)))
    return profile
