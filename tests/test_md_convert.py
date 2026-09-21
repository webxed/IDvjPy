"""Документы → markdown для `:md` (`src/md_convert.py` + маршрут в `app.py`).

Unit: детект «текст или документ» по содержимому, поиск конвертера, кэш,
ошибки конвертера, локальный OCR скан-PDF (`ocrmypdf`). App: `:md report.pdf`
уходит в конвертер и открывает просмотрщик на исходном пути, `md_converter`
из settings уважается, кэш отдаётся повторно (даже если конвертер пропал),
без конвертера — подсказка.
"""
from __future__ import annotations

import asyncio
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import time
import types
import zipfile
from pathlib import Path

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
    # `md_ocr: off` — иначе установленный в системе ocrmypdf включит распознавание.
    result = md_convert.convert(_document(tmp_path), preferred=converter, ocr="off")
    assert result.error == "empty"


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


# --- Локальный OCR скан-PDF (`ocrmypdf`) -----------------------------------

OCR_SCRIPT = """\
#!/usr/bin/env python3
import os
import pathlib
import sys

runs = os.environ.get("MD_OCR_RUNS")
if runs:
    with open(runs, "a", encoding="utf-8") as handle:
        handle.write("run\\n")

argv = sys.argv[1:]
source, target = pathlib.Path(argv[-2]), pathlib.Path(argv[-1])
target.write_bytes(source.read_bytes() + b"%%OCR%%")
if "--sidecar" in argv:  # реальный ocrmypdf пишет текстовый файл рядом с PDF
    pathlib.Path(argv[argv.index("--sidecar") + 1]).write_text(
        "Revenue grew by 12 percent in Q3.\\n", encoding="utf-8"
    )
"""

SCAN_AWARE_SCRIPT = """\
import os
import pathlib
import sys

data = pathlib.Path(sys.argv[-1]).read_bytes()
runs = os.environ.get("MD_CONVERT_RUNS")
if runs:
    with open(runs, "a", encoding="utf-8") as handle:
        handle.write("run\\n")
if b"%%OCR%%" not in data:  # скан без текстового слоя: как pdfplumber на скане
    sys.exit(0)
print("# Recognized")
print()
print("Revenue grew by 12 percent in Q3.")
"""

#: Фейковый `ocrmypdf` без языкового пакета: так отвечает настоящий, если у
#: tesseract нет данных языка (ошибка сверху, пояснения ниже).
OCR_LANGUAGE_SCRIPT = """\
#!/usr/bin/env python3
import sys

sys.stderr.write(
    "OCR engine does not have language data for the following requested languages:\\n"
    "rus\\n"
    "Please install the appropriate language data for your OCR engine.\\n"
)
sys.exit(2)
"""


def _fake_ocr_tool(tmp_path, monkeypatch, body: str = OCR_SCRIPT) -> Path:
    """Исполняемый `ocrmypdf` в отдельном каталоге + этот каталог первым в PATH."""
    tools = tmp_path / "tools"
    tools.mkdir(exist_ok=True)
    tool = tools / "ocrmypdf"
    tool.write_text(body, encoding="utf-8")
    tool.chmod(0o755)
    original = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", f"{tools}{os.pathsep}{original}")
    return tool


def _install_fake_anydoc(monkeypatch) -> None:
    """`anydoc`: без текстового слоя — `NeedsOcrError`, с ним — markdown."""
    module = types.ModuleType("anydoc")

    class NeedsOcrError(Exception):
        """Как у настоящего anydoc: скан-страницы без OCR."""

    def to_markdown(path):
        if b"%%OCR%%" in Path(path).read_bytes():
            return "# Recognized page\n\nRevenue grew by 12 percent in Q3.\n"
        raise NeedsOcrError("scanned pages")

    # `__dict__`, а не атрибуты: для чекеров `ModuleType` не знает своих полей.
    module.__dict__.update({"to_markdown": to_markdown, "NeedsOcrError": NeedsOcrError})
    monkeypatch.setitem(sys.modules, "anydoc", module)


def test_find_ocr_auto_off_env_and_explicit(monkeypatch):
    monkeypatch.delenv(md_convert.ENV_OCR, raising=False)
    monkeypatch.setattr(md_convert, "ocr_available", lambda name: True)
    assert md_convert.find_ocr("") == "ocrmypdf"
    assert md_convert.find_ocr("off") == ""
    assert md_convert.find_ocr("NONE") == ""
    assert md_convert.find_ocr("0") == ""
    # «Авто» словами — то же, что пусто.
    assert md_convert.find_ocr("auto") == "ocrmypdf"
    assert md_convert.find_ocr("true") == "ocrmypdf"
    # Явная команда не гасится и не подменяется.
    assert md_convert.find_ocr("ocrmypdf -l rus+eng") == "ocrmypdf -l rus+eng"

    monkeypatch.setattr(md_convert, "ocr_available", lambda name: False)
    assert md_convert.find_ocr("") == ""  # автопоиск: движка нет — молча мимо
    assert md_convert.find_ocr("my-ocr") == "my-ocr"  # сказали явно — сообщим

    monkeypatch.setenv(md_convert.ENV_OCR, "off")
    assert md_convert.find_ocr("") == ""
    monkeypatch.setenv(md_convert.ENV_OCR, "ocrmypdf -l deu")
    assert md_convert.find_ocr("") == "ocrmypdf -l deu"


def test_failure_detail_prefers_the_error_line():
    """Из stderr берём причину, а не хвост пояснений (у ocrmypdf он бывает про другое)."""
    traceback = 'Traceback (most recent call last):\n  File "x.py", line 1\nValueError: bad format\n'
    assert md_convert._failure_detail(traceback, "fail") == "ValueError: bad format"
    languages = (
        "OCR engine does not have language data for the following requested languages:\n"
        "rus\nPlease install the appropriate language data.\n"
    )
    assert md_convert._failure_detail(languages, "fail").endswith(": rus")
    assert md_convert._missing_language(languages) == "rus"
    assert md_convert._missing_language("nothing here") == ""
    assert md_convert._failure_detail("", "exit code 2") == "exit code 2"
    assert md_convert._failure_detail("just noise\n", "fail") == "just noise"


def test_md_ocr_setting_survives_yaml_booleans():
    """`md_ocr: off` без кавычек YAML отдаёт булевым `False` — это «выключено»."""
    assert CommandRunner._ocr_setting(False) == "off"
    assert CommandRunner._ocr_setting(True) == ""  # `on` → автопоиск
    assert CommandRunner._ocr_setting(None) == ""
    assert CommandRunner._ocr_setting("") == ""
    assert CommandRunner._ocr_setting("ocrmypdf -l rus") == "ocrmypdf -l rus"


def test_ocr_command_adds_safe_flags(tmp_path):
    source, target = tmp_path / "in.pdf", tmp_path / "out.pdf"
    sidecar = tmp_path / "out.txt"
    command = md_convert._ocr_command("ocrmypdf", source, target, sidecar)
    assert command[-2:] == [str(source), str(target)]
    assert "--skip-text" in command  # без него ocrmypdf откажется от PDF с текстом
    assert "--optimize" in command and "--output-type" in command
    assert command[command.index("--sidecar") + 1] == str(sidecar)

    own = md_convert._ocr_command("ocrmypdf --force-ocr -l rus", source, target, sidecar)
    assert "--force-ocr" in own and "-l" in own and "rus" in own
    assert "--skip-text" not in own  # свой режим не перебиваем
    assert "--sidecar" in own  # но текст забираем всё равно
    assert own[-2:] == [str(source), str(target)]

    custom = md_convert._ocr_command("my-ocr --fast", source, target, sidecar)
    assert custom[-3:] == ["--fast", str(source), str(target)]
    assert "--sidecar" not in custom  # чужая команда может такого флага и не знать


def test_looks_like_pdf_reads_signature(tmp_path):
    assert md_convert.looks_like_pdf(_document(tmp_path))
    assert not md_convert.looks_like_pdf(tmp_path / "missing.pdf")
    note = tmp_path / "note.md"
    note.write_text("# hi\n", encoding="utf-8")
    assert not md_convert.looks_like_pdf(note)


def test_scanned_pdf_is_recognized_locally(tmp_path, monkeypatch):
    """Пустой ответ конвертера → локальный OCR → повторная конвертация, затем кэш."""
    monkeypatch.setenv("MD_OCR_RUNS", str(tmp_path / "ocr.runs"))
    monkeypatch.setenv("MD_CONVERT_RUNS", str(tmp_path / "convert.runs"))
    _fake_ocr_tool(tmp_path, monkeypatch)
    converter = _write_script(tmp_path, SCAN_AWARE_SCRIPT)
    source = _document(tmp_path)
    cache_dir = tmp_path / "mdcache"

    result = md_convert.convert(source, cache_dir=cache_dir, preferred=converter)
    assert result.ok, result.error or result.detail
    assert "Revenue grew by 12 percent" in result.markdown
    assert result.converter.endswith("+ocrmypdf"), result.converter
    assert (tmp_path / "ocr.runs").read_text(encoding="utf-8").count("run") == 1
    # Конвертер звали дважды: до OCR (пусто) и после него.
    assert (tmp_path / "convert.runs").read_text(encoding="utf-8").count("run") == 2

    second = md_convert.convert(source, cache_dir=cache_dir, preferred=converter)
    assert second.cached and second.markdown == result.markdown
    assert second.converter.endswith("+ocrmypdf")
    assert (tmp_path / "ocr.runs").read_text(encoding="utf-8").count("run") == 1

    # `md_ocr: off` — распознавания нет, сообщение остаётся честным.
    monkeypatch.setenv(md_convert.ENV_OCR, "off")
    assert md_convert.convert(source, cache_dir=cache_dir, preferred=converter).error == "empty"


def test_anydoc_needs_ocr_triggers_local_ocr(tmp_path, monkeypatch):
    """`NeedsOcrError` от anydoc — не тупик: распознаём локально и читаем заново."""
    monkeypatch.setenv("MD_OCR_RUNS", str(tmp_path / "ocr.runs"))
    monkeypatch.delenv(md_convert.ENV_CONVERTER, raising=False)
    monkeypatch.delenv(md_convert.ENV_OCR, raising=False)
    _fake_ocr_tool(tmp_path, monkeypatch)
    _install_fake_anydoc(monkeypatch)
    source = _document(tmp_path)

    result = md_convert.convert(source, cache_dir=tmp_path / "mdcache", preferred="anydoc")
    assert result.ok, result.error or result.detail
    assert result.converter == "anydoc+ocrmypdf"
    assert "Recognized page" in result.markdown
    assert (tmp_path / "ocr.runs").read_text(encoding="utf-8").count("run") == 1


def test_scanned_pdf_without_engine_says_ocr_needed(tmp_path, monkeypatch):
    """Движка нет — прежнее поведение: отказ конвертера доходит до пользователя."""
    monkeypatch.delenv(md_convert.ENV_OCR, raising=False)
    monkeypatch.setattr(md_convert, "ocr_available", lambda name: False)
    converter = _write_script(tmp_path, SCAN_AWARE_SCRIPT)
    result = md_convert.convert(_document(tmp_path), preferred=converter)
    assert result.error == "empty"
    assert not result.cached


def test_explicit_ocr_tool_missing_is_reported(tmp_path):
    converter = _write_script(tmp_path, SCAN_AWARE_SCRIPT)
    result = md_convert.convert(
        _document(tmp_path), preferred=converter, ocr="definitely-not-ocr"
    )
    assert result.error == "ocr_missing"
    assert result.detail == "definitely-not-ocr"


def test_missing_language_pack_is_reported(tmp_path, monkeypatch):
    """Нет языкового пакета — отдельная ошибка с кодом языка, а не хвост stderr."""
    _fake_ocr_tool(tmp_path, monkeypatch, OCR_LANGUAGE_SCRIPT)
    converter = _write_script(tmp_path, SCAN_AWARE_SCRIPT)
    result = md_convert.convert(_document(tmp_path), preferred=converter)
    assert result.error == "ocr_language"
    assert result.detail == "rus"


def test_ocr_text_layer_is_used_when_converter_refuses(tmp_path, monkeypatch):
    """`anydoc` не берёт «картиночный» PDF даже с OCR-слоем — отдаём текст от ocrmypdf."""
    monkeypatch.setenv("MD_OCR_RUNS", str(tmp_path / "ocr.runs"))
    _fake_ocr_tool(tmp_path, monkeypatch)
    converter = _write_script(tmp_path, EMPTY_SCRIPT)  # пусто и до OCR, и после него

    result = md_convert.convert(_document(tmp_path), preferred=converter)
    assert result.ok, result.error or result.detail
    assert result.converter == "ocrmypdf"  # структуры нет — текст дал только OCR
    assert "Revenue grew by 12 percent" in result.markdown


def test_ocr_without_text_and_without_sidecar_is_empty(tmp_path, monkeypatch):
    """Ни текстового слоя, ни sidecar — честное «пусто», а не «поставьте ocrmypdf»."""
    monkeypatch.setenv("MD_OCR_RUNS", str(tmp_path / "ocr.runs"))
    _fake_ocr_tool(tmp_path, monkeypatch)
    converter = _write_script(tmp_path, EMPTY_SCRIPT)
    monkeypatch.setattr(md_convert, "_read_sidecar", lambda sidecar: "")

    result = md_convert.convert(_document(tmp_path), preferred=converter)
    assert result.error == "empty"
    assert result.converter.endswith("+ocrmypdf")


# --- Живой OCR (`ocrmypdf` + tesseract): пропускается, если их нет ----------


def _live_ocr_ready() -> bool:
    """Живой OCR: `ocrmypdf`, `tesseract`, Pillow (сделать скан) и `anydoc` (прочитать PDF)."""
    if shutil.which("tesseract") is None:
        return False
    if not md_convert.ocr_available("ocrmypdf") or not md_convert.anydoc_available():
        return False
    return importlib.util.find_spec("PIL") is not None


#: Шрифты с кириллицей для «русского скана» (есть хотя бы один — иначе тест пропускается).
_CYRILLIC_FONTS = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


def _tesseract_languages() -> set[str]:
    """Языковые пакеты tesseract (`tesseract --list-langs`); пусто — не спросили."""
    try:
        done = subprocess.run(
            ["tesseract", "--list-langs"], capture_output=True, text=True, timeout=30
        )
    except (OSError, subprocess.TimeoutExpired):
        return set()
    return set(done.stdout.split())


def _cyrillic_font_path() -> str:
    return next((path for path in _CYRILLIC_FONTS if Path(path).is_file()), "")


def _live_russian_ocr_ready() -> bool:
    """Живой русский OCR: всё из `_live_ocr_ready` плюс пакет `rus` и шрифт с кириллицей."""
    return _live_ocr_ready() and "rus" in _tesseract_languages() and bool(_cyrillic_font_path())


@pytest.mark.skipif(not _live_ocr_ready(), reason="ocrmypdf + tesseract + Pillow не установлены")
def test_scanned_pdf_is_recognized_by_real_ocr(tmp_path):
    """Настоящий скан (картинка без текстового слоя) → `ocrmypdf` → markdown."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1200, 400), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=56)
    except TypeError:  # Pillow < 10.1: только встроенный растровый шрифт
        font = ImageFont.load_default()
    draw.text((60, 80), "OCR pipeline check", fill="black", font=font)
    draw.text((60, 220), "kubectl get pods -A", fill="black", font=font)
    scan = tmp_path / "scan.pdf"
    image.save(scan)

    result = md_convert.convert(scan, cache_dir=tmp_path / "mdcache", preferred="anydoc")
    assert result.ok, result.error or result.detail
    # anydoc читает крупные сканы со слоем; на мелких отказывается — тогда текст берём
    # из sidecar ocrmypdf, поэтому проверяем результат, а не имя пары конвертеров.
    assert "ocrmypdf" in result.converter
    assert "pipeline" in result.markdown.lower()
    cached = md_convert.convert(scan, cache_dir=tmp_path / "mdcache", preferred="anydoc")
    assert cached.cached and cached.markdown == result.markdown


@pytest.mark.skipif(
    not _live_russian_ocr_ready(), reason="нет tesseract-ocr-rus или шрифта с кириллицей"
)
def test_russian_scan_needs_the_language_pack(tmp_path):
    """`-l rus`: без языкового пакета из скана выходит латиница, с ним — русский текст."""
    from PIL import Image, ImageDraw, ImageFont

    lines = (
        "Квартальный отчёт",
        "Выручка выросла на 12 процентов за третий квартал.",
        "Ответственные: команда платформы.",
    )
    image = Image.new("RGB", (1200, 700), "white")
    draw = ImageDraw.Draw(image)
    draw.text((60, 80), lines[0], fill="black", font=ImageFont.truetype(_cyrillic_font_path(), 48))
    draw.text((60, 220), lines[1], fill="black", font=ImageFont.truetype(_cyrillic_font_path(), 30))
    draw.text((60, 300), lines[2], fill="black", font=ImageFont.truetype(_cyrillic_font_path(), 30))
    scan = tmp_path / "otchet.pdf"
    image.save(scan, resolution=150)

    # По умолчанию tesseract распознаёт английским — той же строки не получится.
    english = md_convert.convert(scan, cache_dir=tmp_path / "eng", preferred="anydoc")
    assert english.ok, english.error or english.detail
    assert "Квартальный" not in english.markdown

    russian = md_convert.convert(
        scan, cache_dir=tmp_path / "rus", preferred="anydoc", ocr="ocrmypdf -l rus"
    )
    assert russian.ok, russian.error or russian.detail
    assert "Квартальный" in russian.markdown
    assert "команда платформы" in russian.markdown


async def test_md_command_ocrs_scanned_pdf(isolated_home, monkeypatch):
    """:md <скан-PDF> в TUI: распознавание локально и открытие просмотрщика."""
    monkeypatch.setenv("MD_OCR_RUNS", str(isolated_home / "ocr.runs"))
    monkeypatch.setenv("MD_CONVERT_RUNS", str(isolated_home / "convert.runs"))
    monkeypatch.setenv(md_convert.ENV_CONVERTER, _write_script(isolated_home, SCAN_AWARE_SCRIPT))
    _fake_ocr_tool(isolated_home, monkeypatch)
    document = _document(isolated_home)

    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {document}")
        screen = await _wait_screen(app, HandbookMarkdownScreen)
        assert screen._path.name == "report.pdf"
        assert "Revenue grew by 12 percent" in screen._markdown


async def test_md_command_reports_missing_ocr_tool(isolated_home, monkeypatch):
    monkeypatch.setenv(md_convert.ENV_CONVERTER, _write_script(isolated_home, SCAN_AWARE_SCRIPT))
    monkeypatch.setattr(md_convert, "find_ocr", lambda preferred="": "definitely-not-ocr")
    document = _document(isolated_home)

    app = CommandRunner()
    async with app.run_test(size=(100, 20)) as pilot:
        await submit(pilot, f":md {document}")
        text = await _wait_info(app, "definitely-not-ocr")
        assert "md_ocr" in text
