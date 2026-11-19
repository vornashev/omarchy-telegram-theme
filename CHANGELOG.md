# Changelog

Все заметные изменения проекта фиксируются в этом файле.

## [1.1.2] — 2026-11-19

### Исправлено
- **Превью вложений (`⋮` / `×`) и медиа-оверлеи**: вместо compile-time алиасов `roundedBg`/`roundedFg` (которые игнорируются в `.tdesktop-theme`) заданы реальные ключи `radialBg` (`#111111cc`) и `radialFg` (`#ffffff`). Также зафиксированы тёмные подложки и белые иконки для `stickerPanDelete*`, `historyForwardChoose*`, `msgDateImg*`, `historyIconFgInverted`, `historySendingInvertedIconFg`, `historyFileThumbIconFg*`, `historyFileThumbRadialFg*`, `videoPlayIcon*`, `youtubePlayIconFg`, `layerBg`, `photoCropPointFg` и `mediaviewFileExtFg`.
- **Аватары чатов**: `historyPeerUserpicFg` зафиксирован в `#ffffff` (инициалы больше не становятся чёрными при светлых/серых акцентах), градиенты `historyPeer*UserpicBg*` сохраняются без искажения, добавлен `historyPeerArchiveUserpicBg` (`#647280`) для читаемости на светлых темах.
- **Галочки верификации, чекбоксы и загрузка медиа**: исправлен контраст для `dialogsVerifiedIcon*`, `profileVerifiedCheck*`, `overviewCheck*`, `msgFileIn/OutBg*`, `historyFileIn/OutIconFg*`, `historyFileIn/OutRadialFg`.
- **Выделенные сообщения и активный чат**: исправлен контраст ссылок, моноширинного текста, дат, имён файлов, черновиков и статусов (`historyLink*Selected`, `msg*MonoFgSelected`, `msg*DateFgSelected`, `msg*ServiceFgSelected`, `historyFileName*Selected`, `historyOutIconFgSelected`, `dialogsDraftFgActive`, `dialogsSendingIconFgActive`, `dialogsOnlineBadgeFgActive`, `msgServiceBgSelected`).
- **Меню, звонки, трей и поля ввода**: исправлены `mainMenuCover*`, `mainMenuCloud*`, `titleButtonCloseFgOver`, `trayCounter*`, `call*`, `callBar*`, `inputBorderFg`, `filterInputBorderFg`, `placeholderFg*`, `checkboxFg`, `boxDividerFg`, `historyPinnedBg`, `historyUnreadBar*`, `searchedBar*`, `botKbColor`, `sideBarBadgeBg*`.
- **Тесты**: добавлены проверки контраста (в том числе поверх белого фото) для всех медиа-оверлеев, аватаров и UI-элементов, а также проверка отсутствия неконтролируемых ссылок на `windowFgActive`.

## [1.1.1] — 2026-10-28

- Попытка исправления иконок действий поверх миниатюр вложений (`roundedBg`/`roundedFg`).

## [1.1.0] — 2026-10-28

- Разделение оттенков фона переписки, списка чатов, боковой панели и панелей ввода.
- Усилен контраст пузырей сообщений, текста, ссылок и времени.

## [1.0.1] — 2026-10-28

- Исправлена читаемость уведомлений о пересылке (`toast*`) и всплывающих подсказок (`tooltip*`, `importantTooltip*`).

## [1.0.0] — 2026-10-28

- Первый релиз автоматического генератора тем Telegram Desktop для Omarchy с установщиком `setup.py`, хуком `theme-set.d` и тестами.
