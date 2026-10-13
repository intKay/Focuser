"""Portable rules only. Never import usage, pause state, bonus records or paths."""
from __future__ import annotations
import copy
from screen_time_core import validate_groups

FIELDS = {'id','name','mode','minutes','weekly_minutes','curfews','icon','enabled','color','domains','apps'}


def export_config(groups):
    cleaned = [{key:copy.deepcopy(value) for key,value in group.items() if key in FIELDS} for group in groups]
    return {'format':'focuser-config','version':1,'groups':validate_groups(cleaned)}


def import_config(config, native_apps):
    if (not isinstance(config,dict) or set(config)!={'format','version','groups'}
            or config.get('format')!='focuser-config' or type(config.get('version')) is not int or config['version']!=1):
        raise ValueError('配置文件格式或版本不支持')
    groups=config['groups']
    if not isinstance(groups,list):
        raise ValueError('配置文件格式或版本不支持')
    for group in groups:
        if not isinstance(group,dict) or set(group)-FIELDS:
            raise ValueError('配置不能包含用量、额外分钟或其他私人状态')
        for window in group.get('curfews') or []:
            if not isinstance(window,dict) or set(window)!={'start','end'}:
                raise ValueError('配置文件格式或版本不支持')
    normalized=validate_groups(groups)
    if not native_apps and any(group['enabled'] and group['apps'] for group in normalized):
        raise ValueError('配置含当前平台不支持的桌面 App 规则，请先在原平台通过验证调整规则')
    return normalized
