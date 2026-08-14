"""Базовые сценарии: ввод, выполнение, история, переменные, выход."""
from app import CommandBlock, CommandRunner, InfoBlock

from tests.conftest import input_widget, last_info, submit, type_keys, wait_command_done


async def test_app_starts_with_input_focused(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert input_widget(app).has_focus
        welcome = " ".join(block.text_content for block in app.query(InfoBlock))
        assert "IDvjPy_term" in welcome


async def test_echo_command_creates_block(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo ok-from-test")
        block = await wait_command_done(app)
        assert "ok-from-test" in block.raw_stdout
        assert block.return_code == 0
        assert input_widget(app).value == ""


async def test_failed_command_shows_stderr(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "ls /this-path-does-not-exist-idivjopy")
        block = await wait_command_done(app)
        assert block.return_code != 0
        assert block.raw_stderr.strip() != ""


async def test_empty_enter_does_not_create_command_block(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "")
        assert list(app.query(CommandBlock)) == []


async def test_session_history_up_down(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo first")
        await wait_command_done(app)
        await submit(pilot, "echo second")
        await wait_command_done(app)

        await pilot.press("escape")
        await pilot.press("up")
        assert input_widget(app).value == "echo second"
        # После подстановки истории может открыться completion — Up уйдёт в список.
        await pilot.press("escape")
        await pilot.press("up")
        assert input_widget(app).value == "echo first"
        await pilot.press("escape")
        await pilot.press("down")
        assert input_widget(app).value == "echo second"


async def test_variable_assignment_and_substitution(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "$FOO=bar-test")
        assert "Variable $FOO set to 'bar-test'" in last_info(app).text_content
        assert app.local_env["FOO"] == "bar-test"

        await submit(pilot, "echo $FOO")
        block = await wait_command_done(app)
        assert "bar-test" in block.raw_stdout


async def test_colon_clear_and_quit(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo keep-me")
        await wait_command_done(app)
        await submit(pilot, ":c")
        texts = [block.text_content for block in app.query(InfoBlock)]
        assert any("All blocks cleared" in text for text in texts)
        assert list(app.query(CommandBlock)) == []

        await submit(pilot, ":q")
    # Context manager exits cleanly after :q.


async def test_shift_insert_pastes_into_input(isolated_home, monkeypatch):
    monkeypatch.setattr("pyperclip.paste", lambda: "pasted-value")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("escape")
        await type_keys(pilot, "echo ")
        await pilot.press("shift+insert")
        await pilot.pause()
        assert "pasted-value" in input_widget(app).value
