#!/usr/bin/env python3
"""Supplemental Bitcoin-attestation verifier for EdgeSeeker audit_trail anchors.

This is an OPTIONAL companion to `verify.py`. It does NOT replace it and does
NOT touch it.

  - `verify.py`         proves predictions + salt -> the published anchor file,
                        dated by that file's GitHub commit timestamp. Pure
                        stdlib, offline, zero third-party dependencies.

  - `verify_bitcoin.py` (this script) adds the second, independent timestamp:
                        it proves each anchor file was committed to the Bitcoin
                        blockchain via its OpenTimestamps (`.ots`) proof -- a
                        timestamp that does not rely on trusting GitHub's clock.

The two share the SAME anchor file (`anchors/YYYY-MM-DD.json`), which is the
hinge: verify.py binds predictions -> anchor file; this binds anchor file ->
Bitcoin block. Together: those predictions existed before that Bitcoin block was
mined.

--------------------------------------------------------------------------------
HOW TO FULLY EXERCISE THIS (the trustless / gold-standard path)
--------------------------------------------------------------------------------

Prerequisites
  - The OpenTimestamps reference client:   pip install -r requirements-bitcoin.txt
    (opentimestamps-client==0.7.2, pinned; provides the `ots` command). We verify
    THROUGH the reference client and never reimplement Bitcoin/merkle validation.
  - A LOCAL BITCOIN NODE (Bitcoin Core; pruned is fine -- it keeps every block
    header, which is all an OTS proof needs). This is REQUIRED for the actual
    Bitcoin check, not optional. See the trust model below.
  - Network access (for `ots upgrade`, if a proof is still pending).

Trust model -- why a node is mandatory, not a convenience
  The cryptographic merkle path inside a `.ots` proof is checked locally, but
  confirming that "block N's merkle root is really Bitcoin's" requires an
  authoritative source for Bitcoin block headers. The OpenTimestamps client has
  NO public-explorer fallback: `ots verify` talks to a local Bitcoin Core node
  (via its cookie / RPC) and fails outright if there isn't one. That is by
  design -- it makes the verification fully trustless (your own node validated
  Bitcoin's consensus; nobody tells you what's in a block). There is no
  "trust a block explorer instead" shortcut in this client.

  Without a node you can still: (a) run `verify.py` for the content+commit
  layer, and (b) use `--offline` here to READ the Bitcoin block attestation each
  (upgraded) proof already contains. But independently CONFIRMING those blocks
  are real is exactly what the node does, and there is no substitute.

Steps (this script automates 2-3 across all anchors; you can also run them by
hand on any single date):
  1. (Only if a proof is still pending) complete it from the calendars:
         ots upgrade anchors/2026-05-20.json.ots
     A verifier should not mutate files, so this script does NOT auto-upgrade;
     the published proofs in this repo are already upgraded/complete.
  2. Verify the proof against the anchor file's hash, using your node:
         ots verify -d <sha256 of anchors/2026-05-20.json> anchors/2026-05-20.json.ots
     -> "Success! Bitcoin block NNN attests existence as of ..."
  3. Join to the content proof: the file hashed here is the same
     `anchors/2026-05-20.json` that `verify.py` matched predictions+salt to.

Usage
  python verify_bitcoin.py                       # all anchors -- needs a node
  python verify_bitcoin.py --date 2026-05-20     # one anchor
  python verify_bitcoin.py --offline             # read each proof's on-chain
                                                 # attestation (block height)
                                                 # from the .ots itself; no node,
                                                 # no network, no block-truth check
  python verify_bitcoin.py --digests             # just the anchor sha256s
                                                 # (no ots, no network)

Exit codes: 0 = every checked proof confirmed (or, with --offline/--digests,
listed); 1 = a proof failed / mismatched; 2 = prerequisite missing (no `ots`,
or `ots verify` could not reach a Bitcoin node) or a usage error. PENDING
proofs are reported and do not by themselves set a non-zero exit.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

_BLOCK_RE = re.compile(r"[Bb]itcoin block (\d+) attests existence as of (.+)")


def _anchor_sha256(anchor_path: Path) -> str:
    return hashlib.sha256(anchor_path.read_bytes()).hexdigest()


def _ots_path() -> str | None:
    return shutil.which("ots")


def _list_anchor_dates(repo_root: Path, only_date: str | None) -> list[str]:
    anchors_dir = repo_root / "anchors"
    if only_date:
        return [only_date]
    dates = []
    for p in sorted(anchors_dir.glob("*.json")):
        if (anchors_dir / f"{p.name}.ots").exists():
            dates.append(p.stem)
    return dates


def _classify_verify(combined: str) -> tuple[str, str]:
    """Map `ots verify` output to (status, detail). status in
    {confirmed, pending, no_node, failed}."""
    low = combined.lower()
    if ("could not connect to bitcoin" in low or "cookie file" in low
            or "no bitcoin" in low or ("bitcoin node" in low and "connect" in low)):
        return "no_node", "no local Bitcoin node reachable -- required for the trustless check (no explorer fallback)"
    m = _BLOCK_RE.search(combined)
    if m:
        return "confirmed", f"block {m.group(1)}  {m.group(2).strip()}"
    if "success" in low and "bitcoin" in low:
        return "confirmed", combined.strip().splitlines()[-1][:80]
    if "pending" in low or "not yet" in low or "incomplete" in low:
        return "pending", "not yet on-chain -- run `ots upgrade` first"
    return "failed", (combined.strip().splitlines() or ["no output"])[-1][:120]


def _classify_info(combined: str) -> tuple[str, str]:
    """Offline classification from `ots info` (no network, no node)."""
    m = re.search(r"[Bb]itcoin block (?:header attestation\()?(\d+)", combined)
    if "BitcoinBlockHeaderAttestation" in combined or m:
        return "on-chain", (f"proof carries a Bitcoin attestation (block {m.group(1)})" if m
                            else "proof carries a Bitcoin attestation")
    if "PendingAttestation" in combined or "pending" in combined.lower():
        return "pending", "calendar-pending; not yet upgraded -- run `ots upgrade`"
    return "unknown", (combined.strip().splitlines() or ["no output"])[-1][:120]


def _run(cmd: list[str]) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return "TIMEOUT: ots did not return within 180s (network?)"
    return (r.stdout or "") + (r.stderr or "")


def main() -> int:
    p = argparse.ArgumentParser(
        description="Supplemental Bitcoin-attestation verifier for audit_trail anchors. "
                    "Trustless verification needs a local Bitcoin node; see the module "
                    "docstring (top of this file) for the full runbook.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--date", default=None, help="verify a single anchor date (YYYY-MM-DD)")
    p.add_argument("--repo-root", default=".", help="path to a clone of this repo (default: cwd)")
    p.add_argument("--offline", action="store_true",
                   help="read each proof's on-chain attestation via `ots info` -- no node, no network")
    p.add_argument("--digests", action="store_true",
                   help="print the sha256 of each anchor file and exit (no `ots`, no network)")
    args = p.parse_args()

    repo_root = Path(args.repo_root).resolve()
    anchors_dir = repo_root / "anchors"
    if not anchors_dir.is_dir():
        print(f"ERROR: no anchors/ directory under {repo_root} "
              f"(run from the repo root, or pass --repo-root).", file=sys.stderr)
        return 2

    dates = _list_anchor_dates(repo_root, args.date)
    if not dates:
        print("ERROR: no anchor files found.", file=sys.stderr)
        return 2

    # --digests: pure-stdlib, offline, no ots. Just the file->digest binding.
    if args.digests:
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
              "       (--digests works without it -- prints the anchor file hashes.)",
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

        if args.offline:
            status, detail = _classify_info(_run([ots, "info", str(ots_file)]))
            tag = {"on-chain": "ON-CHAIN", "pending": "PENDING", "unknown": "UNKNOWN"}[status]
            pendings += status == "pending"
            print(f"{d:<12} {short:<18} {tag:<9} {detail}")
            continue

        # Online verify against your Bitcoin node: binds file -> digest -> block.
        status, detail = _classify_verify(_run([ots, "verify", "-d", digest, str(ots_file)]))
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
    if no_nodes and not args.offline:
        print("To run the trustless Bitcoin check you need a local Bitcoin Core node "
              "(pruned is fine). Until then, `--offline` reads the block attestation each "
              "proof already carries.")
    if failures:
        return 1
    if no_nodes:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
