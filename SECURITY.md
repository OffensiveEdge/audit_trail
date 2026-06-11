# Security Policy

This repository is a public, tamper-evident commitment ledger and its
independent verifier. We take reports about its integrity seriously.

## What we want to hear about

- A flaw in `verify.py` (any subcommand: `anchor`, `content`, `bitcoin`) — e.g.
  a way to make verification **pass** for predictions that were never committed,
  or **fail** for ones that were.
- A weakness in the anchoring / manifest protocol (see `METHODOLOGY.md`) — for
  example, a way to forge or alter a `manifest_hash`, `content_hash`, or
  `verifier_sha256` binding.
- A way to bypass the append-only integrity guard
  (`.github/workflows/integrity.yml`).
- A suspected integrity problem with a published anchor, model registration, or
  `.ots` proof.

## How to report

Email **security@offensiveedge.com** with details and, where possible, a
reproduction. **Please do not open a public issue** for a suspected
vulnerability until we have had a chance to respond.

We aim to acknowledge within **3 business days**. Confirmed integrity incidents
are then disclosed publicly under the policy in
[`incidents/README.md`](incidents/README.md) (7-day window, append-only, no
silent edits).

## Scope

**In scope** — the public surface of this repository:
- `verify.py` (subcommands: `anchor`, `content`, `bitcoin`)
- the manifest / anchor protocol and methodology
- the integrity CI guard
- the published ledger artifacts (`anchors/`, `models/`, `reports/`, `.ots` proofs)

**Out of scope** — EdgeSeeker's private prediction pipeline and infrastructure.
The predictions, salts, and model binaries are **not** in this repository
(see [`OPERATIONS.md`](OPERATIONS.md)); issues there are not part of this public
repo's attack surface.

## What does not qualify

- "The model was wrong about a game." That is performance, not a vulnerability —
  see the performance reports and `incidents/README.md` → *"What does not
  qualify as an incident."*
- Verification failing because you altered a tracked file locally (including a
  line-ending rewrite — see `.gitattributes`). That is the verifier working as
  intended.
