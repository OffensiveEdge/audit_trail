# 2026-05-29 — Duplicate intermediate anchors for two MLB predictions

**Status:** Resolved. Root cause confirmed, fix shipped.
**Severity:** Low — no customer-delivered pick affected; ledger integrity for the
affected ids is preserved (the canonical state is recoverable and correct), but
two superseded intermediate rows remain permanently in the ledger.

## Detection

- **Detected (UTC):** 2026-05-29T20:34:00Z, during a routine audit-trail integrity review.
- **Incident occurred (UTC):** 2026-05-24, during the 08:00 ET live morning run
  (audit_trail writes at 2026-05-24T12:00:10Z through 2026-05-24T12:00:26Z).

## Scope

- **Sport:** MLB.
- **Game:** Orioles vs. Tigers, `date_event` 2026-05-24.
- **Models:** `2022_2025_0007159714` (dataset `pb`) and `2022_2025_0005519214` (dataset `pm`).
- **Predictions affected:** 2 (`ml_prediction_id` `ae914e09-c3c5-4b12-9fa7-60fb74baf009`
  and `b4096f0a-4fe0-4cfc-a647-50cc84e6f0d7`).
- **audit_trail rows involved:** 4 — i.e. 2 spurious duplicate rows, one per affected
  prediction. Each affected prediction has two rows: an earlier intermediate snapshot
  and a later canonical snapshot.
- **Anchor affected:** the 2026-05-24 daily anchor (`row_count` 32) includes the 2
  spurious rows. The anchor manifest itself is valid and verifies — it faithfully
  anchors the rows that were in the ledger, including the duplicates.
- **No other date is affected.** A full-ledger scan found duplicate `ml_prediction_id`
  rows on 2026-05-24 only; every other day (ledger start 2026-05-20 onward) has exactly
  one row per prediction.

## Customer impact

**None.** Both affected predictions were classified `intelligence_category='skip'`
(`passed_conformal=false`) — neither was a bet, so neither was promoted to
`sanitized_predictions` nor delivered to any customer as a pick. No customer acted on,
or was shown, either row. No published win-rate or calibration figure is affected: the
daily performance report scores only bet-grade (`passed_conformal=true`) rows, which
these are not.

## Root cause

The live morning run reads game "splits" from Redis and, for each
`(sport, prediction_type, dataset)`, validates and scores every listed game. For this
slate, the Redis splits listed the Orioles/Tigers game **twice** within a single
`(MLB, gamewinner, pb)` and `(MLB, gamewinner, pm)` batch — a refreshed betting line
produced a second entry (the moneyline moved from home -127 to home -121 between the
two entries, flipping the model's pick from home/favorite to away/underdog).

The in-run dedup guard only compared against predictions already persisted in the
database at the start of the run, so both in-batch copies passed validation and were
saved. The `ml_predictions` upsert (conflict key
`sport,category,dataset,home_team,away_team,date_event,prediction_mode`) correctly
collapsed them to a single row reflecting the **later** entry — but the audit-trail
writer fired once per save. The `audit_trail` idempotency constraint is the business-key
tuple **including `bet_type`**, and because `bet_type` flipped (`favorite` → `underdog`),
the second insert was not recognized as a duplicate and a second immutable row was
written.

Net effect: one prediction id ended up with two content-divergent immutable audit rows —
an earlier intermediate (home/favorite, line -127) and the later canonical state
(away/underdog, line -121) that matches what `ml_predictions` actually holds.

## Resolution and remediation

Shipped in `edgeseeker` (`service/aiml/predictions/service.py`) and `edgeseeker-api`:

1. **Intra-batch dedup (primary fix).** `_process_sport` now deduplicates games within a
   single validation batch by the same key the upsert uses, keeping the **latest**
   occurrence. Each prediction is therefore saved — and anchored — exactly once, with the
   same line the upsert ultimately delivers. This eliminates the class of bug, not just
   this instance.
2. **Ledger idempotency safety net.** `_write_audit_trail` now checks for an existing
   `audit_trail` row for the `ml_prediction_id` before inserting and skips (with a warning)
   if one exists, guarding every other re-entry path (retries, manual re-trigger). It fails
   open: if the check itself errors, the insert proceeds rather than risk dropping a real
   pick's only receipt. A database-level `UNIQUE(ml_prediction_id)` was considered and
   rejected — it cannot be added while the two historical duplicate rows exist, and those
   rows are immutable by design and cannot be deleted.
3. **Read-path tolerance.** The public `GET /v1/audit/{id}` endpoint now orders by
   `recorded_at` descending and returns the latest row, so the two historical
   multi-row ids resolve to their canonical state instead of erroring. (Before this fix,
   requesting the receipt for either affected id returned a 500.)

## Disposition of the affected predictions

The two spurious intermediate rows **remain in the ledger permanently** — `audit_trail`
is append-only and enforced immutable by database trigger, exactly as designed; we do not
and cannot delete from it. They are disclosed here instead.

For each affected prediction, the **canonical record is the row with the latest
`recorded_at`**, which matches the corresponding `ml_predictions` row and is what the API
now returns. The earlier row is a superseded intermediate snapshot that was never
delivered to a customer.

Both affected predictions were non-bets; **they can be honored at face value** with the
canonical (latest) row as the record of truth. Nothing needs to be reissued or withdrawn.
