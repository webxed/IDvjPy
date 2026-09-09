#!/usr/bin/env bash
# Build an installable idvjpy-term wheel from the current source tree.
#
# The wheel embeds a private copy of ../src inside the boot package
# (idvjpy_boot/src). At runtime the bootstrapper puts that directory on
# sys.path, so top-level imports (app, database_v2, ...) and resources
# (app.css, demos/, *.example.yml, .bashrc_term.example) resolve from the
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
HERE="$(pwd)"

echo "==> Embedding current $(pwd)/../src into $EMBED"
rm -rf "$EMBED"
mkdir -p "$EMBED"
cp -R ../src/. "$EMBED/"
# The embedded copy is shipped code-only: drop interpreter caches.
find "$EMBED" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$EMBED" -type f -name '*.py[co]' -delete

echo "==> Building wheel (no build isolation; uses installed setuptools)"
rm -rf dist build idvjpy_boot.egg-info
python3 -m pip wheel . --no-deps --no-build-isolation -w dist >/dev/null

wheel="$(ls dist/idvjpy_term-*.whl)"
echo "==> Built: ${wheel#dist/}"
echo "==> Restoring clean package state (embedded src is generated on demand)"
rm -rf "$EMBED" idvjpy_boot.egg-info build
echo "==> Done. Install with: pip install \"$HERE/$wheel\""
