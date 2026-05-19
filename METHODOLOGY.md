# Audit Trail Methodology

This repository is the public commitment ledger for predictions produced by EdgeSeeker. Each file in `anchors/`, `models/`, and `reports/` is part of a chain of evidence that lets any third party verify, without trusting EdgeSeeker, that specific predictions existed at specific times.

## What this repository proves

Three independent things can be proven from this repository:

1. **Predictions existed before games started.** Every weekday morning, EdgeSeeker commits a hash of the day's predictions to this repository. The GitHub commit timestamp is an external, third-party attestation that the hash existed at that point in time. If the hash later matches a set of predictions, those predictions are bound to that timestamp.

2. **Predictions were not altered after the fact.** Each prediction has an individual content hash bound to the day's manifest hash. Mutating any single field would change the content hash and break the manifest match.

3. **Predictions came from specific, registered models.** Every model artifact used in production is registered in this repository (see `models/`) with its content hash. The artifact bytes themselves are stored privately; under contract, the bytes can be supplied to a customer and independently verified to match the registered hash.

What this repository does *not* prove on its own:

- It does not reveal the predictions themselves. The hash is a one-way commitment. Predictions are revealed only under contract.
- It does not prove the model is *good*. That is the role of the performance reports (`reports/`) and the walk-forward backtest, anchored by the same daily commits.

## The chain of evidence

```
prediction generated → audit_trail row (private DB)
                    → content_hash (private)
                    → daily salted manifest hash
                    → GitHub commit to anchors/YYYY-MM-DD.json (public)
                    → GitHub commit timestamp (third-party)
```

Each step is locally reproducible by the verifier (`verify.py`) once the customer has the inputs they are entitled to under contract.

## Daily anchor protocol

Every weekday, after morning generation completes:

1. EdgeSeeker selects all `audit_trail` rows recorded that UTC day.
2. For each row, the minimal triple `{id, content_hash, recorded_at}` is collected.
3. The triples are sorted by `content_hash` and serialized to canonical JSON (sorted keys, no whitespace).
4. A 32-byte random salt is generated for that day. The salt is stored privately.
5. `manifest_hash = sha256(canonical_bytes || salt_bytes)` (concatenation).
6. The anchor file `anchors/YYYY-MM-DD.json`, plus any public `models/<model_id>.json` files for newly registered models, are committed and pushed to this repository in one push.

The canonical manifest payload (v2) commits to both predictions and newly registered models in a single hash:

```json
{
  "predictions": [
    {"id": "<uuid>", "content_hash": "<sha256>", "recorded_at": "<ISO ts>"},
    ...
  ],
  "new_models": [
    {"model_id": "<id>", "artifact_sha256": "<sha256>", "recorded_at": "<ISO ts>"},
    ...
  ]
}
```

`predictions` are sorted by `content_hash`, `new_models` by `model_id`. Empty arrays are allowed; a day with no new predictions but new model registrations still anchors.

The public anchor file is small and contains only public counts:

```json
{
  "anchor_date": "YYYY-MM-DD",
  "manifest_hash": "<64-char sha256>",
  "prediction_count": <int>,
  "new_model_count": <int>,
  "salted": true,
  "hash_algorithm": "sha256",
  "manifest_schema_version": 2,
  "published_at": "<ISO 8601 UTC timestamp>"
}
```

Once published, the commit timestamp on GitHub is external evidence that this hash existed at that time. EdgeSeeker cannot alter the commit timestamp; GitHub records it.

The manifest schema is versioned. v1 anchors (none yet published) hashed only the day's predictions as a bare JSON array. v2 (current) hashes a JSON object with `predictions` and `new_models` keys. Each anchor file declares its `manifest_schema_version` so verifiers can dispatch correctly.

## Per-prediction content hash

Each prediction has its own `content_hash` computed at the moment the prediction is committed to the `audit_trail` table:

`content_hash = sha256(canonical_json(prediction_fields))`

The exact list of `prediction_fields` is fixed and documented in `verify.py`. It excludes timestamps (which are circular) and post-game fields (such as result and bet status, which change after the game). The hash binds the prediction's value at generation time and never changes.

## Model registration

When a model artifact is promoted into production, an immutable registration is committed both to a private ledger and to this repository at `models/<model_id>.json`. The public file contains:

```json
{
  "model_id": "<string>",
  "artifact_sha256": "<64-char sha256 of the artifact archive>",
  "training_window_start": "YYYY-MM-DD",
  "training_window_end": "YYYY-MM-DD",
  "sport": "...",
  "prediction_type": "...",
  "dataset": "...",
  "code_commit_sha": "<git commit of the training code>",
  "recorded_at": "<ISO 8601 UTC timestamp>"
}
```

The artifact bytes themselves are stored privately. Under contract, EdgeSeeker provides the bytes and the customer verifies `sha256(bytes) == artifact_sha256`. A prediction's `model_id` in the audit trail resolves to exactly one entry here.

Model registrations are anchored into the next daily manifest hash after they are committed, so the model lineage is bound to the same external timestamps as the predictions.

## Performance and calibration reports

The `reports/` directory contains periodic performance metrics computed from the audit trail joined with game outcomes:

- Brier score, log-loss, expected calibration error (ECE)
- Hit rate and ROI, sliced by sport, category, model_id
- Calibration curves

Reports are anchored into the daily manifest hash, so claimed performance is bound to the same external timestamps as the predictions it describes. Performance reports begin from the first day the audit trail was live; metrics before that date are reported separately via reproducible walk-forward backtest, not via this repository.

## Disclosed reconstructed data

EdgeSeeker began capturing predictions live with sub-second timestamps from late 2025. Earlier predictions exist in operational tables but their timestamps were lost during a database migration and reconstructed by setting `created_at = game_time - 5 minutes`. Reconstructed-timestamp rows are **not** committed to this audit trail and are not part of any "live capture" claim. They are usable as inputs to the walk-forward backtest (which proves no leakage by construction), not as evidence of live timing.

The first anchor in this repository marks the start of the unimpeachable live-capture period.

## Verification

The repository ships with `verify.py`, a small pure-stdlib Python 3 script. Two modes:

### Mode A — anchor verification

```bash
python verify.py anchor --date 2026-05-20 \
  --predictions predictions_subset.json --salt salt.hex
```

Confirms that a set of rows (and the day's salt, which EdgeSeeker provides under contract) hashes to the value published in `anchors/2026-05-20.json`. If it does, those rows were committed to this repository at the GitHub commit timestamp for that anchor file.

### Mode B — content verification

```bash
python verify.py content --predictions predictions_full.json
```

For each row, recomputes `sha256(canonical_json(prediction_fields))` and confirms it matches the row's published `content_hash`. If it does, the prediction values are exactly what EdgeSeeker committed to.

Mode A and Mode B together give a complete proof for any historical prediction: *this exact prediction* existed at *this exact time*.

## Roadmap

This repository is the public-facing artifact for an evolving integrity stack. Planned additions:

- **Data lineage**: for each prediction, the upstream features (and the data sources they came from) will be hashed and anchored alongside the predictions. This closes the loop on the *input* side, complementing the model and prediction registrations on the *output* side.
- **Independent third-party audit**: at appropriate revenue scale, a security firm will independently verify a sample of anchors and the chain of custody.
- **OpenTimestamps**: redundant anchoring of the daily manifest hash to a public blockchain timestamp for very-long-term verification independent of GitHub's continued operation.

The methodology in this document is versioned. If it changes materially, the previous version is retained in `methodology/` for historical reference.

## Contact

For verification questions or contracted access to predictions and salts, contact EdgeSeeker.
