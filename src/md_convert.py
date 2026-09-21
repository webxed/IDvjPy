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
по содержимому, PDF читает локально, вызывается импортом и отпускает GIL.
Остальные конвертеры — внешние процессы «файл → markdown в stdout»
(``pandoc`` — в GFM).

3. **Скан-PDF — локальный OCR.** Если конвертер текста не нашёл (``needs_ocr``
   или пусто), а файл действительно PDF — накладываем текстовый слой через
   ``ocrmypdf`` и читаем PDF заново уже как обычный. Движок: `md_ocr`
   (settings.yml) → ``$IDVJPY_MD_OCR`` → автопоиск; ``off`` выключает.
   Наружу ничего не уходит: и `anydoc.to_markdown`, и `ocrmypdf` работают
   локально (``ocr="hosted"`` у anydoc не используем — сеть в проекте только
   через ``src/net.py`` и только для update/llm/import). Движка нет — честное
   сообщение «нужен OCR» с подсказкой об установке.

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
import re
import shlex
import shutil
import subprocess
import tempfile
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
#: Локальный OCR скан-PDF: инструмент, его таймаут и безопасные флаги.
OCR_TOOL = "ocrmypdf"
OCR_TIMEOUT = 300.0
#: `--skip-text` — не трогать страницы с текстом (без него ocrmypdf откажется),
#: `--optimize 0` и обычный PDF — без сжатия и PDF/A: нам нужен только текст.
OCR_FLAGS = ("--skip-text", "--optimize", "0", "--output-type", "pdf")
#: Режимы, заданные человеком: тогда свои флаги не добавляем.
_OCR_OWN_FLAGS = ("--skip-text", "--force-ocr", "--redo-ocr", "--mode", "-m")
#: Подстановка в сообщение «нужен OCR» (текст берётся из локали).
OCR_INSTALL_HINT = (
    "apt install ocrmypdf | dnf install ocrmypdf | apk add ocrmypdf | brew install ocrmypdf"
)
#: Переменная окружения — разовая замена `md_ocr` из settings.yml.
ENV_OCR = "IDVJPY_MD_OCR"
#: Значения `md_ocr`, выключающие распознавание (в т.ч. когда движок есть).
_OCR_OFF = frozenset({"off", "none", "no", "false", "0"})
#: Значения, означающие «автопоиск» (в т.ч. YAML-булев `true` в кавычках).
_OCR_ON = frozenset({"auto", "on", "yes", "true", "1"})
#: Отказы конвертера, которые для PDF означают «текстового слоя нет».
_NO_TEXT_ERRORS = frozenset({"needs_ocr", "empty"})
#: По этим словам находим строку с причиной среди stderr: у `ocrmypdf` ошибка
#: сверху, у питоновских конвертеров (traceback) — снизу.
_ERROR_HINT = re.compile(
    r"error|failed|fail:|does not|cannot|can't|unknown|unsupported|not found|отказ|не удалось",
    re.IGNORECASE,
)
_PDF_SIGNATURE = b"%PDF-"
#: Сигнатуры контейнеров — текст с таких байтов не начинается.
_DOC_SIGNATURES = (_PDF_SIGNATURE, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", b"{\\rtf")
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

    ``error``: ``no_converter`` · ``converter_missing`` · ``ocr_missing`` ·
    ``ocr_language`` · ``failed`` · ``timeout`` · ``empty`` · ``needs_ocr``.
    ``detail`` — текст исключения или stderr инструмента; показывать его или
    нет, решает вызывающий.
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


def _tool_name(command: str) -> str:
    """Короткое имя инструмента для сообщений («anydoc», «ocrmypdf», «document.pdf»)."""
    try:
        parts = shlex.split(command or "")
    except ValueError:
        parts = []
    return os.path.basename(parts[0]) if parts else "?"


def looks_like_pdf(path: str | os.PathLike[str]) -> bool:
    """PDF по сигнатуре: локальный OCR имеет смысл только для него."""
    try:
        with Path(path).open("rb") as handle:
            return handle.read(len(_PDF_SIGNATURE)) == _PDF_SIGNATURE
    except OSError:
        return False


def ocr_available(command: str) -> bool:
    """Есть ли OCR-команда в системе (это всегда внешний процесс)."""
    try:
        parts = shlex.split(command or "")
    except ValueError:
        return False
    return bool(parts) and _command_exists(parts[0])


def find_ocr(preferred: str = "") -> str:
    """Команда локального OCR для скан-PDF: settings.yml → ``$IDVJPY_MD_OCR`` → автопоиск.

    Пусто — распознавания нет (движка нет или выключено). ``off`` / ``none`` /
    ``no`` / ``false`` / ``0`` выключают явно (в т.ч. когда `ocrmypdf` установлен),
    ``auto`` / ``on`` / ``true`` равнозначны пустому значению. Заданная команда
    возвращается как есть, даже если её нет: про отсутствующую сообщаем отдельно,
    а не молча оставляем скан без текста.
    """
    wanted = (preferred or "").strip() or os.environ.get(ENV_OCR, "").strip()
    lowered = wanted.lower()
    if not wanted or lowered in _OCR_ON:
        return OCR_TOOL if ocr_available(OCR_TOOL) else ""
    return "" if lowered in _OCR_OFF else wanted


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


def _failure_detail(stderr: str, fallback: str) -> str:
    """Строка с причиной из stderr: у `ocrmypdf` и `pandoc` ошибка сверху.

    Просто брать последнюю строку нельзя: `ocrmypdf` после своей ошибки печатает
    ещё и пояснения (про коды языков и т.п.), и в сообщение попадала подсказка
    про китайский вместо «нет данных языка».
    """
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    if not lines:
        return fallback
    for index, line in enumerate(lines):
        if _ERROR_HINT.search(line):
            # У `ocrmypdf` имя языка пишется отдельной строкой — приклеиваем его.
            following = lines[index + 1] if index + 1 < len(lines) else ""
            if len(following.split()) == 1:
                return f"{line} {following}"
            return line
    return lines[-1]


def _missing_language(stderr: str) -> str:
    """`ocrmypdf`: «no language data …» → код языка, которого нет у tesseract."""
    lines = [line.strip() for line in (stderr or "").splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if "language data" in line.lower() and index + 1 < len(lines):
            return lines[index + 1].split()[0]
    return ""


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
        detail = _failure_detail(proc.stderr, f"exit code {proc.returncode}")
        return ConvertResult(converter=converter, error="failed", detail=detail)
    return _clean(proc.stdout, converter)


def _run_converter(source: Path, converter: str, timeout: float) -> ConvertResult:
    """Один проход конвертера: `anydoc` — импортом, остальные — процессом."""
    if _looks_like_anydoc(converter):
        return _convert_with_anydoc(source, converter)
    return _convert_with_command(source, converter, timeout)


def _ocr_command(
    ocr: str, source: Path, target: Path, sidecar: Path | None = None
) -> list[str]:
    """Команда OCR: вход, затем выход последним аргументом (так ждёт `ocrmypdf`).

    Свои «безопасные» флаги добавляем только `ocrmypdf` и только если человек не
    задал режим сам: без `--skip-text` он отказывается работать с PDF, где часть
    страниц уже с текстом, а `--optimize 0 --output-type pdf` не тратят время
    на сжатие и PDF/A — нам нужен только текстовый слой. `--sidecar` — текстовый
    файл рядом с PDF: если конвертер откажется читать «картиночный» PDF (у
    `anydoc` свой порог), отдаём распознанный текст хотя бы им.
    """
    parts = shlex.split(ocr)
    executable = shutil.which(parts[0]) or os.path.expanduser(parts[0])
    extra = parts[1:]
    if _tool_name(ocr).lower().startswith(OCR_TOOL):
        if not any(flag in extra for flag in _OCR_OWN_FLAGS):
            extra = [*extra, *OCR_FLAGS]
        if sidecar is not None and "--sidecar" not in extra:
            extra = [*extra, "--sidecar", str(sidecar)]
    return [executable, *extra, str(source), str(target)]


def _read_sidecar(sidecar: Path | None) -> str:
    """Текст, который `ocrmypdf` положил рядом с PDF (`--sidecar`); пусто — нет."""
    if sidecar is None:
        return ""
    try:
        return sidecar.read_text(encoding=TEXT_ENCODING).strip()
    except (OSError, UnicodeDecodeError):
        return ""


def _ocr_label(converter: str, ocr: str) -> str:
    """Имя пары для сообщений: «anydoc+ocrmypdf» — видно, что текст распознан."""
    return f"{_tool_name(converter)}+{_tool_name(ocr)}"


def _convert_with_ocr(source: Path, converter: str, ocr: str, timeout: float) -> ConvertResult:
    """Скан-PDF: наложить текстовый слой (`ocrmypdf`) и сконвертировать заново.

    Распознанный PDF живёт во временном каталоге: он нужен только как вход для
    конвертера, в кэш уходит markdown (см. `convert`).
    """
    label = _ocr_label(converter, ocr)
    with tempfile.TemporaryDirectory(prefix="idvjpy-md-ocr-") as workdir:
        target = Path(workdir) / "ocr.pdf"
        sidecar = Path(workdir) / "ocr.txt"
        command = _ocr_command(ocr, source, target, sidecar)
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding=TEXT_ENCODING,
                errors="replace",
                stdin=subprocess.DEVNULL,
                timeout=OCR_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return ConvertResult(converter=label, error="timeout", detail=f"{OCR_TIMEOUT:g}")
        except (OSError, ValueError) as exc:
            return ConvertResult(converter=label, error="failed", detail=str(exc))
        if proc.returncode != 0 or not target.is_file():
            # Нет языкового пакета — самый частый отказ у не-английских сканов.
            if code := _missing_language(proc.stderr):
                return ConvertResult(converter=label, error="ocr_language", detail=code)
            detail = _failure_detail(proc.stderr, f"exit code {proc.returncode}")
            return ConvertResult(converter=label, error="failed", detail=detail)
        result = _run_converter(target, converter, timeout)
        if result.ok:
            result.converter = label
            return result
        text = _read_sidecar(sidecar)
        if text:
            # Конвертер не берёт «картиночный» PDF (у anydoc свой порог по тексту),
            # а распознанный текст уже есть — отдаём его, это лучше отказа.
            return ConvertResult(markdown=text, converter=_tool_name(ocr))
        if result.error in _NO_TEXT_ERRORS:
            # OCR прошёл, а текста всё равно нет — не советуем ставить ocrmypdf снова.
            return ConvertResult(converter=label, error="empty")
        result.converter = label
        return result


def convert(
    path: str | os.PathLike[str],
    *,
    cache_dir: str | os.PathLike[str] | None = None,
    preferred: str = "",
    ocr: str = "",
    timeout: float = CONVERT_TIMEOUT,
) -> ConvertResult:
    """Документ → markdown: конвертер по приоритету, локальный OCR скан-PDF и кэш.

    Синхронно: вызывать из рабочего потока приложения — файл может быть большим,
    а распознавание идёт секундами, UI ждать не должен.
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

    ocr_command = find_ocr(ocr)
    is_pdf = looks_like_pdf(source)
    ocr_cache = None
    if is_pdf and ocr_command:
        ocr_cache = _cache_file(cache_dir, source, cache_key(source, f"{converter}|{ocr_command}"))
        recognized = _read_cache(ocr_cache)
        if recognized is not None:
            # Прошлый раз этот файл пришлось распознавать — OCR не повторяем.
            return ConvertResult(
                markdown=recognized,
                converter=_ocr_label(converter, ocr_command),
                cached=True,
            )

    result = _run_converter(source, converter, timeout)
    if result.ok:
        _write_cache(cache, result.markdown)
        return result
    if result.error not in _NO_TEXT_ERRORS or not is_pdf:
        return result
    if not ocr_command:
        return result  # движка OCR нет — честное «нужен OCR» с подсказкой
    if not ocr_available(ocr_command):
        return ConvertResult(converter=ocr_command, error="ocr_missing", detail=ocr_command)
    result = _convert_with_ocr(source, converter, ocr_command, timeout)
    if result.ok:
        _write_cache(ocr_cache, result.markdown)
    return result
