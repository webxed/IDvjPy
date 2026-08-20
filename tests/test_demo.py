"""Демо-режим: YAML-сценарий печатает команды в живом TUI."""
import time

from app import CommandBlock, CommandRunner, InfoBlock
from demo import (
    bundled_demo_names,
    load_scenario,
    normalize_step,
    resolve_demo_path,
    _type_gap,
)

from tests.conftest import input_widget, last_info, submit, wait_command_done


def test_bundled_short_and_full_resolve():
    names = bundled_demo_names()
    assert "short" in names
    assert "ip" in names
    assert "full" in names
    short = resolve_demo_path("short")
    assert short is not None and short.is_file()
    scenario = load_scenario(short)
    assert scenario["steps"]
    assert scenario["title"]
    ip = load_scenario(resolve_demo_path("ip"))
    echo_step = next(s for s in ip["steps"] if (s.get("type") or "").startswith("echo -e "))
    assert r"\n" in echo_step["type"]
    types = [s.get("type") or "" for s in ip["steps"]]
    assert "#hello curl -s $MY_IP_SVC" in types
    assert "#hello jq -r '.country'" in types
    assert any(t.startswith("#hello echo") and "hello[2]" in t for t in types)
    assert "!! hello[1]|hello[2]" in types
    comments = [t for t in types if t.startswith("# ") and not t.startswith("#hello")]
    assert len(comments) >= 8
    assert any("hello[1]" in t for t in comments)


def test_normalize_string_step_types_and_enters():
    step = normalize_step("echo hello")
    assert step["type"] == "echo hello"
    assert step["enter"] is True
    assert step["clear"] is True
    assert step["keys"] == []


def test_normalize_keys_and_aliases():
    step = normalize_step({"keys": "tab, esc, pgup", "caption": "jump"})
    assert step["keys"] == ["tab", "escape", "pageup"]
    assert step["enter"] is False
    assert step["type"] == ""
    assert step["caption"] == "jump"


def test_normalize_type_defaults_enter():
    step = normalize_step({"type": "!", "enter": False, "pause": 1.2})
    assert step["enter"] is False
    assert step["pause"] == 1.2


def test_normalize_step_type_delay():
    step = normalize_step({"type": "echo x", "type_delay": 0.04})
    assert step["type_delay"] == 0.04
    assert normalize_step("echo x")["type_delay"] is None


def test_type_gap_long_lines_are_faster():
    slow = _type_gap(0.12, "jq")
    fast = _type_gap(0.12, "https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2#")
    assert fast < slow
    assert _type_gap(0, "anything") == 0.005


async def test_bundled_short_plays(isolated_home):
    """Прогон bundled short на большой скорости — ловит поломки YAML/клавиш."""
    path = resolve_demo_path("short")
    assert path is not None
    scenario = load_scenario(path)
    scenario["start_pause"] = 0
    scenario["type_delay"] = 0
    scenario["pause"] = 0
    app = CommandRunner(demo=scenario, demo_speed=25)
    async with app.run_test(size=(120, 40)) as pilot:
        deadline = time.monotonic() + 45
        while app._demo_active and time.monotonic() < deadline:
            await pilot.pause()
        assert app._demo_active is False
        assert "Demo error" not in (app.sub_title or "")
        stdout = " ".join(block.raw_stdout for block in app.query(CommandBlock))
        assert "hello-idvj" in stdout
        assert "api.agify.io" in stdout


async def test_demo_types_and_runs_echo(isolated_home):
    scenario = {
        "title": "unit",
        "start_pause": 0,
        "type_delay": 0,
        "pause": 0,
        "command_timeout": 8,
        "steps": [
            {"type": "echo demo-ok-123", "enter": True, "wait_command": True, "pause": 0},
        ],
    }
    app = CommandRunner(demo=scenario, demo_speed=20)
    async with app.run_test(size=(120, 40)) as pilot:
        deadline = time.monotonic() + 12
        while app._demo_active and time.monotonic() < deadline:
            await pilot.pause()
        assert app._demo_active is False
        block = await wait_command_done(app)
        assert "demo-ok-123" in block.raw_stdout
        assert input_widget(app).value == ""


async def test_demo_echo_dash_e_prints_newline(isolated_home):
    scenario = {
        "title": "echo-nl",
        "start_pause": 0,
        "type_delay": 0,
        "pause": 0,
        "command_timeout": 8,
        "steps": [
            {"type": "echo -e 'hello\\nworld'", "enter": True, "wait_command": True, "pause": 0},
        ],
    }
    app = CommandRunner(demo=scenario, demo_speed=20)
    async with app.run_test(size=(120, 40)) as pilot:
        deadline = time.monotonic() + 12
        while app._demo_active and time.monotonic() < deadline:
            await pilot.pause()
        block = await wait_command_done(app)
        assert "hello\nworld" in block.raw_stdout


async def test_demo_escape_stops_playback(isolated_home):
    scenario = {
        "title": "stop",
        "start_pause": 0,
        "type_delay": 0,
        "pause": 0,
        "steps": [
            {"caption": "hold", "pause": 8},
            {"type": "echo should-not-finish-this-line", "enter": True, "pause": 0},
        ],
    }
    app = CommandRunner(demo=scenario, demo_speed=1)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        app._stop_demo("stopped-by-test")
        await pilot.pause()
        assert app._demo_active is False
        assert "stopped-by-test" in (app.sub_title or "")
        assert list(app.query(CommandBlock)) == []


async def test_demo_wait_command_waits_for_pipe_block(isolated_home):
    """wait_command must not return on the previous finished curl/echo block."""
    scenario = {
        "title": "pipe-wait",
        "start_pause": 0,
        "type_delay": 0,
        "pause": 0,
        "command_timeout": 8,
        "steps": [
            {"type": "printf 'aaa\\nbbb\\n'", "enter": True, "wait_command": True, "pause": 0},
            {"type": "| grep bbb", "enter": True, "wait_command": True, "pause": 0},
        ],
    }
    app = CommandRunner(demo=scenario, demo_speed=20)
    async with app.run_test(size=(120, 40)) as pilot:
        deadline = time.monotonic() + 12
        while app._demo_active and time.monotonic() < deadline:
            await pilot.pause()
        assert app._demo_active is False
        blocks = list(app.query(CommandBlock))
        assert len(blocks) >= 2
        assert "bbb" in blocks[-1].raw_stdout
        assert "aaa" not in blocks[-1].raw_stdout


async def test_demo_tab_then_pipe_does_not_trigger_line_nav(isolated_home):
    """Tab leaves focus on the journal; Enter there is line-cursor (F2), not submit."""
    scenario = {
        "title": "tab-pipe",
        "start_pause": 0,
        "type_delay": 0,
        "pause": 0,
        "command_timeout": 8,
        "steps": [
            {"type": "printf 'aaa\\nbbb\\n'", "enter": True, "wait_command": True, "pause": 0},
            {"keys": ["tab"], "pause": 0},
            {"type": "| grep bbb", "enter": True, "wait_command": True, "pause": 0},
        ],
    }
    app = CommandRunner(demo=scenario, demo_speed=20)
    async with app.run_test(size=(120, 40)) as pilot:
        deadline = time.monotonic() + 12
        while app._demo_active and time.monotonic() < deadline:
            await pilot.pause()
        assert app._demo_active is False
        blocks = list(app.query(CommandBlock))
        assert len(blocks) >= 2
        assert "bbb" in blocks[-1].raw_stdout
        assert "aaa" not in blocks[-1].raw_stdout
        assert not any(getattr(block, "line_nav_active", False) for block in blocks)


async def test_demo_slow_tab_pipe_f2_after_output(isolated_home):
    """F2 must not fire while `| grep` is still being typed (live-TUI race)."""
    nav_while_typing = []

    orig = CommandBlock.enter_line_nav

    def wrapped(self, notify=True):
        inp = input_widget(self.app)
        blocks = list(self.app.query(CommandBlock))
        nav_while_typing.append(
            {
                "input": inp.value if inp is not None else "",
                "n_blocks": len(blocks),
                "last": blocks[-1].raw_stdout if blocks else "",
            }
        )
        return orig(self, notify=notify)

    CommandBlock.enter_line_nav = wrapped
    try:
        scenario = {
            "title": "slow-f2",
            "start_pause": 0,
            "type_delay": 0.05,
            "pause": 0,
            "command_timeout": 8,
            "steps": [
                {"type": "printf 'aaa\\nbbb\\n'", "enter": True, "wait_command": True, "pause": 0},
                {"keys": ["tab"], "pause": 0.15},
                {"type": "| grep bbb", "enter": True, "wait_command": True, "pause": 0.2},
                {"keys": ["tab", "f2"], "pause": 0},
            ],
        }
        app = CommandRunner(demo=scenario, demo_speed=1)
        async with app.run_test(size=(120, 40)) as pilot:
            deadline = time.monotonic() + 20
            while app._demo_active and time.monotonic() < deadline:
                await pilot.pause()
            assert app._demo_active is False
            blocks = list(app.query(CommandBlock))
            assert len(blocks) >= 2
            assert "bbb" in blocks[-1].raw_stdout
            assert "aaa" not in blocks[-1].raw_stdout
            assert nav_while_typing, "F2/line-nav never ran"
            first = nav_while_typing[0]
            assert "bbb" in first["last"]
            assert "aaa" not in first["last"]
    finally:
        CommandBlock.enter_line_nav = orig


async def test_demo_help_mentions_flag(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":?")
        assert "--demo" in last_info(app).text_content
        assert isinstance(last_info(app), InfoBlock)


def test_resolve_custom_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    custom = tmp_path / "mine.yml"
    custom.write_text(
        "title: custom\nsteps:\n  - echo x\n",
        encoding="utf-8",
    )
    path = resolve_demo_path(str(custom))
    assert path == custom.resolve()
    scenario = load_scenario(path)
    assert scenario["steps"][0]["type"] == "echo x"
