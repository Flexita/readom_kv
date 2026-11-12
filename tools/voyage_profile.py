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
MEASURED_KEYS = (
    'eips_sha256', 'eips_bytes', 'uname_release', 'uname_version',
    'machine_id', 'stock_cmdline', 'ram', 'partition_table', 'stock_functions',
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
