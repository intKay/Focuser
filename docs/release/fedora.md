# Fedora 安装与迁移

Fedora 的 GNOME/KDE、Wayland/X11 均使用浏览器扩展计时，无需读取整个桌面的活动窗口，也不需要关闭 SELinux 或开放防火墙端口。Linux 原生 App 拦截尚未实现；不要将浏览器支持理解为桌面 App 支持。

## 准备环境

在 Fedora 终端运行，使用普通用户安装项目，不要 sudo pip：

```sh
sudo dnf install python3 python3-pip git
git clone https://github.com/intKay/Focuser.git
cd Focuser
```

浏览器优先使用 Chromium 系列的未打包扩展。Fedora 默认 Firefox 的测试扩展只能临时加载，重启后需重新加载；未提供签名 XPI。Flatpak 浏览器的 loopback 连通性需自行验收，不建议先用它诊断后端。

## 已有 Windows 用户：先保留数据

1. 在原系统备份完整实际数据目录。源码一键配置默认使用 `outputs/screen_time/release/ScreenTime/data`，安装包默认使用 `%LOCALAPPDATA%\Focuser`；自定义目录以实际启动参数为准。
2. 如果分类绑定了启用的 Windows App，先在原本机网页通过随机定积分验证调整不兼容规则，再迁移。安装器与 Linux 服务不会自动删除 App 规则；遇到这种规则会拒绝启动。
3. 维护切换前正常结束旧服务，复制最终完整数据目录到 Fedora 的 `~/.local/share/focuser`。通过私人本地介质传输，不上传 GitHub；不要覆盖 Fedora 已在使用的另一份数据，不合并或重新初始化记录。关闭旧系统后再运行新系统。
4. 保持两系统日期、时区一致。以下安装和升级不重置当日用量、规则、暂停状态或额外分钟；正常日期切换仍按程序规则结算。

```sh
chmod -R go-rwx "$HOME/.local/share/focuser"
python3 scripts/setup_fedora.py --data-dir "$HOME/.local/share/focuser" --plan
python3 scripts/setup_fedora.py --data-dir "$HOME/.local/share/focuser"
systemctl --user daemon-reload
systemctl --user enable --now focuser.service
```

安装器创建 Linux 虚拟环境、安装基础服务并生成权限为 600 的 systemd 用户服务，既不编辑状态，也不自行启动服务。不复制 Windows `.venv`、启动快捷方式或浏览器配置；它们不可作为 Linux 环境使用。已有服务文件不会被覆盖。

数据目录路径变更会改变 `instance_id`。目标 Fedora 浏览器安装一份新扩展，连接这份**已迁移数据**，端口保持 18765；不要清空数据解决连接问题。跨系统不实时同步，两套系统交替使用需在停止服务后传递最终数据；目前不支持并行使用或自动合并。

## 真正首次使用

仅没有既有记录的新用户使用 `--new-install`；迁移用户使用上一节流程。此标志要求数据目录不存在或为空。

```sh
python3 scripts/setup_fedora.py --new-install --plan
python3 scripts/setup_fedora.py --new-install
systemctl --user daemon-reload
systemctl --user enable --now focuser.service
```

服务在用户登录后静默运行，无需管理员或 linger。控制页手动打开 `http://127.0.0.1:18765/`。不需要后台服务打开浏览器，因此不依赖 systemd 中的 DISPLAY/Wayland 环境变量。

## 验收和升级

```sh
systemctl --user status focuser.service
curl --fail http://127.0.0.1:18765/api/health
journalctl --user -u focuser.service -n 30 --no-pager
```

只在本机查看诊断；分享问题时删除路径和状态，不发送完整数据。安装扩展后在网页检查平台能力、扩展连接，以及迁移前后的分类、今日用量和额外分钟状态。关闭浏览器再打开，应保持额度。Firefox 重启后需重新加载临时扩展。

升级先在独立目录/端口测试，再备份实际数据；维护停止服务、用原虚拟环境安装新源码后立即恢复服务，保留原 unit 与数据路径。暂停或退出恢复访问仍需网页验证；维护停服不能用作恢复访问。

CI 增加了 Fedora 容器中的 Python/扩展回归；容器测试无法证明真实 GNOME/Wayland 或浏览器扩展已验收。实机验收仍需在 Fedora 完成。

systemd 参考：[用户服务](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html)、[用户会话与 linger](https://www.freedesktop.org/software/systemd/man/latest/loginctl.html)。
