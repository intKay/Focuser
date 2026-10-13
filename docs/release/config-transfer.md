# 私人配置导入与导出 / Private configuration transfer

在“连接与设置 → 配置备份”中点击“加密导出配置”，输入并确认至少 12 个字符的密码。浏览器下载 `focuser-config.focuser`。文件使用 AES-256-GCM 加密，密码通过 PBKDF2-SHA256（600,000 次迭代、随机盐）派生密钥；每次导出使用新的随机盐和 IV。密码不保存、不发送后端，忘记密码无法解密该文件。

导出只包含已保存的分类规则：名称、域名、App、每日/星期额度、停用时段、颜色、图标与开关。它不含历史用量、额外分钟记录、暂停状态、本机路径、浏览器连接或用途。规则也可能透露个人习惯，因此只提供加密文件，不提供面向公开分享的个人配置。不要把密码与文件放在同一位置。

导入时选择 `.focuser` 文件并输入密码，查看分类预览后确认。规则会替换当前规则；本机历史、额外分钟与暂停状态保留。增加额度、删除限制、改分类 ID 等放宽操作仍需原来的单次定积分验证。取消、错误密码、损坏文件或保存失败不会应用配置。不兼容的启用 App 规则不会自动删除，须在原平台网页验证调整后再导出。

**该文件不是完整用量迁移备份。** 从 Windows 迁移 Fedora 时仍要私下保留最终完整数据目录，不能用配置文件和空数据重置当日用量。使用历史配置也不会回退目标系统已经消耗的时间。

In **Connect & settings → Configuration backup**, choose **Export encrypted configuration** and enter a matching password of at least 12 characters. Download `focuser-config.focuser`. AES-256-GCM encrypts the rules; PBKDF2-SHA256 derives the key with 600,000 iterations and a fresh random salt. Every export also uses a fresh IV. Passwords stay in browser memory and are never sent to the backend or stored. A forgotten password cannot decrypt that file.

The encrypted file contains saved category rules only. It excludes usage history, bonus claims, pause state, local paths, browser bindings and intention text. Rules can still reveal habits: keep the password separately and treat the file as private.

Import decrypts locally, previews categories, then applies them through the existing guarded configuration API. Local usage, bonus records and pause state stay intact. Relaxing limits requires the same single-action integral challenge. Unsupported active native app rules, runtime-state fields, wrong passwords and damaged files are rejected; cancellation and save failure do not apply rules.

**This is not a full usage migration backup.** Keep the complete private data directory when moving operating systems. Do not use a rules file plus an empty data directory to reset consumption.

Implementation: `scripts/screen_time_config.py`, `resources/screen_time/web/config-transfer.js`. Browser cryptography follows [Web Crypto encryption](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/encrypt) and [key derivation](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/deriveKey).
