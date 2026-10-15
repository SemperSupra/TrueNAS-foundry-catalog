"""Adversarial offline controls for the no-write GHCR digest reader."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("ghcr_verify", ROOT/"scripts/verify_registry_candidate.py")
assert spec and spec.loader
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
IMAGE={"mediaType":"application/vnd.oci.image.manifest.v1+json",
       "digest":"sha256:"+"a"*64,"size":1000,
       "platform":{"os":"linux","architecture":"amd64"}}
ATT={"mediaType":"application/vnd.oci.image.manifest.v1+json",
     "digest":"sha256:"+"b"*64,"size":1200,
     "platform":{"os":"unknown","architecture":"unknown"},
     "annotations":{"vnd.docker.reference.type":"attestation-manifest",
                    "vnd.docker.reference.digest":IMAGE["digest"]}}

def fixture(doc=None):
    if doc is None:
        doc={"schemaVersion":2,"mediaType":"application/vnd.oci.image.index.v1+json",
             "manifests":[copy.deepcopy(IMAGE),copy.deepcopy(ATT)]}
    raw=json.dumps(doc,sort_keys=True,separators=(",",":")).encode()
    ref="ghcr.io/sempersupra/truenas-foundry-catalog@sha256:"+hashlib.sha256(raw).hexdigest()
    return ref,raw,doc

class GhcrReadOnlyTests(unittest.TestCase):
    def test_positive_structure_is_not_release(self):
        ref,raw,_=fixture()
        out=v.verify(ref,raw)
        self.assertEqual(out["status"],"REGISTRY_INDEX_STRUCTURE_PASS_NOT_RELEASE")
        self.assertFalse(out["signed_provenance_verified"])
        self.assertFalse(out["attestation_contents_verified"])
        self.assertEqual(out["physical_apply"],"HOLD")

    def test_ref_scope_and_mutable_tag_denied(self):
        ref,raw,_=fixture()
        for bad in [ref.split("@")[0]+":latest",ref.replace("ghcr.io","docker.io"),
                    ref.replace("sempersupra","attacker"),ref.replace("catalog","other"),
                    ref.upper(),ref+"/extra"]:
            with self.subTest(ref=bad),self.assertRaises(v.AdmissionError):
                v.verify(bad,raw)

    def test_changed_digest_denied(self):
        ref,raw,_=fixture()
        with self.assertRaises(v.AdmissionError):
            v.verify(ref[:-1]+("0" if ref[-1]!="0" else "1"),raw)

    def test_wrong_attestation_binding_denied(self):
        _,_,doc=fixture()
        doc["manifests"][1]["annotations"]["vnd.docker.reference.digest"]="sha256:"+"f"*64
        with self.assertRaises(v.AdmissionError):
            v.verify(*fixture(doc)[:2])

    def test_no_attestation_and_duplicate_attestation_denied(self):
        _,_,doc=fixture()
        doc["manifests"].pop()
        with self.assertRaises(v.AdmissionError):
            v.verify(*fixture(doc)[:2])
        _,_,doc=fixture()
        doc["manifests"].append(copy.deepcopy(ATT))
        with self.assertRaises(v.AdmissionError):
            v.verify(*fixture(doc)[:2])

    def test_foreign_platform_and_nested_index_denied(self):
        _,_,doc=fixture()
        doc["manifests"][0]["platform"]["architecture"]="arm64"
        with self.assertRaises(v.AdmissionError):
            v.verify(*fixture(doc)[:2])
        _,_,doc=fixture()
        doc["manifests"][0]["mediaType"]="application/vnd.oci.image.index.v1+json"
        with self.assertRaises(v.AdmissionError):
            v.verify(*fixture(doc)[:2])

    def test_garbage_and_oversized_denied(self):
        ref,_,_=fixture()
        for raw in [b"garbage",b"",b"!"*2_000_001]:
            with self.subTest(size=len(raw)),self.assertRaises(v.AdmissionError):
                v.verify(ref,raw)

    def test_duplicate_json_keys_rejected(self):
        raw=b'{"schemaVersion":2,"schemaVersion":2,"mediaType":"application/vnd.oci.image.index.v1+json","manifests":[]}'
        ref="ghcr.io/sempersupra/truenas-foundry-catalog@sha256:"+hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(v.AdmissionError, "duplicate JSON"):
            v.verify(ref,raw)

    def test_no_publish_or_login(self):
        text=(ROOT/"scripts/verify_registry_candidate.py").read_text()
        self.assertIn('"imagetools", "inspect", "--raw"',text)
        self.assertNotIn('"push"',text)
        self.assertNotIn('"login"',text)

if __name__=="__main__":
    unittest.main()
