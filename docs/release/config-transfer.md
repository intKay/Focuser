# 配置导入与导出 / Configuration transfer

在“连接与设置 → 配置备份”点击“导出配置”，直接下载 `focuser-config.json`，不需要密码。文件是普通 JSON，由用户自行保存；分类名称、网站与 App 列表可以直接查看，不要作为公开仓库或 Release 附件上传。

导出只包含已保存的分类规则：名称、域名、App、每日/星期额度、停用时段、颜色、图标与开关。不包含历史用量、额外分钟记录、暂停状态、本机路径、浏览器连接或用途。项目忽略默认导出文件名，源码发布也排除该文件。

导入时选择 JSON 文件，查看分类预览后确认。规则替换当前规则，本机历史、额外分钟与暂停状态保留。增加额度、删除限制、改分类 ID 等放宽操作仍需单次定积分验证。取消、无效文件或保存失败不会应用配置。当前平台不支持的启用 App 规则须在原平台通过验证调整后再导出，不会自动删除。

**配置文件不是完整用量迁移备份。** 从 Windows 迁移 Fedora 仍要私下保留最终完整数据目录，不能用配置文件和空数据重置用量。旧 `.focuser` 加密文件不支持直接导入，请从仍保存规则的原服务重新导出 JSON；修改扩展名不会解密文件。

In **Connect & settings → Configuration backup**, choose **Export configuration** to download `focuser-config.json` directly. No password is required. This is a plain JSON file that you keep yourself; category names, domains and app names are readable. Do not publish personal exports in a repository or release.

The file contains saved category rules only, excluding usage, bonus claims, pause state, local paths, browser bindings and intention text. The default export filename is ignored by Git and excluded from source distributions.

Import reads the JSON locally, previews categories and applies them through the existing guarded configuration API. Local usage, bonus records and pause state remain intact. Relaxing limits still requires the single-action integral challenge. Unsupported native app rules and runtime-state fields are rejected. Cancellation and save failure do not apply rules.

**This is not a full usage migration backup.** Preserve the complete private data directory when moving operating systems. Legacy encrypted `.focuser` files cannot be directly imported; export a new JSON file from the original service that still holds your rules.
