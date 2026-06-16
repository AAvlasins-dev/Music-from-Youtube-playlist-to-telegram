"""Unit tests for the GUI layer (gui_app.py).

These cover the pure, GUI-framework-independent building blocks that the
desktop app relies on — input normalisers, the .env read/write helpers,
and the log-line parsers that drive the live counters and progress bar.
No QApplication or widgets are constructed here.

The GUI dispatch guard in gui_app.py exits early only for --bot-* flags,
which pytest never passes, so importing the module is safe.
"""
from __future__ import annotations

import importlib
import os
import sys

import pytest

# Qt needs an offscreen platform plugin on headless machines (CI).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Skip the whole module gracefully if the GUI stack can't be imported
# (e.g. a CI box missing the Qt system libraries). The bot tests still run.
try:
    gui = importlib.import_module("gui_app")
except Exception as exc:  # noqa: BLE001
    pytest.skip(f"gui_app unavailable ({exc})", allow_module_level=True)


# --------------------------------------------------------------------------- #
# Input normalisers — must mirror the bot's own helpers
# --------------------------------------------------------------------------- #
class TestExtractPlaylistId:
    @pytest.mark.parametrize("text,expected", [
        ("https://www.youtube.com/playlist?list=PLabc123", "PLabc123"),
        ("https://music.youtube.com/playlist?list=RDxyz", "RDxyz"),
        ("https://www.youtube.com/watch?v=foo&list=PLbar&index=2", "PLbar"),
        ("PLbareId", "PLbareId"),
        ("  PLwhitespace  ", "PLwhitespace"),
    ])
    def test_extract(self, text, expected):
        assert gui.extract_playlist_id(text) == expected


class TestNormaliseHandle:
    @pytest.mark.parametrize("text,expected", [
        ("@my_channel", "@my_channel"),
        ("my_channel", "@my_channel"),
        ("https://t.me/my_channel", "@my_channel"),
        ("  @spaced  ", "@spaced"),
        ("", ""),
    ])
    def test_normalise(self, text, expected):
        assert gui.normalise_handle(text) == expected


# --------------------------------------------------------------------------- #
# .env read / write helpers (used by the schedule + inline-add features)
# --------------------------------------------------------------------------- #
class TestEnvHelpers:
    def test_read_missing_returns_default(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gui, "ENV_PATH", tmp_path / ".env")
        assert gui.read_env_value("WATCH_INTERVAL", "3600") == "3600"

    def test_set_then_read_roundtrip(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("TELEGRAM_BOT_TOKEN=abc\n", encoding="utf-8")
        monkeypatch.setattr(gui, "ENV_PATH", env)
        gui.set_env_value("WATCH_INTERVAL", "86400")
        assert gui.read_env_value("WATCH_INTERVAL") == "86400"

    def test_set_updates_in_place_no_duplicate(self, tmp_path, monkeypatch):
        env = tmp_path / ".env"
        env.write_text("WATCH_INTERVAL=3600\nTELEGRAM_BOT_TOKEN=abc\n", encoding="utf-8")
        monkeypatch.setattr(gui, "ENV_PATH", env)
        gui.set_env_value("WATCH_INTERVAL", "7200")
        text = env.read_text(encoding="utf-8")
        assert text.count("WATCH_INTERVAL=") == 1          # updated, not appended
        assert "WATCH_INTERVAL=7200" in text
        assert "TELEGRAM_BOT_TOKEN=abc" in text            # other lines preserved


# --------------------------------------------------------------------------- #
# Log-line parsers — drive the live counters and the progress bar
# --------------------------------------------------------------------------- #
class TestLogParsers:
    POSTED = "2026 | INFO | telegram_bot_music_youtube | [chan] [3/55] Posted: Some & Track"
    DL = "2026 | INFO | telegram_bot_music_youtube | [chan] [3/55] Downloading: Some Track"
    NEW = "2026 | INFO | telegram_bot_music_youtube | [chan] 12 new video(s) to post."
    NONEW = "2026 | INFO | telegram_bot_music_youtube | [chan] No new videos to post."
    FAILED = "2026 | ERROR | telegram_bot_music_youtube | [chan] Failed to process x (T): boom"
    TRACE = 'File "yt_dlp/foo.py", line 99, in bar'

    def test_posted_match_and_index(self):
        m = gui.DashboardPage._POSTED_RX.search(self.POSTED)
        assert m and m.group(1) == "3" and m.group(2) == "55"
        assert m.group(3).strip() == "Some & Track"        # title incl. & extracted

    def test_downloading_index(self):
        m = gui.DashboardPage._DL_RX.search(self.DL)
        assert m and (int(m.group(1)), int(m.group(2))) == (3, 55)

    def test_new_count(self):
        assert gui.DashboardPage._NEW_RX.search(self.NEW).group(1) == "12"

    def test_no_new(self):
        assert gui.DashboardPage._NONEW_RX.search(self.NONEW)

    def test_failed(self):
        assert gui.DashboardPage._FAILED_RX.search(self.FAILED)

    def test_traceback_is_not_counted(self):
        # A bare traceback line must not look like a post or a failure
        assert not gui.DashboardPage._POSTED_RX.search(self.TRACE)
        assert not gui.DashboardPage._FAILED_RX.search(self.TRACE)


# --------------------------------------------------------------------------- #
# Language detection — first launch English, saved choice persists
# --------------------------------------------------------------------------- #
class TestLanguage:
    def test_first_launch_is_english(self, tmp_path, monkeypatch):
        monkeypatch.setattr(gui, "LANG_SETTING_FILE", tmp_path / "lang.txt")
        assert gui._detect_lang() == "en"

    def test_saved_choice_persists(self, tmp_path, monkeypatch):
        f = tmp_path / "lang.txt"
        f.write_text("ru", encoding="utf-8")
        monkeypatch.setattr(gui, "LANG_SETTING_FILE", f)
        assert gui._detect_lang() == "ru"


# --------------------------------------------------------------------------- #
# Self-dispatcher — the GUI .exe re-runs itself as the engine via --bot-* flags
# --------------------------------------------------------------------------- #
class TestBotDispatcher:
    """The dispatcher at the top of gui_app.py is the spine of the desktop app:
    BotWorker relaunches the same executable with --bot-watch/once/check/test,
    and _run_bot_mode must map each flag to the right engine entry point."""

    def test_flag_to_mode_map(self):
        assert gui._BOT_MODES == {
            "--bot-watch": "watch",
            "--bot-once": "once",
            "--bot-check": "check",
            "--bot-test": "test",
        }

    @pytest.mark.parametrize("mode,fn_name", [
        ("watch", "_do_watch"),
        ("once", "_do_run"),
        ("check", "_do_check"),
        ("test", "_do_test"),
    ])
    def test_run_bot_mode_dispatches_to_engine(self, monkeypatch, mode, fn_name):
        bot = importlib.import_module("telegram_bot_music_youtube")
        called: list[str] = []
        for name in ("_do_watch", "_do_run", "_do_check", "_do_test"):
            monkeypatch.setattr(bot, name, lambda n=name: called.append(n) or 0)
        rc = gui._run_bot_mode(mode)
        assert called == [fn_name]
        assert rc == 0

    def test_run_bot_mode_returns_engine_exit_code(self, monkeypatch):
        bot = importlib.import_module("telegram_bot_music_youtube")
        monkeypatch.setattr(bot, "_do_run", lambda: 7)
        assert gui._run_bot_mode("once") == 7

    def test_run_bot_mode_unknown_returns_1(self):
        assert gui._run_bot_mode("nonsense") == 1


# --------------------------------------------------------------------------- #
# Launch-at-startup toggle — HKCU Run key (winreg), mocked so no real registry
# --------------------------------------------------------------------------- #
class _FakeWinreg:
    """Minimal in-memory stand-in for the winreg module's Run-key surface."""
    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 2
    REG_SZ = 1

    def __init__(self):
        self.values: dict[str, str] = {}

    class _Key:
        def __init__(self, reg):
            self._reg = reg
        def __enter__(self):
            return self
        def __exit__(self, *exc):
            return False

    def OpenKey(self, root, path, reserved=0, access=0):
        return self._Key(self)

    def SetValueEx(self, key, name, reserved, typ, value):
        key._reg.values[name] = value

    def QueryValueEx(self, key, name):
        if name not in key._reg.values:
            raise FileNotFoundError(name)
        return (key._reg.values[name], self.REG_SZ)

    def DeleteValue(self, key, name):
        if name not in key._reg.values:
            raise FileNotFoundError(name)
        del key._reg.values[name]


class TestAutostart:
    def test_noop_off_windows(self, monkeypatch):
        monkeypatch.setattr(gui.sys, "platform", "linux")
        assert gui.set_autostart(True) is False
        assert gui.autostart_enabled() is False

    def test_registry_roundtrip(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "winreg", _FakeWinreg())
        monkeypatch.setattr(gui.sys, "platform", "win32")
        assert gui.autostart_enabled() is False    # nothing registered yet
        assert gui.set_autostart(True) is True
        assert gui.autostart_enabled() is True      # now in the Run key
        assert gui.set_autostart(False) is False
        assert gui.autostart_enabled() is False      # removed again
