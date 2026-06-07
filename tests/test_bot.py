"""Unit tests for the Space Music Hub bot.

These cover the pure, side-effect-free building blocks:
  - JSON state I/O
  - Video filtering
  - ChannelConfig helpers
  - RunResult helpers
  - The retry decorator (sync + async)
  - Config validation

Network and Telegram calls are intentionally not exercised here.
"""

from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import pytest

import telegram_bot_music_youtube as bot

REQUIRED_ENV = (
    "TELEGRAM_BOT_TOKEN",
    "PLAYLIST_ANDREY",
    "TELEGRAM_CHANNEL_ANDREY",
    "PLAYLIST_BAYBA",
    "TELEGRAM_CHANNEL_BAYBA",
)


# --------------------------------------------------------------------------- #
# Setup-wizard helpers (pure parsing + .env writing)
# --------------------------------------------------------------------------- #
class TestExtractPlaylistId:
    def test_full_url(self):
        url = "https://www.youtube.com/playlist?list=PLabc123_-XYZ"
        assert bot._extract_playlist_id(url) == "PLabc123_-XYZ"

    def test_watch_url_with_list(self):
        url = "https://www.youtube.com/watch?v=xyz&list=PLqwe456"
        assert bot._extract_playlist_id(url) == "PLqwe456"

    def test_bare_id_passes_through(self):
        assert bot._extract_playlist_id("  PLrawId123  ") == "PLrawId123"


class TestNormaliseHandle:
    def test_plain_name(self):
        assert bot._normalise_handle("music_ch") == "@music_ch"

    def test_with_at(self):
        assert bot._normalise_handle("@music_ch") == "@music_ch"

    def test_tme_link(self):
        assert bot._normalise_handle("https://t.me/music_ch") == "@music_ch"

    def test_empty(self):
        assert bot._normalise_handle("   ") == ""


class TestWriteEnvFile:
    def test_writes_token_and_channels(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bot, "_app_dir", lambda: str(tmp_path))
        channels = [
            ("music", "PL1", "@music_ch"),
            ("baiba", "PL2", "baiba_ch"),
        ]
        bot._write_env_file("TOKEN123", channels, download_dir="C:\\Temp\\x")
        content = (tmp_path / ".env").read_text(encoding="utf-8")
        assert "TELEGRAM_BOT_TOKEN=TOKEN123" in content
        assert "CHANNEL_1_PLAYLIST=PL1" in content
        assert "CHANNEL_1_TELEGRAM=music_ch" in content  # @ stripped
        assert "CHANNEL_2_NAME=baiba" in content
        assert "DOWNLOAD_DIR=C:\\Temp\\x" in content

    def test_written_env_is_loadable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bot, "_app_dir", lambda: str(tmp_path))
        bot._write_env_file("TKN", [("music", "PLx", "@chan")])
        # The numbered pair must be parseable back by _load_channels
        _clear_channel_env(monkeypatch)
        for line in (tmp_path / ".env").read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, _, val = line.partition("=")
                monkeypatch.setenv(key.strip(), val.strip())
        channels = bot._load_channels()
        assert len(channels) == 1
        assert channels[0].playlist_id == "PLx"
        assert channels[0].channel_id == "chan"


# --------------------------------------------------------------------------- #
# JSON state helpers
# --------------------------------------------------------------------------- #
class TestJsonHelpers:
    def test_load_missing_returns_empty(self, tmp_path):
        assert bot.load_json(str(tmp_path / "does_not_exist.json")) == {}

    def test_save_and_load_roundtrip(self, tmp_path):
        path = str(tmp_path / "state.json")
        data = {"abc123": {"title": "Зной — трек", "message_id": 42}}
        bot.save_json(path, data)
        assert bot.load_json(path) == data

    def test_unicode_preserved(self, tmp_path):
        path = str(tmp_path / "unicode.json")
        data = {"id": {"title": "Привет мир 🎵"}}
        bot.save_json(path, data)
        loaded = bot.load_json(path)
        assert loaded["id"]["title"] == "Привет мир 🎵"


# --------------------------------------------------------------------------- #
# Video filtering
# --------------------------------------------------------------------------- #
class TestFilterNewVideos:
    def test_keeps_unseen(self):
        videos = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        sent = {"b": {"title": "x"}}
        assert [v["id"] for v in bot.filter_new_videos(videos, sent)] == ["a", "c"]

    def test_all_seen_returns_empty(self):
        videos = [{"id": "a"}, {"id": "b"}]
        sent = {"a": {}, "b": {}}
        assert bot.filter_new_videos(videos, sent) == []

    def test_empty_state_returns_all(self):
        videos = [{"id": "a"}]
        assert bot.filter_new_videos(videos, {}) == videos

    def test_empty_playlist_returns_empty(self):
        assert bot.filter_new_videos([], {"a": {}}) == []

    def test_preserves_order(self):
        videos = [{"id": "c"}, {"id": "a"}, {"id": "b"}]
        result = bot.filter_new_videos(videos, {"a": {}})
        assert [v["id"] for v in result] == ["c", "b"]


# --------------------------------------------------------------------------- #
# ChannelConfig
# --------------------------------------------------------------------------- #
class TestChannelConfig:
    def _make(self, channel_id: str) -> bot.ChannelConfig:
        return bot.ChannelConfig(
            name="test",
            playlist_id="PL123",
            channel_id=channel_id,
            sent_videos_file="sent.json",
            pinned_msgs_file="pinned.json",
        )

    def test_normalise_without_at(self):
        cfg = self._make("my_channel")
        assert cfg.normalised_channel_id == "@my_channel"

    def test_normalise_with_at(self):
        cfg = self._make("@my_channel")
        assert cfg.normalised_channel_id == "@my_channel"

    def test_normalise_strips_whitespace(self):
        cfg = self._make("  my_channel  ")
        assert cfg.normalised_channel_id == "@my_channel"

    def test_normalise_double_at_not_added(self):
        cfg = self._make("@@oops")
        # only adds @ if not already present — @@ is left as-is (user mistake)
        assert cfg.normalised_channel_id == "@@oops"


# --------------------------------------------------------------------------- #
# RunResult
# --------------------------------------------------------------------------- #
class TestRunResult:
    def test_success_rate_all_posted(self):
        r = bot.RunResult(channel="x", posted=5, failed=0, total_new=5)
        assert r.success_rate == 1.0

    def test_success_rate_partial(self):
        r = bot.RunResult(channel="x", posted=3, failed=2, total_new=5)
        assert r.success_rate == pytest.approx(0.6)

    def test_success_rate_no_new_videos(self):
        r = bot.RunResult(channel="x", posted=0, failed=0, total_new=0)
        assert r.success_rate == 1.0

    def test_str_no_failures(self):
        r = bot.RunResult(channel="andrey", posted=5, failed=0, total_new=5)
        assert "✅" in str(r)
        assert "failed" not in str(r)

    def test_str_with_failures(self):
        r = bot.RunResult(channel="andrey", posted=3, failed=2, total_new=5)
        assert "⚠️" in str(r)
        assert "failed" in str(r)


# --------------------------------------------------------------------------- #
# Retry decorator — sync
# --------------------------------------------------------------------------- #
class TestRetrySync:
    def test_succeeds_after_failures(self):
        calls = {"n": 0}

        @bot.with_retry(attempts=3, delay=0)
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ValueError("boom")
            return "ok"

        assert flaky() == "ok"
        assert calls["n"] == 3

    def test_exhausts_and_reraises(self):
        calls = {"n": 0}

        @bot.with_retry(attempts=2, delay=0)
        def always_fails():
            calls["n"] += 1
            raise RuntimeError("nope")

        with pytest.raises(RuntimeError):
            always_fails()
        assert calls["n"] == 2

    def test_succeeds_first_try(self):
        @bot.with_retry(attempts=3, delay=0)
        def works():
            return 42

        assert works() == 42


# --------------------------------------------------------------------------- #
# Retry decorator — async
# --------------------------------------------------------------------------- #
class TestRetryAsync:
    def test_succeeds_after_failures(self):
        calls = {"n": 0}

        @bot.with_retry(attempts=3, delay=0)
        async def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise ValueError("boom")
            return "ok"

        assert asyncio.run(flaky()) == "ok"
        assert calls["n"] == 2

    def test_exhausts_and_reraises(self):
        @bot.with_retry(attempts=2, delay=0)
        async def always_fails():
            raise RuntimeError("nope")

        with pytest.raises(RuntimeError):
            asyncio.run(always_fails())


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _clear_channel_env(monkeypatch):
    """Remove every channel-related env var for a clean slate."""
    for var in REQUIRED_ENV:
        monkeypatch.delenv(var, raising=False)
    for i in range(1, 12):
        for suffix in ("PLAYLIST", "TELEGRAM", "NAME"):
            monkeypatch.delenv(f"CHANNEL_{i}_{suffix}", raising=False)


# --------------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------------- #
class TestValidateConfig:
    def test_raises_when_token_missing(self, monkeypatch):
        _clear_channel_env(monkeypatch)
        with pytest.raises(OSError, match="TELEGRAM_BOT_TOKEN"):
            bot._validate_config()

    def test_raises_when_no_channels(self, monkeypatch):
        _clear_channel_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy")
        with pytest.raises(OSError, match="No channels configured"):
            bot._validate_config()

    def test_passes_with_legacy_pair(self, monkeypatch):
        _clear_channel_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy")
        monkeypatch.setenv("PLAYLIST_ANDREY", "PL1")
        monkeypatch.setenv("TELEGRAM_CHANNEL_ANDREY", "chan")
        bot._validate_config()  # must not raise

    def test_passes_with_numbered_pair(self, monkeypatch):
        _clear_channel_env(monkeypatch)
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy")
        monkeypatch.setenv("CHANNEL_1_PLAYLIST", "PL1")
        monkeypatch.setenv("CHANNEL_1_TELEGRAM", "chan")
        bot._validate_config()  # must not raise


# --------------------------------------------------------------------------- #
# Dynamic channel loading
# --------------------------------------------------------------------------- #
class TestLoadChannels:
    def test_empty_when_nothing_set(self, monkeypatch):
        _clear_channel_env(monkeypatch)
        assert bot._load_channels() == []

    def test_legacy_pairs(self, monkeypatch):
        _clear_channel_env(monkeypatch)
        monkeypatch.setenv("PLAYLIST_ANDREY", "PLa")
        monkeypatch.setenv("TELEGRAM_CHANNEL_ANDREY", "andrey_ch")
        monkeypatch.setenv("PLAYLIST_BAYBA", "PLb")
        monkeypatch.setenv("TELEGRAM_CHANNEL_BAYBA", "bayba_ch")
        channels = bot._load_channels()
        assert [c.name for c in channels] == ["andrey", "bayba"]
        assert channels[0].playlist_id == "PLa"
        assert channels[1].channel_id == "bayba_ch"

    def test_numbered_pairs(self, monkeypatch):
        _clear_channel_env(monkeypatch)
        monkeypatch.setenv("CHANNEL_1_PLAYLIST", "PL1")
        monkeypatch.setenv("CHANNEL_1_TELEGRAM", "tg1")
        monkeypatch.setenv("CHANNEL_2_PLAYLIST", "PL2")
        monkeypatch.setenv("CHANNEL_2_TELEGRAM", "tg2")
        channels = bot._load_channels()
        assert len(channels) == 2
        assert channels[0].playlist_id == "PL1"
        assert channels[1].channel_id == "tg2"

    def test_numbered_custom_name(self, monkeypatch):
        _clear_channel_env(monkeypatch)
        monkeypatch.setenv("CHANNEL_1_NAME", "rock")
        monkeypatch.setenv("CHANNEL_1_PLAYLIST", "PL1")
        monkeypatch.setenv("CHANNEL_1_TELEGRAM", "tg1")
        channels = bot._load_channels()
        assert channels[0].name == "rock"
        assert os.path.basename(channels[0].sent_videos_file) == "sent_videos_rock.json"

    def test_numbered_default_name(self, monkeypatch):
        _clear_channel_env(monkeypatch)
        monkeypatch.setenv("CHANNEL_1_PLAYLIST", "PL1")
        monkeypatch.setenv("CHANNEL_1_TELEGRAM", "tg1")
        assert bot._load_channels()[0].name == "channel1"

    def test_numbered_takes_priority_over_legacy(self, monkeypatch):
        _clear_channel_env(monkeypatch)
        monkeypatch.setenv("PLAYLIST_ANDREY", "PLa")
        monkeypatch.setenv("TELEGRAM_CHANNEL_ANDREY", "andrey_ch")
        monkeypatch.setenv("CHANNEL_1_PLAYLIST", "PL1")
        monkeypatch.setenv("CHANNEL_1_TELEGRAM", "tg1")
        channels = bot._load_channels()
        assert len(channels) == 1
        assert channels[0].playlist_id == "PL1"

    def test_stops_at_first_gap(self, monkeypatch):
        _clear_channel_env(monkeypatch)
        monkeypatch.setenv("CHANNEL_1_PLAYLIST", "PL1")
        monkeypatch.setenv("CHANNEL_1_TELEGRAM", "tg1")
        # CHANNEL_2 missing, CHANNEL_3 set — loader must stop at the gap
        monkeypatch.setenv("CHANNEL_3_PLAYLIST", "PL3")
        monkeypatch.setenv("CHANNEL_3_TELEGRAM", "tg3")
        assert len(bot._load_channels()) == 1


# --------------------------------------------------------------------------- #
# ffmpeg discovery
# --------------------------------------------------------------------------- #
class TestFindFfmpeg:
    def test_env_override(self, tmp_path, monkeypatch):
        fake = tmp_path / "my_ffmpeg.exe"
        fake.write_bytes(b"binary")
        monkeypatch.setenv("FFMPEG_PATH", str(fake))
        assert bot._find_ffmpeg() == str(fake)

    def test_beside_app(self, tmp_path, monkeypatch):
        monkeypatch.delenv("FFMPEG_PATH", raising=False)
        (tmp_path / "ffmpeg.exe").write_bytes(b"binary")
        monkeypatch.setattr(bot, "_app_dir", lambda: str(tmp_path))
        assert bot._find_ffmpeg() == str(tmp_path / "ffmpeg.exe")

    def test_env_override_beats_beside_app(self, tmp_path, monkeypatch):
        explicit = tmp_path / "explicit.exe"
        explicit.write_bytes(b"binary")
        (tmp_path / "ffmpeg.exe").write_bytes(b"binary")
        monkeypatch.setenv("FFMPEG_PATH", str(explicit))
        monkeypatch.setattr(bot, "_app_dir", lambda: str(tmp_path))
        assert bot._find_ffmpeg() == str(explicit)


# --------------------------------------------------------------------------- #
# Audio download
# --------------------------------------------------------------------------- #
class _FakeYDL:
    """Stand-in for yt_dlp.YoutubeDL that writes a file instead of downloading."""

    written_size = 200_000  # > the 50 KB minimum by default

    def __init__(self, opts):
        self.opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def download(self, urls):
        if self.written_size is None:
            return  # simulate "nothing produced"
        path = self.opts["outtmpl"].replace("%(ext)s", "mp3")
        with open(path, "wb") as f:
            f.write(b"\x00" * self.written_size)


class TestDownloadAudio:
    def test_returns_path_for_valid_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bot, "DOWNLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(bot.yt_dlp, "YoutubeDL", _FakeYDL)
        result = bot._download_audio("vid123")
        assert result.endswith("vid123.mp3")
        assert os.path.exists(result)

    def test_raises_when_nothing_produced(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bot, "DOWNLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(bot.time, "sleep", lambda *a: None)  # skip retry waits

        class _EmptyYDL(_FakeYDL):
            written_size = None

        monkeypatch.setattr(bot.yt_dlp, "YoutubeDL", _EmptyYDL)
        with pytest.raises(FileNotFoundError):
            bot._download_audio("missing")

    def test_rejects_small_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(bot, "DOWNLOAD_DIR", str(tmp_path))
        monkeypatch.setattr(bot.time, "sleep", lambda *a: None)

        class _TinyYDL(_FakeYDL):
            written_size = 100  # below the 50 KB threshold

        monkeypatch.setattr(bot.yt_dlp, "YoutubeDL", _TinyYDL)
        with pytest.raises(FileNotFoundError):
            bot._download_audio("tiny")
        # the rejected file must have been cleaned up
        assert not os.path.exists(str(tmp_path / "tiny.mp3"))


# --------------------------------------------------------------------------- #
# post_new_videos — core posting loop
# --------------------------------------------------------------------------- #
class _FakeBot:
    """Async stand-in for telegram.Bot that records calls instead of network I/O."""

    def __init__(self, *args, **kwargs):
        self.sent_audios: list[dict] = []
        self.pinned: list[int] = []
        self.unpinned: list[int] = []

    async def send_audio(self, chat_id, audio, title, caption, parse_mode):
        mid = 1000 + len(self.sent_audios)
        self.sent_audios.append({"chat_id": chat_id, "title": title, "message_id": mid})
        return SimpleNamespace(message_id=mid)

    async def pin_chat_message(self, chat_id, message_id, disable_notification):
        self.pinned.append(message_id)

    async def unpin_chat_message(self, chat_id, message_id):
        self.unpinned.append(message_id)


def _setup_post(tmp_path, monkeypatch, videos, *, fail_ids=()):
    """Wire up a fully-mocked environment for post_new_videos and return the bot."""
    fake_bot = _FakeBot()
    monkeypatch.setattr(bot, "Bot", lambda *a, **k: fake_bot)
    monkeypatch.setattr(bot, "POST_DELAY", 0)
    monkeypatch.setattr(bot, "_get_playlist_videos", lambda playlist_id: videos)

    def fake_download(video_id):
        if video_id in fail_ids:
            raise RuntimeError(f"download failed for {video_id}")
        path = os.path.join(str(tmp_path), f"{video_id}.mp3")
        with open(path, "wb") as f:
            f.write(b"\x00" * 100)
        return path

    monkeypatch.setattr(bot, "_download_audio", fake_download)
    return fake_bot


def _make_channel(tmp_path, **overrides):
    return bot.ChannelConfig(
        name=overrides.get("name", "test"),
        playlist_id=overrides.get("playlist_id", "PL1"),
        channel_id=overrides.get("channel_id", "test_channel"),
        sent_videos_file=str(tmp_path / "sent.json"),
        pinned_msgs_file=str(tmp_path / "pinned.json"),
    )


class TestPostNewVideos:
    def test_posts_all_new_videos(self, tmp_path, monkeypatch):
        videos = [{"id": "a", "title": "Track A"}, {"id": "b", "title": "Track B"}]
        fake_bot = _setup_post(tmp_path, monkeypatch, videos)
        channel = _make_channel(tmp_path)

        result = asyncio.run(bot.post_new_videos(channel))

        assert result.posted == 2
        assert result.failed == 0
        assert result.total_new == 2
        assert [s["title"] for s in fake_bot.sent_audios] == ["Track A", "Track B"]

    def test_skips_already_sent(self, tmp_path, monkeypatch):
        videos = [{"id": "a", "title": "Track A"}, {"id": "b", "title": "Track B"}]
        fake_bot = _setup_post(tmp_path, monkeypatch, videos)
        channel = _make_channel(tmp_path)
        bot.save_json(channel.sent_videos_file, {"a": {"title": "Track A"}})

        result = asyncio.run(bot.post_new_videos(channel))

        assert result.posted == 1
        assert result.total_new == 1
        assert [s["title"] for s in fake_bot.sent_audios] == ["Track B"]

    def test_no_new_videos_returns_zero(self, tmp_path, monkeypatch):
        videos = [{"id": "a", "title": "Track A"}]
        _setup_post(tmp_path, monkeypatch, videos)
        channel = _make_channel(tmp_path)
        bot.save_json(channel.sent_videos_file, {"a": {"title": "Track A"}})

        result = asyncio.run(bot.post_new_videos(channel))

        assert result.posted == 0
        assert result.total_new == 0

    def test_counts_download_failure(self, tmp_path, monkeypatch):
        videos = [{"id": "a", "title": "Track A"}, {"id": "b", "title": "Track B"}]
        fake_bot = _setup_post(tmp_path, monkeypatch, videos, fail_ids=("a",))
        channel = _make_channel(tmp_path)

        result = asyncio.run(bot.post_new_videos(channel))

        assert result.posted == 1
        assert result.failed == 1
        assert [s["title"] for s in fake_bot.sent_audios] == ["Track B"]

    def test_persists_state_after_each_post(self, tmp_path, monkeypatch):
        videos = [{"id": "a", "title": "Track A"}]
        _setup_post(tmp_path, monkeypatch, videos)
        channel = _make_channel(tmp_path)

        asyncio.run(bot.post_new_videos(channel))

        saved = bot.load_json(channel.sent_videos_file)
        assert "a" in saved
        assert saved["a"]["title"] == "Track A"

    def test_pins_latest_message(self, tmp_path, monkeypatch):
        videos = [{"id": "a", "title": "Track A"}, {"id": "b", "title": "Track B"}]
        fake_bot = _setup_post(tmp_path, monkeypatch, videos)
        channel = _make_channel(tmp_path)

        asyncio.run(bot.post_new_videos(channel))

        # the last sent message id must be the one left pinned
        last_msg_id = fake_bot.sent_audios[-1]["message_id"]
        assert fake_bot.pinned[-1] == last_msg_id
        saved_pin = bot.load_json(channel.pinned_msgs_file)
        assert saved_pin["last_message_id"] == last_msg_id

    def test_cleans_up_downloaded_files(self, tmp_path, monkeypatch):
        videos = [{"id": "a", "title": "Track A"}]
        _setup_post(tmp_path, monkeypatch, videos)
        channel = _make_channel(tmp_path)

        asyncio.run(bot.post_new_videos(channel))

        # the temp mp3 must be removed after a successful send
        assert not os.path.exists(str(tmp_path / "a.mp3"))
