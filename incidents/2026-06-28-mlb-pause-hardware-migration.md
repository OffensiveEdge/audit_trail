# 2026-06-28 — MLB models taken offline for hardware migration

**Status:** Ongoing. MLB prediction pipeline offline pending hardware migration.
No estimated re-enable date.
**Severity:** Low — no customer-delivered prediction was affected; no ledger row
was altered. The impact is the *absence* of MLB predictions, not incorrect ones.

## Detection

- **Pause initiated (UTC):** 2026-06-25 — `morning_run_enabled=false` was set
  for `sport='mlb'` in `configs_predictions`.
- **Reason:** the operator elected to migrate the MLB prediction pipeline to a
  more capable host so future training and inference can run at higher
  throughput. The pause covers the duration of the migration; other sports
  continue normally.

## Scope

- **Sports:** MLB only. NBA, NFL, NHL, NCAAB, NCAAF unaffected.
- **Predictions suppressed:** the morning generation run skips MLB while
  `morning_run_enabled=false`. Predictions for other sports continue normally
  and are anchored normally.
- **Rows affected:** none. No `audit_trail`, `ml_predictions`, `audit_anchors`,
  or `audit_models` rows have been written incorrectly, deleted, or modified.
  The effect is zero MLB rows for the affected window where, on a normal day,
  MLB rows would have existed.

## Customer impact

**No customer received incorrect, stale, or post-game data.** No MLB
prediction was delivered late under a false timestamp. The impact is that no
MLB picks are available from 2026-06-25 forward until re-enabled.

## Status and re-enable timeline

**No estimated re-enable date.** A follow-up disclosure will be appended to
this file when MLB predictions resume, including the resume date.

## Disposition

Nothing to honor, reissue, or withdraw — no MLB predictions are being
delivered for the affected window. The daily anchor for sports other than MLB
continues to publish on the normal schedule.
