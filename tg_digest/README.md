# tg_digest — Telegram AI digest (MVP)

Reads your Telegram chats/channels through Telethon (as your account), summarizes
them with Groq (`llama-3.3-70b-versatile`) and sends you a daily digest via your
own Telegram bot.

## Architecture

```
your account ──► collector.py ──► SQLite ──► summarizer.py ──► digest_sender.py ──► your bot
                                                                          ▲
                                                                          │
                                                                    scheduler.py
```

## Project layout

```
tg_digest/
├── config.py            # chats list, blacklist, prompt, model
├── database.py          # SQLite (digest.db at repo root)
├── collector.py         # Telethon — fetches new messages
├── summarizer.py        # Groq — per-chat summaries
├── digest_sender.py     # Bot — formats and sends the digest
├── scheduler.py         # Entry point + APScheduler-style loop
├── requirements.txt
├── .env.example
└── README.md
```

## 1. Get the keys (all free)

### Telegram API (Telethon)
1. Go to <https://my.telegram.org>.
2. Log in with your phone number.
3. *API development tools* → create an app.
4. Copy `API_ID` and `API_HASH`.

### Groq API
1. Go to <https://console.groq.com>.
2. Sign up → *API Keys* → *Create Key*.
3. Free tier: ~14,400 requests/day — more than enough.

### Telegram bot (delivers the digest to you)
1. Open Telegram, find **@BotFather**.
2. `/newbot` → name → copy `BOT_TOKEN`.
3. Send `/start` to your new bot.
4. Get your `CHAT_ID` from **@userinfobot**.

## 2. Configure

```bash
cd tg_digest
cp .env.example .env
# fill in TG_API_ID, TG_API_HASH, TG_PHONE, BOT_TOKEN, YOUR_CHAT_ID, GROQ_API_KEY
```

Edit `tg_digest/config.py` and add chats to `CHATS_TO_MONITOR`:

```python
CHATS_TO_MONITOR = [
    "durov",                 # public channel @durov
    "some_private_chat",     # by username
    -1001234567890,          # numeric id for private chats without a username
]
```

## 3. Install

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r tg_digest/requirements.txt
```

## 4. First run (Telethon authorization)

The first run will ask for your phone code (and 2FA password if enabled). After
that the session is persisted to `session_name.session` in the repo root and
no further interactive login is required.

```bash
# one-shot test run (collect + summarize + send right now)
python -m tg_digest.scheduler --once
```

## 5. Run on a schedule

```bash
# starts a long-running process that fires every day at DIGEST_TIME (default 08:00)
python -m tg_digest.scheduler
```

## Where to host it

| Option            | Cost              | Notes                        |
|-------------------|-------------------|------------------------------|
| Your own PC/Mac   | Free              | Must stay on at digest time  |
| Raspberry Pi      | ~$15 one-off      | 24/7                         |
| VPS (Hetzner/DO)  | $4–5/mo           | Reliable                     |
| Railway.app       | Free tier         | Easy to deploy               |

## Troubleshooting

- **`TG_API_ID/TG_API_HASH are not set`** — fill them in `.env`.
- **`BOT_TOKEN` / `YOUR_CHAT_ID` errors** — also from `.env`.
- **Bot does not send messages** — make sure you've sent `/start` to your bot
  first; `YOUR_CHAT_ID` must be your own user id (use @userinfobot).
- **`UserDeactivatedBanError` / login fails** — Telegram may rate-limit fresh
  accounts; wait a few minutes and retry.
- **No messages collected** — check `CHATS_TO_MONITOR` in `config.py` and that
  your account is actually a member of those chats.
