# Focuser · 把注意力留给真正想做的事

**免费开源、本地运行的屏幕使用时间工具。** 为网站与桌面 App 设置共享的每日额度，在打开前确认用途，在额度耗尽后拦截访问。无需账号、订阅或试用；填写的用途不保存、不上传。MIT License。

Focuser is a free, local-first screen-time budget tool. A Python loopback service and browser extensions share category budgets across browsers; Windows also supports native apps. No account, cloud backend, telemetry, or saved intention text. Linux/Fedora and macOS support browser budgets; native app enforcement is Windows-only.

## 为什么使用 Focuser

- **帮助自律**：每日额度、按星期额度、多个停用时段；打开受限网站或 App 前先确认用途。
- **共享额度**：同一分类中的网站与绑定 Windows App 共用额度；换浏览器也不会刷新余额。
- **数据留在本机**：只监听 `127.0.0.1`，不保存用途、页面标题或实际访问 URL；仅保留规则与近两周分类总时长等必要状态。
- **给冲动增加一点阻力**：放宽规则、暂停或退出恢复访问需要完成操作绑定的随机定积分验证；每天仍有既定的一次额外一分钟。
- **跨平台浏览器支持**：Windows、macOS、Linux/Fedora 的 Python 后端；浏览器扩展负责网站计时与拦截，主要操作都在网页完成。
- **轻量可维护**：基础服务没有第三方运行依赖；支持登录后静默启动，代码、协议与测试可检查。

这是可由本机用户管理的自我约束工具。它不能阻止管理员卸载扩展、结束进程或更改系统时间，不是企业级防绕过系统。详见 [安全与隐私](SECURITY.md)。

## 平台与状态

当前版本 **1.3.0rc1**，仍是发布候选版。

| 平台 / 浏览器 | 网站额度 | 原生桌面 App | 说明 |
| --- | --- | --- | --- |
| Windows 10/11 | 支持 | 支持，可选依赖 | 提供一键配置 |
| Fedora / 其他 Linux | 支持 | 尚未实现 | 提供 Fedora 安装与 systemd 用户服务；Wayland 不需要全局窗口权限 |
| macOS | 支持 | 尚未实现 | 提供 launchd 模板 |
| Chrome / Edge / Brave / Opera / Vivaldi | Chromium 扩展 | 由系统适配器决定 | 各浏览器连接同一后端与数据目录 |
| Firefox 128+ | 测试扩展 | 由系统适配器决定 | 未签名，临时加载在重启后失效 |
| Safari / Android / iOS | 未支持 | 未支持 | 不承诺移动端支持 |

“跨平台”指桌面浏览器后端，不代表所有系统均可拦截原生 App，也不包含自动跨设备同步。具体证据与待验收项目见 [兼容性说明](docs/release/compatibility.md)。

## 快速开始

需要 Python 3.10+。Windows 可双击 [一键配置.cmd](一键配置.cmd)，安装环境、保留已有数据并配置静默启动。源码手动安装：

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install ".[desktop]"
.venv\Scripts\focuser.exe
```

macOS / Linux 新用户：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/focuser
```

**已有用户必须继续使用原数据，或完整私下迁移数据后显式指定 `--data-dir`，不能用新目录重置用量。** Fedora 用户请先阅读 [Fedora 安装与迁移](docs/release/fedora.md)，其中提供安装脚本、开机服务和验收步骤。

打开 [本机控制页](http://127.0.0.1:18765/)，进入“连接与设置”，下载并解压对应扩展。Chromium 系列在扩展管理页启用开发者模式，加载解压目录；Firefox 在 `about:debugging` 临时加载测试包的 `manifest.json`。每个浏览器都要安装扩展，并连接同一端口。安装和更新依赖可能联网，日常运行不需要云服务。

默认规则封印抖音；社区与视频分类共用每日 30 分钟。可在网页自定义分类、域名、星期额度和停用时段。浏览器扩展仅计活动前台网页；午夜按本机日期结算。

## 静默启动与升级

```sh
focuser --data-dir /absolute/path/to/existing-data --background
focuser --dry-run
focuser-startup --data-dir /absolute/path/to/existing-data --output /path/to/new-templates
```

启动模板不会自动启用或覆盖已有服务。升级保留数据、端口、规则、历史及额外分钟记录。跨系统路径变化会改变扩展绑定标识，应在目标系统使用新扩展安装连接已迁移的数据；不要为解决绑定问题新建空数据。见 [安装指南](docs/release/install.md)。

## 给开发者与 Agent

目标：用本地分类预算帮助用户减少无意识的网站和 App 使用，不采集用途内容，不引入账号或云依赖。

| 路径 | 职责 |
| --- | --- |
| `scripts/screen_time_core.py` | 分类预算、计时、时段、持久化状态 |
| `scripts/screen_time_server.py` | 本机 HTTP API 与静态资源 |
| `scripts/screen_time_platform.py` / `screen_time_windows.py` | 平台能力与 Windows App 适配 |
| `resources/screen_time/web/` | 网页控制台 |
| `resources/screen_time/extension/` | 浏览器计时、用途确认、拦截与本机连接 |
| `tests/` | 核心、接口、额度保留、扩展回归 |
| `outputs/` | 本地运行数据与产物，禁止公开提交 |

维护原则：放宽限制必须保留验证门槛；重启、迁移、安装或缺少平台依赖不能静默放宽额度。测试使用独立数据目录与端口，不消耗真实额外分钟。只发布白名单源码与通用文档，禁止提交用户状态、备份、凭据、浏览器配置和私人协作记录。

```sh
python -m unittest discover -s tests -p "test_*.py"
node tests/test_screen_time_extension.cjs
python -m pip install build
python -m build --outdir outputs/packages
python scripts/screen_time_release.py --output outputs/distribution
```

[架构与扩展协议](docs/release/architecture.md) · [贡献指南](CONTRIBUTING.md) · [变更记录](CHANGELOG.md) · [发布检查](docs/release/checklist.md)
