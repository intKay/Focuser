"""Generate opt-in per-user startup files; never install or enable them silently."""
from __future__ import annotations
import argparse
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path

from screen_time_runtime import default_data_dir


def command(python, data_dir, port):
    # -m works for installed wheels and does not depend on the checkout location.
    return [str(Path(python).resolve()), '-m', 'screen_time_server', '--background',
            '--data-dir', str(Path(data_dir).expanduser().resolve()), '--port', str(port)]


def render(platform, argv):
    if platform == 'darwin':
        return 'org.focuser.local.plist', plistlib.dumps({
            'Label': 'org.focuser.local', 'ProgramArguments': argv,
            'RunAtLoad': True, 'KeepAlive': {'SuccessfulExit': False},
            'ThrottleInterval': 10}).decode()
    if platform == 'linux':
        # systemd escaping: quotes/backslashes and literal percent specifiers.
        quoted = ['"' + arg.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$') + '"' for arg in argv]
        return 'focuser.service', '\n'.join([
            '[Unit]', 'Description=Focuser local screen time', 'After=graphical-session.target',
            '[Service]', 'Type=simple', 'ExecStart=' + ' '.join(quoted),
            'Restart=on-failure', 'RestartSec=10', 'UMask=0077',
            '[Install]', 'WantedBy=default.target', ''])
    if platform == 'win32':
        # VBScript invokes the interpreter hidden; doubled quotes are VBS escaping.
        line = subprocess.list2cmdline(argv).replace('"', '""')
        return 'Focuser.vbs', 'Set shell = CreateObject("WScript.Shell")\n' + f'shell.Run "{line}", 0, False\n'
    raise ValueError('不支持的平台')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=['win32', 'darwin', 'linux'], default=sys.platform)
    parser.add_argument('--python', default=sys.executable)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--port', type=int, default=18765)
    parser.add_argument('--output', type=Path, help='Write into this directory; no automatic installation')
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('端口必须在1024到65535之间')
    argv = command(args.python, args.data_dir or default_data_dir(args.platform), args.port)
    if any('\n' in item or '\r' in item or '\x00' in item for item in argv):
        parser.error('启动路径不能含换行或空字符')
    name, content = render(args.platform, argv)
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        target = args.output / name
        with target.open('x', encoding='utf-8', newline='\n') as handle:
            handle.write(content)
        print(json.dumps({'written': str(target), 'installed': False}, ensure_ascii=False))
    else:
        print(content, end='')


if __name__ == '__main__':
    main()
