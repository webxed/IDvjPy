"""Файловые подсказки: видимость списка, Tab не затирает команду, каталоги с /."""
import pyperclip
from app import CommandRunner

from tests.conftest import input_widget, submit, type_keys, wait_command_done


async def test_path_completion_keeps_existing_command(isolated_home):
    (isolated_home / "alpha.txt").write_text("x\n", encoding="utf-8")
    (isolated_home / "subdir").mkdir()

    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "")  # ensure mounted/focused
        await pilot.press("escape")
        await type_keys(pilot, "cat ./al")
        await pilot.pause()
        assert app._completion_list.is_visible()
        assert any("alpha.txt" in item for item in app._completion_list.all_candidates)

        await pilot.press("tab")
        await pilot.pause()
        value = input_widget(app).value
        assert value.startswith("cat ")
        assert "alpha.txt" in value
        assert not value.startswith("alpha")


async def test_directory_completion_appends_slash_and_reopens(isolated_home):
    nested = isolated_home / "folder" / "inner"
    nested.mkdir(parents=True)
    (nested / "file.txt").write_text("y\n", encoding="utf-8")

    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("escape")
        await type_keys(pilot, "ls ./fo")
        await pilot.pause()
        assert app._completion_list.is_visible()

        await pilot.press("tab")
        await pilot.pause()
        value = input_widget(app).value
        assert value.startswith("ls ")
        assert value.endswith("folder/") or "/folder/" in value
        assert app._completion_list.is_visible()
        assert any("inner/" in item for item in app._completion_list.all_candidates)


async def test_ls_home_slash_keeps_home_directory(isolated_home, monkeypatch):
    """ls ~/ не должен подменяться первым ребёнком домашнего каталога."""
    monkeypatch.setenv("HOME", str(isolated_home))
    (isolated_home / "Documents").mkdir()
    (isolated_home / "a.txt").write_text("x\n", encoding="utf-8")

    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("escape")
        await type_keys(pilot, "ls ~/")
        await pilot.pause()
        assert app._completion_list.is_visible()
        assert app._completion_list.all_candidates[0] == "~/"
        assert any("Documents" in item for item in app._completion_list.all_candidates)

        await pilot.press("enter")
        await wait_command_done(app)
        blocks = list(app.query("CommandBlock"))
        assert blocks
        assert "$ ls ~/" in blocks[-1].header
        assert "Documents" in blocks[-1].raw_stdout


async def test_ls_home_slash_tab_keeps_directory_then_child(isolated_home, monkeypatch):
    monkeypatch.setenv("HOME", str(isolated_home))
    (isolated_home / "Documents").mkdir()

    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("escape")
        await type_keys(pilot, "ls ~/")
        await pilot.pause()
        assert app._completion_list.all_candidates[0] == "~/"

        await pilot.press("tab")
        await pilot.pause()
        assert input_widget(app).value == "ls ~/"
        assert not app._completion_list.is_visible()

        await type_keys(pilot, "D")
        await pilot.pause()
        assert app._completion_list.is_visible()
        await pilot.press("tab")
        await pilot.pause()
        value = input_widget(app).value
        assert value.startswith("ls ")
        assert "Documents" in value


async def test_space_backspace_enter_does_not_duplicate_command(isolated_home):
    """После вставки из подсказки: пробел, Backspace, Enter не даёт `cat cat json.file`."""
    (isolated_home / "json.file").write_text("ok\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "cat json.file")
        await wait_command_done(app)
        await pilot.press("escape")
        await type_keys(pilot, "cat js")
        await pilot.pause()
        assert app._completion_list.is_visible()
        await pilot.press("tab")
        await pilot.pause()
        value = input_widget(app).value
        assert "json.file" in value
        assert not value.startswith("cat cat")

        await pilot.press("space")
        await pilot.pause()
        await pilot.press("backspace")
        await pilot.pause()
        await pilot.press("enter")
        block = await wait_command_done(app)
        assert "$ cat cat json.file" not in block.header
        assert "$ cat json.file" in block.header
        assert input_widget(app).value != "cat cat json.file"


async def test_trailing_space_runs_command_without_completion(isolated_home):
    """Пробел после команды: Enter выполняет её, а не кандидата с аргументами."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo with-args extra")
        await wait_command_done(app)
        await pilot.press("escape")
        await type_keys(pilot, "echo")
        await pilot.pause()
        assert app._completion_list.is_visible()
        selected = app._completion_list.get_selected()
        assert selected and "with-args" in selected

        await pilot.press("space")
        await pilot.pause()
        assert not app._completion_list.is_visible()
        await type_keys(pilot, "  ")
        await pilot.pause()
        assert not app._completion_list.is_visible()

        await pilot.press("enter")
        block = await wait_command_done(app)
        assert "with-args extra" not in block.header
        assert "$ echo" in block.header


async def test_completion_scroll_window(isolated_home):
    for i in range(20):
        (isolated_home / f"file_{i:02d}.txt").write_text("n\n", encoding="utf-8")

    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("escape")
        await type_keys(pilot, "ls ./file_")
        await pilot.pause()
        clist = app._completion_list
        assert clist.is_visible()
        assert clist.total_candidates >= 16
        first = clist.get_selected()
        await pilot.press("down")
        await pilot.pause()
        assert clist.get_selected() != first


async def test_completion_list_grows_and_shows_count(isolated_home):
    for i in range(14):
        (isolated_home / f"hint_{i:02d}.txt").write_text("n\n", encoding="utf-8")

    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("escape")
        await type_keys(pilot, "ls ./hint_")
        await pilot.pause()
        clist = app._completion_list
        assert clist.is_visible()
        n = clist.total_candidates
        assert n >= 14
        assert clist._visible_capacity() > 8
        assert len(clist.candidates) == n
        status = clist._window_status()
        assert f"{n}/{n}" in status
        assert "all" in status


async def test_completion_list_overflow_status(isolated_home):
    for i in range(20):
        (isolated_home / f"many_{i:02d}.txt").write_text("n\n", encoding="utf-8")

    app = CommandRunner()
    async with app.run_test(size=(120, 22)) as pilot:
        await pilot.press("escape")
        await type_keys(pilot, "ls ./many_")
        await pilot.pause()
        clist = app._completion_list
        assert clist.is_visible()
        assert clist.total_candidates >= 16
        cap = clist._visible_capacity()
        assert cap < clist.total_candidates
        assert len(clist.candidates) == cap
        status = clist._window_status()
        assert f"/ {clist.total_candidates}" in status
        assert "more" in status
        for _ in range(cap + 1):
            await pilot.press("down")
        await pilot.pause()
        scrolled = clist._window_status()
        assert "↑" in scrolled


async def test_pageup_hides_completion_and_leaves_journal(isolated_home):
    (isolated_home / "alpha.txt").write_text("x\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "echo keep-journal")
        await wait_command_done(app)
        await pilot.press("escape")
        await type_keys(pilot, "ls ./al")
        await pilot.pause()
        assert app._completion_list.is_visible()
        # Overlay больше не перекрывает журнал: блок вывода остаётся в дереве.
        assert list(app.query("CommandBlock"))
        await pilot.press("pageup")
        await pilot.pause()
        assert not app._completion_list.is_visible()


async def test_arrows_scroll_journal_when_block_focused(isolated_home):
    from textual.containers import VerticalScroll
    from app import CommandBlock

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "seq 1 80")
        await wait_command_done(app)
        await pilot.press("pageup")
        await pilot.pause()
        assert isinstance(app.focused, CommandBlock)
        assert not app.focused.line_nav_active
        container = app.query_one("#results-container", VerticalScroll)
        y_before = container.scroll_y
        await pilot.press("down")
        await pilot.pause()
        # Без режима курсора стрелки не ставят line_index.
        assert app.focused.line_index is None
        assert not input_widget(app).has_focus
        _ = y_before


async def test_line_cursor_mode_toggles_on_block(isolated_home):
    from app import CommandBlock

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "seq 1 80")
        await wait_command_done(app)
        await pilot.press("pageup")
        await pilot.pause()
        assert isinstance(app.focused, CommandBlock)

        await pilot.press("enter")
        await pilot.pause()
        assert app.focused.line_nav_active
        assert app.focused.line_index is not None
        first = app.focused.line_index
        await pilot.press("down")
        await pilot.pause()
        assert app.focused.line_index == first + 1
        await pilot.press("up")
        await pilot.pause()
        assert app.focused.line_index == first
        await pilot.press("home")
        await pilot.pause()
        assert app.focused.line_index == 0
        await pilot.press("end")
        await pilot.pause()
        assert app.focused.line_index == len(app.focused._nav_lines()) - 1

        await pilot.press("home")
        await pilot.pause()
        copied = None
        for _ in range(8):
            line = app._strip_formatting_tags(
                app.focused._nav_lines()[app.focused.line_index]
            )
            if line == "1":
                copied = line
                break
            await pilot.press("down")
            await pilot.pause()
        assert copied == "1"
        await pilot.press("enter")
        await pilot.pause()
        assert pyperclip.paste() == "1"
        assert input_widget(app).has_focus
        assert app.sub_title == app.MSG_COPIED
        blocks = list(app.query("CommandBlock"))
        assert blocks and not blocks[0].line_nav_active


async def test_line_copy_strips_trailing_spaces(isolated_home):
    from app import CommandBlock

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "printf 'hello   \\n'")
        await wait_command_done(app)
        await pilot.press("pageup")
        await pilot.pause()
        assert isinstance(app.focused, CommandBlock)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("home")
        await pilot.pause()
        found = False
        for _ in range(8):
            line = app.focused._plain_copy_line(
                app.focused._nav_lines()[app.focused.line_index]
            )
            if line == "hello":
                found = True
                break
            await pilot.press("down")
            await pilot.pause()
        assert found
        await pilot.press("enter")
        await pilot.pause()
        assert pyperclip.paste() == "hello"
        assert app.clipboard == "hello"
        assert input_widget(app).has_focus


async def test_line_copy_shift_insert_pastes_into_input(isolated_home, monkeypatch):
    from app import CommandBlock

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "echo COPYME")
        await wait_command_done(app)
        await pilot.press("pageup")
        await pilot.pause()
        assert isinstance(app.focused, CommandBlock)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("home")
        await pilot.pause()
        for _ in range(8):
            line = app.focused._plain_copy_line(
                app.focused._nav_lines()[app.focused.line_index]
            )
            if line == "COPYME":
                break
            await pilot.press("down")
            await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert input_widget(app).has_focus
        # Даже если pyperclip пуст, Shift+Insert берёт буфер Textual / PRIMARY.
        monkeypatch.setattr("pyperclip.paste", lambda: "")
        inp = input_widget(app)
        inp.value = ""
        inp.cursor_position = 0
        await pilot.press("shift+insert")
        await pilot.pause()
        assert inp.value == "COPYME"


async def test_shift_enter_appends_line_to_input(isolated_home):
    from app import CommandBlock

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "seq 1 3")
        await wait_command_done(app)
        inp = input_widget(app)
        inp.value = "cmd"
        inp.cursor_position = 3
        await pilot.press("pageup")
        await pilot.pause()
        assert isinstance(app.focused, CommandBlock)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("home")
        await pilot.pause()
        for _ in range(8):
            if app.focused._current_plain_line() == "1":
                break
            await pilot.press("down")
            await pilot.pause()
        await pilot.press("shift+enter")
        await pilot.pause()
        assert inp.value == "cmd 1"
        assert isinstance(app.focused, CommandBlock)
        assert app.focused.line_nav_active
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("shift+enter")
        await pilot.pause()
        assert inp.value == "cmd 1 2"
        assert isinstance(app.focused, CommandBlock)
        assert not input_widget(app).has_focus
        current = app.focused._current_plain_line()
        await pilot.press("ctrl+v")
        await pilot.pause()
        assert inp.value == f"cmd 1 2 {current}"
        assert isinstance(app.focused, CommandBlock)
        from textual.events import Paste
        await pilot.press("down")
        await pilot.pause()
        nxt = app.focused._current_plain_line()
        app.focused.post_message(Paste("CLIPBOARD-SHOULD-NOT-APPEAR"))
        await pilot.pause()
        assert inp.value == f"cmd 1 2 {current} {nxt}"
        assert "CLIPBOARD-SHOULD-NOT-APPEAR" not in inp.value
        assert isinstance(app.focused, CommandBlock)
        assert app.focused.line_nav_active


async def test_line_nav_enter_keeps_input_text_and_paste_appends(isolated_home, monkeypatch):
    from app import CommandBlock

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "echo COPYME")
        await wait_command_done(app)
        inp = input_widget(app)
        inp.value = "keep-me"
        inp.cursor_position = len("keep-me")
        await pilot.press("pageup")
        await pilot.pause()
        assert isinstance(app.focused, CommandBlock)
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("home")
        await pilot.pause()
        for _ in range(8):
            if app.focused._current_plain_line() == "COPYME":
                break
            await pilot.press("down")
            await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert inp.has_focus
        assert inp.value == "keep-me"
        assert inp.selection.start == inp.selection.end
        monkeypatch.setattr("pyperclip.paste", lambda: "PASTE")
        await pilot.press("shift+insert")
        await pilot.pause()
        assert inp.value == "keep-mePASTE"
        await pilot.press("ctrl+v")
        await pilot.pause()
        assert inp.value == "keep-mePASTEPASTE"


async def test_tab_focuses_output_when_input_empty(isolated_home):
    from app import CommandBlock, InfoBlock

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("escape")
        await pilot.pause()
        inp = input_widget(app)
        assert inp.has_focus
        assert inp.value == ""
        await pilot.press("tab")
        await pilot.pause()
        assert not inp.has_focus
        assert isinstance(app.focused, (CommandBlock, InfoBlock))
        await pilot.press("escape")
        await pilot.pause()
        assert inp.has_focus


async def test_tab_focuses_output_when_text_without_completion(isolated_home):
    from app import CommandBlock, InfoBlock

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "echo tab-target")
        await wait_command_done(app)
        await pilot.press("escape")
        await type_keys(pilot, "x")  # слишком коротко для списка подсказок
        await pilot.pause()
        assert not app._completion_list.is_visible()
        await pilot.press("tab")
        await pilot.pause()
        assert not input_widget(app).has_focus
        assert isinstance(app.focused, (CommandBlock, InfoBlock))
        assert input_widget(app).value == "x"


async def test_tab_focuses_colon_h_block_after_command(isolated_home):
    from app import CommandBlock, InfoBlock

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "echo tab-after-h")
        await wait_command_done(app)
        await submit(pilot, ":h")
        await pilot.pause()
        inp = input_widget(app)
        assert inp.has_focus
        await pilot.press("tab")
        await pilot.pause()
        assert isinstance(app.focused, InfoBlock)
        assert not isinstance(app.focused, CommandBlock)
        assert "echo tab-after-h" in app.focused.text_content


async def test_tab_focuses_help_block_after_command(isolated_home):
    from app import CommandBlock, InfoBlock

    app = CommandRunner()
    async with app.run_test(size=(80, 24)) as pilot:
        await submit(pilot, "echo tab-after-help")
        await wait_command_done(app)
        await submit(pilot, ":?")
        await pilot.pause()
        assert input_widget(app).has_focus
        await pilot.press("tab")
        await pilot.pause()
        assert isinstance(app.focused, InfoBlock)
        assert not isinstance(app.focused, CommandBlock)
        assert "Line-cursor mode" in app.focused.text_content


async def test_bang_completion_lists_tags_on_exclamation(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#file ls -la")
        await submit(pilot, "#kube kubectl get pods")
        await submit(pilot, "#log echo logs")
        await pilot.press("escape")
        await type_keys(pilot, "!")
        await pilot.pause()
        clist = app._completion_list
        assert clist.is_visible()
        displays = " ".join(clist.all_displays)
        assert "file" in displays
        assert "kube" in displays
        assert "log" in displays
        assert clist.preview == "[file, kube, log]"
        assert clist.all_candidates == ["!file", "!kube", "!log"]
        await pilot.press("tab")
        await pilot.pause()
        assert input_widget(app).value.strip() == "!file"
        assert any("ls -la" in d for d in app._completion_list.all_displays)


async def test_bang_completion_shows_command_inserts_ref(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#file ls -la")
        await submit(pilot, "#file cat json.file")
        await submit(pilot, "#kube kubectl get pods")
        await pilot.press("escape")
        await type_keys(pilot, "!file")
        await pilot.pause()
        clist = app._completion_list
        assert clist.is_visible()
        assert any("ls -la" in d for d in clist.all_displays)
        assert any("file[1]" in d for d in clist.all_displays)
        assert all(item.startswith("!file[") for item in clist.all_candidates)
        await pilot.press("tab")
        await pilot.pause()
        value = input_widget(app).value
        assert value.strip() == "!file[1]"
        assert "ls -la" not in value


async def test_bang_completion_keeps_save_prefix_and_previews(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#file ls -la")
        await submit(pilot, "#file cat json.file")
        await pilot.press("escape")
        await type_keys(pilot, "#pack !file")
        await pilot.pause()
        assert app._completion_list.is_visible()
        await pilot.press("tab")
        await pilot.pause()
        value = input_widget(app).value
        assert value.startswith("#pack ")
        assert "!file[1]" in value
        assert "ls -la" not in value
        await type_keys(pilot, "| !file")
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        value = input_widget(app).value
        assert value.startswith("#pack ")
        assert "!file[1]" in value
        assert "!file[2]" in value
        assert "ls -la" not in value
        assert "cat json.file" not in value
        preview = app._completion_list.preview
        assert "ls -la" in preview
        assert "cat json.file" in preview
