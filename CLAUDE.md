# Claude / agent instructions

This is an **immutable public commitment ledger.** The full policy is in
[`INTEGRITY.md`](./INTEGRITY.md) — read it before editing anything.

Non-negotiable (enforced by CI — the build fails on violation):

- **Never** modify, rename, or delete files under `anchors/` or `models/` (append-only).
- **Never** delete an `anchors/*.ots` proof (upgrade-in-place only).
- **Never** rewrite history or force-push `main`.
- **Never** edit `verify.py` unless explicitly asked for a reviewed verifier change — it is anchored into every manifest.

If a task seems to require any of the above, stop and confirm with a human first.
