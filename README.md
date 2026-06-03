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
                          production: artifact fingerprint, training window,
                          code commit, sport, prediction type. Binary
                          artifacts are stored privately; the fingerprint
                          (a Merkle-style hash of the artifact's file contents,
                          not a hash of the tarball — see METHODOLOGY.md) lets
                          a contracted customer verify the files.

reports/YYYY-MM-DD.json   Performance and calibration metrics computed from
                          the audit trail joined with game outcomes. Committed
                          alongside the daily anchor (so each carries a GitHub
                          commit timestamp); not yet folded into the salted
                          manifest hash — see METHODOLOGY.md.

verify.py                 Pure-stdlib Python 3 script that lets anyone
                          independently verify any anchor or any individual
                          prediction's content hash.

METHODOLOGY.md            Full protocol description.

sample/                   Synthetic, runnable fixture so anyone can exercise
                          verify.py end-to-end without a contract or any real
                          EdgeSeeker data. See sample/README.md.
```

## Quick verification

If you are a contracted customer and have been given a set of predictions and the day's salt, you can confirm they match the public anchor:

```bash
git clone https://github.com/OffensiveEdge/audit_trail.git
cd audit_trail
python verify.py anchor --date 2026-05-20 \
  --predictions predictions_subset.json --salt salt.hex
# PASS  anchor 2026-05-20: 34 predictions + 0 new model registrations hash to 6071446a… which matches the published anchor
```

And to confirm an individual prediction's value was not altered:

```bash
python verify.py content --predictions predictions_full.json
# PASS  content: all 34 rows' content_hash values match the recomputed canonical hash of their prediction fields
```

## Try it without a contract

If you just want to confirm `verify.py` works as described — without an NDA, contract, or any real EdgeSeeker data — run it against the synthetic fixture in [`sample/`](sample/):

```bash
git clone https://github.com/OffensiveEdge/audit_trail.git
cd audit_trail

# Per-row content hashes
python verify.py content --predictions sample/predictions_full.json

# Daily anchor verification
python verify.py anchor \
  --date 2099-01-01 \
  --predictions sample/predictions_subset.json \
  --models sample/models.json \
  --salt sample/salt.hex \
  --repo-root sample/
```

Both should print `PASS`. Everything in `sample/` is fabricated — no real predictions, features, or model parameters are exposed. See [`sample/README.md`](sample/README.md) for the full description of what the fixture proves (and doesn't).

## Supplemental: Bitcoin attestation (optional)

`verify.py` proves predictions → anchor file, dated by that file's **GitHub commit timestamp**, with zero dependencies and no network. Each anchor *also* carries an OpenTimestamps proof (`anchors/YYYY-MM-DD.json.ots`) that stamps it to the **Bitcoin** blockchain — an independent timestamp that doesn't rely on trusting GitHub's clock. Checking that is an **optional, supplemental** step, kept in a separate script so the core verifier stays pure-stdlib and offline:

```bash
pip install opentimestamps-client          # the `ots` reference client
python verify_bitcoin.py                    # all anchors  (needs a local Bitcoin node)
python verify_bitcoin.py --date 2026-05-20  # one anchor
python verify_bitcoin.py --offline          # read each proof's on-chain block, no node/network
python verify_bitcoin.py --digests          # just the anchor hashes, no ots
```

`verify_bitcoin.py` verifies *through* the OpenTimestamps reference client — it never reimplements Bitcoin/merkle validation. For each anchor it confirms the `.ots` proof commits to the exact `sha256` of that anchor file (the same file `verify.py` matched your predictions to), then resolves the Bitcoin attestation to a block + time. The published `.ots` proofs are **upgraded and self-contained** — each carries its Bitcoin block attestation directly, so verification never depends on an OpenTimestamps calendar staying online. **Trust note:** the merkle path is checked locally, but confirming the block is real requires **your own Bitcoin Core node** (pruned is fine — it keeps every block header, which is all the proof needs). The client has **no public-explorer fallback**, and that is deliberate: needing your own node is what makes the check fully trustless. Without a node, `--offline` reads the Bitcoin block each proof already contains. Full runbook: `python verify_bitcoin.py --help`.

## Full protocol

See [METHODOLOGY.md](METHODOLOGY.md) for the full specification: anchor protocol, per-prediction content hash, model registration, performance reports, and disclosed pre-ledger reconstructed data.

## License

The verification code (`verify.py`) is released under the MIT License so any third party can independently audit a claim of EdgeSeeker's. Predictions, salts, and model artifacts are private and provided only under contract.
