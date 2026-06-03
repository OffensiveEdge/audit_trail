# Agent guide

This repository is an **immutable, append-only public commitment ledger.**
Before making any change, read [`INTEGRITY.md`](./INTEGRITY.md) and obey it.

Hard constraints — the CI integrity guard enforces these and will fail the build:

- **Never** modify, rename, or delete any file under `anchors/` or `models/`. They are append-only.
- **Never** delete an `anchors/*.ots` proof — it may only be upgraded in place.
- **Never** rewrite git history or force-push `main`.
- **Never** edit `verify.py` except as an explicitly requested, reviewed verifier change — its sha256 is anchored into every manifest.

When in doubt, stop and ask a human.
