#!/usr/bin/env bash
# Setup IDvjPy_term: виртуальное окружение + зависимости.
#   ./setup.sh              # .venv + runtime-зависимости
#   pip install -r requirements-dev.txt   # плюс тесты (pytest)
# Запуск приложения: python3 app.py   (данные — settings.yml / БД — создаются сами)
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

python="python3"
if ! command -v "$python" >/dev/null 2>&1; then
    echo "Нужен python3 (проект требует Python 3.12+)." >&2
    exit 1
fi
if ! "$python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)'; then
    echo "Нужен Python 3.12+ (сейчас: $("$python" -V 2>&1))." >&2
    exit 1
fi

if [ ! -d .venv ]; then
    echo "==> Создаю .venv"
    "$python" -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate

echo "==> Ставлю зависимости из requirements.txt"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

echo
echo "Готово. Запуск: python3 app.py"
echo "Тесты (отдельно): pip install -r requirements-dev.txt && python3 -m pytest tests/ -v"
echo "Необязательные справочники:"
echo "  python3 src/seed_linux_commands.py --seed   # linux"
echo "  python3 src/seed_k8s_chains.py --seed       # k8s (K8S_CHAINS.md)"
echo "  python3 src/seed_git.py --seed              # git"
echo "  python3 src/seed_ops.py --seed              # остальные ops"
echo "Данные (settings.yml, mytags.db, history) создаются при первом запуске;"
echo "каталог задаётся флагами --data-dir / \$IDVJPY_DATA_DIR (иначе — системный)."
