# Audit Trail Methodology

This repository is the public commitment ledger for predictions produced by EdgeSeeker. Each file in `anchors/`, `models/`, and `reports/` is part of a chain of evidence that lets any third party verify, without trusting EdgeSeeker, that specific predictions existed at specific times.

## What this repository proves

Three independent things can be proven from this repository:

1. **Predictions existed before games started.** Every weekday morning, EdgeSeeker commits a hash of the day's predictions to this repository. The GitHub commit timestamp is an external, third-party attestation that the hash existed at that point in time. If the hash later matches a set of predictions, those predictions are bound to that timestamp.

2. **Predictions were not altered after the fact.** Each prediction has an individual content hash bound to the day's manifest hash. Mutating any single field would change the content hash and break the manifest match.

3. **Predictions came from specific, registered models.** Every model artifact used in production is registered in this repository (see `models/`) with its content hash. The artifact bytes themselves are stored privately; under contract, the bytes can be supplied to a customer and independently verified to match the registered hash.

What this repository does *not* prove on its own:

- It does not reveal the predictions themselves. The hash is a one-way commitment. Predictions are revealed only under contract.
- It does not prove the model is *good*. That is the role of the performance reports (`reports/`), anchored by the same daily commits — and a reproducible walk-forward backtest provided under contract.

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

The canonical manifest payload (v3) commits to predictions, newly registered models, AND the verifier itself in a single hash:

```json
{
  "predictions": [
    {"id": "<uuid>", "content_hash": "<sha256>", "recorded_at": "<ISO ts>"},
    ...
  ],
  "new_models": [
    {"model_id": "<id>", "artifact_sha256": "<sha256>", "recorded_at": "<ISO ts>"},
    ...
  ],
  "verifier_sha256": "<sha256 of verify.py at time of anchor>"
}
```

`predictions` are sorted by `content_hash`, `new_models` by `model_id`. Empty arrays are allowed; a day with no new predictions or new models still anchors so long as the verifier hash is committed.

Including the verifier's own hash in the manifest prevents a future tampered `verify.py` from silently re-verifying past anchors. The verifier self-checks: it computes its own sha256 at runtime and refuses to run if the anchor it's verifying was published against a different verifier.

The public anchor file is small and contains only public counts plus the verifier hash plus the conformal coverage policy in force on the anchor date:

```json
{
  "anchor_date": "YYYY-MM-DD",
  "manifest_hash": "<64-char sha256>",
  "prediction_count": <int>,
  "new_model_count": <int>,
  "verifier_sha256": "<64-char sha256>",
  "salted": true,
  "hash_algorithm": "sha256",
  "manifest_schema_version": 4,
  "conformal_coverage_policy": {
    "default": 0.90,
    "overrides": [
      {"sport": "mlb",   "season_type": "post", "target": 0.80},
      {"sport": "nba",   "season_type": "post", "target": 0.80},
      {"sport": "ncaab", "season_type": "post", "target": 0.80},
      {"sport": "ncaaf", "season_type": "post", "target": 0.80},
      {"sport": "nfl",   "season_type": "post", "target": 0.80},
      {"sport": "nhl",   "season_type": "post", "target": 0.80}
    ],
    "notes": "..."
  },
  "published_at": "<ISO 8601 UTC timestamp>"
}
```

Once published, the commit timestamp on GitHub is external evidence that this hash existed at that time. EdgeSeeker cannot alter the commit timestamp; GitHub records it.

The manifest schema is versioned. v1 anchors (never published) hashed only predictions. v2 (never published) added new_models. v3 added verifier_sha256. v4 (current) adds `conformal_coverage_policy` — the per-(sport, season_type) coverage target rule in force on the anchor date. Each anchor file declares its `manifest_schema_version` so verifiers can dispatch correctly. The policy block is human-readable disclosure; the per-row coverage target each prediction was actually evaluated against is committed into that row's `content_hash` (see "Per-prediction content hash" below) — so the policy stated here is verifiable against actual usage row-by-row.

## Conformal coverage policy

EdgeSeeker uses a conformal prediction filter — not a hand-tuned probability threshold — to decide which model outputs are promoted from "skip" to "bet" at the customer surface. The filter is parameterized by a **coverage target**: the probability that the credible set output by the conformal layer contains the true outcome. At a 90% coverage target, the credible set covers the true outcome 90% of the time (under exchangeability). Lower coverage = tighter credible sets = more rows promoted to bet.

The current policy is:

| Sport | Season type | Coverage target |
|---|---|---|
| All | Regular season | 0.90 |
| MLB, NBA, NCAAB, NCAAF, NFL, NHL | Postseason | 0.80 |

The lower postseason target reflects an empirical observation: best-vs-best matchups during playoffs have structurally higher single-game variance, and the regular-season-calibrated 90% gate over-rejects relative to the underlying signal. The 0.80 postseason target accepts a 20% credible-set error rate (vs 10% in regular season) in exchange for surfacing picks during the highest-variance segment of each season. Customers see this as a wider denominator on postseason bet counts and a published empirical hit rate per coverage tier in the daily report (see "Performance and calibration reports" below — `by_coverage_target` slice).

Per-(sport, season_type) refinement (different coverage, per-bet-type variation, per-sport calibration-window changes) is expected as each sport's pipeline gets its dedicated overhaul. The unified 0.90 / 0.80 split is the *starting* rule. Changes are disclosed by version-bumping the policy block on the next daily anchor — the previous policy stays verifiable on its anchored manifest.

## Per-prediction content hash

Each prediction has its own `content_hash` computed at the moment the prediction is committed to the `audit_trail` table:

`content_hash = sha256(canonical_json(prediction_fields))`

The exact list of `prediction_fields` is fixed and documented in `verify.py`. It excludes timestamps (which are circular) and post-game fields (such as result and bet status, which change after the game). The hash binds the prediction's value at generation time and never changes.

## Model registration

When a model artifact is promoted into production, an immutable registration is committed both to a private ledger and to this repository at `models/<model_id>.json`. The public file contains:

```json
{
  "model_id": "<string>",
  "artifact_sha256": "<64-char Merkle-style fingerprint of the artifact's file contents (see below) — NOT a hash of the tarball>",
  "training_window_start": "YYYY-MM-DD",
  "training_window_end": "YYYY-MM-DD",
  "sport": "...",
  "prediction_type": "...",
  "dataset": "...",
  "code_commit_sha": "<git commit of the training code>",
  "artifact_size_bytes": <int>,
  "recovered": <bool>,
  "reproducible": <bool>,
  "recorded_at": "<ISO 8601 UTC timestamp>",
  "is_canonical": <bool>,
  "canonicalized_at": "<ISO 8601 UTC timestamp, or null>"
}
```

The artifact bytes themselves are stored privately. Under contract, EdgeSeeker provides the artifact's files and the customer recomputes `artifact_sha256` and compares. The fingerprint is **not** a flat hash of the `.tar.gz` (gzip/tar framing is not byte-deterministic); it is a Merkle-style hash of the file *contents*: for every file in the artifact directory, sorted by relative path, compute `sha256(file_bytes)`, form the line `"<relative_path>\n<file_sha256>\n"`, concatenate the lines in sorted-path order, and take the `sha256` of that concatenation. A prediction's `model_id` in the audit trail resolves to exactly one entry here.

Model registrations are anchored into the next daily manifest hash after they are committed, so the model lineage is bound to the same external timestamps as the predictions.

From 2026-06-01, the private registration additionally records the model's held-out validation metrics (ROC-AUC, F1, precision, recall, balanced accuracy, MCC, accuracy) captured at registration. These are not printed in the public file above, but they live inside the artifact archive (`metrics.json`) whose `artifact_sha256` is published here and anchored — so under the same bytes-disclosure contract, a customer verifies the metrics against the anchored hash, with no change to the manifest format. Models registered before that date predate the field; their training-time performance is provided via reproducible walk-forward backtest.

From 2026-06-11, each model file carries two additional lifecycle fields: `is_canonical` and `canonicalized_at`. `is_canonical = true` indicates the model was deliberately promoted to serve customers (a Promote action in the operator's training-lineage UI). `is_canonical = false` indicates a training or discovery candidate that was registered but never reached production — kept in the registry for transparency, hidden from the default per-slot lineage view on EdgeSeeker's `/verification` page. `canonicalized_at` is the timestamp of the Promote moment for models promoted on or after 2026-06-11. For canonical models predating this field (the backfill set), `canonicalized_at = recorded_at` is used as a best-available proxy; the same disclosure is mirrored in EdgeSeeker's UI as "Activated on or before <date>." Lifecycle fields are additive and do not change the canonical manifest hash; older `models/*.json` files predating this addition simply lack the two keys.

## Performance and calibration reports

The `reports/` directory contains periodic performance metrics computed from the audit trail joined with game outcomes:

- Brier score, log-loss, expected calibration error (ECE)
- Hit rate and ROI, sliced by sport, category, model_id, **and coverage target**
- Calibration curves

The `by_coverage_target` slice publishes the empirical hit rate for each declared coverage tier (e.g. all picks declared at the 0.80 target, all picks declared at 0.90). Verifiers can compare each tier's empirical rate against the policy stated on that day's anchor (`conformal_coverage_policy.overrides` and `.default`) — declared vs achieved coverage row-by-row.

Reports are committed to this repository alongside the daily anchors, so each carries the external GitHub commit timestamp for its date. They are **not** included in the salted manifest hash (schema v4): a report's metrics are timestamped by their commit but are not bound into the cryptographic manifest the way predictions and model registrations are. Performance reports begin from the first day the audit trail was live; metrics before that date are reported separately via reproducible walk-forward backtest, not via this repository.

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

Confirms that a set of rows (and the day's salt, which EdgeSeeker provides under contract) hashes to the value published in `anchors/2026-05-20.json`. If it does, those rows were committed to this repository at the GitHub commit timestamp for that anchor file. (The `--predictions` and `--salt` files are supplied under contract and are not in this public repo. To exercise `verify.py` end-to-end with no contract, run it against the synthetic fixture in `sample/` — see `sample/README.md`.) Mode A validates the manifest hash and the GitHub-committed anchor using pure stdlib; the matching `.ots` Bitcoin proof is checked by the `bitcoin` subcommand below (which wraps the OpenTimestamps `ots` client) — that keeps Modes A/B pure-stdlib and offline while still bundling the Bitcoin check into the same verifier file.

### Mode B — content verification

```bash
python verify.py content --predictions predictions_full.json
```

For each row, recomputes `sha256(canonical_json(prediction_fields))` and confirms it matches the row's published `content_hash`. If it does, the prediction values are exactly what EdgeSeeker committed to.

Mode A and Mode B together give a complete proof for any historical prediction: *this exact prediction* existed at *this exact time*.

### Mode C — Bitcoin attestation (optional)

Modes A/B date an anchor by its **GitHub commit timestamp**. Each anchor also has an OpenTimestamps proof (`anchors/YYYY-MM-DD.json.ots`) stamping it to the **Bitcoin** blockchain — an independent timestamp that does not rely on GitHub's clock. This is checked by the `bitcoin` subcommand, which lazy-loads the `ots` CLI only when invoked, so Modes A/B stay pure-stdlib, offline, zero-dependency:

```bash
pip install -r requirements-bitcoin.txt          # the `ots` client (opentimestamps-client==0.7.2, pinned)
python verify.py bitcoin                          # all anchors  (needs a local Bitcoin node)
python verify.py bitcoin --offline                # read each proof's on-chain block, no node/network
python verify.py bitcoin --digests                # just print anchor file sha256s; no ots needed
```

The `bitcoin` subcommand verifies *through* the OpenTimestamps reference client (it never reimplements Bitcoin/merkle validation): for each anchor it confirms the `.ots` proof commits to the exact `sha256` of the anchor file Mode A matched, then resolves the attestation to a Bitcoin block + time. The published `.ots` proofs are upgraded and self-contained — each carries its Bitcoin block attestation directly, so verification does not depend on any OpenTimestamps calendar remaining online. The merkle path is checked locally, but confirming the block is real requires **your own Bitcoin Core node** (pruned suffices — it retains every block header); the client has no public-explorer fallback, which is precisely what makes the check fully trustless. Without a node, `--offline` reads the Bitcoin block each proof already contains. Full runbook: `python verify.py bitcoin --help`.

Pre-v1.0 anchors were verified by a separate `verify_bitcoin.py` script; v1.0 folded that into `verify.py bitcoin` so customers maintain a single verifier file. The pre-v1.0 verify_bitcoin.py remains in git history (`git checkout <pre-v1.0-commit> -- verify_bitcoin.py`) for verifying pre-v1.0 anchors with their original tooling.

## Roadmap

The integrity stack described above is complete and operating. One planned addition, gated on business scale rather than engineering:

- **Independent third-party audit**: at appropriate revenue scale, a security firm will independently verify a sample of anchors and the chain of custody.

The methodology in this document is versioned. If it changes materially, the previous version is retained in `methodology/` for historical reference.

## Contact

For verification questions or contracted access to predictions and salts, contact EdgeSeeker.
