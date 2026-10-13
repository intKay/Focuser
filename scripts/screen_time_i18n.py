"""Native UI language, separate from budget state. FOCUSER_LANG overrides OS locale."""
from __future__ import annotations

import json
import locale
import os
import re
from functools import lru_cache


def language():
    chosen = os.environ.get('FOCUSER_LANG', 'auto')
    if chosen in ('en', 'zh'):
        return chosen
    return 'zh' if (locale.getlocale()[0] or '').lower().startswith(('zh', 'chinese')) else 'en'


@lru_cache(maxsize=1)
def catalog():
    from screen_time_release import extension_files
    return json.loads(extension_files().joinpath('i18n.json').read_text(encoding='utf-8'))


def t(value):
    if language() != 'en':
        return value
    data = catalog()
    if value in data['messages']:
        return data['messages'][value]
    for pattern, replacement in data['patterns']:
        if re.search(pattern, value):
            return re.sub(pattern, replacement, value)
    return value
