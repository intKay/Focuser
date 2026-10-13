"""Run against a wheel installed in a separate empty virtual environment."""
from __future__ import annotations
import argparse
import copy
import io
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from datetime import date
from pathlib import Path


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--python', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    temp_root = root / 'outputs/screen_time/test-temp'
    temp_root.mkdir(parents=True, exist_ok=True)
    fixture = Path(tempfile.mkdtemp(prefix='wheel-', dir=temp_root))
    data = fixture / 'data'; data.mkdir()
    state = {'version': 1, 'groups': [
        {'id': 'social', 'name': 'Wheel fixture', 'mode': 'limit', 'minutes': 30,
         'enabled': True, 'color': '#5856d6', 'domains': ['example.com'], 'apps': []}],
        'history': {date.today().isoformat(): {'social': 1860}},
        'bonus': {date.today().isoformat(): 'social'}, 'paused': False}
    (data / 'state.json').write_text(json.dumps(state), encoding='utf-8')
    port = free_port()
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    env = dict(os.environ, PYTHONUTF8='1')
    command = [str(args.python.resolve()), '-m', 'screen_time_server', '--port', str(port),
               '--data-dir', str(data), '--no-ui']
    checks = {}

    def get(route):
        with opener.open(f'http://127.0.0.1:{port}{route}', timeout=3) as response:
            return response.read()

    def start():
        process = subprocess.Popen(command, cwd=fixture, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(60):
            try:
                if json.loads(get('/api/health'))['service'] == 'focuser': return process
            except Exception: pass
            if process.poll() is not None:
                raise RuntimeError(process.communicate()[1].decode('utf-8'))
            time.sleep(0.1)
        process.terminate(); process.wait(5)
        raise RuntimeError('Wheel server did not start')

    process = start()
    try:
        checks['installed_assets'] = b'Focuser' in get('/')
        for browser in ['chromium', 'firefox']:
            with zipfile.ZipFile(io.BytesIO(get(f'/extensions/{browser}.zip'))) as archive:
                checks[f'{browser}_packaged_assets'] = 'connection.js' in archive.namelist()
        before = json.loads((data / 'state.json').read_text(encoding='utf-8'))
        result = subprocess.run(command, cwd=fixture, env=env, capture_output=True, timeout=10)
        checks['repeat_start_same_instance'] = result.returncode == 0
        checks['repeat_start_keeps_state'] = before == json.loads((data / 'state.json').read_text(encoding='utf-8'))
        other_command = command.copy(); other_command[other_command.index('--port') + 1] = str(free_port())
        result = subprocess.run(other_command, cwd=fixture, env=env, capture_output=True, timeout=10)
        checks['second_writer_rejected'] = result.returncode != 0
        status = json.loads(get('/api/status'))
        checks['quota_and_bonus_preserved'] = status['groups'][0]['remaining_seconds'] == 0 and status['bonus_used'] and not status['paused']
    finally:
        process.terminate(); process.wait(5)
    process = start()
    try:
        status = json.loads(get('/api/status'))
        checks['restart_keeps_exhaustion'] = status['groups'][0]['blocked'] and status['bonus_used'] and not status['paused']
    finally:
        process.terminate(); process.wait(5)
    result = {'checks': checks, 'fixture': str(fixture)}
    (fixture / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    if not all(checks.values()): raise SystemExit(1)


if __name__ == '__main__':
    main()
