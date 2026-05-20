# sample/

A **synthetic, self-contained fixture** that lets anyone run `verify.py`
end-to-end without a contract or any real EdgeSeeker data.

Everything in this directory is invented for demonstration. The schemas match
the real `audit_trail` schemas exactly (so `verify.py` exercises real code
paths), but the values — predictions, model IDs, salt, anchor date — are all
fabricated.

## What you get

| File | Purpose |
|---|---|
| `predictions_full.json`    | 20 fake prediction rows with every hashed field + the computed `content_hash`. Input for `verify.py content`. |
| `predictions_subset.json`  | Same rows trimmed to `{id, content_hash, recorded_at}`. Input for `verify.py anchor`. |
| `models.json`              | 1 fake model registration. The anchor's `new_models` list. |
| `salt.hex`                 | A deterministic 32-byte salt for this fixture. In production the salt stays private; here it's exposed so the demo is fully reproducible. |
| `anchors/2099-01-01.json`  | The synthetic anchor whose `manifest_hash` matches the canonicalized predictions + models + salt + the current verifier self-hash. |
| `make_sample.py`           | The generator script. Regenerate after any change to `verify.py` (the verifier self-hash baked into the anchor will shift). |

The anchor date `2099-01-01` is chosen to be clearly synthetic — it cannot
collide with any real anchor.

## Run the verifier

From the repository root:

```bash
# Mode B — per-row content hashes
python verify.py content --predictions sample/predictions_full.json

# Mode A — daily anchor verification
python verify.py anchor \
  --date 2099-01-01 \
  --predictions sample/predictions_subset.json \
  --models sample/models.json \
  --salt sample/salt.hex \
  --repo-root sample/
```

Expected output:

```
PASS  content: all 20 rows' content_hash values match the recomputed canonical hash of their prediction fields
PASS  anchor 2099-01-01: 20 predictions + 1 new model registrations hash to … which matches the published anchor
```

If either fails on a clean clone, the verifier was tampered with or the
fixture is out of date — regenerate via `python sample/make_sample.py`.

## What this proves (and what it doesn't)

**Proves:** the verifier code works as described in `METHODOLOGY.md`. Given a
manifest, predictions, models, and a salt, it can recompute and check the
anchor's `manifest_hash`. Given full prediction rows, it can recompute and
check each row's `content_hash`.

**Does not prove:** anything about real EdgeSeeker predictions. The fixture
contains no real predictions, no real model parameters, no feature values, and
no feature names. The synthetic anchor here was never committed to a
production anchor file and is not stamped against the Bitcoin blockchain.

To verify a real anchor you need:
1. A subset of real `audit_trail` rows for that date (provided under contract),
2. The day's real salt (provided under contract),
3. The real anchor file at `anchors/YYYY-MM-DD.json` (already public in this
   repo), and
4. The real `.ots` proof at `anchors/YYYY-MM-DD.json.ots`, which independently
   stamps the anchor against Bitcoin.

The sandbox skips steps 1, 2, and 4. Step 3 is replaced by the synthetic
anchor at `sample/anchors/2099-01-01.json`.
