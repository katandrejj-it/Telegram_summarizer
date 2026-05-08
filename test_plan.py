"""tg_digest MVP smoke + unit tests.

How to run (from the repo root):

    python3 -m venv .venv
    source .venv/bin/activate           # Windows: .venv\\Scripts\\activate
    pip install -r tg_digest/requirements.txt
    python test_plan.py

Then send the full output back to me.

The script needs NO real credentials and never touches the network — every
external call (Telegram, Groq, Bot API) is mocked.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {name}{(' — ' + detail) if detail else ''}")


def safe(name: str, fn) -> None:
    try:
        fn()
    except AssertionError as e:
        record(name, False, f"AssertionError: {e}")
    except Exception:
        record(name, False, "EXCEPTION:\n" + traceback.format_exc())


# -------- T1: Module imports --------
def t1_imports() -> None:
    import importlib

    for mod in (
        "tg_digest.config",
        "tg_digest.database",
        "tg_digest.collector",
        "tg_digest.summarizer",
        "tg_digest.digest_sender",
        "tg_digest.scheduler",
    ):
        importlib.import_module(mod)
    record("T1 imports", True, "all 6 modules import")


# -------- T2: make_tg_link --------
def t2_make_tg_link() -> None:
    from tg_digest.digest_sender import make_tg_link

    private = make_tg_link(chat_id=-1001234567890, message_id=42)
    public = make_tg_link(chat_id=-1001234567890, message_id=42, username="durov")
    assert private == "https://t.me/c/1234567890/42", f"private mismatch: {private!r}"
    assert public == "https://t.me/durov/42", f"public mismatch: {public!r}"
    record("T2 make_tg_link", True, f"private={private} public={public}")


# -------- T3: _escape_md --------
def t3_escape_md() -> None:
    from tg_digest.digest_sender import _escape_md

    plain = _escape_md("plain text")
    assert plain == "plain text", f"plain mutated: {plain!r}"
    inp = "Hello _world_ *bold* [x](y) `code`"
    out = _escape_md(inp)
    for ch in ["_", "*", "[", "]", "`"]:
        assert ("\\" + ch) in out, f"{ch!r} not escaped in {out!r}"
    record("T3 _escape_md", True, repr(out))


# -------- T4: missing-secret error paths --------
def t4_missing_secrets() -> None:
    import tg_digest.collector as collector_mod
    import tg_digest.digest_sender as ds_mod
    import tg_digest.summarizer as s_mod

    keep = {
        k: os.environ.pop(k, None)
        for k in ("TG_API_ID", "TG_API_HASH", "BOT_TOKEN", "GROQ_API_KEY", "YOUR_CHAT_ID")
    }
    try:
        cases = [
            ("collector._build_client", collector_mod._build_client, "TG_API"),
            ("digest_sender._build_bot", ds_mod._build_bot, "BOT_TOKEN"),
            ("digest_sender._target_chat_id", ds_mod._target_chat_id, "YOUR_CHAT_ID"),
            ("summarizer._get_client", s_mod._get_client, "GROQ_API_KEY"),
        ]
        for label, fn, expected_substr in cases:
            try:
                fn()
            except RuntimeError as e:
                assert expected_substr in str(e), f"{label}: msg missing {expected_substr!r}: {e}"
            else:
                raise AssertionError(f"{label}: did not raise RuntimeError")
        record("T4 missing-secret errors", True, "all 4 raise RuntimeError")
    finally:
        for k, v in keep.items():
            if v is not None:
                os.environ[k] = v


# -------- T5: DB lifecycle --------
def t5_db_lifecycle() -> None:
    import tg_digest.database as db_mod

    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = Path(tmp) / "t5.db"
        with patch.object(db_mod, "DB_PATH", tmp_db):
            db_mod.init_db()
            assert tmp_db.exists(), "DB file not created"

            import sqlite3

            conn = sqlite3.connect(tmp_db)
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            conn.close()
            assert "messages" in tables and "digest_log" in tables, f"tables={tables}"

            recent = datetime.now(tz=timezone.utc)
            old = recent - timedelta(hours=2)

            msg = {
                "chat_id": 111,
                "chat_name": "Recent",
                "chat_username": "recent_chat",
                "message_id": 7,
                "sender": "Alice",
                "text": "hello",
                "date": recent,
            }
            old_msg = {
                "chat_id": 222,
                "chat_name": "Old",
                "chat_username": None,
                "message_id": 9,
                "sender": "Bob",
                "text": "old",
                "date": old,
            }

            n1 = db_mod.save_messages([msg, old_msg])
            assert n1 == 2, f"first insert returned {n1}"

            n2 = db_mod.save_messages([msg])  # dup
            assert n2 == 0, f"dup insert returned {n2}"

            grouped_1h = db_mod.get_messages_for_digest(hours_back=1)
            assert 222 not in grouped_1h, "old msg leaked into 1h window"
            assert 111 in grouped_1h, f"recent msg missing from 1h window: {grouped_1h}"

            grouped_24h = db_mod.get_messages_for_digest(hours_back=24)
            assert 111 in grouped_24h and 222 in grouped_24h, f"24h window: {grouped_24h}"
            assert grouped_24h[111]["name"] == "Recent"
            assert grouped_24h[111]["username"] == "recent_chat"
            assert grouped_24h[111]["messages"][0]["message_id"] == 7

            db_mod.log_digest_run(hours_back=24, chats_count=5, status="ok")
            conn = sqlite3.connect(tmp_db)
            row = conn.execute(
                "SELECT hours_back, chats_count, status FROM digest_log"
            ).fetchone()
            conn.close()
            assert row == (24, 5, "ok"), f"digest_log row: {row}"

    record("T5 DB lifecycle", True, "init/save/dedup/cutoff/log_digest_run all OK")


# -------- T6: summarize_chat below threshold --------
def t6_summarize_below() -> None:
    import tg_digest.summarizer as s_mod

    msgs = [
        {"date": "x", "sender": "a", "text": "1", "message_id": 1},
        {"date": "x", "sender": "a", "text": "2", "message_id": 2},
    ]
    with patch.dict(os.environ, {"MIN_MESSAGES": "3"}, clear=False), patch.object(
        s_mod, "_get_client"
    ) as get_client:
        out = s_mod.summarize_chat("x", msgs, hours=24)
        assert out is None, f"expected None, got {out!r}"
        assert not get_client.called, "Groq client should NOT be created below threshold"
    record("T6 summarize_chat below threshold", True, "returned None, Groq untouched")


# -------- T7: summarize_chat happy path --------
def t7_summarize_happy() -> None:
    import tg_digest.summarizer as s_mod

    fake_choice = MagicMock()
    fake_choice.message.content = "FIXTURE_SUMMARY"
    fake_resp = MagicMock()
    fake_resp.choices = [fake_choice]

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    msgs = [
        {"date": "x", "sender": "a", "text": f"line {i}", "message_id": i}
        for i in range(5)
    ]
    with patch.dict(os.environ, {"MIN_MESSAGES": "3"}, clear=False):
        out = s_mod.summarize_chat("Demo", msgs, hours=24, client=fake_client)
    assert out == "FIXTURE_SUMMARY", f"got {out!r}"
    fake_client.chat.completions.create.assert_called_once()
    record("T7 summarize_chat happy", True, "returned fixture, exactly 1 Groq call")


# -------- T8: summarize_all aggregation --------
def t8_summarize_all() -> None:
    import tg_digest.summarizer as s_mod

    fake_choice = MagicMock()
    fake_choice.message.content = "S"
    fake_resp = MagicMock()
    fake_resp.choices = [fake_choice]

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp

    chats = {
        100: {
            "name": "Big",
            "username": "big_chat",
            "messages": [
                {"date": "x", "sender": "u", "text": f"m{i}", "message_id": i}
                for i in range(5)
            ],
        },
        200: {
            "name": "Small",
            "username": None,
            "messages": [
                {"date": "x", "sender": "u", "text": "m", "message_id": 1}
            ],
        },
    }
    with patch.dict(os.environ, {"MIN_MESSAGES": "3"}, clear=False), patch.object(
        s_mod, "_get_client", return_value=fake_client
    ):
        out = s_mod.summarize_all(chats, hours=24)

    assert len(out) == 1, f"expected 1 entry, got {len(out)}: {out}"
    item = out[0]
    assert item["chat_id"] == 100
    assert item["chat_name"] == "Big"
    assert item["chat_username"] == "big_chat"
    assert item["msg_count"] == 5
    assert item["first_msg_id"] == 0
    assert item["summary"] == "S"
    record("T8 summarize_all", True, "below-threshold dropped, fields intact")


# -------- T9: send_digest empty branch --------
def t9_send_digest_empty() -> None:
    import tg_digest.digest_sender as ds_mod

    fake_bot = MagicMock()
    fake_bot.send_message = AsyncMock()

    with patch.dict(
        os.environ,
        {"BOT_TOKEN": "x", "YOUR_CHAT_ID": "1"},
        clear=False,
    ), patch.object(ds_mod, "_build_bot", return_value=fake_bot):
        asyncio.run(ds_mod.send_digest([], hours=24))

    assert fake_bot.send_message.await_count == 1, fake_bot.send_message.await_count
    call = fake_bot.send_message.await_args_list[0]
    text = call.kwargs.get("text", "")
    assert "📭" in text and "24" in text, f"text={text!r}"
    assert "parse_mode" not in call.kwargs, f"parse_mode leaked: {call.kwargs}"
    record("T9 send_digest empty", True, "1 send, no parse_mode, contains 📭+24")


# -------- T10: send_digest populated --------
def t10_send_digest_populated() -> None:
    import tg_digest.digest_sender as ds_mod
    from telegram.constants import ParseMode

    fake_bot = MagicMock()
    fake_bot.send_message = AsyncMock()

    summaries = [
        {
            "chat_id": -1001234567890,
            "chat_name": "Public * chat",
            "chat_username": "durov",
            "msg_count": 10,
            "first_msg_id": 5,
            "summary": "summary A",
        },
        {
            "chat_id": -1009876543210,
            "chat_name": "Private",
            "chat_username": None,
            "msg_count": 7,
            "first_msg_id": 11,
            "summary": "summary B",
        },
    ]

    with patch.dict(
        os.environ,
        {"BOT_TOKEN": "x", "YOUR_CHAT_ID": "1"},
        clear=False,
    ), patch.object(ds_mod, "_build_bot", return_value=fake_bot):
        asyncio.run(ds_mod.send_digest(summaries, hours=24))

    n = fake_bot.send_message.await_count
    assert n == 3, f"expected 3 sends (header+2), got {n}"

    header = fake_bot.send_message.await_args_list[0].kwargs.get("text", "")
    assert "Дайджест" in header and "2" in header, f"header={header!r}"

    item1 = fake_bot.send_message.await_args_list[1]
    item2 = fake_bot.send_message.await_args_list[2]

    assert "https://t.me/durov/5" in item1.kwargs["text"], item1.kwargs["text"]
    assert "https://t.me/c/9876543210/11" in item2.kwargs["text"], item2.kwargs["text"]

    for item in (item1, item2):
        assert item.kwargs["parse_mode"] == ParseMode.MARKDOWN, item.kwargs
        assert item.kwargs["disable_web_page_preview"] is True, item.kwargs

    record(
        "T10 send_digest populated",
        True,
        "3 sends, public+private links correct, Markdown enabled",
    )


# -------- T11: scheduler --once --------
def t11_scheduler_once() -> None:
    runner = REPO / "_t11_run.py"
    runner.write_text(
        """
import asyncio, os, sys
from unittest.mock import AsyncMock, patch

os.environ.setdefault("TG_API_ID", "1")
os.environ.setdefault("TG_API_HASH", "x")
os.environ.setdefault("BOT_TOKEN", "x")
os.environ.setdefault("YOUR_CHAT_ID", "1")
os.environ.setdefault("GROQ_API_KEY", "x")

with patch("tg_digest.collector.collect_messages", new=AsyncMock(return_value=0)), \\
     patch("tg_digest.summarizer.summarize_all", return_value=[]), \\
     patch("tg_digest.digest_sender.send_digest", new=AsyncMock(return_value=None)):
    sys.argv = ["scheduler", "--once"]
    from tg_digest.scheduler import main
    main()
""".strip()
    )
    db_existed_before = (REPO / "digest.db").exists()
    try:
        env = {**os.environ}
        env["PYTHONPATH"] = str(REPO)
        start = time.time()
        proc = subprocess.run(
            [sys.executable, str(runner)],
            cwd=REPO,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        elapsed = time.time() - start
        assert proc.returncode == 0, (
            f"exit={proc.returncode}\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
        assert (REPO / "digest.db").exists(), "digest.db not created"
        record(
            "T11 scheduler --once",
            True,
            f"exit=0 in {elapsed:.1f}s, digest.db created",
        )
    finally:
        runner.unlink(missing_ok=True)
        # Only delete digest.db if THIS test created it. Don't wipe a real one.
        if not db_existed_before:
            (REPO / "digest.db").unlink(missing_ok=True)


# -------- T12: requirements snapshot --------
def t12_requirements() -> None:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:  # pragma: no cover - py<3.8
        from importlib_metadata import PackageNotFoundError, version  # type: ignore

    expected = ["telethon", "groq", "python-telegram-bot", "python-dotenv", "schedule"]
    found = {}
    missing = []
    for pkg in expected:
        try:
            found[pkg] = version(pkg)
        except PackageNotFoundError:
            missing.append(pkg)
    assert not missing, f"missing: {missing}"
    record("T12 requirements", True, ", ".join(f"{k}=={v}" for k, v in found.items()))


def main() -> int:
    print(f"Python: {sys.version.split()[0]} @ {sys.executable}")
    print(f"Repo:   {REPO}\n")

    if not (REPO / "tg_digest").is_dir():
        print(
            f"ERROR: expected to find a 'tg_digest/' folder next to this script "
            f"(at {REPO / 'tg_digest'}). Place test_plan.py in the repo root."
        )
        return 2

    safe("T1", t1_imports)
    safe("T2", t2_make_tg_link)
    safe("T3", t3_escape_md)
    safe("T4", t4_missing_secrets)
    safe("T5", t5_db_lifecycle)
    safe("T6", t6_summarize_below)
    safe("T7", t7_summarize_happy)
    safe("T8", t8_summarize_all)
    safe("T9", t9_send_digest_empty)
    safe("T10", t10_send_digest_populated)
    safe("T11", t11_scheduler_once)
    safe("T12", t12_requirements)

    print("\n=== SUMMARY ===")
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, detail in results:
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {name}: {detail}")
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
