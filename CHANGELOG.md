# audit_trail changelog

Tooling and protocol changes only. Day-to-day anchors and reports are recorded as their own commits in `anchors/` and `reports/` — that history is the ledger, not this file.

This file tracks changes that affect verification: the `verify.py` CLI surface, the canonical hash protocol, manifest shape, and methodology revisions.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

_Staged for the `v1.0.0` tag — the first locked release. Convert this heading to `## [1.0.0] - YYYY-MM-DD` when the tag is cut._

### Verification
- `verify.py` — pure-stdlib verifier (Python 3.8+, zero dependencies). Mode A (anchor: predictions + salt → published `manifest_hash`) and Mode B (content: per-row `content_hash`). Self-hashing: refuses to verify an anchor published against a different `verify.py` (`verifier_sha256`).
- `verify_bitcoin.py` — supplemental, optional Bitcoin-attestation check through the OpenTimestamps reference client (`opentimestamps-client==0.7.2`, pinned in `requirements-bitcoin.txt`). Trustless verification requires a local Bitcoin Core node; `--offline` / `--digests` work without one.

### Protocol
- Manifest schema **v3**: salted SHA-256 over `{predictions, new_models, verifier_sha256}`. Reports are committed and GitHub-commit-timestamped but **not** folded into the manifest hash.
- Per-prediction `content_hash` over the fixed prediction-field set (documented in `verify.py` / `METHODOLOGY.md`).
- Model registrations carry a Merkle-style `artifact_sha256` (of file contents, not the tarball).

### Integrity & operations
- `INTEGRITY.md` change-control policy; append-only CI guard (`.github/workflows/integrity.yml`) that fails on any modify/delete of published `anchors/` / `models/` or removal of an `.ots` proof; branch protection (no force-push/deletion); agent guardrails (`AGENTS.md`, `CLAUDE.md`, `.cursor/`).
- `OPERATIONS.md` (hosting, custody, backups, RTO/RPO, disclosed gaps), `incidents/` disclosure policy, `sample/` runnable fixture.

### Supply chain
- The sole external dependency (`ots`) is pinned; CI runner pinned to `ubuntu-24.04` and `actions/checkout` pinned to an immutable commit SHA.
