import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from screen_time_i18n import t, language
from screen_time_setup import main as setup, validate_install


class LanguageAndSetupTests(unittest.TestCase):
    def test_windows_and_posix_chinese_locale_names(self):
        with patch.dict(os.environ, {'FOCUSER_LANG':'auto'}):
            for name in ['zh_CN', 'Chinese (Simplified)_China']:
                with patch('screen_time_i18n.locale.getlocale', return_value=(name, 'utf-8')):
                    self.assertEqual(language(), 'zh')

    def test_native_languages_and_dynamic_units(self):
        with patch.dict(os.environ, {'FOCUSER_LANG':'en'}):
            self.assertEqual(t('暂停限制'), 'Pause limits')
            self.assertEqual(t('120秒'), '120 s')
            self.assertEqual(t('2 个网站 · 3 个桌面 App'), '2 websites · 3 apps')
            self.assertIn('80 to 4000 characters', t('请填写80到4000字的推导过程'))
            self.assertEqual(t('A user category'), 'A user category')
        with patch.dict(os.environ, {'FOCUSER_LANG':'zh'}):
            self.assertEqual(t('暂停限制'), '暂停限制')

    def test_setup_plan_and_generation_never_create_usage(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder); data=base/'data'; output=base/'startup'
            args=['--new-install','--data-dir',str(data),'--output-dir',str(output)]
            setup(args+['--plan'])
            self.assertFalse(output.exists()); self.assertFalse(data.exists())
            setup(args)
            self.assertFalse(data.exists())
            self.assertTrue((output/'browser-extension/i18n.json').is_file())
            self.assertTrue((output/'browser-extension/manifest.json').is_file())

    def test_existing_native_rules_and_new_install_reset_refused(self):
        from screen_time_core import DEFAULT_GROUPS
        with tempfile.TemporaryDirectory() as folder:
            data=Path(folder); original=json.dumps({'groups':DEFAULT_GROUPS,'history':{},'bonus':{},'paused':False}).encode()
            (data/'state.json').write_bytes(original)
            with self.assertRaises(ValueError):validate_install(data,True,True)
            with self.assertRaises(ValueError):validate_install(data,False,False)
            self.assertEqual((data/'state.json').read_bytes(),original)

    def test_catalog_contains_all_visible_literal_translation_calls(self):
        import re
        messages=json.loads((ROOT/'resources/screen_time/extension/i18n.json').read_text(encoding='utf-8'))['messages']
        for file in [ROOT/'resources/screen_time/web/app.js',*(ROOT/'resources/screen_time/extension').glob('*.js')]:
            for text in re.findall(r"\bt\('([^'\n]*)'\)",file.read_text(encoding='utf-8')):
                if re.search(r'[\u3400-\u9fff]',text):self.assertIn(text,messages,(file.name,text))
