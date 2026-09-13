"""Защита от Textual `MarkupError`: `[...=...]` в выводе/команде не вешает блок.

Регрессия: `cat` JSON с `"[...-config=/home/vault/config.json"` рвал
`Static.update()` (парсер Textual строже Rich), а `update_content` выставлял
`pending=False` до `update()` — блок навсегда оставался в `[Executing...]`.
"""
from textual.content import Content

from app import CommandRunner, escape_display_markup
from tests.conftest import submit, wait_command_done

# Минимальный фрагмент, на котором падает парсер Textual (тег через строки).
BAD_LINE = '"items": [\n  "a -config=/p.json"\n]'


def test_escape_display_markup_escapes_all_brackets():
    assert escape_display_markup("a[b]c") == "a\\[b]c"
    assert escape_display_markup("") == ""
    assert escape_display_markup(None or "") == ""


async def test_brackets_in_output_do_not_hang_block(isolated_home):
    (isolated_home / "bad.json").write_text("{\n" + BAD_LINE + "\n}\n", encoding="utf-8")
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "cat bad.json")
        block = await wait_command_done(app)
        # Блок не остался в «выполняется» и содержит реальный вывод.
        assert "[Executing...]" not in block.text_content
        assert "-config=/p.json" in block.text_content
        # Версия для рендера безопасна для Textual-разметки…
        Content.from_markup(block._format_output(display=True))
        # …а плоский текст (копирование) — без экранирующих слэшей.
        assert "\\[" not in block._format_output()


async def test_brackets_in_command_header_do_not_hang_block(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, "printf '%s\\n' 'x [ a=/p.json\" ]'")
        block = await wait_command_done(app)
        assert "[Executing...]" not in block.text_content
        Content.from_markup(block._format_output(display=True))
