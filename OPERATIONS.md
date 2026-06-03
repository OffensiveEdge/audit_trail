# Operations

This document describes the operational posture supporting the integrity claims in this repository: where data lives, who can write to it, what backups exist, and what happens if infrastructure is lost. The goal is to make commitments here that a customer's diligence questionnaire can verify against, and to be transparent about the gaps that exist at EdgeSeeker's current operating stage.

## Hosting

- **Application + scheduler**: a single Hetzner Cloud server in Helsinki, Finland (`5.78.208.0`). All PM2 processes (predictions API, scoring, training, analysis, inference, the morning generation job, and the audit anchor publisher) run here. Reverse-proxied via Caddy. Tailnet-gated for all internal endpoints.
- **Database**: Supabase Cloud (Postgres + Storage). All audit ledgers (`audit_trail`, `audit_anchors`, `audit_models`) and the private `models/` Storage bucket are hosted here. (Per-day anchor salts are stored as the `salt` column on `audit_anchors`, not a separate table.)
- **Source control**: self-hosted Gitea on the same Hetzner server (private; `gitea.offensiveedge.com`, tailnet only).
- **Public anchor repository**: `github.com/OffensiveEdge/audit_trail` (public).
- **Scheduler**: n8n in a Docker container on the Hetzner server. Runs the morning generation trigger (08:00 ET) and the audit anchor publisher (09:00 ET).

## Who can write to integrity-critical tables

The ledger tables (`audit_trail`, `audit_anchors`, `audit_models`) are protected by Postgres `BEFORE UPDATE` and `BEFORE DELETE` triggers that raise on any attempt to mutate or delete rows. Only INSERTs are permitted. RLS policies further restrict access to the `service_role` only.

The `service_role` Supabase key is currently held by:

- The Hetzner server (used by the predictions service at write time and the audit anchor publisher at commit time).
- The single operator (founder) for administrative purposes.

This is a single-operator setup. EdgeSeeker discloses this rather than hide it: the operator can in theory disable the immutability triggers, write rows, and re-enable triggers without external evidence. Mitigations:

- Triggers themselves live in DDL that is version-controlled (`service/server/supabase/schema/`) and any change to them appears in git history.
- The daily anchor pushed to GitHub commits the *content* of the audit ledger; any retroactive insertion after a daily anchor that does not match would fail Mode A verification.
- An external third-party audit of the operator's access logs is planned (see "Roadmap").

## Backups

- **Supabase**: Supabase Cloud manages automatic daily backups of the Postgres database including all audit ledgers. Backup retention follows the Supabase plan in use.
- **Audit anchor salts**: the per-day salts live as the `salt` column on the `audit_anchors` table, so they are covered by the same Supabase daily database backups as the other ledgers (above) — there is no separate salt-table export. Without the salts, past manifest hashes cannot be reproduced — losing them does not invalidate past commitments, but it prevents EdgeSeeker from helping a customer verify a past anchor; the Supabase backups mitigate that risk.
- **Model artifacts**: the private `models/` Supabase Storage bucket is the source of truth. Originals on the Hetzner server in `service/aiml/models/` are a hot cache; the Supabase copy is the durable one.
- **Code**: replicated across Gitea on Hetzner and individual developer laptops. The `audit_trail` repository is mirrored at GitHub.

## Recovery objectives

- **Recovery Time Objective (RTO)**: 24 hours to resume morning generation on a new server if Hetzner is lost. The recovery procedure is the existing `setup.sh` plus restoring the Supabase service-role key from offline storage.
- **Recovery Point Objective (RPO)**: zero for the audit ledgers (Supabase Cloud handles continuous replication). Up to 24 hours for operational tables that depend on n8n backups.
- **Public repository**: the GitHub anchor repository is itself durable independent of EdgeSeeker. If EdgeSeeker disappears, all past anchors and their commit timestamps remain verifiable as long as the repository remains accessible. Past predictions can still be verified by anyone with the predictions and salt for the relevant date.

## Key custody

| Key / credential | Holder | Storage | Notes |
|---|---|---|---|
| Supabase `service_role` key | Operator | `.env` files (Hetzner + laptop), 1Password vault | Rotate quarterly |
| GitHub deploy key (audit_trail) | Hetzner box | `~/.ssh/audit_trail_deploy` | Read-write to one repo only |
| Per-day anchor salts | Supabase `audit_anchors.salt` column | Service-role only; covered by Supabase daily backups | Treat backups like keys |
| n8n API key | Hetzner | `service/server/.env` | Used only for n8n workflow management |
| `OPS_BACKUPS_TOKEN` | Hetzner | `.env` files | Shared between services + n8n |

Key rotation is a manual procedure today. Automated rotation is on the roadmap.

## Audit trail of operator actions

A complete audit trail of operator actions (SSH sessions on Hetzner, queries against the Supabase service role, n8n workflow changes) is not currently captured externally. This is a known gap. Today's mitigations:

- All Hetzner SSH access is gated through Tailscale, which logs connection events centrally.
- All Caddy access logs are retained on the Hetzner server.
- All n8n executions are logged in the n8n SQLite database (backed up nightly).
- All code changes are in git, signed off in Gitea.
- All Supabase migrations are listed via the Supabase migration API.

Operator-action immutable audit logging external to EdgeSeeker is on the roadmap.

## Roadmap

- Operator-action immutable audit logging external to EdgeSeeker (planned: a small cloud-hosted append-only log of significant administrative actions, anchored to the same daily manifest hash).
- Automated key rotation across all integrity-critical credentials.
- Quarterly third-party audit of the audit ledger chain, contracted at appropriate revenue scale.
- Multi-region failover for the predictions API and audit anchor publisher (currently single-region).

## Contact

For operational questions related to integrity or to report a potential incident, contact EdgeSeeker.
