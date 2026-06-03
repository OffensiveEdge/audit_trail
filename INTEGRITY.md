# Integrity & Change-Control Policy

This repository is the public commitment ledger for EdgeSeeker predictions. Its
entire value is that it is **tamper-evident and append-only** — anyone can
verify that published commitments were never altered after the fact. These
rules, and the mechanisms that enforce them, exist to keep that guarantee true.

## Invariants

1. **The ledger is append-only.** Files under `anchors/` and `models/`, once
   committed, are **never modified, renamed, or deleted.** New dates and new
   model registrations are added; existing ones are immutable.
2. **OpenTimestamps proofs are extend-only.** An `anchors/*.ots` file may be
   *upgraded* in place (pending calendar attestation → confirmed Bitcoin
   attestation). It is **never deleted or renamed.**
3. **History is never rewritten.** No force-push, no rebasing of `main`, no
   history deletion. `main` is linear and protected.
4. **`verify.py` is anchored.** Its sha256 is committed into every daily
   manifest, so changing it **forks the verifier going forward and never alters
   the validity of past anchors** — a historical anchor is always verified
   against the `verify.py` it was published with. A change to `verify.py` is
   therefore a deliberate, reviewed event, not a casual edit.
5. **Superseded methodology is retained.** Archived versions under
   `methodology/` are append-only.

## How these are enforced (defense in depth)

- **Cryptographic.** Each anchor commits to a salted manifest hash and to
  `verify.py`'s own hash; every prediction's `content_hash` binds each field.
  Altering any input breaks the published hash.
- **Upstream database.** The source `audit_trail` table is written only by the
  prediction pipeline and has triggers rejecting `UPDATE`/`DELETE`.
- **CI — `.github/workflows/integrity.yml`.** Every push and pull request runs
  an append-only guard that **fails the build** if any published
  `anchors/`/`models/` file is modified, renamed, or deleted, or if any `.ots`
  proof is removed.
- **Branch protection + `CODEOWNERS`.** `main` forbids force-push and history
  rewrites; changes to `verify.py`, `anchors/`, `models/`, and this policy
  require code-owner review.

## For automated contributors (AI agents)

If you are an AI coding agent operating in this repository, treat the invariants
above as hard constraints. **Never** modify or delete anything under `anchors/`
or `models/`, **never** rewrite git history or force-push, and **never** edit
`verify.py` except as an explicitly requested, reviewed verifier change. When in
doubt, stop and ask a human. The CI guard will fail the build if these are
violated — do not attempt to work around it.
