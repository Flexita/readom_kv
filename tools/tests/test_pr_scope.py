#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""tools/check-pr-scope.py, on pull requests made for it in a repository of its own.

Each case is a base commit shaped like this tree where it matters (a shared
device directory, the case statement of the kernel build, the emulator's
profile) and one commit on top. The cases that must be refused are as many
as the ones that must pass: a check that only ever said yes would pass the
second half by itself.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / 'tools/check-pr-scope.py'

BUILD_KERNEL = '''MODEL="${PW3_KERNEL_MODEL:-pw3}"
case "$MODEL" in
  pw3)  DEFCONFIG=imx60_wario_defconfig; suffix='' ;;
  duet) DEFCONFIG=imx60_duet_defconfig; suffix="-$MODEL" ;;
  *) echo 'Unknown kernel model' >&2; exit 2 ;;
esac
TOOLCHAIN=/home/builder/toolchains/aosp-arm-gcc49
'''
VOYAGE_ENTRY = '  voyage) DEFCONFIG=imx60_wario_defconfig; suffix="-$MODEL" ;;\n'
BASE = {
    'tools/build-kernel.sh': BUILD_KERNEL,
    'config/models/pw3.config': 'CONFIG_A=y\n',
    'config/models/duet.config': 'CONFIG_B=y\n',
    'device/amazon/pw3/BoardConfig.mk': 'TARGET_ARCH := arm\n',
    'boot/profiles/pw3-5.16.2.1.1.json': '{}\n',
    'boot/profiles/qemu-vexpress.json': '{}\n',
    'docs/img/a.png': b'\x89PNG\r\n\x1a\n\0\0',
    'device/amazon/pw3/apps/dict.dat': b'\0\1\2',
    'README.md': 'readme\n',
}
VOYAGE = {
    'device/amazon/voyage/BoardConfig.mk': 'TARGET_ARCH := arm\n',
    'config/models/voyage.config': 'CONFIG_C=y\n',
    'boot/profiles/voyage-5.13.6.json': '{}\n',
    'tools/build-kernel.sh': BUILD_KERNEL.replace("  *) echo", VOYAGE_ENTRY + "  *) echo"),
}


# A repository of the test's own: no identity or setting of the machine's leaks in.
ENV = dict(os.environ, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t',
           GIT_COMMITTER_EMAIL='t@t', GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')


def git(repo, *args):
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, check=True, text=True,
                          env=ENV).stdout


class Symlink(str):
    """A symbolic link to this target."""


class Gitlink(str):
    """A submodule entry pointing at this commit."""


def write(repo, files):
    for name, content in files.items():
        path = repo / name
        if content is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or path.exists():
            path.unlink()
        if isinstance(content, Gitlink):
            continue
        if isinstance(content, Symlink):
            path.symlink_to(content)
        elif isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content)


class PullRequestScope(unittest.TestCase):
    def check(self, change, base_extra=None):
        """Exit status and output of the check for one commit on top of BASE."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, 'init', '-q')
            write(repo, dict(BASE, **(base_extra or {})))
            git(repo, 'add', '-A')
            git(repo, 'commit', '-qm', 'base')
            write(repo, change)
            git(repo, 'add', '-A')
            for name, content in change.items():
                if isinstance(content, Gitlink):
                    git(repo, 'update-index', '--add', '--cacheinfo', '160000,%s,%s' % (content, name))
            git(repo, 'commit', '-qm', 'pull request')
            run = subprocess.run([sys.executable, str(CHECK), 'HEAD^1', 'HEAD'], cwd=repo,
                                 capture_output=True, text=True, env=ENV)
            return run.returncode, run.stdout + run.stderr

    def passes(self, change, base_extra=None):
        code, out = self.check(change, base_extra)
        self.assertEqual(code, 0, out)
        return out

    def refused(self, change, *mentions, base_extra=None):
        code, out = self.check(change, base_extra)
        self.assertEqual(code, 1, out)
        for text in mentions:
            self.assertIn(text, out)
        return out

    # What has to pass.

    def test_shared_change_is_not_a_model_pull_request(self):
        out = self.passes({'device/amazon/pw3/BoardConfig.mk': 'TARGET_ARCH := arm64\n', 'README.md': 'x\n'})
        self.assertIn("not a model's pull request", out)

    def test_new_model_with_its_registration(self):
        self.assertIn('a pull request for voyage', self.passes(VOYAGE))

    def test_new_profile_of_a_model_that_exists(self):
        out = self.passes({'boot/profiles/voyage-5.13.7.json': '{}\n'},
                          base_extra={'config/models/voyage.config': 'CONFIG_C=y\n'})
        self.assertIn('a pull request for voyage', out)

    def test_emulator_profile_is_not_a_model(self):
        out = self.passes({'boot/profiles/qemu-vexpress.json': '{"a": 1}\n', 'README.md': 'x\n'})
        self.assertIn("not a model's pull request", out)

    def test_images_and_deleted_binaries(self):
        self.passes({'docs/img/b.webp': b'RIFF\0\0\0\0WEBP', 'device/amazon/pw3/apps/dict.dat': None})

    # What has to be refused.

    def test_model_with_a_shared_change(self):
        self.refused(dict(VOYAGE, **{'device/amazon/pw3/BoardConfig.mk': 'TARGET_ARCH := arm64\n'}),
                     "not voyage's own", '  device/amazon/pw3/BoardConfig.mk\n')

    def test_model_with_a_shared_common_directory(self):
        self.refused(dict(VOYAGE, **{'device/amazon/common/x.mk': 'x\n'}),
                     "not voyage's own", '  device/amazon/common/x.mk\n')

    def test_model_with_more_than_its_registration(self):
        changed = VOYAGE['tools/build-kernel.sh'].replace('aosp-arm-gcc49', 'aosp-arm-gcc10')
        self.refused(dict(VOYAGE, **{'tools/build-kernel.sh': changed}),
                     'may change only the case entry of voyage', 'aosp-arm-gcc10')

    def test_registration_of_another_model(self):
        changed = VOYAGE['tools/build-kernel.sh'].replace('duet) DEFCONFIG=imx60_duet', 'duet) DEFCONFIG=imx60_other')
        self.refused(dict(VOYAGE, **{'tools/build-kernel.sh': changed}),
                     'may change only the case entry of voyage', 'imx60_other')

    def test_profile_for_a_model_with_a_shared_change(self):
        self.refused({'boot/profiles/voyage-5.13.7.json': '{}\n', 'README.md': 'x\n'},
                     "not voyage's own", '  README.md\n',
                     base_extra={'config/models/voyage.config': 'CONFIG_C=y\n'})

    def test_binary_in_any_pull_request(self):
        self.refused({'device/amazon/pw3/modules/x.ko': b'\x7fELF\1\1\1\0'}, '1 binary file(s)', 'x.ko')

    def test_binary_inside_a_model_directory(self):
        self.refused(dict(VOYAGE, **{'device/amazon/voyage/waveform.wbf': b'\0\1\2\3'}),
                     '1 binary file(s)', 'waveform.wbf')

    def test_gitattributes_does_not_make_a_binary_text(self):
        self.refused({'.gitattributes': '*.bin diff\n', 'fw.bin': b'abc\0def'}, '1 binary file(s)', 'fw.bin')

    def test_model_deleting_a_shared_file(self):
        self.refused(dict(VOYAGE, **{'README.md': None}), "not voyage's own", '  README.md\n')

    def test_two_models_in_one_pull_request(self):
        self.refused(dict(VOYAGE, **{'config/models/duet.config': 'CONFIG_B=n\n'}),
                     'own files of 2 models (duet, voyage)')

    def test_moving_a_file_from_one_model_to_another(self):
        self.refused({'device/amazon/duet/x.mk': None, 'device/amazon/voyage/x.mk': 'x\n'},
                     'own files of 2 models (duet, voyage)',
                     base_extra={'device/amazon/duet/x.mk': 'x\n'})

    def test_registration_line_that_carries_more(self):
        sneaked = VOYAGE_ENTRY.replace(';;\n', ';; esac; TOOLCHAIN=elsewhere; case "$MODEL" in\n')
        changed = BUILD_KERNEL.replace("  *) echo", sneaked + "  *) echo")
        self.refused(dict(VOYAGE, **{'tools/build-kernel.sh': changed}),
                     'may change only the case entry of voyage', 'TOOLCHAIN=elsewhere')

    def test_link_turned_into_a_binary(self):
        self.refused({'device/amazon/pw3/firmware': b'\x7fELF\1\1\1\0'}, '1 binary file(s)', 'firmware',
                     base_extra={'device/amazon/pw3/firmware': Symlink('BoardConfig.mk')})

    def test_submodule(self):
        self.refused({'vendor/blobs': Gitlink('1' * 40)}, '1 binary file(s) or submodule(s)', 'vendor/blobs')

    def test_binary_named_as_an_image(self):
        self.refused({'docs/img/c.png': b'\x7fELF\1\1\1\0'}, '1 binary file(s)', 'c.png')

    def test_renamed_binary_is_still_binary(self):
        self.refused({'device/amazon/pw3/apps/dict.dat': None, 'dict.bin': b'\0\1\2'}, '1 binary file(s)', 'dict.bin')


if __name__ == '__main__':
    unittest.main()
