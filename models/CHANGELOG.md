# Model Changelog

Append-only log of model registrations, promotions, retrainings, and retirements.
Newer entries at the top. Each entry corresponds to events that are bound by a
specific daily anchor (see `anchors/`); the model's individual public registration
lives at `models/<model_id>.json`.

This file is read by humans; for machine-verifiable lineage, use the per-model
JSON files and the daily anchors that committed them.

---

## 2026-05-20 — bootstrap registration of initial production models

Sixteen models currently in production were formally registered into the immutable
audit ledger for the first time and anchored together in the day-1 daily manifest.
All were trained earlier (in the calendar year ending 2025-12-31) on the same
2022–2025 walk-forward expanding window. This entry is retrospective: it represents
the registration moment, not the training moment.

| model_id              | sport  | dataset | prediction_type | size  |
|-----------------------|--------|---------|-----------------|-------|
| 2022_2025_0005519214  | mlb    | pb      | gamewinner      | 17.5M |
| 2022_2025_0007159714  | mlb    | pm      | gamewinner      | 8.7M  |
| 2022_2025_0009318814  | mlb    | pb      | spreadwinner    | 6.7M  |
| 2022_2025_0010558214  | mlb    | pm      | spreadwinner    | 14.6M |
| 2022_2025_0002475314  | nba    | pb      | gamewinner      | 9.1M  |
| 2022_2025_0004128914  | nba    | pm      | gamewinner      | 8.1M  |
| 2022_2025_2348111514  | ncaab  | pb      | gamewinner      | 10.0M |
| 2022_2025_2348113214  | ncaab  | pm      | gamewinner      | 6.7M  |
| 2022_2025_2351105414  | ncaaf  | pb      | gamewinner      | 3.2M  |
| 2022_2025_2351126614  | ncaaf  | pm      | gamewinner      | 2.4M  |
| 2022_2025_2353131314  | nfl    | pb      | gamewinner      | 0.7M  |
| 2022_2025_2353220214  | nfl    | pm      | gamewinner      | 1.0M  |
| 2022_2025_0004159614  | nhl    | pb      | gamewinner      | 10.1M |
| 2022_2025_0005434314  | nhl    | pm      | gamewinner      | 4.1M  |
| 2022_2025_0012268714  | nhl    | pb      | spreadwinner    | 4.5M  |
| 2022_2025_0033160114  | nhl    | pm      | spreadwinner    | 10.5M |

Size is the compressed tar.gz of the artifact directory; the canonical
`artifact_sha256` is a Merkle-style fingerprint of file contents, not the tarball.
See each `models/<model_id>.json` for the per-artifact hash.

Disclosure: these registrations are flagged `recovered=true` in the audit_models
ledger. The model files were retrieved from the production server's working
directory rather than captured at the moment of training. The training code's
git commit at the time of original training is not recorded for these entries
(set to the registration-time commit). Future retrainings will set
`recovered=false` and record the training-time commit precisely.
