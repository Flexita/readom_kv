#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""What a pull request may change, read from its diff alone.

Two rules of CONTRIBUTING.md, checked where a person can miss them in a long
file list:

  binary   No file the pull request adds or changes holds a NUL byte, except
           an image (.png, .jpg, .jpeg, .webp, .pgm) that starts the way its
           format does -- a name alone does not make a file an image. A kernel module, a
           firmware blob, a panel waveform, an update package or a jailbreak
           is binary; the images of the documents and the screens are the
           only binary files a contributor has reason to send. The fonts and
           the dictionary the tree also holds come from the maintainer.
  scope    A pull request that touches a model's own files -- device/amazon/<model>/,
           config/models/<model>.config, boot/profiles/<model>-<firmware>.json,
           for any model but pw3 -- is about that one model and touches
           nothing else, apart from that model's line in the case statement of
           tools/build-kernel.sh, in the shape the existing entries have
           ("Porting to another model", rule 1). device/amazon/pw3/ is the
           code every model shares today, so it is not a model's own; nor is
           device/amazon/common/, where porting-to-other-models.md section 4
           moves the shared part once there is a second model.

Bytes are read from the objects, not judged by git's diff: a .gitattributes
in the same pull request decides what `git diff` calls text, and so cannot
decide what this calls binary.

What it does not do: tell an Amazon text file from ours, or hold against a
pull request that edits this file or the workflow that runs it -- for a pull
request GitHub runs the pull request's own copy of both. It catches mistakes;
the review reads the rest (CONTRIBUTING.md, "Before a model is merged").

Usage: check-pr-scope.py BASE HEAD     (in the repository; exit 1 on a finding)
In CI, HEAD is the merge GitHub made and HEAD^1 the branch it merges into, so
the diff is exactly what merging would change.
"""
import re
import subprocess
import sys

IMAGES = ('.png', '.jpg', '.jpeg', '.webp', '.pgm')
# How each of those formats begins. WebP is a RIFF container with WEBP at byte 8.
IMAGE_START = (re.compile(rb'\x89PNG\r\n\x1a\n'), re.compile(rb'\xff\xd8\xff'),
               re.compile(rb'RIFF.{4}WEBP', re.S), re.compile(rb'P5\s'))
SHARED = {'pw3', 'common'}
REGISTRY = 'tools/build-kernel.sh'
DEVICE = re.compile(r'device/amazon/([^/]+)/')
CONFIG = re.compile(r'config/models/([^/]+)\.config$')
PROFILE = re.compile(r'boot/profiles/([^/-]+)-[^/]+\.json$')


def git(*args, check=True):
    return subprocess.run(['git', *args], capture_output=True, check=check).stdout


def changes(base, head):
    """(status, new mode, new object, path) for every path the diff touches.

    --no-renames: a rename is a deletion and an addition, and both paths have
    to be allowed."""
    raw = git('diff', '--raw', '-z', '--no-renames', '--no-abbrev', base, head).split(b'\0')
    out = []
    for meta, path in zip(raw[0::2], raw[1::2]):
        if not meta:
            break
        _, new_mode, _, new_obj, status = meta.decode().lstrip(':').split(' ')
        out.append((status[0], new_mode, new_obj, path.decode('utf-8', 'surrogateescape')))
    return out


def models(paths, head):
    """The models other than pw3 whose own files the pull request touches."""
    named = {m.group(1) for p in paths for m in (DEVICE.match(p), CONFIG.match(p)) if m}
    for p in paths:
        m = PROFILE.match(p)
        # A profile names a model only if the model exists: qemu-vexpress.json
        # is the emulator's profile, not a model called qemu.
        if m and (m.group(1) in named or exists(head, 'config/models/%s.config' % m.group(1))):
            named.add(m.group(1))
    return named - SHARED


def exists(commit, path):
    return subprocess.run(['git', 'cat-file', '-e', '%s:%s' % (commit, path)],
                          capture_output=True).returncode == 0


def owned(path, model):
    for pattern in (DEVICE, CONFIG, PROFILE):
        m = pattern.match(path)
        if m and m.group(1) == model:
            return True
    return False


def registry_lines(base, head, named):
    """The changed lines of the build script that are not this model's entry in
    its case statement. The whole line is held to the shape the other models'
    entries have, not only its start: what follows `;;` on the same line would
    otherwise be a change to every model."""
    entry = re.compile(r'^\s*(%s)\)\s*DEFCONFIG=[A-Za-z0-9_]+;\s*suffix="-\$MODEL"\s*;;\s*$'
                       % '|'.join(map(re.escape, sorted(named))))
    diff = git('diff', '-U0', '--no-renames', base, head, '--', REGISTRY).decode('utf-8', 'replace')
    return [line for line in diff.splitlines()
            if line[:1] in '+-' and not line.startswith(('+++', '---')) and not entry.match(line[1:])]


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    base, head = sys.argv[1:]
    touched = changes(base, head)
    binary, outside, registry = [], [], []

    for status, mode, obj, path in touched:
        if status == 'D':
            continue
        if mode == '160000':
            binary.append(path)
        elif mode in ('100644', '100755'):
            data = git('cat-file', 'blob', obj)
            if b'\0' in data and not (path.lower().endswith(IMAGES) and any(r.match(data) for r in IMAGE_START)):
                binary.append(path)

    paths = [p for _, _, _, p in touched]
    named = models(paths, head)
    if len(named) == 1:
        for path in paths:
            if any(owned(path, m) for m in named):
                continue
            if path == REGISTRY:
                registry = registry_lines(base, head, named)
                if not registry:
                    continue
            outside.append(path)

    who = ', '.join(sorted(named))
    several = len(named) > 1
    print('%d path(s) changed; %s' % (len(paths), 'a pull request for ' + who if named
                                       else "not a model's pull request"))
    if several:
        print('\nThis touches the own files of %d models (%s). A pull request is about one model '
              '(CONTRIBUTING.md, "Porting to another model", rule 1).' % (len(named), who))
    if binary:
        print('\n%d binary file(s) or submodule(s). Only images (%s) may come in a pull request; device '
              "data and Amazon's files never (CONTRIBUTING.md, the second hard rule):"
              % (len(binary), ', '.join(IMAGES)))
        print(''.join('  %s\n' % p for p in binary), end='')
    if outside:
        print('\n%d file(s) that are not %s\'s own. A change to shared code goes in a pull request of '
              'its own (CONTRIBUTING.md, "Porting to another model", rule 1):' % (len(outside), who))
        print(''.join('  %s\n' % p for p in outside), end='')
        if registry:
            print('%s may change only the case entry of %s; it also changes:' % (REGISTRY, who))
            print(''.join('    %s\n' % line for line in registry[:5]), end='')
    return 1 if binary or outside or several else 0


if __name__ == '__main__':
    sys.exit(main())
