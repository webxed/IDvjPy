"""`:cht <query>` — справки cheat.sh (cht.sh). Сеть не дёргаем: fetch подменяется."""
from __future__ import annotations

import app as app_module
from app import CommandRunner
from cheat_sh import (
    CheatShError,
    _merge_options,
    build_url,
    strip_ansi,
)
from tests.conftest import last_info, submit, wait_command_done


def test_build_url_variants():
    assert build_url("tar") == "https://cht.sh/tar?T"
    assert build_url("python read file") == "https://cht.sh/python+read+file?T"
    assert build_url("/python/lambda") == "https://cht.sh/python/lambda?T"
    assert build_url("~snapshot") == "https://cht.sh/~snapshot?T"
    assert build_url("go/:learn") == "https://cht.sh/go/:learn?T"
    # Свои опции объединяются с дефолтными (Q + T).
    assert build_url("lua/table+keys?Q") == "https://cht.sh/lua/table+keys?QT"
    assert (
        build_url("tar", base_url="http://localhost:8002", options="QT")
        == "http://localhost:8002/tar?QT"
    )
    assert build_url("tar", options="") == "https://cht.sh/tar"


def test_merge_options_order_and_dedupe():
    assert _merge_options("Q", "T") == "QT"
    assert _merge_options("T", "Q") == "TQ"
    assert _merge_options("Q", "Q") == "Q"
    assert _merge_options("", "") == ""


def test_strip_ansi():
    assert strip_ansi("\x1b[31mred\x1b[0m") == "red"
    assert strip_ansi("\x1b]0;title\x07tail") == "tail"
    assert strip_ansi("plain text") == "plain text"


async def test_cht_success_block(isolated_home, monkeypatch):
    seen = {}

    def fake(query, base_url=None, options=None, env=None, timeout=None):
        seen["query"] = query
        seen["base_url"] = base_url
        return "cheat.sh: tar\n  tar -xf archive.tar\n"

    monkeypatch.setattr(app_module, "fetch_cheat_sheet", fake)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":cht tar")
        block = await wait_command_done(app)
        assert "tar -xf archive.tar" in block.raw_stdout
        assert block.return_code == 0
        assert block.source_command == ":cht tar"
    assert seen["query"] == "tar"
    assert seen["base_url"] == app.cheat_sh_url


async def test_cht_multiword_query_joined(isolated_home, monkeypatch):
    seen = {}

    def fake(query, **kwargs):
        seen["query"] = query
        return "ok\n"

    monkeypatch.setattr(app_module, "fetch_cheat_sheet", fake)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":cht python read file")
        await wait_command_done(app)
    assert seen["query"] == "python read file"


async def test_cht_error_reports_stderr(isolated_home, monkeypatch):
    def boom(*args, **kwargs):
        raise CheatShError("Network error for https://cht.sh/tar?T: blocked")

    monkeypatch.setattr(app_module, "fetch_cheat_sheet", boom)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":cht tar")
        block = await wait_command_done(app)
        assert block.return_code == 1
        assert "Network error" in block.raw_stderr


async def test_cht_without_args_shows_usage(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":cht")
        assert "Usage: :cht" in last_info(app).text_content


async def test_cht_recorded_in_history_but_not_completion(isolated_home, monkeypatch):
    monkeypatch.setattr(app_module, "fetch_cheat_sheet", lambda *a, **k: "ok\n")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":cht tar")
        await wait_command_done(app)
        assert ":cht tar" in app._read_file_history()
        assert ":cht tar" not in app.get_completion_candidates(":cht")
