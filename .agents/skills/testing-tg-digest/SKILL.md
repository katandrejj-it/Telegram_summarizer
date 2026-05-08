---
name: testing-tg-digest
description: Smoke + unit test the tg_digest pipeline (collector / summarizer / digest_sender / scheduler) without touching real Telegram, Groq, or Bot APIs. Use when verifying changes to any tg_digest module before asking the user for a real end-to-end run.
---

# Testing tg_digest

This project talks to three external services (Telegram via Telethon, Groq, Telegram Bot API). None of them can be exercised end-to-end without the user's own secrets and phone number, so the local test pass is **mock-heavy** and stops at the user-account boundary.

## Environment

- venv lives at `/home/ubuntu/tg_digest_venv` (reuse it across sessions). If it doesn't exist:
  ```bash
  python3 -m venv /home/ubuntu/tg_digest_venv
  /home/ubuntu/tg_digest_venv/bin/pip install -r tg_digest/requirements.txt
  ```
- Pinned versions at the time of MVP: Telethon 1.43.2, groq 1.2.0, python-telegram-bot 22.7, python-dotenv 1.2.2, schedule 1.2.2. Use floor pins (`>=`) in `requirements.txt`.
- All runtime artefacts (`*.session`, `digest.db`, `.env`) are gitignored — never commit them.

## What to test locally (no secrets needed)

For each PR that touches `tg_digest/*.py`, run the full smoke suite. All 12 cases live in the project test report and runner; key invariants:

1. **Imports** — every module imports cleanly with current pins.
2. **Pure helpers** — `digest_sender.make_tg_link` (public vs `t.me/c/...` for private) and `digest_sender._escape_md` (must escape `_ * [ ] \``).
3. **Missing-secret paths** — `collector._build_client`, `digest_sender._build_bot`, `digest_sender._target_chat_id`, `summarizer._get_client` MUST raise `RuntimeError` (not `KeyError`) when env vars are absent. Patch via `patch.dict(os.environ, ..., clear=False)`.
4. **Database** — `init_db` creates `messages` + `digest_log`; `save_messages` is idempotent on `(chat_id, message_id)` (use `INSERT OR IGNORE`); `get_messages_for_digest(hours_back=N)` cuts at the right boundary. Test with a `tempfile.TemporaryDirectory` and `patch.object(db_mod, "DB_PATH", tmp_db)`.
5. **Summarizer** — below `MIN_MESSAGES` returns `None` AND must NOT instantiate the Groq client (assert `_get_client.called is False`). Above threshold: pass `client=fake_client` directly to `summarize_chat` to bypass real network. `summarize_all` aggregates `{chat_id, chat_name, chat_username, msg_count, first_msg_id, summary}`.
6. **Digest sender** — `send_digest([])` sends exactly one message with `📭`, NO `parse_mode`. `send_digest([N])` sends `1 + N` messages, header + items, items use `parse_mode=ParseMode.MARKDOWN` and `disable_web_page_preview=True`. Use `AsyncMock()` for `bot.send_message` and patch `_build_bot`.
7. **Scheduler `--once`** — must exit cleanly (non-zero exit = fail), not enter `while True`. Easiest test: write a tiny runner that patches `collect_messages`, `summarize_all`, `send_digest`, sets `sys.argv = ["scheduler", "--once"]`, calls `main()`, then run via `subprocess.run(..., timeout=20)`. Clean up `digest.db` after.

A reference runner that executes all of the above in order lives at `/home/ubuntu/run_tests.py` in the testing VM (not committed).

## What CANNOT be tested without the user

Always list these explicitly when reporting results, so the user knows what's still on them:

- Real Telethon login (SMS code / 2FA cloud password) — only the user can complete the prompt.
- Real chat reads from `CHATS_TO_MONITOR`.
- Real Groq calls with the user's `GROQ_API_KEY`.
- Real bot send to the user's `YOUR_CHAT_ID`.
- Schedule firing at `DIGEST_TIME`.

User entry point for their own end-to-end: `python -m tg_digest.scheduler --once` after filling `.env` and `CHATS_TO_MONITOR`.

## Devin Secrets Needed

None for the smoke + unit pass. A real end-to-end would need user-provided values for `TG_API_ID`, `TG_API_HASH`, `TG_PHONE`, `BOT_TOKEN`, `YOUR_CHAT_ID`, `GROQ_API_KEY` — but these MUST come from the user interactively (Telethon SMS flow can't be automated by Devin).

## Common gotchas

- Don't `clear=True` in `patch.dict` for env — module-level imports may have already read other vars; use `clear=False` and only set the keys you care about.
- `python-telegram-bot` v22 uses `telegram.constants.ParseMode.MARKDOWN`, NOT the legacy string `"Markdown"`. Assert against the enum.
- Patch `_get_client` rather than monkey-patching `groq.Groq` — it's the seam the code provides.
- `make_tg_link` strips the `-100` prefix only for private chats (no username); the public branch uses the username and ignores chat_id.
- The scheduler's `--once` must be tested in a subprocess with a hard timeout — if it ever regresses to entering the schedule loop, the test will hang otherwise.
