#!/usr/bin/env python3
"""Tamper-evidence guard for the public commitment ledger.

Fails CI if a commit touches an already-published ledger artifact. The ledger
is append-only by design; this makes that property mechanically enforced in
public rather than merely asserted in prose. See INTEGRITY.md.

Rules:
  anchors/*.json   append-only — only additions allowed (no modify/rename/delete)
  models/*.json    append-only — only additions allowed
  methodology/*    append-only archive of superseded methodology versions
  anchors/*.ots    may be upgraded in place (modify), but never deleted/renamed
  verify.py        may change deliberately, but any change is surfaced loudly:
                   its sha256 is anchored into every manifest, so a change forks
                   the verifier going forward and never alters past anchors.
"""
from __future__ import annotations

import fnmatch
import os
import subprocess
import sys

APPEND_ONLY = ("anchors/*.json", "models/*.json", "methodology/*")
OTS_NO_REMOVE = ("anchors/*.ots",)


def _matches(path: str, patterns) -> bool:
    return any(fnmatch.fnmatch(path, pat) for pat in patterns)


def main() -> int:
    event = os.environ.get("EVENT", "")
    head = os.environ.get("HEAD_SHA", "")
    if event == "pull_request":
        base = os.environ.get("BASE_SHA", "")
    elif event == "push":
        base = os.environ.get("BEFORE_SHA", "")
        if not base or set(base) <= {"0"}:
            print("No prior commit to compare (new branch / first push); skipping.")
            return 0
    else:
        print(f"Unsupported event '{event}'; skipping.")
        return 0

    if not base or not head:
        print("Missing base/head SHA; skipping.")
        return 0

    diff = subprocess.run(
        ["git", "diff", "--name-status", "-M", base, head],
        capture_output=True, text=True, check=True,
    ).stdout

    violations: list[str] = []
    warnings: list[str] = []

    for line in diff.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0][0]  # A, M, D, R, C
        # rename/copy lines are: "R100\told\tnew" — check both old and new paths
        paths = parts[2:] if code in ("R", "C") else parts[1:]

        for p in paths:
            if _matches(p, APPEND_ONLY) and code != "A":
                violations.append(f"{parts[0]}\t{p}  (append-only: published ledger files are immutable)")
            if _matches(p, OTS_NO_REMOVE) and code in ("D", "R", "C"):
                violations.append(f"{parts[0]}\t{p}  (.ots proofs may be upgraded in place but never removed)")

        if "verify.py" in paths and code != "A":
            warnings.append(line)

    violations = list(dict.fromkeys(violations))  # dedupe, keep order

    for w in warnings:
        print(
            f"::warning title=verify.py changed::{w} — the anchored verifier was modified. "
            f"This forks the verifier going forward and must be a deliberate, reviewed change "
            f"(see INTEGRITY.md). Past anchors remain valid against their original verifier."
        )

    if violations:
        print("::error title=Ledger tamper detected::published, immutable ledger artifacts were modified or removed")
        print("\nAPPEND-ONLY VIOLATIONS:")
        for v in violations:
            print(f"  {v}")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a") as fh:
                fh.write("## ❌ Ledger tamper detected\n\n")
                fh.write("The following published, immutable ledger artifacts were modified, renamed, or deleted:\n\n")
                for v in violations:
                    fh.write(f"- `{v}`\n")
                fh.write("\nThis ledger is append-only (see `INTEGRITY.md`). Revert these changes.\n")
        return 1

    print("OK: no append-only violations — ledger integrity preserved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
