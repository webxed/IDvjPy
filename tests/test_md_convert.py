"""Документы → markdown для `:md` (`src/md_convert.py` + маршрут в `app.py`).

Unit: детект «текст или документ» по содержимому, поиск конвертера, кэш,
ошибки конвертера. App: `:md report.pdf` уходит в конвертер и открывает
просмотрщик на исходном пути, `md_converter` из settings уважается, кэш
отдаётся повторно (даже если конвертер пропал), без конвертера — подсказка.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
import time
import zipfile

import pytest

import md_convert
from app import CommandRunner, InfoBlock
from md_viewer import HandbookMarkdownScreen
from tests.conftest import submit

# --- Детект «текст / документ» (по содержимому, не по имени) ----------------

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n"
ODF_MIMETYPE = b"application/vnd.oasis.opendocument.text"


def _zip_with(parts: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_plain_text_accepts_text_and_empty():
    assert md_convert.is_plain_text(b"# Title\n\ntext\n")
    assert md_convert.is_plain_text(b"")  # пустой файл — не документ
    # cp1251 — не UTF-8, но всё равно текст (нет управляющих байтов).
    assert md_convert.is_plain_text("Пример заметки".encode("cp1251"))


def test_plain_text_rejects_containers_and_binary():
    assert not md_convert.is_plain_text(PDF_BYTES), "ASCII-PDF должен уходить конвертеру"
    assert not md_convert.is_plain_text(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"ole2")
    assert not md_convert.is_plain_text(b"{\\rtf1\\ansi hello}")
    assert not md_convert.is_plain_text(b"# Title\n\x00\x01\x02binary")
    assert not md_convert.is_plain_text(_zip_with({"[Content_Types].xml": b"<Types/>"}))
    assert not md_convert.is_plain_text(_zip_with({"mimetype": ODF_MIMETYPE}))


def test_zip_holds_document_ignores_plain_archives():
    assert md_convert.zip_holds_document(_zip_with({"word/document.xml": b"<w/>"}))
    assert not md_convert.zip_holds_document(_zip_with({"notes.txt": b"hello"}))
    assert not md_convert.zip_holds_document(b"not a zip at all")


def test_decode_text_never_raises_on_broken_bytes():
    assert md_convert.decode_text("Привет".encode("cp1251")).count("\ufffd") == 6
    assert md_convert.decode_text(b"plain") == "plain"


# --- Поиск конвертера ------------------------------------------------------


def test_converter_available_by_module_or_command(monkeypatch):
    assert not md_convert.converter_available("")
    assert not md_convert.converter_available("definitely-not-a-converter-xyz")
    assert md_convert.converter_available(sys.executable)  # путь до исполняемого файла
    # `anydoc` — именно python-пакет: доступность = наличие `to_markdown`.
    assert md_convert.converter_available("anydoc") == md_convert.anydoc_available()


def test_find_converter_prefers_settings_then_env(monkeypatch):
    monkeypatch.setenv(md_convert.ENV_CONVERTER, "markitdown")
    assert md_convert.find_converter("pandoc") == "pandoc"  # settings бьёт env
    assert md_convert.find_converter("") == "markitdown"
    # Явный конвертер не подменяется: «не найден» полезнее тихой смены движка.
    monkeypatch.delenv(md_convert.ENV_CONVERTER, raising=False)
    assert md_convert.find_converter("no-such-converter") == "no-such-converter"


def test_find_converter_auto_picks_first_available(monkeypatch):
    monkeypatch.delenv(md_convert.ENV_CONVERTER, raising=False)
    monkeypatch.setattr(md_convert, "available_converters", lambda: ("pandoc", "markitdown"))
    assert md_convert.find_converter("") == "pandoc"
    monkeypatch.setattr(md_convert, "available_converters", lambda: ())
    assert md_convert.find_converter("") == ""


def test_install_hint_names_the_package():
    assert "firecrawl-anydoc" in md_convert.INSTALL_HINT


# --- Конвертация внешней командой и кэш ------------------------------------

CONVERTER_SCRIPT = """\
import os
import pathlib
import sys

runs = os.environ.get("MD_CONVERT_RUNS")
if runs:
    with open(runs, "a", encoding="utf-8") as handle:
        handle.write("run\\n")

source = pathlib.Path(sys.argv[-1])
print("# Converted")
print()
print(f"source: {source.name}")
"""

FAILING_SCRIPT = """\
import sys
sys.stderr.write("boom: unsupported format\\n")
sys.exit(3)
"""

SLOW_SCRIPT = """\
import time
time.sleep(5)
print("late")
"""

EMPTY_SCRIPT = """\
print("   ")
"""


def _write_script(tmp_path, body: str) -> str:
    """Конвертер-заглушка: `md_converter: "<python> <скрипт>"`."""
    script = tmp_path / "fake-converter.py"
    script.write_text(body, encoding="utf-8")
    return f"{sys.executable} {script}"


def _document(tmp_path, name: str = "report.pdf"):
    path = tmp_path / name
    path.write_bytes(PDF_BYTES)
    return path


def test_command_converter_produces_markdown_and_cache(tmp_path, monkeypatch):
    runs = tmp_path / "runs.txt"
    monkeypatch.setenv("MD_CONVERT_RUNS", str(runs))
    converter = _write_script(tmp_path, CONVERTER_SCRIPT)
    source = _document(tmp_path)
    cache_dir = tmp_path / "mdcache"

    first = md_convert.convert(source, cache_dir=cache_dir, preferred=converter)
    assert first.ok and not first.cached
    assert first.converter == converter
    assert "# Converted" in first.markdown and "source: report.pdf" in first.markdown
    assert runs.read_text(encoding="utf-8").count("run") == 1
    assert list(cache_dir.glob("*.md")), "markdown не попал в кэш"

    second = md_convert.convert(source, cache_dir=cache_dir, preferred=converter)
    assert second.cached and second.markdown == first.markdown
    assert runs.read_text(encoding="utf-8").count("run") == 1, "кэш не сработал"


def test_cache_key_follows_mtime_and_size(tmp_path):
    source = _document(tmp_path)
    before = md_convert.cache_key(source, "anydoc")
    assert md_convert.cache_key(source, "pandoc") != before, "смена конвертера — другой кэш"

    source.write_bytes(PDF_BYTES)  # тот же размер, новая метка времени
    stamp = time.time() + 5
    os.utime(source, (stamp, stamp))
    assert md_convert.cache_key(source, "anydoc") != before


def test_convert_without_cache_dir_reconverts(tmp_path, monkeypatch):
    runs = tmp_path / "runs.txt"
    monkeypatch.setenv("MD_CONVERT_RUNS", str(runs))
    converter = _write_script(tmp_path, CONVERTER_SCRIPT)
    source = _document(tmp_path)

    assert md_convert.convert(source, preferred=converter).ok
    assert md_convert.convert(source, preferred=converter).ok
    assert runs.read_text(encoding="utf-8").count("run") == 2


def test_convert_reports_missing_converter(tmp_path):
    result = md_convert.convert(_document(tmp_path), preferred="definitely-not-a-converter-xyz")
    assert result.error == "converter_missing"
    assert result.detail == "definitely-not-a-converter-xyz"
    assert not result.markdown


def test_convert_reports_no_converter(tmp_path, monkeypatch):
    monkeypatch.delenv(md_convert.ENV_CONVERTER, raising=False)
    monkeypatch.setattr(md_convert, "available_converters", lambda: ())
    assert md_convert.convert(_document(tmp_path)).error == "no_converter"


def test_converter_failure_shows_stderr(tmp_path):
    converter = _write_script(tmp_path, FAILING_SCRIPT)
    result = md_convert.convert(_document(tmp_path), preferred=converter)
    assert result.error == "failed"
    assert result.detail == "boom: unsupported format"


def test_converter_timeout_is_bounded(tmp_path):
    converter = _write_script(tmp_path, SLOW_SCRIPT)
    started = time.monotonic()
    result = md_convert.convert(_document(tmp_path), preferred=converter, timeout=0.4)
    assert result.error == "timeout" and result.detail == "0.4"
    assert time.monotonic() - started < 4


def test_empty_converter_output_is_error(tmp_path):
    converter = _write_script(tmp_path, EMPTY_SCRIPT)
    assert md_convert.convert(_document(tmp_path), preferred=converter).error == "empty"


def test_command_for_pandoc_asks_for_gfm(tmp_path):
    source = _document(tmp_path)
    assert md_convert._command_for("pandoc", source)[-3:] == ["--to", "gfm", "--wrap=none"]
    assert md_convert._command_for("markitdown", source)[-1] == str(source)


# --- App: `:md <документ>` -------------------------------------------------


def _set_converter(workdir, converter: str) -> None:
    settings = workdir / "settings.yml"
    settings.write_text(
        settings.read_text(encoding="utf-8") + f'md_converter: "{converter}"\n',
        encoding="utf-8",
    )


async def _wait_screen(app, kind, timeout: float = 8.0):
    """Конвертация идёт в рабочем потоке — ждём, пока экран появится."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if isinstance(app.screen, kind):
            return app.screen
        await asyncio.sleep(0.05)
    raise AssertionError(f"{kind.__name__} did not open: {[b.text_content for b in app.query(InfoBlock)]}")


async def _wait_info(app, needle: str, timeout: float = 8.0) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for block in app.query(InfoBlock):
            if needle in block.text_content:
                return block.text_content
        await asyncio.sleep(0.05)
    raise AssertionError(f"no InfoBlock with {needle!r}: {[b.text_content for b in app.query(InfoBlock)]}")


async def test_md_command_converts_document(isolated_home, monkeypatch):
    monkeypatch.setenv("MD_CONVERT_RUNS", str(isolated_home / "runs.txt"))
    converter = _write_script(isolated_home, CONVERTER_SCRIPT)
    _set_converter(isolated_home, converter)
    document = _document(isolated_home)

    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {document}")
        screen = await _wait_screen(app, HandbookMarkdownScreen)
        # Просмотрщик открыт на исходном документе, а не на файле кэша.
        assert screen._path.name == "report.pdf"
        assert "# Converted" in screen._markdown
        assert (isolated_home / "mdcache").is_dir()


async def test_md_command_serves_cached_conversion(isolated_home, monkeypatch):
    """Кэш проверяется раньше доступности конвертера — пропавший движок не мешает."""
    monkeypatch.setenv("MD_CONVERT_RUNS", str(isolated_home / "runs.txt"))
    converter = _write_script(isolated_home, CONVERTER_SCRIPT)
    _set_converter(isolated_home, converter)
    document = _document(isolated_home)
    cache_dir = isolated_home / "mdcache"
    assert md_convert.convert(document, cache_dir=cache_dir, preferred=converter).ok
    (isolated_home / "fake-converter.py").unlink()  # конвертер больше не доступен

    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {document}")
        screen = await _wait_screen(app, HandbookMarkdownScreen)
        assert "# Converted" in screen._markdown


async def test_md_command_hints_install_without_converter(isolated_home, monkeypatch):
    monkeypatch.delenv(md_convert.ENV_CONVERTER, raising=False)
    monkeypatch.setattr(md_convert, "available_converters", lambda: ())
    document = _document(isolated_home)

    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {document}")
        text = await _wait_info(app, "firecrawl-anydoc")
        assert "md_converter" in text  # подсказка про настройку тоже на месте


async def test_md_command_reports_missing_converter(isolated_home):
    _set_converter(isolated_home, "definitely-not-a-converter-xyz")
    document = _document(isolated_home)

    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {document}")
        text = await _wait_info(app, "definitely-not-a-converter-xyz")
        assert "md_converter" in text


async def test_plain_text_does_not_call_converter(isolated_home, monkeypatch):
    """Текстовый файл открывается как раньше — до конвертера дело не доходит."""

    def _boom(*args, **kwargs):
        raise AssertionError("convert() не должен вызываться для текстового файла")

    monkeypatch.setattr(md_convert, "convert", _boom)
    note = isolated_home / "NOTE.txt"
    note.write_text("# Title\n\ntext\n", encoding="utf-8")

    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {note}")
        await pilot.pause()
        assert isinstance(app.screen, HandbookMarkdownScreen)


# --- Живой `anydoc` (тесты пропускаются, если пакет не установлен) ----------

_DOCX_TYPES = (
    '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument'
    '.wordprocessingml.document.main+xml"/></Types>'
)
_DOCX_RELS = (
    '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
    'officeDocument" Target="word/document.xml"/></Relationships>'
)
_DOCX_BODY = (
    '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
    "<w:body><w:p><w:r><w:t>Hello minimal docx</w:t></w:r></w:p>"
    "<w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p></w:body></w:document>"
)


def _minimal_docx() -> bytes:
    """Настоящий (хотя и куцый) docx: `anydoc` разбирает его без внешних инструментов."""
    return _zip_with(
        {
            "[Content_Types].xml": _DOCX_TYPES.encode(),
            "_rels/.rels": _DOCX_RELS.encode(),
            "word/document.xml": _DOCX_BODY.encode(),
        }
    )


@pytest.mark.skipif(not md_convert.anydoc_available(), reason="firecrawl-anydoc не установлен")
def test_anydoc_converts_docx_live(tmp_path):
    """Настоящий `anydoc`: docx → markdown, повторный вызов — из кэша."""
    source = tmp_path / "minimal.docx"
    source.write_bytes(_minimal_docx())
    assert not md_convert.is_plain_text(source.read_bytes()), "docx должен идти конвертеру"

    result = md_convert.convert(source, cache_dir=tmp_path / "mdcache", preferred="anydoc")
    assert result.ok and result.converter == "anydoc", result.error or result.detail
    assert "Hello minimal docx" in result.markdown
    cached = md_convert.convert(source, cache_dir=tmp_path / "mdcache", preferred="anydoc")
    assert cached.cached and cached.markdown == result.markdown


@pytest.mark.skipif(not md_convert.anydoc_available(), reason="firecrawl-anydoc не установлен")
async def test_md_command_with_anydoc_live(isolated_home):
    """`:md <docx>` в TUI с настоящим anydoc и автопоиском (`md_converter: ""`)."""
    document = isolated_home / "minimal.docx"
    document.write_bytes(_minimal_docx())

    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {document}")
        screen = await _wait_screen(app, HandbookMarkdownScreen)
        assert screen._path.name == "minimal.docx"
        assert "Hello minimal docx" in screen._markdown
