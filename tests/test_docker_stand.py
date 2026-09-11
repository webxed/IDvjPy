"""Демостенд в Docker: файлы стенда на месте и не разъехались.

Собирать образ в тестах дорого, поэтому проверяем статически: что entrypoint
сеет существующие seed-скрипты, что compose указывает на корень репозитория и
именованный том, и что Dockerfile копирует код и тянет зависимости.
"""
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCKER = ROOT / "docker"
DEMO_VOLUME = "idvjpy-demo-data"


def test_stand_files_and_entrypoint_shebang():
    for name in ("Dockerfile", "entrypoint.sh", "compose.yaml", "README.md", "tui-smoke.py"):
        assert (DOCKER / name).is_file(), name
    assert (ROOT / ".dockerignore").is_file()
    # Образ запускает entrypoint напрямую, поэтому важен shebang; бит +x в git
    # не проверяем — он зависит от core.fileMode, а в Dockerfile есть chmod +x.
    first_line = (DOCKER / "entrypoint.sh").read_text(encoding="utf-8").splitlines()[0]
    assert first_line.startswith("#!")
    smoke = (DOCKER / "tui-smoke.py").read_text(encoding="utf-8")
    assert smoke.startswith("#!/usr/bin/env python3")


def test_entrypoint_seeds_existing_scripts():
    text = (DOCKER / "entrypoint.sh").read_text(encoding="utf-8")
    names = sorted(set(re.findall(r"seed_[a-z0-9_]+", text)))
    assert names, "entrypoint не упоминает ни одного seed-скрипта"
    for name in names:
        assert (ROOT / "src" / f"{name}.py").is_file(), f"нет src/{name}.py"
    # Шаблоны копируются из src/, а посев идёт только при пустой библиотеке.
    assert "settings.example.yml" in text
    assert "llm_providers.example.yml" in text
    assert "has_live_commands" in text


def test_compose_builds_from_repo_root_with_tty_and_named_volume():
    cfg = yaml.safe_load((DOCKER / "compose.yaml").read_text(encoding="utf-8"))
    service = cfg["services"]["idvjpy"]
    assert service["build"]["context"] == ".."
    # Путь к Dockerfile — от контекста сборки (корня репозитория), а не от docker/.
    assert (ROOT / service["build"]["dockerfile"]).is_file()
    # TUI без TTY не запустится.
    assert service["tty"] is True
    assert service["stdin_open"] is True
    assert any(entry.startswith("idvjpy-data:") for entry in service["volumes"])
    assert any(entry.endswith(":/data") for entry in service["volumes"])
    assert cfg["volumes"]["idvjpy-data"]["name"] == DEMO_VOLUME
    # Команда сброса в README должна называть тот же том.
    readme = (DOCKER / "README.md").read_text(encoding="utf-8")
    assert f"docker volume rm {DEMO_VOLUME}" in readme


def test_dockerfile_installs_deps_and_copies_app():
    text = (DOCKER / "Dockerfile").read_text(encoding="utf-8")
    base = next(line for line in text.splitlines() if line.startswith("FROM "))
    assert base.startswith("FROM python:3.12-alpine")  # маленькая база — часть замысла
    assert "COPY requirements.txt" in text
    assert "COPY src/ ./src/" in text
    assert "COPY docker/tui-smoke.py" in text  # смоук TUI едет в образ
    assert "ENTRYPOINT" in text and "idvjpy-demo" in text
    # Приложение запускает команды и TTY через /bin/bash — в образе он обязателен.
    assert "bash" in text
    # Данные живут в томе.
    assert 'VOLUME ["/data"]' in text


def test_dockerignore_keeps_context_small_but_keeps_requirements():
    lines = [
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    ]
    for needed in (".git", ".venv", "tests", "packaging"):
        assert needed in lines, f".dockerignore не исключает {needed}"
    # requirements.txt нужен образу, поэтому исключение идёт после маски.
    assert "*.txt" in lines
    assert lines.index("!requirements.txt") > lines.index("*.txt")


def test_ci_job_builds_and_smokes_the_stand():
    """GitHub Actions собирает образ и прогоняет те же проверки, что и локально."""
    text = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    cfg = yaml.safe_load(text)
    assert "docker-demo" in cfg["jobs"], "в workflow нет job со стендом"
    job = cfg["jobs"]["docker-demo"]
    assert job["runs-on"] == "ubuntu-latest"
    uses = [step.get("uses", "") for step in job["steps"]]
    assert any("docker/build-push-action" in item for item in uses), uses
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "docker/Dockerfile" in text
    assert "--demo short --demo-quit" in commands
    # TUI в CI рендерится под pty: смоук-скрипт едет в образ.
    assert "/usr/local/bin/tui-smoke.py" in commands
    # Первый запуск сеет, второй — нет: проверяем идемпотентность стенда.
    assert "наполняю библиотеку тегов" in commands
