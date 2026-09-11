"""`$VAR=@key` / `$$VAR=@key` — значение из табличного вывода блока.

Строка, первый токен которой равен `key` (таблицы `vault read` / `vault write`),
иначе `@last` — последняя непустая строка. Работает с сфокусированным или
последним завершённым CommandBlock.
"""
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

from app import CommandRunner
from tests.conftest import last_info, submit, wait_command_done

TABLE = (
    "printf 'Key        Value\\n---        -----\\n"
    "role_id    2474a21f-uuid\\nsecret_id  abc-def\\n'"
)


async def test_capture_table_row_into_var(isolated_home):
    """`$VAR=@key` берёт остаток строки таблицы; значение не из журнала-вывода."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, TABLE)
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "$MYROLE=@role_id")
        await pilot.pause()
        assert app.local_env.get("MYROLE") == "2474a21f-uuid"
        assert "from block @role_id" in last_info(app).text_content


async def test_capture_secret_from_table(isolated_home):
    """`$$VAR=@key` кладёт значение в секреты, без показа в журнале."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, TABLE)
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "$$MYSEC=@secret_id")
        await pilot.pause()
        assert app.local_env.get("MYSEC") == "abc-def"
        assert "MYSEC" in app._secret_names
        assert "abc-def" not in last_info(app).text_content
        assert "abc-def" in Path(app.FILE_SECRETS).read_text(encoding="utf-8")


async def test_capture_missing_key_lists_keys(isolated_home):
    """Нет строки с таким ключом — явная ошибка со списком ключей."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, TABLE)
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "$X=@nope")
        await pilot.pause()
        text = last_info(app).text_content
        assert "not found" in text
        assert "role_id" in text
        assert "X" not in app.local_env


async def test_capture_without_finished_block_errors(isolated_home):
    """Нет завершённого блока — явная ошибка, без переменной."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "$X=@role_id")
        await pilot.pause()
        assert "no finished command block" in last_info(app).text_content
        assert "X" not in app.local_env


async def test_capture_last_line(isolated_home):
    """`@last` — последняя непустая строка (после `| jq -r .field`)."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "printf 'a\\nb\\nlast-val\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "$V=@last")
        await pilot.pause()
        assert app.local_env.get("V") == "last-val"


async def test_capture_value_keeps_spaces(isolated_home):
    """Значение — всё после ключа (политики, списки в скобках)."""
    app = CommandRunner()
    async with app.run_test(size=(120, 40)) as pilot:
        await submit(pilot, "printf 'token_policies  [\"default\" \"stage:ro\"]\\n'")
        await wait_command_done(app, timeout=8.0)
        await submit(pilot, "$POL=@token_policies")
        await pilot.pause()
        assert app.local_env.get("POL") == '["default" "stage:ro"]'
