"""`:watch <sec> <command>` — периодический перезапуск команды (фича watch).

Один блок, тики обновляют его; F4 / :kill / :watch stop / :c останавливают.
"""
import asyncio
import re

import pytest

pytestmark = pytest.mark.slow

from app import CommandBlock, CommandRunner
from tests.conftest import last_info, submit


async def _watch_block(app: CommandRunner) -> CommandBlock:
    for _ in range(100):
        blocks = [b for b in app.query(CommandBlock) if getattr(b, "_watch", False)]
        if blocks:
            return blocks[-1]
        await asyncio.sleep(0.05)
    raise AssertionError("No watch block found")


def _last_tick(block: CommandBlock) -> int:
    """Номер последнего тика из текста блока (каждый тик заменяет текст)."""
    match = re.findall(r"watch #(\d+)", block.text_content or "")
    return max((int(n) for n in match), default=0)


async def test_watch_ticks_update_one_block(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":watch 1 echo tick")
        block = await _watch_block(app)
        await asyncio.sleep(2.6)
        assert _last_tick(block) >= 2
        assert "watch stopped" not in (block.text_content or "")


async def test_watch_stop_finalizes_block(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":watch 1 echo tick")
        block = await _watch_block(app)
        await asyncio.sleep(1.3)
        await submit(pilot, ":watch stop")
        # Ждём финализацию из потока.
        for _ in range(100):
            if not block.pending and app._watch_state is None:
                break
            await asyncio.sleep(0.05)
        assert app._watch_state is None
        assert not block.pending
        assert "watch stopped after" in (block.text_content or "")


async def test_watch_usage_and_single_instance(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":watch")
        assert "Usage: :watch <sec>" in last_info(app).text_content
        await submit(pilot, ":watch abc echo x")
        assert "Usage: :watch <sec>" in last_info(app).text_content
        await submit(pilot, ":watch -1 echo x")
        assert "sec должен быть > 0" in last_info(app).text_content
        await submit(pilot, ":watch 1 echo a")
        await _watch_block(app)
        await submit(pilot, ":watch 1 echo b")
        assert "already running" in last_info(app).text_content
        await submit(pilot, ":watch stop")
        await submit(pilot, ":watch stop")
        assert "No active watch to stop" in last_info(app).text_content


async def test_clear_stops_watch(isolated_home):
    app = CommandRunner()
    async with app.run_test(size=(100, 30)) as pilot:
        await submit(pilot, ":watch 1 echo tick")
        await _watch_block(app)
        await submit(pilot, ":c")
        # Поток-цикл получил event и завершился; новый watch можно запускать.
        await asyncio.sleep(0.3)
        await submit(pilot, ":watch 1 echo again")
        await _watch_block(app)
        assert app._watch_state is not None
        await submit(pilot, ":watch stop")
        for _ in range(100):
            if app._watch_state is None:
                break
            await asyncio.sleep(0.05)
        assert app._watch_state is None
