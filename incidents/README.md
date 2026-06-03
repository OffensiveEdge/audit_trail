# Incidents

EdgeSeeker commits to disclosing in this directory any data, model, or system
incident that affected the integrity, accuracy, or timeliness of predictions
delivered to customers or anchored in this repository.

## Disclosure policy

For any qualifying incident:

- **Timing**: a disclosure file is committed within **7 calendar days** of the
  incident being detected, even if root cause is still under investigation.
  Material updates to a disclosure (root cause confirmed, scope expanded,
  resolution shipped) are appended to the same file, not silently edited.
- **Naming**: `incidents/YYYY-MM-DD-<short-slug>.md` (date is the detection
  date, not the incident-occurred date).
- **Required content**:
  - Detection timestamp (UTC)
  - Incident-occurred window (UTC) if knowable
  - Scope: which sports, which model_ids, which date range of predictions
    were affected, approximate row count
  - Customer impact: which deliveries, if any, contained affected data
  - Root cause (or current best understanding)
  - Resolution and remediation
  - Whether the affected predictions can still be honored at face value,
    must be reissued, or must be withdrawn
- **No silent edits**: once committed, a disclosure file is appended to in
  Git, never rewritten. Errors in earlier disclosures are corrected by
  appending a follow-up section, not by force-pushing.

## What qualifies as an incident

- A bug that caused predictions delivered to customers to use stale, incorrect,
  or post-game data
- A loss or corruption of audit_trail, audit_anchors, or audit_models rows
  (per-day salts live in the audit_anchors.salt column)
- A gap in daily anchor publication exceeding 24 hours
- An unauthorized write to any of those tables, or unauthorized release of a
  per-day salt
- A model promotion that bypassed the registration ledger
- A change to the verifier (`verify.py`) or methodology that altered the
  semantics of past verifications

## What does *not* qualify as an incident

- Predictions whose model was simply wrong about a game's outcome. Model loss
  is expected; performance reports cover that.
- Scheduled maintenance or model retraining, provided the changelog and
  registration ledger reflect it.

## Current state

- [`2026-05-29-duplicate-intermediate-anchors.md`](2026-05-29-duplicate-intermediate-anchors.md)
  — two MLB non-bet predictions on 2026-05-24 each received a duplicate intermediate
  audit row from a mid-run line move. No customer impact; root cause fixed. Resolved.
- [`2026-05-31-ingestion-outage-missed-slate.md`](2026-05-31-ingestion-outage-missed-slate.md)
  — a data-ingestion outage suppressed MLB predictions 2026-05-28 → 2026-05-31 and
  caused no daily anchor to publish for 2026-05-31. No customer impact; no ledger row
  altered; ingestion fixed and inputs backfilled. Resolved.
