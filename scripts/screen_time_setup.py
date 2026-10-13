"""Connect a local installation to private data and user-login startup."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from screen_time_runtime import default_data_dir
from screen_time_startup import command, render
from screen_time_release import extension_entries


def selected_data(explicit=None):
    if explicit:
        return Path(explicit).expanduser().resolve()
    root = Path(__file__).resolve().parents[1]
    for relative in ['outputs/screen_time/release/ScreenTime/data', 'outputs/screen_time/data']:
        candidate = root / relative
        if (candidate / 'state.json').is_file():
            return candidate
    return default_data_dir().resolve()


def validate_install(data, new_install, native):
    if new_install:
        if data.exists() and any(data.iterdir()):
            raise ValueError('Data directory is not empty. Omit --new-install to retain existing usage.')
    else:
        path = data / 'state.json'
        if not path.is_file():
            raise ValueError('Existing state.json not found. Copy your private data first; only first-time users should use --new-install.')
        from screen_time_core import validate_groups
        state = json.loads(path.read_text(encoding='utf-8'))
        groups = validate_groups(state['groups'])
        if not native and any(g['enabled'] and g['apps'] for g in groups):
            raise ValueError('Native app rules are unsupported here. Verify and adjust incompatible rules in the original dashboard before migration.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--port', type=int, default=18765)
    parser.add_argument('--new-install', action='store_true')
    parser.add_argument('--enable-startup', action='store_true', help='Install and start the user-login service')
    parser.add_argument('--output-dir', type=Path, help='Generate only into an isolated folder')
    parser.add_argument('--plan', action='store_true', help='No writes, installation or process changes')
    parser.add_argument('--no-open', action='store_true')
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        parser.error('Port must be between 1024 and 65535')
    if args.enable_startup and args.output_dir:
        parser.error('--output-dir is for isolated generation; do not combine with --enable-startup')
    from screen_time_platform import select_platform
    data = selected_data(args.data_dir)
    try:
        validate_install(data, args.new_install, select_platform().native_apps)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    python = Path(sys.executable)
    if sys.platform == 'win32':
        python = python.with_name('pythonw.exe')
    argv = command(python, data, args.port)
    if any('\n' in x or '\r' in x or '\x00' in x for x in argv):
        parser.error('Paths cannot contain newlines or null characters')
    name, unit = render(sys.platform, argv)
    startup = {'linux': Path.home()/'.config/systemd/user',
               'darwin': Path.home()/'Library/LaunchAgents',
               'win32': Path(os.environ.get('APPDATA', Path.home()/'AppData/Roaming'))/'Microsoft/Windows/Start Menu/Programs/Startup'}[sys.platform]
    output = args.output_dir or startup
    target = output / name
    extensions = (args.output_dir or default_data_dir().parent / 'focuser-install') / 'browser-extension'
    if target.exists() and target.read_text(encoding='utf-8') != unit:
        parser.error('An existing startup entry has different settings. Keep its data directory and interpreter; it was not overwritten.')
    plan = {'data_dir':str(data), 'startup':str(target), 'extension':str(extensions), 'modifies_state':False,
            'enable_startup':args.enable_startup, 'panel':f'http://127.0.0.1:{args.port}/'}
    if args.plan:
        print(json.dumps(plan, ensure_ascii=False, indent=2)); return
    output.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        with target.open('x', encoding='utf-8', newline='\n') as handle:
            if sys.platform != 'win32': target.chmod(0o600)
            handle.write(unit)
    extensions.mkdir(parents=True, exist_ok=True)
    for relative, content in extension_entries('chromium'):
        destination = extensions / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    if args.enable_startup:
        if sys.platform == 'linux':
            subprocess.run(['systemctl','--user','daemon-reload'], check=True)
            subprocess.run(['systemctl','--user','enable','--now','focuser.service'], check=True)
        elif sys.platform == 'darwin':
            subprocess.run(['launchctl','bootstrap',f'gui/{os.getuid()}',str(target)], check=True)
        else:
            subprocess.Popen(argv, creationflags=0x08000000)
        if not args.no_open:
            import webbrowser
            webbrowser.open(plan['panel'])
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    print('Next: open the dashboard, then load the browser-extension folder in your browser.\n下一步：打开控制页，在浏览器扩展管理页加载 browser-extension 文件夹。')


if __name__ == '__main__':
    main()
