# SPDX-License-Identifier: Apache-2.0
"""Staging output must never look like a release installer."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load():
    path = ROOT / 'tools/voyage-stage-experimental-package.py'
    spec = importlib.util.spec_from_file_location('voyage_stage', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class VoyageStageExperimental(unittest.TestCase):
    def test_forbidden_release_names(self):
        mod = load()
        self.assertIn('Readom.sh', mod.FORBIDDEN_BASENAMES)
        self.assertTrue(any(p.startswith('readom-system-') for p in mod.FORBIDDEN_PREFIXES))
        self.assertTrue(any(p.startswith('readom-data-') for p in mod.FORBIDDEN_PREFIXES))

    def test_script_documents_fail_closed(self):
        body = (ROOT / 'tools/voyage-stage-experimental-package.py').read_text()
        self.assertIn('NOT-INSTALLABLE', body)
        self.assertIn('refuse_unless_installable', body)
        self.assertNotIn('installable = True', body)
        self.assertNotIn('installable=True', body)


if __name__ == '__main__':
    unittest.main()
