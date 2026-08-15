"""Теги: сохранение, запрос, удаление. Команды с '-', '=', '+' не должны ломать парсер."""
import database_v2 as database
from app import CommandRunner

from tests.conftest import info_texts, input_widget, last_info, submit, wait_command_done


async def test_save_and_query_tag(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#logs echo tagged-ok")
        assert "Saved:" in last_info(app).text_content
        assert "logs[1]" in last_info(app).text_content

        await submit(pilot, "?logs")
        joined = "\n".join(info_texts(app))
        assert "tagged-ok" in joined or "echo tagged-ok" in joined


async def test_save_command_with_dash_is_not_delete(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#net ping -c 1 127.0.0.1")
        text = last_info(app).text_content
        assert "Saved:" in text
        assert "marked as deleted" not in text.lower()
        rows = database.get_commands_by_tag(app.db_file, "net")
        assert any("ping -c 1" in row["command"] for row in rows)


async def test_save_command_with_equals(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#cfg echo A=B")
        assert "Saved:" in last_info(app).text_content
        rows = database.get_commands_by_tag(app.db_file, "cfg")
        assert any("A=B" in row["command"] for row in rows)


async def test_delete_tag_id_and_bang_execute(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#demo echo bang-target")
        await submit(pilot, "?demo")
        await submit(pilot, "!demo[1]")
        # !tag[tid] вставляет команду в input, не запускает её сразу.
        assert "echo bang-target" in input_widget(app).value
        await pilot.press("escape")
        await pilot.press("enter")
        await wait_command_done(app)
        block = list(app.query("CommandBlock"))[-1]
        assert "bang-target" in block.raw_stdout

        await submit(pilot, "#demo-1")
        assert "marked as deleted" in last_info(app).text_content


async def test_restore_soft_deleted_command(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#pack echo restore-me")
        await submit(pilot, "#pack-1")
        assert database.get_command_by_tid(app.db_file, "pack", 1) is None
        await submit(pilot, "#pack!1")
        assert "Restored pack[1]" in last_info(app).text_content
        row = database.get_command_by_tid(app.db_file, "pack", 1)
        assert row is not None
        assert "restore-me" in row["command"]


async def test_export_and_import_tag(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "#ship echo cargo-one")
        await submit(pilot, ":export ship ship.json")
        assert "Exported 1" in last_info(app).text_content
        await submit(pilot, "#ship-")
        await submit(pilot, ":import ship.json")
        assert "Imported 1" in last_info(app).text_content
        rows = database.get_commands_by_tag(app.db_file, "ship")
        assert any("cargo-one" in row["command"] for row in rows)
