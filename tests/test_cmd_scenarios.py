"""Автотесты по сценариям test_cmd.md (IDvjPy_term v1.1.18)."""
from pathlib import Path

import database_v2 as database
import pyperclip
from rich.text import Text
from app import CommandBlock, CommandRunner, InfoBlock

from tests.conftest import (
    confirm_input,
    input_widget,
    last_info,
    submit,
    wait_command_done,
)


def _cmd(app, tag, tid):
    return database.get_command_by_tid(app.db_file, tag, tid)


async def test_s01_variables(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "$PROJECT=/tmp/idivjopy_test")
        await submit(pilot, "$EDITOR=nvim")
        assert app.local_env["PROJECT"] == "/tmp/idivjopy_test"
        assert "Variable $EDITOR set to 'nvim'" in last_info(app).text_content

        await submit(pilot, "echo $PROJECT")
        block = await wait_command_done(app)
        assert "/tmp/idivjopy_test" in block.raw_stdout


async def test_s02_save_tags(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#start echo Starting app")
        await submit(pilot, "#test echo pytest -v")
        await submit(pilot, "#deploy echo restart nginx")
        await submit(pilot, "#backup echo rsync -av /data /backup")
        await submit(pilot, "#cfg echo A=B")
        assert "Saved:" in last_info(app).text_content
        assert _cmd(app, "backup", 1)["command"] == "echo rsync -av /data /backup"
        assert _cmd(app, "cfg", 1)["command"] == "echo A=B"


async def test_s02_references_saved_literal(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#start echo START")
        await submit(pilot, "#deploy echo DEPLOY")
        await submit(pilot, "#full !deploy[1] && !start[1]")
        saved = _cmd(app, "full", 1)["command"]
        assert saved == "!deploy[1] && !start[1]"

        await submit(pilot, "?full[1]")
        preview = last_info(app).text_content
        assert "!deploy[1] && !start[1]" in preview
        assert "echo DEPLOY && echo START" in preview


async def test_s02_edit_plus(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#dev echo original")
        await submit(pilot, "#dev+1 echo updated")
        assert "Updated dev[1]" in last_info(app).text_content
        assert _cmd(app, "dev", 1)["command"] == "echo updated"

        await submit(pilot, "#dev+1")
        assert input_widget(app).value == "#dev echo updated"


async def test_s03_vars_in_tagged_commands(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "$API=https://api.example.com")
        await submit(pilot, "#api echo endpoint=$API")
        await submit(pilot, "!api[1]")
        assert "echo endpoint=$API" in input_widget(app).value
        block = await confirm_input(pilot, app)
        assert "endpoint=https://api.example.com" in block.raw_stdout


async def test_s04_comments(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#start echo Starting app")
        await submit(pilot, "#start=Startup commands")
        await submit(pilot, "#start=1=Start in normal mode")

        await submit(pilot, "?")
        tags = last_info(app).text_content
        assert "start" in tags
        assert "Startup commands" in tags

        await submit(pilot, "?start")
        one = last_info(app).text_content
        one_plain = Text.from_markup(one).plain
        assert "Start in normal mode" in one
        assert "Start in normal mode" in one_plain
        assert "start[1]" in one_plain

        await submit(pilot, "??")
        all_cmds = last_info(app).text_content
        all_plain = Text.from_markup(all_cmds).plain
        assert "Startup commands" in all_cmds
        assert "Start in normal mode" in all_cmds
        assert "Start in normal mode" in all_plain
        assert "start[1]" in all_plain

        # #tag=ID= accepts global <id> (not only tid); missing id is an error
        await submit(pilot, "#other echo filler")
        await submit(pilot, "#start echo via-gid")
        start_rows = [r for r in database.get_commands_by_tag(app.db_file, "start")
                      if "via-gid" in r["command"]]
        assert start_rows
        gid = start_rows[0]["id"]
        tid = start_rows[0]["tid"]
        assert gid != tid
        await submit(pilot, f"#start={gid}=comment by global id")
        assert "comment set" in last_info(app).text_content
        assert database.get_command_comment(app.db_file, "start", tid) == "comment by global id"
        await submit(pilot, "?start")
        assert "comment by global id" in Text.from_markup(last_info(app).text_content).plain

        await submit(pilot, "#start=186=test comment")
        assert "not found" in last_info(app).text_content.lower()
        assert database.get_command_comment(app.db_file, "start", 186) == ""


async def test_s06_query(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#deploy echo restart nginx")
        await submit(pilot, "?")
        assert "deploy" in last_info(app).text_content

        await submit(pilot, "??")
        assert "echo restart nginx" in last_info(app).text_content
        assert "deploy[1]" in last_info(app).text_content

        await submit(pilot, "?missing")
        assert "None found" in last_info(app).text_content


async def test_s07_bang_insert(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#deploy echo restart nginx")
        await submit(pilot, "!deploy[1]")
        assert input_widget(app).value == "echo restart nginx"

        await submit(pilot, "!1")
        assert "echo restart nginx" in input_widget(app).value

        await submit(pilot, "!deploy[999]")
        assert "not found" in last_info(app).text_content.lower()

        await submit(pilot, "!notanumber")
        assert "Invalid syntax" in last_info(app).text_content


async def test_s08_double_bang(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#deploy echo DEPLOY")
        await submit(pilot, "#start echo START")

        await submit(pilot, "!! deploy[1] start[1]")
        assert input_widget(app).value == "echo DEPLOY echo START"

        await submit(pilot, "!! deploy[1];start[1]")
        assert input_widget(app).value == "echo DEPLOY ; echo START"

        await submit(pilot, "!! deploy[1]&&start[1]")
        assert input_widget(app).value == "echo DEPLOY && echo START"


async def test_s09_autoload_on_restart(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#a echo ONE")
        await submit(pilot, "#b echo TWO")

    app2 = CommandRunner()
    async with app2.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "!! 1 2")
        assert "echo ONE" in input_widget(app2).value
        assert "echo TWO" in input_widget(app2).value


async def test_s10_pipe(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "printf 'alpha.py\\nbeta.txt\\ngamma.py\\n'")
        src = await wait_command_done(app)
        assert "alpha.py" in src.raw_stdout

        await submit(pilot, "| grep py")
        piped = await wait_command_done(app)
        assert "alpha.py" in piped.raw_stdout
        assert "gamma.py" in piped.raw_stdout
        assert "beta.txt" not in piped.raw_stdout


async def test_s11_nav_history_copy(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo first")
        first = await wait_command_done(app)
        await submit(pilot, "echo second")
        await wait_command_done(app)

        await pilot.press("escape")
        await pilot.press("up")
        assert input_widget(app).value == "echo second"
        await pilot.press("escape")
        await pilot.press("up")
        assert input_widget(app).value == "echo first"

        first.focus()
        await pilot.pause()
        await pilot.press("f3")
        await pilot.pause()
        assert "first" in pyperclip.paste()
        assert app.sub_title == app.MSG_COPIED


async def test_s12_colon_commands(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo hist-line")
        await wait_command_done(app)
        await submit(pilot, "echo hist-line-2")
        await wait_command_done(app)

        info_before = len(list(app.query(InfoBlock)))
        await submit(pilot, ":h")
        infos = list(app.query(InfoBlock))
        assert len(infos) == info_before + 1
        hist = last_info(app).text_content
        assert "echo hist-line" in hist
        assert "echo hist-line-2" in hist
        assert "\n" in hist.strip()

        await submit(pilot, ":w test_output.txt")
        assert "written to" in last_info(app).text_content
        dumped = Path("test_output.txt").read_text(encoding="utf-8")
        assert "hist-line" in dumped

        await submit(pilot, ":?")
        help_text = last_info(app).text_content
        assert ":" in help_text or "help" in help_text.lower() or "JSON" in help_text

        await submit(pilot, ":c")
        assert "All blocks cleared" in last_info(app).text_content
        assert list(app.query(CommandBlock)) == []


async def test_s13_delete(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#cleanup echo temp1")
        await submit(pilot, "#cleanup echo temp2")
        await submit(pilot, "#cleanup-1")
        await submit(pilot, "?cleanup")
        listing = last_info(app).text_content
        assert "temp1" not in listing
        assert "temp2" in listing

        await submit(pilot, "#cleanup-")
        await submit(pilot, "?cleanup")
        assert "None found" in last_info(app).text_content


async def test_s14_aliases(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        app.aliases["mytest"] = "echo Hello from alias"
        await submit(pilot, "mytest")
        block = await wait_command_done(app)
        assert "Hello from alias" in block.raw_stdout


async def test_s15_errors_timeout_truncate(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "ls /no-such-idivjopy-dir")
        failed = await wait_command_done(app)
        assert failed.return_code != 0
        assert failed.raw_stderr.strip() != ""

        await submit(pilot, "sleep 8")
        timed = await wait_command_done(app, timeout=12)
        assert timed.return_code == 124
        assert "timed out" in timed.raw_stderr.lower()

        await submit(pilot, "seq 1 400")
        long_block = await wait_command_done(app)
        assert long_block._truncated
        assert "400" in long_block.raw_stdout
        assert "truncated" in long_block._format_output().lower()


async def test_s16_dev_cycle(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "$PROJECT=myapp")
        await submit(pilot, "#dev echo run-$PROJECT")
        await submit(pilot, "#dev echo pytest")
        await submit(pilot, "#dev=Development workflow")
        await submit(pilot, "#dev=1=Run app")

        await submit(pilot, "!dev[1]")
        assert "echo run-$PROJECT" in input_widget(app).value
        block = await confirm_input(pilot, app)
        assert "run-myapp" in block.raw_stdout

        await submit(pilot, "!! dev[1];dev[2]")
        assert "echo run-$PROJECT ; echo pytest" == input_widget(app).value


async def test_s17_edge_cases(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#")
        assert "Invalid syntax" in last_info(app).text_content

        await submit(pilot, "!abc[xyz]")
        assert "Invalid syntax" in last_info(app).text_content

        await submit(pilot, "!9999")
        assert "not found" in last_info(app).text_content.lower()

        await submit(pilot, "#special echo ok")
        await submit(pilot, "#special=chars @#$")
        await submit(pilot, "#special=1=Test @#$%")
        assert "comment set" in last_info(app).text_content
        await submit(pilot, "?special")
        text = last_info(app).text_content
        assert "chars @#$" in text
        assert "Test @#$%" in text


async def test_s18_many_commands(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        for i in range(1, 9):
            await submit(pilot, f"#perf echo test {i}")
        await submit(pilot, "??")
        listing = last_info(app).text_content
        assert "test 1" in listing
        assert "test 8" in listing
        assert "perf[8]" in listing


async def test_s21_ingress_help(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":i")
        help_text = last_info(app).text_content
        assert "list" in help_text.lower() or "ingress" in help_text.lower() or "Usage" in help_text

        await submit(pilot, ":i list -n")
        err = last_info(app).text_content
        assert "Missing namespace" in err or "Usage" in err
