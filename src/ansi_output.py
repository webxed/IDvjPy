"""ANSI/ESC в выводе команд: цвета как в терминале, мусор — вырезан.

Приложение отдаёт текст блока прямо в терминал (кадр TUI пишется целиком).
Если в тексте остаются сырые escape-последовательности (`curl wttr.in`,
`ls --color=always`, прогресс-бары `curl`/`docker`/`pip`), реальный терминал
исполняет их **внутри кадра**: цвета текут на соседние клетки, `\\x1b[0m`
сбрасывает стиль приложения, `\\r` уводит курсор в начало строки. Именно поэтому
такой вывод выглядел «сломанным», хотя сама команда отрабатывала.

Правила:

- SGR (`\\x1b[..m` — цвета и атрибуты) переводим в Textual-разметку
  (`to_markup`) — так цвета видны, как в терминале. Выключается ключом
  `ansi_colors: false` (и режимом F6 «Simple output»), тогда цвета вырезаются;
- все остальные последовательности (курсор, стирание, OSC/гиперссылки,
  bracketed paste) вырезаем всегда — они управляют настоящим терминалом, а не
  блоком журнала;
- `\\r`-перерисовку (прогресс-бары) сворачиваем до итогового состояния строки,
  как это видно в терминале.

Плоский текст (`to_plain`) — для копирования, пайпа, `$OUT`/`$BLOCK`, `:log`,
`@key`: escape-кодов в нём нет вообще, поэтому он же уходит в другие команды.
"""
from __future__ import annotations

import re

from rich.text import Text
from textual.content import Content

# Огромный цветной вывод на разметку не разбираем: парсер ANSI не бесплатный
# (~25 ms на 300 строк × 100 символов), а журнал такие блоки всё равно обрезает
# до MAX_DISPLAY_LINES. Цвета тут не стоят задержки кадра.
MAX_MARKUP_CHARS = 200_000

# CSI (в том числе SGR), OSC (заголовок окна, гиперссылка) и одиночные ESC-коды.
RE_ESCAPES = re.compile(
    r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)|[@-Z\\-_])"
)
# SGR — единственное, что оставляем для разбора цвета (`\x1b[0;32;1m`).
RE_SGR = re.compile(r"\x1b\[[0-9;:]*m")
RE_SGR_SPLIT = re.compile(r"(\x1b\[[0-9;:]*m)")
# Стирание строки/экрана от курсора: `\x1b[K`, `\x1b[0J` и т.п.
RE_ERASE = re.compile(r"\x1b\[0?[KJ]")
# Прочие управляющие символы: звонок, backspace, вертикальная табуляция…
RE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def has_escapes(text: str) -> bool:
    """Есть ли в тексте escape-последовательности (быстрая проверка)."""
    return "\x1b" in (text or "")


def escape_brackets(text: str) -> str:
    """`[` → `\\[`: чужой вывод не должен стать разметкой Textual.

    Близнец `app.escape_display_markup`: здесь он нужен, чтобы быстрый путь
    (`to_markup` без ANSI) экранировал скобки так же, как путь через Rich.
    """
    return (text or "").replace("[", "\\[")


def strip_escapes(text: str) -> str:
    """Убрать все escape-последовательности и управляющие символы.

    `\\n` и `\\t` сохраняются — они часть текста, а не управление терминалом.
    """
    if not text:
        return ""
    # Порядок важен: сначала последовательности целиком (в них есть сам ESC),
    # и только потом одиночные управляющие символы — иначе от `\x1b[31m`
    # останется `[31m`.
    if "\x1b" in text:
        text = RE_ESCAPES.sub("", text)
    if RE_CONTROL.search(text):
        text = RE_CONTROL.sub("", text)
    return text


def collapse_carriage_returns(text: str) -> str:
    """`\\r` как в терминале: возврат к началу строки и перезапись.

    Прогресс-бары перерисовывают одну строку десятки раз; в журнале нужен итог,
    а не все промежуточные кадры. Вызывать **до** `strip_escapes`: наличие
    стирания (`\\x1b[K`) меняет трактовку строки.
    """
    if "\r" not in text:
        return text
    return "\n".join(_collapse_line(line) for line in text.split("\n"))


def _collapse_line(line: str) -> str:
    """Одна строка: перезапись с колонки 0, стёртый хвост не дописываем."""
    if "\r" not in line:
        return line
    parts = line.split("\r")
    if RE_ERASE.search(line):
        # `…100%\r\x1b[K50%`: строку стёрли целиком и написали заново, старый
        # хвост не «просвечивает». Иначе: `…100%\r50%` → `50%` (перезапись).
        return parts[-1]
    buffer = parts[0]
    for part in parts[1:]:
        buffer = part + buffer[len(part):] if len(part) < len(buffer) else part
    return buffer


def to_plain(text: str) -> str:
    """Плоский текст вывода: без escape-кодов, `\\r` свёрнут (как в терминале)."""
    if not text:
        return ""
    if "\x1b" not in text and "\r" not in text and not RE_CONTROL.search(text):
        return text
    return strip_escapes(collapse_carriage_returns(text))


def to_markup(text: str) -> str:
    """Вывод команды → Textual-разметка: SGR становятся цветами.

    Быстрый путь — текст без ANSI (обычный случай): только экранирование `[`.
    Остальные последовательности вырезаются и здесь: в кадр TUI они не должны
    попадать никогда.
    """
    if not text:
        return ""
    if "\r" in text:
        text = collapse_carriage_returns(text)
    if "\x1b" not in text or len(text) > MAX_MARKUP_CHARS:
        return escape_brackets(strip_escapes(text))
    prepared = keep_sgr(text)
    if "\x1b" not in prepared:
        return escape_brackets(prepared)
    return rich_to_markup(prepared)


def keep_sgr(text: str) -> str:
    """Оставить SGR (цвета), вырезать всё остальное: курсор, OSC, управление."""
    return "".join(
        part if RE_SGR.fullmatch(part) else strip_escapes(part)
        for part in RE_SGR_SPLIT.split(text)
    )


def rich_to_markup(text: str) -> str:
    """SGR → разметка Textual (Rich разбирает коды сам и экранирует `[`)."""
    try:
        return Content.from_rich_text(Text.from_ansi(text)).markup
    except Exception:
        # Разбор не удался — лучше плоский текст, чем падение рендера блока.
        return escape_brackets(strip_escapes(text))
