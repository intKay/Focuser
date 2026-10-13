import re
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from screen_time_core import DEFAULT_GROUPS, ICONS, validate_groups

WEB = Path(__file__).resolve().parents[1] / "resources" / "screen_time" / "web"
EXT = Path(__file__).resolve().parents[1] / "resources" / "screen_time" / "extension"


class WebAssetTests(unittest.TestCase):
    def test_every_script_id_exists_in_page(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        script = (WEB / "app.js").read_text(encoding="utf-8")
        ids = set(re.findall(r'id="([^"]+)"', html))
        used = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", script))
        self.assertEqual(used - ids, set())

    def test_nav_views_have_sections(self):
        html = (WEB / "index.html").read_text(encoding="utf-8")
        for view in re.findall(r'data-view="([a-z]+)"', html):
            self.assertIn(f'<section id="{view}"', html)

    def test_no_unverified_bypass_controls(self):
        # 忽略限额 / 稍后提醒 would relax limits without the integral challenge.
        for path in (WEB / "index.html", WEB / "app.js", EXT / "blocked.html", EXT / "blocked.js"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("忽略限额", text, path.name)
            self.assertNotIn("分钟后提醒", text, path.name)

    def test_blocked_page_keeps_bonus_and_panel_hooks(self):
        html = (EXT / "blocked.html").read_text(encoding="utf-8")
        for hook in ('id="reason"', 'id="bonus"', 'id="panel"', 'id="ok"'):
            self.assertIn(hook, html)

    def test_icon_ids_match_between_page_and_server(self):
        script = (WEB / "app.js").read_text(encoding="utf-8")
        block = script[script.index("const GLYPHS={"):script.index("const GUESS=")]
        self.assertEqual(set(re.findall(r"^ (\w+):'", block, re.M)), set(ICONS))

    def test_icon_validation(self):
        groups = copy.deepcopy(DEFAULT_GROUPS)
        self.assertIsNone(validate_groups(groups)[0]["icon"])
        groups[0]["icon"] = "video"
        self.assertEqual(validate_groups(groups)[0]["icon"], "video")
        groups[0]["icon"] = "<script>"
        with self.assertRaises(ValueError):
            validate_groups(groups)


if __name__ == "__main__":
    unittest.main()
