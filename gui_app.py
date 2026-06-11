#!/usr/bin/env python3
"""Space Music Hub — GUI v2  (PyQt6 · Cyber Neon 2026)

Launch:
    python gui_app.py

Requires:
    pip install PyQt6
"""

from __future__ import annotations

import datetime
import math
import os
import random
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import (
    QSize, QTimer, QThread, QUrl,
    Qt, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QIcon, QLinearGradient,
    QPainter, QPainterPath, QPen,
)
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu,
    QPushButton, QScrollBar, QSizePolicy, QStackedWidget,
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
LOGO_PATH  = _resource("logo.png")
LOGO_ICO   = _resource("logo.ico")
BOT_SCRIPT = BASE_DIR / "telegram_bot_music_youtube.py"
VIDEO_PATHS = [
    _resource("bg.mp4"),
    BASE_DIR / "bg.mp4",
    BASE_DIR / "docs" / "bg.mp4",
]

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
    fn = {"watch": bot._do_watch, "once": bot._do_run, "check": bot._do_check}.get(mode)
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
    background: rgba(0,0,0,140);
    border: 1px solid rgba(255,255,255,8);
    border-radius: 12px;
    padding: 10px 14px;
    color: #6a7590;
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
#  Equalizer  (custom QPainter widget)
# ══════════════════════════════════════════════════════════════════════
class EqualizerWidget(QWidget):
    """Animated neon equalizer bars — idle shimmer → active dance."""

    def __init__(self, bars: int = 32, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bars   = bars
        self._t      = 0.0
        self._active = False
        self._phases = [random.uniform(0, math.pi * 2) for _ in range(bars)]
        self._speeds = [random.uniform(0.035, 0.085)   for _ in range(bars)]

        self.setFixedHeight(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(30)  # ~33 fps

    def set_active(self, active: bool) -> None:
        self._active = active

    def _tick(self) -> None:
        self._t += 1.0
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        gap   = 4
        bar_w = max(4, (w - (self._bars - 1) * gap) // self._bars)

        for i in range(self._bars):
            phase = self._t * self._speeds[i] + self._phases[i]
            if self._active:
                val = 0.25 + 0.75 * abs(math.sin(phase))
            else:
                val = 0.07 + 0.09 * abs(math.sin(phase * 0.4))

            bh = max(3, int(val * h))
            x  = i * (bar_w + gap)
            y  = h - bh

            g = QLinearGradient(x, float(y + bh), x, float(y))
            g.setColorAt(0.0, QColor(MAGENTA))
            g.setColorAt(0.5, QColor(PURPLE))
            g.setColorAt(1.0, QColor(CYAN))

            path = QPainterPath()
            path.addRoundedRect(float(x), float(y), float(bar_w), float(bh), 2.0, 2.0)
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
        self._lbl.setText("IDLE")
        self.setStyleSheet("QWidget { background: rgba(255,255,255,4);"
                           " border: 1px solid rgba(255,255,255,10);"
                           " border-radius: 999px; }")

    def set_running(self) -> None:
        self._pulse.start(550)
        self._dot.setStyleSheet(f"color: {SUCCESS}")
        self._lbl.setStyleSheet(f"color: {CYAN}; letter-spacing: 2px;")
        self._lbl.setText("RUNNING")
        self.setStyleSheet("QWidget { background: rgba(0,212,255,8);"
                           " border: 1px solid rgba(0,212,255,30);"
                           " border-radius: 999px; }")

    def set_error(self) -> None:
        self._pulse.stop()
        self._dot.setStyleSheet(f"color: {ERROR}")
        self._lbl.setStyleSheet(f"color: {ERROR}; letter-spacing: 2px;")
        self._lbl.setText("ERROR")
        self.setStyleSheet("QWidget { background: rgba(248,113,113,8);"
                           " border: 1px solid rgba(248,113,113,30);"
                           " border-radius: 999px; }")

    def set_done(self) -> None:
        self._pulse.stop()
        self._dot.setStyleSheet(f"color: {SUCCESS}")
        self._lbl.setStyleSheet(f"color: {SUCCESS}; letter-spacing: 2px;")
        self._lbl.setText("DONE")
        self.setStyleSheet("QWidget { background: rgba(52,211,153,8);"
                           " border: 1px solid rgba(52,211,153,30);"
                           " border-radius: 999px; }")

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
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

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

        # Don't pop up a console window on Windows when the GUI subprocess
        # spawns the bot worker.
        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

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
            )
            assert self._proc.stdout is not None
            for line in self._proc.stdout:
                if line:
                    self.log.emit(line.rstrip())
            self._proc.wait()
            self.done.emit(self._proc.returncode == 0)

        except Exception as exc:                  # noqa: BLE001
            self.log.emit(f"[ERROR] {exc}")
            self.done.emit(False)


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

    # ── build ──────────────────────────────────────────────────────────
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = GlassCard()
        card.setFixedWidth(560)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(44, 40, 44, 40)
        inner.setSpacing(18)

        # ── step dots ─────────────────────────────────────────────────
        dot_row = QHBoxLayout()
        dot_row.setSpacing(6)
        self._dots: list[QLabel] = []
        for i in range(3):
            d = QLabel("●" if i == 0 else "○")
            d.setFont(QFont("Segoe UI", 12))
            d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            dot_row.addWidget(d)
            self._dots.append(d)
            if i < 2:
                sep = QLabel("──")
                sep.setStyleSheet(f"color: {MUTED}; font-size: 13px;")
                dot_row.addWidget(sep)
        dot_row.addStretch()
        inner.addLayout(dot_row)

        # ── labels ────────────────────────────────────────────────────
        self._step_lbl = QLabel("STEP 1 OF 3")
        self._step_lbl.setStyleSheet(
            f"color: {CYAN}; font-size: 10px; font-weight: 700; letter-spacing: 3px;")
        inner.addWidget(self._step_lbl)

        self._title_lbl = QLabel("Connect your Telegram Bot")
        self._title_lbl.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        self._title_lbl.setStyleSheet(f"color: {WHITE};")
        self._title_lbl.setWordWrap(True)
        inner.addWidget(self._title_lbl)

        self._sub_lbl = QLabel(
            "Create a bot via @BotFather, copy the token, and paste it below.")
        self._sub_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px;")
        self._sub_lbl.setWordWrap(True)
        inner.addWidget(self._sub_lbl)

        # ── input stack ───────────────────────────────────────────────
        self._inputs = QStackedWidget()

        # page 0 — token
        p0 = QWidget(); p0l = QVBoxLayout(p0); p0l.setContentsMargins(0,0,0,0)
        self._token_in = QLineEdit()
        self._token_in.setPlaceholderText("1234567890:AAFxxxxxxxxxxxxxxxxx")
        self._token_in.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_in.setMinimumHeight(46)
        p0l.addWidget(self._token_in)
        self._inputs.addWidget(p0)

        # page 1 — channel + playlist
        p1 = QWidget(); p1l = QVBoxLayout(p1); p1l.setContentsMargins(0,0,0,0); p1l.setSpacing(10)
        self._chan_in   = QLineEdit(); self._chan_in.setPlaceholderText("@your_channel")
        self._chan_in.setMinimumHeight(46)
        self._plist_in  = QLineEdit(); self._plist_in.setPlaceholderText("YouTube playlist URL or ID")
        self._plist_in.setMinimumHeight(46)
        p1l.addWidget(self._chan_in); p1l.addWidget(self._plist_in)
        self._inputs.addWidget(p1)

        # page 2 — review
        p2 = QWidget(); p2l = QVBoxLayout(p2); p2l.setContentsMargins(0,0,0,0)
        self._review_lbl = QLabel()
        self._review_lbl.setStyleSheet(f"color: {TEXT}; font-size: 13px; line-height: 1.7;")
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
        self._back_btn = NeonButton("← Back",            style="glass")
        self._next_btn = NeonButton("Verify & Continue →", style="cyan", glow=True)
        self._back_btn.setVisible(False)
        btn_row.addWidget(self._back_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._next_btn)
        inner.addLayout(btn_row)

        self._back_btn.clicked.connect(self._back)
        self._next_btn.clicked.connect(self._next)

        root.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)

    # ── navigation ────────────────────────────────────────────────────
    def _refresh(self) -> None:
        _steps = [
            ("STEP 1 OF 3", "Connect your Telegram Bot",
             "Create a bot via @BotFather, copy the token, and paste it below."),
            ("STEP 2 OF 3", "Add your first Channel",
             "Enter the Telegram channel handle and the YouTube playlist URL to mirror."),
            ("STEP 3 OF 3", "Review & Save",
             "Looks good! Click Save to write the config and launch the dashboard."),
        ]
        self._step_lbl.setText(_steps[self._step][0])
        self._title_lbl.setText(_steps[self._step][1])
        self._sub_lbl.setText(_steps[self._step][2])
        self._inputs.setCurrentIndex(self._step)
        self._back_btn.setVisible(self._step > 0)
        self._next_btn.setText(
            "Save & Launch →" if self._step == 2 else "Continue →")
        self._status.setText("")
        for i, dot in enumerate(self._dots):
            if i <= self._step:
                dot.setText("●"); dot.setStyleSheet(f"color: {CYAN}")
            else:
                dot.setText("○"); dot.setStyleSheet(f"color: {MUTED}")

        if self._step == 2 and self._channels:
            ch = self._channels[0]
            token_preview = self._token[:12] + "…" if len(self._token) > 12 else self._token
            self._review_lbl.setText(
                f"<b style='color:{WHITE}'>Bot token:</b> <code>{token_preview}</code><br>"
                f"<b style='color:{WHITE}'>Channel:</b> {ch['channel']}<br>"
                f"<b style='color:{WHITE}'>Playlist:</b> {ch['playlist'][:55]}…"
            )

    def _back(self) -> None:
        if self._step > 0:
            self._step -= 1
            self._refresh()

    def _next(self) -> None:
        if self._step == 0:
            token = self._token_in.text().strip()
            if ":" not in token or len(token) < 20:
                self._err("Please enter a valid bot token (from @BotFather).")
                return
            self._token = token
            self._step = 1

        elif self._step == 1:
            ch = self._chan_in.text().strip()
            pl = self._plist_in.text().strip()
            if not ch.startswith("@"):
                self._err("Channel must start with @ (e.g. @my_music_channel).")
                return
            if not pl:
                self._err("Please enter a YouTube playlist URL or ID.")
                return
            self._channels = [{"channel": ch, "playlist": pl}]
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
        ch = self._channels[0] if self._channels else {}
        lines = [
            f"TELEGRAM_BOT_TOKEN={self._token}",
            f"CHANNEL_1_NAME=channel1",
            f"CHANNEL_1_PLAYLIST={ch.get('playlist', '')}",
            f"CHANNEL_1_TELEGRAM={ch.get('channel', '')}",
        ]
        ENV_PATH.write_text("\n".join(lines), encoding="utf-8")


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
        env_lbl = QLabel("✓ Config loaded" if env_ok else "⚠ No config — run wizard")
        env_lbl.setStyleSheet(
            f"color: {SUCCESS}; font-size: 11px;" if env_ok
            else f"color: {AMBER}; font-size: 11px;"
        )
        hdr.addWidget(env_lbl)
        lay.addLayout(hdr)

        # ── equalizer ─────────────────────────────────────────────────
        self._eq = EqualizerWidget(bars=34)
        lay.addWidget(self._eq)

        # ── action buttons ────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(10)
        self._btn_watch = NeonButton("▶  WATCH",    style="cyan",   glow=True)
        self._btn_once  = NeonButton("⚡  RUN ONCE", style="purple", glow=True)
        self._btn_check = NeonButton("🔍  CHECK",   style="glass")
        self._btn_stop  = NeonButton("■  STOP",     style="danger")
        self._btn_conf  = NeonButton("⚙  CONFIG",  style="glass")
        self._btn_stop.setVisible(False)

        for b in [self._btn_watch, self._btn_once, self._btn_check,
                  self._btn_stop, self._btn_conf]:
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        # ── stats cards ───────────────────────────────────────────────
        stats_row = QHBoxLayout(); stats_row.setSpacing(10)
        self._n_posted  = self._stat_card(stats_row, "TRACKS POSTED", CYAN)
        self._n_failed  = self._stat_card(stats_row, "FAILED",        MAGENTA)
        self._n_session = self._stat_card(stats_row, "SESSION RUNS",  PURPLE)
        self._session_runs = 0
        lay.addLayout(stats_row)

        # ── log ───────────────────────────────────────────────────────
        log_hdr = QHBoxLayout()
        log_title = QLabel("LOG OUTPUT")
        log_title.setStyleSheet(f"color: {MUTED}; font-size: 10px;"
                                " letter-spacing: 3px; font-weight: 700;")
        self._btn_clear = QPushButton("clear")
        self._btn_clear.setStyleSheet(
            f"color: {MUTED}; font-size: 11px; background: transparent;"
            " border: none; padding: 0; cursor: pointer;")
        self._btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_clear.clicked.connect(lambda: self._log.clear())
        log_hdr.addWidget(log_title)
        log_hdr.addStretch()
        log_hdr.addWidget(self._btn_clear)
        lay.addLayout(log_hdr)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(160)
        lay.addWidget(self._log)

        # ── wiring ────────────────────────────────────────────────────
        self._btn_watch.clicked.connect(lambda: self._start("watch"))
        self._btn_once.clicked.connect( lambda: self._start("once"))
        self._btn_check.clicked.connect(lambda: self._start("check"))
        self._btn_stop.clicked.connect(self._stop)
        self._btn_conf.clicked.connect(self.go_config)

        self._log_line(f"Space Music Hub GUI v2 — ready.")
        if not ENV_PATH.exists():
            self._log_line("No .env found — please configure via ⚙ CONFIG first.")

    # ── stat card helper ──────────────────────────────────────────────
    def _stat_card(self, row: QHBoxLayout, label: str, color: str) -> QLabel:
        card = GlassCard()
        card.setMinimumHeight(68)
        cl = QVBoxLayout(card); cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num = QLabel("0")
        num.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        num.setAlignment(Qt.AlignmentFlag.AlignCenter)
        num.setStyleSheet(f"color: {color};")
        lbl = QLabel(label)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(f"color: {TEXT}; font-size: 10px; letter-spacing: 2px;")
        cl.addWidget(num); cl.addWidget(lbl)
        row.addWidget(card)
        return num

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
        self._status_badge.set_running()
        self._eq.set_active(True)
        for b in [self._btn_watch, self._btn_once, self._btn_check]:
            b.setEnabled(False)
        self._btn_stop.setVisible(True)
        self._log_line(f"▶  Starting [{mode.upper()}] mode…")

    def _stop(self) -> None:
        if self._worker:
            self._worker.stop()
        self._log_line("■  Stopped by user.")
        self._on_done(True)

    def _on_done(self, ok: bool) -> None:
        self._eq.set_active(False)
        for b in [self._btn_watch, self._btn_once, self._btn_check]:
            b.setEnabled(True)
        self._btn_stop.setVisible(False)
        if ok:
            self._status_badge.set_done()
        else:
            self._status_badge.set_error()

    # ── log ───────────────────────────────────────────────────────────
    def _log_line(self, text: str) -> None:
        ts  = datetime.datetime.now().strftime("%H:%M:%S")
        txt = text.strip()

        # colour keywords
        if any(k in txt.lower() for k in ("error", "fail", "exception")):
            colour = ERROR
        elif any(k in txt.lower() for k in ("ok", "✓", "posted", "success", "done")):
            colour = SUCCESS
        elif any(k in txt.lower() for k in ("warn", "skip")):
            colour = AMBER
        else:
            colour = "#6a7590"

        html = (
            f'<span style="color:{MUTED}">[{ts}]</span> '
            f'<span style="color:{colour}">{txt}</span>'
        )
        self._log.append(html)
        sb: QScrollBar = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())


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
        self._setup_video()
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

        # Video layer (z=0)
        self._vid_widget = QVideoWidget(central)
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

    def _setup_video(self) -> None:
        self._player  = QMediaPlayer()
        self._audio   = QAudioOutput()
        self._audio.setVolume(0.0)  # muted
        self._player.setAudioOutput(self._audio)
        self._player.setVideoOutput(self._vid_widget)
        for vp in VIDEO_PATHS:
            if vp.exists():
                self._player.setSource(QUrl.fromLocalFile(str(vp)))
                self._player.setLoops(-1)   # infinite
                self._player.play()
                break

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

        badge = QLabel("v2.0 · GUI")
        badge.setStyleSheet(
            f"color: {CYAN}; background: rgba(0,212,255,10);"
            f" border: 1px solid rgba(0,212,255,28);"
            f" border-radius: 8px; padding: 4px 10px;"
            f" font-size: 10px; font-weight: 700; letter-spacing: 1px;")
        lay.addWidget(badge)

        self._content_lay.addWidget(nav)

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

        menu = QMenu()
        act_show  = QAction("Open Dashboard",    self)
        act_watch = QAction("▶ Start Watching",  self)
        act_stop  = QAction("■ Stop",            self)
        act_quit  = QAction("Quit",              self)

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
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

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
            "Still running in the tray — right-click the icon to control or quit.",
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
