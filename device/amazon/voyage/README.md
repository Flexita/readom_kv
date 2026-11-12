# Voyage 设备目录

实验性产品名。继承 `device/amazon/pw3` 里的 i.MX6SL 板级代码，因为 GPL 源码里的 Voyage defconfig 也是 `imx60_wario_defconfig`。这不是已经启动过的证明。

交接参数不在这里。`boot/profiles/voyage-5.13.6.json` 的 `installable` 为 false 时，入口、安装器和交接模块都不会被打成可安装包。缺的真机只读采集项写在 `docs/design/voyage-port.md`。

English: this directory names the product. It does not contain a handoff plan, and it has not been booted on hardware.
