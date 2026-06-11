#!/usr/bin/env python3
"""Independent verifier for EdgeSeeker audit_trail anchors.

Three verification modes, all runnable locally without trusting EdgeSeeker:

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

  Mode C — Bitcoin attestation verification:
    Verifies that each anchor file was committed to the Bitcoin blockchain via
    its OpenTimestamps (`.ots`) proof — an external, independent timestamp
    beyond GitHub's commit clock. Trustless mode requires a local Bitcoin Core
    node (pruned is fine); `--offline` reads the on-chain attestation each
    proof already carries; `--digests` just prints anchor file hashes.

    Requires the `ots` CLI: `pip install -r requirements-bitcoin.txt`
    (opentimestamps-client==0.7.2, pinned). Mode A and Mode B do NOT need it.

This script has no third-party imports (pure stdlib); the Bitcoin mode invokes
the `ots` CLI as a subprocess. Licensed for free use under the same terms as
the public repository.

Usage:
  python verify.py anchor --date 2026-05-20 \
      --predictions predictions_subset.json --salt salt.hex
  python verify.py content --predictions predictions_full.json
  python verify.py bitcoin --date 2026-05-20         # needs a local Bitcoin node
  python verify.py bitcoin --offline                 # reads each .ots's on-chain claim
  python verify.py bitcoin --digests                 # just anchor file sha256s

Files for Mode A / Mode B:
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

Schema versions supported by this verifier:
  3  — predictions + new_models + verifier_sha256
  4  — same canonical payload as v3; adds `conformal_coverage_policy` block
       to the public anchor file (human-readable disclosure of the per-(sport,
       season_type) coverage rule in force on the anchor date). The hashed
       payload is unchanged from v3, so Mode A logic is identical; the only
       difference is that the field set for per-row content_hash (Mode B)
       gained `conformal_coverage_target` for predictions from 2026-06-12
       forward.

Older anchors:
  Pre-v1.0 anchors and older schemas are still verifiable via the verify.py at
  their corresponding git commit (the anchor's `verifier_sha256` self-check
  refuses to run this verifier against an anchor it wasn't published for).
  Run `git log -- verify.py` to find the matching commit for a given date.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# =============================================================================
# Schema dispatch
# =============================================================================
# Each entry describes how to canonicalize the per-day payload for that schema
# version. The payload bytes feed `sha256(payload || salt)` to recompute the
# anchor's `manifest_hash`. v3 and v4 share a handler — the v4 bump only
# changed the public anchor file (added `conformal_coverage_policy`), not the
# hashed canonical payload. Future schema bumps register new handlers here
# without requiring a new verifier file.
_SCHEMA_HANDLERS: dict = {
    3: "v3_v4",
    4: "v3_v4",
}

# =============================================================================
# Per-prediction content_hash field tuple
# =============================================================================
# Must match exactly the fields hashed by the EdgeSeeker writer
# (`_AUDIT_TRAIL_HASH_FIELDS` in service/aiml/predictions/service.py).
# See METHODOLOGY.md for the canonical list and rationale.
#
# `conformal_coverage_target` joined the tuple on 2026-06-12 as part of the
# v1.0 cut. Predictions written before that date do not carry the field; for
# Mode B verification of pre-v1.0 predictions, check out the verify.py at the
# matching commit (the anchor's `verifier_sha256` will route you there).
_CONTENT_HASH_FIELDS = (
    "sport", "category", "dataset", "model_id", "prediction_type", "prediction_mode",
    "season", "date_event", "game_time", "home_team", "away_team",
    "home_team_rotation", "away_team_rotation",
    "home_line", "away_line", "home_juice", "away_juice",
    "prediction", "confidence", "bet_type",
    "conformal_set_size", "conformal_set", "conformal_coverage_target",
    "intelligence_category",
    "probability", "edge", "expected_value", "kelly_criterion", "kelly_amount",
    "sharp_money",
)


# =============================================================================
# Shared helpers
# =============================================================================
def _self_sha256():
    return hashlib.sha256(Path(__file__).resolve().read_bytes()).hexdigest()


def _canonical_day_payload_v3_v4(prediction_rows, model_rows, verifier_sha256):
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


def _canonical_day_payload(schema_version, prediction_rows, model_rows, verifier_sha256):
    handler = _SCHEMA_HANDLERS.get(schema_version)
    if handler == "v3_v4":
        return _canonical_day_payload_v3_v4(prediction_rows, model_rows, verifier_sha256)
    raise ValueError(
        f"Unsupported manifest_schema_version: {schema_version}. "
        f"This verifier supports versions: {sorted(_SCHEMA_HANDLERS)}. "
        f"Check out the verify.py at the commit that published this anchor."
    )


def _canonical_row_payload(row):
    payload = {f: row.get(f) for f in _CONTENT_HASH_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _load_salt(salt_path):
    text = Path(salt_path).read_text().strip()
    try:
        return bytes.fromhex(text)
    except ValueError:
        import base64
        return base64.b64decode(text)


# =============================================================================
# Mode A — anchor verification
# =============================================================================
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
    verifier_hash = _self_sha256()

    anchor_path = Path(repo_root) / "anchors" / f"{date_str}.json"
    if not anchor_path.exists():
        print(f"ERROR: anchor file not found: {anchor_path}", file=sys.stderr)
        print("       (Are you running from the audit_trail repo root, "
              "or pass --repo-root?)", file=sys.stderr)
        return 2

    anchor = json.loads(anchor_path.read_text())
    published_hash = anchor.get("manifest_hash")
    anchored_verifier = anchor.get("verifier_sha256")
    schema_version = anchor.get("manifest_schema_version", 3)

    if anchored_verifier and anchored_verifier != verifier_hash:
        print(f"FAIL  verifier mismatch: this verify.py hashes to {verifier_hash[:16]}… "
              f"but anchor {date_str} expects {anchored_verifier[:16]}…", file=sys.stderr)
        print("      The verifier has been altered since this anchor was published. "
              "Refusing to verify; recheck out the repository at the commit that "
              "produced this anchor and re-run.", file=sys.stderr)
        return 1

    try:
        payload = _canonical_day_payload(schema_version, prediction_rows, model_rows, verifier_hash)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    recomputed = hashlib.sha256(payload + salt).hexdigest()

    if recomputed == published_hash:
        print(f"PASS  anchor {date_str} (schema v{schema_version}): "
              f"{len(prediction_rows)} predictions + {len(model_rows)} new model "
              f"registrations hash to {recomputed[:16]}… which matches the published "
              f"anchor (verifier_sha256 {verifier_hash[:16]}… also matches)")
        return 0
    print(f"FAIL  anchor {date_str}: recomputed {recomputed[:16]}…  "
          f"published {published_hash[:16]}…", file=sys.stderr)
    print("      The rows + salt you provided do not match what was committed "
          "to the repository for this date.", file=sys.stderr)
    return 1


# =============================================================================
# Mode B — content verification
# =============================================================================
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


# =============================================================================
# Mode C — Bitcoin attestation verification
# =============================================================================
# Lifted from the retired verify_bitcoin.py (pre-v1.0). Trust model unchanged:
# trustless verification requires a local Bitcoin Core node, since the
# OpenTimestamps client has no public-explorer fallback for confirming that
# "block N's merkle root is really Bitcoin's." `--offline` reads each proof's
# on-chain claim without a node; `--digests` skips OTS entirely and just
# prints the anchor file sha256s.
_BLOCK_RE = re.compile(r"[Bb]itcoin block (\d+) attests existence as of (.+)")


def _anchor_sha256(anchor_path):
    return hashlib.sha256(anchor_path.read_bytes()).hexdigest()


def _ots_path():
    return shutil.which("ots")


def _list_anchor_dates(repo_root, only_date):
    anchors_dir = repo_root / "anchors"
    if only_date:
        return [only_date]
    dates = []
    for p in sorted(anchors_dir.glob("*.json")):
        if (anchors_dir / f"{p.name}.ots").exists():
            dates.append(p.stem)
    return dates


def _classify_verify(combined):
    low = combined.lower()
    if ("could not connect to bitcoin" in low or "cookie file" in low
            or "no bitcoin" in low or ("bitcoin node" in low and "connect" in low)):
        return "no_node", "no local Bitcoin node reachable — required for the trustless check (no explorer fallback)"
    m = _BLOCK_RE.search(combined)
    if m:
        return "confirmed", f"block {m.group(1)}  {m.group(2).strip()}"
    if "success" in low and "bitcoin" in low:
        return "confirmed", combined.strip().splitlines()[-1][:80]
    if "pending" in low or "not yet" in low or "incomplete" in low:
        return "pending", "not yet on-chain — run `ots upgrade` first"
    return "failed", (combined.strip().splitlines() or ["no output"])[-1][:120]


def _classify_info(combined):
    m = re.search(r"[Bb]itcoin block (?:header attestation\()?(\d+)", combined)
    if "BitcoinBlockHeaderAttestation" in combined or m:
        return "on-chain", (f"proof carries a Bitcoin attestation (block {m.group(1)})" if m
                            else "proof carries a Bitcoin attestation")
    if "PendingAttestation" in combined or "pending" in combined.lower():
        return "pending", "calendar-pending; not yet upgraded — run `ots upgrade`"
    return "unknown", (combined.strip().splitlines() or ["no output"])[-1][:120]


def _run_subprocess(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return "TIMEOUT: ots did not return within 180s (network?)"
    return (r.stdout or "") + (r.stderr or "")


def _verify_bitcoin(date_str, repo_root, offline, digests_only):
    root = Path(repo_root).resolve()
    anchors_dir = root / "anchors"
    if not anchors_dir.is_dir():
        print(f"ERROR: no anchors/ directory under {root} "
              f"(run from the repo root, or pass --repo-root).", file=sys.stderr)
        return 2

    dates = _list_anchor_dates(root, date_str)
    if not dates:
        print("ERROR: no anchor files found.", file=sys.stderr)
        return 2

    # --digests: pure-stdlib, offline, no ots. Just the file -> digest binding.
    if digests_only:
        for d in dates:
            anchor = anchors_dir / f"{d}.json"
            print(f"{d}  sha256={_anchor_sha256(anchor)}" if anchor.exists()
                  else f"{d}  MISSING anchors/{d}.json")
        return 0

    ots = _ots_path()
    if ots is None:
        print("ERROR: the `ots` command was not found.\n"
              "       Install the OpenTimestamps reference client (pinned):\n"
              "           pip install -r requirements-bitcoin.txt\n"
              "       (`bitcoin --digests` works without it — prints the anchor file hashes.)",
              file=sys.stderr)
        return 2

    failures = 0
    pendings = 0
    no_nodes = 0
    print(f"{'DATE':<12} {'ANCHOR SHA-256':<18} STATUS")
    print("-" * 72)
    for d in dates:
        anchor = anchors_dir / f"{d}.json"
        ots_file = anchors_dir / f"{d}.json.ots"
        if not anchor.exists() or not ots_file.exists():
            print(f"{d:<12} {'-':<18} FAILED   missing anchor or .ots file")
            failures += 1
            continue
        digest = _anchor_sha256(anchor)
        short = digest[:16] + "…"

        if offline:
            status, detail = _classify_info(_run_subprocess([ots, "info", str(ots_file)]))
            tag = {"on-chain": "ON-CHAIN", "pending": "PENDING", "unknown": "UNKNOWN"}[status]
            pendings += status == "pending"
            print(f"{d:<12} {short:<18} {tag:<9} {detail}")
            continue

        # Online verify against your Bitcoin node: binds file -> digest -> block.
        status, detail = _classify_verify(_run_subprocess([ots, "verify", "-d", digest, str(ots_file)]))
        tag = {"confirmed": "CONFIRMED", "pending": "PENDING",
               "no_node": "NO-NODE", "failed": "FAILED"}[status]
        failures += status == "failed"
        pendings += status == "pending"
        no_nodes += status == "no_node"
        print(f"{d:<12} {short:<18} {tag:<9} {detail}")

    print("-" * 72)
    ok = len(dates) - failures - pendings - no_nodes
    print(f"{len(dates)} anchor(s): {ok} confirmed, {pendings} pending, "
          f"{no_nodes} need-a-node, {failures} failed.")
    if no_nodes and not offline:
        print("To run the trustless Bitcoin check you need a local Bitcoin Core node "
              "(pruned is fine). Until then, `--offline` reads the block attestation each "
              "proof already carries.")
    if failures:
        return 1
    if no_nodes:
        return 2
    return 0


# =============================================================================
# CLI
# =============================================================================
def main():
    p = argparse.ArgumentParser(
        description="Independent verifier for EdgeSeeker audit_trail anchors. "
                    "Subcommands: anchor (Mode A), content (Mode B), bitcoin (Mode C).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="mode", required=True)

    a = sub.add_parser("anchor", help="Verify a daily anchor (Mode A)")
    a.add_argument("--date", required=True, help="anchor date in YYYY-MM-DD")
    a.add_argument("--predictions", required=True,
                   help="path to predictions subset JSON (id, content_hash, recorded_at)")
    a.add_argument("--models", default=None,
                   help="optional path to new_models subset JSON; required only on days "
                        "whose anchor includes model registrations")
    a.add_argument("--salt", required=True, help="path to salt file (hex or base64)")
    a.add_argument("--repo-root", default=".",
                   help="path to local clone of this repository (default: cwd)")

    c = sub.add_parser("content", help="Verify per-row content hashes (Mode B)")
    c.add_argument("--predictions", required=True,
                   help="path to predictions full JSON (id, content_hash, all hashed fields)")

    b = sub.add_parser("bitcoin",
                       help="Verify Bitcoin OpenTimestamps attestation on anchors (Mode C)")
    b.add_argument("--date", default=None, help="verify a single anchor date (YYYY-MM-DD)")
    b.add_argument("--repo-root", default=".",
                   help="path to a clone of this repo (default: cwd)")
    b.add_argument("--offline", action="store_true",
                   help="read each proof's on-chain attestation via `ots info` — no node, no network")
    b.add_argument("--digests", action="store_true",
                   help="print the sha256 of each anchor file and exit (no `ots`, no network)")

    args = p.parse_args()

    if args.mode == "anchor":
        sys.exit(_verify_anchor(args.date, args.predictions, args.models, args.salt, args.repo_root))
    if args.mode == "content":
        sys.exit(_verify_content(args.predictions))
    if args.mode == "bitcoin":
        sys.exit(_verify_bitcoin(args.date, args.repo_root, args.offline, args.digests))


if __name__ == "__main__":
    main()
