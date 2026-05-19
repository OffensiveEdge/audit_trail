#!/usr/bin/env python3
"""Independent verifier for EdgeSeeker audit_trail anchors.

Two verification modes, both run locally without trusting EdgeSeeker:

  Mode A — anchor verification:
    Given a date, a list of audit_trail rows for that date (each row has id,
    content_hash, recorded_at), and the per-day salt, recompute the manifest
    hash and compare it to the anchor at anchors/YYYY-MM-DD.json. If the hash
    matches, those exact rows were committed to this repository on the date
    GitHub recorded the commit. The salt itself stays private; only its
    revealed bytes are needed here.

  Mode B — content verification:
    Given one or more "full" audit_trail rows (with every prediction-defining
    field), recompute each row's content_hash from the canonical-JSON encoding
    and compare to the content_hash that came back from EdgeSeeker. If the
    hashes match, the prediction values are exactly what EdgeSeeker committed
    to. Combined with Mode A, the customer has a complete proof that specific
    predictions existed at a specific time, with no trust in EdgeSeeker needed
    at any step.

This script has no third-party dependencies (pure stdlib) and is licensed for
free use under the same terms as the public repository.

Usage:
  python verify.py anchor --date 2026-05-20 \
      --predictions predictions_subset.json --salt salt.hex
  python verify.py content --predictions predictions_full.json

Files:
  predictions_subset.json:
      [
        {"id": "<uuid>", "content_hash": "<sha256>", "recorded_at": "<ISO ts>"},
        ...
      ]
  predictions_full.json:
      [
        {"id": "<uuid>", "content_hash": "<sha256>", <all prediction-defining fields...>},
        ...
      ]
  salt.hex:
      Hex string of the 32-byte salt for that date (provided by EdgeSeeker
      under contract).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Must match exactly the fields hashed by the EdgeSeeker writer.
# See METHODOLOGY.md for the canonical list and rationale.
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


def _canonical_day_payload(prediction_rows, model_rows):
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
        {"predictions": predictions, "new_models": models},
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _canonical_row_payload(row):
    payload = {f: row.get(f) for f in _CONTENT_HASH_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _load_salt(salt_path):
    text = Path(salt_path).read_text().strip()
    # Accept hex or base64
    try:
        return bytes.fromhex(text)
    except ValueError:
        import base64
        return base64.b64decode(text)


def _verify_anchor(date_str, predictions_path, models_path, salt_path, repo_root):
    data = json.loads(Path(predictions_path).read_text())
    if isinstance(data, list):
        prediction_rows = data
    elif isinstance(data, dict):
        prediction_rows = data.get("predictions", [])
    else:
        print("ERROR: predictions file must be a JSON array or object", file=sys.stderr)
        return 2

    model_rows = []
    if models_path:
        loaded = json.loads(Path(models_path).read_text())
        model_rows = loaded.get("new_models", loaded) if isinstance(loaded, dict) else loaded

    salt = _load_salt(salt_path)
    recomputed = hashlib.sha256(_canonical_day_payload(prediction_rows, model_rows) + salt).hexdigest()

    anchor_path = Path(repo_root) / "anchors" / f"{date_str}.json"
    if not anchor_path.exists():
        print(f"ERROR: anchor file not found: {anchor_path}", file=sys.stderr)
        print("       (Are you running from the audit_trail repo root, "
              "or pass --repo-root?)", file=sys.stderr)
        return 2

    anchor = json.loads(anchor_path.read_text())
    published_hash = anchor.get("manifest_hash")
    if recomputed == published_hash:
        print(f"PASS  anchor {date_str}: {len(prediction_rows)} predictions + "
              f"{len(model_rows)} new model registrations hash to {recomputed[:16]}… "
              f"which matches the published anchor")
        return 0
    print(f"FAIL  anchor {date_str}: recomputed {recomputed[:16]}…  "
          f"published {published_hash[:16]}…", file=sys.stderr)
    print("      The rows + salt you provided do not match what was committed "
          "to the repository for this date.", file=sys.stderr)
    return 1


def _verify_content(predictions_path):
    rows = json.loads(Path(predictions_path).read_text())
    if not isinstance(rows, list):
        print("ERROR: predictions file must be a JSON array", file=sys.stderr)
        return 2
    mismatched = []
    for r in rows:
        recomputed = hashlib.sha256(_canonical_row_payload(r)).hexdigest()
        if recomputed != r.get("content_hash"):
            mismatched.append((str(r.get("id")), recomputed, r.get("content_hash")))
    if not mismatched:
        print(f"PASS  content: all {len(rows)} rows' content_hash values "
              f"match the recomputed canonical hash of their prediction fields")
        return 0
    print(f"FAIL  content: {len(mismatched)} of {len(rows)} rows do not match", file=sys.stderr)
    for rid, got, expected in mismatched[:10]:
        print(f"      id={rid}  recomputed={got[:16]}…  published={(expected or '')[:16]}…",
              file=sys.stderr)
    if len(mismatched) > 10:
        print(f"      … and {len(mismatched) - 10} more", file=sys.stderr)
    return 1


def main():
    p = argparse.ArgumentParser(description="Independent verifier for EdgeSeeker audit_trail anchors")
    sub = p.add_subparsers(dest="mode", required=True)

    a = sub.add_parser("anchor", help="Verify a daily anchor (Mode A)")
    a.add_argument("--date", required=True, help="anchor date in YYYY-MM-DD")
    a.add_argument("--predictions", required=True, help="path to predictions subset JSON (id, content_hash, recorded_at)")
    a.add_argument("--models", default=None,
                   help="optional path to new_models subset JSON; required only on days whose anchor includes model registrations")
    a.add_argument("--salt", required=True, help="path to salt file (hex or base64)")
    a.add_argument("--repo-root", default=".", help="path to local clone of this repository (default: cwd)")

    c = sub.add_parser("content", help="Verify per-row content hashes (Mode B)")
    c.add_argument("--predictions", required=True, help="path to predictions full JSON (id, content_hash, all hashed fields)")

    args = p.parse_args()

    if args.mode == "anchor":
        sys.exit(_verify_anchor(args.date, args.predictions, args.models, args.salt, args.repo_root))
    if args.mode == "content":
        sys.exit(_verify_content(args.predictions))


if __name__ == "__main__":
    main()
