"""Plan and optionally apply the next daily Skills release."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / ".claude-plugin/plugin.json"
MARKETPLACE = ROOT / ".claude-plugin/marketplace.json"
SUPPORT = ROOT / "contracts/launch-support-manifest.json"
RELEASE_PATHS = ("skills", "contracts", ".claude-plugin", "README.md", "CHANGELOG.md")
VERSION = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=check)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def latest_tag() -> tuple[str, str]:
    tags = git("tag", "--list", "skills-v*").stdout.splitlines()
    versions = []
    for tag in tags:
        value = tag.removeprefix("skills-v")
        if VERSION.fullmatch(value):
            versions.append((tuple(map(int, value.split("."))), tag))
    if not versions:
        raise ValueError("No previous Skills release tag")
    parts, tag = max(versions)
    git("merge-base", "--is-ancestor", tag, "HEAD")
    return ".".join(map(str, parts)), tag


def plan(apply: bool) -> dict:
    plugin = read_json(PLUGIN)
    marketplace = read_json(MARKETPLACE)
    support = read_json(SUPPORT)
    current = plugin["version"]
    if not VERSION.fullmatch(current):
        raise ValueError("plugin version must be major.minor.patch")
    if any(item.get("version") != current for item in marketplace["plugins"]):
        raise ValueError("marketplace versions differ from the plugin")
    if support.get("skills_version") != current:
        raise ValueError("launch support manifest version differs from the plugin")
    previous, tag = latest_tag()
    current_parts, previous_parts = tuple(map(int, current.split("."))), tuple(map(int, previous.split(".")))
    if current_parts < previous_parts:
        raise ValueError(f"source {current} is behind published {previous}")
    if current_parts > previous_parts:
        target, bump = current, False
    else:
        diff = git("diff", "--quiet", tag, "HEAD", "--", *RELEASE_PATHS, check=False)
        if diff.returncode not in (0, 1):
            raise RuntimeError(diff.stderr)
        if diff.returncode == 0:
            return {"action": "skip", "version": current, "baseline": tag}
        target, bump = f"{current_parts[0]}.{current_parts[1]}.{current_parts[2] + 1}", True
    if apply and bump:
        plugin["version"] = target
        for item in marketplace["plugins"]:
            item["version"] = target
        support["skills_version"] = target
        write_json(PLUGIN, plugin)
        write_json(MARKETPLACE, marketplace)
        write_json(SUPPORT, support)
    return {"action": "publish", "version": target, "bump": bump, "commit": bump, "baseline": tag}


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--apply", action="store_true")
        args = parser.parse_args()
        print(json.dumps(plan(args.apply), sort_keys=True))
    except (ValueError, RuntimeError, subprocess.CalledProcessError, OSError) as error:
        print(f"daily Skills release planning failed: {error}", file=sys.stderr)
        sys.exit(1)
