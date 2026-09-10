"""`:editor` — внешний редактор для файла, $OUT и $BLOCK (фича editor).

Редактор не запускаем: `_run_in_tty` подменяется заглушкой, которая правит
файл так, как это сделал бы человек. TTY и сеть не нужны.
"""
import os
import re
import shlex

import pytest

pytestmark = pytest.mark.slow

import editor_open
from editor_open import (
    EditorError,
    build_editor_command,
    read_text_file,
    resolve_editor,
    write_temp_text,
)


def test_resolve_editor_priority_settings_env_fallback(monkeypatch):
    monkeypatch.setattr(editor_open.shutil, "which", lambda name: f"/usr/bin/{name}")
    # settings.yml важнее окружения; значение может содержать аргументы.
    assert resolve_editor("nano -w", {"VISUAL": "vi", "EDITOR": "ed"}) == ["nano", "-w"]
    # Пустое значение в настройках пропускается: $VISUAL, затем $EDITOR.
    assert resolve_editor("", {"VISUAL": "vi", "EDITOR": "ed"}) == ["vi"]
    assert resolve_editor(None, {"VISUAL": "   ", "EDITOR": "ed"}) == ["ed"]
    # Ничего не задано — системный список (в этом тесте which успешен у всех).
    assert resolve_editor(None, {}) == ["sensible-editor"]


def test_resolve_editor_missing_binary_is_explicit(monkeypatch):
    monkeypatch.setattr(editor_open.shutil, "which", lambda name: None)
    with pytest.raises(EditorError) as excinfo:
        resolve_editor("nvim", {})
    assert "nvim" in str(excinfo.value)
    assert "settings.yml" in str(excinfo.value)
    # Совсем ничего не нашли — тоже явная ошибка, а не молчаливый запуск.
    with pytest.raises(EditorError):
        resolve_editor(None, {})


def test_resolve_editor_bad_quoting_is_explicit(monkeypatch):
    monkeypatch.setattr(editor_open.shutil, "which", lambda name: f"/usr/bin/{name}")
    with pytest.raises(EditorError) as excinfo:
        resolve_editor("vim 'unclosed", {})
    assert "Cannot parse" in str(excinfo.value)


def test_build_editor_command_quotes_path():
    command = build_editor_command(["code", "--wait"], "/tmp/my notes.txt")
    assert shlex.split(command) == ["code", "--wait", "/tmp/my notes.txt"]


def test_write_temp_text_roundtrip():
    path = write_temp_text("hello\nworld\n")
    try:
        assert read_text_file(path) == "hello\nworld\n"
        # Файл во временном каталоге и с узнаваемым префиксом.
        assert os.path.basename(path).startswith(editor_open.TEMP_PREFIX)
    finally:
        os.unlink(path)


def _fake_editor(monkeypatch, transform, code=0):
    """Подменяет `_run_in_tty`: пишет transform(text) в файл (последний argv)."""
    from app import CommandRunner

    def fake_run(self, command):
        path = shlex.split(command)[-1]
        original = read_text_file(path) if os.path.exists(path) else ""
        result = transform(original)
        if result is not None:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(result)
        return code

    monkeypatch.setattr(CommandRunner, "_run_in_tty", fake_run)


async def test_editor_file_saved_in_place(isolated_home, monkeypatch):
    _fake_editor(monkeypatch, lambda text: text + "added\n")
    target = isolated_home / "notes.txt"
    target.write_text("old\n", encoding="utf-8")

    from app import CommandRunner
    from tests.conftest import info_texts, input_widget, submit

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        app.editor = "true"
        await pilot.pause()
        await submit(pilot, f":editor {target}")
        await pilot.pause()

        assert target.read_text(encoding="utf-8") == "old\nadded\n"
        assert f"Editor: saved {target}" in " ".join(info_texts(app))
        # Файл на диске во ввод не дублируется.
        assert input_widget(app).value == ""


async def test_editor_file_created_and_not_created(isolated_home, monkeypatch):
    target = isolated_home / "fresh.txt"

    from app import CommandRunner
    from tests.conftest import info_texts, submit

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        app.editor = "true"
        await pilot.pause()
        # Редактор ничего не создал — явный отчёт, без падения.
        _fake_editor(monkeypatch, lambda text: None)
        await submit(pilot, f":editor {target}")
        await pilot.pause()
        assert f"Editor: {target} was not created" in " ".join(info_texts(app))
        # Редактор создал файл.
        _fake_editor(monkeypatch, lambda text: "created\n")
        await submit(pilot, f":editor {target}")
        await pilot.pause()
        assert target.read_text(encoding="utf-8") == "created\n"
        assert f"Editor: created {target}" in " ".join(info_texts(app))


async def test_editor_out_single_line_goes_to_input(isolated_home, monkeypatch):
    _fake_editor(monkeypatch, lambda text: text.strip().upper() + "\n")

    from app import CommandRunner
    from tests.conftest import info_texts, input_widget, submit, wait_command_done

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        app.editor = "true"
        await submit(pilot, "printf 'pod-7\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":editor $OUT")
        await pilot.pause()

        assert input_widget(app).value == "POD-7"
        assert "→ input" in " ".join(info_texts(app))


async def test_editor_block_multiline_kept_at_path(isolated_home, monkeypatch):
    """$BLOCK из нескольких строк в однострочный ввод не влезает — файл остаётся."""
    _fake_editor(monkeypatch, lambda text: text.replace("l2", "l2-fixed"))

    from app import CommandRunner
    from tests.conftest import info_texts, input_widget, submit, wait_command_done

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        app.editor = "true"
        await submit(pilot, "printf 'l1\\nl2\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":editor $BLOCK")
        await pilot.pause()

        text = " ".join(info_texts(app))
        assert input_widget(app).value == ""
        match = re.search(r"kept at (\S+)", text)
        assert match, text
        kept = match.group(1)
        try:
            assert read_text_file(kept) == "l1\nl2-fixed\n"
        finally:
            os.unlink(kept)


async def test_editor_scratch_buffer_goes_to_input(isolated_home, monkeypatch):
    _fake_editor(monkeypatch, lambda text: "ls -la /tmp\n")

    from app import CommandRunner
    from tests.conftest import input_widget, submit

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        app.editor = "true"
        await pilot.pause()
        await submit(pilot, ":editor")
        await pilot.pause()

        assert input_widget(app).value == "ls -la /tmp"


async def test_editor_unchanged_keeps_input_empty(isolated_home, monkeypatch):
    _fake_editor(monkeypatch, lambda text: None)

    from app import CommandRunner
    from tests.conftest import info_texts, input_widget, submit, wait_command_done

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        app.editor = "true"
        await submit(pilot, "printf 'pod-7\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, ":editor $OUT")
        await pilot.pause()

        assert "Editor: $OUT unchanged." in " ".join(info_texts(app))
        assert input_widget(app).value == ""


async def test_editor_block_without_block_is_explicit(isolated_home):
    from app import CommandRunner
    from tests.conftest import last_info, submit

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        app.editor = "true"
        await pilot.pause()
        await submit(pilot, ":editor $BLOCK")
        assert "need a finished command block" in last_info(app).text_content


async def test_editor_usage_and_directory(isolated_home):
    from app import CommandRunner
    from tests.conftest import last_info, submit

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        app.editor = "true"
        await pilot.pause()
        await submit(pilot, ":editor a b")
        assert "Usage: :editor [<file>|$OUT|$BLOCK]" in last_info(app).text_content
        await submit(pilot, f":editor {isolated_home}")
        assert "is a directory" in last_info(app).text_content


async def test_editor_missing_binary_is_reported(isolated_home):
    from app import CommandRunner
    from tests.conftest import last_info, submit

    app = CommandRunner()
    async with app.run_test(size=(110, 30)) as pilot:
        app.editor = "definitely-not-an-editor-xyz"
        await pilot.pause()
        await submit(pilot, ":editor")
        text = last_info(app).text_content
        assert "not found" in text
        assert "settings.yml" in text


async def test_editor_setting_from_settings_yml(isolated_home):
    """Ключ `editor:` из settings.yml попадает в приложение (дефолт — там же)."""
    from tests.conftest import TEST_SETTINGS

    (isolated_home / "settings.yml").write_text(
        TEST_SETTINGS + "editor: nano -w\n", encoding="utf-8"
    )

    from app import CommandRunner

    app = CommandRunner()
    async with app.run_test(size=(110, 30)):
        assert app.editor == "nano -w"
