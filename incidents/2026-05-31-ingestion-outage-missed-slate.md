# 2026-05-31 — Data-ingestion outage: suppressed MLB predictions and a missed daily anchor

**Status:** Resolved. Root cause confirmed, fix shipped.
**Severity:** Low — no customer-delivered prediction was affected; no ledger row was
altered, mis-timed, or back-dated. The impact is *absence* of predictions, not
incorrect ones.

## Detection

- **Detected (UTC):** 2026-05-31, during a routine review of why MLB predictions had
  stopped reaching the sanitized set.
- **Incident window (UTC):** 2026-05-28 through 2026-05-31.

## Scope

- **Sports:** MLB (no predictions generated 2026-05-28 → 2026-05-31). Other sports
  were unaffected on 05-28, 05-29, and 05-30 and anchored normally those days.
- **2026-05-31 specifically:** the morning generation run did not execute at all
  (all sports), and **no daily anchor was published for 2026-05-31**. The previous
  anchor is 2026-05-30; the next is expected 2026-06-01 on the normal schedule.
- **Rows affected:** none. No `audit_trail`, `ml_predictions`, `audit_anchors`, or
  `audit_models` rows were written incorrectly, deleted, or modified. The effect was
  zero rows where, on a healthy day, some would have existed.

## Customer impact

**No customer received incorrect, stale, or post-game data.** No prediction was
delivered late under a false timestamp. The impact is that no MLB picks were
available 2026-05-28 → 2026-05-31, and no picks of any sport were available on
2026-05-31. Predictions that a healthy pipeline would have produced are not
reconstructed after the fact — doing so would violate the live-timing guarantee
this ledger exists to protect — so they are treated as never having existed, not
as withheld or reissued.

## Root cause

A fault in the data-ingestion subsystem caused upstream MLB input data to stop
refreshing from approximately 2026-05-28. With only stale inputs available, the
prediction pipeline correctly declined to generate predictions for games it could
not confirm as current, resulting in zero MLB predictions for the affected days.

Separately, on 2026-05-31 the backend was briefly offline during remediation at the
time the scheduler invoked the morning generation and daily anchor jobs, so neither
executed — hence the missing 2026-05-31 anchor.

## Resolution and remediation

1. **Ingestion fix.** The fault in the data-ingestion subsystem was identified and
   corrected so that input data refreshes reliably and a stalled refresh can no
   longer silently persist stale inputs.
2. **Backfill.** The affected input data for 2026-05-15 → 2026-05-30 was
   re-ingested, restoring the current inputs the prediction pipeline consumes. This
   affects operational input data only — no row in this ledger was created, altered,
   or back-dated as part of the remediation.

## Disposition

Nothing to honor, reissue, or withdraw — no predictions were delivered for the
affected window. The 2026-05-31 anchor gap is disclosed here in lieu of an anchor
file for that date; daily anchoring resumes on the normal schedule from 2026-06-01.
