#!/bin/sh
# Демостенд IDvjPy_term: подготовить data-каталог, один раз наполнить библиотеку
# тегов и запустить TUI. Аргументы пробрасываются в app.py, например:
#   docker compose run --rm idvjpy --demo short --demo-quit
set -eu

APP_DIR="${IDVJPY_APP_DIR:-/app}"
DATA_DIR="${IDVJPY_DATA_DIR:-/data}"

cd "$DATA_DIR"

# Первый запуск в пустом томе: личные файлы создаются из шаблонов — ровно так,
# как приложение делает это в обычном data-каталоге. Шаблоны локализованы по
# каталогам src/settings/<lang>.yml и src/llm_providers/<lang>.yml; язык —
# в режиме auto ($IDVJPY_LANG → $LC_ALL/$LC_MESSAGES/$LANG → en).
lang="${IDVJPY_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}"
lang="$(printf '%s' "$lang" | tr 'A-Z' 'a-z' | cut -d. -f1 | cut -d_ -f1 | cut -d- -f1)"
case "$lang" in
    en|ru|zh) : ;;
    *)        lang="en" ;;
esac

if [ ! -f settings.yml ]; then
    cp "$APP_DIR/src/settings/$lang.yml" settings.yml
    echo "[demo] settings.yml ← src/settings/$lang.yml"
fi
if [ ! -f llm_providers.yml ]; then
    cp "$APP_DIR/src/llm_providers/$lang.yml" llm_providers.yml
    echo "[demo] llm_providers.yml ← src/llm_providers/$lang.yml"
fi

# Образец документа для `:md`: docx — это ZIP с XML, поэтому собираем его на месте
# (бинарник в репозитории не нужен). Дальше — как обычные данные: `:md report.docx`.
if [ ! -f report.docx ]; then
python3 - <<'PY'
import zipfile

TYPES = (
    '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument'
    '.wordprocessingml.document.main+xml"/></Types>'
)
RELS = (
    '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
    'officeDocument" Target="word/document.xml"/></Relationships>'
)
LINES = (
    'Report',
    'Revenue grew by 12 percent in Q3.',
    'Owners: platform team.',
)
BODY = (
    '<?xml version="1.0"?>'
    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
    + ''.join('<w:p><w:r><w:t>' + line + '</w:t></w:r></w:p>' for line in LINES)
    + '</w:body></w:document>'
)
with zipfile.ZipFile('report.docx', 'w') as archive:
    archive.writestr('[Content_Types].xml', TYPES)
    archive.writestr('_rels/.rels', RELS)
    archive.writestr('word/document.xml', BODY)
PY
    echo "[demo] report.docx — образец документа для :md (docx → markdown)"
fi

has_live_commands() {
    python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import database_v2 as db
from seed_lib import get_db_file
try:
    live = db.has_live_commands(get_db_file())
except Exception:  # пустой файл без схемы — считаем, что библиотеки нет
    live = False
raise SystemExit(0 if live else 1)
' "$APP_DIR/src"
}

# Библиотека тегов: сеем один раз, чтобы `?`, `??` и `!tag[tid]` сразу было что
# показать. Повторный запуск ничего не пересобирает (и не плодит бэкапы).
if has_live_commands; then
    :
else
    # Посев сам делает снимки БД перед заменой тегов (защита от потери).
    # В стартовом состоянии демо терять нечего (БД пустая, в снимках — только
    # что залитые нами seed-теги), поэтому если папки снимков до нас не было,
    # убираем её — иначе первый запуск выглядит как «после инцидента».
    if [ -d backups ]; then
        had_backups=yes
    else
        had_backups=no
    fi
    echo "[demo] наполняю библиотеку тегов (linux, k8s, git, ops) — один раз"
    for seed in seed_linux_commands seed_k8s_chains seed_git seed_ops; do
        python3 "$APP_DIR/src/$seed.py" --seed >/dev/null
    done
    if [ "$had_backups" = no ]; then
        rm -rf backups   # backup_dir: backups (settings.yml)
    fi
    live=$(python3 -c '
import sys
sys.path.insert(0, sys.argv[1])
import database_v2 as db
from seed_lib import get_db_file
print(db.usage_stats(get_db_file())["live"])
' "$APP_DIR/src")
    echo "[demo] готово: $live команд. Начните с :?   ?   ??   !tag[tid]   :q"
fi

exec python3 "$APP_DIR/app.py" "$@"
