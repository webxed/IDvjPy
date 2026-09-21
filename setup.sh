#!/usr/bin/env bash
# Setup IDvjPy_term: виртуальное окружение + зависимости.
#   ./setup.sh                 # .venv + runtime-зависимости
#   ./setup.sh --shell-helper  # функция-обёртка в shell-rc (cwd следует за приложением) и выход
#   pip install -r requirements-dev.txt   # плюс тесты (pytest)
# Запуск приложения: python3 app.py   (данные — settings.yml / БД — создаются сами)
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
REPO_DIR="$(pwd)"

# Функция-обёртка: каталог оболочки следует за приложением. Сменить cwd
# родительской оболочки дочерний процесс не может, поэтому обёртка читает
# `$IDVJPY_CWD_FILE` уже после выхода приложения и делает `cd` (как ranger/nnn).
# Куда писать — `$IDVJPY_RC`, иначе rc текущего shell (zsh → `.zshrc`, остальные
# → `.bashrc`); чужое содержимое не затирается, рядом кладётся `.idvjpy.bak`.
# Повторный прогон обновляет только свой блок между маркерами.
install_shell_helper() {
    local rc="${IDVJPY_RC:-}"
    if [ -z "$rc" ]; then
        case "${SHELL:-}" in
            *zsh) rc="${ZDOTDIR:-$HOME}/.zshrc" ;;
            *) rc="$HOME/.bashrc" ;;
        esac
    fi
    # Запуск: pip-пакет (`command` — чтобы не звать эту же функцию) или этот клон.
    local launch
    if command -v idvjpy >/dev/null 2>&1; then
        launch='command idvjpy'
    else
        launch="python3 '$REPO_DIR/app.py'"
    fi
    local block
    block="$(cat <<'WRAPPER'
# >>> idvjpy cwd helper >>>
idvjpy() {                     # каталог shell следует за приложением
    local f; f="$(mktemp)"
    IDVJPY_CWD_FILE="$f" @LAUNCH@ "$@"
    cd "$(cat "$f")" 2>/dev/null
    rm -f "$f"
}
# <<< idvjpy cwd helper <<<
WRAPPER
)"
    block="${block//@LAUNCH@/$launch}"
    local begin="${block%%$'\n'*}"
    local end="${block##*$'\n'}"

    local tmp; tmp="$(mktemp)"
    if [ -f "$rc" ]; then
        # Выкинуть прошлый блок (если был) — путь к app.py мог измениться.
        awk -v b="$begin" -v e="$end" '
            $0 == b { skip = 1 }
            skip != 1 { print }
            $0 == e { skip = 0 }
        ' "$rc" > "$tmp"
        cp "$rc" "$rc.idvjpy.bak"
    fi
    # Хвостовые пустые строки не копим: `$(cat …)` срезает их, а блок кладём
    # после ровно одной пустой строки (иначе каждый прогон добавлял бы ещё одну).
    local body; body="$(cat "$tmp")"
    : > "$tmp"
    [ -n "$body" ] && printf '%s\n\n' "$body" >> "$tmp"
    printf '%s\n' "$block" >> "$tmp"
    mv "$tmp" "$rc"

    echo "==> Обёртка idvjpy записана в $rc"
    [ -f "$rc.idvjpy.bak" ] && echo "    копия прежнего файла: $rc.idvjpy.bak"
    echo "    Новый терминал подхватит сам; в текущем — source $rc"
    echo "    Зависимости (если ещё не): ./setup.sh"
}

for arg in "$@"; do
    case "$arg" in
        --shell-helper)
            # Отдельное действие (как `backup_db.py`): правит shell, а не проект,
            # и работы с venv не требует.
            install_shell_helper
            exit 0
            ;;
        -h|--help)
            sed -n '2,7p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Неизвестный флаг: $arg (см. ./setup.sh --help)" >&2
            exit 1
            ;;
    esac
done

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
