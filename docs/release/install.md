# 安装、浏览器与升级

## 第一次安装

1. 使用 Python 3.10+，在固定目录创建虚拟环境。Windows 推荐安装 `.[desktop]`；macOS/Linux 安装 `.`。
2. 启动 `focuser`，打开输出端口的本机网页，进入“连接与设置”。
3. 下载并解压对应扩展到固定目录。浏览器不会允许普通网页直接安装扩展，最后一步必须在浏览器扩展管理页完成。
4. Chromium 系列开启开发者模式，加载解压目录；Firefox 在 about:debugging 临时加载 manifest.json。Firefox 测试包不是签名 XPI，浏览器重启后需重新加载。
5. 打开扩展选项，检查端口，打开控制页、刷新目标网页。每个浏览器配置与隐私窗口都需要安装/授权。

基础服务无外部运行依赖，不要求桌面 App 或固定机器的 Python 路径。安装 Python 包及桌面依赖时，pip 可能联网下载依赖；安装完成后的运行与扩展下载完全本地。

## 数据目录

| 系统 | 新安装默认目录 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Focuser` |
| macOS | `~/Library/Application Support/Focuser` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/focuser` |

源码运行若检测到已有项目交付数据，会优先使用该旧目录。现有 `screen_time_start.py` 仍使用项目交付目录。wheel 安装与程序目录分离；升级时必须传入原 `--data-dir`。不要把 `--data-dir` 指向空目录来绕过限制。

同一数据目录只允许一个写入进程，即使使用不同端口也会拒绝第二个写入者。端口被其他服务占用时失败退出，不打开陌生服务或覆盖 state.json。损坏数据保留原文件并拒绝启动，不自动归零。维护退出不设置 paused。

## 升级与迁移

1. 先备份原数据目录，保留 state.json、用量与 bonus 记录。不要提交备份。
2. 在另一个目录/虚拟环境安装候选版本，使用独立端口和隔离测试数据完成验收。
3. 正式切换时停止旧后台，立即使用**原端口和原数据目录**启动新服务。不要同时运行两个写入者。
4. 从新服务控制页下载扩展；在原扩展目录覆盖更新资源后重新加载，保留扩展 storage 与绑定信息。改变浏览器配置会产生新的扩展实例，需要重新安装。
5. 确认当日剩余、history、bonus、paused 与切换前相同。失败时恢复原程序继续使用同一数据，不重置记录。

数据格式仍为 version=1，1.3不执行配额迁移。扩展1.3要求 API v1 与 /api/health，旧1.2服务不符合该握手；因此先更新服务再更新扩展。旧1.2扩展仍能与新服务通信。绑定 ID 基于规范化数据目录；迁移路径时不要直接清理扩展绑定，先制定保留记录的迁移流程。

## 开机静默运行

使用虚拟环境内的 `focuser-startup --output <一个新的输出目录>`。只生成模板，不自动启用或停止现有服务，不会覆盖现有模板。已有用户增加 `--data-dir <原目录>`；自定义端口增加 `--port`。

Windows：生成 `Focuser.vbs`，将其复制到当前用户的 `shell:startup` 目录。模板调用指定虚拟环境的 Python 并隐藏窗口，无需管理员。已有自启动入口不要重复安装。

macOS：生成 `org.focuser.local.plist`，复制到 `~/Library/LaunchAgents/`，然后运行：

```sh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/org.focuser.local.plist
```

Linux（systemd 用户会话）：复制生成的 `focuser.service` 到 `~/.config/systemd/user/`，然后运行：

```sh
systemctl --user daemon-reload
systemctl --user enable --now focuser.service
```

不需要 linger 或系统级服务。模板在异常退出时重试；正常退出后不会自动重新启用限制。虚拟环境与数据目录需要长期保留。非 systemd 系统可用桌面环境的用户登录启动设置执行相同命令。

## 排障

- 无连接：确认服务启动，端口一致，扩展拥有网站权限；查看 `/api/health`。
- 本地数据绑定不同：使用原数据目录启动服务，不能用新目录替代已消耗的用量。
- App 不拦截：查看网页的平台能力与错误状态。缺少桌面能力且已有启用 App 规则时拒绝启动；macOS/Linux 暂无桌面拦截。Fedora 迁移见 [专用指南](fedora.md)。
- 扩展离线：有缓存时保留规则，启用分类按离线限制处理；重新连接后继续原额度。
- 磁盘只读/满：操作返回503且规则、暂停、bonus回滚；修复保存权限后重试。未确认保存前不要认为操作成功。
- 自定义 Chromium 浏览器：底层需支持 Manifest V3、DNR 与相关扩展 API，未逐一实机认证。

浏览器分发说明：[Chrome 官方分发限制](https://developer.chrome.com/docs/extensions/how-to/distribute)、[Firefox background 差异](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/manifest.json/background)。正式商店上架仍需各商店审核与签名，此项目不会自动提交。
