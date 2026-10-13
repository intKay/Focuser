import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from screen_time_core import DEFAULT_GROUPS
from screen_time_startup import render
from setup_fedora import validate_data


class FedoraTests(unittest.TestCase):
    def test_migration_validation_preserves_state(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            groups = copy.deepcopy(DEFAULT_GROUPS)
            for group in groups:
                group['apps'] = []
            original = json.dumps({'groups': groups, 'history': {'2026-10-13': {'social': 1800}},
                                   'bonus': {'2026-10-13': 'social'}, 'paused': False}).encode()
            state = data / 'state.json'
            state.write_bytes(original)
            validate_data(data)
            self.assertEqual(state.read_bytes(), original)
            with self.assertRaises(ValueError):
                validate_data(data, new_install=True)

    def test_missing_or_incompatible_data_refused_without_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            with self.assertRaises(ValueError):
                validate_data(data)
            validate_data(data, new_install=True)
            self.assertEqual(list(data.iterdir()), [])
            state = data / 'state.json'
            original = json.dumps({'groups': DEFAULT_GROUPS}).encode()
            state.write_bytes(original)
            with self.assertRaises(ValueError):
                validate_data(data)
            self.assertEqual(state.read_bytes(), original)

    def test_systemd_paths_remain_literal_and_data_is_private(self):
        _, unit = render('linux', ['/home/a $USER/100%/python', '--data-dir', '/data/with space'])
        self.assertIn('"/home/a $$USER/100%%/python"', unit)
        self.assertIn('"/data/with space"', unit)
        self.assertIn('UMask=0077', unit)
        self.assertNotIn('--no-apps', unit)
