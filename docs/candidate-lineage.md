# CP3 source candidate provenance and release boundary

- Origin: `foundry-catalog-product-candidate-20261014.zip` generated in the preceding Foundry Catalog session.
- Original ZIP SHA-256: `1d7c1c2f6540c89ae070f04b631c2300f2cf72497d77d06792464176b29468a1`. The original archive passed its embedded checksums at import review.
- This Git branch is the **reviewed product-source import**, not a byte-for-byte claim for every file in the original ZIP: documentation, tests and the repository name were normalized during staging. Git commit identities, rather than the seed ZIP digest, are authoritative for all future CI and image provenance.
- Generic Foundry read engine and gateway must be drawn from the exact Git commit `SemperSupra/truenas-app-foundry@4efc55a2d0069bd4a4a0b7fcbb4eec8c7e091825` via `scripts/fetch-foundry.sh`; never from floating `main`.
- Product repository: `SemperSupra/TrueNAS-foundry-catalog` (public); qualification DLE: `SemperSupra/TrueNAS-foundry-catalog-private` (private).
- Upstream DLE: [Foundry private #328](https://github.com/SemperSupra/truenas-app-foundry-private/issues/328), [challenge #329](https://github.com/SemperSupra/truenas-app-foundry-private/issues/329), [repository provisioning #330](https://github.com/SemperSupra/truenas-app-foundry-private/issues/330).
- **Security:** No private credentials, TLS keys or target site state are included. Product HTTP is read-only; every discovery item remains `DISCOVERED_ONLY`.
- **Not proven by committing this source:** published image digest, correct OCI base image, SBOM/signature/provenance, native TrueNAS 25.04.2.6 bootstrap, real portal, restart/rollback recovery, independent red team or physical deployment.
- Site-specific Compose is a **template containing intentionally invalid placeholders**; do not apply. It must be bound by the existing Foundry site binder under independent authority.
- Physical mutation remains HOLD under [Foundry private #291](https://github.com/SemperSupra/truenas-app-foundry-private/issues/291).

Next critical evidence: product CI that fetches pinned actual Foundry modules, then a deterministic OCI image build on a disposable GHA runner with a verified base digest. Hold release until the image has an immutable registry digest and its own native TrueNAS disposable installation/recovery receipt.
