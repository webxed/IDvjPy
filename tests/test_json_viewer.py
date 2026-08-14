"""JSON Viewer: открытие, поиск, Enter → $JSON, закрытие без падения."""
from textual.widgets import Input, Tree

from app import CommandRunner
from json_viewer import JSONViewer

from tests.conftest import (
    input_widget,
    last_info,
    submit,
    type_keys,
    wait_command_done,
    wait_json_viewer,
)


SAMPLE = {
    "spec": {
        "rules": [{"http": {"paths": [{"path": "/health"}]}}],
        "name": "demo",
    }
}


async def test_open_json_file_expands_tree_and_sets_json_var(isolated_home):
    import json

    (isolated_home / "sample.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":json sample.json")
        viewer = await wait_json_viewer(app)
        assert isinstance(viewer, JSONViewer)

        tree = app.screen.query_one(Tree)
        assert tree.root.is_expanded
        assert tree.root.children
        # Полное раскрытие: хотя бы один вложенный узел тоже expanded.
        nested = [child for child in tree.root.children if child.is_expanded]
        assert nested

        search = app.screen.query_one("#json-search", Input)
        if search.has_focus:
            await pilot.press("tab")
        tree.focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(app.screen, JSONViewer)
        assert "jq path" in last_info(app).text_content
        assert "JSON" in app.local_env
        assert app.local_env["JSON"].startswith(".")


async def test_json_search_filters_nodes(isolated_home):
    import json

    (isolated_home / "sample.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":json sample.json")
        viewer = await wait_json_viewer(app)
        assert isinstance(viewer, JSONViewer)
        before = viewer.total_nodes

        await pilot.press("/")
        await type_keys(pilot, "health")
        await pilot.pause()
        assert viewer.search_query == "health"
        assert viewer.total_nodes < before
        assert viewer.match_nodes

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, JSONViewer)


async def test_json_right_arrow_does_not_crash(isolated_home):
    import json

    (isolated_home / "sample.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":json sample.json")
        await wait_json_viewer(app)
        await pilot.press("right")
        await pilot.pause()
        assert isinstance(app.screen, JSONViewer)
        tree = app.screen.query_one(Tree)
        assert tree.cursor_node is not None


async def test_f3_opens_viewer_from_command_output(isolated_home):
    import json

    (isolated_home / "sample.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "cat sample.json")
        await wait_command_done(app)
        await pilot.press("f3")
        await wait_json_viewer(app)
        await pilot.press("q")
        await pilot.pause()
        assert not isinstance(app.screen, JSONViewer)


async def test_json_var_usable_in_command(isolated_home):
    import json

    (isolated_home / "sample.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, ":json sample.json")
        viewer = await wait_json_viewer(app)
        search = viewer.query_one("#json-search", Input)
        if search.has_focus:
            await pilot.press("tab")
        viewer.query_one(Tree).focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()
        jq_path = app.local_env["JSON"]
        await submit(pilot, "echo $JSON")
        block = await wait_command_done(app)
        assert jq_path in block.raw_stdout
        # Input should be empty after submit, not leftover search text.
        assert input_widget(app).value == ""
        # Search input from viewer must not leak; command input exists.
        assert app.query_one("#command-input", Input)
