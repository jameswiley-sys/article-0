#!/usr/bin/env python3
"""
Self-contained SHA-256 hash chain and Merkle root verifier for Article 0.
Zero external dependencies required (Python 3 standard library only).

Usage:
    python3 audit/verify_chain.py
"""

import csv
import hashlib
import sys
from pathlib import Path

AUDIT_DIR = Path(__file__).resolve().parent
CSV_PATH = AUDIT_DIR / "agent-task-chain.csv"
ROOT_PATH = AUDIT_DIR / "CHAIN_ROOT.txt"

FORBIDDEN_CATEGORIES = {
    "ballot_cast",
    "ballot_tabulation",
    "ballot_adjudication",
    "election_certification",
    "unauthorized_voter_record_access",
}

def compute_merkle_root(leaves):
    if not leaves:
        return "0" * 64
    level = list(leaves)
    while len(level) > 1:
        if len(level) % 2 == 1:
            level.append(level[-1])
        next_level = []
        for i in range(0, len(level), 2):
            combined = (level[i] + level[i + 1]).encode("utf-8")
            next_level.append(hashlib.sha256(combined).hexdigest())
        level = next_level
    return level[0]

def main():
    if not CSV_PATH.exists() or not ROOT_PATH.exists():
        print("ERROR: Missing agent-task-chain.csv or CHAIN_ROOT.txt", file=sys.stderr)
        sys.exit(1)

    manifest = {}
    for line in ROOT_PATH.read_text(encoding="utf-8").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            manifest[k.strip()] = v.strip()

    raw_bytes = CSV_PATH.read_bytes()
    actual_file_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    prev_hash = "0" * 64
    leaf_hashes = []
    row_count = 0

    with CSV_PATH.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header != ["timestamp", "bot_role_name", "task_category", "compliance_gate_verdict"]:
            print(f"ERROR: Invalid CSV header: {header}", file=sys.stderr)
            sys.exit(1)

        for idx, row in enumerate(reader, start=1):
            if len(row) != 4:
                print(f"ERROR: Row {idx} does not have exactly 4 columns", file=sys.stderr)
                sys.exit(1)
            ts, bot, cat, verdict = row
            if cat in FORBIDDEN_CATEGORIES:
                print(f"ERROR: Forbidden election task category '{cat}' at row {idx}", file=sys.stderr)
                sys.exit(1)
            line_str = ",".join(row)
            prev_hash = hashlib.sha256(f"{prev_hash}\n{line_str}".encode("utf-8")).hexdigest()
            leaf_hashes.append(hashlib.sha256(line_str.encode("utf-8")).hexdigest())
            row_count += 1

    actual_merkle = compute_merkle_root(leaf_hashes)

    expected_rows = int(manifest.get("total_verified_rows", "-1"))
    expected_file_sha = manifest.get("csv_file_sha256", "")
    expected_tip = manifest.get("sequential_chain_tip_sha256", "")
    expected_merkle = manifest.get("merkle_root_sha256", "")

    print("Article 0 Operational Audit Log Verifier")
    print("========================================")
    print(f"Rule:                   {manifest.get('article_0_rule', '')}")
    print(f"Verified Rows:          {row_count} (expected {expected_rows})")
    print(f"CSV SHA-256:            {actual_file_sha256}")
    print(f"Sequential Chain Tip:   {prev_hash}")
    print(f"Merkle Root SHA-256:    {actual_merkle}")
    print("Forbidden Vote Tasks:   0")

    if (
        row_count != expected_rows
        or actual_file_sha256 != expected_file_sha
        or prev_hash != expected_tip
        or actual_merkle != expected_merkle
    ):
        print("VERIFICATION FAILED: Hash mismatch detected.", file=sys.stderr)
        sys.exit(1)

    print("STATUS:                 VERIFIED OK")

if __name__ == "__main__":
    main()
