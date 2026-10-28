#!/usr/bin/env python3
"""Install, configure, inspect, or remove Omarchy Telegram Theme. Python 3.11+."""
# SPDX-License-Identifier: GPL-3.0-or-later
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request

VERSION = '1.0.1'
REPO = 'vornashev/omarchy-telegram-theme'
# Verified when this standalone installer downloads release payloads.
HASHES = {'theme.py': 'bd2a3cdd77f5e6f474871963e77e578815263881d4a82bf399b6af009dca6843', 'assets/base-night.tdesktop-palette': '9f6e0cdf85cad2e9baa33885e7bb102d5f63f06039c920908d3fb29fc50cbd8d'}
HOME = Path.home()
CONFIG_HOME = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config'))
DATA_HOME = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share'))
STATE_HOME = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state'))
DATA = DATA_HOME / 'omarchy-telegram'
CONFIG = CONFIG_HOME / 'omarchy-telegram/config.json'
BIN = HOME / '.local/bin'
HOOK = CONFIG_HOME / 'omarchy/hooks/theme-set.d/telegram-theme'
MANIFEST = DATA / 'installation.json'
THEME = DATA / 'Omarchy.tdesktop-theme'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_config():
    return json.loads(CONFIG.read_text()) if CONFIG.exists() else {}


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, mode='w', delete=False) as f:
        json.dump(data, f, indent=2)
        f.write('\n')
        temp = Path(f.name)
    os.replace(temp, path)


def payload(name):
    local = Path(__file__).resolve().parent / name
    if local.is_file():
        return local.read_bytes()
    url = f'https://raw.githubusercontent.com/{REPO}/v{VERSION}/{name}'
    with urllib.request.urlopen(url, timeout=30) as response:
        content = response.read()
    if digest(content) != HASHES.get(name):
        raise ValueError(f'Checksum mismatch: {name}')
    return content


def generator():
    path = BIN / 'omarchy-telegram-theme'
    if not path.is_file():
        raise ValueError('Not installed. Run: python3 setup.py install')
    return path


def render(config=None):
    command = [sys.executable, str(generator())]
    if config is None:
        subprocess.run(command, check=True)
        return
    # Validate and render before replacing the persistent configuration.
    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp) / 'config.json'
        candidate.write_text(json.dumps(config))
        subprocess.run(command + ['--config', str(candidate)], check=True)
    atomic_json(CONFIG, config)


def install():
    theme = payload('theme.py')
    base = payload('assets/base-night.tdesktop-palette')
    # Preflight the palette and generator before touching existing integration.
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        (stage / 'assets').mkdir()
        (stage / 'theme.py').write_bytes(theme)
        (stage / 'assets/base-night.tdesktop-palette').write_bytes(base)
        subprocess.run([sys.executable, str(stage / 'theme.py'), '--output', str(stage / 'preview.tdesktop-theme')], check=True)
    files = {
        BIN / 'omarchy-telegram-theme': (theme, 0o755),
        DATA / 'base-night.tdesktop-palette': (base, 0o644),
        DATA / 'manage.py': (Path(__file__).read_bytes(), 0o755),
        BIN / 'omarchy-telegram': ((f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(DATA / "manage.py"))} "$@"\n').encode(), 0o755),
        HOOK: ((f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(BIN / "omarchy-telegram-theme"))}\n').encode(), 0o755),
    }
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {'files': {}, 'backups': {}}
    for path in files:
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise ValueError(f'Refusing to replace a symlink or directory: {path}')
        previous = manifest['files'].get(str(path))
        if previous and (not path.exists() or digest(path.read_bytes()) != previous):
            raise ValueError(f'Installed file changed locally; save your changes before reinstalling: {path}')
    DATA.mkdir(parents=True, exist_ok=True)
    for path, (content, mode) in files.items():
        key = str(path)
        if path.exists() and key not in manifest['files']:
            backup = DATA / 'backups' / str(len(manifest['backups']))
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, backup)
            manifest['backups'][key] = str(backup)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(mode)
        manifest['files'][key] = digest(content)
        # Record ownership incrementally so interrupted installs can be removed.
        atomic_json(MANIFEST, manifest)
    manifest['version'] = VERSION
    atomic_json(MANIFEST, manifest)
    if not CONFIG.exists():
        atomic_json(CONFIG, {'palette': 'auto', 'colors': {}})
    render()
    print(f'Installed v{VERSION}. Import this file ONCE in Telegram:\n{THEME}')
    print('Settings > Chat Settings > ⋮ > Create new theme > Import existing theme; Keep changes.')
    print('Turn Auto-night mode off. Future Omarchy theme changes apply automatically.')
    print(f'Management command: {BIN / "omarchy-telegram"}')


def configure(args):
    config = {'palette': 'auto', 'colors': {}} if args.reset else read_config()
    if args.palette is not None:
        config['palette'] = 'auto' if args.palette == 'auto' else str(Path(args.palette).expanduser().resolve())
    colors = config.setdefault('colors', {})
    for name in ('accent', 'background', 'foreground'):
        value = getattr(args, name)
        if value is not None:
            colors[name] = value
    render(config)
    print(f'Configuration saved: {CONFIG}')


def status():
    if not MANIFEST.exists():
        print('Not installed with setup.py. Legacy/manual integration may still exist.')
        return 1
    manifest = json.loads(MANIFEST.read_text())
    print(f'Omarchy Telegram Theme v{manifest.get("version", "unknown")}')
    ok = True
    for filename, expected in manifest['files'].items():
        path = Path(filename)
        good = path.is_file() and digest(path.read_bytes()) == expected
        print(f'{"OK" if good else "CHANGED/MISSING"}: {path}')
        ok &= good
    print(f'Theme: {THEME} ({"exists" if THEME.exists() else "missing"})')
    print(f'Configuration: {CONFIG}\n{json.dumps(read_config(), indent=2)}')
    print('Telegram must have this local file imported. Application selection is not inspected.')
    return 0 if ok and THEME.exists() else 1


def uninstall(purge=False):
    if not MANIFEST.exists():
        raise ValueError('No installation manifest; refusing to remove unowned files.')
    manifest = json.loads(MANIFEST.read_text())
    for filename, expected in manifest['files'].items():
        path = Path(filename)
        if path.is_symlink() or (path.exists() and (not path.is_file() or digest(path.read_bytes()) != expected)):
            raise ValueError(f'Locally modified file: {path}. Save it and restore the installed version before uninstalling.')
    for filename in manifest['files']:
        path = Path(filename)
        backup = manifest['backups'].get(filename)
        if backup:
            shutil.copy2(backup, path)
            Path(backup).unlink()
            print(f'Restored previous file: {path}')
        else:
            path.unlink(missing_ok=True)
    MANIFEST.unlink()
    if purge:
        CONFIG.unlink(missing_ok=True)
        THEME.unlink(missing_ok=True)
        (DATA / '.lock').unlink(missing_ok=True)
    for path in (DATA / 'backups', DATA, CONFIG.parent):
        try:
            path.rmdir()
        except OSError:
            pass
    print('Removed. Previously replaced files were restored, if present.')
    print('Select another theme in Telegram. Theme/config kept unless --purge was used.')


def main():
    if sys.version_info < (3, 11):
        raise ValueError('Python 3.11 or newer is required.')
    if os.geteuid() == 0:
        raise ValueError('Run as your desktop user, without sudo.')
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('install', help='Install or update; preserve configuration')
    commands.add_parser('refresh', help='Regenerate the theme now')
    commands.add_parser('status', help='Inspect files and configuration')
    config = commands.add_parser('configure', help='Apply settings and regenerate')
    config.add_argument('--reset', action='store_true')
    config.add_argument('--palette', help='auto, or a colors.toml path')
    for name in ('accent', 'background', 'foreground'):
        config.add_argument('--' + name, help='#RRGGBB override (quote the value)')
    remove = commands.add_parser('uninstall', help='Remove integration and restore backups')
    remove.add_argument('--purge', action='store_true', help='Also delete generated theme and configuration')
    args = parser.parse_args()
    if args.command == 'install':
        install()
    elif args.command == 'configure':
        configure(args)
    elif args.command == 'refresh':
        render()
    elif args.command == 'status':
        return status()
    elif args.command == 'uninstall':
        uninstall(args.purge)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
