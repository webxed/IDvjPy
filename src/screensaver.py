"""Norton Commander-style starfield, DevOps-themed.

Stars fly toward the viewer (classic NC screensaver). Closer particles
become kubectl/git/helm tokens and IDvjPy fragments. Live tags/commands
from the library scroll as a bright-green ticker at the top. Any key or
click dismisses the overlay; that key is not typed into the prompt.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from rich.text import Text
from textual.app import ComposeResult
from textual.events import Click, Key, MouseDown, MouseScrollDown, MouseScrollUp
from textual.screen import ModalScreen
from textual.widgets import Static

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
COMETS = (
    "lint → test → ship",
    "plan → apply",
    "build → push → deploy",
    "observe → alert → fix",
    "define → join → run",
)
STYLES_FAR = ("dim #334155", "dim #475569")
STYLES_MID = ("#64748b", "#22d3ee", "#a78bfa")
STYLES_NEAR = ("bold #e2e8f0", "bold #5eead4", "bold #c4b5fd", "bold #86efac")
STYLE_COMET = "bold #fbbf24"
STYLE_TICKER = "bold #00ff5f"
HINT = "any key"
TICKER_SEP = "    ·    "
TICKER_CPS = 2.5  # characters per second; slow crawl so it stays readable


def flatten_command(text: str) -> str:
    """Collapse a command to a single ticker-friendly line."""
    return " ".join((text or "").split())


def ticker_items_from_commands(
    rows: Iterable[Tuple[str, int, str]],
) -> Tuple[str, ...]:
    """Live (tag, tid, command) rows → `!tag[tid]  cmd` ticker entries."""
    items: List[str] = []
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


def load_library_reminders(db_file: str | None) -> Tuple[str, ...]:
    """Snapshot live commands from SQLite. Hidden handbook tags stay out."""
    rows: List[Tuple[str, int, str]] = []
    if db_file:
        try:
            import database_v2 as database

            hidden = set(database.get_hidden_tags(db_file))
            for row in database.get_all_commands_with_ids(db_file):
                tag = row["tag"]
                if tag in hidden:
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
        self.items: Tuple[str, ...] = tuple(items)
        self.order: List[str] = []
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


@dataclass
class Star:
    x: float
    y: float
    z: float
    speed: float
    glyph: str
    kind: str  # dust / token / comet


class StarField:
    """Pure simulation: tick + render. Safe to unit-test without Textual."""

    def __init__(
        self,
        width: int,
        height: int,
        *,
        seed: int | None = None,
        tokens: Sequence[str] | None = None,
        comets: Sequence[str] | None = None,
    ) -> None:
        self.width = max(8, width)
        self.height = max(4, height)
        self.rng = random.Random(seed)
        self.tokens: Tuple[str, ...] = tuple(tokens) if tokens else TOKENS
        self.comets: Tuple[str, ...] = tuple(comets) if comets else COMETS
        self.stars: List[Star] = []
        self._seed_stars()

    def resize(self, width: int, height: int) -> None:
        self.width = max(8, width)
        self.height = max(4, height)
        n = self._budget()
        if len(self.stars) < n:
            for _ in range(n - len(self.stars)):
                self.stars.append(self._spawn(far=True))
        elif len(self.stars) > n:
            self.stars = self.stars[:n]

    def tick(self, dt: float = 0.08) -> None:
        for star in self.stars:
            star.z -= star.speed * dt
            if star.z <= 0.04:
                self._respawn(star)

    def render_text(self) -> Text:
        width, height = self.width, self.height
        hint_row = height - 1
        cells: List[List[Tuple[str, str]]] = [
            [(" ", "")] * width for _ in range(height)
        ]
        drawn: List[Tuple[float, Star]] = []
        for star in self.stars:
            drawn.append((star.z, star))
        drawn.sort(key=lambda item: -item[0])  # far first, near overwrites
        for z, star in drawn:
            sx, sy = self._project(star)
            glyph = star.glyph if z < 0.55 or star.kind != "dust" else self._dust_for(z)
            if star.kind == "dust" and z > 0.55:
                glyph = self._dust_for(z)
            style = self._style_for(star, z)
            self._blit(cells, int(sx), int(sy), glyph, style, hint_row)
        canvas = Text()
        for y, row in enumerate(cells):
            if y:
                canvas.append("\n")
            if y == hint_row:
                line = self._hint_line(width)
                canvas.append_text(line)
                continue
            for ch, style in row:
                if style:
                    canvas.append(ch, style=style)
                else:
                    canvas.append(ch)
        return canvas

    def _budget(self) -> int:
        area = self.width * self.height
        return min(90, max(28, area // 28))

    def _seed_stars(self) -> None:
        self.stars = [self._spawn(far=self.rng.random() > 0.35) for _ in range(self._budget())]

    def _spawn(self, *, far: bool) -> Star:
        roll = self.rng.random()
        tokens = self.tokens or TOKENS
        comets = self.comets or COMETS
        if roll > 0.94:
            kind, glyph = "comet", self.rng.choice(comets)
        elif roll > 0.62:
            kind, glyph = "token", self.rng.choice(tokens)
        else:
            kind, glyph = "dust", self.rng.choice(DUST)
        z = self.rng.uniform(0.55, 1.0) if far else self.rng.uniform(0.12, 0.95)
        speed = self.rng.uniform(0.18, 0.55)
        if kind == "comet":
            speed *= 0.7
        return Star(
            x=self.rng.uniform(-0.85, 0.85),
            y=self.rng.uniform(-0.7, 0.7),
            z=z,
            speed=speed,
            glyph=glyph,
            kind=kind,
        )

    def _respawn(self, star: Star) -> None:
        fresh = self._spawn(far=True)
        star.x, star.y, star.z = fresh.x, fresh.y, fresh.z
        star.speed, star.glyph, star.kind = fresh.speed, fresh.glyph, fresh.kind

    def _project(self, star: Star) -> Tuple[float, float]:
        z = max(star.z, 0.04)
        cx = (self.width - 1) / 2.0
        cy = (self.height - 2) / 2.0
        scale = min(self.width, self.height) * 0.42
        return cx + star.x / z * scale, cy + star.y / z * scale

    def _dust_for(self, z: float) -> str:
        if z > 0.75:
            return "."
        if z > 0.45:
            return "·"
        return "*"

    def _style_for(self, star: Star, z: float) -> str:
        if star.kind == "comet":
            return STYLE_COMET
        if z > 0.7:
            return STYLES_FAR[0]
        if z > 0.38:
            return STYLES_MID[hash(star.glyph) % len(STYLES_MID)]
        return STYLES_NEAR[hash(star.glyph) % len(STYLES_NEAR)]

    def _blit(
        self,
        cells: List[List[Tuple[str, str]]],
        x: int,
        y: int,
        glyph: str,
        style: str,
        hint_row: int,
    ) -> None:
        if y < 0 or y >= hint_row or y >= len(cells):
            return
        row = cells[y]
        width = len(row)
        for i, ch in enumerate(glyph):
            px = x + i
            if 0 <= px < width:
                row[px] = (ch, style)

    def _hint_line(self, width: int) -> Text:
        pad = max(0, (width - len(HINT)) // 2)
        line = Text(" " * pad)
        line.append(HINT, style="dim #334155")
        if line.cell_len < width:
            line.append(" " * (width - line.cell_len))
        return line[:width]


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
    """

    def __init__(
        self,
        *,
        seed: int | None = None,
        tokens: Sequence[str] | None = None,
        comets: Sequence[str] | None = None,
        ticker_items: Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._seed = seed
        self._tokens = tokens
        self._comets = comets
        self._ticker_items = ticker_items
        self._field = StarField(80, 24, seed=seed, tokens=tokens, comets=comets)
        self._ticker = LibraryTicker((), seed=seed)
        self._timer = None

    def compose(self) -> ComposeResult:
        yield Static(id="ss-ticker", classes="-empty")
        yield Static(id="ss-canvas")

    def on_mount(self) -> None:
        if self._ticker_items is None:
            items = load_library_reminders(getattr(self.app, "db_file", None))
        else:
            items = tuple(self._ticker_items)
        self._ticker = LibraryTicker(items, seed=self._seed)
        self._field = StarField(
            max(8, self.size.width or 80),
            max(4, (self.size.height or 24) - (1 if items else 0)),
            seed=self._seed,
            tokens=self._tokens,
            comets=self._comets,
        )
        canvas = self.query_one("#ss-canvas", Static)
        canvas.can_focus = True
        canvas.focus()
        self._sync_size()
        self._paint()
        self._timer = self.set_interval(0.08, self._tick)

    def on_unmount(self) -> None:
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None

    def on_resize(self) -> None:
        self._sync_size()

    def _sync_size(self) -> None:
        try:
            canvas = self.query_one("#ss-canvas", Static)
            width = max(8, canvas.size.width or self.size.width or 80)
            height = max(4, canvas.size.height or self.size.height or 24)
        except Exception:
            width = max(8, self.size.width or 80)
            height = max(4, self.size.height or 24)
        self._field.resize(width, height)

    def _tick(self) -> None:
        self._field.tick(0.08)
        self._ticker.tick(0.08)
        self._paint()

    def _paint(self) -> None:
        try:
            self.query_one("#ss-canvas", Static).update(self._field.render_text())
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
