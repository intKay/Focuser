"""Standalone local Screen Time service and panel; run --dry-run first."""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import threading
import signal
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from screen_time_core import BudgetStore
from screen_time_core import validate_groups
from screen_time_config import export_config, import_config
from screen_time_challenge import ChallengeGuard, ChallengeRequired, relaxation
from screen_time_platform import select_platform, supervise
from screen_time_runtime import API_VERSION, VERSION, DataLock, default_data_dir, instance_id


PORT = 18765


def startup_view(no_ui=False, background=False, native_ui=False):
    """Select the control surface without changing app intention prompts."""
    if no_ui or background:
        return 'background'
    return 'native' if native_ui else 'web'


def resource_root():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "web"
    source = Path(__file__).resolve().parents[1] / "resources" / "screen_time" / "web"
    if source.is_dir():
        return source
    from importlib.resources import files
    return files('focuser_assets').joinpath('web')


def valid_origin(origin, port):
    if origin is None:
        return True  # loopback command-line probes and direct browser navigation
    return origin == f"http://127.0.0.1:{port}" or bool(re.fullmatch(
        r"chrome-extension://[a-p]{32}|moz-extension://[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", origin))


def make_handler(store, stop, root, port, adapter=None):
    guard = ChallengeGuard()
    adapter = adapter or select_platform()
    identity = instance_id(store.data_dir) if hasattr(store, 'data_dir') else 'test'
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *_args):
            pass  # Never persist requested URLs.

        def allowed(self):
            host = self.headers.get("Host")
            return host == f"127.0.0.1:{port}" and valid_origin(self.headers.get("Origin"), port)

        def reply(self, value, status=200):
            body = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            origin = self.headers.get("Origin")
            if origin and self.allowed():
                self.send_header("Access-Control-Allow-Origin", origin)
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            if not self.allowed():
                return self.reply({"error": "Origin denied"}, 403)
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", self.headers.get("Origin", f"http://127.0.0.1:{port}"))
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()

        def do_GET(self):
            if not self.allowed():
                return self.reply({"error": "Origin denied"}, 403)
            route = urlsplit(self.path).path
            if route in ('/extensions/chromium.zip', '/extensions/firefox.zip'):
                from screen_time_release import extension_archive
                browser = route.rsplit('/', 1)[-1].split('.')[0]
                content = extension_archive(browser)
                self.send_response(200)
                self.send_header('Content-Type', 'application/zip')
                self.send_header('Content-Disposition', f'attachment; filename="focuser-{browser}.zip"')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            if route == '/api/health':
                return self.reply({'service': 'focuser', 'version': VERSION,
                                   'api_version': API_VERSION, 'instance_id': identity,
                                   'capabilities': adapter.capabilities(),
                                   'app_errors': dict(store.app_errors)})
            if route == "/api/status":
                result = store.snapshot()
                result.update(version=VERSION, api_version=API_VERSION, instance_id=identity,
                              capabilities=adapter.capabilities())
                return self.reply(result)
            if route == "/api/apps":
                return self.reply({"apps": adapter.available_apps(), 'supported': adapter.native_apps})
            if route == '/api/config/export':
                with store.lock:
                    return self.reply(export_config(store.state['groups']))
            paths = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css", '/i18n.js': 'i18n.js', '/i18n.json': 'i18n.json', '/config-transfer.js':'config-transfer.js'}
            if route not in paths:
                return self.reply({"error": "Not found"}, 404)
            if route in ('/i18n.js', '/i18n.json'):
                from screen_time_release import extension_files
                content = extension_files().joinpath(paths[route]).read_bytes()
            else:
                content = (root / paths[route]).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(paths[route])[0] + "; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            if not self.allowed() or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.reply({"error": "Origin or content type denied"}, 403)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 65536:
                    raise ValueError("请求大小无效")
                data = json.loads(self.rfile.read(size).decode("utf-8"))
                if not isinstance(data, dict):
                    raise ValueError('请求必须为 JSON 对象')
                if 'instance_id' in data and data['instance_id'] != identity:
                    return self.reply({'error': '数据目录与扩展绑定不一致，请启动原服务；未执行操作'}, 409)
                route = urlsplit(self.path).path
                if route == '/api/challenge':
                    result = guard.issue(data.get('action'), data.get('payload'))
                elif route == '/api/verify':
                    result = guard.verify(data.get('id'), data.get('answer'), data.get('reasoning'))
                elif route == "/api/heartbeat":
                    active = data.get("active")
                    if active is True and not adapter.desktop_unlocked():
                        active = False
                    client, group_id = data.get("client"), data.get("group")
                    result = store.heartbeat(client, group_id, active, data.get("browser"), require_intent=True)
                    result["intent_granted"] = store.has_intent(client, group_id)
                    result.update(instance_id=identity, api_version=API_VERSION,
                                  capabilities=adapter.capabilities(), version=VERSION)
                elif route == "/api/intent":
                    result = store.submit_intent(data.get("client"), data.get("group"), data.get("purpose"))
                elif route == "/api/bonus":
                    result = store.claim_minute(data.get("group"))
                elif route == '/api/config/preview':
                    groups = import_config(data.get('config'), adapter.native_apps)
                    with store.lock:
                        result = {'groups':groups, 'requires_challenge':relaxation(store.state['groups'],groups),
                                  'categories':len(groups), 'websites':sum(len(g['domains']) for g in groups),
                                  'apps':sum(len(g['apps']) for g in groups)}
                elif route == "/api/config":
                    groups = validate_groups(data.get('groups'))
                    with store.lock:
                        if relaxation(store.state['groups'], groups):
                            guard.require('config', {'groups': data.get('groups')}, data.get('token'))
                        result = store.configure(groups)
                elif route == "/api/pause":
                    if data.get('paused') is True:
                        guard.require('pause', {'paused': True}, data.get('token'))
                    result = store.pause(data.get("paused"))
                elif route == "/api/quit":
                    guard.require('quit', {}, data.get('token'))
                    store.pause(True)
                    stop.set()
                    result = {"ok": True}
                else:
                    return self.reply({"error": "Not found"}, 404)
                self.reply(result)
            except ChallengeRequired as error:
                self.reply({'error': str(error), 'challenge_required': True}, 428)
            except (ValueError, TypeError, AttributeError, KeyError) as error:
                self.reply({"error": str(error)}, 400)
            except OSError:
                self.reply({'error': '无法保存数据，请检查磁盘权限与空间；服务未确认本次操作'}, 503)

    return Handler


def main():
    if len(sys.argv)>1 and sys.argv[1]=='setup':
        from screen_time_setup import main as setup
        return setup(sys.argv[2:])
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument('--lang', choices=['auto', 'en', 'zh'], default='auto', help='Native UI language; web UI has its own language selector')
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-ui", action="store_true")
    parser.add_argument("--background", action="store_true", help="Start without opening the panel")
    parser.add_argument("--native-ui", action="store_true", help="Optional native control window")
    parser.add_argument("--gate-client")
    parser.add_argument("--gate-group")
    parser.add_argument("--no-apps", action="store_true", help="Testing: never terminate apps")
    parser.add_argument('--version', action='version', version=VERSION)
    args = parser.parse_args()
    if args.lang != 'auto':
        os.environ['FOCUSER_LANG'] = args.lang
    if not 1024 <= args.port <= 65535:
        parser.error('端口必须在1024到65535之间')
    view = startup_view(args.no_ui, args.background, args.native_ui)
    if args.gate_client:
        from screen_time_gate import RemoteStore, ask_intention
        approved = ask_intention(RemoteStore(args.port), args.gate_group, args.gate_client, threading.Event())
        raise SystemExit(0 if approved else 2)
    if getattr(sys, 'frozen', False):
        legacy = Path(sys.executable).parent / 'data'
    else:
        root = Path(__file__).resolve().parents[1]
        legacy = root / 'outputs/screen_time/release/ScreenTime/data'
        if not (legacy / 'state.json').exists():
            legacy = root / 'outputs/screen_time/data'
    data_dir = (args.data_dir or (legacy if (legacy / 'state.json').exists() else default_data_dir())).expanduser().resolve()
    adapter = select_platform(native=not args.no_apps)
    if args.dry_run:
        print(json.dumps({"data_dir": str(data_dir), "writes": ["state.json"],
                          "overwrite": "Atomic replacement; consumed time retained; invalid existing file refused",
                          "listen": f"127.0.0.1:{args.port}", "app_enforcement": adapter.native_apps,
                          'capabilities': adapter.capabilities(),
                          "startup_view": view,
                          "system_changes": "none"}, ensure_ascii=False))
        return
    # Refuse conflicting services before touching state. Reopening our own
    # instance is allowed only when both the API and the data identity match.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f'http://127.0.0.1:{args.port}/api/health', timeout=1) as response:
            health = json.load(response)
    except Exception:
        health = None
    if health and health.get('service') == 'focuser' and health.get('instance_id') == instance_id(data_dir):
        if view == 'web':
            adapter.open_panel(f'http://127.0.0.1:{args.port}/')
        return
    with DataLock(data_dir):
        serve(args, view, data_dir, adapter)


def serve(args, view, data_dir, adapter):
    store = BudgetStore(data_dir)
    if not store.path.exists() and not adapter.native_apps:
        # New browser-only installations have no native bindings. Existing
        # state, including unsupported bindings, must never be rewritten here.
        for group in store.state['groups']:
            group['apps'] = []
    if (not args.no_apps and not adapter.native_apps
            and any(g['enabled'] and g['apps'] for g in store.state['groups'])):
        raise RuntimeError('规则包含桌面 App，但当前平台无法拦截；Windows 请安装 focuser-local[desktop]。跨平台迁移须先在原控制页验证并调整不兼容规则；未放宽限制')
    store.port = args.port
    stop = threading.Event()
    url = f"http://127.0.0.1:{args.port}/"
    try:
        class LocalServer(ThreadingHTTPServer):
            allow_reuse_address = False
        server = LocalServer(("127.0.0.1", args.port), make_handler(store, stop, resource_root(), args.port, adapter))
    except OSError as error:
        raise RuntimeError(f'端口 {args.port} 无法绑定；未覆盖数据，请检查已有服务') from error
    server.daemon_threads = True
    store.save()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if adapter.native_apps:
        threading.Thread(target=supervise, args=(store, stop, adapter.monitor), daemon=True).start()
    if not args.no_ui and hasattr(adapter, 'run_tray'):
        def tray():
            try:
                adapter.run_tray(store, stop, url)
            except Exception:
                store.app_errors['tray'] = '托盘不可用；请从浏览器打开控制页面'
        threading.Thread(target=tray, daemon=True).start()
    if view == 'native':
        from screen_time_launcher import show_launcher
        show_launcher(args.port, stop)
    elif view == 'web':
        threading.Thread(target=adapter.open_panel, args=(url,), daemon=True).start()
    previous_signals = {}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous_signals[sig] = signal.signal(sig, lambda *_: stop.set())
    try:
        while not stop.wait(0.25):
            store.settle()
    except KeyboardInterrupt:
        stop.set()
    finally:
        # Give the 30-second extension alarm time to read the paused state.
        # Native enforcement stops immediately; the HTTP server stays readable.
        if store.state["paused"]:
            threading.Event().wait(32)
        store.save()
        server.shutdown()
        server.server_close()
        for sig, handler in previous_signals.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    main()
