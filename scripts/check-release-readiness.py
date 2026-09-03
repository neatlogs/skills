#!/usr/bin/env python3
"""Fail Skill publication until every contracted SDK/Wizard release exists."""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPPORT = ROOT / "contracts" / "skills-support-v1.json"
MINIMUM = re.compile(r"^>=(\d+\.\d+\.\d+)(?:\s|$)")


def minimum_version(version_range: str) -> str:
    match = MINIMUM.match(version_range)
    if not match:
        raise ValueError(f"release range must start with an exact minimum: {version_range}")
    return match.group(1)


def release_targets() -> list[tuple[str, str]]:
    contract = json.loads(SUPPORT.read_text(encoding="utf-8"))
    stacks = contract["stacks"]
    wizard_version = minimum_version(contract["wizard"]["version_range"])
    python_version = minimum_version(stacks["python"]["sdk"]["version_range"])
    typescript_version = minimum_version(
        stacks["typescript"]["sdk"]["version_range"]
    )
    go_version = minimum_version(stacks["go"]["sdk"]["version_range"])
    return [
        (
            f"@neatlogs/wizard@{wizard_version}",
            f"https://registry.npmjs.org/%40neatlogs%2Fwizard/{wizard_version}",
        ),
        (
            f"neatlogs (npm)@{typescript_version}",
            f"https://registry.npmjs.org/neatlogs/{typescript_version}",
        ),
        (
            f"neatlogs (PyPI)=={python_version}",
            f"https://pypi.org/pypi/neatlogs/{python_version}/json",
        ),
        (
            f"neatlogs-go@v{go_version}",
            "https://api.github.com/repos/neatlogs/neatlogs-go/git/ref/"
            f"tags/v{go_version}",
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate release targets without accessing registries.",
    )
    args = parser.parse_args()
    targets = release_targets()
    if args.validate_only:
        print("Validated release-order targets: " + ", ".join(name for name, _ in targets))
        return 0

    failures: list[str] = []
    for name, url in targets:
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "neatlogs-skills-release"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                if response.status != 200:
                    failures.append(f"{name}: HTTP {response.status}")
        except (urllib.error.URLError, TimeoutError) as exc:
            failures.append(f"{name}: {exc}")
    if failures:
        raise SystemExit(
            "Required public releases are missing; publish SDKs and Wizard first:\n- "
            + "\n- ".join(failures)
        )
    print("All contracted SDK and Wizard releases are public")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
