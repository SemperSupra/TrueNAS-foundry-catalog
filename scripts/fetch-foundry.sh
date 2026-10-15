#!/bin/sh
# Acquire two exact-commit, content-hash pinned Foundry source files, no Git or apt.
set -eu
: "${FOUNDRY_REF:?FOUNDRY_REF must be the reviewed immutable Git commit}"
case "$FOUNDRY_REF" in *[!a-f0-9]*|'') echo 'invalid source commit' >&2; exit 2 ;; esac
[ "${#FOUNDRY_REF}" -eq 40 ] || { echo 'source commit must be 40 lowercase hex' >&2; exit 2; }
VENDOR_DIR=${VENDOR_DIR:-/app/vendor}
export FOUNDRY_REF VENDOR_DIR
python3 - <<'PY'
import hashlib, os, pathlib, urllib.parse, urllib.request
ref=os.environ["FOUNDRY_REF"]
destination=pathlib.Path(os.environ["VENDOR_DIR"])
expected={
    "foundry_catalog_federation.py":"cd6a1bb4a90e3edb76988a1aed8f2a07e82480c4b8cd1b467ea5ea241a2cabc5",
    "foundry_catalog_read_http.py":"002bee37818faab404a39537c15b52ce3e42207c7e4582b11ef29445c8367923",
}
destination.mkdir(parents=True,exist_ok=True)
for name, sha in expected.items():
    url=f"https://raw.githubusercontent.com/SemperSupra/truenas-app-foundry/{ref}/tools/{name}"
    request=urllib.request.Request(url,headers={"User-Agent":"FoundryCatalogExactSource/1"})
    with urllib.request.urlopen(request,timeout=30) as response:
        if urllib.parse.urlsplit(response.geturl()).hostname!="raw.githubusercontent.com":
            raise ValueError("source redirect host drift")
        payload=response.read(2_000_001)
    if not payload or len(payload)>2_000_000 or hashlib.sha256(payload).hexdigest()!=sha:
        raise ValueError("source content SHA-256 mismatch for "+name)
    target=destination/name
    if target.is_symlink():
        raise ValueError("source destination must not be a symlink")
    target.write_bytes(payload)
    target.chmod(0o644)
    print(f"Verified {name}: sha256:{sha}")
PY
python3 -m py_compile "$VENDOR_DIR"/*.py
