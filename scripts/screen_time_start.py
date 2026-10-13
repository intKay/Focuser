"""Local source entry point for an installed, signed Python runtime."""
from __future__ import annotations

import sys
import json
import urllib.request
import argparse
from pathlib import Path


def existing_service(port, data_dir):
    """Allow the desktop entry to open an existing 1.2 service during upgrades."""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f'http://127.0.0.1:{port}/api/status', timeout=2) as response:
            status = json.load(response)
        if not isinstance(status, dict) or not isinstance(status.get('groups'), list):
            return False
        if status.get('version') == '1.2.0':
            return True
        from screen_time_runtime import instance_id
        return status.get('api_version') == 1 and status.get('instance_id') == instance_id(data_dir)
    except Exception:
        return False


def main():
    root = Path(__file__).resolve().parents[1]
    dependencies = root / 'outputs' / 'screen_time' / 'builder'
    if dependencies.is_dir():
        sys.path.insert(0, str(dependencies))
    if '--data-dir' not in sys.argv and '--gate-client' not in sys.argv:
        sys.argv.extend(['--data-dir', str(root / 'outputs/screen_time/release/ScreenTime/data')])
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--port', type=int, default=18765)
    parser.add_argument('--data-dir', type=Path)
    selected, _ = parser.parse_known_args()
    if '--gate-client' not in sys.argv and '--dry-run' not in sys.argv and existing_service(selected.port, selected.data_dir):
        if '--background' not in sys.argv and '--no-ui' not in sys.argv:
            from screen_time_platform import select_platform
            select_platform().open_panel(f'http://127.0.0.1:{selected.port}/')
        return
    from screen_time_server import main as serve
    serve()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # pythonw must not hide a failed desktop/boot launch.
        import traceback
        log = Path(__file__).resolve().parents[1] / 'outputs/screen_time/startup-error.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(traceback.format_exc(), encoding='utf-8')
        if sys.platform == 'win32' and '--background' not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, f'启动失败：{error}\n\n诊断记录：{log}', 'Focuser', 0x10)
        raise
