# 贡献与 Agent 工作指南

先阅读 README、SECURITY.md 与 docs/release/architecture.md，按现有 Python/JavaScript 结构修改，不引入无必要的云服务、依赖或数据采集。

- 不提交 outputs、迁移快照、state.json、备份、日志、凭据或个人浏览器配置。
- 用临时数据与独立端口测试；不要连接真实用户服务或领取真实额外分钟。
- 计时与限制修改运行完整 Python 与扩展回归。保留用量、额外分钟和操作绑定验证；不通过新分类、空目录或删除规则绕过验证。
- 平台支持按真实能力表述。缺少原生适配器时不能静默丢弃已有 App 限制。
- Issue 仅提供版本、平台、复现步骤与去敏错误。不要上传私人状态或历史。

基础测试无需桌面依赖：

```sh
python -m unittest discover -s tests -p "test_*.py"
node tests/test_screen_time_extension.cjs
```
