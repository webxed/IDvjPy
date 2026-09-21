"""Конвертация документов (docx, pdf, xlsx, pptx, …) в markdown для `:md`.

`:md` открывает markdown; всё остальное — здесь, двумя путями:

1. **Текст читаем сами.** Файл декодируется и не похож на контейнер (PDF, ZIP
   офисного пакета, OLE2, RTF) — `:md` покажет его как есть, конвертер не нужен.
   Решаем **по содержимому**, а не по имени: `.pdf` часто декодируется без
   ошибки (байты в основном ASCII), а `.md` с другим именем встречается.
2. **Иначе — конвертер.** Порядок: `md_converter` из settings.yml (пусто —
   автопоиск) → ``$IDVJPY_MD_CONVERT`` → ``anydoc`` → ``markitdown`` →
   ``pandoc``. Явно заданный конвертер не подменяется другим: сообщение
   «не найден» полезнее молчаливой смены движка.

``anydoc`` (`pip install firecrawl-anydoc`) — Rust-расширение **без зависимостей**
с колесами под 3.10+ (macOS, manylinux, musllinux, win_amd64): формат определяет
по содержимому, PDF читает локально, вызывается импортом и отпускает GIL. OCR не
включаем: скан-PDF получает ``needs_ocr``, а не отправку в облако — сеть в
проекте только через ``src/net.py`` и только для update/llm/import. Остальные
конвертеры — внешние процессы «файл → markdown в stdout» (``pandoc`` — в GFM).

Результат кэшируется в ``<data>/mdcache/<имя>-<ключ>.md`` (ключ — путь, mtime,
размер и конвертер), поэтому в просмотрщике работают ``#L<n>``, поиск ``/`` и
``y`` — как для обычного ``.md``, а повторное ``:md`` мгновенное. Кэш — обычные
файлы, их можно удалить руками.

Модуль не зависит от Textual.
"""
from __future__ import annotations

import hashlib
import io
import os
import shlex
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path

TEXT_ENCODING = "utf-8"
#: Внешний конвертер может быть и медленным — но не бесконечным.
CONVERT_TIMEOUT = 30.0
#: Каталог кэша внутри data-каталога приложения.
CACHE_DIR_NAME = "mdcache"
#: Переменная окружения — разовая замена `md_converter` из settings.yml.
ENV_CONVERTER = "IDVJPY_MD_CONVERT"
#: Автопоиск конвертера: `anydoc` первым — без зависимостей и с PDF/старыми форматами.
CONVERTERS: tuple[str, ...] = ("anydoc", "markitdown", "pandoc")
#: Подстановка в сообщение «конвертера нет» (текст берётся из локали).
INSTALL_HINT = "pip install firecrawl-anydoc   (or markitdown / pandoc)"
#: Сигнатуры контейнеров — текст с таких байтов не начинается.
_DOC_SIGNATURES = (b"%PDF-", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", b"{\\rtf")
#: Части ZIP-пакета: наличие любой — офисный документ, а не просто архив.
_OFFICE_ZIP_PARTS = frozenset(
    {
        "[Content_Types].xml",
        "word/document.xml",
        "xl/workbook.xml",
        "ppt/presentation.xml",
    }
)
#: mimetype ODF/EPUB-пакетов (у них нет `[Content_Types].xml`).
_ODF_MIMETYPES = (b"application/vnd.oasis.opendocument", b"application/epub+zip")
_SNIFF_BYTES = 65536
#: Ниже этой доли «печатных» байтов файл не в UTF-8 считаем бинарём.
_PRINTABLE_MIN_RATIO = 0.90


@dataclass
class ConvertResult:
    """Итог конвертации: markdown либо причина отказа (`error` — для текста сообщения).

    ``error``: ``no_converter`` · ``converter_missing`` · ``failed`` · ``timeout``
    · ``empty`` · ``needs_ocr``. ``detail`` — текст исключения или stderr
    конвертера; показывать его или нет, решает вызывающий.
    """

    markdown: str = ""
    converter: str = ""
    error: str = ""
    detail: str = ""
    cached: bool = False

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.markdown)


def _printable_ratio(data: bytes) -> float:
    """Доля «печатных» байтов: управляющие (< 0x20, кроме `\\t \\n \\r`) выдают бинарь."""
    sample = data[:_SNIFF_BYTES]
    if not sample:
        return 1.0
    printable = sum(1 for byte in sample if byte >= 0x20 or byte in (0x09, 0x0A, 0x0D))
    return printable / len(sample)


def zip_holds_document(data: bytes) -> bool:
    """ZIP-контейнер офисного документа (docx/xlsx/pptx, odt/ods/odp, epub)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
            if names & _OFFICE_ZIP_PARTS:
                return True
            if "mimetype" in names:
                with archive.open("mimetype") as handle:
                    head = handle.read(64)
                return head.startswith(_ODF_MIMETYPES)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile):
        return False
    return False


def is_plain_text(data: bytes, encoding: str = TEXT_ENCODING) -> bool:
    """Можно ли показать файл как текст, не конвертируя (по содержимому, не по имени)."""
    if not data:
        return True
    if b"\x00" in data[:_SNIFF_BYTES]:
        return False
    if data.startswith(_DOC_SIGNATURES):
        return False
    if data.startswith(b"PK\x03\x04") and zip_holds_document(data):
        return False
    try:
        data.decode(encoding)
    except UnicodeDecodeError:
        # Не UTF-8 (например, cp1251): бинарь выдаёт обилие управляющих байтов.
        return _printable_ratio(data) >= _PRINTABLE_MIN_RATIO
    return True


def decode_text(data: bytes, encoding: str = TEXT_ENCODING) -> str:
    """Текст файла: UTF-8, а при неудаче — с заменами (лучше мусора, чем исключение)."""
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        return data.decode(encoding, errors="replace")


def anydoc_available() -> bool:
    """Есть ли python-пакет `anydoc` (он же `firecrawl-anydoc`).

    Имя импорта занято посторонним проектом на PyPI, поэтому `import anydoc`
    мало — проверяем, что у модуля есть `to_markdown`.
    """
    try:
        import anydoc
    except Exception:
        return False
    return callable(getattr(anydoc, "to_markdown", None))


def _command_exists(name: str) -> bool:
    """Есть ли команда: путь (абсолютный/относительный) или имя в PATH."""
    expanded = os.path.expanduser(name)
    if os.sep in name or (os.altsep and os.altsep in name):
        return os.path.isfile(expanded) and os.access(expanded, os.X_OK)
    return shutil.which(expanded) is not None


def _looks_like_anydoc(converter: str) -> bool:
    """`anydoc` — python-пакет (импорт), а не внешняя команда: см. `anydoc_available`."""
    try:
        parts = shlex.split(converter or "")
    except ValueError:
        return False
    return bool(parts) and os.path.basename(parts[0]).lower().startswith("anydoc")


def converter_available(converter: str) -> bool:
    """Доступен ли конвертер: `anydoc` — по модулю, остальное — командой в PATH.

    Допустима и своя команда с аргументами (``md_converter: "my-tool --md"``):
    файл дописывается последним аргументом, markdown ожидается в stdout.
    """
    command = (converter or "").strip()
    if not command:
        return False
    if _looks_like_anydoc(command):
        return anydoc_available()
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    return bool(parts) and _command_exists(parts[0])


def available_converters() -> tuple[str, ...]:
    """Доступные конвертеры в порядке приоритета."""
    return tuple(name for name in CONVERTERS if converter_available(name))


def find_converter(preferred: str = "") -> str:
    """Имя конвертера: settings.yml → ``$IDVJPY_MD_CONVERT`` → автопоиск.

    Пусто — конвертера нет. Явно заданный возвращается как есть, даже если его
    нет в системе: вызывающий покажет «не найден» вместо тихой смены движка.
    """
    wanted = (preferred or "").strip() or os.environ.get(ENV_CONVERTER, "").strip()
    if wanted:
        return wanted
    found = available_converters()
    return found[0] if found else ""


def cache_key(path: Path, converter: str = "") -> str:
    """Ключ кэша: путь, mtime, размер и конвертер (изменилось что-то — конвертируем заново)."""
    try:
        stat = path.stat()
        stamp = f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}|{converter}"
    except OSError:
        stamp = f"{path.resolve()}|-|-|{converter}"
    return hashlib.sha1(stamp.encode(TEXT_ENCODING)).hexdigest()[:12]


def _cache_file(cache_dir: str | os.PathLike[str] | None, path: Path, key: str) -> Path | None:
    """Путь кэша для файла (`stem` очищен от разделителей пути)."""
    if not cache_dir:
        return None
    stem = "".join(ch for ch in path.stem if ch.isalnum() or ch in "._-")[:40] or "doc"
    return Path(cache_dir) / f"{stem}-{key}.md"


def _read_cache(cache: Path | None) -> str | None:
    """Готовый markdown из кэша; ``None`` — кэша нет (или он пустой/битый)."""
    if cache is None:
        return None
    try:
        text = cache.read_text(encoding=TEXT_ENCODING)
    except (OSError, UnicodeDecodeError):
        return None
    return text or None


def _write_cache(cache: Path | None, markdown: str) -> None:
    """Кэш не критичен: не записался — в следующий раз просто сконвертируем снова."""
    if cache is None:
        return
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(markdown, encoding=TEXT_ENCODING)
    except OSError:
        pass


def _command_for(converter: str, source: Path) -> list[str]:
    """Команда конвертера: файл последним аргументом, markdown — в stdout.

    `pandoc` без флага сам угадывает формат вывода, поэтому просим GFM и не
    переносим строки — так вывод совпадает с остальными конвертерами.
    """
    parts = shlex.split(converter)
    executable = shutil.which(parts[0]) or os.path.expanduser(parts[0])
    if "pandoc" in os.path.basename(parts[0]).lower():
        return [executable, *parts[1:], str(source), "--to", "gfm", "--wrap=none"]
    return [executable, *parts[1:], str(source)]


def _clean(markdown: str | None, converter: str) -> ConvertResult:
    """Пустой результат — тоже ошибка: открывать пустой просмотрщик хуже сообщения."""
    text = markdown or ""
    if not text.strip():
        return ConvertResult(converter=converter, error="empty")
    return ConvertResult(markdown=text, converter=converter)


def _convert_with_anydoc(source: Path, converter: str) -> ConvertResult:
    """`anydoc.to_markdown` — локально, без OCR (`ocr="hosted"` ходил бы в сеть)."""
    try:
        import anydoc
    except Exception as exc:  # битое/неподходящее колесо тоже сюда
        return ConvertResult(converter=converter, error="failed", detail=str(exc))
    try:
        markdown = anydoc.to_markdown(str(source))
    except OSError as exc:
        return ConvertResult(converter=converter, error="failed", detail=str(exc))
    except Exception as exc:
        # Скан-PDF: у anydoc это NeedsOcrError — говорим об этом отдельно.
        error = "needs_ocr" if type(exc).__name__ == "NeedsOcrError" else "failed"
        return ConvertResult(converter=converter, error=error, detail=str(exc) or type(exc).__name__)
    return _clean(markdown, converter)


def _convert_with_command(source: Path, converter: str, timeout: float) -> ConvertResult:
    """Внешний конвертер: файл в аргументах, markdown в stdout."""
    command = _command_for(converter, source)
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding=TEXT_ENCODING,
            errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ConvertResult(converter=converter, error="timeout", detail=f"{timeout:g}")
    except (OSError, ValueError) as exc:
        return ConvertResult(converter=converter, error="failed", detail=str(exc))
    if proc.returncode != 0:
        lines = (proc.stderr or "").strip().splitlines()
        detail = lines[-1] if lines else f"exit code {proc.returncode}"
        return ConvertResult(converter=converter, error="failed", detail=detail)
    return _clean(proc.stdout, converter)


def convert(
    path: str | os.PathLike[str],
    *,
    cache_dir: str | os.PathLike[str] | None = None,
    preferred: str = "",
    timeout: float = CONVERT_TIMEOUT,
) -> ConvertResult:
    """Документ → markdown: конвертер по приоритету + кэш (см. описание модуля).

    Синхронно: вызывать из рабочего потока приложения — файл может быть большим,
    UI ждать не должен.
    """
    source = Path(path)
    converter = find_converter(preferred)
    key = cache_key(source, converter)
    cache = _cache_file(cache_dir, source, key)
    cached = _read_cache(cache)
    if cached is not None:
        # Кэш переживает удаление конвертера — отдаём, что уже сконвертировано.
        return ConvertResult(markdown=cached, converter=converter, cached=True)
    if not converter:
        return ConvertResult(error="no_converter")
    if not converter_available(converter):
        return ConvertResult(converter=converter, error="converter_missing", detail=converter)
    if _looks_like_anydoc(converter):
        result = _convert_with_anydoc(source, converter)
    else:
        result = _convert_with_command(source, converter, timeout)
    if result.ok:
        _write_cache(cache, result.markdown)
    return result
