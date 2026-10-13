from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from screen_time_challenge import relaxation
from screen_time_core import BudgetStore, DEFAULT_GROUPS, curfew_covers, validate_groups


class Clock:
    def __init__(self, when):
        self.wall = when.timestamp()
        self.mono = 1000.0

    def advance(self, seconds):
        self.wall += seconds
        self.mono += seconds


def group(**extra):
    base = copy.deepcopy(DEFAULT_GROUPS[1])
    base.update(extra)
    return base


class ScheduleTests(unittest.TestCase):
    def store(self, when, groups=None):
        root = SCRIPTS.parent / "outputs" / "screen_time" / "test-temp"
        root.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temp.cleanup)
        clock = self.clock = Clock(when)
        store = BudgetStore(Path(temp.name), lambda: clock.wall, lambda: clock.mono)
        if groups:
            store.configure(groups)
        return store

    @staticmethod
    def social(store):
        return next(g for g in store.snapshot()["groups"] if g["id"] == "social")

    def test_defaults_normalise_without_schedule(self):
        for item in validate_groups(copy.deepcopy(DEFAULT_GROUPS)):
            self.assertIsNone(item["weekly_minutes"])
            self.assertEqual(item["curfews"], [])

    def test_weekly_budget_applies_per_weekday(self):
        groups = [DEFAULT_GROUPS[0], group(weekly_minutes=[30, 31, 32, 33, 34, 60, 90])]
        tuesday = self.store(datetime(2026, 10, 6, 12, 0), groups)
        sunday = self.store(datetime(2026, 10, 11, 12, 0), groups)
        self.assertEqual(self.social(tuesday)["minutes_today"], 31)
        self.assertEqual(self.social(sunday)["minutes_today"], 90)

    def test_legacy_weekend_budget_expands_and_keeps_backup(self):
        root = SCRIPTS.parent / "outputs" / "screen_time" / "test-temp"
        root.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=root)
        self.addCleanup(temp.cleanup)
        import json
        old = [DEFAULT_GROUPS[0], group(weekend_minutes=60)]
        path = Path(temp.name) / "state.json"
        path.write_text(json.dumps({"version": 1, "groups": old, "history": {}, "paused": False, "bonus": {}}), encoding="utf-8")
        store = BudgetStore(Path(temp.name))
        item = self.social(store)
        self.assertEqual(item["weekly_minutes"], [30] * 5 + [60, 60])
        self.assertNotIn("weekend_minutes", item)
        self.assertTrue((Path(temp.name) / "state.pre-weekly.json").exists())

    def test_weekend_budget_applies_on_saturday_only(self):
        groups = [DEFAULT_GROUPS[0], group(weekly_minutes=[30] * 5 + [60, 60])]
        weekday = self.store(datetime(2026, 10, 9, 12, 0), groups)  # Friday
        weekend = self.store(datetime(2026, 10, 10, 12, 0), groups)  # Saturday
        self.assertEqual(self.social(weekday)["minutes_today"], 30)
        self.assertEqual(self.social(weekend)["minutes_today"], 60)
        self.assertEqual(self.social(weekend)["remaining_seconds"], 3600)

    def test_weekend_budget_caps_charging_and_zero_blocks(self):
        store = self.store(datetime(2026, 10, 10, 12, 0), [DEFAULT_GROUPS[0], group(weekly_minutes=[30] * 5 + [1, 1])])
        store.heartbeat("c", "social", True)
        for _ in range(100):
            self.clock.advance(1)
            store.heartbeat("c", "social", True)
        self.assertTrue(self.social(store)["blocked"])
        self.assertLessEqual(self.social(store)["used_seconds"], 60)
        free = self.store(datetime(2026, 10, 10, 12, 0), [DEFAULT_GROUPS[0], group(weekly_minutes=[30] * 5 + [0, 0])])
        self.assertTrue(self.social(free)["blocked"])

    def test_curfew_blocks_with_time_left_and_offers_no_bonus(self):
        shut = [DEFAULT_GROUPS[0], group(curfews=[{"start": "22:00", "end": "06:00"}])]
        night = self.store(datetime(2026, 10, 7, 23, 30), shut)
        item = self.social(night)
        self.assertTrue(item["blocked"] and item["curfew_active"])
        self.assertEqual(item["remaining_seconds"], 0)
        self.assertFalse(item["bonus_available"])
        with self.assertRaises(ValueError):
            night.claim_minute("social")
        early = self.store(datetime(2026, 10, 7, 5, 59), shut)
        self.assertTrue(self.social(early)["blocked"])
        day = self.store(datetime(2026, 10, 7, 12, 0), shut)
        self.assertFalse(self.social(day)["blocked"])

    def test_multiple_windows_and_legacy_single_window(self):
        windows = [{"start": "14:00", "end": "18:00"}, {"start": "08:00", "end": "12:00"}]
        groups = [DEFAULT_GROUPS[0], group(curfews=windows)]
        self.assertEqual(validate_groups(groups)[1]["curfews"][0]["start"], "08:00")  # sorted
        morning = self.store(datetime(2026, 10, 7, 9, 0), groups)
        noon = self.store(datetime(2026, 10, 7, 13, 0), groups)
        evening = self.store(datetime(2026, 10, 7, 15, 0), groups)
        self.assertTrue(self.social(morning)["curfew_active"])
        self.assertFalse(self.social(noon)["curfew_active"])
        self.assertEqual(self.social(noon)["curfew_starts_in"], 3600)
        self.assertTrue(self.social(evening)["curfew_active"])
        old = validate_groups([DEFAULT_GROUPS[0], group(curfew={"start": "22:00", "end": "06:00"})])
        self.assertEqual(old[1]["curfews"], [{"start": "22:00", "end": "06:00"}])
        self.assertNotIn("curfew", old[1])

    def test_curfew_countdown(self):
        store = self.store(datetime(2026, 10, 7, 21, 55), [DEFAULT_GROUPS[0], group(curfews=[{"start": "22:00", "end": "06:00"}])])
        self.assertEqual(self.social(store)["curfew_starts_in"], 300)

    def test_curfew_covers_wraps_midnight(self):
        wrap = {"start": "22:00", "end": "06:00"}
        self.assertTrue(curfew_covers(wrap, 23 * 60) and curfew_covers(wrap, 0) and curfew_covers(wrap, 359))
        self.assertFalse(curfew_covers(wrap, 360) or curfew_covers(wrap, 12 * 60))

    def test_validation_rejects_bad_schedule(self):
        for extra in ({"weekly_minutes": [30] * 6}, {"weekly_minutes": [30] * 6 + [-1]}, {"weekly_minutes": [30] * 6 + [1441]},
                      {"weekly_minutes": [30] * 6 + [True]}, {"weekly_minutes": "30"}, {"weekend_minutes": 1441},
                      {"curfews": [{"start": "25:00", "end": "06:00"}]}, {"curfews": [{"start": "22:00", "end": "22:00"}]},
                      {"curfews": "22:00-06:00"}, {"curfews": [{"start": "22:00"}]}, {"curfews": [{"start": f"0{i}:00", "end": f"0{i}:30"} for i in range(7)]}):
            with self.assertRaises(ValueError, msg=str(extra)):
                validate_groups([DEFAULT_GROUPS[0], group(**extra)])

    def test_block_mode_drops_schedule(self):
        item = validate_groups([group(mode="block", minutes=0, weekly_minutes=[30] * 7, curfews=[{"start": "22:00", "end": "23:00"}])])[0]
        self.assertIsNone(item["weekly_minutes"])
        self.assertEqual(item["curfews"], [])

    def test_relaxation_rules(self):
        def norm(*items):
            return validate_groups([DEFAULT_GROUPS[0], *items])
        plain = norm(group())
        shut = {"start": "22:00", "end": "06:00"}
        # tightening needs no challenge
        self.assertFalse(relaxation(plain, norm(group(weekly_minutes=[30] * 5 + [10, 10]))))
        self.assertFalse(relaxation(plain, norm(group(curfew=shut))))
        self.assertFalse(relaxation(norm(group(curfew=shut)), norm(group(curfews=[{"start": "21:00", "end": "07:00"}]))))
        self.assertTrue(relaxation(plain, norm(group(weekly_minutes=[31, 30, 30, 30, 30, 30, 30]))))
        self.assertFalse(relaxation(norm(group(weekly_minutes=[60] * 7)), norm(group(minutes=30))))
        # more weekend time, or a shorter/removed curfew, is a relaxation
        self.assertTrue(relaxation(plain, norm(group(weekly_minutes=[30] * 5 + [45, 45]))))
        self.assertTrue(relaxation(norm(group(weekly_minutes=[30] * 5 + [10, 10])), norm(group(weekly_minutes=[30] * 5 + [20, 20]))))
        self.assertTrue(relaxation(norm(group(curfew=shut)), norm(group())))
        self.assertTrue(relaxation(norm(group(curfew=shut)), norm(group(curfews=[{"start": "23:00", "end": "06:00"}]))))
        self.assertTrue(relaxation(norm(group(curfew=shut)), norm(group(curfews=[{"start": "22:00", "end": "05:00"}]))))
        two = [{"start": "08:00", "end": "12:00"}, {"start": "14:00", "end": "18:00"}]
        self.assertFalse(relaxation(norm(group(curfews=two[:1])), norm(group(curfews=two))))
        self.assertTrue(relaxation(norm(group(curfews=two)), norm(group(curfews=two[:1]))))
        # legacy states without the new keys compare cleanly
        legacy = [copy.deepcopy(g) for g in DEFAULT_GROUPS]
        self.assertFalse(relaxation(legacy, norm(group())))


if __name__ == "__main__":
    unittest.main()
