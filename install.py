"""One source installer for Windows, macOS and Linux. Never reset existing data."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--new-install', action='store_true', help='Only for first-time users')
    parser.add_argument('--data-dir', type=Path, help='Existing private data directory for upgrades/migration')
    parser.add_argument('--port', type=int, default=18765)
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--no-open', action='store_true')
    parser.add_argument('--no-startup', action='store_true', help='Generate a template only')
    args = parser.parse_args()
    if sys.version_info < (3,10): parser.error('Python 3.10 or newer is required')
    root = Path(__file__).resolve().parent
    sys.path.insert(0,str(root/'scripts'))
    from screen_time_setup import selected_data, validate_install
    data = selected_data(args.data_dir)
    try:
        validate_install(data,args.new_install,sys.platform=='win32')
    except (OSError,ValueError,KeyError) as error: parser.error(str(error))
    if not 1024 <= args.port <= 65535: parser.error('Invalid port')
    venv = root/'.venv'
    python = venv/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')
    if args.plan:
        print(json.dumps({'venv':str(venv),'data_dir':str(data),'writes_state':False,'enable_startup':not args.no_startup},indent=2));return
    if not python.exists():
        if venv.exists() and any(venv.iterdir()): parser.error('Existing .venv is incompatible. Use a fresh source directory, retaining --data-dir.')
        subprocess.run([sys.executable,'-m','venv',str(venv)],check=True)
    spec = str(root)+('[desktop]' if sys.platform=='win32' else '')
    subprocess.run([str(python),'-m','pip','install',spec],check=True)
    command=[str(python),'-m','screen_time_setup','--data-dir',str(data),'--port',str(args.port)]
    if args.new_install:command.append('--new-install')
    if not args.no_startup:command.append('--enable-startup')
    if args.no_open:command.append('--no-open')
    subprocess.run(command,check=True)


if __name__=='__main__':main()
