# Contributing to Space Music Hub

Thank you for considering a contribution! Here's everything you need to get started.

## Development setup

```bash
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements-dev.txt   # pulls in requirements.txt (incl. PyQt6) + test/lint tools
cp .env.example .env                   # fill in your credentials
```

## Running tests

```bash
ruff check .                              # lint — must be clean
QT_QPA_PLATFORM=offscreen pytest -q       # full suite (101 tests), headless Qt
```

`QT_QPA_PLATFORM=offscreen` lets the PyQt6 GUI tests run without a display
(this is what CI does). All tests must pass and there must be zero lint
errors before opening a PR.

## Project structure

```
gui_app.py                      ← PyQt6 desktop app: wizard, dashboard, tray,
                                  scheduler, i18n — also the self-dispatcher that
                                  re-launches the engine on --bot-watch/once/check
telegram_bot_music_youtube.py   ← engine: YouTube playlist → MP3 → Telegram
SpaceMusicHubGUI.spec           ← PyInstaller build recipe (GUI + engine + assets)
installer/SpaceMusicHub.iss     ← Inno Setup script → the Windows installer
tests/
    test_bot.py                 ← engine unit tests
    test_gui.py                 ← GUI / log-parser unit tests
    conftest.py                 ← shared fixtures
.github/workflows/
    ci.yml                      ← lint + test on every push and PR
    bot.yml                     ← headless engine, manual dispatch only
```

## Architecture in one paragraph

The built `SpaceMusicHub.exe` is the GUI. When the user clicks Watch / Run
once / Check, the GUI **re-launches itself** with a `--bot-watch` /
`--bot-once` / `--bot-check` flag; a dispatcher at the top of `gui_app.py`
sees the flag and runs the bundled engine instead of opening a window,
streaming the engine's stdout back into the dashboard log. No separate Python
is bundled, and a bot crash can't take down the UI.

## How to add a playlist → channel pair

End users do this in the GUI wizard (or the **+ Add another channel** field on
the dashboard) — no code changes needed. Under the hood it writes numbered
`CHANNEL_N_*` variables to `.env` (see `.env.example`):

```dotenv
CHANNEL_1_NAME=my_channel
CHANNEL_1_TELEGRAM=my_channel
CHANNEL_1_PLAYLIST=https://www.youtube.com/playlist?list=...
```

The engine reads every `CHANNEL_N_*` group at startup — you don't edit a
`CHANNELS` list in code.

## Commit style

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add thumbnail support
fix: handle empty playlist gracefully
docs: update configuration table
chore: bump yt-dlp to 2025.3.1
```

## Opening a pull request

1. Fork → create a feature branch (`git checkout -b feat/my-feature`)
2. Make your changes + add/update tests
3. `ruff check . && QT_QPA_PLATFORM=offscreen pytest` — must be clean
4. Push and open a PR against `master`
5. Fill in the PR template

## Reporting bugs

Please use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.yml) issue template and include your `bot.log` output (the token is masked automatically).
