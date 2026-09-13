"""End-to-end замер вывода больших файлов через реальное приложение (headless).

Прогоняет `cat <файл>` в настоящем `CommandRunner` под `run_test` (без TTY),
меряет время до готового блока и проверяет, что блок обрезан, а полный вывод
доступен. Дополнительно сравнивает старую (split) и новую (rsplit) реализации
хвостовой обрезки журнала на том же тексте.

Запуск:

    python3 experiments/big_output_bench.py                 # 10k / 100k / 500k
    python3 experiments/big_output_bench.py --lines 1000000  # один размер

Данные пишутся в временный каталог, приложение изолировано `$IDVJPY_DATA_DIR`.
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


def make_file(path: str, lines: int, width: int = 80) -> int:
    """Записать `lines` строк; вернуть размер файла в байтах."""
    with open(path, "w", encoding="utf-8") as handle:
        for i in range(lines):
            handle.write(f"{i:>9}  " + ("x" * width) + "\n")
    return os.path.getsize(path)


def old_truncate(text: str, keep: int = 300) -> str:
    """Прежняя реализация: split всей строки в список строк."""
    parts = text.split("\n")
    if len(parts) <= keep:
        return text
    return "\n".join(parts[-keep:])


def new_truncate(text: str, keep: int = 300) -> str:
    """Новая реализация: rsplit с лимитом (аллоцирует только хвост)."""
    parts = text.rsplit("\n", keep)
    if len(parts) <= keep:
        return text
    return "\n".join(parts[1:])


async def measure(lines: int, width: int) -> dict[str, float]:
    from app import CommandRunner
    from tests.conftest import wait_command_done

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["IDVJPY_DATA_DIR"] = tmp
        with open(os.path.join(tmp, "settings.yml"), "w", encoding="utf-8") as cfg:
            # Без сети на старте и без таймаута команды.
            cfg.write("check_updates: false\nscreensaver_idle: 0\ncommand_timeout: 0\n")
        path = os.path.join(tmp, "big.log")
        size = make_file(path, lines, width)

        app = CommandRunner()
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            inp = app.query_one(f"#{app.ID_INPUT}", Input)
            inp.value = f"cat {path}"
            inp.cursor_position = len(inp.value)
            await pilot.pause()
            await pilot.press("escape")
            # Замер — от Enter до готового блока (без посимвольного ввода pilot).
            started = time.perf_counter()
            await pilot.press("enter")
            block = await wait_command_done(app, timeout=300)
            elapsed = time.perf_counter() - started

        text = block.raw_stdout
        raw_lines = text.count("\n")

        started = time.perf_counter()
        old_truncate(text)
        old_s = time.perf_counter() - started

        started = time.perf_counter()
        new_truncate(text)
        new_s = time.perf_counter() - started

        return {
            "lines": raw_lines,
            "size_mb": size / 1024 / 1024,
            "elapsed_s": elapsed,
            "truncated": float(block._truncated),
            "old_ms": old_s * 1000,
            "new_ms": new_s * 1000,
        }


async def main_async(sizes: list[int], width: int) -> int:
    print(f"big_output_bench — cat через приложение (width={width} симв.)")
    print("-" * 84)
    header = (
        f"{'строк':>10} {'файл, МБ':>9} {'блок, с':>9} {'обрезка':>8} "
        f"{'split, мс':>10} {'rsplit, мс':>11} {'ускорение':>10}"
    )
    print(header)
    for lines in sizes:
        r = await measure(lines, width)
        speedup = (r["old_ms"] / r["new_ms"]) if r["new_ms"] else float("inf")
        print(
            f"{r['lines']:>10,} {r['size_mb']:>9.1f} {r['elapsed_s']:>9.2f} "
            f"{'да' if r['truncated'] else 'нет':>8} "
            f"{r['old_ms']:>10.1f} {r['new_ms']:>11.1f} {speedup:>9.1f}x"
        )
    print("-" * 84)
    print("Полный вывод без обрезки открывается в приложении по :log / F7 (Line API).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="big_output_bench")
    parser.add_argument(
        "--lines",
        type=int,
        action="append",
        help="размер в строках (можно несколько раз); по умолчанию 10k/100k/500k",
    )
    parser.add_argument("--width", type=int, default=80, help="длина строки в символах")
    args = parser.parse_args(argv)
    sizes = args.lines or [10_000, 100_000, 500_000]
    return asyncio.run(main_async(sizes, args.width))


if __name__ == "__main__":
    raise SystemExit(main())
