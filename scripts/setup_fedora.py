"""Install a Linux venv and generate a private systemd user unit, without starting it.

Existing users must supply their copied data directory. No usage or rules are edited.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from screen_time_runtime import default_data_dir
from screen_time_startup import command, render


def validate_data(data, new_install=False):
    state = data / 'state.json'
    if new_install:
        if data.exists() and any(data.iterdir()):
            raise ValueError('新安装目录必须为空；已有用户请移除 --new-install 并保留原数据')
    else:
        if not state.is_file():
            raise ValueError('找不到已有 state.json；迁移时请先私下复制完整数据目录。首次使用才添加 --new-install')
        # Validate a copy in memory only. BudgetStore initialization can migrate
        # legacy schemas, so the installer deliberately does not instantiate it.
        from screen_time_core import validate_groups
        config = json.loads(state.read_text(encoding='utf-8'))
        groups = validate_groups(config['groups'])
        if any(group['enabled'] and group['apps'] for group in groups):
            raise ValueError('Linux 不支持原生 App 拦截；先在原系统网页完成验证并调整不兼容规则，再复制数据')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=default_data_dir('linux'))
    parser.add_argument('--venv', type=Path, default=Path(__file__).resolve().parents[1] / '.venv')
    parser.add_argument('--output', type=Path, default=Path.home() / '.config/systemd/user')
    parser.add_argument('--port', type=int, default=18765)
    parser.add_argument('--new-install', action='store_true', help='Only for first-time users, never migration')
    parser.add_argument('--plan', action='store_true', help='Read-only; no installation or writes')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('此脚本仅在 Fedora/Linux 内运行')
    if not 1024 <= args.port <= 65535:
        parser.error('端口必须在1024到65535之间')
    data, venv, output = (path.expanduser().resolve() for path in (args.data_dir, args.venv, args.output))
    try:
        validate_data(data, args.new_install)
    except (ValueError, KeyError, OSError) as error:
        parser.error(str(error))
    python = venv / 'bin/python'
    argv = command(python, data, args.port)
    if any('\n' in item or '\r' in item or '\x00' in item for item in argv):
        parser.error('启动路径不能含换行或空字符')
    name, content = render('linux', argv)
    target = output / name
    if target.exists():
        parser.error('已有 focuser.service；安装器不会覆盖。升级请保留现有服务和数据目录')
    plan = {'venv': str(venv), 'data_dir': str(data), 'unit': str(target),
            'port': args.port, 'starts_service': False, 'modifies_state': False}
    if args.plan:
        print(json.dumps(plan, ensure_ascii=False))
        return
    if not python.exists():
        if venv.exists() and any(venv.iterdir()):
            parser.error('目标虚拟环境非空且缺少 bin/python；请选独立 Linux 虚拟环境')
        subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
    root = Path(__file__).resolve().parents[1]
    subprocess.run([str(python), '-m', 'pip', 'install', str(root)], check=True)
    output.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8', newline='\n') as handle:
        target.chmod(0o600)
        handle.write(content)
    print(json.dumps(plan, ensure_ascii=False))
    print('systemctl --user daemon-reload\nsystemctl --user enable --now focuser.service')


if __name__ == '__main__':
    main()
