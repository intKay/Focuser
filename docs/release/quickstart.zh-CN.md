# 安装 Focuser

## 推荐：源码包与统一安装器

1. 安装 Python 3.10+。Fedora：`sudo dnf install python3 python3-pip`。Windows 的 Python 应包含 Tcl/Tk，并能在终端用 `python` 启动。
2. 从 [v1.3.0-rc.2](https://github.com/intKay/Focuser/releases/tag/v1.3.0-rc.2) 下载 `focuser-local-1.3.0rc2-source.zip`，解压到长期保留、可写的目录，在该目录打开终端。
3. 首次使用：Windows 运行 `python install.py --new-install`；Linux/macOS 运行 `python3 install.py --new-install`。使用普通用户，不要用 root。

安装器创建 `.venv`、安装依赖、准备 Chromium 扩展目录并配置用户登录启动，最后打开 `http://127.0.0.1:18765/`。安装依赖需要网络，日常运行不需要。

加 `--plan` 只查看计划，不写文件；`--no-open` 不打开浏览器；`--no-startup` 只生成模板而不启用。Linux 登录启动需要 systemd 用户会话。安装器不会代装 Python，也不能自动完成浏览器扩展安装或签名。

## 连接浏览器扩展

控制页打开“连接与设置”，下载 `chromium.zip`，解压到固定目录。进入扩展管理页：

| 浏览器 | 地址 |
| --- | --- |
| Chrome / Brave / Chromium | `chrome://extensions` |
| Edge | `edge://extensions` |
| Vivaldi | `vivaldi://extensions` |
| Opera | `opera://extensions` |

开启“开发者模式”，选择“加载已解压的扩展程序”，选中包含 `manifest.json` 的文件夹。每个浏览器都要安装并连接相同端口。安装或更新后刷新目标网页；隐私窗口需要单独授予扩展权限。

Firefox：解压独立 Firefox 包，在 `about:debugging#/runtime/this-firefox` 点击“临时载入附加组件”，选择 `manifest.json`。该测试包未签名，重启浏览器后会移除。

## 已有用户：保留额度

先备份完整实际数据目录，使用 `--data-dir /原数据目录`，不要加 `--new-install`。Windows 用 `python`，Linux/macOS 用 `python3`。自定义端口使用 `--port`；升级保留解释器、启动设置和数据路径，冲突的启动入口不会被覆盖。

安装器不结束已有后端，也不编辑状态。正在运行的后端可能继续使用旧代码，直到维护重启。先用独立数据和端口测试升级，再维护结束原进程，并立即用原数据和端口恢复。不要借维护停服恢复访问。

跨系统迁移：维护结束旧服务后，私下复制最终完整数据，不上传 GitHub。若有启用的 Windows App 规则，先在原网页完成验证并调整不兼容规则，再迁移 Linux/macOS。见 [Fedora 迁移指南](fedora.md)。目标系统的新扩展连接已迁移的数据，不新建空数据替代。

新用户默认目录：Windows `%LOCALAPPDATA%\Focuser`；macOS `~/Library/Application Support/Focuser`；Linux `${XDG_DATA_HOME:-~/.local/share}/focuser`。旧源码安装可能使用 `outputs/screen_time/release/ScreenTime/data`，以实际既有目录为准。

## wheel 与高级安装

wheel 是 Python 包，不是独立可执行程序。在虚拟环境安装 `focuser_local-1.3.0rc2-py3-none-any.whl`。Windows 原生 App 需要额外的 `psutil`、`pystray`、`Pillow` 和 Python 自带 Tk；希望自动配置依赖时使用源码安装器。

```sh
focuser setup --new-install --enable-startup
# 已有用户：
focuser setup --data-dir /原数据目录 --enable-startup
focuser --data-dir /原数据目录 --background
```

网页与扩展语言选项只保存界面偏好。Windows 原生提示跟随系统语言，`focuser --lang en` 或 `FOCUSER_LANG=en` 可指定英文。自定义分类名属于用户内容，翻译不会改写它们。

## 排障

- 控制页打不开：检查 `http://127.0.0.1:18765/api/health`。Linux 可用 `systemctl --user status focuser.service` 和 `journalctl --user -u focuser.service`。
- 绑定的数据不同：恢复原服务目录，或在目标系统用新扩展连接私下迁移的数据；不能新建空用量修复连接。
- 原生规则不支持：Windows 检查桌面依赖；Linux/macOS 目前仅限制网站。
- 启动入口冲突：保留其原解释器、数据和端口。安装器不会覆盖冲突入口。
- 反馈只提供去敏错误、版本与复现步骤，不上传状态、私人路径日志或浏览器配置。
