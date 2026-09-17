"""Полуавтоматический прогон цепочки команд: `:run` (runbook).

Разбор плана (директивы `run:` в комментариях тега, YAML) — юнит-тестами;
проигрывание (auto/manual/prompt, стоп по ошибке и по Esc) — Pilot-сценариями.
"""
from __future__ import annotations

import asyncio
import time

import pytest

pytestmark = pytest.mark.slow

import database_v2 as database
from app import CommandBlock, CommandRunner, InfoBlock
from runbook import (
    MODE_AUTO,
    MODE_MANUAL,
    MODE_PROMPT,
    RunbookError,
    build_plan,
    format_plan,
    parse_directives,
    steps_from_tag,
    steps_from_yaml,
    tags_with_directives,
    usage_text,
)
from tests.conftest import input_widget, last_info, submit, type_keys


def _db(tmp_path) -> str:
    db = str(tmp_path / "runbook.db")
    database.init_db(db)
    return db


def _add(db: str, command: str, tag: str = "chain", comment: str = "") -> int:
    tid = database.add_command(db, command, tag)
    if comment:
        database.set_command_comment(db, tag, tid, comment)
    return tid


async def _wait_run_done(app: CommandRunner, timeout: float = 20.0) -> None:
    deadline = time.monotonic() + timeout
    while app._run_active and time.monotonic() < deadline:
        await asyncio.sleep(0.05)
    assert not app._run_active, "runbook did not finish in time"


async def _wait_armed(app: CommandRunner, index: int, timeout: float = 10.0) -> None:
    """Дождаться, что прогон дошёл до шага `index` и ждёт человека."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = app._run_state or {}
        if state.get("index") == index and f"· {index}/" in (app.sub_title or ""):
            return
        await asyncio.sleep(0.05)
    raise AssertionError(f"runbook did not reach step {index}: {app.sub_title!r}")


def _info_text(app: CommandRunner) -> str:
    return "\n".join(block.text_content for block in app.query(InfoBlock))


async def _enter_line(pilot, app: CommandRunner, text: str) -> None:
    """Отправить строку без Esc: `conftest.submit` жмёт Esc, а он остановит прогон."""
    inp = input_widget(app)
    inp.value = text
    inp.cursor_position = len(text)
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()


def _stdouts(app: CommandRunner) -> list[str]:
    return [block.raw_stdout.strip() for block in app.query(CommandBlock)]


# --- разбор плана ------------------------------------------------------------


def test_parse_directives_modes_and_hint():
    spec, warnings = parse_directives("run:manual подтвердите выпуск секрета")
    assert (spec.mode, spec.hint, warnings) == (MODE_MANUAL, "подтвердите выпуск секрета", [])
    assert parse_directives("run:prompt")[0].mode == MODE_PROMPT
    assert parse_directives("run:auto run:pause=2")[0].mode == MODE_AUTO
    assert parse_directives("run:auto run:pause=2")[0].pause == 2.0
    # Без директив комментарий остаётся обычным комментарием, режим — auto.
    spec, warnings = parse_directives("role_id из табличного вывода")
    assert (spec.mode, spec.hint, warnings) == (MODE_AUTO, "role_id из табличного вывода", [])


def test_parse_directives_continue_and_bad_values():
    assert parse_directives("run:continue шаг не важен")[0].stop_on_error is False
    spec, warnings = parse_directives(None or "")
    assert (spec.mode, spec.hint, spec.pause, spec.stop_on_error) == (MODE_AUTO, "", None, True)
    spec, warnings = parse_directives("run:pause=abc шаг")
    assert spec.pause is None and warnings and "пауза" in warnings[0]
    spec, warnings = parse_directives("run:nope остальное")
    # Неизвестная директива не съедает комментарий: он остаётся подсказкой.
    assert spec.hint == "run:nope остальное" and warnings


def test_parse_directives_inherits_tag_defaults():
    base, _ = parse_directives("run:pause=1.5 run:continue")
    spec, _ = parse_directives("run:manual шаг", base=base)
    assert spec.pause == 1.5 and spec.stop_on_error is False
    assert spec.mode == MODE_MANUAL  # режим шага не наследуется от тега
    assert parse_directives("", base=base)[0].mode == MODE_AUTO


def test_steps_from_tag_reads_directives(tmp_path):
    db = _db(tmp_path)
    _add(db, "echo one", comment="run:manual проверьте")
    _add(db, "echo two")
    database.set_tag_comment(db, "chain", "run:pause=1.5 цепочка")
    plan = steps_from_tag(db, "chain")
    assert plan.title == "chain" and plan.source == "chain"
    assert [step.mode for step in plan.steps] == [MODE_MANUAL, MODE_AUTO]
    assert [step.text for step in plan.steps] == ["echo one", "echo two"]
    assert plan.steps[0].hint == "проверьте"
    assert plan.pause == 1.5 and plan.steps[1].pause == 1.5
    assert [step.origin for step in plan.steps] == ["chain[1]", "chain[2]"]


def test_steps_from_tag_missing_tag(tmp_path):
    db = _db(tmp_path)
    with pytest.raises(RunbookError) as excinfo:
        steps_from_tag(db, "nosuch")
    assert "not found" in str(excinfo.value)


def test_tags_with_directives(tmp_path):
    db = _db(tmp_path)
    _add(db, "echo one", tag="chain", comment="run:manual шаг")
    _add(db, "echo two", tag="other")
    assert tags_with_directives(db) == [("chain", 1)]
    assert "Runbook tags" in usage_text(db)
    assert "chain" in usage_text(db)


def test_steps_from_yaml_modes_and_errors(tmp_path):
    path = tmp_path / "chain.yml"
    path.write_text(
        "title: deploy\n"
        "pause: 0.1\n"
        "steps:\n"
        "  - echo one\n"
        "  - type: echo two\n"
        "    manual: true\n"
        "    caption: подтвердите\n"
        "  - prompt: имя роли\n"
        "  - type: echo four\n"
        "    pause: 2\n"
        "    stop_on_error: false\n",
        encoding="utf-8",
    )
    plan = steps_from_yaml(str(path))
    assert plan.title == "deploy" and plan.pause == 0.1
    assert [step.mode for step in plan.steps] == [MODE_AUTO, MODE_MANUAL, MODE_PROMPT, MODE_AUTO]
    assert plan.steps[1].hint == "подтвердите"
    assert plan.steps[2].hint == "имя роли" and plan.steps[2].text == ""
    assert plan.steps[3].pause == 2 and plan.steps[3].stop_on_error is False

    with pytest.raises(RunbookError):
        steps_from_yaml(str(tmp_path / "nope.yml"))
    empty = tmp_path / "empty.yml"
    empty.write_text("title: x\n", encoding="utf-8")
    with pytest.raises(RunbookError):
        steps_from_yaml(str(empty))
    plain = tmp_path / "plain.yml"
    plain.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(RunbookError):
        steps_from_yaml(str(plain))


def test_steps_from_yaml_ignores_demo_keys_with_note(tmp_path):
    """`:playbook`-файл должен приниматься прогоном (демо-ключи не мешают)."""
    path = tmp_path / "play.yml"
    path.write_text(
        "title: session playbook\n"
        "start_pause: 0.6\n"
        "type_delay: 0.03\n"
        "pause: 0.1\n"
        "command_timeout: 12\n"
        "steps:\n"
        "  - type: echo one\n"
        "    wait_command: true\n"
        "  - echo two\n"
        "  - type: echo three\n"
        "    unknown_key: 1\n",
        encoding="utf-8",
    )
    plan = steps_from_yaml(str(path))
    assert [step.text for step in plan.steps] == ["echo one", "echo two", "echo three"]
    assert all(step.mode == MODE_AUTO for step in plan.steps)
    assert any("unknown_key" in warning for warning in plan.warnings)


def test_build_plan_step_flag_and_routing(tmp_path):
    db = _db(tmp_path)
    _add(db, "echo one", comment="run:prompt набрать")
    _add(db, "echo two")
    plain = build_plan(db, "chain")
    assert [step.mode for step in plain.steps] == [MODE_PROMPT, MODE_AUTO]
    stepped = build_plan(db, "chain", step=True)
    # `--step`: auto-шаги становятся manual, prompt остаётся prompt.
    assert [step.mode for step in stepped.steps] == [MODE_PROMPT, MODE_MANUAL]
    path = tmp_path / "chain.yml"
    path.write_text("steps:\n  - echo file-one\n", encoding="utf-8")
    assert build_plan(db, str(path)).steps[0].text == "echo file-one"
    with pytest.raises(RunbookError):
        build_plan(db, "")
    with pytest.raises(RunbookError):
        build_plan(db, str(tmp_path / "missing.yml"))


def test_format_plan_lists_modes_and_hints(tmp_path):
    db = _db(tmp_path)
    _add(db, "echo one", comment="run:manual проверьте вывод")
    text = format_plan(build_plan(db, "chain"), dry=True)
    assert "Runbook chain" in text and "dry run" in text
    assert "manual" in text and "проверьте вывод" in text


# --- проигрывание -------------------------------------------------------------


async def test_run_auto_chain_finishes(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    database.add_command(str(db), "echo step-one", "chain")
    database.add_command(str(db), "echo step-two", "chain")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run chain")
        await _wait_run_done(app)
        assert _stdouts(app) == ["step-one", "step-two"]
        assert "Runbook chain: 2 step(s) done." in _info_text(app)
        # `:run` — запрос в историю (↑/`:h`), но не в подсказки: шаги видны там же.
        assert ":run chain" in app._read_file_history()


async def test_run_manual_step_waits_for_enter(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    database.add_command(str(db), "echo auto-first", "chain")
    tid = database.add_command(str(db), "echo manual-second", "chain")
    database.set_command_comment(str(db), "chain", tid, "run:manual подтвердите вывод")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run chain")
        await _wait_armed(app, 2)
        # Строка вставлена в ввод, но не выполнена: ждём человека.
        assert input_widget(app).value == "echo manual-second"
        assert _stdouts(app) == ["auto-first"]

        await pilot.press("enter")
        await _wait_run_done(app)
        assert _stdouts(app) == ["auto-first", "manual-second"]
        assert "Runbook chain: 2 step(s) done." in _info_text(app)


async def test_run_prompt_step_waits_for_typed_line(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    tid = database.add_command(str(db), "echo placeholder", "chain")
    database.set_command_comment(str(db), "chain", tid, "run:prompt введите команду")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run chain")
        await _wait_armed(app, 1)
        assert input_widget(app).value == ""  # ничего не навязано
        assert "введите команду" in _info_text(app)

        await type_keys(pilot, "echo typed-by-human")
        await pilot.press("enter")
        await _wait_run_done(app)
        assert _stdouts(app) == ["typed-by-human"]
        assert "echo placeholder" not in _stdouts(app)


async def test_run_empty_enter_skips_manual_step(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    tid = database.add_command(str(db), "echo skipped", "chain")
    database.set_command_comment(str(db), "chain", tid, "run:manual необязательный")
    database.add_command(str(db), "echo after", "chain")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run chain")
        await _wait_armed(app, 1)
        input_widget(app).value = ""  # человек стёр строку и нажал Enter — пропуск
        await pilot.press("enter")
        await _wait_run_done(app)
        assert _stdouts(app) == ["after"]


async def test_run_stops_on_error(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    database.add_command(str(db), "sh -c 'exit 3'", "chain")
    database.add_command(str(db), "echo never", "chain")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run chain")
        await _wait_run_done(app)
        assert _stdouts(app) == [""]
        text = _info_text(app)
        assert "Runbook chain stopped" in text and "exited 3" in text
        assert "echo never" not in _stdouts(app)


async def test_run_continue_keeps_going_after_error(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    tid = database.add_command(str(db), "sh -c 'exit 4'", "chain")
    database.set_command_comment(str(db), "chain", tid, "run:continue диагностика")
    database.add_command(str(db), "echo still-here", "chain")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run chain")
        await _wait_run_done(app)
        assert _stdouts(app) == ["", "still-here"]
        assert "2 step(s) done" in _info_text(app)


async def test_esc_stops_runbook_waiting_for_human(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    database.add_command(str(db), "echo first-stop", "chain")
    tid = database.add_command(str(db), "echo second-stop", "chain")
    database.set_command_comment(str(db), "chain", tid, "run:manual подождать")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run chain")
        await _wait_armed(app, 2)
        await pilot.press("escape")
        await pilot.pause()
        assert not app._run_active
        text = _info_text(app)
        assert "stopped at step 2/2" in text
        # Второй шаг не выполнялся: останавливаться до запуска — смысл manual.
        assert _stdouts(app) == ["first-stop"]


async def test_run_stop_command(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    tid = database.add_command(str(db), "echo first-stop-cmd", "chain")
    database.set_command_comment(str(db), "chain", tid, "run:manual стоп по команде")
    database.add_command(str(db), "echo never-again", "chain")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run chain")
        await _wait_armed(app, 1)
        await _enter_line(pilot, app, ":run stop")
        assert not app._run_active
        assert "stopped at step 1/2" in _info_text(app)


async def test_run_dry_does_not_execute(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    tid = database.add_command(str(db), "echo dry-one", "chain")
    database.set_command_comment(str(db), "chain", tid, "run:manual проверьте")
    database.add_command(str(db), "echo dry-two", "chain")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run chain --dry")
        text = _info_text(app)
        assert "dry run" in text and "echo dry-one" in text and "manual" in text
        assert not app.query(CommandBlock)
        assert not app._run_active


async def test_run_help_topic(isolated_home):
    """:? run` — справка по прогону, `:run` в ней кликабелен."""
    app = CommandRunner()
    async with app.run_test(size=(110, 40)) as pilot:
        await submit(pilot, ":? run")
        text = last_info(app).text_content
        assert "Runbook" in text and "run:manual" in text and "--step" in text
        assert "insert_colon_draft('run')" in text


async def test_run_usage_and_unknown_target(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    tid = database.add_command(str(db), "echo usage-one", "chain")
    database.set_command_comment(str(db), "chain", tid, "run:manual шаг")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run")
        text = _info_text(app)
        assert "Usage: :run" in text and "chain" in text

        await submit(pilot, ":run nosuch --step")
        assert "not found" in _info_text(app)
        assert not app._run_active

        await submit(pilot, ":run chain --nope")
        assert "Unknown flag(s): --nope" in _info_text(app)


async def test_run_from_yaml_file(isolated_home):
    (isolated_home / "chain.yml").write_text(
        "title: file-chain\n"
        "pause: 0.05\n"
        "steps:\n"
        "  - echo from-file\n"
        "  - type: echo manual-file\n"
        "    manual: true\n"
        "    caption: проверьте файл\n"
        "  - echo tail-file\n",
        encoding="utf-8",
    )
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run chain.yml")
        await _wait_armed(app, 2)
        assert input_widget(app).value == "echo manual-file"
        assert _stdouts(app) == ["from-file"]
        await pilot.press("enter")
        await _wait_run_done(app)
        assert _stdouts(app) == ["from-file", "manual-file", "tail-file"]
        assert "Runbook file-chain: 3 step(s) done." in _info_text(app)


async def test_run_refuses_while_another_runs(isolated_home):
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    tid = database.add_command(str(db), "echo hold-on", "chain")
    database.set_command_comment(str(db), "chain", tid, "run:manual держим")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":run chain")
        await _wait_armed(app, 1)
        await _enter_line(pilot, app, ":run chain")
        assert "already running" in _info_text(app)
        await _enter_line(pilot, app, ":run stop")
        assert not app._run_active


async def test_run_watch_and_run_do_not_interfere(isolated_home):
    """:watch во время прогона и `:run` во время watch — оба отказа явные."""
    db = isolated_home / "test_history.db"
    database.init_db(str(db))
    tid = database.add_command(str(db), "echo watch-hold", "chain")
    database.set_command_comment(str(db), "chain", tid, "run:manual ждём")
    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        await submit(pilot, ":watch 5 echo tick")
        await pilot.pause()
        await _enter_line(pilot, app, ":run chain")
        assert "watch is running" in _info_text(app)
        await _enter_line(pilot, app, ":watch stop")
        await pilot.pause()
