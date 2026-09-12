"""Пересылка команд между сессиями: ящик `inbox_<session>.jsonl` и `:send`.

Сессии — отдельные процессы; обмен идёт файлами в data-каталоге (см.
`src/session_mailbox.py`). Здесь: unit-тесты ящика (запись/вычерпывание/lock/
права) и Pilot-тесты `:send` / `:send!` / broadcast / маскировки секретов.
"""
import json
import os

import pytest

from app import CommandRunner
from session_mailbox import (
    MAX_COMMAND_BYTES,
    MODE_INSERT,
    MODE_RUN,
    MailboxError,
    drain_inbox,
    inbox_file_for,
    inbox_path,
    pending_sessions,
    send_message,
)
from tests.conftest import input_widget, last_info, submit, wait_command_done

# --- Ящик (unit) -----------------------------------------------------------


def test_inbox_file_naming():
    assert inbox_file_for("s2") == "inbox_s2.jsonl"
    assert inbox_path("/data", "s3") == os.path.join("/data", "inbox_s3.jsonl")


def test_send_and_drain_roundtrip(tmp_path):
    send_message(str(tmp_path), "s2", "echo hi", sender="default")
    send_message(str(tmp_path), "s2", "echo bye", sender="default", mode=MODE_RUN)
    messages = drain_inbox(inbox_path(str(tmp_path), "s2"))
    assert [m["command"] for m in messages] == ["echo hi", "echo bye"]
    assert messages[0]["from"] == "default"
    assert messages[0]["to"] == "s2"
    assert messages[0]["mode"] == MODE_INSERT
    assert messages[1]["mode"] == MODE_RUN
    # Ящик обнулён: повторное вычерпывание пусто.
    assert drain_inbox(inbox_path(str(tmp_path), "s2")) == []


def test_drain_missing_file_is_empty(tmp_path):
    assert drain_inbox(inbox_path(str(tmp_path), "nope")) == []


def test_drain_skips_malformed_and_empty_lines(tmp_path):
    send_message(str(tmp_path), "s2", "good-1", sender="d")
    path = inbox_path(str(tmp_path), "s2")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("this is not json\n")
        handle.write("\n")
        handle.write(json.dumps({"command": ""}) + "\n")
        handle.write(json.dumps({"command": "   "}) + "\n")
        handle.write(json.dumps({"not_command": 1}) + "\n")
    assert [m["command"] for m in drain_inbox(path)] == ["good-1"]


def test_send_rejects_empty_and_oversized(tmp_path):
    with pytest.raises(MailboxError):
        send_message(str(tmp_path), "s2", "   ", sender="d")
    with pytest.raises(MailboxError):
        send_message(str(tmp_path), "s2", "x" * (MAX_COMMAND_BYTES + 1), sender="d")


@pytest.mark.skipif(os.name == "nt", reason="POSIX-права 0600")
def test_inbox_file_is_private(tmp_path):
    send_message(str(tmp_path), "s2", "echo hi", sender="d")
    mode = os.stat(inbox_path(str(tmp_path), "s2")).st_mode & 0o777
    assert mode == 0o600


def test_pending_sessions_reports_nonempty_inboxes(tmp_path):
    assert pending_sessions(str(tmp_path)) == []
    send_message(str(tmp_path), "beta", "echo hi", sender="d")
    assert pending_sessions(str(tmp_path)) == ["beta"]
    drain_inbox(inbox_path(str(tmp_path), "beta"))
    assert pending_sessions(str(tmp_path)) == []


# --- `:send` в TUI (Pilot) -------------------------------------------------


async def test_send_without_args_shows_help(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":send")
        await pilot.pause()
        text = last_info(app).text_content
        assert ":send[!]" in text
        assert "this session: default" in text


async def test_send_missing_command_is_usage(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":send s2")
        await pilot.pause()
        assert "Usage: :send" in last_info(app).text_content


async def test_send_invalid_target_is_usage(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":send ../evil echo hi")
        await pilot.pause()
        assert "Usage: :send" in last_info(app).text_content
        assert not os.path.exists(inbox_path(str(isolated_home), "evil"))


async def test_send_to_self_inserts_into_input(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":send default echo hi")
        await pilot.pause()
        assert input_widget(app).value == "echo hi"
        assert "Forwarded" in last_info(app).text_content
        # Своя сессия — через файл не ходим.
        assert not os.path.exists(inbox_path(str(isolated_home), "default"))


async def test_poll_insert_appends_to_typed_input(isolated_home):
    """Пересылка не затирает уже набранную строку — дописывает в конец."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        input_widget(app).value = "echo typed"
        send_message(str(isolated_home), "default", "&& echo hi", sender="s2")
        app._poll_session_inbox()
        await pilot.pause()
        assert input_widget(app).value == "echo typed && echo hi"


async def test_send_run_to_self_executes(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":send! default seq 3")
        block = await wait_command_done(app)
        assert "3" in block.raw_stdout
        assert "Forwarded" in last_info(app).text_content


async def test_send_writes_other_session_inbox(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":send beta echo hello-beta")
        await pilot.pause()
        messages = drain_inbox(inbox_path(str(isolated_home), "beta"))
        assert [m["command"] for m in messages] == ["echo hello-beta"]
        assert messages[0]["mode"] == MODE_INSERT
        assert "Sent to beta (insert)" in last_info(app).text_content


async def test_send_run_marks_run_mode(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":send! beta date")
        await pilot.pause()
        messages = drain_inbox(inbox_path(str(isolated_home), "beta"))
        assert messages[0]["mode"] == MODE_RUN
        assert "Sent to beta (run)" in last_info(app).text_content


async def test_send_broadcast_excludes_current(isolated_home):
    (isolated_home / "history_alpha.txt").write_text("echo x\n", encoding="utf-8")
    (isolated_home / "history_beta.txt").write_text("echo y\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":send * echo everyone")
        await pilot.pause()
        for name in ("alpha", "beta"):
            messages = drain_inbox(inbox_path(str(isolated_home), name))
            assert [m["command"] for m in messages] == ["echo everyone"]
        assert not os.path.exists(inbox_path(str(isolated_home), "default"))


async def test_send_without_other_sessions_reports_none(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":send * echo nobody")
        await pilot.pause()
        # В изолированном каталоге есть только текущая сессия.
        assert "No other sessions" in last_info(app).text_content


async def test_send_masks_secrets_in_inbox(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "$$TOKEN=supersecret")
        await submit(pilot, ":send beta echo $TOKEN")
        await pilot.pause()
        path = inbox_path(str(isolated_home), "beta")
        raw = open(path, encoding="utf-8").read()
        assert "supersecret" not in raw
        assert "****" in raw
        assert "secret values masked" in last_info(app).text_content


async def test_poll_delivers_queued_insert(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        send_message(
            str(isolated_home), "default", "echo queued", sender="s2", mode=MODE_INSERT
        )
        app._poll_session_inbox()
        await pilot.pause()
        assert input_widget(app).value == "echo queued"
        assert "Forwarded" in last_info(app).text_content


async def test_poll_delivers_queued_run(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)):
        send_message(str(isolated_home), "default", "seq 2", sender="s2", mode=MODE_RUN)
        app._poll_session_inbox()
        block = await wait_command_done(app)
        assert "2" in block.raw_stdout


async def test_poll_offline_queue_from_previous_send(isolated_home):
    """Сообщение, оставленное до старта сессии, доставляется на первом опросе."""
    send_message(str(isolated_home), "default", "echo late", sender="s2")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        app._poll_session_inbox()
        await pilot.pause()
        assert input_widget(app).value == "echo late"


# --- Автодополнение имён сессий после `:send ` ------------------------------ 


def test_send_completion_items_and_prefix(isolated_home):
    (isolated_home / "history_alpha.txt").write_text("echo a\n", encoding="utf-8")
    (isolated_home / "history_beta.txt").write_text("echo b\n", encoding="utf-8")
    app = CommandRunner()
    items, preview = app.get_send_completions(":send ", len(":send "))
    assert preview == ""
    inserts = [i.insert for i in items]
    assert {"default", "alpha", "beta", "*"} <= set(inserts)
    current = next(i for i in items if i.insert == "default")
    assert "(this session)" in current.display
    # По префиксу — только подходящие имена.
    items, _ = app.get_send_completions(":send al", len(":send al"))
    assert [i.insert for i in items] == ["alpha"]
    # До `:send!` доходят те же подсказки.
    items, _ = app.get_send_completions(":send! be", len(":send! be"))
    assert [i.insert for i in items] == ["beta"]


def test_send_completion_hides_after_command_starts(isolated_home):
    app = CommandRunner()
    assert app.get_send_completions(":send", len(":send")) == ([], "")
    assert app.get_send_completions(":send alpha ", len(":send alpha ")) == ([], "")
    assert app.get_send_completions(":send alpha echo hi", 19) == ([], "")
    # Другая colon-команда не перехватывается.
    assert app.get_send_completions(":session ", len(":session ")) == ([], "")


async def test_send_tab_applies_session_name(isolated_home):
    (isolated_home / "history_stage.txt").write_text("echo s\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        inp = input_widget(app)
        inp.value = ":send st"
        inp.cursor_position = len(":send st")
        await pilot.pause()
        assert app._completion_list.is_visible()
        assert app._completion_list.total_candidates == 1
        await pilot.press("tab")
        await pilot.pause()
        assert inp.value == ":send stage "
