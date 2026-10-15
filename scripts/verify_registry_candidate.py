#!/usr/bin/env python3
"""Fail-closed, read-only GHCR registry index qualifier; no publish or release."""
import argparse
import hashlib
import json
import re
import subprocess
import sys

REF = re.compile(r"ghcr[.]io/sempersupra/truenas-foundry-catalog@sha256:([a-f0-9]{64})")
DIGEST = re.compile(r"sha256:[a-f0-9]{64}")
INDEX_TYPES = {"application/vnd.oci.image.index.v1+json",
               "application/vnd.docker.distribution.manifest.list.v2+json"}
MANIFEST_TYPES = {"application/vnd.oci.image.manifest.v1+json",
                  "application/vnd.docker.distribution.manifest.v2+json"}

class AdmissionError(ValueError):
    pass

def reject_duplicate_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise AdmissionError("duplicate JSON key in OCI index")
        out[key] = value
    return out

def verify(reference, raw):
    match = REF.fullmatch(reference)
    if not match:
        raise AdmissionError("require exact lowercase GHCR product @sha256 reference")
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 2_000_000:
        raise AdmissionError("registry manifest size invalid")
    actual = hashlib.sha256(raw).hexdigest()
    if actual != match.group(1):
        raise AdmissionError("registry index digest mismatch")
    try:
        index = json.loads(raw, object_pairs_hook=reject_duplicate_pairs)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AdmissionError("malformed registry index") from exc
    if not isinstance(index, dict) or index.get("schemaVersion") != 2 or index.get("mediaType") not in INDEX_TYPES:
        raise AdmissionError("expected OCI/Docker image index")
    manifests = index.get("manifests")
    if not isinstance(manifests, list) or not 2 <= len(manifests) <= 10:
        raise AdmissionError("unexpected index descriptor count")
    images, attestations = [], []
    for item in manifests:
        if not isinstance(item, dict) or item.get("mediaType") not in MANIFEST_TYPES:
            raise AdmissionError("unsupported OCI index entry")
        if not isinstance(item.get("digest"), str) or not DIGEST.fullmatch(item["digest"]):
            raise AdmissionError("invalid manifest digest")
        if type(item.get("size")) is not int or not 0 < item["size"] < 100_000_000:
            raise AdmissionError("invalid descriptor size")
        platform, annotations = item.get("platform") or {}, item.get("annotations") or {}
        if not isinstance(platform, dict) or not isinstance(annotations, dict):
            raise AdmissionError("invalid platform/annotations")
        if platform.get("os") == "linux" and platform.get("architecture") == "amd64":
            images.append(item)
        elif annotations.get("vnd.docker.reference.type") == "attestation-manifest":
            if platform.get("os") not in (None, "unknown"):
                raise AdmissionError("attestation platform invalid")
            attestations.append(item)
        else:
            raise AdmissionError("unexpected image or attestation entry")
    if len(images) != 1 or not attestations:
        raise AdmissionError("expected exactly one amd64 image and attestation")
    image_digest = images[0]["digest"]
    if len({a["digest"] for a in attestations}) != len(attestations):
        raise AdmissionError("duplicate attestation descriptor")
    if any(a["annotations"].get("vnd.docker.reference.digest") != image_digest for a in attestations):
        raise AdmissionError("attestation points at another image")
    return {
        "schema": "truenas-foundry-catalog-ghcr-readonly/v1",
        "status": "REGISTRY_INDEX_STRUCTURE_PASS_NOT_RELEASE",
        "registry_reference": reference,
        "registry_index_digest": "sha256:" + actual,
        "amd64_manifest_digest": image_digest,
        "attestation_manifest_digests": [a["digest"] for a in attestations],
        "attestation_contents_verified": False,
        "signed_provenance_verified": False,
        "native_truenas_qualified": False,
        "registry_mutation_performed": False,
        "physical_apply": "HOLD",
    }

def inspect(reference):
    if not REF.fullmatch(reference):
        raise AdmissionError("exact product GHCR @sha256 reference required")
    try:
        process = subprocess.run(
            ["docker", "buildx", "imagetools", "inspect", "--raw", reference],
            capture_output=True, timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AdmissionError("registry inspector unavailable") from exc
    if process.returncode:
        raise AdmissionError("read-only registry inspection denied or unavailable")
    return verify(reference, process.stdout)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(inspect(args.image), sort_keys=True, indent=2))
        return 0
    except AdmissionError as exc:
        print(json.dumps({"status": "BLOCKED", "reason": str(exc), "physical_apply": "HOLD"}), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
