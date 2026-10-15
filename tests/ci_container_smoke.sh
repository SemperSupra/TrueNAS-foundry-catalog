#!/bin/sh
# One disposable, local-only candidate-container smoke test on GitHub Actions.
set -eu
IMAGE="${1:?candidate image required}"
TMP="$(mktemp -d)"
NAME="foundry-catalog-rdte-$$"
cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT HUP INT TERM
mkdir -p "$TMP/indexes" "$TMP/secrets"
chmod 755 "$TMP" "$TMP/indexes" "$TMP/secrets"
cat > "$TMP/indexes/foundry.json" <<'JSON'
{
  "schema": "truenas-foundry-catalog-source/v0",
  "publisher": "rdte.example",
  "source": "offline",
  "uri": "https://example.org/catalog.git",
  "revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "apps": [
    {
      "train": "community",
      "name": "catalog-probe",
      "version": "1.0.0",
      "path": "ix-dev/community/catalog-probe",
      "source_tree_sha256": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    }
  ]
}
JSON
TOKEN="$(openssl rand -hex 32)"
printf '%s\n' "$TOKEN" > "$TMP/secrets/catalog-token"
openssl req -new -x509 -nodes -newkey rsa:2048 -days 1 \
  -keyout "$TMP/secrets/tls.key" -out "$TMP/secrets/tls.crt" -subj "/CN=localhost" \
  >/dev/null 2>&1
chmod 0400 "$TMP/secrets/catalog-token" "$TMP/secrets/tls.key"
chmod 0444 "$TMP/secrets/tls.crt" "$TMP/indexes/foundry.json"
sudo chown 65532:65532 "$TMP/secrets/catalog-token" "$TMP/secrets/tls.key"
docker run -d --name "$NAME" --read-only --cap-drop=ALL \
  --security-opt no-new-privileges --user 65532:65532 \
  -p 127.0.0.1:38443:8443 \
  --mount "type=bind,source=$TMP/indexes,target=/data/indexes,readonly" \
  --mount "type=bind,source=$TMP/secrets/catalog-token,target=/run/secrets/catalog-token,readonly" \
  --mount "type=bind,source=$TMP/secrets/tls.crt,target=/run/secrets/tls.crt,readonly" \
  --mount "type=bind,source=$TMP/secrets/tls.key,target=/run/secrets/tls.key,readonly" \
  "$IMAGE" >/dev/null
ready=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  if curl -kfsS --max-time 2 https://127.0.0.1:38443/healthz -o "$TMP/health.json" 2>/dev/null; then ready=1;break;fi
  sleep 1
done
if [ "$ready" -ne 1 ]; then
  docker logs "$NAME" || true
  echo "FAIL: isolated HTTPS service did not become ready" >&2
  exit 1
fi
python3 -c 'import json,sys;h=json.load(open(sys.argv[1]));assert h["mode"]=="READ_ONLY"' "$TMP/health.json"
UNAUTHORIZED="$(curl -sk --max-time 3 -o "$TMP/denied.json" -w '%{http_code}' https://127.0.0.1:38443/v0/catalog/apps)"
[ "$UNAUTHORIZED" = 401 ] || { echo "FAIL: unauthenticated catalog access" >&2; exit 1; }
curl -kfsS --max-time 3 -H "Authorization: Bearer $TOKEN" \
  https://127.0.0.1:38443/v0/catalog/apps -o "$TMP/list.json"
python3 -c 'import json,sys;j=json.load(open(sys.argv[1]));assert j["count"]==1;assert j["apps"][0]["admission"]=="DISCOVERED_ONLY"' "$TMP/list.json"
REFUSED="$(curl -sk --max-time 3 -X POST -H "Authorization: Bearer $TOKEN" -o "$TMP/write.json" -w '%{http_code}' https://127.0.0.1:38443/v0/catalog/apps)"
[ "$REFUSED" = 405 ] || { echo "FAIL: mutation endpoint accepted" >&2; exit 1; }
echo "PASS: isolated digest-input OCI candidate ran TLS, 401/200 read-only discovery and 405 mutation refusal."
