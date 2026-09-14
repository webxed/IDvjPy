"""Поиск по markdown (`:rg`) — Obsidian-vault и любой каталог с .md.

Unit: встроенный сканер (python) и ripgrep. App: `:rg` рисует кликабельные
результаты, `:rg <N>` открывает N-й, `:md <path>` открывает файл по пути.
"""
from __future__ import annotations

import asyncio
import time

import pyperclip
import pytest
from textual.widgets import Static

import app as app_module
from app import CommandRunner
from md_search import MdMatch, MdSearchResult, rg_available, search
from md_viewer import HandbookMarkdownScreen
from output_viewer import OutputView, OutputViewerScreen
from tests.conftest import last_info, submit

# --- Встроенный сканер ------------------------------------------------------


def _vault(tmp_path):
    (tmp_path / "a.md").write_text("alpha\nNeedle here\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("needle\n", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("x\nneedle deep\n", encoding="utf-8")
    hidden = tmp_path / ".obsidian"
    hidden.mkdir()
    (hidden / "d.md").write_text("needle hidden\n", encoding="utf-8")
    return tmp_path


def test_python_search_md_only_and_skips_hidden(tmp_path):
    _vault(tmp_path)
    result = search("needle", str(tmp_path), use_rg=False)
    assert {m.path for m in result.matches} == {"a.md", "sub/c.md"}
    assert result.files == 2
    assert result.backend == "python"
    assert not result.truncated


def test_python_search_smart_case(tmp_path):
    (tmp_path / "a.md").write_text("Needle\nneedle\n", encoding="utf-8")
    assert len(search("needle", str(tmp_path), use_rg=False).matches) == 2
    assert len(search("Needle", str(tmp_path), use_rg=False).matches) == 1


def test_python_search_limit_and_truncated(tmp_path):
    (tmp_path / "a.md").write_text("needle\n" * 10, encoding="utf-8")
    result = search("needle", str(tmp_path), limit=3, use_rg=False)
    assert result.truncated
    assert len(result.matches) == 4  # limit + 1 — признак обрезки


def test_search_invalid_regex_raises(tmp_path):
    (tmp_path / "a.md").write_text("x\n", encoding="utf-8")
    with pytest.raises(ValueError):
        search("([", str(tmp_path), use_rg=False)


@pytest.mark.skipif(not rg_available(), reason="ripgrep not installed")
def test_rg_backend_matches_python(tmp_path):
    _vault(tmp_path)
    rg_result = search("needle", str(tmp_path), use_rg=True)
    py_result = search("needle", str(tmp_path), use_rg=False)
    assert {m.path for m in rg_result.matches} == {m.path for m in py_result.matches}
    assert rg_result.backend == "rg"


# --- App: `:rg` и `:md <path>` ---------------------------------------------


def _fake_result(base: str, *paths: str) -> MdSearchResult:
    notes = []
    for i, path in enumerate(paths):
        notes.append(
            MdMatch(path=path, abs_path=f"{base}/{path}", line=i + 1, text=f"needle #{i}")
        )
    return MdSearchResult(matches=notes, files=len(notes), backend="rg", base=base)


async def _wait_for(app: CommandRunner, needle: str, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(needle in block.text_content for block in app.query(app_module.InfoBlock)):
            return True
        await asyncio.sleep(0.05)
    return False


async def test_rg_shows_clickable_results(isolated_home, monkeypatch):
    # Файл в cwd (base по умолчанию = cwd), чтобы `:rg 1` реально открыл его.
    (isolated_home / "note.md").write_text("# note\nneedle line\n", encoding="utf-8")

    def fake(pattern, base, **kwargs):
        return _fake_result(str(base), "note.md")

    monkeypatch.setattr(app_module, "search_markdown", fake)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":rg needle")
        assert await _wait_for(app, "needle #0")
        text = last_info(app).text_content
        assert "open_md_result(0)" in text  # кликабельная ссылка
        assert "matches / 1 files" in text

        # `:rg <N>` открывает N-й результат в md-просмотрщике.
        await submit(pilot, ":rg 1")
        await pilot.pause()
        assert isinstance(app.screen, HandbookMarkdownScreen)


async def test_rg_no_matches_reports(isolated_home, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "search_markdown",
        lambda pattern, base, **kwargs: MdSearchResult(base=base, backend="rg"),
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":rg nothing-here")
        assert await _wait_for(app, "No matches for")


async def test_rg_without_args_shows_usage(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":rg")
        text = last_info(app).text_content
        assert "Usage: :rg" in text
        assert "Base dir:" in text


async def test_rg_out_of_range_reports(isolated_home, monkeypatch):
    monkeypatch.setattr(
        app_module, "search_markdown", lambda pattern, base, **kwargs: _fake_result(base, "a.md")
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":rg needle")
        assert await _wait_for(app, "needle #0")
        await submit(pilot, ":rg 9")
        assert "No result 9" in last_info(app).text_content


async def test_rg_directory_argument(isolated_home, monkeypatch):
    vault = isolated_home / "vault"
    vault.mkdir()
    seen: dict[str, str] = {}

    def fake(pattern, base, **kwargs):
        seen["base"] = base
        return MdSearchResult(base=base, backend="rg")

    monkeypatch.setattr(app_module, "search_markdown", fake)
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, f":rg needle {vault}")
        assert await _wait_for(app, "No matches for")
    assert seen["base"] == str(vault)


async def test_md_opens_file_by_path(isolated_home):
    note = isolated_home / "vault" / "deep" / "note.md"
    note.parent.mkdir(parents=True)
    note.write_text("# deep note\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, f":md {note}")
        await pilot.pause()
        assert isinstance(app.screen, HandbookMarkdownScreen)


async def test_rg_and_md_recorded_in_history(isolated_home, monkeypatch):
    """`:rg` / `:md` можно повторить по ↑ — они пишутся в history_*.txt."""
    note = isolated_home / "note.md"
    note.write_text("# note\nneedle\n", encoding="utf-8")
    monkeypatch.setattr(
        app_module, "search_markdown", lambda pattern, base, **kwargs: _fake_result(base, "note.md")
    )
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":rg needle")
        assert await _wait_for(app, "needle #0")
        await submit(pilot, f":md {note}")
        await pilot.pause()
        history = app._read_file_history()
        assert ":rg needle" in history
        assert any(line.startswith(":md ") for line in history)
        # В подсказках не предлагаются (colon-команды).
        assert ":rg needle" not in app.get_completion_candidates(":rg")


def _tall_markdown() -> str:
    parts: list[str] = []
    for i in range(40):
        parts.append(f"## Section {i}")
        parts.append("")
        parts.append(f"text line for section {i}")
        parts.append("")
    return "\n".join(parts)


async def test_md_opens_at_line(isolated_home):
    note = isolated_home / "long.md"
    note.write_text(_tall_markdown(), encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(80, 20)) as pilot:
        # Секция 20 — строка 83 (1-based).
        await submit(pilot, f":md {note}#L83")
        screen = app.screen
        assert isinstance(screen, HandbookMarkdownScreen)
        assert screen._line == 83
        for _ in range(30):
            if screen._jump_done:
                break
            await pilot.pause()
        assert screen._jump_done
        assert float(screen.query_one("#md-scroll").scroll_y) > 0


async def test_rg_result_opens_at_its_line(isolated_home, monkeypatch):
    note = isolated_home / "doc.md"
    note.write_text(_tall_markdown(), encoding="utf-8")
    monkeypatch.setattr(
        app_module,
        "search_markdown",
        lambda pattern, base, **kwargs: MdSearchResult(
            matches=[MdMatch(path="doc.md", abs_path=str(note), line=83, text="needle")],
            files=1,
            backend="rg",
            base=base,
        ),
    )
    app = CommandRunner()
    async with app.run_test(size=(80, 20)) as pilot:
        await submit(pilot, ":rg needle")
        assert await _wait_for(app, "needle")
        await submit(pilot, ":rg 1")
        screen = app.screen
        assert isinstance(screen, HandbookMarkdownScreen)
        assert screen._line == 83


# --- Большие md: raw-вид в Line API вместо форматированного рендера -------


def _long_markdown(lines: int = 30) -> str:
    return "\n".join(f"line {i} of the note" for i in range(1, lines + 1))


def _set_render_limit(isolated_home, limit: int) -> None:
    settings = isolated_home / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + f"md_render_lines: {limit}\n",
        encoding="utf-8",
    )


async def test_large_md_opens_raw_line_viewer(isolated_home):
    """Выше `md_render_lines` — исходник в Line-API просмотрщике, без тормозов."""
    _set_render_limit(isolated_home, 10)
    note = isolated_home / "big.md"
    note.write_text(_long_markdown(30), encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {note}")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, OutputViewerScreen)
        view = screen.query_one(OutputView)
        assert view.line_count == 30
        assert view._lines[0] == "line 1 of the note"
        assert "raw view" in (screen.sub_title or "")
        assert "md_render_lines=10" in (screen.sub_title or "")


async def test_large_md_raw_viewer_jumps_to_line(isolated_home):
    """`:md <big>#L20` — raw-вид открывается сразу на строке 20."""
    _set_render_limit(isolated_home, 10)
    note = isolated_home / "big.md"
    note.write_text(_long_markdown(30), encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {note}#L20")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, OutputViewerScreen)
        view = screen.query_one(OutputView)
        assert view.match_row == 19  # 0-based
        assert "line 20" in (screen.sub_title or "")


async def test_small_md_still_rendered(isolated_home):
    """Ниже порога поведение прежнее — форматированный просмотрщик."""
    _set_render_limit(isolated_home, 10)
    note = isolated_home / "small.md"
    note.write_text("# Title\n\ntext\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {note}")
        await pilot.pause()
        assert isinstance(app.screen, HandbookMarkdownScreen)


# --- Копирование полного пути (`y` / клик по имени) ------------------------


async def test_md_formatted_view_copies_full_path(isolated_home):
    note = isolated_home / "notes" / "copy-me.md"
    note.parent.mkdir(parents=True)
    note.write_text("# note\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {note}")
        await pilot.pause()
        assert isinstance(app.screen, HandbookMarkdownScreen)
        pyperclip.copy("")
        await pilot.press("y")
        await pilot.pause()
        assert pyperclip.paste() == str(note.resolve())
        # Шапка подтверждает и показывает полный путь.
        shown = getattr(app.screen.query_one("#md-title", Static).visual, "plain", "")
        assert "copied" in shown
        assert str(note.resolve()) in shown


async def test_md_raw_view_copies_full_path(isolated_home):
    _set_render_limit(isolated_home, 10)
    note = isolated_home / "big.md"
    note.write_text(_long_markdown(30), encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {note}")
        await pilot.pause()
        assert isinstance(app.screen, OutputViewerScreen)
        pyperclip.copy("")
        await pilot.press("y")
        await pilot.pause()
        assert pyperclip.paste() == str(note.resolve())
        assert "Path copied" in (app.screen.sub_title or "")
