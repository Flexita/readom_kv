#!/bin/bash
# x86_64 host path: run Jack with the VM's amd64 OpenJDK 8 inside the Jammy
# chroot. The lima-pw3 ARM64 scripts (provision-native-jack.sh) bind an aarch64
# JRE for QEMU-user AOSP hosts; they do not apply on a native amd64 builder.
set -euo pipefail
[[ "$(uname -s)" == Linux && "$(hostname)" == lima-pw3 ]] || exit 1
[[ "$(uname -m)" == x86_64 ]] || {
  echo 'provision-host-jack-amd64.sh is only for x86_64 hosts' >&2
  exit 2
}
root=/srv/aosp-x86
jdk=/usr/lib/jvm/java-8-openjdk-amd64
test -x "$jdk/bin/java" || {
  echo 'Install openjdk-8-jdk-headless (amd64) on the host first.' >&2
  exit 1
}
test -x "$root/usr/sbin/runuser"
# OpenJDK lives on the host; bind it read-only into the chroot when absent there.
if [[ ! -x "$root$jdk/bin/java" ]]; then
  sudo mkdir -p "$root$jdk"
  if ! mountpoint -q "$root$jdk"; then
    sudo mount --bind "$jdk" "$root$jdk"
    sudo mount -o remount,bind,ro "$root$jdk"
  fi
fi
if [[ -d /etc/java-8-openjdk ]]; then
  sudo mkdir -p "$root/etc/java-8-openjdk"
  if ! mountpoint -q "$root/etc/java-8-openjdk"; then
    sudo mount --bind /etc/java-8-openjdk "$root/etc/java-8-openjdk"
    sudo mount -o remount,bind,ro "$root/etc/java-8-openjdk"
  fi
fi
mkdir -p /mnt/build-share/logs
sudo chroot "$root" /usr/sbin/runuser -u builder -- \
  "$jdk/bin/java" -XshowSettings:properties -version \
  > /mnt/build-share/logs/host-jack-jvm-amd64.txt 2>&1
grep -Eq 'os.arch = (amd64|x86_64)' /mnt/build-share/logs/host-jack-jvm-amd64.txt
dpkg-query -W -f='${Package} ${Version} ${Architecture}\n' \
  openjdk-8-jdk-headless openjdk-8-jre-headless \
  > /mnt/build-share/logs/host-jack-packages-amd64.txt
sudo mkdir -p "$root/opt/pw3-java-tools"
# Native amd64: real javac/java, not the QEMU -Xint wrappers.
sudo ln -sfn "$jdk/bin/javac" "$root/opt/pw3-java-tools/javac"
sudo ln -sfn "$jdk/bin/java" "$root/opt/pw3-java-tools/java"
sudo ln -sfn "$jdk/bin/jar" "$root/opt/pw3-java-tools/jar"
sudo ln -sfn "$jdk/bin/javadoc" "$root/opt/pw3-java-tools/javadoc"
echo 'amd64 OpenJDK 8 is available inside the build chroot for Jack.'
