#!/bin/bash
# Install AOSP arm-linux-androideabi-4.9 at the revision pinned in source-lock.json.
# Use when the unpublished aosp-arm-gcc49-0390252.tar.gz bytes are unavailable.
# Does not flash a device. Writes .pw3-toolchain-revision for tools/ensure-toolchain.py.
set -euo pipefail
LOCK=/mnt/port/source-lock.json
TARGET=${1:-/home/builder/toolchains/aosp-arm-gcc49}
WORKDIR=${2:-/tmp/aosp-gcc/arm-linux-androideabi-4.9}
read -r REPO REV < <(python3 -c 'import json; c=json.load(open("'"$LOCK"'"))["cross_compiler"]; print(c["repository"], c["revision"])')
mkdir -p "$(dirname "$WORKDIR")"
if [[ ! -d "$WORKDIR/.git" ]]; then
  git clone --filter=blob:none --no-checkout "$REPO" "$WORKDIR"
fi
git -C "$WORKDIR" fetch --depth 1 origin "$REV"
git -C "$WORKDIR" checkout --force "$REV"
mkdir -p "$(dirname "$TARGET")"
rm -rf "$TARGET"
mkdir -p "$TARGET"
# Copy the checked-out tree without .git (cp -a keeps androidkernel symlinks).
cp -a "$WORKDIR"/. "$TARGET"/
rm -rf "$TARGET/.git"
printf '%s\n' "$REV" > "$TARGET/.pw3-toolchain-revision"
"$TARGET/bin/arm-linux-androidkernel-gcc" --version | head -1
echo "materialized revision $REV at $TARGET"
