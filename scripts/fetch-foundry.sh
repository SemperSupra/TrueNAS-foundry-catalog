#!/bin/sh
set -eu
: "${FOUNDRY_REF:?FOUNDRY_REF must be full immutable Git SHA}"
case "$FOUNDRY_REF" in *[!a-f0-9]*|'') echo 'invalid ref' >&2; exit 2 ;; esac
[ "${#FOUNDRY_REF}" -eq 40 ] || { echo 'expected 40-character ref' >&2; exit 2; }
cd /tmp
mkdir -p upstream
cd upstream
git init -q
git remote add upstream https://github.com/SemperSupra/truenas-app-foundry.git
git fetch --no-tags --depth=1 upstream "$FOUNDRY_REF"
[ "$(git rev-parse FETCH_HEAD)" = "$FOUNDRY_REF" ] || { echo 'source SHA drift' >&2; exit 2; }
VENDOR_DIR=${VENDOR_DIR:-/app/vendor}
mkdir -p "$VENDOR_DIR"
git show "$FOUNDRY_REF:tools/foundry_catalog_federation.py" > "$VENDOR_DIR/foundry_catalog_federation.py"
git show "$FOUNDRY_REF:tools/foundry_catalog_read_http.py" > "$VENDOR_DIR/foundry_catalog_read_http.py"
python3 -m py_compile "$VENDOR_DIR"/*.py
