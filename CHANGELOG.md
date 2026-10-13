# 变更记录

## 1.3.0rc2 — 2026-10-13

- English and Simplified Chinese dashboard, extension prompts, block pages, validation messages and Windows native prompts; language preferences do not change quota state.
- Unified source installer (`install.py`) and installed-package setup (`focuser setup`), with preserved data paths and opt-in first-install semantics.
- English README with a matching Chinese translation, synthetic screenshots and clear asset/platform installation guides.
- Public prerelease assets: source ZIP, wheel, Chromium/Firefox extensions and SHA256SUMS. Native Linux/macOS app limits and signed Firefox distribution remain pending.
- 新增中英文界面与 Windows 原生提示；语言切换不修改规则、用量、额外分钟及绑定。
- 统一源码安装器及 `focuser setup`，明确区分首次使用与迁移，保留原数据与门槛。
- 英文首页、对应中文翻译、模拟数据截图，以及按资产和平台划分的安装指南。

## 未发布 — 2026-10-13

- 面向公开仓库重写用途、功能、隐私边界与人/Agent 开发入口；明确桌面浏览器跨平台支持与 Windows 原生 App 支持的区别。
- Fedora 安装器生成私有 systemd 用户服务；迁移检查既有数据，不编辑状态，不自动覆盖服务或启动。
- Linux/macOS 遇到启用的原生 App 规则拒绝启动，避免迁移静默放宽限制。
- systemd 启动参数转义美元符号，增加私有文件掩码；增加 Fedora 容器 CI 与迁移回归。

## 未发布 — 2026-10-09

- 网页控制台改为仿 iOS“屏幕使用时间”：时间额度页（−/+ 步进器）、管理类别、类别详情、按字母分组的 App 选择器、跨类别移动确认、暗色模式与窄屏布局。
- 拦截页改为“时间额度已用完”样式，保留“好”、每日一次额外分钟与打开控制台。
- 不新增“忽略限额”“稍后提醒”：任何放宽（增加额度、移除网站/App、关闭类别）仍在保存时走定积分验证。
- 分类图标改为墨水屏风格：纸面底色 + 单色线条图标（视频、社交、聊天、游戏、阅读、音乐、购物、工作、网站、禁用、通用），按名称/域名/程序自动匹配，可在类别详情手动指定（`icon` 字段）。不下载或内置第三方品牌图标，也不联网取站点图标。状态胶囊与汇总卡改为中性色。
- 按星期额度（`weekly_minutes`）：周一到周日可分别设置额度，0 表示当天禁用；旧的周末额度自动展开，原状态备份为 `state.pre-weekly.json`。
- 停用时间支持多个时段（最多 6 个，如 8–12 点、14–18 点），字段 `curfews`；旧的单时段自动转换。
- 网页“停用时间”入口（仿 iPadOS）；桌面 App 确认窗口与网页拦截页统一样式并跟随系统深浅色；额外分钟已领取时给出提示。
- 禁用时段（`curfew`，HH:MM，可跨午夜）：时段内即使有剩余额度也封印，且不可领取额外分钟。
- 放宽判定（需定积分验证）新增：增加周末额度、关闭/缩短/移除禁用时段；新增周末额度或禁用时段属于收紧。
- 扩展在额度剩余约 5 分钟、不足 1 分钟及禁用时段前 5 分钟，于网页角落提示一次；拦截页区分“禁用时段”。
- 近两周按类别堆叠着色，点击某天展开各类别用时。
- 新增 tests/test_screen_time_web_assets.py 检查页面元素与禁止绕过入口。

## 1.3.0rc1 — 2026-10-07

- 服务、平台能力、资源、数据目录与启动入口解耦；基础Python服务无第三方依赖。
- Windows原生拦截延迟加载；macOS/Linux浏览器服务与登录启动模板。
- Chromium与Firefox独立安装包、网页下载/指引、扩展端口配置和数据目录绑定。
- 同目录进程锁、服务身份握手、持久化fsync、异常数据拒绝及保存失败回滚。
- 公共API版本/健康检查、适配层状态、Python包与白名单发布构建、跨平台CI配置。
- 原格式用量/bonus与数学门槛保留；无自动升级或真实数据重置。

发布候选版仍有跨平台/跨浏览器实机验收与Firefox签名工作；macOS/Linux桌面App拦截未实现。
