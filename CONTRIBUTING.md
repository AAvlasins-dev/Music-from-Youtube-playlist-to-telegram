# Contributing to Space Music Hub

Thank you for considering a contribution! Here's everything you need to get started.

## Development setup

```bash
git clone https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram.git
cd Music-from-Youtube-playlist-to-telegram

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements-dev.txt
cp .env.example .env             # fill in your credentials
```

## Running tests

```bash
pytest          # run the full test suite
ruff check .    # lint
```

All tests must pass and there must be zero lint errors before opening a PR.

## Project structure

```
telegram_bot_music_youtube.py   ← single-file bot (keep it this way)
tests/test_bot.py               ← unit tests (pure functions only)
.github/workflows/
    bot.yml                     ← scheduled runner
    ci.yml                      ← lint + test on every push
```

## How to add a new playlist → channel pair

Open `telegram_bot_music_youtube.py` and append a new `ChannelConfig` to the `CHANNELS` list:

```python
ChannelConfig(
    name="my_channel",
    playlist_id=os.getenv("PLAYLIST_MY_CHANNEL", ""),
    channel_id=os.getenv("TELEGRAM_CHANNEL_MY_CHANNEL", ""),
    sent_videos_file="sent_videos_my_channel.json",
    pinned_msgs_file="pinned_msgs_my_channel.json",
),
```

Then add the two new variables to your `.env` and GitHub Actions secrets.

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
3. `pytest && ruff check .` — must be clean
4. Push and open a PR against `master`
5. Fill in the PR template

## Reporting bugs

Please use the [Bug Report](.github/ISSUE_TEMPLATE/bug_report.yml) issue template and include your `bot.log` output.
