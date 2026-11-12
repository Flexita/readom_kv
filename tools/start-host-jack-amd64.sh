#!/bin/bash
# Invoked as the build user inside the amd64 chroot on an x86_64 host.
set -euo pipefail
cd /src
jdk=/usr/lib/jvm/java-8-openjdk-amd64
test -x "$jdk/bin/java"
export PATH="$jdk/bin:$PATH"
export JACK_SERVER_VM_ARGUMENTS="-Dfile.encoding=UTF-8 -XX:+TieredCompilation -Xmx3g"
if [[ ! -d /home/builder/.jack-server ]]; then
  prebuilts/sdk/tools/jack-admin install-server \
    prebuilts/sdk/tools/jack-launcher.jar prebuilts/sdk/tools/jack-server-4.11.ALPHA.jar
fi
test -s /home/builder/.jack-server/server.jks
test -s /home/builder/.jack-server/client.jks
python3 /port/tools/patch-jack-tls.py \
  prebuilts/sdk/tools/jack-server-4.11.ALPHA.jar \
  /home/builder/.jack-server/server-1.jar /build-share/logs/jack-tls-patch.json
prebuilts/sdk/tools/jack-admin start-server 9>&-
prebuilts/sdk/tools/jack-admin server-stat > /build-share/logs/jack-server-stat.txt
grep -Eq 'os.arch: (amd64|x86_64)' /build-share/logs/jack-server-stat.txt || {
  echo 'Jack server is not running as amd64 on this x86_64 host.' >&2
  exit 1
}
