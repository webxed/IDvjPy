#!/usr/bin/env bash
# Build an installable idvjpy-term wheel from the current source tree.
#
# The wheel embeds a private copy of ../src inside the boot package
# (idvjpy_boot/src). At runtime the bootstrapper puts that directory on
# sys.path, so top-level imports (app, database_v2, ...) and resources
# (app.tcss, demos/, *.example.yml, .bashrc_term.example) resolve from the
# installed package, not from a source checkout.
#
# Usage:
#   packaging/build_wheel.sh          # build into packaging/dist/
#
# Requirements: python3 with pip + setuptools>=68 (no network needed:
# the build is isolated from PyPI via --no-build-isolation --no-deps).
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
# The embedded copy is shipped code-only: drop interpreter caches.
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
