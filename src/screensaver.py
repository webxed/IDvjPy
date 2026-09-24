"""Norton Commander-style starfield, DevOps-themed — or Matrix digital rain.

Stars fly toward the viewer (classic NC screensaver). Closer particles
become kubectl/git/helm tokens and IDvjPy fragments. Live clock and date
drift with them. Live tags/commands from the library scroll full-width at
the top. Command help types along the bottom left; load 1/5/15 and RAM sit
on the bottom right with the same corner inset (they may overlap in a
narrow terminal). Any key or click dismisses the overlay; that key is not
typed into the prompt.

`screensaver_matrix: true` (settings.yml) заменяет холст на «матричный дождь»
(`MatrixRain`) — падающие столбцы глифов; лента, справка и load/RAM остаются.
На раз холст переключается из TUI: `:screensaver matrix` / `:screensaver stars`.
"""
from __future__ import annotations

import os
import random
import time
from collections.abc import Callable, Collection, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.events import Click, Key, MouseDown, MouseScrollDown, MouseScrollUp
from textual.screen import ModalScreen
from textual.widgets import Static

from i18n import tlist

DUST = (".", "·", "*", "+")
TOKENS = (
    "k8s",
    "git",
    "helm",
    "tf",
    "ci",
    "cd",
    "sre",
    "docker",
    "ansible",
    "prom",
    "nginx",
    "etcd",
    "argo",
    "!tag",
    "!!",
    "$OUT",
    "#ops",
    "| jq",
    ":?",
    "ship",
)
STYLES_FAR = ("dim #334155", "dim #475569")
STYLES_MID = ("#64748b", "#22d3ee", "#a78bfa")
STYLES_NEAR = ("bold #e2e8f0", "bold #5eead4", "bold #c4b5fd", "bold #86efac")
STYLE_CLOCK_TIME = "bold #fde047"
STYLE_CLOCK_DATE = "bold #67e8f9"
STYLE_TICKER = "bold #00ff5f"
STYLE_HELP = "#67e8f9"
STYLE_HELP_CMD = "bold #67e8f9"
STYLE_HOST_LOAD = "bold #fde047"
STYLE_HOST_MEM = "bold #67e8f9"
TICKER_SEP = "    ·    "
TICKER_CPS = 2.5  # characters per second; slow crawl so it stays readable
HELP_TYPE_CPS = 22.0

# --- Матричный дождь (`screensaver_matrix`) ---------------------------------
# Глифы как в «Матрице»: полуширинные катаканы, цифры, знаки.
MATRIX_GLYPHS = (
    "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ"
    "0123456789"
    "ABCDEFZ<>*+-/\\|=%$#@!?"
)
MATRIX_HEAD_STYLE = "bold #d8ffe4"  # голова столбца — самая яркая
MATRIX_TAIL_STYLES = ("#00ff5f", "#00d44f", "#00a83c", "#007c2c", "#00571f", "#003a15")
# Скорость в строках в секунду. Медленно и ровно: за кадр (`TICK_SECONDS`) голова
# сдвигается меньше чем на полстроки — шаг вниз глаза не «дёргает».
MATRIX_MIN_SPEED = 1.8
MATRIX_MAX_SPEED = 6.0
MATRIX_MIN_TRAIL = 4
MATRIX_MAX_TRAIL = 16
MATRIX_FLICKER_PER_SECOND = 2.0  # сколько раз в секунду в хвосте меняется глиф
# Кадр заставки: 20 fps. Все тики принимают `dt`, поэтому на скорости звёзд, ленты,
# справки и load/RAM это не влияет — только на плавность движения.
TICK_SECONDS = 0.05
# Перерисовка холста реже, чем симуляция: дождь идёт 1.8–6 строк/с (за кадр
# меньше строки), звёзды/лента/справка тоже живут по `dt`, так что 20 fps
# симуляции при 10 fps отрисовки не меняют картинку — только вдвое меньше CPU.
PAINT_INTERVAL = 0.1
HELP_PAUSE_SEC = 2.2
HELP_INDENT_RATIO = 0.2  # off the left edge, left of center
HOST_POLL_SEC = 1.0  # /proc reads; not every starfield frame
CLOCK_LABELS = ("time", "date")

# One-line Command help for the bottom typewriter (:? prefixes and :commands).
COMMAND_HELP_LINES = (
    ":?  — full command help",
    ":q  — quit",
    ":w file  — write journal to a file",
    ":h [N]  — last N history lines",
    ":h /text  — search history in completions",
    ":h import [shell]  — append the shell's own history file",
    ":c  — clear journal blocks",
    ":json  — JSON viewer (last block or file)",
    ":md file|path[#L n]  — Markdown; documents (docx/pdf/…) are converted",
    ":rg pat [dir]  — search .md (ripgrep/built-in); click path:line",
    ":cd [path]  — show or change shell cwd (tags DB stays at launch dir)",
    ":fm [path]  — OS file manager (new window)",
    ":term [--tab|--window] [path]  — system terminal (window or tab — term_open)",
    ":env  — re-read .bashrc_term* into this process",
    ":session [NAME]  — show or switch instance",
    ":session new [NAME] [DIR]  — app window in a new terminal",
    ":new [NAME|-] [DIR]  — app window in a new terminal (own session)",
    ":send <session|*> cmd  — forward a command to another session (:send! runs it)",
    ":welcome  — seed catalog",
    ":backup  — snapshot the tags DB",
    ":screensaver  — matrix rain now (default) or stars; idle: screensaver_idle",
    ":r [N]  — block command into the input (N = how far back)",
    ":cmd [N] [show]  — block command with current $VAR/secrets to clipboard",
    ":name label  — label a block for |@label",
    ":log [N]  — full block output: / search, f — matches only (F7)",
    ":kill [all]  — stop running background commands (SIGTERM group)",
    ":watch N cmd  — rerun the command every N seconds in one block",
    ":stats  — runs per tag, top commands, never-run",
    ":mv tag[1] tag2 | :mv tag tag2  — move a command / rename a tag",
    ":scope add|rm|clear  — keep/hide tags in lists and hints (this session)",
    ":export <tag>|* [file]  — one tag JSON / whole library Markdown",
    ":import f.json|url  — insert commands (bare :import = library_url)",
    ":alias <tag>|* [file.sh]  — commands as bash functions",
    ":diff  — unified diff of two block outputs",
    ":o [N] | :o /text  — session output history / search",
    ":llm [provider] msg  — ask an LLM (default provider; $OUT / $BLOCK)",
    ":llm offline msg  — built-in stub (no network, no key)",
    ":llm ask [provider] task  — task + tag library → !tag[tid] refs",
    ":cht query  — cheat.sh reference in the journal",
    ":lang code  — UI language (saved); :relang — re-translate seed comments",
    ":ed [file|$OUT|$BLOCK]  — external editor (TUI paused; editor: in settings.yml)",
    ":kctx [cluster] [N]  — cluster journal: saved vars per cluster (kctx_vars)",
    ":/text · :g  — search journal lines; :n / :N next/prev",
    ":theme [name]  — TUI theme (saved in settings.yml)",
    ":playbook [file]  — dump this session as --demo YAML",
    ":run tag|file.yml  — half-automatic chain; manual steps wait for Enter",
    ":update  — compare VERSION with GitHub main",
    ":i  — Kubernetes Ingress Analyzer",
    "> cmd  — real TTY (htop, vim, ssh); env/$PWD come back",
    "@ cmd  — run without command_timeout (long non-TTY jobs)",
    "& cmd  — separate terminal window or tab; the TUI keeps running",
    "#tag cmd  — save literal template (refs not expanded)",
    "# command  — park a line in history, do not run",
    "#tag- / #tag!  — soft-delete / restore a tag",
    "? / ??  — query tags; ?text = content search across commands",
    "!tag[tid]  — insert a template (does not run)",
    "!!  — assemble refs into the input line",
    "| cmd  — pipe focused block stdout",
    "$VAR=val  — set env in .bashrc_term_<instance>",
    "$VAR=@key  — take value from the focused block line (key column)",
    "$$VAR=val  — SECRET env var (hidden in journal, not sent to :llm)",
    "$OUT / $BLOCK  — last line / full stdout of the source block",
    "Enter  — run the assembled line; ! / !! only insert",
    "Tab  — focus last journal block (from input)",
    "F2 line-cursor · F3 copy · F4 stop · F5 JSON · F6 simple · F7 full output  — journal keys",
)


def command_help_lines() -> tuple[str, ...]:
    """Строки подсказок заставки на текущем языке (`screensaver.help`).

    Каталог — `src/locales/<lang>/screensaver.yml`; встроенный набор выше служит
    запасным, если локалей нет. Совпадение наборов сторожит `tests/test_i18n.py`.
    """
    return tlist("screensaver.help") or COMMAND_HELP_LINES


# Кэш разобранных стилей палитры (см. `_style_object`).
_STYLE_CACHE: dict[str, Style] = {}


def _style_object(spec: str) -> Style:
    """Разобранный `Style` по строке — с кэшем.

    Палитры заставки — константы, а `Style.parse` не кэширует: при поячеечной
    сборке кадра он вызывался на каждую стилизованную ячейку (замер профиля:
    13.8k раз за 3 с).
    """
    cached = _STYLE_CACHE.get(spec)
    if cached is None:
        cached = Style.parse(spec)
        _STYLE_CACHE[spec] = cached
    return cached


def cells_to_text(cells: Sequence[Sequence[tuple[str, str]]]) -> Text:
    """Собрать `Text` из сетки `(глиф, стиль)`, склеивая соседние одинаковые стили.

    Поячеечный `Text.append` на 200×50 — это ~9.6k вызовов на кадр (столько же
    span'ов потом разбирает Textual); куски уменьшают и то, и другое в разы.
    """
    canvas = Text()
    for y, row in enumerate(cells):
        if y:
            canvas.append("\n")
        if not row:
            continue
        start, style = 0, row[0][1]
        for x in range(1, len(row) + 1):
            current = row[x][1] if x < len(row) else None
            if current != style or x == len(row):
                canvas.append(
                    "".join(cell[0] for cell in row[start:x]),
                    style=_style_object(style) if style else None,
                )
                start, style = x, current
    return canvas


def clock_glyph(moment: datetime, label: str) -> str:
    """``time`` → 24h clock with seconds; ``date`` → ISO calendar day."""
    if label == "time":
        return moment.strftime("%H:%M:%S")
    return moment.strftime("%Y-%m-%d")


def flatten_command(text: str) -> str:
    """Collapse a command to a single ticker-friendly line."""
    return " ".join((text or "").split())


@dataclass(frozen=True)
class HostSnapshot:
    load1: float | None = None
    load5: float | None = None
    load15: float | None = None
    mem_used: int | None = None
    mem_total: int | None = None


def format_bytes_short(n: int) -> str:
    n = max(0, int(n))
    gib = 1024 ** 3
    mib = 1024 ** 2
    if n >= gib:
        val = n / gib
        return f"{val:.1f}G" if val < 10 else f"{val:.0f}G"
    if n >= mib:
        return f"{n / mib:.0f}M"
    if n >= 1024:
        return f"{n / 1024:.0f}K"
    return f"{n}B"


def parse_meminfo(text: str) -> tuple[int | None, int | None]:
    """Parse `/proc/meminfo` body → ``(used_bytes, total_bytes)``."""
    kb: dict[str, int] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        key = parts[0].rstrip(":")
        try:
            kb[key] = int(parts[1])
        except ValueError:
            continue
    total_kb = kb.get("MemTotal")
    if not total_kb:
        return None, None
    avail_kb = kb.get("MemAvailable")
    if avail_kb is None:
        avail_kb = kb.get("MemFree", 0) + kb.get("Buffers", 0) + kb.get("Cached", 0)
    return max(0, (total_kb - avail_kb) * 1024), total_kb * 1024


def read_meminfo(path: str = "/proc/meminfo") -> tuple[int | None, int | None]:
    try:
        with open(path, encoding="utf-8") as fh:
            return parse_meminfo(fh.read())
    except OSError:
        return None, None


def read_loadavg() -> tuple[float, float, float] | None:
    try:
        return os.getloadavg()
    except (OSError, AttributeError):
        return None


def read_host_snapshot(*, meminfo_path: str = "/proc/meminfo") -> HostSnapshot:
    """Cheap kernel counters: loadavg + MemAvailable. No subprocess."""
    load = read_loadavg()
    used, total = read_meminfo(meminfo_path)
    return HostSnapshot(
        load1=None if load is None else load[0],
        load5=None if load is None else load[1],
        load15=None if load is None else load[2],
        mem_used=used,
        mem_total=total,
    )


def format_host_text(snap: HostSnapshot) -> Text:
    """Compact ``load avg …  mem …`` for the bottom-right status."""
    if snap.load1 is None or snap.load5 is None or snap.load15 is None:
        load_s = "—"
    else:
        load_s = f"{snap.load1:.2f} {snap.load5:.2f} {snap.load15:.2f}"
    if snap.mem_total:
        pct = int(round(100.0 * (snap.mem_used or 0) / snap.mem_total))
        mem_s = f"{format_bytes_short(snap.mem_used or 0)}/{format_bytes_short(snap.mem_total)} {pct}%"
    else:
        mem_s = "—"
    line = Text()
    line.append("load avg ", style=STYLE_HOST_LOAD)
    line.append(load_s, style=STYLE_HOST_LOAD)
    line.append("  mem ", style=STYLE_HOST_MEM)
    line.append(mem_s, style=STYLE_HOST_MEM)
    return line


def _edge_pad(width: int) -> int:
    """Same corner inset as the command-help typewriter."""
    return min(max(2, int(width * HELP_INDENT_RATIO)), max(0, width - 4))


def _text_cells(text: Text, width: int) -> list[tuple[str, str]]:
    padded = Text()
    padded.append_text(text)
    if padded.cell_len < width:
        padded.append(" " * (width - padded.cell_len))
    clipped = padded[:width]
    plain = clipped.plain
    styles = [""] * len(plain)
    for span in clipped.spans:
        style = str(span.style) if span.style else ""
        for i in range(span.start, min(span.end, len(styles))):
            styles[i] = style
    cells = [(ch, styles[i] if i < len(styles) else "") for i, ch in enumerate(plain)]
    if len(cells) < width:
        cells.extend((" ", "") for _ in range(width - len(cells)))
    return cells[:width]


def _cells_to_text(cells: list[tuple[str, str]]) -> Text:
    line = Text()
    buf: list[str] = []
    prev = None
    for ch, style in cells:
        if style != prev:
            if buf:
                line.append("".join(buf), style=prev or None)
                buf = []
            prev = style
        buf.append(ch)
    if buf:
        line.append("".join(buf), style=prev or None)
    return line


def render_host_line(snap: HostSnapshot, width: int) -> Text:
    """Right-aligned load/mem with the same corner inset as command help."""
    width = max(1, width)
    pad = _edge_pad(width)
    body = format_host_text(snap)
    room = max(1, width - pad)
    if body.cell_len > room:
        body = body[:room]
    left = max(0, width - pad - body.cell_len)
    line = Text(" " * left)
    line.append_text(body)
    if line.cell_len < width:
        line.append(" " * (width - line.cell_len))
    return line[:width]


def overlay_host_on_help(help_line: Text, snap: HostSnapshot, width: int) -> Text:
    """Help on the left, host on the right; a narrow row may let host cover help."""
    width = max(1, width)
    pad = _edge_pad(width)
    cells = _text_cells(help_line, width)
    body = format_host_text(snap)
    room = max(1, width - pad)
    if body.cell_len > room:
        body = body[:room]
    start = max(0, width - pad - body.cell_len)
    for i, cell in enumerate(_text_cells(body, body.cell_len)):
        idx = start + i
        if 0 <= idx < width:
            cells[idx] = cell
    return _cells_to_text(cells)


class HostStats:
    """Sample host load/RAM at ``poll`` seconds, not on every starfield frame."""

    def __init__(
        self,
        *,
        reader: Callable[[], HostSnapshot] | None = None,
        poll: float = HOST_POLL_SEC,
    ) -> None:
        self._reader = reader or read_host_snapshot
        self.poll = poll
        self._age = 0.0
        self.snapshot = self._refresh()

    def _refresh(self) -> HostSnapshot:
        try:
            return self._reader()
        except Exception:
            return HostSnapshot()

    def tick(self, dt: float) -> bool:
        self._age += dt
        if self._age < self.poll:
            return False
        self._age = 0.0
        self.snapshot = self._refresh()
        return True

    def render_line(self, width: int) -> Text:
        return render_host_line(self.snapshot, width)


def ticker_items_from_commands(
    rows: Iterable[tuple[str, int, str]],
) -> tuple[str, ...]:
    """Live (tag, tid, command) rows → `!tag[tid]  cmd` ticker entries."""
    items: list[str] = []
    for tag, tid, command in rows:
        name = (tag or "").strip()
        if not name:
            continue
        body = flatten_command(str(command or ""))
        if body:
            items.append(f"!{name}[{int(tid)}]  {body}")
        else:
            items.append(f"!{name}[{int(tid)}]")
    return tuple(items)


def load_library_reminders(
    db_file: str | None, allowed_tags: Collection[str] | None = None
) -> tuple[str, ...]:
    """Snapshot live commands from SQLite. Hidden handbook tags stay out.

    ``allowed_tags`` — scope сессии (`:scope`): лента заставки — тоже список
    команд, поэтому показывает только видимое. ``None`` — фильтра нет.
    """
    rows: list[tuple[str, int, str]] = []
    if db_file:
        try:
            import database_v2 as database

            hidden = set(database.get_hidden_tags(db_file))
            allowed = set(allowed_tags) if allowed_tags is not None else None
            for row in database.get_all_commands_with_ids(db_file):
                tag = row["tag"]
                if tag in hidden:
                    continue
                if allowed is not None and tag not in allowed:
                    continue
                rows.append((tag, int(row["tid"]), row["command"] or ""))
        except Exception:
            rows = []
    return ticker_items_from_commands(rows)


class LibraryTicker:
    """Infinite marquee of shuffled library commands. Unit-testable."""

    def __init__(
        self,
        items: Sequence[str],
        *,
        seed: int | None = None,
        speed: float = TICKER_CPS,
    ) -> None:
        self.rng = random.Random(seed)
        self.speed = speed
        self.offset = 0.0
        self.items: tuple[str, ...] = tuple(items)
        self.order: list[str] = []
        self._tape = ""
        self._reshuffle()

    def _reshuffle(self) -> None:
        self.order = list(self.items)
        self.rng.shuffle(self.order)
        if not self.order:
            self._tape = ""
            return
        self._tape = TICKER_SEP.join(self.order) + TICKER_SEP

    def tick(self, dt: float) -> None:
        if not self._tape:
            return
        self.offset += self.speed * dt

    def render_line(self, width: int) -> Text:
        width = max(1, width)
        if not self._tape:
            return Text(" " * width)
        tape = self._tape
        while len(tape) < width * 2:
            tape += self._tape
        start = int(self.offset) % len(tape)
        window = (tape + tape)[start : start + width]
        if len(window) < width:
            window = (window + tape)[:width]
        return Text(window, style=STYLE_TICKER)


class HelpTypewriter:
    """Bottom help: type LTR over the previous line, pause, next in shuffle order."""

    def __init__(
        self,
        lines: Sequence[str] | None = None,
        *,
        seed: int | None = None,
        type_cps: float = HELP_TYPE_CPS,
        pause: float = HELP_PAUSE_SEC,
    ) -> None:
        self.rng = random.Random(seed)
        self.lines: tuple[str, ...] = tuple(lines) if lines else command_help_lines()
        self.type_cps = type_cps
        self.pause = pause
        self.phase = "type"
        self.typed = 0.0
        self.pause_left = 0.0
        self.current = ""
        self.previous = ""
        self._deck: list[str] = []
        self._pick()

    def _pick(self) -> None:
        if not self.lines:
            self.current = ""
            self.previous = ""
            self.typed = 0.0
            self.phase = "pause"
            self.pause_left = self.pause
            return
        last = self.current
        if not self._deck:
            self._deck = list(self.lines)
            self.rng.shuffle(self._deck)
        nxt = self._deck.pop()
        if nxt == last and self._deck:
            self._deck.insert(0, nxt)
            nxt = self._deck.pop()
        self.previous = self.current
        self.current = nxt
        self.typed = 0.0
        self.phase = "type"

    def tick(self, dt: float) -> None:
        if not self.current and not self.previous:
            return
        if self.phase == "pause":
            self.pause_left -= dt
            if self.pause_left <= 0:
                self._pick()
            return
        self.typed += max(0.0, self.type_cps) * dt
        limit = max(len(self.current), len(self.previous), 1)
        if self.typed >= limit:
            self.typed = float(limit)
            self.phase = "pause"
            self.pause_left = self.pause

    def visible(self) -> str:
        if self.phase == "pause":
            return self.current
        n = int(self.typed)
        cur, prev = self.current, self.previous
        span = max(len(cur), len(prev))
        n = min(n, span)
        chars: list[str] = []
        for i in range(span):
            if i < n:
                chars.append(cur[i] if i < len(cur) else " ")
            else:
                chars.append(prev[i] if i < len(prev) else " ")
        return "".join(chars)

    def render_line(self, width: int) -> Text:
        width = max(1, width)
        pad = _edge_pad(width)
        inner = max(1, width - pad)
        raw = self.visible()
        if len(raw) < inner:
            raw = raw + " " * (inner - len(raw))
        else:
            raw = raw[:inner]
        sep = "  — "
        line = Text(" " * pad)
        if sep in raw:
            cmd, rest = raw.split(sep, 1)
            line.append(cmd, style=STYLE_HELP_CMD)
            line.append(sep, style="dim #334155")
            line.append(rest, style=STYLE_HELP)
        else:
            line.append(raw, style=STYLE_HELP)
        if line.cell_len < width:
            line.append(" " * (width - line.cell_len))
        return line[:width]


@dataclass
class Star:
    x: float
    y: float
    z: float
    speed: float
    glyph: str
    kind: str  # dust / token / clock
    label: str = ""


class StarField:
    """Pure simulation: tick + render. Safe to unit-test without Textual."""

    def __init__(
        self,
        width: int,
        height: int,
        *,
        seed: int | None = None,
        tokens: Sequence[str] | None = None,
        now: Callable[[], datetime] | None = None,
        stars: bool = True,
    ) -> None:
        self.width = max(8, width)
        self.height = max(4, height)
        self.rng = random.Random(seed)
        self.tokens: tuple[str, ...] = tuple(tokens) if tokens else TOKENS
        self._now = now or datetime.now
        self.stars_enabled = bool(stars)
        self.stars: list[Star] = []
        self.version = 0
        self._seed_stars()

    def resize(self, width: int, height: int) -> None:
        self.width = max(8, width)
        self.height = max(4, height)
        clocks = [star for star in self.stars if star.kind == "clock"]
        others = [star for star in self.stars if star.kind != "clock"]
        n = self._budget()
        if len(others) < n:
            for _ in range(n - len(others)):
                others.append(self._spawn(far=True))
        elif len(others) > n:
            others = others[:n]
        have = {star.label for star in clocks}
        for label in CLOCK_LABELS:
            if label not in have:
                clocks.append(self._spawn_clock(label))
        self.stars = others + clocks

    def tick(self, dt: float = TICK_SECONDS) -> bool:
        """Двинуть звёзды. True — изменилась хотя бы одна видимая ячейка.

        Звёзды летят непрерывно, но проекция округляется до клетки (и до
        ступени палитры), поэтому без изменений кадр не пересобираем впустую.
        """
        changed = False
        for star in self.stars:
            before = self._cell_key(star)
            star.z -= star.speed * dt
            if star.kind == "clock":
                glyph = clock_glyph(self._now(), star.label)
                if glyph != star.glyph:
                    star.glyph = glyph
                    changed = True
            if star.z <= 0.04:
                self._respawn(star)
                changed = True
                continue
            if self._cell_key(star) != before:
                changed = True
        if changed:
            self.version += 1
        return changed

    def _cell_key(self, star: Star) -> tuple[int, int, str]:
        """Ключ видимой клетки: (x, y, стиль) — критерий «кадр стоит перерисовки»."""
        sx, sy = self._project(star)
        return int(sx), int(sy), self._style_for(star, star.z)

    def render_text(self) -> Text:
        width, height = self.width, self.height
        cells: list[list[tuple[str, str]]] = [
            [(" ", "")] * width for _ in range(height)
        ]
        drawn: list[tuple[float, Star]] = []
        for star in self.stars:
            drawn.append((star.z, star))
        drawn.sort(key=lambda item: -item[0])  # far first, near overwrites
        for z, star in drawn:
            sx, sy = self._project(star)
            glyph = star.glyph if z < 0.55 or star.kind != "dust" else self._dust_for(z)
            if star.kind == "dust" and z > 0.55:
                glyph = self._dust_for(z)
            style = self._style_for(star, z)
            self._blit(cells, int(sx), int(sy), glyph, style)
        return cells_to_text(cells)

    def _budget(self) -> int:
        if not self.stars_enabled:
            return 0
        area = self.width * self.height
        return min(90, max(28, area // 28))

    def _seed_stars(self) -> None:
        self.stars = [self._spawn(far=self.rng.random() > 0.35) for _ in range(self._budget())]
        self.stars.extend(self._spawn_clock(label) for label in CLOCK_LABELS)
        self.version += 1

    def _spawn(self, *, far: bool) -> Star:
        roll = self.rng.random()
        tokens = self.tokens or TOKENS
        if roll > 0.62:
            kind, glyph = "token", self.rng.choice(tokens)
        else:
            kind, glyph = "dust", self.rng.choice(DUST)
        z = self.rng.uniform(0.55, 1.0) if far else self.rng.uniform(0.12, 0.95)
        speed = self.rng.uniform(0.06, 0.18)
        return Star(
            x=self.rng.uniform(-0.85, 0.85),
            y=self.rng.uniform(-0.7, 0.7),
            z=z,
            speed=speed,
            glyph=glyph,
            kind=kind,
        )

    def _spawn_clock(self, label: str, *, far: bool = True) -> Star:
        z = self.rng.uniform(0.62, 1.0) if far else self.rng.uniform(0.18, 0.9)
        return Star(
            x=self.rng.uniform(-0.5, 0.5),
            y=self.rng.uniform(-0.4, 0.4),
            z=z,
            speed=self.rng.uniform(0.03, 0.08),
            glyph=clock_glyph(self._now(), label),
            kind="clock",
            label=label,
        )

    def _respawn(self, star: Star) -> None:
        if star.kind == "clock":
            fresh = self._spawn_clock(star.label, far=True)
            star.x, star.y, star.z = fresh.x, fresh.y, fresh.z
            star.speed, star.glyph = fresh.speed, fresh.glyph
            return
        fresh = self._spawn(far=True)
        star.x, star.y, star.z = fresh.x, fresh.y, fresh.z
        star.speed, star.glyph, star.kind = fresh.speed, fresh.glyph, fresh.kind

    def _project(self, star: Star) -> tuple[float, float]:
        z = max(star.z, 0.04)
        cx = (self.width - 1) / 2.0
        cy = (self.height - 1) / 2.0
        scale = min(self.width, self.height) * 0.42
        return cx + star.x / z * scale, cy + star.y / z * scale

    def _dust_for(self, z: float) -> str:
        if z > 0.75:
            return "."
        if z > 0.45:
            return "·"
        return "*"

    def _style_for(self, star: Star, z: float) -> str:
        if star.kind == "clock":
            return STYLE_CLOCK_TIME if star.label == "time" else STYLE_CLOCK_DATE
        if z > 0.7:
            return STYLES_FAR[0]
        if z > 0.38:
            return STYLES_MID[hash(star.glyph) % len(STYLES_MID)]
        return STYLES_NEAR[hash(star.glyph) % len(STYLES_NEAR)]

    def _blit(
        self,
        cells: list[list[tuple[str, str]]],
        x: int,
        y: int,
        glyph: str,
        style: str,
    ) -> None:
        if y < 0 or y >= len(cells):
            return
        row = cells[y]
        width = len(row)
        for i, ch in enumerate(glyph):
            px = x + i
            if 0 <= px < width:
                row[px] = (ch, style)


@dataclass
class RainColumn:
    """Столбец дождя: голова (строка, float), скорость, длина хвоста, глифы строк."""

    y: float
    speed: float
    length: int
    glyphs: list[str]


class MatrixRain:
    """Digital rain в стиле «Матрицы» — падающие вниз столбцы глифов.

    Тот же интерфейс, что у `StarField` (`tick` / `resize` / `render_text`),
    чтобы `DevopsScreensaver` рисовал на холсте либо звёздное поле, либо дождь.
    Голова столбца — самым ярким стилем, хвост затухает (`MATRIX_TAIL_STYLES`).
    Чистая симуляция: без Textual, тестируется без TUI.
    """

    def __init__(
        self,
        width: int,
        height: int,
        *,
        seed: int | None = None,
        glyphs: str | None = None,
    ) -> None:
        self.width = max(8, width)
        self.height = max(4, height)
        self.rng = random.Random(seed)
        self.glyphs = glyphs or MATRIX_GLYPHS
        self.columns: list[RainColumn] = []
        self.version = 0
        self._seed_columns()

    def resize(self, width: int, height: int) -> None:
        """Пересобрать столбцы под новый размер (головы снова вразнобой)."""
        self.width = max(8, width)
        self.height = max(4, height)
        self._seed_columns()

    def tick(self, dt: float = TICK_SECONDS) -> bool:
        """Сдвинуть дождь. Возвращает True, если картинка изменилась.

        Счётчик `version` растёт только на видимых изменениях: за тик голова
        сдвигается меньше чем на строку, поэтому перерисовывать такой кадр
        бессмысленно (`DevopsScreensaver._paint` это учитывает).
        """
        changed = False
        for column in self.columns:
            before = int(column.y)
            column.y += column.speed * dt
            if int(column.y) != before:
                changed = True
            if self.rng.random() < MATRIX_FLICKER_PER_SECOND * dt:
                row = self._visible_row(column)
                if row is not None:
                    column.glyphs[row] = self._glyph()
                    changed = True
            if column.y - column.length > self.height:
                self._reset(column)
                changed = True
        if changed:
            self.version += 1
        return changed

    def _visible_row(self, column: RainColumn) -> int | None:
        """Случайная строка хвоста, реально видимая на экране (иначе мерцать нечему)."""
        head = int(column.y)
        top = max(0, head - column.length + 1)
        bottom = min(self.height - 1, head)
        if top > bottom:
            return None
        return self.rng.randint(top, bottom)

    def render_text(self) -> Text:
        cells: list[list[tuple[str, str]]] = [
            [(" ", "")] * self.width for _ in range(self.height)
        ]
        for x, column in enumerate(self.columns):
            head = int(column.y)
            for i in range(column.length):
                row = head - i
                if not 0 <= row < self.height:
                    continue
                cells[row][x] = (column.glyphs[row], self._style_for(i))
        return cells_to_text(cells)


    def _seed_columns(self) -> None:
        self.columns = [self._new_column(stagger=True) for _ in range(self.width)]
        self.version += 1

    def _new_column(self, *, stagger: bool) -> RainColumn:
        length = self.rng.randint(MATRIX_MIN_TRAIL, MATRIX_MAX_TRAIL)
        # Вразнобой: при старте головы разбросаны над экраном, после сброса —
        # столбец начинается целиком за верхней границей (без «вспышки» в кадре).
        start = self.rng.uniform(-float(self.height), 0.0) if stagger else -float(length)
        return RainColumn(
            y=start,
            speed=self.rng.uniform(MATRIX_MIN_SPEED, MATRIX_MAX_SPEED),
            length=length,
            glyphs=[self._glyph() for _ in range(self.height)],
        )

    def _reset(self, column: RainColumn) -> None:
        fresh = self._new_column(stagger=False)
        column.y = fresh.y
        column.speed = fresh.speed
        column.length = fresh.length
        column.glyphs = fresh.glyphs

    def _glyph(self) -> str:
        return self.rng.choice(self.glyphs)

    def _style_for(self, index: int) -> str:
        if index == 0:
            return MATRIX_HEAD_STYLE
        return MATRIX_TAIL_STYLES[min(index - 1, len(MATRIX_TAIL_STYLES) - 1)]


class DevopsScreensaver(ModalScreen[None]):
    """Full-screen starfield. Any key / click returns to the TUI."""

    _modal = True
    CSS = """
    DevopsScreensaver {
        layout: vertical;
        width: 100%;
        height: 100%;
        background: #000000;
        overflow: hidden;
    }
    DevopsScreensaver #ss-ticker {
        dock: top;
        height: 1;
        width: 100%;
        background: #000000;
        color: #00ff5f;
        overflow: hidden;
    }
    DevopsScreensaver #ss-ticker.-empty {
        height: 0;
        display: none;
    }
    DevopsScreensaver #ss-canvas {
        width: 100%;
        height: 1fr;
        background: #000000;
        color: #cbd5e1;
        overflow: hidden;
    }
    DevopsScreensaver #ss-help {
        dock: bottom;
        height: 1;
        width: 100%;
        background: #000000;
        color: #67e8f9;
        overflow: hidden;
    }
    """

    def __init__(
        self,
        *,
        seed: int | None = None,
        tokens: Sequence[str] | None = None,
        ticker_items: Sequence[str] | None = None,
        help_lines: Sequence[str] | None = None,
        host_reader: Callable[[], HostSnapshot] | None = None,
        stars: bool | None = None,
        matrix: bool | None = None,
        allowed_tags: Collection[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._seed = seed
        self._tokens = tokens
        self._ticker_items = ticker_items
        self._help_lines = help_lines
        self._stars = stars
        self._matrix = matrix
        self._allowed_tags = allowed_tags
        self._field: StarField | MatrixRain = StarField(
            80, 24, seed=seed, tokens=tokens, stars=stars is not False
        )
        self._ticker = LibraryTicker((), seed=seed)
        self._help = HelpTypewriter(help_lines, seed=seed)
        self._host = HostStats(reader=host_reader)
        self._timer = None
        self._last_paint_at = 0.0
        self._painted_version = -1

    def compose(self) -> ComposeResult:
        yield Static(id="ss-ticker", classes="-empty")
        yield Static(id="ss-canvas")
        yield Static(id="ss-help")

    def on_mount(self) -> None:
        if self._ticker_items is None:
            items = load_library_reminders(
                getattr(self.app, "db_file", None), self._allowed_tags
            )
        else:
            items = tuple(self._ticker_items)
        self._ticker = LibraryTicker(items, seed=self._seed)
        self._help = HelpTypewriter(self._help_lines, seed=self._seed)
        if self._stars is None:
            self._stars = bool(getattr(self.app, "screensaver_stars", True))
        if self._matrix is None:
            self._matrix = bool(getattr(self.app, "screensaver_matrix", True))
        self._field = self._make_field(
            max(8, self.size.width or 80),
            max(4, (self.size.height or 24) - (1 if items else 0)),
        )
        canvas = self.query_one("#ss-canvas", Static)
        canvas.can_focus = True
        canvas.focus()
        self._sync_size()
        self._paint()
        self._timer = self.set_interval(TICK_SECONDS, self._tick)

    def on_unmount(self) -> None:
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None

    def on_resize(self) -> None:
        self._sync_size()
        self._paint(force=True)  # новый размер — рисуем сразу, не ждём троттлинг

    def _make_field(self, width: int, height: int) -> StarField | MatrixRain:
        """Холст заставки: матричный дождь или звёздное поле.

        `matrix` — из settings.yml (`screensaver_matrix`) или явного аргумента
        (`:screensaver matrix` / `:screensaver stars`).
        """
        if self._matrix:
            return MatrixRain(width, height, seed=self._seed)
        return StarField(
            width,
            height,
            seed=self._seed,
            tokens=self._tokens,
            stars=self._stars is not False,
        )

    def _sync_size(self) -> None:
        try:
            canvas = self.query_one("#ss-canvas", Static)
            width = max(8, canvas.size.width or self.size.width or 80)
            height = max(4, canvas.size.height or self.size.height or 24)
        except Exception:
            width = max(8, self.size.width or 80)
            height = max(4, self.size.height or 24)
        self._field.resize(width, height)
        self._painted_version = -1  # размер изменился — холст перерисовать сразу

    def _tick(self) -> None:
        # Симуляция идёт на TICK_SECONDS (20 fps), а отрисовка — реже
        # (PAINT_INTERVAL): холст — самый дорогой виджет, а картинка от
        # прореженных кадров не меняется (дождь сдвигается меньше строки).
        self._field.tick(TICK_SECONDS)
        self._ticker.tick(TICK_SECONDS)
        self._help.tick(TICK_SECONDS)
        self._host.tick(TICK_SECONDS)
        self._paint()

    def _paint(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_paint_at < PAINT_INTERVAL:
            return
        self._last_paint_at = now
        # Холст пересобираем, только если поле реально изменилось: за тик
        # (50 мс) дождь сдвигается меньше чем на строку, а сборка кадра на
        # 200×50 — самая дорогая часть заставки.
        version = getattr(self._field, "version", None)
        if force or version != self._painted_version:
            try:
                self.query_one("#ss-canvas", Static).update(self._field.render_text())
                self._painted_version = version
            except Exception:
                pass
        try:
            bar = self.query_one("#ss-ticker", Static)
            if self._ticker.items:
                bar.remove_class("-empty")
                width = max(8, bar.size.width or self.size.width or 80)
                bar.update(self._ticker.render_line(width))
            else:
                bar.add_class("-empty")
                bar.update("")
        except Exception:
            pass
        try:
            help_bar = self.query_one("#ss-help", Static)
            width = max(8, help_bar.size.width or self.size.width or 80)
            help_bar.update(
                overlay_host_on_help(
                    self._help.render_line(width),
                    self._host.snapshot,
                    width,
                )
            )
        except Exception:
            pass

    def _wake(self) -> None:
        if self.app.screen is self:
            self.app.pop_screen()
        bump = getattr(self.app, "_bump_screensaver_idle", None)
        if bump:
            bump()

    def on_key(self, event: Key) -> None:
        event.stop()
        event.prevent_default()
        self._wake()

    def on_mouse_down(self, event: MouseDown) -> None:
        event.stop()
        self._wake()

    def on_click(self, event: Click) -> None:
        event.stop()
        self._wake()

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        event.stop()
        event.prevent_default()

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        event.stop()
        event.prevent_default()
