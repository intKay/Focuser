from __future__ import annotations
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import socket
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from screen_time_core import BudgetStore, DEFAULT_GROUPS, validate_groups
from screen_time_runtime import DataLock, default_data_dir, instance_id
from screen_time_platform import BrowserPlatform, select_platform
from screen_time_release import extension_archive, source_files
from screen_time_server import make_handler, resource_root, valid_origin
from screen_time_startup import command, render
from screen_time_start import existing_service


class PortableTests(unittest.TestCase):
    def setUp(self):
        base = ROOT / 'outputs/screen_time/test-temp'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.data = Path(self.temp.name) / 'data'

    def tearDown(self):
        self.temp.cleanup()

    def test_platform_data_paths(self):
        self.assertEqual(default_data_dir('win32', {'LOCALAPPDATA': 'C:/local'}, '/user'), Path('C:/local/Focuser'))
        self.assertEqual(default_data_dir('darwin', {}, '/user'), Path('/user/Library/Application Support/Focuser'))
        self.assertEqual(default_data_dir('linux', {'XDG_DATA_HOME': '/data'}, '/user'), Path('/data/focuser'))

    def test_core_runs_without_site_packages(self):
        result = subprocess.run([sys.executable, '-S', str(ROOT / 'scripts/screen_time_server.py'),
                                 '--data-dir', str(self.data), '--no-apps', '--dry-run'], capture_output=True, check=True,
                                env=dict(os.environ, PYTHONUTF8='1'))
        self.assertFalse(json.loads(result.stdout)['app_enforcement'])
        self.assertFalse(self.data.exists())

    def test_zero_dependency_new_install_and_existing_native_guard(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
        command = [sys.executable, '-S', str(ROOT / 'scripts/screen_time_server.py'),
                   '--data-dir', str(self.data), '--port', str(port), '--no-ui']
        env = dict(os.environ, PYTHONUTF8='1')
        process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        status = None
        try:
            for _ in range(50):
                try:
                    with opener.open(f'http://127.0.0.1:{port}/api/status', timeout=1) as response:
                        status = json.load(response); break
                except Exception: time.sleep(0.1)
            self.assertIsNotNone(status)
            self.assertFalse(status['capabilities']['native_apps'])
            self.assertTrue(all(not group['apps'] for group in status['groups']))
        finally:
            process.terminate(); process.wait(5)
            process.stdout.close(); process.stderr.close()
        state = json.loads((self.data / 'state.json').read_text(encoding='utf-8'))
        state['groups'][0]['apps'] = ['douyin.exe']
        before = json.dumps(state).encode()
        (self.data / 'state.json').write_bytes(before)
        result = subprocess.run(command, env=env, capture_output=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.data / 'state.json').read_bytes(), before)

    def test_mac_and_linux_do_not_import_windows_dependencies(self):
        for platform in ['darwin', 'linux']:
            with patch('screen_time_platform.sys.platform', platform), patch('screen_time_platform.importlib.util.find_spec', side_effect=AssertionError('dependency check')):
                adapter = select_platform()
                self.assertFalse(adapter.native_apps)
                self.assertEqual(adapter.available_apps(), [])

    def test_data_lock_blocks_other_process_and_releases(self):
        script = 'from screen_time_runtime import DataLock; import sys; DataLock(sys.argv[1]).acquire()'
        env = dict(os.environ, PYTHONPATH=str(ROOT / 'scripts'))
        with DataLock(self.data):
            result = subprocess.run([sys.executable, '-c', script, str(self.data)], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((self.data / 'state.json').exists())
        result = subprocess.run([sys.executable, '-c', script, str(self.data)], env=env, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_data_identity_stable_without_disclosing_path(self):
        identity = instance_id(self.data)
        self.assertEqual(identity, instance_id(self.data / '..' / 'data'))
        self.assertNotEqual(identity, instance_id(self.data / 'other'))
        self.assertEqual(len(identity), 32)

    def test_invalid_usage_and_bonus_refused_without_replacement(self):
        store = BudgetStore(self.data)
        for field, value in [('history', {'2026-10-07': {'social': -1}}),
                             ('history', {'2026-10-07': {'social': float('nan')}}),
                             ('paused', 'false'), ('bonus', []), ('bonus', {'2026-10-07': 5})]:
            state = copy.deepcopy(store.state)
            state[field] = value
            self.data.mkdir(exist_ok=True)
            store.path.write_text(json.dumps(state), encoding='utf-8')
            before = store.path.read_bytes()
            with self.assertRaises(ValueError):
                BudgetStore(self.data)
            self.assertEqual(store.path.read_bytes(), before)

    def test_failed_persistent_operations_roll_back_in_memory(self):
        for action in ['pause', 'configure', 'bonus']:
            store = BudgetStore(self.data)
            store.save()
            before = copy.deepcopy(store.state)
            disk = store.path.read_bytes()
            with patch.object(store, 'save', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    if action == 'pause': store.pause(True)
                    elif action == 'configure':
                        groups = copy.deepcopy(DEFAULT_GROUPS); groups[1]['minutes'] = 10
                        store.configure(groups)
                    else: store.claim_minute('douyin')
            self.assertEqual(store.state, before)
            self.assertEqual(store.path.read_bytes(), disk)

    def test_extra_browsers_share_usage_and_survive_restart(self):
        tick = [1000.0]
        store = BudgetStore(self.data, lambda: 1791374400 + tick[0], lambda: tick[0])
        for name in ['Chrome', 'Edge', 'Firefox', 'Brave', 'Opera', 'Chromium', 'Vivaldi']:
            store.heartbeat(name, 'social', True, browser=name)
        self.assertTrue(store.snapshot()['browsers']['Vivaldi'])
        tick[0] += 2
        self.assertEqual(store.snapshot()['groups'][1]['used_seconds'], 2)
        store.claim_minute('douyin'); store.save()
        restored = BudgetStore(self.data, lambda: 1791374400 + tick[0], lambda: tick[0])
        self.assertEqual(restored.snapshot()['groups'][1]['used_seconds'], 2)
        self.assertTrue(restored.snapshot()['bonus_used'])

    def test_firefox_origin_is_exact(self):
        self.assertTrue(valid_origin('moz-extension://12345678-abcd-1234-abcd-123456789abc', 18765))
        for origin in ['moz-extension://anything', 'moz-extension://12345678-abcd-1234-abcd-123456789abc.evil', 'https://127.0.0.1:18765']:
            self.assertFalse(valid_origin(origin, 18765))

    def test_supported_browser_processes_cannot_be_native_targets(self):
        for executable in ['brave.exe', 'opera.exe', 'chromium.exe', 'vivaldi.exe']:
            groups = copy.deepcopy(DEFAULT_GROUPS)
            groups[1]['apps'] = [executable]
            with self.assertRaises(ValueError):
                validate_groups(groups)

    def test_extension_manifests_and_source_exclude_private_data(self):
        for browser in ['chromium', 'firefox']:
            with zipfile.ZipFile(io.BytesIO(extension_archive(browser))) as archive:
                manifest = json.loads(archive.read('manifest.json'))
                self.assertIn('options.js', archive.namelist())
                self.assertIn('connection.js', archive.namelist())
                self.assertIn('vendor/LICENSE-Focuser.txt', archive.namelist())
                self.assertNotIn('state.json', archive.namelist())
                if browser == 'firefox':
                    self.assertIn('scripts', manifest['background'])
                    self.assertNotIn('service_worker', manifest['background'])
                else: self.assertIn('service_worker', manifest['background'])
        files = [p.relative_to(ROOT).as_posix() for p in source_files(ROOT)]
        self.assertTrue(files)
        self.assertFalse(any(p.startswith(('outputs/', 'migration/')) or p.endswith('state.json') for p in files))

    def test_generated_startup_templates_preserve_argv(self):
        import plistlib
        argv = command('/python path/python', self.data, 19876)
        name, content = render('darwin', argv)
        self.assertEqual(plistlib.loads(content.encode())['ProgramArguments'], argv)
        _, content = render('linux', argv)
        self.assertIn('Restart=on-failure', content)
        self.assertIn('--data-dir', content)
        _, content = render('win32', argv)
        self.assertIn(', 0, False', content)

    def test_desktop_opens_legacy_service_and_rejects_different_data(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({'version': '1.2.0', 'groups': []}).encode()
        opener = MagicMock(); opener.open.return_value = response
        with patch('screen_time_start.urllib.request.build_opener', return_value=opener):
            self.assertTrue(existing_service(19876, self.data))
            response.__enter__.return_value.read.return_value = json.dumps({'version':'1.3.0rc1','groups':[], 'api_version':1,'instance_id':instance_id(self.data / 'different')}).encode()
            self.assertFalse(existing_service(19876, self.data))


class PortableHTTPTests(unittest.TestCase):
    def setUp(self):
        PortableTests.setUp(self)
        self.store = BudgetStore(self.data)
        self.store.save()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), lambda *a: None)
        self.port = self.server.server_address[1]
        self.server.RequestHandlerClass = make_handler(self.store, threading.Event(), resource_root(), self.port, BrowserPlatform())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(2)
        PortableTests.tearDown(self)

    def request(self, route, data=None, origin=None):
        headers = {'Content-Type': 'application/json'}
        if origin: headers['Origin'] = origin
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{route}', data=json.dumps(data).encode() if data is not None else None, headers=headers)
        try:
            with self.opener.open(req, timeout=3) as response: return response.status, response.read()
        except urllib.error.HTTPError as error: return error.code, error.read()

    def test_health_and_downloads_do_not_consume_time(self):
        before = self.store.path.read_bytes()
        code, body = self.request('/api/health')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['api_version'], 1)
        for browser in ['chromium', 'firefox']:
            code, body = self.request(f'/extensions/{browser}.zip')
            self.assertEqual(code, 200)
            with zipfile.ZipFile(io.BytesIO(body)) as archive: self.assertIn('manifest.json', archive.namelist())
        self.assertEqual(before, self.store.path.read_bytes())

    def test_mismatched_data_identity_cannot_claim_or_change_rules(self):
        for route, data in [('/api/bonus', {'group': 'douyin'}), ('/api/pause', {'paused': False}), ('/api/heartbeat', {'client': 'x', 'group': 'social', 'active': True})]:
            data['instance_id'] = 'different'
            self.assertEqual(self.request(route, data)[0], 409)
        self.assertFalse(self.store.snapshot()['bonus_used'])

    def test_bad_payload_and_web_origin_rejected(self):
        self.assertEqual(self.request('/api/pause', [1])[0], 400)
        self.assertEqual(self.request('/api/status', origin='https://evil.example')[0], 403)

    def test_new_classification_cannot_bypass_challenge(self):
        groups = copy.deepcopy(DEFAULT_GROUPS)
        groups[1]['id'] = 'new-social'
        self.assertEqual(self.request('/api/config', {'groups': groups})[0], 428)
        self.assertEqual(self.store.state['groups'], DEFAULT_GROUPS)


if __name__ == '__main__':
    unittest.main()
