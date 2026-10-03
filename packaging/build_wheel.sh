#!/usr/bin/env bash
# Собрать устанавливаемый wheel idvjpy-term из текущего дерева исходников.
#
# Wheel встраивает приватную копию ../src внутрь boot-пакета
# (idvjpy_boot/src). При запуске бутстрап кладёт этот каталог в sys.path,
# поэтому импорты верхнего уровня (app, database_v2, …) и ресурсы
# (app.tcss, demos/, *.example.yml, .bashrc_term.example) берутся из
# установленного пакета, а не из исходного дерева.
#
# Использование:
#   packaging/build_wheel.sh          # сборка в packaging/dist/
#
# Требования: python3 с pip + setuptools>=68 (сеть не нужна: сборка
# изолирована от PyPI через --no-build-isolation --no-deps).
set -euo pipefail

cd "$(dirname "$0")"
EMBED="idvjpy_boot/src"
EMBED_DOCS="idvjpy_boot/docs"
EMBED_OVERVIEW="idvjpy_boot/K8S_CHAINS.md"
HERE="$(pwd)"

echo "==> Embedding current $(pwd)/../src into $EMBED"
rm -rf "$EMBED"
mkdir -p "$EMBED"
cp -R ../src/. "$EMBED/"
# Встраиваемая копия поставляется только кодом: убираем кэши интерпретатора.
find "$EMBED" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$EMBED" -type f -name '*.py[co]' -delete

# Справочники `:md` (`docs/<lang>/*.md`) и обзор k8s: `handbook_md_path` ищет их в
# REPO_ROOT — у установленного пакета это каталог idvjpy_boot/.
echo "==> Embedding handbooks: ../docs, ../K8S_CHAINS.md"
rm -rf "$EMBED_DOCS"
mkdir -p "$EMBED_DOCS"
cp -R ../docs/. "$EMBED_DOCS/"
find "$EMBED_DOCS" -type d -name '__pycache__' -prune -exec rm -rf {} +
cp ../K8S_CHAINS.md "$EMBED_OVERVIEW"

echo "==> Building wheel (no build isolation; uses installed setuptools)"
rm -rf dist build idvjpy_boot.egg-info
python3 -m pip wheel . --no-deps --no-build-isolation -w dist >/dev/null

wheel="$(ls dist/idvjpy_term-*.whl)"
echo "==> Built: ${wheel#dist/}"
echo "==> Restoring clean package state (embedded src is generated on demand)"
rm -rf "$EMBED" "$EMBED_DOCS" "$EMBED_OVERVIEW" idvjpy_boot.egg-info build
echo "==> Done. Install with: pip install \"$HERE/$wheel\""
