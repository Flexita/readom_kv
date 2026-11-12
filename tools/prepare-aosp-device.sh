#!/bin/bash
# Copy only this project's owned product, then apply its pinned AOSP changes.
set -euo pipefail
[[ "$(uname -s)" == Linux && "$(hostname)" == lima-pw3 ]] || exit 1
SRC=/home/builder/android-src
bash /mnt/port/tools/prepare-kernel-hardware.sh
# pw3 remains the shared platform tree (HAL/init). Voyage lunch inherits it and
# adds only device/amazon/voyage; both copies are marked .pw3-owned-copy.
for model_dir in pw3 voyage; do
  src_tree=/mnt/port/device/amazon/$model_dir
  [[ -d "$src_tree" ]] || continue
  DEST="$SRC/device/amazon/$model_dir"
  if [[ -e "$DEST" && ! -f "$DEST/.pw3-owned-copy" ]]; then
    echo "Refusing to overwrite a device tree not owned by this port: $DEST" >&2
    exit 1
  fi
done
python3 /mnt/port/tools/fetch-prebuilts.py --check   # the fetched APKs, before anything is copied
for model_dir in pw3 voyage; do
  src_tree=/mnt/port/device/amazon/$model_dir
  [[ -d "$src_tree" ]] || continue
  DEST="$SRC/device/amazon/$model_dir"
  mkdir -p "$DEST"
  # Keep unchanged inputs stable; timestamp changed copies at synchronization so
  # make never mistakes an older host mtime for source already compiled in VM.
  rsync -ac --no-times --delete "$src_tree/" "$DEST/"
  touch "$DEST/.pw3-owned-copy"
done
grep -v '^#' /mnt/port/patches/projects.txt | while read -r project series; do
  [[ -n "$project" ]] || continue
  python3 /mnt/port/tools/apply-patch-series.py "$SRC/$project" /mnt/port/patches/"$series"/*.patch
done
