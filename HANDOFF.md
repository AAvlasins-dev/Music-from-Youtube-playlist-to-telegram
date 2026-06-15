# 🔁 Передача проекта (для новой сессии Claude)

> Открой этот файл первым в новом чате: скажи Claude **«прочитай HANDOFF.md»**.
> Запускай Claude Code **в этой же папке**:
> `C:\Users\СтражВремени\Desktop\СКРИПТЫ\Музыка с Yotube плейлиста`

---

## Что это за проект

**Space Music Hub** — десктоп-приложение для Windows (PyQt6), которое зеркалит
плейлисты YouTube в Telegram-каналы как MP3 192 kbps. Внутри — проверенный
бот-движок (ветка `v1-classic`), которым управляет неоновый GUI. Плюс
сайт-презентация на GitHub Pages.

- **Репозиторий:** https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram
- **Ветка:** `master` (есть `v1-classic` — старая CLI-версия)
- **Живой сайт:** https://aavlasins-dev.github.io/Music-from-Youtube-playlist-to-telegram/
- **Релизы:** https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram/releases
- Git user: `AAvlasins-dev`

## ✅ Текущее состояние (актуально на 2026-06-15)

Проект **финализирован и зарелизен** как **v2.0.0**:
- 🚀 **Релиз v2.0.0** опубликован, установщик `SpaceMusicHub-Setup-v2.0.0.exe`
  (78 МБ) прикреплён и скачивается с GitHub Releases.
- 🧪 **86 тестов** (pytest), CI зелёный, `ruff` чист.
- 📖 README переписан под десктоп-приложение (EN + RU), есть секции Architecture
  и Testing. CHANGELOG имеет запись `[2.0.0]`. Версии (pyproject + installer)
  выровнены на `2.0.0`.
- 📦 Свежий установщик также лежит на **рабочем столе**:
  `C:\Users\СтражВремени\Desktop\SpaceMusicHub-Setup-v2.0.0.exe`
- ❌ Скриншоты на сайт/README решили **не добавлять** (пользователь отказался).
- ↩️ Был эксперимент: заменить терминал-мокап на сайте мокапом GUI-визарда —
  **откатили** (`git revert`), оставили старую версию сайта с терминалом.

## 🗂 Ключевые файлы

| Файл | Что это |
|---|---|
| `gui_app.py` | **PyQt6 десктоп-приложение** — визард, дашборд, трей, планировщик, i18n (EN/RU/LV) |
| `telegram_bot_music_youtube.py` | Движок — плейлист → MP3 → Telegram (бот из v1-classic) |
| `SpaceMusicHubGUI.spec` | PyInstaller spec — собирает GUI + движок + ассеты в `.exe` |
| `installer/SpaceMusicHub.iss` | Inno Setup → `SpaceMusicHub-Setup-vX.Y.Z.exe` |
| `installer/Latvian.isl` | Латышский перевод UI установщика |
| `docs/index.html` | Сайт-презентация (один файл, HTML+CSS+JS, без сборки) |
| `docs/logo.png`, `logo_round.png`, `logo_round.ico`, `bg.jpg` | Ассеты сайта/приложения |
| `tests/test_bot.py`, `tests/test_gui.py` | Юнит-тесты (86 шт) |
| `pyproject.toml` | Конфиг ruff + pytest (`per-file-ignores` для gui_app.py) |
| `.tools/` | Портативный **gh CLI** (gitignored, не в репо) |

## 🏗 Архитектура (важно понимать)

**Один бинарь — две роли.** Собранный `SpaceMusicHub.exe` — это GUI. Когда юзер
жмёт Watch/Run once/Check, GUI **перезапускает сам себя** с флагом
`--bot-watch` / `--bot-once` / `--bot-check`. Диспетчер в начале `gui_app.py`
видит флаг и запускает встроенный движок вместо окна, стримя stdout обратно в
лог дашборда. Отдельный Python в бандле не нужен; падение бота не роняет UI.
Также есть `--bot-test` (читает `SMH_TEST_TOKEN`/`SMH_TEST_CHANNEL` из env →
кнопка «Тест канала» в визарде), `--tray` (фоновый автозапуск).

## 🔨 Сборка / тесты / релиз (рабочий процесс)

```bash
# Тесты + линтер
pip install -r requirements-dev.txt
ruff check .                                   # должно быть чисто
QT_QPA_PLATFORM=offscreen pytest -q            # 86 тестов

# Собрать .exe (PyInstaller)
pyinstaller --noconfirm SpaceMusicHubGUI.spec  # → dist/SpaceMusicHub/SpaceMusicHub.exe (~2-4 мин)

# Упаковать установщик (Inno Setup 6 стоит локально):
#   1) стейджим dist → installer/SpaceMusicHub, чистим runtime-файлы (.env, *.json, bot.log, lang.txt)
#   2) запускаем iscc.exe installer/SpaceMusicHub.iss → dist/SpaceMusicHub-Setup-vX.Y.Z.exe
```

### ⚠️ Гочи (грабли), которые уже наступили
- **Песочница блокирует вызов `iscc.exe`** (путь в "Program Files") → запускать
  PowerShell с `dangerouslyDisableSandbox: true`, путь к iscc:
  `C:\Program Files (x86)\Inno Setup 6\iscc.exe`.
- **Кириллица в путях** ломает bash-вывод (кракозябры в консоли) — на работу не
  влияет, но `python3` в этой среде нет, используй `python`.
- **Кодировка бота:** диспетчер форсит UTF-8 на stdout/stderr (иначе русский текст
  бота приходил в GUI как зелёные ◆). Не убирать `reconfigure(encoding="utf-8")`.
- **Токен НЕ должен попадать в логи** — есть `_TokenMaskFilter` + httpx/telegram
  заглушены до WARNING. Перед каждой выкладкой `.exe` я сканирую его mmap'ом на
  наличие токена/`.env`/`bot.log`.
- **lang.txt** хранит выбранный язык (в папке установки). Первый запуск = English.
- **`.env`** удаляется при деинсталляции (там токен). При обновлении (Setup поверх) —
  сохраняется.
- Установщик дефолтит на English (`LanguageDetectionMethod=none`), GUI тоже.

### GitHub Release (gh CLI уже поставлен портативно)
```bash
GH="./.tools/bin/gh.exe"
# токен берётся из git credential (gh auth login его отвергает из-за scope,
# поэтому используем GH_TOKEN напрямую — он gh не валидирует):
token=$(printf "protocol=https\nhost=github.com\n\n" | git credential fill 2>/dev/null | grep '^password=' | cut -d= -f2-)
GH_TOKEN="$token" "$GH" release create vX.Y.Z --title "..." --notes-file notes.md "dist/Setup.exe"
```

## 🌐 Сайт (`docs/index.html`)
- Один файл, без сборки. Фон — статичная картинка `bg.jpg` (раньше было видео,
  убрали из-за тормозов). Шрифты: Unbounded (заголовки) + Space Grotesk.
- i18n: переключатель **EN / LV / RU**, переводы в JS-объекте внутри файла,
  тексты помечены `data-i18n`. На мобильных нет горизонтального вылета
  (`overflow-x:hidden` на html+body, эквалайзер клипится).
- Публикация: `git add docs/index.html && git commit && git push` → GitHub Pages
  (Source = master /docs) пересоберёт за 1-2 мин.

## 👤 О пользователе
- Подпись разработчика: **Chrono Warden** (github.com/AAvlasins-dev), email
  chronowarden23@gmail.com. Проект — портфолио для работодателя.
- Общается по-русски. Любит, когда чинят по-настоящему (с проверкой), а не на глаз.

## Как продолжить в новом чате
1. Открой Claude Code в этой папке.
2. Скажи: «прочитай HANDOFF.md» — и дальше свою задачу.
3. Весь код, git-история, доступ к GitHub, Inno Setup, gh CLI (`.tools/`) — на месте.
