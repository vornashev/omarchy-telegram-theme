import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile
import io
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('theme', ROOT / 'theme.py')
theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(theme)


class ThemeTests(unittest.TestCase):
    def test_light_and_dark_contrast(self):
        for bg, fg, accent in [('#2e3440', '#d8dee9', '#81a1c1'), ('#eff1f5', '#4c4f69', '#1e66f5'), ('#101315', '#cacccc', '#798186'), ('#000000', '#ffffff', '#a0a0a0'), ('#ffffff', '#202020', '#2266cc'), ('#1e1e2e', '#cdd6f4', '#89b4fa')]:
            with self.subTest(bg=bg), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'colors.toml'
                path.write_text(f'background="{bg}"\nforeground="{fg}"\naccent="{accent}"\n')
                wallpaper, colors = theme.palette(path)
                def resolve(key, seen=()):
                    self.assertNotIn(key, seen)
                    value = colors[key]
                    return value if value.startswith('#') else resolve(value, (*seen, key))
                for key in colors:
                    self.assertRegex(resolve(key), r'^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$')
                surfaces = ('historyBg', 'dialogsBg', 'sideBarBg', 'topBarBg', 'msgInBg', 'msgOutBg')
                self.assertEqual(len({resolve(k) for k in surfaces}), len(surfaces))
                self.assertEqual(wallpaper, resolve('historyBg'))
                self.assertGreaterEqual(theme.contrast(resolve('historyBg'), resolve('msgInBg')), 1.15)
                for foreground, background in [('historyTextInFg', 'msgInBg'), ('historyTextOutFg', 'msgOutBg'), ('historyLinkInFg', 'msgInBg'), ('historyLinkOutFg', 'msgOutBg'), ('msgInDateFg', 'msgInBg'), ('msgOutDateFg', 'msgOutBg'), ('dialogsTextFg', 'dialogsBg'), ('dialogsTextFgOver', 'dialogsBgOver'), ('sideBarTextFg', 'sideBarBg'), ('historyComposeAreaFg', 'historyComposeAreaBg')]:
                    self.assertGreaterEqual(theme.contrast(resolve(foreground), resolve(background)), 4.5, foreground)
                for state in ('', 'Over', 'Active'):
                    for muted in ('', 'Muted'):
                        self.assertGreaterEqual(theme.contrast(resolve('dialogsUnreadFg' + state), resolve('dialogsUnreadBg' + muted + state)), 4.5)
                for foreground, background in [('mediaviewCaptionFg', 'mediaviewCaptionBg'), ('mediaviewControlFg', 'mediaviewControlBg')]:
                    value = resolve(background)
                    opacity = int(value[7:], 16) / 255
                    composite = theme.blend('#ffffff', value[:7], opacity)
                    self.assertGreaterEqual(theme.contrast(resolve(foreground), composite), 4.5)
                for foreground, background in [('toastFg', 'toastBg'), ('tooltipFg', 'tooltipBg'), ('importantTooltipFg', 'importantTooltipBg'), ('importantTooltipFgLink', 'importantTooltipBg')]:
                    value = resolve(background)
                    opacity = int(value[7:], 16) / 255 if len(value) == 9 else 1
                    composite = theme.blend('#ffffff', value[:7], opacity)
                    self.assertGreaterEqual(theme.contrast(resolve(foreground), composite), 4.5, foreground)


class BootstrapTests(unittest.TestCase):
    def test_download_checksums(self):
        spec = importlib.util.spec_from_file_location('installer', ROOT / 'setup.py')
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(installer, '__file__', str(Path(tmp) / 'setup.py')):
            for name in installer.HASHES:
                data = (ROOT / name).read_bytes()
                with mock.patch.object(installer.urllib.request, 'urlopen', return_value=io.BytesIO(data)):
                    self.assertEqual(installer.payload(name), data)
                with mock.patch.object(installer.urllib.request, 'urlopen', return_value=io.BytesIO(b'corrupt')):
                    with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
                        installer.payload(name)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='omarchy telegram ')
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = dict(os.environ, HOME=str(self.home), XDG_CONFIG_HOME=str(self.home / 'config space'), XDG_DATA_HOME=str(self.home / 'data space'), XDG_STATE_HOME=str(self.home / 'state space'))
        self.data = Path(self.env['XDG_DATA_HOME']) / 'omarchy-telegram'
        self.config = Path(self.env['XDG_CONFIG_HOME']) / 'omarchy-telegram/config.json'
        self.hook = Path(self.env['XDG_CONFIG_HOME']) / 'omarchy/hooks/theme-set.d/telegram-theme'
        self.output = self.data / 'Omarchy.tdesktop-theme'
        palette = Path(self.env['XDG_STATE_HOME']) / 'omarchy/current/theme/colors.toml'
        palette.parent.mkdir(parents=True)
        palette.write_text('background="#2e3440"\nforeground="#d8dee9"\naccent="#81a1c1"\n')

    def run_setup(self, *args, success=True, installed=False):
        script = self.data / 'manage.py' if installed else ROOT / 'setup.py'
        result = subprocess.run([sys.executable, str(script), *args], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_install_configure_hook_idempotence_uninstall(self):
        self.run_setup('install')
        original_inode = self.output.stat().st_ino
        self.run_setup('status', installed=True)
        subprocess.run([str(self.home / '.local/bin/omarchy-telegram'), 'status'], env=self.env, check=True, capture_output=True)
        before = self.output.stat().st_mtime_ns
        subprocess.run([str(self.hook)], env=self.env, check=True, capture_output=True)
        self.assertEqual(self.output.stat().st_mtime_ns, before)
        self.run_setup('configure', '--accent', '#a3be8c', installed=True)
        self.assertEqual(json.loads(self.config.read_text())['colors']['accent'], '#a3be8c')
        self.assertEqual(self.output.stat().st_ino, original_inode)
        with zipfile.ZipFile(self.output) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(set(archive.namelist()), {'colors.tdesktop-theme', 'background.png'})
        before = self.output.read_bytes()
        config_before = self.config.read_bytes()
        self.run_setup('configure', '--accent', 'invalid', success=False)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(self.config.read_bytes(), config_before)
        self.run_setup('install')
        self.assertEqual(self.output.read_bytes(), before)
        self.run_setup('configure', '--reset')
        self.assertEqual(json.loads(self.config.read_text()), {'palette': 'auto', 'colors': {}})
        self.run_setup('uninstall', '--purge', installed=True)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.hook.exists())
        self.assertFalse(self.config.exists())

    def test_restore_previous_hook_and_keep_theme(self):
        self.hook.parent.mkdir(parents=True)
        self.hook.write_text('#!/bin/sh\necho previous\n')
        self.hook.chmod(0o700)
        self.run_setup('install')
        self.run_setup('install')
        self.run_setup('uninstall', installed=True)
        self.assertEqual(self.hook.read_text(), '#!/bin/sh\necho previous\n')
        self.assertEqual(self.hook.stat().st_mode & 0o777, 0o700)
        self.assertTrue(self.output.exists())
        self.assertTrue(self.config.exists())

    def test_modified_file_prevents_removal(self):
        self.run_setup('install')
        original = self.hook.read_bytes()
        self.hook.write_text('# custom hook\n')
        self.run_setup('uninstall', success=False)
        self.assertTrue((self.data / 'installation.json').exists())
        self.hook.write_bytes(original)
        self.run_setup('uninstall', '--purge')

    def test_preflight_missing_palette(self):
        palette = Path(self.env['XDG_STATE_HOME']) / 'omarchy/current/theme/colors.toml'
        palette.unlink()
        self.run_setup('install', success=False)
        self.assertFalse(self.hook.exists())
        self.assertFalse((self.home / '.local/bin/omarchy-telegram-theme').exists())


if __name__ == '__main__':
    unittest.main()
