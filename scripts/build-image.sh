#!/bin/sh
set -eu
: "${PYTHON_IMAGE:?PYTHON_IMAGE must be a reviewed digest-pinned Python image}"
: "${OUTPUT_IMAGE:?OUTPUT_IMAGE must specify an output image reference}"
case "$PYTHON_IMAGE" in
  *@sha256:*) digest=${PYTHON_IMAGE##*@sha256:} ;;
  *) echo 'Python base image must be an OCI digest reference' >&2; exit 2 ;;
esac
printf '%s' "$digest" | grep -Eq '^[a-f0-9]{64}$' || { echo 'base digest must be 64 lowercase hex characters' >&2; exit 2; }
case "$OUTPUT_IMAGE" in
  *' '*|'') echo 'invalid output image' >&2; exit 2 ;;
esac
FOUNDRY_REF=4efc55a2d0069bd4a4a0b7fcbb4eec8c7e091825
[ "${1:-}" = '--verify-only' ] && { echo 'build inputs structurally admitted; no build executed'; exit 0; }
command -v docker >/dev/null 2>&1 || { echo 'Docker/buildx required on a separate build actor' >&2; exit 2; }
docker buildx build --pull --build-arg "PYTHON_IMAGE=$PYTHON_IMAGE" \
  --build-arg "FOUNDRY_REF=$FOUNDRY_REF" --tag "$OUTPUT_IMAGE" --metadata-file build-metadata.json .
echo 'Do not deploy the output tag. Verify and use the pushed OCI digest from build metadata.'
