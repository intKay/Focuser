from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from screen_time_core import BudgetStore, DEFAULT_GROUPS, validate_groups
from screen_time_server import valid_origin, startup_view


class Clock:
    def __init__(self, wall=None):
        self.wall = wall or datetime(2026, 10, 7, 12, 0).timestamp()
        self.mono = 1000.0

    def advance(self, seconds):
        self.wall += seconds
        self.mono += seconds


class ScreenTimeTests(unittest.TestCase):
    def setUp(self):
        temp_root = SCRIPTS.parent / "outputs" / "screen_time" / "test-temp"
        temp_root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_root)
        self.clock = Clock()
        self.store = BudgetStore(Path(self.temp.name), lambda: self.clock.wall, lambda: self.clock.mono)

    def tearDown(self):
        self.temp.cleanup()

    def social(self):
        return next(g for g in self.store.snapshot()["groups"] if g["id"] == "social")

    def test_first_activity_does_not_backfill(self):
        self.clock.advance(100)
        self.store.heartbeat("chrome", "social", True)
        self.assertEqual(self.social()["used_seconds"], 0)

    def test_overlapping_browsers_and_app_count_once(self):
        for client in ["chrome", "edge", "native"]:
            self.store.heartbeat(client, "social", True)
        self.clock.advance(2)
        self.assertEqual(self.social()["used_seconds"], 2)

    def test_blur_stops_counting(self):
        self.store.heartbeat("chrome", "social", True)
        self.clock.advance(1)
        self.store.heartbeat("chrome", "social", False)
        self.clock.advance(2)
        self.assertEqual(self.social()["used_seconds"], 1)

    def test_switch_to_vivaldi_shares_exhausted_budget(self):
        groups = copy.deepcopy(DEFAULT_GROUPS)
        groups[1]['minutes'] = 1
        self.store.configure(groups)
        for browser in ['Chrome', 'Vivaldi']:
            for _ in range(30):
                self.store.heartbeat(browser, 'social', True, browser=browser)
                self.clock.advance(1)
            self.store.heartbeat(browser, 'social', False, browser=browser)
        self.assertEqual(self.social()['used_seconds'], 60)
        self.assertEqual(self.social()['remaining_seconds'], 0)
        for browser in ['Chrome', 'Edge', 'Vivaldi']:
            result = self.store.heartbeat(browser, 'social', True, browser=browser)
            self.assertTrue(result['groups'][1]['blocked'])
        self.store.save()
        restored = BudgetStore(Path(self.temp.name), lambda: self.clock.wall, lambda: self.clock.mono)
        self.assertEqual(restored.snapshot()['groups'][1]['remaining_seconds'], 0)

    def test_expired_client_lease(self):
        self.store.heartbeat("chrome", "social", True)
        self.clock.advance(3)
        self.assertEqual(self.social()["used_seconds"], 2)
        self.clock.advance(1)
        self.assertEqual(self.social()["used_seconds"], 2)

    def test_sleep_does_not_charge(self):
        self.store.heartbeat("chrome", "social", True)
        self.clock.advance(300)
        self.assertEqual(self.social()["used_seconds"], 0)

    def test_midnight_splits_and_resets_without_losing_yesterday(self):
        self.clock.wall = datetime(2026, 10, 7, 23, 59, 59).timestamp()
        self.store.last_wall = self.clock.wall
        self.store.heartbeat("chrome", "social", True)
        self.clock.advance(2)
        result = self.store.snapshot()
        self.assertEqual(result["history"]["2026-10-07"]["social"], 1)
        self.assertEqual(result["history"]["2026-10-08"]["social"], 1)
        self.assertEqual(self.social()["remaining_seconds"], 1799)

    def test_exhaustion_blocks_group_and_survives_restart(self):
        groups = copy.deepcopy(DEFAULT_GROUPS)
        groups[1]["minutes"] = 1
        self.store.configure(groups)
        for _ in range(60):
            self.store.heartbeat("chrome", "social", True)
            self.clock.advance(1)
        self.assertTrue(self.social()["blocked"])
        self.store.save()
        restored = BudgetStore(Path(self.temp.name), lambda: self.clock.wall, lambda: self.clock.mono)
        self.assertTrue(restored.snapshot()["groups"][1]["blocked"])

    def test_toggle_and_quota_changes_do_not_refill_usage(self):
        self.store.heartbeat("chrome", "social", True)
        self.clock.advance(2)
        groups = copy.deepcopy(DEFAULT_GROUPS)
        groups[1]["enabled"] = False
        self.store.configure(groups)
        groups[1]["enabled"] = True
        groups[1]["minutes"] = 15
        self.store.configure(groups)
        self.assertEqual(self.social()["remaining_seconds"], 898)

    def test_pause_preserves_usage(self):
        self.store.heartbeat("chrome", "social", True)
        self.clock.advance(2)
        self.store.pause(True)
        self.assertFalse(self.store.snapshot()["groups"][0]["blocked"])
        self.clock.advance(3)
        self.store.pause(False)
        self.assertEqual(self.social()["used_seconds"], 2)

    def test_wrong_clock_does_not_charge(self):
        self.store.heartbeat("chrome", "social", True)
        self.clock.wall -= 3600
        self.clock.mono += 1
        self.assertEqual(self.social()["used_seconds"], 0)

    def test_invalid_config_does_not_replace_valid_state(self):
        self.store.save()
        before = self.store.path.read_bytes()
        groups = copy.deepcopy(DEFAULT_GROUPS)
        groups[1]["minutes"] = 0
        with self.assertRaises(ValueError):
            self.store.configure(groups)
        self.assertEqual(before, self.store.path.read_bytes())

    def test_corrupted_state_is_preserved(self):
        self.store.path.write_text("broken", encoding="utf-8")
        with self.assertRaises(ValueError):
            BudgetStore(Path(self.temp.name))
        self.assertEqual(self.store.path.read_text(encoding="utf-8"), "broken")

    def test_domain_boundaries_and_protected_apps(self):
        groups = copy.deepcopy(DEFAULT_GROUPS)
        groups[1]["domains"].append("live.douyin.com")
        with self.assertRaises(ValueError):
            validate_groups(groups)
        groups = copy.deepcopy(DEFAULT_GROUPS)
        groups[1]["apps"] = ["explorer.exe"]
        with self.assertRaises(ValueError):
            validate_groups(groups)

    def test_data_dir_cannot_be_a_file(self):
        path = Path(self.temp.name) / "file"
        path.write_text("keep", encoding="utf-8")
        with self.assertRaises(ValueError):
            BudgetStore(path)
        self.assertEqual(path.read_text(encoding="utf-8"), "keep")

    def test_origin_boundaries(self):
        self.assertTrue(valid_origin("http://127.0.0.1:18765", 18765))
        self.assertTrue(valid_origin("chrome-extension://" + "a" * 32, 18765))
        for origin in ["http://evil.com", "http://127.0.0.1.evil.com:18765", "null", "chrome-extension://wrong"]:
            self.assertFalse(valid_origin(origin, 18765))

    def exhaust(self):
        self.store.state["history"].setdefault(self.store.day(self.clock.wall), {})["social"] = 1800
        self.assertTrue(self.social()["blocked"])

    def test_minute_only_after_exhaustion(self):
        with self.assertRaises(ValueError):
            self.store.claim_minute('social')
        self.exhaust()
        result = self.store.claim_minute("social")
        self.assertTrue(result["bonus_used"])
        self.assertFalse(self.social()["blocked"])
        self.assertEqual(self.social()["remaining_seconds"], 60)
        with self.assertRaises(ValueError):
            self.store.claim_minute("social")

    def test_minute_expires_and_restart_cannot_claim_again(self):
        self.exhaust()
        self.store.claim_minute("social")
        for _ in range(60):
            self.store.heartbeat("test", "social", True)
            self.clock.advance(1)
        self.assertTrue(self.social()["blocked"])
        restored = BudgetStore(Path(self.temp.name), lambda: self.clock.wall, lambda: self.clock.mono)
        with self.assertRaises(ValueError):
            restored.claim_minute("social")

    def test_bonus_shared_by_every_group(self):
        self.exhaust()
        groups = copy.deepcopy(DEFAULT_GROUPS)
        groups.append({**groups[1], "id": "another", "domains": []})
        self.store.configure(groups)
        self.store.state["history"][self.store.day(self.clock.wall)]["another"] = 1800
        self.store.claim_minute("social")
        with self.assertRaises(ValueError):
            self.store.claim_minute("another")

    def test_douyin_minute_requires_purpose_expires_and_is_shared(self):
        self.store.claim_minute('douyin')
        self.store.heartbeat('web', 'douyin', True, require_intent=True)
        self.clock.advance(2)
        self.assertEqual(self.store.snapshot()['groups'][0]['used_seconds'], 0)
        self.store.submit_intent('web', 'douyin', '查指定视频')
        for _ in range(62):
            self.store.heartbeat('web', 'douyin', True, require_intent=True)
            self.clock.advance(1)
        group = self.store.snapshot()['groups'][0]
        self.assertTrue(group['blocked'])
        self.assertEqual(group['used_seconds'], 60)
        self.exhaust()
        with self.assertRaises(ValueError):
            self.store.claim_minute('social')

    def test_stale_active_heartbeat_cannot_shorten_extra_minute(self):
        self.exhaust()
        for _ in range(3):
            self.store.heartbeat('stale', 'social', True)
            self.clock.advance(2)
        self.assertEqual(self.social()['used_seconds'], 1800)
        self.store.claim_minute('social')
        self.assertEqual(self.social()['remaining_seconds'], 60)

    def test_legacy_overcount_still_grants_full_minute(self):
        self.exhaust()
        self.store.state['history'][self.store.day(self.clock.wall)]['social'] = 1805
        self.store.claim_minute('social')
        self.assertEqual(self.social()['remaining_seconds'], 60)

    def test_paused_douyin_cannot_claim(self):
        self.store.pause(True)
        with self.assertRaises(ValueError):
            self.store.claim_minute('douyin')

    def test_midnight_refreshes_one_minute_allowance(self):
        self.exhaust()
        self.store.claim_minute("social")
        self.clock.advance(86400)
        self.assertFalse(self.store.snapshot()["bonus_used"])
        self.exhaust()
        self.store.claim_minute("social")

    def test_intention_required_before_counting_and_text_not_saved(self):
        self.store.heartbeat("document1", "social", True, require_intent=True)
        self.clock.advance(2)
        self.assertEqual(self.social()["used_seconds"], 0)
        with self.assertRaises(ValueError):
            self.store.submit_intent("document1", "social", "  ")
        self.store.submit_intent("document1", "social", "查闭包的定义")
        self.store.heartbeat("document1", "social", True, require_intent=True)
        self.clock.advance(2)
        self.assertEqual(self.social()["used_seconds"], 2)
        self.store.save()
        self.assertNotIn("查闭包", self.store.path.read_text(encoding="utf-8"))
        self.assertFalse(self.store.has_intent("document2", "social"))
        restored = BudgetStore(Path(self.temp.name), lambda: self.clock.wall, lambda: self.clock.mono)
        self.assertFalse(restored.has_intent("document1", "social"))

    def test_intention_does_not_bypass_blocked_group(self):
        with self.assertRaises(ValueError):
            self.store.submit_intent("document1", "douyin", "看一个视频")

    def test_transient_atomic_file_lock_is_retried(self):
        from screen_time_storage import write_json
        attempts = []
        def locked(path, state):
            attempts.append(path)
            if len(attempts) < 3:
                raise PermissionError("temporary scanner lock")
            write_json(path, state)
        with patch("screen_time_core.write_json", side_effect=locked), patch("screen_time_core.time.sleep"):
            self.store.save()
        self.assertEqual(len(attempts), 3)
        self.assertTrue(self.store.path.is_file())

    @unittest.skipUnless(sys.platform == 'win32', 'Windows adapter')
    def test_panel_uses_registered_windows_browser(self):
        from screen_time_windows import open_panel
        with patch("screen_time_windows.os.startfile") as launch:
            open_panel("http://127.0.0.1:18765/")
        launch.assert_called_once_with("http://127.0.0.1:18765/")

    @unittest.skipUnless(sys.platform == 'win32', 'Windows adapter')
    def test_foreground_process_exit_is_not_an_app_error(self):
        import psutil
        from screen_time_windows import monitor
        class OneIteration:
            calls = 0
            def wait(self, _timeout):
                self.calls += 1
                return self.calls > 1
        with patch("screen_time_windows.foreground_pid", return_value=42), patch("screen_time_windows.psutil.Process", side_effect=psutil.NoSuchProcess(42)):
            monitor(self.store, OneIteration())
        self.assertEqual(self.store.app_errors, {})

    def test_dry_run_creates_no_files(self):
        target = Path(self.temp.name) / "fresh"
        result = subprocess.run([sys.executable, str(SCRIPTS / "screen_time_server.py"),
                                 "--data-dir", str(target), "--dry-run"], capture_output=True, check=True)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["writes"], ["state.json"])
        self.assertFalse(target.exists())

    def test_source_launcher_dry_run_preserves_selected_path(self):
        target = Path(self.temp.name) / 'source-data'
        result = subprocess.run([sys.executable, str(SCRIPTS / 'screen_time_start.py'),
                                 '--data-dir', str(target), '--dry-run'], capture_output=True, check=True)
        self.assertEqual(json.loads(result.stdout)['data_dir'], str(target.resolve()))
        self.assertFalse(target.exists())

    def test_web_is_default_and_boot_is_quiet(self):
        self.assertEqual(startup_view(), 'web')
        self.assertEqual(startup_view(background=True), 'background')
        self.assertEqual(startup_view(no_ui=True), 'background')
        self.assertEqual(startup_view(native_ui=True), 'native')
        self.assertEqual(startup_view(background=True, native_ui=True), 'background')


if __name__ == "__main__":
    unittest.main()
