# Security Policy

## Supported versions

This is a portfolio project. Security fixes are applied to the latest release
only.

| Version | Supported |
|---------|-----------|
| 2.0.x   | ✅        |
| < 2.0   | ❌        |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Instead, report privately via either:

- GitHub's **[Private vulnerability reporting](https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram/security/advisories/new)**
  (Security tab → "Report a vulnerability"), or
- email **chronowarden23@gmail.com** with the details and steps to reproduce.

You can expect an initial response within a few days. Once a fix is ready it
will ship in the next release and the report will be credited (unless you
prefer to stay anonymous).

## Handling secrets

This app talks to the Telegram Bot API with **your** bot token.

- The token lives only in your local `.env` (created by the setup wizard) and
  is **never** committed — `.env` is gitignored and removed on uninstall.
- The token is **masked** in all logs (`bot.log` and the in-app log) by a
  dedicated logging filter, so it never leaks into a shared log or screenshot.
- If you ever expose a token, revoke it immediately via
  [@BotFather](https://t.me/BotFather) (`/revoke`) and issue a new one.
