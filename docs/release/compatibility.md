# 兼容性与发布状态

本轮交付为 **1.3.0rc1 发布候选版**。核心与网页已去除 Windows 依赖，不等于所有平台的桌面拦截已经完成。

| 环境 | 浏览器服务 | 桌面 App 拦截 | 当前证据 |
| --- | --- | --- | --- |
| Windows 当前本机 | 支持 | 可选 Windows 适配器 | Python回归、隔离浏览器验收；原版App实机验收见本地历史 |
| Windows 10/11 其他设备 | 目标支持 | 目标支持 | 待干净机器验收；未提供签名安装程序 |
| macOS + Python 3.10+ | 可移植实现 | 未实现 | 路径/能力选择/launchd模板单测；待实机验收 |
| Linux + Python 3.10+ | 可移植实现 | 未实现，包括 Wayland | 路径/能力选择/systemd模板单测；待实机验收 |
| Fedora GNOME/KDE | 浏览器实现与安装器 | 未实现 | systemd 用户服务、迁移拒绝不兼容规则、Fedora 容器 CI；仍需 Fedora 实机验收 |
| Chrome / Edge 120+ | Chromium包 | 使用平台服务 | Chrome隔离测试；Edge未在本轮操作 |
| Brave / Opera / Chromium | 同一Chromium包 | 使用平台服务 | API兼容目标，待各浏览器实测；部分UA显示Chrome |
| Vivaldi（Chromium 120+） | 同一Chromium包 | 使用平台服务 | 浏览器识别、共享额度与重启保留回归；真实用户配置待安装验收 |
| Firefox 128+ | 独立测试包 | 使用平台服务 | manifest、命名空间、Origin单测；待实机及签名 |
| Safari / 内嵌浏览器 | 未支持 | 未支持 | 不作支持承诺 |
| Windows 7/8及旧浏览器 | 不作支持承诺 | 不作支持承诺 | 不降低现代依赖要求来支持过时环境 |

网页可在桌面与窄屏使用；离线模式的DNR和内容遮罩仅在扩展仍安装/启用并拥有对应权限时有效。跨浏览器同步范围为同一用户、同一服务、同一数据目录，不包含另一套操作系统或另一台电脑。

CI配置覆盖Windows/macOS/Linux与Python3.10/3.13，并增加Fedora容器。当前结果请检查GitHub Actions，配置文件本身不代表CI通过。正式1.3.0需完成清单中的真实平台和浏览器验收后发布。
