"""Файловые подсказки: видимость списка, Tab не затирает команду, каталоги с /."""
from app import CommandRunner

from tests.conftest import input_widget, submit, type_keys


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
