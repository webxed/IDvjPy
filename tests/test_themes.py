"""Темы: своя `matrix` и приглушённая подсветка блока в фокусе.

Тема `matrix` — зелёный фосфор на почти чёрном, как в скринсейвере (`#00ff5f`).
Пока она активна, на `Screen` висит класс `matrix-mode`, по которому app.tcss
красит рамки (в остальных темах они свои — фиолетовые).

Подсветка блока в фокусе — `$primary 25%` (смешение с фоном блока): сплошной
`$primary-darken-1` слепил, особенно на большом блоке.
"""
from __future__ import annotations

from textual.geometry import Region

from app import MATRIX_CLASS, MATRIX_THEME, MATRIX_THEME_NAME, CommandRunner
from tests.conftest import submit, wait_command_done


def _input_row(app):
    """Строка ввода: рамка (и подсветка фокуса) живёт на контейнере, не на поле."""
    return app.query_one(f"#{app.ID_INPUT_ROW}")


def _hex_of(color) -> str:
    """Цвет в `#rrggbb` (Textual-Color отдаёт `.hex`, rich — через truecolor)."""
    hex_value = getattr(color, "hex", None)
    if isinstance(hex_value, str):
        return hex_value.lower()
    try:
        return color.get_truecolor().hex.lower()
    except Exception:  # pragma: no cover — запасной путь для нестандартных цветов
        return str(color).lower()


def _brightness(hex_color: str) -> float:
    """Грубая яркость 0..255 (0.299R + 0.587G + 0.114B)."""
    text = hex_color.lstrip("#")
    if len(text) != 6:
        return -1.0
    r, g, b = (int(text[i : i + 2], 16) for i in (0, 2, 4))
    return round(0.299 * r + 0.587 * g + 0.114 * b, 1)


def _rendered_bg(block, rows: int = 4) -> str:
    """Фон текстового сегмента отрисованного блока (как в кадре)."""
    width = int(block.size.width)
    height = min(rows, int(block.size.height))
    for strip in block.render_lines(Region(0, 0, width, height)):
        for segment in strip:
            if segment.text.strip() and segment.style and segment.style.bgcolor:
                return _hex_of(segment.style.bgcolor)
    return "(none)"


def _write_settings(home, text: str) -> None:
    (home / "settings.yml").write_text(
        "check_updates: false\nscreensaver_idle: 0\n" + text, encoding="utf-8"
    )


async def _focus_and_measure(app, pilot) -> tuple[str, str]:
    """Фон блока до и после фокуса (Tab)."""
    await submit(pilot, "echo theme-check")
    block = await wait_command_done(app)
    await pilot.press("escape")
    await pilot.pause()
    unfocused = _rendered_bg(block)
    await pilot.press("tab")
    await pilot.pause()
    await pilot.pause()
    return unfocused, _rendered_bg(block)


def test_matrix_theme_palette():
    """Палитра matrix: фосфор на почти чёрном, тёмная тема."""
    assert MATRIX_THEME.name == MATRIX_THEME_NAME
    assert MATRIX_THEME.dark is True
    assert MATRIX_THEME.primary.lower() == "#00ff5f"  # тот же зелёный, что в скринсейвере
    assert MATRIX_THEME.background is not None
    r, g, b = (
        int(MATRIX_THEME.background.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)
    )
    assert g > r and g > b  # зелёный оттенок, а не серый


async def test_matrix_theme_is_selectable(isolated_home):
    """`:theme matrix` (и settings.yml) включают тему, она есть в списке."""
    _write_settings(isolated_home, f"theme: {MATRIX_THEME_NAME}\n")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert MATRIX_THEME_NAME in app.available_themes
        assert app.theme == MATRIX_THEME_NAME
        assert app.screen.has_class(MATRIX_CLASS)
        # Рамка строки ввода — в тон фосфору, а не фиолетовая.
        border = _input_row(app).styles.border_top
        assert _hex_of(border[1]).lower() == MATRIX_THEME.primary.lower()


async def test_matrix_class_follows_theme(isolated_home):
    """Класс `matrix-mode` — только пока активна matrix."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert not app.screen.has_class(MATRIX_CLASS)
        default_border = _hex_of(_input_row(app).styles.border_top[1])

        await submit(pilot, f":theme {MATRIX_THEME_NAME}")
        await pilot.pause()
        assert app.screen.has_class(MATRIX_CLASS)
        assert _hex_of(_input_row(app).styles.border_top[1]) != default_border

        await submit(pilot, ":theme textual-dark")
        await pilot.pause()
        assert not app.screen.has_class(MATRIX_CLASS)
        assert _hex_of(_input_row(app).styles.border_top[1]) == default_border


async def test_matrix_theme_survives_restart(isolated_home):
    """`:theme matrix` пишется в settings.yml и подхватывается при старте."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        await submit(pilot, f":theme {MATRIX_THEME_NAME}")
        await pilot.pause()
    assert f"theme: {MATRIX_THEME_NAME}" in (isolated_home / "settings.yml").read_text(
        encoding="utf-8"
    )

    second = CommandRunner()
    async with second.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert second.theme == MATRIX_THEME_NAME
        assert second.screen.has_class(MATRIX_CLASS)


async def test_palette_theme_change_keeps_input_row_width(isolated_home):
    """Смена темы при открытой палитре не ломает рамку строки ввода.

    Textual матчит CSS по **имени класса**: у поля палитры `Ctrl+P` (в
    `textual.command`) оно совпадает с именем нашего виджета и объявляет
    `width: 1fr; border: blank; …`. Пока строка ввода была самим полем, это
    правило начинало действовать на нём, как только палитра открывалась (её CSS
    попадает в общий stylesheet), а применялось — при следующем переприменении
    CSS (смена темы): поле становилось шире экрана на колонку, и правая рамка
    уезжала за край. Теперь рамка — у контейнера `#input-row`, а поле адресуется
    по id, так что чужое правило не решает ничего: сторож смотрит на строку.
    """
    app = CommandRunner()
    async with app.run_test(size=(70, 18)) as pilot:
        await pilot.pause()
        row = _input_row(app)
        assert row.region.width == 70 - 2  # margin 0 1: по колонке с каждой стороны
        inp = app.query_one(f"#{app.ID_INPUT}")
        assert inp.region.right <= row.region.right - 1  # поле внутри рамки

        await pilot.press("ctrl+p")
        await pilot.pause()
        await pilot.pause()
        app.theme = "textual-light"  # ровно как ThemeProvider (DiscoveryHit)
        await pilot.pause()
        await pilot.pause()
        assert row.region.width == 70 - 2, "строка ввода поехала от чужого CSS"
        assert inp.region.right <= row.region.right - 1

        await pilot.press("escape")
        await pilot.pause()
        await pilot.pause()
        assert row.region.width == 70 - 2
        assert inp.region.right <= row.region.right - 1


async def test_block_focus_highlight_is_soft(isolated_home):
    """Подсветка блока в фокусе: видна, но не слепит (было `$primary-darken-1`)."""
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause()
        assert app.theme == "textual-dark"
        unfocused, focused = await _focus_and_measure(app, pilot)

    assert focused != unfocused  # подсветка есть
    lift = _brightness(focused) - _brightness(unfocused)
    # Сплошной `$primary-darken-1` давал скачок ~65; смешение 25% — ~19.
    assert 0 < lift < 40, (unfocused, focused)
