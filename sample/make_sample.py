#!/usr/bin/env python3
"""Generate a synthetic, runnable fixture for verify.py.

Produces:
  sample/predictions_full.json    — 20 fake prediction rows with all hashed fields
                                   + computed content_hash, for `verify.py content`
  sample/predictions_subset.json  — same rows trimmed to {id, content_hash, recorded_at}
                                   for `verify.py anchor`
  sample/models.json              — 1 fake model registration, for the anchor's new_models list
  sample/salt.hex                 — random 32-byte salt for this fixture's anchor
  sample/anchors/<date>.json      — the synthetic anchor whose manifest_hash matches
                                   the canonicalized predictions + models + salt + the
                                   current verify.py self-hash

EVERYTHING IN THIS FIXTURE IS FAKE. The schemas match the real audit_trail
schemas (so the verifier exercises real code paths), but the values
(predictions, model IDs, salt) are invented for demonstration only. No real
features, real models, real games, or real customer data are exposed.

Regenerate after any change to verify.py (the verifier self-hash will shift).
"""
from __future__ import annotations

import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SAMPLE_DIR = _REPO_ROOT / "sample"
_ANCHORS_DIR = _SAMPLE_DIR / "anchors"
_VERIFY_PY = _REPO_ROOT / "verify.py"

# Must match the tuple in verify.py exactly.
_CONTENT_HASH_FIELDS = (
    "sport", "category", "dataset", "model_id", "prediction_type", "prediction_mode",
    "season", "date_event", "game_time", "home_team", "away_team",
    "home_team_rotation", "away_team_rotation",
    "home_line", "away_line", "home_juice", "away_juice",
    "prediction", "confidence", "bet_type",
    "conformal_set_size", "conformal_set", "intelligence_category",
    "probability", "edge", "expected_value", "kelly_criterion", "kelly_amount",
    "sharp_money",
)

SAMPLE_DATE = "2099-01-01"          # clearly synthetic, far-future
SAMPLE_RECORDED_BASE = datetime(2099, 1, 1, 13, 0, 0, tzinfo=UTC)


def _canonical_row_payload(row: dict) -> bytes:
    payload = {f: row.get(f) for f in _CONTENT_HASH_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _canonical_day_payload(prediction_rows: list, model_rows: list, verifier_sha256: str) -> bytes:
    predictions = sorted(
        [
            {"id": str(r["id"]), "content_hash": r["content_hash"], "recorded_at": r["recorded_at"]}
            for r in prediction_rows
        ],
        key=lambda x: x["content_hash"],
    )
    models = sorted(
        [
            {"model_id": m["model_id"], "artifact_sha256": m["artifact_sha256"], "recorded_at": m["recorded_at"]}
            for m in model_rows
        ],
        key=lambda x: x["model_id"],
    )
    return json.dumps(
        {"predictions": predictions, "new_models": models, "verifier_sha256": verifier_sha256},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _self_sha256() -> str:
    return hashlib.sha256(_VERIFY_PY.read_bytes()).hexdigest()


def _make_predictions() -> list[dict]:
    """20 invented rows across a few sports/markets. Deterministic seed so the
    fixture is byte-stable when regenerated."""
    # Deterministic UUIDs/timestamps so reruns produce identical bytes (until
    # verify.py changes; the verifier_sha256 baked into the anchor will shift).
    rows = []
    samples = [
        ("NFL", "moneyline", "home", "Chiefs", "Bills",      -150, +130, -110, -110, 0.62),
        ("NFL", "spread",    "away", "Eagles", "Cowboys",     -3,   +3, -110, -110, 0.55),
        ("NFL", "total",     "over", "49ers",  "Seahawks",  None, None, -110, -110, 0.58),
        ("MLB", "moneyline", "home", "Yankees","Red Sox",    -125, +110, -110, -110, 0.60),
        ("MLB", "total",     "under","Dodgers","Giants",    None, None, -115, -105, 0.53),
        ("NBA", "spread",    "home", "Lakers", "Celtics",     +2,   -2, -110, -110, 0.57),
        ("NBA", "total",     "over", "Bucks",  "Heat",      None, None, -110, -110, 0.59),
        ("NHL", "moneyline", "away", "Bruins", "Maple Leafs",+105, -125, -110, -110, 0.54),
        ("NHL", "total",     "under","Rangers","Devils",    None, None, -120, +100, 0.51),
        ("NCAAF","spread",   "home", "Alabama","Georgia",     -4,   +4, -110, -110, 0.65),
        ("NCAAF","total",    "over", "Texas",  "Oklahoma",  None, None, -115, -105, 0.61),
        ("NCAAB","spread",   "away", "Duke",   "UNC",         +5,   -5, -110, -110, 0.56),
        ("NCAAB","moneyline","home", "Kansas", "Kentucky",   -180, +160, -110, -110, 0.68),
        ("NFL", "spread",    "home", "Ravens", "Bengals",     -2,   +2, -115, -105, 0.59),
        ("NFL", "total",     "under","Packers","Vikings",   None, None, -110, -110, 0.52),
        ("MLB", "moneyline", "away", "Astros", "Rangers",   +115, -135, -110, -110, 0.55),
        ("MLB", "spread",    "home", "Braves", "Mets",      -1.5, +1.5, -130, +110, 0.58),
        ("NBA", "moneyline", "home", "Suns",   "Warriors",   -140, +120, -110, -110, 0.61),
        ("NHL", "spread",    "home", "Lightning","Panthers",-1.5, +1.5, +160, -185, 0.50),
        ("NCAAB","total",    "over", "Gonzaga","UCLA",      None, None, -110, -110, 0.63),
    ]
    for i, (sport, bet_type, side, home, away, home_line, away_line, home_juice, away_juice, conf) in enumerate(samples):
        recorded_at = (SAMPLE_RECORDED_BASE + timedelta(minutes=i * 7)).isoformat()
        game_time = (SAMPLE_RECORDED_BASE + timedelta(hours=6, minutes=i * 23)).isoformat()
        # Deterministic UUID via uuid5 over a namespace+seed for stable rerun bytes.
        rid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"sample-{i}-{sport}-{home}-{away}"))
        row = {
            "id": rid,
            "sport": sport,
            "category": "pb",
            "dataset": "main",
            "model_id": f"sample-{sport.lower()}-{bet_type}-v1",
            "prediction_type": bet_type,
            "prediction_mode": "live",
            "season": 2099,
            "date_event": SAMPLE_DATE,
            "game_time": game_time,
            "home_team": home,
            "away_team": away,
            "home_team_rotation": 1000 + i * 2,
            "away_team_rotation": 1001 + i * 2,
            "home_line": home_line,
            "away_line": away_line,
            "home_juice": home_juice,
            "away_juice": away_juice,
            "prediction": side,
            "confidence": conf,
            "bet_type": bet_type,
            "conformal_set_size": 1,
            "conformal_set": [side],
            "intelligence_category": "bet",
            "probability": conf,
            "edge": round(conf - 0.5, 4),
            "expected_value": round((conf - 0.5) * 1.91, 4),
            "kelly_criterion": round(max(conf - 0.5, 0) * 0.05, 4),
            "kelly_amount": 100,
            "sharp_money": "neutral",
            "recorded_at": recorded_at,
        }
        row["content_hash"] = hashlib.sha256(_canonical_row_payload(row)).hexdigest()
        rows.append(row)
    return rows


def _make_models() -> list[dict]:
    return [
        {
            "model_id": "sample-nfl-spread-v1",
            "artifact_sha256": hashlib.sha256(b"sample-nfl-spread-v1 weights placeholder").hexdigest(),
            "recorded_at": SAMPLE_RECORDED_BASE.isoformat(),
        },
    ]


def main() -> int:
    _SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    _ANCHORS_DIR.mkdir(parents=True, exist_ok=True)

    predictions = _make_predictions()
    models = _make_models()

    # Deterministic salt so the fixture is byte-stable on regeneration (until
    # verify.py changes, which shifts the baked-in verifier_sha256). Committed
    # alongside so the demo is fully reproducible.
    salt_hex = hashlib.sha256(b"edgeseeker-sample-salt-2099-01-01").hexdigest()
    salt = bytes.fromhex(salt_hex)

    verifier_hash = _self_sha256()
    day_payload = _canonical_day_payload(predictions, models, verifier_hash)
    manifest_hash = hashlib.sha256(day_payload + salt).hexdigest()

    anchor = {
        "anchor_date": SAMPLE_DATE,
        "hash_algorithm": "sha256",
        "manifest_hash": manifest_hash,
        "manifest_schema_version": 3,
        "new_model_count": len(models),
        "prediction_count": len(predictions),
        "published_at": SAMPLE_RECORDED_BASE.isoformat(),
        "salted": True,
        "verifier_sha256": verifier_hash,
        "sample": True,
        "_note": "Synthetic fixture for demonstrating verify.py. No real predictions.",
    }

    (_SAMPLE_DIR / "predictions_full.json").write_text(
        json.dumps(predictions, indent=2, sort_keys=True) + "\n"
    )
    subset = [
        {"id": r["id"], "content_hash": r["content_hash"], "recorded_at": r["recorded_at"]}
        for r in predictions
    ]
    (_SAMPLE_DIR / "predictions_subset.json").write_text(
        json.dumps(subset, indent=2, sort_keys=True) + "\n"
    )
    (_SAMPLE_DIR / "models.json").write_text(json.dumps(models, indent=2, sort_keys=True) + "\n")
    (_SAMPLE_DIR / "salt.hex").write_text(salt_hex + "\n")
    (_ANCHORS_DIR / f"{SAMPLE_DATE}.json").write_text(json.dumps(anchor, indent=2, sort_keys=True) + "\n")

    print(f"Wrote synthetic fixture for date {SAMPLE_DATE}")
    print(f"  predictions: {len(predictions)} rows")
    print(f"  models:      {len(models)} rows")
    print(f"  salt:        {salt_hex[:16]}…")
    print(f"  manifest:    {manifest_hash[:16]}…")
    print(f"  verifier:    {verifier_hash[:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
