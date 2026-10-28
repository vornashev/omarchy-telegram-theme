#!/usr/bin/env python3
"""Generate a watched Telegram theme from the current Omarchy palette.

The reference palette is from telegramdesktop/tdesktop (GPL-3.0):
Telegram/Resources/night.tdesktop-theme, colors.tdesktop-theme.
Write in place: Telegram watches the inode with QFileSystemWatcher.
"""
import argparse
import colorsys
import fcntl
import os
from pathlib import Path
import re
import struct
import tomllib
import zipfile
import zlib
import io
import json
import sys

HOME = Path.home()
STATE = Path(os.environ.get('XDG_STATE_HOME', HOME / '.local/state'))
DATA = Path(os.environ.get('XDG_DATA_HOME', HOME / '.local/share')) / 'omarchy-telegram'
CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', HOME / '.config')) / 'omarchy-telegram/config.json'
BASE = Path(__file__).resolve().parent / 'assets/base-night.tdesktop-palette'
if not BASE.is_file():
    BASE = DATA / 'base-night.tdesktop-palette'


def rgb(color):
    return tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))


def blend(a, b, t):
    return '#' + ''.join(f'{round((x * (1 - t) + y * t) * 255):02x}' for x, y in zip(rgb(a), rgb(b)))


def luminance(color):
    c = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb(color)]
    return sum(x * w for x, w in zip(c, (.2126, .7152, .0722)))


def contrast(a, b):
    x, y = sorted((luminance(a), luminance(b)))
    return (y + .05) / (x + .05)


def readable(color, background, target=4.5):
    endpoint = max(('#ffffff', '#000000'), key=lambda c: contrast(c, background))
    for i in range(101):
        result = blend(color, endpoint, i / 100)
        if contrast(result, background) >= target:
            return result
    return endpoint


def palette(source, overrides=None):
    p = tomllib.loads(source.read_text())
    p.update(overrides or {})
    bg, fg = p['background'], p['foreground']
    accent = p.get('accent', p.get('color4', fg))
    for c in (bg, fg, accent):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', c):
            raise ValueError(f'Invalid palette color: {c!r}')
    fg = readable(fg, bg)
    muted = readable(blend(bg, fg, .6), bg)
    panel = blend(bg, fg, .045)
    over = blend(bg, fg, .09)
    out = blend(bg, accent, .22)
    selected = blend(bg, accent, .38)
    selected_fg = readable(fg, selected)
    button_fg = max(('#ffffff', '#000000'), key=lambda c: contrast(c, accent))
    # Telegram shares one text color between normal and muted unread badges.
    # Give both backgrounds enough contrast against that shared foreground.
    badge_bg = readable(accent, fg)
    badge_muted_bg = readable(blend(bg, fg, .2), fg)
    link = readable(accent, bg)
    base = BASE.read_text()
    result = {}
    for name, value in re.findall(r'^(\w+):\s*(#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?|\w+)\s*;', base, re.M):
        if not value.startswith('#'):
            result[name] = value
            continue
        h, saturation, light = colorsys.rgb_to_hsv(*rgb(value))
        alpha = value[7:]
        if light < .3:
            color = blend(bg, fg, light * .3)
        elif saturation < .18:
            color = blend(bg, fg, min(1, max(.12, (light - .15) / .8)))
        elif .48 < h < .72:
            color = blend(bg, accent, min(1, max(.15, light)))
            if 'Fg' in name or 'Icon' in name:
                color = readable(color, bg, 3)
        else:
            # Keep semantic colors for errors, calls, charts, and avatar groups.
            color = value[:7]
        result[name] = color + alpha
    overrides = {
        'windowBg': bg, 'windowFg': fg, 'windowBgOver': over,
        'windowFgOver': fg, 'windowBgRipple': selected,
        'windowBoldFg': fg, 'windowBoldFgOver': fg,
        'windowSubTextFg': muted, 'windowSubTextFgOver': muted,
        'windowBgActive': accent, 'windowFgActive': button_fg,
        'windowActiveTextFg': link, 'windowShadowFgFallback': panel,
        'activeButtonBg': accent, 'activeButtonBgOver': blend(accent, fg, .12),
        'activeButtonBgRipple': blend(accent, fg, .2),
        'activeButtonFg': button_fg, 'activeButtonFgOver': button_fg,
        'activeButtonSecondaryFg': button_fg, 'activeButtonSecondaryFgOver': button_fg,
        'activeLineFg': accent, 'lightButtonBg': bg, 'lightButtonBgOver': over,
        'lightButtonBgRipple': selected, 'lightButtonFg': link, 'lightButtonFgOver': link,
        'menuBg': bg, 'menuBgOver': over, 'menuBgRipple': selected,
        'menuIconFg': muted, 'menuIconFgOver': fg,
        'boxBg': bg, 'boxTextFg': fg, 'boxTitleFg': fg, 'boxDividerBg': panel,
        'scrollBg': over, 'scrollBarBg': muted, 'scrollBarBgOver': accent,
        'dialogsBg': bg, 'dialogsBgOver': over, 'dialogsBgActive': selected,
        'dialogsNameFg': fg, 'dialogsNameFgOver': fg, 'dialogsNameFgActive': selected_fg,
        'dialogsTextFg': muted, 'dialogsTextFgOver': muted, 'dialogsTextFgActive': selected_fg,
        'dialogsDateFg': muted, 'dialogsDateFgOver': muted, 'dialogsDateFgActive': selected_fg,
        'dialogsTextFgService': link, 'dialogsTextFgServiceOver': link,
        'dialogsTextFgServiceActive': selected_fg,
        'dialogsUnreadBg': badge_bg, 'dialogsUnreadFg': fg,
        'dialogsUnreadBgMuted': badge_muted_bg,
        'dialogsUnreadBgOver': badge_bg, 'dialogsUnreadBgMutedOver': badge_muted_bg,
        'dialogsUnreadFgOver': fg, 'dialogsUnreadFgActive': fg,
        'dialogsUnreadBgActive': badge_bg, 'dialogsUnreadBgMutedActive': badge_muted_bg,
        'historyBg': bg, 'historyTextInFg': fg, 'historyTextOutFg': readable(fg, out),
        'historyTextInFgSelected': selected_fg, 'historyTextOutFgSelected': selected_fg,
        'historyLinkInFg': link, 'historyLinkOutFg': readable(accent, out),
        'msgInBg': panel, 'msgOutBg': out,
        'msgInBgSelected': selected, 'msgOutBgSelected': selected,
        'msgInServiceFg': link, 'msgOutServiceFg': readable(accent, out),
        'msgInDateFg': readable(muted, panel), 'msgOutDateFg': readable(muted, out),
        'msgServiceBg': over, 'msgServiceFg': fg,
        'msgInMonoFg': fg, 'msgOutMonoFg': readable(fg, out),
        'historyComposeAreaBg': bg, 'historyComposeAreaFg': fg,
        'historyComposeAreaFgService': muted, 'historyComposeIconFg': muted,
        'historyComposeIconFgOver': link, 'historySendIconFg': accent,
        'topBarBg': bg, 'sideBarBg': panel, 'sideBarBgActive': selected,
        'sideBarBgRipple': over, 'sideBarTextFg': muted,
        'sideBarTextFgActive': link, 'sideBarIconFg': muted,
        'sideBarIconFgActive': link, 'sideBarBadgeBg': badge_bg,
        'sideBarBadgeBgMuted': badge_muted_bg, 'sideBarBadgeFg': fg,
        'filterInputActiveBg': over, 'filterInputInactiveBg': panel,
        'filterInputFg': fg, 'filterInputPlaceholderFg': muted,
        'titleBg': panel, 'titleBgActive': bg,
        'emojiPanBg': bg, 'emojiPanHeaderBg': bg, 'emojiPanCategories': panel,
        'notificationBg': bg, 'botKbBg': over, 'botKbDownBg': selected,
        # Media overlays stay dark even when the theme uses dark button text.
        # Do not inherit windowFgActive here: it may legitimately be black.
        'mediaviewBg': '#111111f2', 'mediaviewVideoBg': '#000000',
        'mediaviewCaptionBg': '#111111ee', 'mediaviewCaptionFg': '#ffffff',
        'mediaviewTextLinkFg': readable(accent, '#222222'),
        'mediaviewControlBg': '#000000b3', 'mediaviewControlFg': '#ffffff',
        'mediaviewMenuBg': '#202020', 'mediaviewMenuBgOver': '#353535',
        'mediaviewMenuBgRipple': '#454545', 'mediaviewMenuFg': '#ffffff',
        'mediaviewSaveMsgBg': '#202020', 'mediaviewSaveMsgFg': '#ffffff',
        'mediaviewPlaybackActive': '#dddddd', 'mediaviewPlaybackActiveOver': '#ffffff',
        'mediaviewPlaybackInactive': '#555555', 'mediaviewPlaybackInactiveOver': '#777777',
        'mediaviewPlaybackProgressFg': '#ffffff',
        'mediaviewPlaybackIconFg': '#dddddd', 'mediaviewPlaybackIconFgOver': '#ffffff',
    }
    # Forward compatibility: unknown entries are accepted by Telegram.
    result.update(overrides)
    return bg, result


def png(color):
    def chunk(kind, content):
        return struct.pack('!I', len(content)) + kind + content + struct.pack('!I', zlib.crc32(kind + content))
    pixel = bytes(round(c * 255) for c in rgb(color))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 32, 32, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + pixel * 32) * 32)) + chunk(b'IEND', b''))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--palette', type=Path, help='Override the configured palette for this run')
    parser.add_argument('--config', type=Path, default=CONFIG)
    parser.add_argument('--output', type=Path, default=DATA / 'Omarchy.tdesktop-theme')
    args = parser.parse_args()
    config = json.loads(args.config.read_text()) if args.config.exists() else {}
    source = args.palette
    if source is None and config.get('palette', 'auto') != 'auto':
        source = Path(config['palette']).expanduser()
    if source is None:
        candidates = [STATE / 'omarchy/current/theme/colors.toml',
                      HOME / '.config/omarchy/current/theme/colors.toml']
        source = next((p for p in candidates if p.is_file()), candidates[0])
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / '.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        bg, colors = palette(source, config.get('colors', {}))
        content = '// Generated by omarchy-telegram-theme\n' + ''.join(f'{k}: {v};\n' for k, v in colors.items())
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in [('colors.tdesktop-theme', content.encode()), ('background.png', png(bg))]:
                entry = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(entry, data)
        data = buf.getvalue()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.exists() and args.output.read_bytes() == data:
            return
        # Keep the inode so Qt continues watching after every update.
        with args.output.open('wb') as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        print(f'Telegram theme updated: {args.output}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError) as error:
        print(f'Theme generation failed: {error}', file=sys.stderr)
        sys.exit(1)
