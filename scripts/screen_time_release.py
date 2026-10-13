"""Allowlisted distribution. Excludes outputs, history, backups and machine state."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path

from screen_time_runtime import VERSION


def extension_files():
    source = Path(__file__).resolve().parents[1] / 'resources/screen_time/extension'
    if not source.is_dir():
        from importlib.resources import files
        source = files('focuser_assets').joinpath('extension')
    return source


def extension_entries(browser='chromium'):
    source = extension_files()
    entries = []
    def copy_tree(current, prefix=''):
        for entry in current.iterdir():
            if entry.is_dir():
                if entry.name == 'vendor':
                    copy_tree(entry, prefix + entry.name + '/')
            elif entry.name != 'manifest.json' and entry.name.endswith(('.js', '.html', '.css', '.txt', '.md')):
                entries.append((prefix + entry.name, entry.read_bytes()))
    copy_tree(source)
    manifest = json.loads(source.joinpath('manifest.json').read_text(encoding='utf-8'))
    if browser == 'firefox':
        manifest.pop('minimum_chrome_version', None)
        manifest['background'] = {'scripts': ['background.js'], 'type': 'module'}
        manifest['browser_specific_settings'] = {'gecko': {
            'id': 'focuser-local@focuser.local', 'strict_min_version': '128.0',
            'data_collection_permissions': {'required': ['none']}}}
    elif browser != 'chromium':
        raise ValueError('不支持的浏览器目标')
    entries.append(('manifest.json', (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')))
    return sorted(entries)


def extension_archive(browser='chromium'):
    buffer = io.BytesIO()
    write_zip(buffer, extension_entries(browser))
    return buffer.getvalue()


def build_extension(destination, browser='chromium'):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name, data in extension_entries(browser):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return destination


def source_files(root):
    root = Path(root)
    for name in ['README.md', 'LICENSE', 'pyproject.toml', 'CHANGELOG.md', 'SECURITY.md', 'CONTRIBUTING.md', '一键配置.cmd']:
        yield root / name
    for folder, suffixes in [('scripts', {'.py', '.ps1'}), ('tests', {'.py', '.cjs'}),
                             ('resources/screen_time', {'.py', '.js', '.ts', '.html', '.css', '.json', '.txt', '.md'}),
                             ('docs/release', {'.md'}), ('.github/workflows', {'.yml', '.yaml'})]:
        for path in sorted((root / folder).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and (path.suffix in suffixes or path.name == 'LICENSE'):
                yield path


def write_zip(path, entries):
    with zipfile.ZipFile(path, 'w' if hasattr(path, 'write') else 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries:
            info = zipfile.ZipInfo(name, (2026, 10, 7, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, data)


def build_release(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    built = []
    source_zip = output / f'focuser-local-{VERSION}-source.zip'
    write_zip(source_zip, [(str(p.relative_to(root)).replace('\\', '/'), p.read_bytes()) for p in source_files(root)])
    built.append(source_zip)
    for browser in ['chromium', 'firefox']:
        with tempfile.TemporaryDirectory(dir=output) as temp:
            ext = build_extension(Path(temp) / 'extension', browser)
            target = output / f'focuser-local-{VERSION}-{browser}.zip'
            write_zip(target, [(str(p.relative_to(ext)).replace('\\', '/'), p.read_bytes()) for p in sorted(ext.rglob('*')) if p.is_file()])
            built.append(target)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in built}
    (output / 'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name, digest in hashes.items()), encoding='utf-8')
    return hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--extension-only', choices=['chromium', 'firefox'])
    args = parser.parse_args()
    if args.extension_only:
        print(build_extension(args.output, args.extension_only))
    else:
        print(json.dumps(build_release(Path(__file__).resolve().parents[1], args.output), indent=2))


if __name__ == '__main__':
    main()
