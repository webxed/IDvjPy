"""Замер цены перерисовки блока: Static-блок vs Line-API-блок.

End-to-end `cat` упирается в сам `cat`, а блок всё равно обрезается до
``MAX_DISPLAY_LINES``. Разница между реализациями — в цене перерисовки:
обычный блок на каждое движение построчного курсора вызывает ``Static.update``
и заново парсит разметку всего вывода; Line-API-блок держит Strip'ы в кэше и
делает ``refresh()``.

Запуск:

    python3 experiments/line_api_block_bench.py
    python3 experiments/line_api_block_bench.py --lines 300 --iterations 200
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
import time

from textual.widgets import Input

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC = os.path.join(ROOT, "src")
for _path in (ROOT, _SRC):
    if _path not in sys.path:
        sys.path.insert(0, _path)


async def measure(line_api: bool, lines: int, iterations: int) -> dict[str, float]:
    os.environ["IDVJPY_LINE_BLOCKS"] = "1" if line_api else "0"
    from app import CommandLineBlock, CommandRunner
    from tests.conftest import wait_command_done

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["IDVJPY_DATA_DIR"] = tmp
        with open(os.path.join(tmp, "settings.yml"), "w", encoding="utf-8") as cfg:
            cfg.write("check_updates: false\nscreensaver_idle: 0\ncommand_timeout: 0\n")
        path = os.path.join(tmp, "rows.log")
        with open(path, "w", encoding="utf-8") as handle:
            for i in range(lines):
                handle.write(f"{i:>9}  " + ("x" * 60) + "\n")

        app = CommandRunner()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            inp = app.query_one(f"#{app.ID_INPUT}", Input)
            inp.value = f"cat {path}"
            inp.cursor_position = len(inp.value)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.press("enter")
            block = await wait_command_done(app, timeout=60)

            # Первичный рендер: высота + все строки (как делает кадр).
            width = int(block.size.width)
            started = time.perf_counter()
            height = block.get_content_height(block.size, block.size, width)
            for y in range(height):
                block.render_line(y)
            first_render_ms = (time.perf_counter() - started) * 1000

            # Движение построчного курсора: перерисовка одной строки.
            block.enter_line_nav(notify=False)
            mid = max(0, height // 2)
            block.line_index = mid
            started = time.perf_counter()
            for _ in range(iterations):
                block._paint_line_cursor()
            cursor_ms = (time.perf_counter() - started) * 1000 / iterations

            block.exit_line_nav(notify=False)

            return {
                "line_api": float(line_api),
                "kind": float(isinstance(block, CommandLineBlock)),
                "lines": height,
                "first_render_ms": first_render_ms,
                "cursor_ms": cursor_ms,
            }


async def main_async(lines: int, iterations: int) -> int:
    print(f"line_api_block_bench — блок из {lines:,} строк, {iterations} движений курсора")
    print("-" * 74)
    print(f"{'блок':<22} {'строк всего':>12} {'1-й рендер, мс':>15} {'курсор, мс/шаг':>16}")
    results = []
    for flag in (False, True):
        r = await measure(flag, lines, iterations)
        results.append(r)
        name = "Line API (render_line)" if flag else "Static (update)"
        print(
            f"{name:<22} {r['lines']:>12,} {r['first_render_ms']:>15.2f} "
            f"{r['cursor_ms']:>16.3f}"
        )
    print("-" * 74)
    old, new = results[0], results[1]
    if new["cursor_ms"]:
        print(f"Ускорение движения курсора: {old['cursor_ms'] / new['cursor_ms']:.1f}x")
    print("Первый рендер у Line API может быть чуть дороже: он строит Strip'ы на кадр.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="line_api_block_bench")
    parser.add_argument("--lines", type=int, default=300, help="строк вывода")
    parser.add_argument("--iterations", type=int, default=100, help="движений курсора")
    args = parser.parse_args(argv)
    return asyncio.run(main_async(args.lines, args.iterations))


if __name__ == "__main__":
    raise SystemExit(main())
