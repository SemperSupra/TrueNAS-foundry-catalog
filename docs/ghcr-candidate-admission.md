# GHCR unpromoted candidate read-only admission

Governance: TrueNAS-foundry-catalog-private #1; Foundry private #328/#329/#330. Physical TrueNAS APPLY HOLD (#291).

The candidate has passed offline SBOM/provenance structural inspection. **No published GHCR digest exists.** A local image ID or OCI index is not a GHCR registry identity. The registry verifier accepts only an immutable ghcr.io/sempersupra/truenas-foundry-catalog@sha256 reference and performs read-only Buildx imagetools inspection. Registry bytes, image platform and descriptor-level attestation binding are checked. An image-index structural PASS is not verification of in-toto payload, registry-bound signed provenance, trusted issuer, vulnerabilities, license obligations or TrueNAS runtime.

Before creating a publishing workflow requiring packages:write, independently admit its identity, org/package permissions and unpromoted candidate publication authority in the DLE. Then verify the registry digest, subject-bound attestation content/signatures, exact source/base/actor provenance; consume the accepted image via the existing generic Foundry binder and strict host resource policy; request an independently admitted Agent Dispatch #396/#480 disposable 25.04.2.6 capsule. No second installer, scheduler, controller, Docker socket, physical host mutation or release promotion.
