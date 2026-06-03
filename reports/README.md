# Reports

Periodic performance and calibration reports computed from the audit trail joined with game outcomes. Each file commits the metrics as of its filename's date.

## File naming

- `reports/YYYY-MM-DD.json` — daily snapshot of cumulative metrics through that date
- `reports/YYYY-MM.json` — monthly summary
- `reports/YYYY-Qn.json` — quarterly summary

The first daily report is committed on the first day the audit trail is live. Reports covering dates before the audit trail's start are not generated here; pre-ledger performance is documented via the reproducible walk-forward backtest, not this repository.

## Schema

```json
{
  "report_date": "YYYY-MM-DD",
  "audit_trail_row_count": <int>,
  "outcomes_resolved_count": <int>,
  "metrics": {
    "overall": {
      "hit_rate": <float|null>,
      "brier": <float|null>,
      "log_loss": <float|null>,
      "ece": <float|null>,
      "n": <int>
    },
    "by_sport": {
      "<sport>": { ... same shape as overall ... }
    },
    "by_model_id": {
      "<model_id>": { ... same shape as overall ... }
    },
    "roi_percent": <float|null>
  },
  "calibration_curve": [
    {"predicted_probability_bin": <float>, "observed_frequency": <float>, "n": <int>}
  ],
  "methodology_version": "<string>",
  "published_at": "<ISO 8601 UTC timestamp>"
}
```

## Anchoring

Reports are committed alongside daily anchors. As of `manifest_schema_version: 3` (current), reports are committed but **not** included in the daily manifest hash. Their GitHub commit timestamp is currently the sole external attestation. A future schema bump (manifest v4) will include the report's content hash in the daily manifest so claimed performance is bound by the same cryptographic commitment as predictions and model registrations.

## Methodology

- **Hit rate**: fraction of predictions whose `prediction` matched the realized outcome among predictions with `bet_status ∈ {win, loss}`.
- **ROI percent**: net profit divided by total stake, using each prediction's `kelly_amount` as the stake. Push/dodge/miss excluded.
- **Brier score**: mean squared error between predicted probability and realized 0/1 outcome.
- **Log loss**: standard binary cross-entropy on `(probability, realized outcome)` pairs.
- **Expected calibration error**: weighted mean absolute deviation between predicted probability and observed frequency, binned in 10% increments.
- **Calibration curve**: 10 bins of predicted probability; for each, the observed frequency and count.

Only predictions with `intelligence_category = 'bet'` and resolved outcomes (`bet_status ∈ {win, loss, push}`) contribute to overall metrics. Pushes are excluded from Brier/log-loss/calibration; included in ROI as zero return.
