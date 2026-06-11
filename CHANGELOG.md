# audit_trail changelog

Tooling and protocol changes only. Day-to-day anchors and reports are recorded as their own commits in `anchors/` and `reports/` — that history is the ledger, not this file.

This file tracks changes that affect verification: the `verify.py` CLI surface, the canonical hash protocol, manifest shape, and methodology revisions.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

_Staged for the `v1.0.0` tag — the first locked release. Convert this heading to `## [1.0.0] - YYYY-MM-DD` when the tag is cut._

### Verification
- `verify.py` — unified verifier (Python 3.8+; pure stdlib for Modes A/B). Three subcommands: `anchor` (Mode A: predictions + salt → published `manifest_hash`), `content` (Mode B: per-row `content_hash`), and `bitcoin` (Mode C: OpenTimestamps + Bitcoin attestation). Self-hashing: refuses to verify an anchor published against a different `verify.py` (`verifier_sha256`).
- The pre-v1.0 standalone `verify_bitcoin.py` was folded into `verify.py bitcoin` for v1.0 — one verifier, one `verifier_sha256`, one CLI surface. The pre-v1.0 file remains in git history for verifying pre-v1.0 anchors: `git checkout <pre-v1.0-commit> -- verify_bitcoin.py`.
- The `bitcoin` subcommand requires the OpenTimestamps reference client (`opentimestamps-client==0.7.2`, pinned in `requirements-bitcoin.txt`) only when invoked. Modes A/B don't need it. Trustless Bitcoin verification still requires a local Bitcoin Core node; `--offline` / `--digests` work without one.
- Schema-version dispatch table inside `verify.py`. Future protocol bumps that share the canonical hashed payload register a new schema version against the existing handler — no new verifier file, no `verifier_sha256` transition.

### Protocol
- Manifest schema **v3**: salted SHA-256 over `{predictions, new_models, verifier_sha256}`. Reports are committed and GitHub-commit-timestamped but **not** folded into the manifest hash.
- Manifest schema **v4**: bumps schema version on the public anchor file to surface the `conformal_coverage_policy` in force on the anchor date — per-(sport, season_type) coverage targets, structured for verifier consumption. The canonical manifest hash itself is unchanged from v3 (still `{predictions, new_models, verifier_sha256}`); the policy block is human-readable disclosure. Per-row `conformal_coverage_target` joins the existing prediction-field set so each `content_hash` commits to the value actually applied at decision time.
- Per-prediction `content_hash` over the fixed prediction-field set (documented in `verify.py` / `METHODOLOGY.md`). Field set extended with `conformal_coverage_target` for predictions from 2026-06-11 forward.
- Model registrations carry a Merkle-style `artifact_sha256` (of file contents, not the tarball).

### Integrity & operations
- `INTEGRITY.md` change-control policy; append-only CI guard (`.github/workflows/integrity.yml`) that fails on any modify/delete of published `anchors/` / `models/` or removal of an `.ots` proof; branch protection (no force-push/deletion); agent guardrails (`AGENTS.md`, `CLAUDE.md`, `.cursor/`).
- `OPERATIONS.md` (hosting, custody, backups, RTO/RPO, disclosed gaps), `incidents/` disclosure policy, `sample/` runnable fixture.

### Supply chain
- The sole external dependency (`ots`) is pinned; CI runner pinned to `ubuntu-24.04` and `actions/checkout` pinned to an immutable commit SHA.
