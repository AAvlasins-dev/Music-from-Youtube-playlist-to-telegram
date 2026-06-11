#!/usr/bin/env python3
"""Space Music Hub — GUI v2  (PyQt6 · Cyber Neon 2026)

Launch:
    python gui_app.py

Requires:
    pip install PyQt6
"""

from __future__ import annotations

import datetime
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    QSize, QTimer, QThread,
    Qt, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QIcon, QLinearGradient, QPixmap,
    QPainter, QPainterPath, QPen,
)
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QProgressBar, QPushButton, QScrollBar, QSizePolicy, QStackedWidget,
    QSystemTrayIcon, QTextEdit, QVBoxLayout, QWidget,
)
from PyQt6.QtGui import QAction

# ── Paths ─────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

def _resource(name: str) -> Path:
    """Look for bundled assets first (PyInstaller _MEIPASS), fall back to repo."""
    if hasattr(sys, "_MEIPASS"):
        p = Path(sys._MEIPASS) / name
        if p.exists():
            return p
    for base in (BASE_DIR, BASE_DIR / "docs"):
        p = base / name
        if p.exists():
            return p
    return BASE_DIR / name

ENV_PATH   = BASE_DIR / ".env"
# Prefer the round (alpha-masked) versions; fall back to legacy square.
LOGO_PATH  = _resource("logo_round.png") if _resource("logo_round.png").exists() else _resource("logo.png")
LOGO_ICO   = _resource("logo_round.ico") if _resource("logo_round.ico").exists() else _resource("logo.ico")
BOT_SCRIPT = BASE_DIR / "telegram_bot_music_youtube.py"
# Static background image — replaces the heavy 4K video which was
# pinning a CPU core on weaker machines.
BG_IMAGE_PATHS = [
    _resource("bg.jpg"),
    BASE_DIR / "bg.jpg",
    BASE_DIR / "docs" / "bg.jpg",
]

# Bot's single-instance lock — bot writes this in _app_dir() while a
# Run/Watch is active, and removes it in a `finally` block. If we
# TerminateProcess the bot subprocess, that finally never runs, so we
# clean it up from the GUI side as well.
LOCK_PATH = BASE_DIR / "bot.lock"

# True when launched with --tray (auto-start / background mode)
START_HIDDEN = "--tray" in sys.argv

# ── Bot-subprocess dispatcher ─────────────────────────────────────────
# The GUI .exe doubles as the bot host: when relaunched with --bot-*
# flags it imports the bot module and runs the corresponding mode,
# instead of bringing up the Qt UI. This lets BotWorker simply
# subprocess.Popen(sys.executable, '--bot-watch') and stream stdout —
# no separate python.exe needed in the bundle.
_BOT_MODES = {
    "--bot-watch": "watch",
    "--bot-once":  "once",
    "--bot-check": "check",
    "--bot-test":  "test",
}


def _run_bot_mode(mode: str) -> int:
    # Make the bundled telegram_bot_music_youtube.py importable both
    # in dev (next to gui_app.py) and inside the PyInstaller bundle
    # (extracted into _MEIPASS).
    if hasattr(sys, "_MEIPASS"):
        sys.path.insert(0, sys._MEIPASS)
    sys.path.insert(0, str(BASE_DIR))
    try:
        import telegram_bot_music_youtube as bot  # noqa: E402
    except Exception as exc:                       # noqa: BLE001
        print(f"[ERROR] Cannot import bot module: {exc}", flush=True)
        return 1
    fn = {
        "watch": bot._do_watch,
        "once":  bot._do_run,
        "check": bot._do_check,
        "test":  bot._do_test,
    }.get(mode)
    if not fn:
        print(f"[ERROR] Unknown bot mode: {mode}", flush=True)
        return 1
    return int(fn() or 0)


# Run early — before Qt is touched.
for _flag, _mode in _BOT_MODES.items():
    if _flag in sys.argv:
        sys.exit(_run_bot_mode(_mode))

# ── Palette ───────────────────────────────────────────────────────────
BG       = "#050505"
CYAN     = "#00d4ff"
PURPLE   = "#8b5cf6"
MAGENTA  = "#f72585"
WHITE    = "#f0f4ff"
TEXT     = "#8892a4"
MUTED    = "#404258"
SUCCESS  = "#34d399"
ERROR    = "#f87171"
AMBER    = "#f59e0b"

# ══════════════════════════════════════════════════════════════════════
#  i18n — three-language string table (Russian / English / Latvian)
# ══════════════════════════════════════════════════════════════════════
LANG_SETTING_FILE = BASE_DIR / "lang.txt"


def _detect_lang() -> str:
    """Pick a UI language: explicit user choice → Windows locale → English."""
    # 1. Explicit override (persisted from a previous switch)
    if LANG_SETTING_FILE.exists():
        v = LANG_SETTING_FILE.read_text(encoding="utf-8", errors="ignore").strip().lower()
        if v in ("ru", "en", "lv"):
            return v
    # 2. Inherit from Windows display language (QLocale is more reliable
    #    than `locale.getlocale()` on Windows for the UI language).
    try:
        from PyQt6.QtCore import QLocale
        code = QLocale.system().name().lower()  # e.g. "ru_ru"
        for prefix in ("ru", "lv"):
            if code.startswith(prefix):
                return prefix
    except Exception:
        pass
    return "en"


LANGS: dict[str, dict[str, str]] = {
    "ru": {
        # Nav
        "nav.title":    "Space Music Hub",
        "nav.badge":    "v2.0 · GUI",

        # Wizard stepper
        "step.1":       "ТОКЕН",
        "step.2":       "КАНАЛ",
        "step.3":       "ГОТОВО",

        # Wizard step 1 — bot token
        "w.step1.title":   "Шаг 1 — создаём Telegram-бота",
        "w.step1.sub":     "Нужно один раз создать своего бота через @BotFather и взять у него токен.",
        "w.step1.howto": (
            "<ol style='margin:0 0 4px 18px; padding:0; line-height:1.7;'>"
            "<li>Открой Telegram (приложение на телефоне или <a style='color:#00d4ff' href='https://web.telegram.org'>web.telegram.org</a>).</li>"
            "<li>В поиске сверху напиши <b>@BotFather</b> и открой бота с синей галочкой ✓.</li>"
            "<li>Нажми кнопку <b>Start</b> (или напиши <code>/start</code>).</li>"
            "<li>Напиши команду <code>/newbot</code>.</li>"
            "<li>BotFather спросит <b>имя</b> бота — придумай любое (например: <i>Моя музыка</i>).</li>"
            "<li>Потом спросит <b>username</b> — он должен заканчиваться на <code>bot</code> "
            "(например: <code>mymusic2026_bot</code>). Если занят — попробуй другое.</li>"
            "<li>BotFather пришлёт сообщение со строкой типа <code>8280083661:AAE7tJTov...</code> — "
            "<b>это твой токен</b>. Скопируй его целиком.</li>"
            "</ol>"
            "<p style='margin:8px 0 0; color:#f59e0b'>⚠ Никому не передавай этот токен — "
            "кто им владеет, тот управляет твоим ботом.</p>"
        ),
        "w.step1.input.placeholder": "Вставь токен сюда: 1234567890:AAFxxxxxxxxxxxxxxxxx",

        # Wizard step 2 — channel + playlist
        "w.step2.title":   "Шаг 2 — куда и откуда брать музыку",
        "w.step2.sub":     "Нужен публичный Telegram-канал, в который бот будет постить треки, и YouTube-плейлист, который он будет мониторить.",
        "w.step2.howto": (
            "<b style='color:#f0f4ff'>Шаг 2.1 — Канал в Telegram:</b>"
            "<ol style='margin:4px 0 10px 18px; padding:0; line-height:1.6;'>"
            "<li>В Telegram: меню (≡) → <b>Создать канал</b> → дай название → выбери <b>Публичный</b>.</li>"
            "<li>Придумай ему публичную ссылку, например <code>my_music_2026</code>. Полностью это будет "
            "<code>@my_music_2026</code>.</li>"
            "<li>Открой канал → ⋯ (три точки) → <b>Управление каналом</b> → <b>Администраторы</b> → "
            "<b>Добавить администратора</b> → найди своего бота по имени → добавь.</li>"
            "<li>Поставь ему галочки <b>«Размещать сообщения»</b> и <b>«Закреплять сообщения»</b>. Без них бот не сможет постить.</li>"
            "</ol>"
            "<b style='color:#f0f4ff'>Шаг 2.2 — Плейлист на YouTube:</b>"
            "<ol style='margin:4px 0 0 18px; padding:0; line-height:1.6;'>"
            "<li>Открой YouTube, найди свой плейлист.</li>"
            "<li>Скопируй из адресной строки браузера ссылку — она должна выглядеть так: "
            "<code>https://www.youtube.com/playlist?list=PLxxxxxxx</code>.</li>"
            "<li>Вставь её в нижнее поле. Можно добавить несколько пар «канал + плейлист» — кнопка <b>+ Добавить пару</b> под последней парой.</li>"
            "</ol>"
        ),
        "w.step2.chan.placeholder":  "@название_канала (с @ в начале)",
        "w.step2.plist.placeholder": "https://www.youtube.com/playlist?list=...",
        "w.step2.add":               "+ Добавить пару (канал + плейлист)",
        "w.step2.remove":            "×",
        "w.step2.pair":              "Пара #{0}",
        "w.test.btn":                "Тест канала",
        "w.test.checking":           "Отправляю тест в {0}…",
        "w.test.ok":                 "✓ Бот может писать в «{0}»",
        "w.test.fail":               "✗ Не вышло: {0}. Проверь, что бот добавлен админом с правом «Размещать сообщения».",
        "w.test.need":               "Сначала введи токен (шаг 1) и канал.",

        # Wizard step 3 — review
        "w.step3.title":  "Шаг 3 — проверь и запусти",
        "w.step3.sub":    "Если всё правильно — жми «Сохранить и запустить». Настройки можно поменять потом через кнопку ⚙ Настройки.",
        "w.review.token":    "Токен бота",
        "w.review.channel":  "Канал",
        "w.review.playlist": "Плейлист",

        # Wizard buttons
        "w.btn.back":     "← Назад",
        "w.btn.next":     "Дальше →",
        "w.btn.save":     "Сохранить и запустить →",

        # Wizard errors
        "w.err.token":    "Токен похож на неправильный — он содержит ':' и длиннее 20 символов. Скопируй ещё раз из BotFather.",
        "w.err.channel":  "Имя канала должно начинаться с @ (например @my_music_channel).",
        "w.err.playlist": "Вставь ссылку на YouTube-плейлист или его ID.",

        # Dashboard
        "d.cfg.ok":       "✓ Настройки загружены",
        "d.cfg.miss":     "⚠ Нет настроек — открой мастер",
        "d.btn.watch":    "▶  СЛЕДИТЬ",
        "d.btn.once":     "⚡  ОДИН РАЗ",
        "d.btn.check":    "🔍  ПРОВЕРИТЬ",
        "d.btn.stop":     "■  СТОП",
        "d.btn.config":   "⚙  НАСТРОЙКИ",
        "d.hint.watch":   "каждые 15 мин сам ищет новые треки и постит",
        "d.hint.once":    "один прогон: скачать всё новое и остановиться",
        "d.hint.check":   "только проверить настройки, ничего не качать",
        "d.hint.stop":    "остановить текущий процесс",
        "d.hint.config":  "поменять токен, каналы или плейлисты",
        "d.stat.posted":  "ТРЕКОВ ОТПРАВЛЕНО",
        "d.stat.failed":  "ОШИБОК",
        "d.stat.runs":    "ЗАПУСКОВ ЗА СЕССИЮ",
        "d.add.title":    "+ Добавить пару (канал + плейлист)",
        "d.add.note":     "Пара добавится в настройки. Если бот сейчас работает — нажми СТОП и СЛЕДИТЬ заново.",
        "d.add.btn":      "Добавить",
        "d.add.ok":       "✓ Пара добавлена. Сейчас в работе: {0}.",
        # Progress + simple-mode log
        "d.progress":     "Трек {0} из {1}",
        "d.mode.simple":  "Простой",
        "d.mode.expert":  "Эксперт",
        "d.s.connected":  "✓ Бот подключён",
        "d.s.checking":   "Проверяю плейлист…",
        "d.s.new":        "⚡ Новых треков: {0}",
        "d.s.nonew":      "Новых треков нет — всё уже отправлено",
        "d.s.posted":     "✓ Отправлено: {0}",
        "d.s.error":      "✗ Ошибка (переключи на «Эксперт» для подробностей)",
        "d.s.done":       "Готово",
        # Bitrate selector
        "d.bitrate":      "Качество MP3:",
        "d.bitrate.hint": "Применится к новым загрузкам. 320 — крупнее файлы; YouTube-звук обычно ~128–160, так что 192 — золотая середина.",
        "d.log.title":    "ЖУРНАЛ",
        "d.log.clear":    "очистить",
        "d.ready":        "Space Music Hub GUI готов.",
        "d.no_env":       "Файла .env нет — сначала открой ⚙ НАСТРОЙКИ.",
        "d.starting":     "▶  Запускаю режим [{0}]…",
        "d.stopped":      "■  Остановлено пользователем.",

        # Status badge
        "badge.idle":     "ОЖИДАНИЕ",
        "badge.running":  "РАБОТАЕТ",
        "badge.error":    "ОШИБКА",
        "badge.done":     "ГОТОВО",

        # Tray
        "tray.open":      "Открыть окно",
        "tray.watch":     "▶ Начать слежение",
        "tray.stop":      "■ Стоп",
        "tray.quit":      "Выйти",
        "tray.hidden":    "Программа продолжает работать в трее. Нажми правой кнопкой по иконке для меню.",
    },
    "en": {
        "nav.title":    "Space Music Hub",
        "nav.badge":    "v2.0 · GUI",
        "step.1":       "TOKEN",
        "step.2":       "CHANNEL",
        "step.3":       "DONE",
        "w.step1.title":   "Step 1 — Create your Telegram bot",
        "w.step1.sub":     "You need to create your own bot via @BotFather once and copy the token.",
        "w.step1.howto": (
            "<ol style='margin:0 0 4px 18px; padding:0; line-height:1.7;'>"
            "<li>Open Telegram (mobile app or <a style='color:#00d4ff' href='https://web.telegram.org'>web.telegram.org</a>).</li>"
            "<li>In the search bar type <b>@BotFather</b> and open the bot with the blue checkmark ✓.</li>"
            "<li>Tap <b>Start</b> (or type <code>/start</code>).</li>"
            "<li>Type the command <code>/newbot</code>.</li>"
            "<li>BotFather asks for the bot <b>name</b> — anything (e.g. <i>My music</i>).</li>"
            "<li>Then for the <b>username</b> — it must end with <code>bot</code> "
            "(e.g. <code>mymusic2026_bot</code>). Try another if taken.</li>"
            "<li>BotFather replies with a string like <code>8280083661:AAE7tJTov...</code> — "
            "<b>that's your token</b>. Copy it completely.</li>"
            "</ol>"
            "<p style='margin:8px 0 0; color:#f59e0b'>⚠ Never share this token — "
            "whoever has it controls your bot.</p>"
        ),
        "w.step1.input.placeholder": "Paste token here: 1234567890:AAFxxxxxxxxxxxxxxxxx",
        "w.step2.title":   "Step 2 — where to post, what to mirror",
        "w.step2.sub":     "You need a public Telegram channel for the bot to post into, and a YouTube playlist for it to watch.",
        "w.step2.howto": (
            "<b style='color:#f0f4ff'>Step 2.1 — Telegram channel:</b>"
            "<ol style='margin:4px 0 10px 18px; padding:0; line-height:1.6;'>"
            "<li>In Telegram: menu (≡) → <b>Create Channel</b> → name it → choose <b>Public</b>.</li>"
            "<li>Set a public link, e.g. <code>my_music_2026</code>. The full handle is "
            "<code>@my_music_2026</code>.</li>"
            "<li>Open the channel → ⋯ → <b>Manage Channel</b> → <b>Administrators</b> → "
            "<b>Add Administrator</b> → find your bot by name → add it.</li>"
            "<li>Give it the <b>“Post Messages”</b> and <b>“Pin Messages”</b> permissions. Without these the bot can't post.</li>"
            "</ol>"
            "<b style='color:#f0f4ff'>Step 2.2 — YouTube playlist:</b>"
            "<ol style='margin:4px 0 0 18px; padding:0; line-height:1.6;'>"
            "<li>Open YouTube, find your playlist.</li>"
            "<li>Copy the URL from the address bar — it looks like "
            "<code>https://www.youtube.com/playlist?list=PLxxxxxxx</code>.</li>"
            "<li>Paste it below. You can add more channel + playlist pairs with the <b>+ Add pair</b> button below the last one.</li>"
            "</ol>"
        ),
        "w.step2.chan.placeholder":  "@channel_handle (must start with @)",
        "w.step2.plist.placeholder": "https://www.youtube.com/playlist?list=...",
        "w.step2.add":               "+ Add pair (channel + playlist)",
        "w.step2.remove":            "×",
        "w.step2.pair":              "Pair #{0}",
        "w.test.btn":                "Test channel",
        "w.test.checking":           "Sending a test to {0}…",
        "w.test.ok":                 "✓ Bot can post to “{0}”",
        "w.test.fail":               "✗ Failed: {0}. Make sure the bot is a channel admin with “Post Messages”.",
        "w.test.need":               "Enter the token (step 1) and a channel first.",
        "w.step3.title":  "Step 3 — review & launch",
        "w.step3.sub":    "Looks good? Click Save & Launch. You can change settings later via ⚙ CONFIG.",
        "w.review.token":    "Bot token",
        "w.review.channel":  "Channel",
        "w.review.playlist": "Playlist",
        "w.btn.back":     "← Back",
        "w.btn.next":     "Continue →",
        "w.btn.save":     "Save & Launch →",
        "w.err.token":    "That token doesn't look right — it should contain ':' and be longer than 20 characters. Copy it again from BotFather.",
        "w.err.channel":  "Channel must start with @ (e.g. @my_music_channel).",
        "w.err.playlist": "Paste a YouTube playlist URL or ID.",
        "d.cfg.ok":       "✓ Config loaded",
        "d.cfg.miss":     "⚠ No config — run wizard",
        "d.btn.watch":    "▶  WATCH",
        "d.btn.once":     "⚡  RUN ONCE",
        "d.btn.check":    "🔍  CHECK",
        "d.btn.stop":     "■  STOP",
        "d.btn.config":   "⚙  CONFIG",
        "d.hint.watch":   "checks playlist every 15 min and auto-posts",
        "d.hint.once":    "one pass: post everything new, then stop",
        "d.hint.check":   "just verify config, don't download anything",
        "d.hint.stop":    "stop the current run",
        "d.hint.config":  "change token, channels or playlists",
        "d.stat.posted":  "TRACKS POSTED",
        "d.stat.failed":  "FAILED",
        "d.stat.runs":    "SESSION RUNS",
        "d.add.title":    "+ Add another channel + playlist pair",
        "d.add.note":     "Pair gets appended to your config. If the bot is running, hit STOP and WATCH again.",
        "d.add.btn":      "Add",
        "d.add.ok":       "✓ Pair added. Now in config: {0}.",
        "d.progress":     "Track {0} of {1}",
        "d.mode.simple":  "Simple",
        "d.mode.expert":  "Expert",
        "d.s.connected":  "✓ Bot connected",
        "d.s.checking":   "Checking playlist…",
        "d.s.new":        "⚡ New tracks: {0}",
        "d.s.nonew":      "No new tracks — all already posted",
        "d.s.posted":     "✓ Posted: {0}",
        "d.s.error":      "✗ Error (switch to “Expert” for details)",
        "d.s.done":       "Done",
        "d.bitrate":      "MP3 quality:",
        "d.bitrate.hint": "Applies to new downloads. 320 = bigger files; YouTube audio is usually ~128–160, so 192 is the sweet spot.",
        "d.log.title":    "LOG OUTPUT",
        "d.log.clear":    "clear",
        "d.ready":        "Space Music Hub GUI ready.",
        "d.no_env":       "No .env found — open ⚙ CONFIG first.",
        "d.starting":     "▶  Starting [{0}] mode…",
        "d.stopped":      "■  Stopped by user.",
        "badge.idle":     "IDLE",
        "badge.running":  "RUNNING",
        "badge.error":    "ERROR",
        "badge.done":     "DONE",
        "tray.open":      "Open Dashboard",
        "tray.watch":     "▶ Start Watching",
        "tray.stop":      "■ Stop",
        "tray.quit":      "Quit",
        "tray.hidden":    "Still running in the tray — right-click the icon for menu.",
    },
    "lv": {
        "nav.title":    "Space Music Hub",
        "nav.badge":    "v2.0 · GUI",
        "step.1":       "TOKEN",
        "step.2":       "KANĀLS",
        "step.3":       "GATAVS",
        "w.step1.title":   "1. solis — izveido savu Telegram botu",
        "w.step1.sub":     "Vienreiz jāizveido savs bots caur @BotFather un jāpaņem tā token.",
        "w.step1.howto": (
            "<ol style='margin:0 0 4px 18px; padding:0; line-height:1.7;'>"
            "<li>Atver Telegram (lietotne vai <a style='color:#00d4ff' href='https://web.telegram.org'>web.telegram.org</a>).</li>"
            "<li>Meklēšanas joslā ieraksti <b>@BotFather</b> un atver botu ar zilo ķeksīti ✓.</li>"
            "<li>Nospied <b>Start</b> (vai ieraksti <code>/start</code>).</li>"
            "<li>Ieraksti komandu <code>/newbot</code>.</li>"
            "<li>BotFather prasīs bota <b>vārdu</b> — jebkurš (piem. <i>Mana mūzika</i>).</li>"
            "<li>Tad prasīs <b>username</b> — tam jābeidzas ar <code>bot</code> "
            "(piem. <code>mymusic2026_bot</code>). Ja aizņemts — mēģini citu.</li>"
            "<li>BotFather atsūtīs virkni <code>8280083661:AAE7tJTov...</code> — "
            "<b>tas ir tavs token</b>. Nokopē to pilnībā.</li>"
            "</ol>"
            "<p style='margin:8px 0 0; color:#f59e0b'>⚠ Nekad nedalies ar šo tokenu — "
            "kuram tas ir, tas vada tavu botu.</p>"
        ),
        "w.step1.input.placeholder": "Ielīmē tokenu: 1234567890:AAFxxxxxxxxxxxxxxxxx",
        "w.step2.title":   "2. solis — kur publicēt un ko sekot",
        "w.step2.sub":     "Vajag publisku Telegram kanālu, kurā bots publicēs, un YouTube atskaņošanas sarakstu, kuru tas vēros.",
        "w.step2.howto": (
            "<b style='color:#f0f4ff'>2.1. solis — Telegram kanāls:</b>"
            "<ol style='margin:4px 0 10px 18px; padding:0; line-height:1.6;'>"
            "<li>Telegram: izvēlne (≡) → <b>Izveidot kanālu</b> → dod vārdu → izvēlies <b>Publisks</b>.</li>"
            "<li>Iestati publisko saiti, piem. <code>my_music_2026</code>. Pilns: <code>@my_music_2026</code>.</li>"
            "<li>Atver kanālu → ⋯ → <b>Pārvaldīt kanālu</b> → <b>Administratori</b> → "
            "<b>Pievienot administratoru</b> → atrodi savu botu → pievieno.</li>"
            "<li>Iedod tam atļaujas <b>«Publicēt ziņas»</b> un <b>«Piespraust ziņas»</b>.</li>"
            "</ol>"
            "<b style='color:#f0f4ff'>2.2. solis — YouTube atskaņošanas saraksts:</b>"
            "<ol style='margin:4px 0 0 18px; padding:0; line-height:1.6;'>"
            "<li>Atver YouTube, atrodi savu sarakstu.</li>"
            "<li>Nokopē saiti no adreses joslas: "
            "<code>https://www.youtube.com/playlist?list=PLxxxxxxx</code>.</li>"
            "<li>Ielīmē to lejasējā laukā. Var pievienot vairākus kanālu+saraksta pārus ar pogu <b>+ Pievienot pāri</b>.</li>"
            "</ol>"
        ),
        "w.step2.chan.placeholder":  "@kanala_vards (jāsākas ar @)",
        "w.step2.plist.placeholder": "https://www.youtube.com/playlist?list=...",
        "w.step2.add":               "+ Pievienot pāri (kanāls + saraksts)",
        "w.step2.remove":            "×",
        "w.step2.pair":              "Pāris #{0}",
        "w.test.btn":                "Testēt kanālu",
        "w.test.checking":           "Sūtu testu uz {0}…",
        "w.test.ok":                 "✓ Bots var rakstīt uz “{0}”",
        "w.test.fail":               "✗ Neizdevās: {0}. Pārliecinies, ka bots ir kanāla administrators ar “Publicēt ziņas”.",
        "w.test.need":               "Vispirms ievadi tokenu (1. solis) un kanālu.",
        "w.step3.title":  "3. solis — pārbaudi un palaid",
        "w.step3.sub":    "Viss kārtībā? Spied «Saglabāt un palaist». Vēlāk var mainīt caur ⚙ IESTATĪJUMI.",
        "w.review.token":    "Bota token",
        "w.review.channel":  "Kanāls",
        "w.review.playlist": "Saraksts",
        "w.btn.back":     "← Atpakaļ",
        "w.btn.next":     "Tālāk →",
        "w.btn.save":     "Saglabāt un palaist →",
        "w.err.token":    "Token nelikās pareizs — tajā jābūt ':' un tas garāks par 20 simboliem. Kopē vēlreiz no BotFather.",
        "w.err.channel":  "Kanāla vārdam jāsākas ar @ (piem. @my_music_channel).",
        "w.err.playlist": "Ielīmē YouTube saraksta saiti vai ID.",
        "d.cfg.ok":       "✓ Iestatījumi ielādēti",
        "d.cfg.miss":     "⚠ Nav iestatījumu — palaid vedni",
        "d.btn.watch":    "▶  SEKOT",
        "d.btn.once":     "⚡  REIZI",
        "d.btn.check":    "🔍  PĀRBAUDĪT",
        "d.btn.stop":     "■  STOP",
        "d.btn.config":   "⚙  IESTATĪJUMI",
        "d.hint.watch":   "ik pa 15 min pārbauda sarakstu un publicē jaunos",
        "d.hint.once":    "vienreiz: publicē visu jauno un apstājas",
        "d.hint.check":   "tikai pārbauda iestatījumus, neko nelejupielādē",
        "d.hint.stop":    "apturēt pašreizējo darbu",
        "d.hint.config":  "mainīt tokenu, kanālus vai sarakstus",
        "d.stat.posted":  "PUBLICĒTI",
        "d.stat.failed":  "KĻŪDAS",
        "d.stat.runs":    "PALAIŠANAS",
        "d.add.title":    "+ Pievienot kanāla + saraksta pāri",
        "d.add.note":     "Pāris tiks pievienots iestatījumiem. Ja bots strādā — STOP un SEKOT vēlreiz.",
        "d.add.btn":      "Pievienot",
        "d.add.ok":       "✓ Pāris pievienots. Tagad iestatījumos: {0}.",
        "d.progress":     "Dziesma {0} no {1}",
        "d.mode.simple":  "Vienkāršs",
        "d.mode.expert":  "Eksperts",
        "d.s.connected":  "✓ Bots savienots",
        "d.s.checking":   "Pārbaudu sarakstu…",
        "d.s.new":        "⚡ Jaunas dziesmas: {0}",
        "d.s.nonew":      "Nav jaunu dziesmu — viss jau publicēts",
        "d.s.posted":     "✓ Publicēts: {0}",
        "d.s.error":      "✗ Kļūda (pārslēdz uz “Eksperts”, lai redzētu detaļas)",
        "d.s.done":       "Pabeigts",
        "d.bitrate":      "MP3 kvalitāte:",
        "d.bitrate.hint": "Attiecas uz jaunām lejupielādēm. 320 = lielāki faili; YouTube skaņa parasti ~128–160, tāpēc 192 ir optimāli.",
        "d.log.title":    "ŽURNĀLS",
        "d.log.clear":    "tīrīt",
        "d.ready":        "Space Music Hub GUI gatavs.",
        "d.no_env":       "Nav .env — vispirms atver ⚙ IESTATĪJUMI.",
        "d.starting":     "▶  Sāk [{0}] režīmu…",
        "d.stopped":      "■  Apturēts.",
        "badge.idle":     "GAIDA",
        "badge.running":  "STRĀDĀ",
        "badge.error":    "KĻŪDA",
        "badge.done":     "PABEIGTS",
        "tray.open":      "Atvērt logu",
        "tray.watch":     "▶ Sākt sekot",
        "tray.stop":      "■ Stop",
        "tray.quit":      "Iziet",
        "tray.hidden":    "Programma joprojām strādā teknē. Labais klikšķis uz ikonas — izvēlne.",
    },
}


LANG = _detect_lang()


def tr(key: str, *args) -> str:
    s = LANGS.get(LANG, {}).get(key) or LANGS["en"].get(key, key)
    if args:
        try: s = s.format(*args)
        except Exception: pass
    return s


def set_lang(code: str) -> None:
    global LANG
    if code in LANGS:
        LANG = code
        try:
            LANG_SETTING_FILE.write_text(code, encoding="utf-8")
        except OSError:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Input normalisers — must match what the bot's setup_wizard does
# ══════════════════════════════════════════════════════════════════════
import re as _re


def extract_playlist_id(text: str) -> str:
    """Accept a full YouTube playlist URL OR a bare PL... ID.

    The bot rebuilds the URL from the ID, so we must NOT save the full URL
    here (otherwise the bot ends up requesting
    `...playlist?list=https://www.youtube.com/playlist?list=PLxxxx`
    and YouTube returns HTTP 400).
    """
    text = (text or "").strip()
    m = _re.search(r"[?&]list=([A-Za-z0-9_-]+)", text)
    return m.group(1) if m else text


def normalise_handle(text: str) -> str:
    """Accept @name, name, or t.me/name — return @name (or empty)."""
    text = (text or "").strip()
    link = _re.search(r"t\.me/([A-Za-z0-9_]+)", text)
    if link:
        text = link.group(1)
    text = text.lstrip("@")
    return f"@{text}" if text else ""


def read_env_value(key: str, default: str = "") -> str:
    """Read a single KEY=value from .env, or *default* if missing."""
    if not ENV_PATH.exists():
        return default
    for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return default


def set_env_value(key: str, value: str) -> None:
    """Update KEY=value in .env in place, or append it if not present."""
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines()
    out, found = [], False
    for line in lines:
        if line.strip().startswith(f"{key}="):
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


# ── Global stylesheet ─────────────────────────────────────────────────
QSS = f"""
QWidget {{
    background: transparent;
    color: {WHITE};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 14px;
    border: none;
}}
QMainWindow, QDialog {{
    background: {BG};
}}
QLineEdit {{
    background: rgba(255,255,255,12);
    border: 1px solid rgba(255,255,255,14);
    border-radius: 10px;
    padding: 11px 15px;
    color: {WHITE};
    font-size: 14px;
    selection-background-color: rgba(0,212,255,50);
}}
QLineEdit:focus {{
    border: 1px solid rgba(0,212,255,80);
    background: rgba(0,212,255,10);
}}
QTextEdit {{
    background: rgba(0,0,0,210);
    border: 1px solid rgba(0,212,255,28);
    border-radius: 12px;
    padding: 14px 18px;
    color: #b8c4d6;
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 12px;
    line-height: 1.6;
}}
QScrollBar:vertical {{
    background: rgba(255,255,255,5);
    width: 5px;
    border-radius: 3px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(0,212,255,55);
    border-radius: 3px;
    min-height: 18px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


# ══════════════════════════════════════════════════════════════════════
#  Static background  (bg.jpg painted once per resize — zero CPU)
# ══════════════════════════════════════════════════════════════════════
class StaticBackgroundWidget(QWidget):
    """Paints a single still frame as the window background.

    Replaces the prior QVideoSink approach: the source clip is 4K at
    30 fps, and CPU-scaling every frame down to ~1100 px wide pegged a
    full core and could freeze weaker machines. The visual difference
    is minimal (the original clip is essentially a slow wallpaper-like
    loop), so we ship one frame and call it a day.
    """

    def __init__(self, image_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._source  = QPixmap(image_path)
        self._scaled: QPixmap | None = None

    def resizeEvent(self, _event) -> None:  # noqa: N802
        if self._source.isNull():
            return
        self._scaled = self._source.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        if self._scaled is None or self._scaled.isNull():
            return
        p = QPainter(self)
        # Centre the scaled pixmap (overflow trimmed by widget bounds).
        x = (self.width()  - self._scaled.width())  // 2
        y = (self.height() - self._scaled.height()) // 2
        p.drawPixmap(x, y, self._scaled)


# ══════════════════════════════════════════════════════════════════════
#  NeonDivider  (static gradient line — replaces the old animated equalizer)
# ══════════════════════════════════════════════════════════════════════
class NeonDivider(QWidget):
    """A thin static magenta→purple→cyan glow line.

    Replaces the former EqualizerWidget, whose QTimer repainted 34 gradient
    bars at ~33 fps non-stop — even idle and even minimised to the tray —
    burning a CPU/GPU slice 24/7. This draws once and never animates.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(3)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        g = QLinearGradient(0.0, 0.0, float(self.width()), 0.0)
        g.setColorAt(0.0, QColor(MAGENTA))
        g.setColorAt(0.5, QColor(PURPLE))
        g.setColorAt(1.0, QColor(CYAN))
        path = QPainterPath()
        path.addRoundedRect(0.0, 0.0, float(self.width()), float(self.height()), 1.5, 1.5)
        p.setBrush(QBrush(g))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)
        p.end()


# ══════════════════════════════════════════════════════════════════════
#  NeonButton
# ══════════════════════════════════════════════════════════════════════
class NeonButton(QPushButton):
    """Styled button with optional drop-shadow glow."""

    _STYLES: dict[str, str] = {
        "cyan": f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {CYAN}, stop:1 #0099bb);
                color: #020202;
                border: none; border-radius: 12px;
                padding: 0 26px;
                font-weight: 700; letter-spacing: 1px;
            }}
            QPushButton:hover  {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #30eaff, stop:1 {CYAN}); }}
            QPushButton:pressed {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #0099bb, stop:1 #006f88); }}
            QPushButton:disabled {{ background: rgba(0,212,255,25); color: rgba(0,0,0,80); }}
        """,
        "purple": f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                    stop:0 {PURPLE}, stop:1 #6d28d9);
                color: white;
                border: none; border-radius: 12px;
                padding: 0 26px;
                font-weight: 700; letter-spacing: 1px;
            }}
            QPushButton:hover  {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
                stop:0 #a07aff, stop:1 {PURPLE}); }}
            QPushButton:disabled {{ background: rgba(139,92,246,25); color: rgba(255,255,255,50); }}
        """,
        "glass": f"""
            QPushButton {{
                background: rgba(255,255,255,7);
                color: {WHITE};
                border: 1px solid rgba(255,255,255,13);
                border-radius: 12px; padding: 0 26px;
            }}
            QPushButton:hover  {{ background: rgba(255,255,255,14);
                border-color: rgba(255,255,255,22); }}
            QPushButton:pressed {{ background: rgba(255,255,255,4); }}
            QPushButton:disabled {{ color: {MUTED}; }}
        """,
        "danger": f"""
            QPushButton {{
                background: rgba(247,37,133,12);
                color: {MAGENTA};
                border: 1px solid rgba(247,37,133,35);
                border-radius: 12px; padding: 0 26px;
            }}
            QPushButton:hover  {{ background: rgba(247,37,133,22);
                border-color: rgba(247,37,133,55); }}
        """,
    }

    def __init__(self, text: str, style: str = "glass",
                 glow: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(46)
        self.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        self.setStyleSheet(self._STYLES.get(style, self._STYLES["glass"]))
        if glow:
            self.add_glow(CYAN if style == "cyan" else PURPLE if style == "purple" else WHITE)

    def add_glow(self, color: str = CYAN, radius: int = 22) -> None:
        fx = QGraphicsDropShadowEffect(self)
        c  = QColor(color)
        c.setAlpha(110)
        fx.setColor(c)
        fx.setBlurRadius(radius)
        fx.setOffset(0, 0)
        self.setGraphicsEffect(fx)


# ══════════════════════════════════════════════════════════════════════
#  GlassCard
# ══════════════════════════════════════════════════════════════════════
class GlassCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,5);
                border: 1px solid rgba(255,255,255,10);
                border-radius: 18px;
            }
        """)


# ══════════════════════════════════════════════════════════════════════
#  StatusBadge
# ══════════════════════════════════════════════════════════════════════
class StatusBadge(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 7, 16, 7)
        lay.setSpacing(7)

        self._dot = QLabel("●")
        self._dot.setFont(QFont("Segoe UI", 9))
        self._lbl = QLabel("IDLE")
        self._lbl.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self._lbl.setStyleSheet("letter-spacing: 2px;")
        lay.addWidget(self._dot)
        lay.addWidget(self._lbl)

        self._pulse = QTimer(self)
        self._pulse.timeout.connect(self._blink)
        self._blink_state = False

        self.set_idle()

    def set_idle(self) -> None:
        self._pulse.stop()
        self._dot.setStyleSheet(f"color: {MUTED}")
        self._lbl.setStyleSheet(f"color: {MUTED}; letter-spacing: 2px;")
        self._state = "idle"
        self._lbl.setText(tr("badge.idle"))
        self.setStyleSheet("QWidget { background: rgba(255,255,255,4);"
                           " border: 1px solid rgba(255,255,255,10);"
                           " border-radius: 999px; }")

    def set_running(self) -> None:
        self._pulse.start(550)
        self._dot.setStyleSheet(f"color: {SUCCESS}")
        self._lbl.setStyleSheet(f"color: {CYAN}; letter-spacing: 2px;")
        self._state = "running"
        self._lbl.setText(tr("badge.running"))
        self.setStyleSheet("QWidget { background: rgba(0,212,255,8);"
                           " border: 1px solid rgba(0,212,255,30);"
                           " border-radius: 999px; }")

    def set_error(self) -> None:
        self._pulse.stop()
        self._dot.setStyleSheet(f"color: {ERROR}")
        self._lbl.setStyleSheet(f"color: {ERROR}; letter-spacing: 2px;")
        self._state = "error"
        self._lbl.setText(tr("badge.error"))
        self.setStyleSheet("QWidget { background: rgba(248,113,113,8);"
                           " border: 1px solid rgba(248,113,113,30);"
                           " border-radius: 999px; }")

    def set_done(self) -> None:
        self._pulse.stop()
        self._dot.setStyleSheet(f"color: {SUCCESS}")
        self._lbl.setStyleSheet(f"color: {SUCCESS}; letter-spacing: 2px;")
        self._state = "done"
        self._lbl.setText(tr("badge.done"))
        self.setStyleSheet("QWidget { background: rgba(52,211,153,8);"
                           " border: 1px solid rgba(52,211,153,30);"
                           " border-radius: 999px; }")

    def retranslate(self) -> None:
        getattr(self, f"set_{self._state}", self.set_idle)()

    def _blink(self) -> None:
        self._blink_state = not self._blink_state
        c = SUCCESS if self._blink_state else "#1a6644"
        self._dot.setStyleSheet(f"color: {c}")


# ══════════════════════════════════════════════════════════════════════
#  Bot worker thread
# ══════════════════════════════════════════════════════════════════════
class BotWorker(QThread):
    log    = pyqtSignal(str)   # new text line
    done   = pyqtSignal(bool)  # finished (success?)

    # CLI flag passed to sys.executable. In a PyInstaller build,
    # sys.executable IS the GUI .exe — it dispatches on these flags
    # at startup (see _run_bot_mode at the top of this file). In dev,
    # sys.executable is python.exe so we explicitly point it at this
    # script.
    _MODE_FLAG = {
        "watch": "--bot-watch",
        "once":  "--bot-once",
        "check": "--bot-check",
    }

    def __init__(self, mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.mode    = mode
        self._proc: subprocess.Popen | None = None

    def stop(self) -> None:
        """Stop the bot subprocess.

        Note: the bot runs without a console window (CREATE_NO_WINDOW),
        so Windows console control signals (CTRL_BREAK / CTRL_C) cannot
        be delivered to it — they require an attached console. We just
        terminate, then sweep the lock ourselves. The bot saves
        sent_videos.json after each posted track, so abrupt termination
        only loses the currently-downloading track at worst.
        """
        proc = self._proc
        if not proc or proc.poll() is not None:
            self._clear_lock("stop called but no live process")
            return

        self.log.emit("[stop] Terminating bot subprocess...")
        try:
            proc.terminate()
        except Exception as exc:                    # noqa: BLE001
            self.log.emit(f"[stop] terminate() failed: {exc}")
        try:
            proc.wait(timeout=4)
        except subprocess.TimeoutExpired:
            self.log.emit("[stop] Still alive after 4s — hard kill.")
            try: proc.kill()
            except Exception: pass

        # Bot's `finally` block doesn't run on TerminateProcess, so the
        # lock file would otherwise stay and block the next Watch.
        self._clear_lock("post-stop sweep")

    def _clear_lock(self, reason: str) -> None:
        if LOCK_PATH.exists():
            try:
                LOCK_PATH.unlink()
                self.log.emit(f"[stop] Cleared bot.lock ({reason}).")
            except OSError as exc:
                self.log.emit(f"[stop] Could not clear bot.lock: {exc}")

    def run(self) -> None:
        flag = self._MODE_FLAG.get(self.mode)
        if not flag:
            self.log.emit(f"[ERROR] Unknown mode: {self.mode}")
            self.done.emit(False)
            return

        # Build the command. Frozen → re-launch self.exe with the flag.
        # Dev      → python.exe gui_app.py --bot-* (so we hit the same dispatcher).
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, flag]
        else:
            cmd = [sys.executable, str(Path(__file__).resolve()), flag]

        # On Windows: CREATE_NEW_PROCESS_GROUP is required so we can send
        # CTRL_BREAK_EVENT to the bot subprocess from .stop() — otherwise
        # the signal goes nowhere. CREATE_NO_WINDOW hides any console flash.
        creationflags = 0
        if sys.platform == "win32":
            creationflags = (
                getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            )

        # A stale lock from a previous abrupt kill would block this run
        # before it even starts — clear it pre-emptively.
        self._clear_lock("pre-run sweep")

        # Force the child Python's stdio to UTF-8 — otherwise on Russian
        # Windows the bot's print() goes out as cp1251 and shows up here as
        # `���������` garbage. PYTHONIOENCODING handles stdout/stderr; we
        # also nudge the encoder to never crash on a stray glyph.
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8:replace"
        child_env["PYTHONUTF8"]       = "1"

        try:
            self.log.emit(f"[exec] {' '.join(cmd)}")
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR),
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                env=child_env,
            )
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                if line:
                    self.log.emit(line.rstrip())
            self._proc.wait()
            # Final sweep — even on clean exit, double-check the lock is gone.
            self._clear_lock("post-run sweep")
            self.done.emit(self._proc.returncode == 0)

        except Exception as exc:                  # noqa: BLE001
            self.log.emit(f"[ERROR] {exc}")
            self._clear_lock("error sweep")
            self.done.emit(False)


# ══════════════════════════════════════════════════════════════════════
#  Channel test worker — sends + deletes a test message via --bot-test
# ══════════════════════════════════════════════════════════════════════
class TestWorker(QThread):
    result = pyqtSignal(bool, str)  # (ok, channel-title-or-error)

    def __init__(self, token: str, channel: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._token   = token
        self._channel = channel

    def run(self) -> None:
        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--bot-test"]
        else:
            cmd = [sys.executable, str(Path(__file__).resolve()), "--bot-test"]

        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

        env = os.environ.copy()
        env["PYTHONIOENCODING"]  = "utf-8:replace"
        env["PYTHONUTF8"]        = "1"
        env["SMH_TEST_TOKEN"]    = self._token
        env["SMH_TEST_CHANNEL"]  = self._channel

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, encoding="utf-8",
                errors="replace", cwd=str(BASE_DIR), env=env,
                creationflags=creationflags, timeout=40,
            )
            # The dispatcher prints exactly one TEST_OK|... / TEST_FAIL|... line
            line = ""
            for ln in (proc.stdout or "").splitlines():
                if ln.startswith(("TEST_OK|", "TEST_FAIL|")):
                    line = ln
                    break
            if line.startswith("TEST_OK|"):
                self.result.emit(True, line.split("|", 1)[1])
            elif line.startswith("TEST_FAIL|"):
                self.result.emit(False, line.split("|", 1)[1])
            else:
                self.result.emit(False, (proc.stderr or proc.stdout or "no response").strip()[:200])
        except subprocess.TimeoutExpired:
            self.result.emit(False, "timeout")
        except Exception as exc:                   # noqa: BLE001
            self.result.emit(False, str(exc))


# ══════════════════════════════════════════════════════════════════════
#  Wizard  (3-step setup)
# ══════════════════════════════════════════════════════════════════════
class WizardPage(QWidget):
    finished = pyqtSignal()  # emitted when .env saved

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._step = 0
        self._token = ""
        self._channels: list[dict] = []
        self._build()
        self.retranslate()

    # ── build ──────────────────────────────────────────────────────────
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Card wider now to fit the detailed instructions, scrollable
        # vertically if window is short.
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.setMaximumWidth(720)
        root.addWidget(scroll, alignment=Qt.AlignmentFlag.AlignCenter)

        card = GlassCard()
        card.setMinimumWidth(640)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(40, 32, 40, 32)
        inner.setSpacing(16)

        # ── numbered step pills ───────────────────────────────────────
        pill_row = QHBoxLayout()
        pill_row.setSpacing(0)
        self._pills: list[QLabel] = []
        self._pill_seps: list[QLabel] = []
        for i in range(3):
            pill = QLabel()
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setMinimumHeight(36)
            pill.setMinimumWidth(150)
            pill.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            pill_row.addWidget(pill)
            self._pills.append(pill)
            if i < 2:
                sep = QLabel("─" * 4)
                sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
                sep.setStyleSheet(f"color: {MUTED}; padding: 0 4px;")
                pill_row.addWidget(sep)
                self._pill_seps.append(sep)
        inner.addLayout(pill_row)

        # ── title + subtitle ──────────────────────────────────────────
        self._title_lbl = QLabel()
        self._title_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color: {WHITE};")
        self._title_lbl.setWordWrap(True)
        inner.addWidget(self._title_lbl)

        self._sub_lbl = QLabel()
        self._sub_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        self._sub_lbl.setWordWrap(True)
        inner.addWidget(self._sub_lbl)

        # ── detailed how-to (rich text, only on steps 1 and 2) ────────
        self._howto_lbl = QLabel()
        self._howto_lbl.setStyleSheet(
            f"color: {WHITE}; background: rgba(0,212,255,5);"
            f" border: 1px solid rgba(0,212,255,18);"
            f" border-radius: 12px; padding: 14px 18px; font-size: 13px;")
        self._howto_lbl.setWordWrap(True)
        self._howto_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._howto_lbl.setOpenExternalLinks(True)
        inner.addWidget(self._howto_lbl)

        # ── input stack ───────────────────────────────────────────────
        self._inputs = QStackedWidget()

        # page 0 — token
        p0 = QWidget(); p0l = QVBoxLayout(p0); p0l.setContentsMargins(0,0,0,0)
        self._token_in = QLineEdit()
        self._token_in.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_in.setMinimumHeight(46)
        p0l.addWidget(self._token_in)
        self._inputs.addWidget(p0)

        # page 1 — dynamic list of channel + playlist pairs
        p1 = QWidget()
        self._p1_layout = QVBoxLayout(p1)
        self._p1_layout.setContentsMargins(0, 0, 0, 0)
        self._p1_layout.setSpacing(10)
        self._pair_rows: list[dict] = []  # each {"frame", "chan", "plist", "remove"}
        self._pairs_container = QWidget()
        self._pairs_layout = QVBoxLayout(self._pairs_container)
        self._pairs_layout.setContentsMargins(0, 0, 0, 0)
        self._pairs_layout.setSpacing(10)
        self._p1_layout.addWidget(self._pairs_container)
        self._add_pair_btn = NeonButton("", style="glass")
        self._add_pair_btn.setMinimumHeight(38)
        self._add_pair_btn.clicked.connect(lambda: self._add_pair())
        self._p1_layout.addWidget(self._add_pair_btn)
        self._add_pair()  # start with one empty pair
        self._inputs.addWidget(p1)

        # page 2 — review
        p2 = QWidget(); p2l = QVBoxLayout(p2); p2l.setContentsMargins(0,0,0,0)
        self._review_lbl = QLabel()
        self._review_lbl.setStyleSheet(f"color: {TEXT}; font-size: 14px; line-height: 1.8;")
        self._review_lbl.setWordWrap(True)
        p2l.addWidget(self._review_lbl)
        self._inputs.addWidget(p2)

        inner.addWidget(self._inputs)

        # ── status line ───────────────────────────────────────────────
        self._status = QLabel("")
        self._status.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
        self._status.setWordWrap(True)
        inner.addWidget(self._status)

        # ── buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        self._back_btn = NeonButton("", style="glass")
        self._next_btn = NeonButton("", style="cyan", glow=True)
        self._back_btn.setVisible(False)
        btn_row.addWidget(self._back_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._next_btn)
        inner.addLayout(btn_row)

        self._back_btn.clicked.connect(self._back)
        self._next_btn.clicked.connect(self._next)

        scroll.setWidget(card)

    # ── navigation ────────────────────────────────────────────────────
    def _pill_style(self, state: str) -> str:
        if state == "active":
            return (f"color: #020202; background: {CYAN};"
                    f" border: 1px solid {CYAN}; border-radius: 18px;"
                    f" padding: 6px 14px; font-weight: 700; letter-spacing: 1px;")
        if state == "done":
            return (f"color: {CYAN}; background: rgba(0,212,255,10);"
                    f" border: 1px solid rgba(0,212,255,40); border-radius: 18px;"
                    f" padding: 6px 14px; font-weight: 700; letter-spacing: 1px;")
        return (f"color: {MUTED}; background: rgba(255,255,255,4);"
                f" border: 1px solid rgba(255,255,255,10); border-radius: 18px;"
                f" padding: 6px 14px; font-weight: 600; letter-spacing: 1px;")

    def retranslate(self) -> None:
        """Reapply all visible strings — called on init and on language switch."""
        labels = (tr("step.1"), tr("step.2"), tr("step.3"))
        for i, pill in enumerate(self._pills):
            pill.setText(f"  {i+1}  ·  {labels[i]}  ")
            if i < self._step:
                pill.setStyleSheet(self._pill_style("done"))
            elif i == self._step:
                pill.setStyleSheet(self._pill_style("active"))
            else:
                pill.setStyleSheet(self._pill_style("pending"))
        for sep in self._pill_seps:
            sep.setStyleSheet(f"color: {MUTED}; padding: 0 4px;")

        keys = [
            ("w.step1.title", "w.step1.sub", "w.step1.howto"),
            ("w.step2.title", "w.step2.sub", "w.step2.howto"),
            ("w.step3.title", "w.step3.sub", ""),
        ]
        title_k, sub_k, howto_k = keys[self._step]
        self._title_lbl.setText(tr(title_k))
        self._sub_lbl.setText(tr(sub_k))
        if howto_k:
            self._howto_lbl.setText(tr(howto_k))
            self._howto_lbl.setVisible(True)
        else:
            self._howto_lbl.setVisible(False)

        self._token_in.setPlaceholderText(tr("w.step1.input.placeholder"))
        self._add_pair_btn.setText(tr("w.step2.add"))
        self._renumber_pairs()  # refreshes placeholder text + pair labels

        self._inputs.setCurrentIndex(self._step)
        self._back_btn.setVisible(self._step > 0)
        self._back_btn.setText(tr("w.btn.back"))
        self._next_btn.setText(tr("w.btn.save") if self._step == 2 else tr("w.btn.next"))
        self._status.setText("")

        if self._step == 2 and self._channels:
            token_preview = self._token[:12] + "…" if len(self._token) > 12 else self._token
            html = [f"<b style='color:{WHITE}'>{tr('w.review.token')}:</b> <code>{token_preview}</code>"]
            for i, ch in enumerate(self._channels, start=1):
                html.append(
                    f"<br><br><b style='color:{CYAN}'>{tr('w.step2.pair', i)}</b><br>"
                    f"<b style='color:{WHITE}'>{tr('w.review.channel')}:</b> {ch['channel']}<br>"
                    f"<b style='color:{WHITE}'>{tr('w.review.playlist')}:</b> <code>{ch['playlist']}</code>"
                )
            self._review_lbl.setText("".join(html))

    # Old name kept for the internal navigation callers
    def _refresh(self) -> None:
        self.retranslate()

    def _back(self) -> None:
        if self._step > 0:
            self._step -= 1
            self._refresh()

    # ── multi-pair management for step 2 ──────────────────────────────
    def _add_pair(self, channel: str = "", playlist: str = "") -> None:
        frame = QFrame()
        frame.setStyleSheet(
            "QFrame { background: rgba(255,255,255,4);"
            " border: 1px solid rgba(255,255,255,10);"
            " border-radius: 12px; }")
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 14)
        lay.setSpacing(8)

        header = QHBoxLayout()
        idx_lbl = QLabel()
        idx_lbl.setStyleSheet(
            f"color: {CYAN}; font-size: 10px; font-weight: 700; letter-spacing: 2px;")
        header.addWidget(idx_lbl)
        header.addStretch()
        remove_btn = QPushButton()
        remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_btn.setFixedSize(QSize(28, 24))
        remove_btn.setStyleSheet(
            f"QPushButton {{ color: {MAGENTA}; background: rgba(247,37,133,12);"
            f" border: 1px solid rgba(247,37,133,30); border-radius: 8px;"
            f" font-size: 16px; font-weight: 700; }}"
            f"QPushButton:hover {{ background: rgba(247,37,133,24); }}")
        header.addWidget(remove_btn)
        lay.addLayout(header)

        chan = QLineEdit(channel);   chan.setMinimumHeight(42)
        plist = QLineEdit(playlist); plist.setMinimumHeight(42)
        lay.addWidget(chan); lay.addWidget(plist)

        # Test-channel row: a button + a status label
        test_row = QHBoxLayout(); test_row.setSpacing(8)
        test_btn = NeonButton("", style="glass")
        test_btn.setMinimumHeight(34)
        test_btn.setMaximumWidth(150)
        test_status = QLabel("")
        test_status.setWordWrap(True)
        test_status.setStyleSheet(f"color: {TEXT}; font-size: 11px;")
        test_row.addWidget(test_btn)
        test_row.addWidget(test_status, 1)
        lay.addLayout(test_row)

        row = {"frame": frame, "idx_lbl": idx_lbl,
               "chan": chan, "plist": plist, "remove": remove_btn,
               "test_btn": test_btn, "test_status": test_status,
               "test_worker": None}
        remove_btn.clicked.connect(lambda: self._remove_pair(row))
        test_btn.clicked.connect(lambda: self._test_channel(row))
        self._pair_rows.append(row)
        self._pairs_layout.addWidget(frame)
        self._renumber_pairs()

    def _remove_pair(self, row: dict) -> None:
        if len(self._pair_rows) <= 1:
            return  # keep at least one pair
        self._pair_rows.remove(row)
        row["frame"].deleteLater()
        self._renumber_pairs()

    def _renumber_pairs(self) -> None:
        for i, row in enumerate(self._pair_rows, start=1):
            row["idx_lbl"].setText(tr("w.step2.pair", i))
            row["chan"].setPlaceholderText(tr("w.step2.chan.placeholder"))
            row["plist"].setPlaceholderText(tr("w.step2.plist.placeholder"))
            row["remove"].setVisible(len(self._pair_rows) > 1)
            row["test_btn"].setText(tr("w.test.btn"))

    def _test_channel(self, row: dict) -> None:
        if row.get("test_worker") and row["test_worker"].isRunning():
            return
        token   = self._token or self._token_in.text().strip()
        channel = normalise_handle(row["chan"].text())
        if ":" not in token or not channel.startswith("@"):
            row["test_status"].setStyleSheet(f"color: {AMBER}; font-size: 11px;")
            row["test_status"].setText(tr("w.test.need"))
            return

        row["test_status"].setStyleSheet(f"color: {TEXT}; font-size: 11px;")
        row["test_status"].setText(tr("w.test.checking", channel))
        row["test_btn"].setEnabled(False)

        worker = TestWorker(token, channel)

        def _on_result(ok: bool, info: str) -> None:
            row["test_btn"].setEnabled(True)
            if ok:
                row["test_status"].setStyleSheet(f"color: {SUCCESS}; font-size: 11px;")
                row["test_status"].setText(tr("w.test.ok", info))
            else:
                row["test_status"].setStyleSheet(f"color: {ERROR}; font-size: 11px;")
                row["test_status"].setText(tr("w.test.fail", info[:120]))

        worker.result.connect(_on_result)
        row["test_worker"] = worker
        worker.start()

    def _next(self) -> None:
        if self._step == 0:
            token = self._token_in.text().strip()
            if ":" not in token or len(token) < 20:
                self._err(tr("w.err.token"))
                return
            self._token = token
            self._step = 1

        elif self._step == 1:
            channels: list[dict] = []
            for i, row in enumerate(self._pair_rows, start=1):
                chan  = normalise_handle(row["chan"].text())
                plist = extract_playlist_id(row["plist"].text())
                raw_chan = row["chan"].text().strip()
                if not raw_chan or not chan.startswith("@"):
                    self._err(tr("w.err.channel") + f"  ({tr('w.step2.pair', i)})")
                    return
                if not plist:
                    self._err(tr("w.err.playlist") + f"  ({tr('w.step2.pair', i)})")
                    return
                channels.append({"channel": chan, "playlist": plist})
            self._channels = channels
            self._step = 2

        elif self._step == 2:
            self._save()
            self.finished.emit()
            return

        self._refresh()

    def _err(self, msg: str) -> None:
        self._status.setStyleSheet(f"color: {ERROR}; font-size: 12px;")
        self._status.setText(msg)

    def _save(self) -> None:
        lines = [f"TELEGRAM_BOT_TOKEN={self._token}"]
        for i, ch in enumerate(self._channels, start=1):
            # NB: PLAYLIST stores the *bare* PL... ID, not the full URL —
            # the bot reconstructs `https://www.youtube.com/playlist?list={id}`.
            lines.append(f"CHANNEL_{i}_NAME=channel{i}")
            lines.append(f"CHANNEL_{i}_PLAYLIST={ch.get('playlist', '')}")
            lines.append(f"CHANNEL_{i}_TELEGRAM={ch.get('channel', '')}")
        ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════
#  Dashboard
# ══════════════════════════════════════════════════════════════════════
class DashboardPage(QWidget):
    go_config = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker: Optional[BotWorker] = None
        self._posted = 0
        self._failed = 0
        self._build()
        self.retranslate()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(32, 16, 32, 20)
        lay.setSpacing(14)

        # ── header row ────────────────────────────────────────────────
        hdr = QHBoxLayout()
        self._status_badge = StatusBadge()
        hdr.addWidget(self._status_badge)
        hdr.addStretch()

        env_ok = ENV_PATH.exists()
        self._env_lbl = QLabel()
        self._env_lbl.setStyleSheet(
            f"color: {SUCCESS}; font-size: 11px;" if env_ok
            else f"color: {AMBER}; font-size: 11px;"
        )
        hdr.addWidget(self._env_lbl)
        lay.addLayout(hdr)

        # ── static neon divider (replaces the animated equalizer) ─────
        divider = NeonDivider()
        lay.addWidget(divider)

        # ── action buttons + one-line hints under each ────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self._btn_watch = NeonButton("", style="cyan",   glow=True)
        self._btn_once  = NeonButton("", style="purple", glow=True)
        self._btn_check = NeonButton("", style="glass")
        self._btn_stop  = NeonButton("", style="danger")
        self._btn_conf  = NeonButton("", style="glass")
        def _stack(btn: NeonButton) -> tuple[QWidget, QLabel]:
            box = QWidget()
            v = QVBoxLayout(box); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(4)
            v.addWidget(btn)
            hint = QLabel("")
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(
                f"color: {TEXT}; font-size: 11px; line-height: 1.3;"
                " font-style: italic;")
            v.addWidget(hint)
            return box, hint

        box_watch, self._hint_watch = _stack(self._btn_watch)
        box_once,  self._hint_once  = _stack(self._btn_once)
        box_check, self._hint_check = _stack(self._btn_check)
        box_stop,  self._hint_stop  = _stack(self._btn_stop)
        box_conf,  self._hint_conf  = _stack(self._btn_conf)
        self._stop_box = box_stop
        self._stop_box.setVisible(False)
        for b in (box_watch, box_once, box_check, box_stop, box_conf):
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        # ── MP3 bitrate selector ──────────────────────────────────────
        br_row = QHBoxLayout(); br_row.setSpacing(8)
        self._br_label = QLabel()
        self._br_label.setStyleSheet(f"color: {WHITE}; font-size: 12px; font-weight: 600;")
        br_row.addWidget(self._br_label)
        self._bitrate = read_env_value("AUDIO_BITRATE", "192")
        if self._bitrate not in ("128", "192", "320"):
            self._bitrate = "192"
        self._br_btns: dict[str, QPushButton] = {}
        for rate in ("128", "192", "320"):
            b = QPushButton(f"{rate}")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(True)
            b.setFixedSize(QSize(56, 30))
            b.clicked.connect(lambda _, r=rate: self._set_bitrate(r))
            self._br_btns[rate] = b
            br_row.addWidget(b)
        self._br_hint = QLabel()
        self._br_hint.setWordWrap(True)
        self._br_hint.setStyleSheet(f"color: {TEXT}; font-size: 10px; font-style: italic;")
        br_row.addWidget(self._br_hint, 1)
        lay.addLayout(br_row)
        self._restyle_bitrate()

        # ── progress bar (visible only during a run) ──────────────────
        self._progress = QProgressBar()
        self._progress.setMinimumHeight(22)
        self._progress.setTextVisible(True)
        self._progress.setFormat("")
        self._progress.setStyleSheet(
            "QProgressBar {"
            f" background: rgba(0,0,0,140); border: 1px solid rgba(0,212,255,28);"
            f" border-radius: 8px; color: {WHITE}; font-size: 11px;"
            " font-weight: 600; text-align: center; }"
            "QProgressBar::chunk {"
            " background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"  stop:0 {MAGENTA}, stop:0.5 {PURPLE}, stop:1 {CYAN});"
            " border-radius: 7px; }")
        self._progress.setVisible(False)
        self._progress_total = 0
        lay.addWidget(self._progress)

        # ── stats cards ───────────────────────────────────────────────
        stats_row = QHBoxLayout(); stats_row.setSpacing(10)
        self._n_posted,  self._lbl_posted  = self._stat_card(stats_row, CYAN)
        self._n_failed,  self._lbl_failed  = self._stat_card(stats_row, MAGENTA)
        self._n_session, self._lbl_session = self._stat_card(stats_row, PURPLE)
        self._session_runs = 0
        lay.addLayout(stats_row)

        # ── inline "Add another channel + playlist" panel ─────────────
        self._add_card = GlassCard()
        add_lay = QVBoxLayout(self._add_card)
        add_lay.setContentsMargins(18, 14, 18, 14)
        add_lay.setSpacing(8)

        self._add_title = QLabel()
        self._add_title.setStyleSheet(
            f"color: {CYAN}; font-size: 12px; font-weight: 700; letter-spacing: 1.5px;")
        add_lay.addWidget(self._add_title)

        self._add_note = QLabel()
        self._add_note.setStyleSheet(f"color: {TEXT}; font-size: 11px;")
        self._add_note.setWordWrap(True)
        add_lay.addWidget(self._add_note)

        add_row = QHBoxLayout(); add_row.setSpacing(8)
        self._add_chan  = QLineEdit(); self._add_chan.setMinimumHeight(38)
        self._add_plist = QLineEdit(); self._add_plist.setMinimumHeight(38)
        self._add_btn   = NeonButton("", style="cyan")
        self._add_btn.setMinimumHeight(38)
        self._add_btn.clicked.connect(self._add_inline_pair)
        add_row.addWidget(self._add_chan, 2)
        add_row.addWidget(self._add_plist, 3)
        add_row.addWidget(self._add_btn, 0)
        add_lay.addLayout(add_row)

        self._add_status = QLabel("")
        self._add_status.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
        self._add_status.setWordWrap(True)
        add_lay.addWidget(self._add_status)
        lay.addWidget(self._add_card)

        # ── log ───────────────────────────────────────────────────────
        log_hdr = QHBoxLayout()
        self._log_title = QLabel()
        self._log_title.setStyleSheet(f"color: {WHITE}; font-size: 13px;"
                                " letter-spacing: 3px; font-weight: 700;")
        # Simple / Expert toggle
        self._simple_mode = True
        self._raw_lines: list[str] = []   # full history for re-render on toggle
        self._mode_btn = QPushButton()
        self._mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mode_btn.setCheckable(True)
        self._mode_btn.setFixedHeight(24)
        self._mode_btn.clicked.connect(self._toggle_mode)
        self._btn_clear = QPushButton()
        self._btn_clear.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; background: transparent;"
            " border: none; padding: 0; cursor: pointer;")
        self._btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear.clicked.connect(self._clear_log)
        log_hdr.addWidget(self._log_title)
        log_hdr.addStretch()
        log_hdr.addWidget(self._mode_btn)
        log_hdr.addSpacing(14)
        log_hdr.addWidget(self._btn_clear)
        lay.addLayout(log_hdr)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(160)
        # Bound memory on multi-hour Watch sessions — keep only the last
        # 2000 lines instead of letting the document grow unbounded.
        self._log.document().setMaximumBlockCount(2000)
        lay.addWidget(self._log)
        self._restyle_mode_btn()

        # ── wiring ────────────────────────────────────────────────────
        self._btn_watch.clicked.connect(lambda: self._start("watch"))
        self._btn_once.clicked.connect( lambda: self._start("once"))
        self._btn_check.clicked.connect(lambda: self._start("check"))
        self._btn_stop.clicked.connect(self._stop)
        self._btn_conf.clicked.connect(self.go_config)

        self._log_line(tr("d.ready"), system=True)
        if not ENV_PATH.exists():
            self._log_line(tr("d.no_env"), system=True)

    def retranslate(self) -> None:
        env_ok = ENV_PATH.exists()
        self._env_lbl.setText(tr("d.cfg.ok") if env_ok else tr("d.cfg.miss"))
        self._btn_watch.setText(tr("d.btn.watch"))
        self._btn_once.setText(tr("d.btn.once"))
        self._btn_check.setText(tr("d.btn.check"))
        self._btn_stop.setText(tr("d.btn.stop"))
        self._btn_conf.setText(tr("d.btn.config"))
        # One-line hint shown below each button + tooltip on hover
        for btn, hint, key in [
            (self._btn_watch, self._hint_watch, "d.hint.watch"),
            (self._btn_once,  self._hint_once,  "d.hint.once"),
            (self._btn_check, self._hint_check, "d.hint.check"),
            (self._btn_stop,  self._hint_stop,  "d.hint.stop"),
            (self._btn_conf,  self._hint_conf,  "d.hint.config"),
        ]:
            hint.setText(tr(key))
            btn.setToolTip(tr(key))
        self._lbl_posted.setText(tr("d.stat.posted"))
        self._lbl_failed.setText(tr("d.stat.failed"))
        self._lbl_session.setText(tr("d.stat.runs"))
        self._log_title.setText(tr("d.log.title"))
        self._btn_clear.setText(tr("d.log.clear"))
        self._br_label.setText(tr("d.bitrate"))
        self._br_hint.setText(tr("d.bitrate.hint"))
        self._restyle_mode_btn()
        # Inline add-pair card
        self._add_title.setText(tr("d.add.title"))
        self._add_note.setText(tr("d.add.note"))
        self._add_btn.setText(tr("d.add.btn"))
        self._add_chan.setPlaceholderText(tr("w.step2.chan.placeholder"))
        self._add_plist.setPlaceholderText(tr("w.step2.plist.placeholder"))
        self._status_badge.retranslate()

    # ── stat card helper ──────────────────────────────────────────────
    def _stat_card(self, row: QHBoxLayout, color: str) -> tuple[QLabel, QLabel]:
        card = GlassCard()
        card.setMinimumHeight(86)
        cl = QVBoxLayout(card); cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.setSpacing(4)
        num = QLabel("0")
        num.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet(f"color: {color};")
        lbl = QLabel("")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {WHITE}; font-size: 13px;"
                          " font-weight: 600; letter-spacing: 2.5px;")
        cl.addWidget(num); cl.addWidget(lbl)
        row.addWidget(card)
        return num, lbl

    # ── bot control ───────────────────────────────────────────────────
    def _start(self, mode: str) -> None:
        if self._worker and self._worker.isRunning():
            return

        self._worker = BotWorker(mode)
        self._worker.log.connect(self._log_line)
        self._worker.done.connect(self._on_done)
        self._worker.start()

        self._session_runs += 1
        self._n_session.setText(str(self._session_runs))
        # Reset per-run counters so the numbers reflect THIS run, not a
        # cumulative total across every run of the session.
        self._posted = 0
        self._failed = 0
        self._n_posted.setText("0")
        self._n_failed.setText("0")
        self._progress_total = 0
        self._progress.setValue(0)
        self._progress.setFormat("")
        self._progress.setVisible(False)
        self._status_badge.set_running()
        for b in [self._btn_watch, self._btn_once, self._btn_check]:
            b.setEnabled(False)
        self._stop_box.setVisible(True)
        self._log_line(tr("d.starting", mode.upper()), system=True)

    def _stop(self) -> None:
        if self._worker:
            self._worker.stop()
        self._log_line(tr("d.stopped"), system=True)
        self._on_done(True)

    def _on_done(self, ok: bool) -> None:
        for b in [self._btn_watch, self._btn_once, self._btn_check]:
            b.setEnabled(True)
        self._stop_box.setVisible(False)
        self._progress.setVisible(False)
        if ok:
            self._status_badge.set_done()
        else:
            self._status_badge.set_error()

    # ── log mode ──────────────────────────────────────────────────────
    def _restyle_mode_btn(self) -> None:
        label = tr("d.mode.simple") if self._simple_mode else tr("d.mode.expert")
        self._mode_btn.setText(f"◧ {label}")
        on = self._simple_mode
        self._mode_btn.setStyleSheet(
            f"QPushButton {{ color: {'#020202' if on else WHITE};"
            f"  background: {CYAN if on else 'rgba(255,255,255,6)'};"
            f"  border: 1px solid {'rgba(0,212,255,80)' if on else 'rgba(255,255,255,16)'};"
            f"  border-radius: 8px; padding: 2px 12px; font-size: 11px; font-weight: 700; }}"
            f"QPushButton:hover {{ background: {'#30eaff' if on else 'rgba(255,255,255,12)'}; }}")

    # ── bitrate ───────────────────────────────────────────────────────
    def _restyle_bitrate(self) -> None:
        for rate, btn in self._br_btns.items():
            on = (rate == self._bitrate)
            btn.setChecked(on)
            btn.setStyleSheet(
                f"QPushButton {{ color: {'#020202' if on else WHITE};"
                f"  background: {CYAN if on else 'rgba(255,255,255,6)'};"
                f"  border: 1px solid {'rgba(0,212,255,80)' if on else 'rgba(255,255,255,16)'};"
                f"  border-radius: 8px; font-size: 12px; font-weight: 700; }}"
                f"QPushButton:hover {{ background: {'#30eaff' if on else 'rgba(255,255,255,12)'}; }}")

    def _set_bitrate(self, rate: str) -> None:
        self._bitrate = rate
        self._restyle_bitrate()
        set_env_value("AUDIO_BITRATE", rate)
        self._log_line(f"[cfg] MP3 = {rate} kbps", system=True)

    def _toggle_mode(self) -> None:
        self._simple_mode = not self._simple_mode
        self._restyle_mode_btn()
        # Re-render the whole buffer under the new mode
        self._log.clear()
        for raw in self._raw_lines:
            self._render(raw, store=False)
        sb: QScrollBar = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_log(self) -> None:
        self._raw_lines.clear()
        self._log.clear()

    # ── log line processing ───────────────────────────────────────────
    _POSTED_RX   = _re.compile(r"\]\s*\[(\d+)/(\d+)\]\s*Posted:\s*(.*)$")
    _DL_RX       = _re.compile(r"\]\s*\[(\d+)/(\d+)\]\s*Downloading:")
    _FAILED_RX   = _re.compile(r"]\s*Failed to process\s")
    _NEW_RX      = _re.compile(r"]\s*(\d+)\s+new video")
    _NONEW_RX    = _re.compile(r"No new videos")
    _SKIP_RX     = _re.compile(r"Too large for Telegram")

    def _log_line(self, text: str, system: bool = False) -> None:
        txt = text.strip()

        # GUI-origin status messages (ready / starting / stopped) are already
        # user-friendly — always show them verbatim, even in Simple mode.
        if system:
            self._raw_lines.append(txt)
            self._log.append(f'<span style="color:{CYAN}">{txt}</span>')
            sb: QScrollBar = self._log.verticalScrollBar()
            sb.setValue(sb.maximum())
            return

        # ── live counters ──
        m_posted = self._POSTED_RX.search(txt)
        if m_posted:
            self._posted += 1
            self._n_posted.setText(str(self._posted))
        elif self._FAILED_RX.search(txt) or self._SKIP_RX.search(txt):
            self._failed += 1
            self._n_failed.setText(str(self._failed))

        # ── progress bar from [i/N] ──
        m_prog = self._DL_RX.search(txt) or self._POSTED_RX.search(txt)
        if m_prog:
            i, n = int(m_prog.group(1)), int(m_prog.group(2))
            if n > 0:
                self._progress_total = n
                self._progress.setMaximum(n)
                self._progress.setValue(i)
                self._progress.setFormat(tr("d.progress", i, n))
                self._progress.setVisible(True)

        self._render(txt, store=True)

    def _render(self, txt: str, store: bool) -> None:
        if store:
            self._raw_lines.append(txt)
            if len(self._raw_lines) > 2000:
                del self._raw_lines[:len(self._raw_lines) - 2000]

        if self._simple_mode:
            friendly = self._simplify(txt)
            if friendly is None:
                return  # hidden in simple mode
            colour, body = friendly
            self._log.append(f'<span style="color:{colour}">{body}</span>')
        else:
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            low = txt.lower()
            if any(k in low for k in ("error", "fail", "exception", "traceback")):
                colour = ERROR
            elif any(k in low for k in ("✓", "posted", "success", "done", " ok ")):
                colour = SUCCESS
            elif any(k in low for k in ("warn", "skip", "too large")):
                colour = AMBER
            else:
                colour = "#6a7590"
            esc = txt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            self._log.append(
                f'<span style="color:{MUTED}">[{ts}]</span> '
                f'<span style="color:{colour}">{esc}</span>')

        sb: QScrollBar = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _simplify(self, txt: str):
        """Map a raw log line to (colour, friendly_text) — or None to hide.

        Used in 'Simple' mode so a non-technical user sees only the
        meaningful events, not yt-dlp internals or Python tracebacks.
        """
        m = self._POSTED_RX.search(txt)
        if m:
            return SUCCESS, tr("d.s.posted", m.group(3).strip())
        m = self._NEW_RX.search(txt)
        if m:
            return CYAN, tr("d.s.new", m.group(1))
        if self._NONEW_RX.search(txt):
            return TEXT, tr("d.s.nonew")
        if self._SKIP_RX.search(txt):
            return AMBER, "⚠ " + txt.split("] ", 1)[-1]
        if "Bot token OK" in txt or "connected as @" in txt:
            return SUCCESS, tr("d.s.connected")
        if "Fetching playlist" in txt or "Playlist fetched" in txt:
            return TEXT, tr("d.s.checking")
        if self._FAILED_RX.search(txt):
            return ERROR, tr("d.s.error")
        # Hide everything else (tracebacks, yt-dlp noise, [exec], etc.)
        return None

    # ── inline add-pair ──────────────────────────────────────────────
    def _add_inline_pair(self) -> None:
        chan  = normalise_handle(self._add_chan.text())
        plist = extract_playlist_id(self._add_plist.text())
        if not chan.startswith("@") or not self._add_chan.text().strip():
            self._add_status.setStyleSheet(f"color: {ERROR}; font-size: 12px;")
            self._add_status.setText(tr("w.err.channel"))
            return
        if not plist:
            self._add_status.setStyleSheet(f"color: {ERROR}; font-size: 12px;")
            self._add_status.setText(tr("w.err.playlist"))
            return

        # Read existing .env, find highest CHANNEL_N_, append a new one
        existing = ENV_PATH.read_text(encoding="utf-8", errors="ignore") \
            if ENV_PATH.exists() else ""
        next_idx = 1
        for m in _re.finditer(r"^CHANNEL_(\d+)_PLAYLIST=", existing, _re.MULTILINE):
            next_idx = max(next_idx, int(m.group(1)) + 1)

        addition = (
            f"CHANNEL_{next_idx}_NAME=channel{next_idx}\n"
            f"CHANNEL_{next_idx}_PLAYLIST={plist}\n"
            f"CHANNEL_{next_idx}_TELEGRAM={chan}\n"
        )
        if existing and not existing.endswith("\n"):
            existing += "\n"
        ENV_PATH.write_text(existing + addition, encoding="utf-8")

        self._add_chan.clear()
        self._add_plist.clear()
        self._add_status.setStyleSheet(f"color: {SUCCESS}; font-size: 12px;")
        self._add_status.setText(tr("d.add.ok", next_idx))
        self._log_line(f"[+] Added pair #{next_idx}: {chan} ← {plist}", system=True)


# ══════════════════════════════════════════════════════════════════════
#  Main Window
# ══════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Space Music Hub")
        self.setMinimumSize(960, 640)
        self.resize(1120, 740)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

        self._force_quit = False
        self._setup_layers()
        self._setup_nav()
        self._setup_pages()
        self._goto_initial()
        self._setup_tray()
        if START_HIDDEN:
            # Launched with --tray (e.g. from Windows startup) — stay hidden,
            # auto-resume Watch mode if config exists.
            QTimer.singleShot(800, self._autostart_watch)

    # ── layer stack ───────────────────────────────────────────────────
    def _setup_layers(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet(f"background: {BG};")

        # Background layer (z=0) — static frame, no video decode
        bg_src = next((p for p in BG_IMAGE_PATHS if p.exists()), None)
        if bg_src is not None:
            self._vid_widget = StaticBackgroundWidget(str(bg_src), central)
        else:
            self._vid_widget = QWidget(central)
            self._vid_widget.setStyleSheet(f"background: {BG};")
        self._vid_widget.setGeometry(0, 0, self.width(), self.height())

        # Dark overlay (z=1)
        self._overlay = QWidget(central)
        self._overlay.setStyleSheet("background: rgba(5,5,5,160);")
        self._overlay.setGeometry(0, 0, self.width(), self.height())

        # Content layer (z=2) — holds nav + page stack
        self._content = QWidget(central)
        self._content.setStyleSheet("background: transparent;")
        self._content.setGeometry(0, 0, self.width(), self.height())
        self._content.raise_()

        self._content_lay = QVBoxLayout(self._content)
        self._content_lay.setContentsMargins(0, 0, 0, 0)
        self._content_lay.setSpacing(0)

    # ── nav bar ───────────────────────────────────────────────────────
    def _setup_nav(self) -> None:
        nav = QWidget()
        nav.setFixedHeight(58)
        nav.setStyleSheet(
            "QWidget { background: rgba(5,5,5,130);"
            " border-bottom: 1px solid rgba(255,255,255,7); }")
        lay = QHBoxLayout(nav)
        lay.setContentsMargins(22, 0, 22, 0)
        lay.setSpacing(10)

        if LOGO_PATH.exists():
            logo = QLabel()
            logo.setPixmap(QIcon(str(LOGO_PATH)).pixmap(QSize(32, 32)))
            logo.setStyleSheet("background: transparent; border: none;")
            lay.addWidget(logo)

        title = QLabel("Space Music Hub")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {WHITE}; background: transparent; border: none;")
        lay.addWidget(title)
        lay.addStretch()

        # Language switcher — three small pills RU / EN / LV
        self._lang_btns: dict[str, QPushButton] = {}
        for code, label in [("ru", "RU"), ("en", "EN"), ("lv", "LV")]:
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setCheckable(True)
            b.setChecked(LANG == code)
            b.setFixedSize(QSize(34, 26))
            b.clicked.connect(lambda _, c=code: self._switch_lang(c))
            self._lang_btns[code] = b
            lay.addWidget(b)
        self._restyle_lang_btns()

        badge = QLabel("v2.0 · GUI")
        badge.setStyleSheet(
            f"color: {CYAN}; background: rgba(0,212,255,10);"
            f" border: 1px solid rgba(0,212,255,28);"
            f" border-radius: 8px; padding: 4px 10px;"
            f" font-size: 10px; font-weight: 700; letter-spacing: 1px;"
            f" margin-left: 12px;")
        lay.addWidget(badge)

        self._content_lay.addWidget(nav)

    def _restyle_lang_btns(self) -> None:
        for code, btn in self._lang_btns.items():
            on = (LANG == code)
            btn.setChecked(on)
            btn.setStyleSheet(
                f"QPushButton {{"
                f"  background: {CYAN if on else 'rgba(255,255,255,5)'};"
                f"  color: {('#020202' if on else WHITE)};"
                f"  border: 1px solid {('rgba(0,212,255,80)' if on else 'rgba(255,255,255,14)')};"
                f"  border-radius: 8px;"
                f"  font-size: 10px; font-weight: 800; letter-spacing: 1px;"
                f"}}"
                f"QPushButton:hover {{ background: {('#30eaff' if on else 'rgba(255,255,255,12)')}; }}"
            )

    def _switch_lang(self, code: str) -> None:
        if code == LANG:
            return
        set_lang(code)
        self._restyle_lang_btns()
        self._wizard.retranslate()
        self._dashboard.retranslate()
        if self._tray:
            self._build_tray_menu()

    # ── page stack ────────────────────────────────────────────────────
    def _setup_pages(self) -> None:
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        self._wizard    = WizardPage()
        self._dashboard = DashboardPage()

        self._wizard.finished.connect(self._to_dashboard)
        self._dashboard.go_config.connect(self._to_wizard)

        self._stack.addWidget(self._wizard)     # index 0
        self._stack.addWidget(self._dashboard)  # index 1
        self._content_lay.addWidget(self._stack)

    def _goto_initial(self) -> None:
        if ENV_PATH.exists() and "TELEGRAM_BOT_TOKEN=" in ENV_PATH.read_text(
                encoding="utf-8", errors="ignore"):
            self._stack.setCurrentIndex(1)
        else:
            self._stack.setCurrentIndex(0)

    def _to_dashboard(self) -> None:
        self._stack.setCurrentIndex(1)

    def _to_wizard(self) -> None:
        self._stack.setCurrentIndex(0)

    # ── resize ────────────────────────────────────────────────────────
    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        w, h = self.width(), self.height()
        self._vid_widget.setGeometry(0, 0, w, h)
        self._overlay.setGeometry(0, 0, w, h)
        self._content.setGeometry(0, 0, w, h)

    # ── system tray + background mode ─────────────────────────────────
    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = None
            return

        icon = QIcon(str(LOGO_ICO)) if LOGO_ICO.exists() else \
               QIcon(str(LOGO_PATH)) if LOGO_PATH.exists() else QIcon()
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("Space Music Hub")
        self._build_tray_menu()
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _build_tray_menu(self) -> None:
        if not self._tray:
            return
        menu = QMenu()
        act_show  = QAction(tr("tray.open"),  self)
        act_watch = QAction(tr("tray.watch"), self)
        act_stop  = QAction(tr("tray.stop"),  self)
        act_quit  = QAction(tr("tray.quit"),  self)
        act_show.triggered.connect(self._show_from_tray)
        act_watch.triggered.connect(lambda: self._dashboard._start("watch"))
        act_stop.triggered.connect(self._dashboard._stop)
        act_quit.triggered.connect(self._quit_for_real)
        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_watch)
        menu.addAction(act_stop)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)

    def _on_tray_activated(self, reason) -> None:
        # Double-click on the tray icon → toggle window
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self._show_from_tray()

    def _show_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self.setWindowState(
            self.windowState() & ~Qt.WindowState.WindowMinimized
            | Qt.WindowState.WindowActive
        )

    def _autostart_watch(self) -> None:
        """Called on --tray boot: start Watch mode silently if config exists."""
        if ENV_PATH.exists() and "TELEGRAM_BOT_TOKEN=" in ENV_PATH.read_text(
                encoding="utf-8", errors="ignore"):
            self._dashboard._start("watch")

    def _quit_for_real(self) -> None:
        self._force_quit = True
        if self._dashboard._worker:
            self._dashboard._worker.stop()
        if self._tray:
            self._tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event) -> None:  # noqa: N802
        """Close button → hide to tray; only exit via tray Quit menu."""
        if self._force_quit or not self._tray:
            event.accept()
            return
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "Space Music Hub",
            tr("tray.hidden"),
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )


# ══════════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════════
def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Space Music Hub")
    app.setStyleSheet(QSS)
    # Critical for tray-only mode: don't exit when last window closes.
    app.setQuitOnLastWindowClosed(False)
    if LOGO_ICO.exists():
        app.setWindowIcon(QIcon(str(LOGO_ICO)))
    elif LOGO_PATH.exists():
        app.setWindowIcon(QIcon(str(LOGO_PATH)))

    win = MainWindow()
    if not START_HIDDEN:
        win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
