#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later

import argparse
import json
import re
from collections import Counter
from pathlib import Path


ANSI = re.compile(r"\x1b\[[0-9;]*[mK]")
FAILURE = re.compile(r"^ FAIL  (.+)$", re.MULTILINE)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument(
        "--expectations",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tests/expected-upstream-divergences.json",
    )
    args = parser.parse_args()

    expected_document = json.loads(args.expectations.read_text(encoding="utf-8"))
    expected = [entry["name"] for entry in expected_document["expected"]]
    failures = FAILURE.findall(ANSI.sub("", args.log.read_text(encoding="utf-8", errors="replace")))
    expected_counts = Counter(expected)
    actual_counts = Counter(failures)
    unexpected = list((actual_counts - expected_counts).elements())
    missing = list((expected_counts - actual_counts).elements())

    if unexpected:
        print("unexpected upstream-suite failures:")
        for failure in unexpected:
            print(f"  {failure}")
    if missing:
        print("expected divergences not observed:")
        for failure in missing:
            print(f"  {failure}")
    if unexpected or missing:
        raise SystemExit(1)
    print(f"classified {len(failures)} intentional downstream divergences")


if __name__ == "__main__":
    main()
