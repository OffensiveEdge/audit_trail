# audit_trail

Public commitment ledger for predictions produced by [EdgeSeeker](https://offensiveedge.com).

Each file in this repository is part of a chain of evidence that lets any third party verify, without trusting EdgeSeeker, that specific predictions existed at specific times — and were not altered after the fact.

## What's in here

```
anchors/YYYY-MM-DD.json   Daily salted SHA-256 manifest hash of the day's
                          predictions. The GitHub commit timestamp on each file
                          is the external attestation that this hash existed
                          before the day's games started.

models/<model_id>.json    Registration of each model artifact used in
                          production: artifact SHA-256, training window,
                          code commit, sport, prediction type. Binary
                          artifacts are stored privately; the hash bound
                          here lets a contracted customer verify the bytes.

reports/YYYY-MM-DD.json   Performance and calibration metrics computed from
                          the audit trail joined with game outcomes. Anchored
                          into the daily manifest, so claimed performance is
                          bound to the same timestamps as the predictions.

verify.py                 Pure-stdlib Python 3 script that lets anyone
                          independently verify any anchor or any individual
                          prediction's content hash.

METHODOLOGY.md            Full protocol description.
```

## Quick verification

If you are a contracted customer and have been given a set of predictions and the day's salt, you can confirm they match the public anchor:

```bash
git clone https://github.com/OffensiveEdge/audit_trail.git
cd audit_trail
python verify.py anchor --date 2026-05-20 \
  --predictions predictions_subset.json --salt salt.hex
# PASS  anchor 2026-05-20: 47 rows hash to 7f3c8e2a… which matches the published anchor
```

And to confirm an individual prediction's value was not altered:

```bash
python verify.py content --predictions predictions_full.json
# PASS  content: all 47 rows' content_hash values match the recomputed canonical hash of their prediction fields
```

## Full protocol

See [METHODOLOGY.md](METHODOLOGY.md) for the full specification: anchor protocol, per-prediction content hash, model registration, performance reports, and disclosed pre-ledger reconstructed data.

## License

The verification code (`verify.py`) is released under the MIT License so any third party can independently audit a claim of EdgeSeeker's. Predictions, salts, and model artifacts are private and provided only under contract.
