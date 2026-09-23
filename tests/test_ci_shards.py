"""CI: набор раскладывается по параллельным шардам (`.github/workflows/tests.yml`).

Один джоб на весь набор не влезал в 30-минутный лимит (1321 тест, локально ~25 мин),
поэтому файлы раскладываются по нескольким джобам. Проверяем не «текст ради текста»,
а два инварианта, которые легко сломать при правке workflow:

* шардов больше одного (иначе смысл правки теряется — снова один джоб на всё);
* раскладка — **партиция** всех `tests/test_*.py`: каждый файл ровно в одном шарде
  (ни потерь, ни дублей — иначе часть набора молча не прогоняется).

Сам расчёт шарда — тот же shell-код из workflow (сбор через `--collect-only`
и жадная укладка по числу тестов), поэтому тест проверяет и его работоспособность.
"""
from __future__ import annotations

import glob
import pathlib
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tests.yml"
MATRIX_JOB = "pytest"

pytestmark = pytest.mark.skipif(shutil.which("bash") is None, reason="нужен bash")


def _step_run() -> str:
    cfg = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = cfg["jobs"][MATRIX_JOB]["steps"]
    return next(s["run"] for s in steps if str(s.get("name", "")).startswith("Run tests"))


def _shards() -> list[int]:
    cfg = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return list(cfg["jobs"][MATRIX_JOB]["strategy"]["matrix"]["shard"])


def _files_of_shard(number: int) -> list[str]:
    """Список файлов шарда — исполняем ту же сборку, что делает CI (без pytest)."""
    script = _step_run()
    script = script.replace("${{ matrix.shard }}", str(number))
    script = script.replace("${{ strategy.job-total }}", str(len(_shards())))
    script = script.split("python -m pytest $files")[0]
    for command in (["bash"], ["sh"]):
        if shutil.which(command[0]) is None:
            continue
        result = subprocess.run(
            [*command, "-c", script], cwd=ROOT, capture_output=True, text=True, timeout=300
        )
        assert result.returncode == 0, result.stderr
        files = [
            line.strip() for line in result.stdout.splitlines()
            if line.strip().startswith("tests/")
        ]
        if files:
            return files
    return []


def test_the_suite_is_split_into_parallel_shards():
    shards = _shards()
    assert len(shards) >= 4, shards
    cfg = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = cfg["jobs"][MATRIX_JOB]
    assert job["strategy"]["fail-fast"] is False
    # Таймаут джоба остался с запасом, а таймаут одного теста — короткий:
    # иначе зависший тест съедает бюджет шарда целиком (было --timeout=1200).
    assert job["timeout-minutes"] <= 30
    assert "--timeout=600" in _step_run()
    # Пустой шард — ошибка, а не «зелёный» прогон без тестов.
    assert "exit 1" in _step_run()


def test_shards_partition_every_test_file():
    """Партиция без потерь и дублей — иначе часть набора молча не прогоняется."""
    shards = _shards()
    collected: list[str] = []
    for number in shards:
        collected += _files_of_shard(number)
    expected = sorted(
        str(pathlib.Path(path).relative_to(ROOT))
        for path in glob.glob(str(ROOT / "tests" / "test_*.py"))
    )
    assert sorted(collected) == expected
    assert len(collected) == len(set(collected)), "файл попал в два шарда"


def test_shards_are_evenly_loaded():
    """Баланс по числу собранных тестов: жадная укладка, разброс не больше 1.2x.

    Баланс именно по числу тестов (доступно за 0.6 с через `--collect-only`) —
    прокси для времени; точные числа даёт `--durations=15` в логе CI.
    """
    loads: list[int] = []
    for number in _shards():
        collected = subprocess.run(
            [sys.executable, "-m", "pytest", *_files_of_shard(number), "--collect-only", "-q"],
            cwd=ROOT, capture_output=True, text=True, timeout=300,
        )
        assert collected.returncode == 0, collected.stderr
        last = collected.stdout.strip().splitlines()[-1]
        loads.append(int(last.split()[0].split("/")[0]))
    assert min(loads) > 0, loads
    assert max(loads) <= min(loads) * 1.2, loads
