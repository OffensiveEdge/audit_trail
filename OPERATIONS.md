# Operations

This document describes the operational posture supporting the integrity claims in this repository: where data lives, who can write to it, what backups exist, and what happens if infrastructure is lost. The goal is to make commitments here that a customer's diligence questionnaire can verify against, and to be transparent about the gaps that exist at EdgeSeeker's current operating stage. Vendor and infrastructure specifics are kept out of public documentation by policy; they are available under NDA during enterprise diligence.

## Operating posture

EdgeSeeker is currently a **single-operator system**. Recovery actions, late anchors, schema fixes, and other catch-up operations are visible in the commit history of this repository — the GitHub commit timestamp on each `anchors/<date>.json` is the durable, third-party-attested record of when each anchor actually landed. The commit log is the standing disclosure surface; material deviations get their own file under `incidents/`.

**A material deviation that triggers an `incidents/` file is any of:**

- An anchor lands more than 24 hours after its sports day.
- An already-committed anchor file is modified (vs. only being added later than intended).
- An audited row's `recorded_at` is altered, or any row's `content_hash` changes after its original commit.
- A verifier mode (A or B) would fail against a published anchor.

Everything else — same-day catch-ups, in-day re-runs after a fixable bug, scheduled cadence shifts under 24h — is covered by the commit history itself and does not require a separate `incidents/` entry. This explicit threshold exists so the disclosure surface stays meaningful at the current single-operator stage; expectations will tighten as automation and redundancy come online (see "Roadmap").

## Hosting

- **Application + scheduler**: a single primary server runs all prediction, scoring, training, analysis, inference, morning-generation, and audit-anchor processes. Internal endpoints are not publicly reachable.
- **Database**: a managed Postgres + object-storage provider hosts all audit ledgers (`audit_trail`, `audit_anchors`, `audit_models`) and the private model-artifact bucket. Per-day anchor salts are stored as the `salt` column on `audit_anchors`, not a separate table.
- **Public anchor repository**: `github.com/OffensiveEdge/audit_trail` (public).
- **Scheduler**: an internal scheduler runs the morning generation trigger and the audit anchor publisher daily. The intended cadence is one anchor per sports day; the GitHub commit timestamp on each `anchors/<date>.json` is the source of truth — every Mode A/B verification dates against that commit, not against a named hour.

## Who can write to integrity-critical tables

The ledger tables (`audit_trail`, `audit_anchors`, `audit_models`) are protected by Postgres `BEFORE UPDATE` and `BEFORE DELETE` triggers that raise on any attempt to mutate or delete rows. Only INSERTs are permitted. Row-level-security policies further restrict access to the service-role credential only.

The service-role credential is currently held by:

- The primary server (used by the predictions service at write time and the audit anchor publisher at commit time).
- The single operator (founder) for administrative purposes.

This is a single-operator setup. EdgeSeeker discloses this rather than hide it: the operator can in theory disable the immutability triggers, write rows, and re-enable triggers without external evidence. Mitigations:

- Triggers themselves live in DDL that is version-controlled, and any change to them appears in git history.
- The daily anchor pushed to GitHub commits the *content* of the audit ledger; any retroactive insertion that does not match a previously committed manifest would fail Mode A verification.
- An external third-party audit of the operator's access logs is planned (see "Roadmap").

## Backups

- **Database**: the managed Postgres provider performs automatic daily backups of all audit ledgers. Retention follows the provider's standard plan.
- **Audit anchor salts**: the per-day salts live as the `salt` column on the `audit_anchors` table and are covered by the same daily database backups — there is no separate salt-table export. Without the salts, past manifest hashes cannot be reproduced. Losing them does not invalidate past commitments, but it prevents EdgeSeeker from helping a customer verify a past anchor; the database backups mitigate that risk.
- **Model artifacts**: the private model-artifact bucket on the managed storage provider is the source of truth. Local on-server copies are a hot cache; the bucket copy is the durable one.
- **Code**: source control is replicated across internal hosting and operator workstations. The public `audit_trail` repository is mirrored at GitHub.

## Recovery objectives

- **Recovery Time Objective (RTO)**: 24 hours to resume morning generation on a new server if the primary server is lost. The recovery procedure is documented internally and restores the service-role credential from offline storage.
- **Recovery Point Objective (RPO)**: zero for the audit ledgers (the managed Postgres provider handles continuous replication). Up to 24 hours for operational tables that depend on scheduler-side backups.
- **Public repository**: the GitHub anchor repository is itself durable independent of EdgeSeeker. If EdgeSeeker disappears, all past anchors and their commit timestamps remain verifiable as long as the repository remains accessible. Past predictions can still be verified by anyone with the predictions and salt for the relevant date.

## Key custody

| Key / credential | Holder | Notes |
|---|---|---|
| Database service-role credential | Operator (managed secrets store + offline escrow) | Rotated periodically |
| GitHub deploy key (audit_trail) | Primary server | Read-write to one repository only |
| Per-day anchor salts | `audit_anchors.salt` column | Service-role only; covered by daily database backups |
| Scheduler credentials | Primary server (managed secrets store) | Used only for scheduler workflow management |

Key rotation is a manual procedure today. Automated rotation is on the roadmap.

## Audit trail of operator actions

A complete external audit trail of operator actions (server access, queries against the service-role credential, scheduler workflow changes) is not currently captured outside of EdgeSeeker. This is a known gap. Today's mitigations:

- Server access is gated through a private network whose connection events are logged centrally.
- Reverse-proxy access logs are retained on the primary server.
- Scheduler executions are logged and backed up nightly.
- All code changes are in version control with sign-off history.
- All database migrations are recorded by the managed provider.

Operator-action immutable audit logging external to EdgeSeeker is on the roadmap.

## Roadmap

- Operator-action immutable audit logging external to EdgeSeeker (planned: a small cloud-hosted append-only log of significant administrative actions, anchored to the same daily manifest hash).
- Automated key rotation across all integrity-critical credentials.
- Quarterly third-party audit of the audit ledger chain, contracted at appropriate revenue scale.
- Multi-region failover for the predictions API and audit anchor publisher (currently single-region).

## Contact

For operational questions related to integrity or to report a potential incident, contact EdgeSeeker.
