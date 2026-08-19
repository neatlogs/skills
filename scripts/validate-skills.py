#!/usr/bin/env python3
"""Validate public skill packages without executing skill content.

The release workflow packages every ``skills/*/SKILL.md`` directory. This
validator makes that implicit contract a PR gate: package identity, local links,
plugin metadata, and archive boundaries must be correct before publication.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
VALID_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")


def frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing opening YAML frontmatter delimiter")

    fields: dict[str, str] = {}
    current_key: str | None = None
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if line[:1].isspace() and current_key is not None:
            fields[current_key] = f"{fields[current_key]} {line.strip()}".strip()
            continue
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            current_key, value = match.groups()
            fields[current_key] = "" if value in {">", "|"} else value.strip('"\' ')
        elif line.strip():
            current_key = None

    raise ValueError("missing closing YAML frontmatter delimiter")


def local_link_target(markdown: Path, raw_target: str) -> Path | None:
    target = raw_target.strip().strip("<>")
    if not target or target.startswith(("#", "http://", "https://", "mailto:", "app://")):
        return None
    target = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if not target:
        return None
    return (markdown.parent / target).resolve()


def validate_skill(skill_dir: Path, errors: list[str]) -> str | None:
    manifest = skill_dir / "SKILL.md"
    if not manifest.is_file():
        return None

    try:
        metadata = frontmatter(manifest)
    except ValueError as exc:
        errors.append(f"{manifest.relative_to(ROOT)}: {exc}")
        return None

    name = metadata.get("name", "").strip()
    description = metadata.get("description", "").strip()
    if name != skill_dir.name:
        errors.append(
            f"{manifest.relative_to(ROOT)}: frontmatter name {name!r} must match directory {skill_dir.name!r}"
        )
    if not VALID_NAME.fullmatch(name):
        errors.append(f"{manifest.relative_to(ROOT)}: invalid skill name {name!r}")
    if not description or description in {">", "|"}:
        errors.append(f"{manifest.relative_to(ROOT)}: description is required")
    elif len(description) > 1024:
        errors.append(f"{manifest.relative_to(ROOT)}: description exceeds 1024 characters")

    skill_root = skill_dir.resolve()
    for path in sorted(skill_dir.rglob("*")):
        if path.is_symlink():
            resolved = path.resolve()
            if not resolved.is_relative_to(skill_root):
                errors.append(
                    f"{path.relative_to(ROOT)}: symlink escapes its published skill directory"
                )
        if not path.is_file():
            continue
        data = path.read_bytes()
        if AWS_ACCESS_KEY.search(data.decode("utf-8", errors="ignore")):
            errors.append(f"{path.relative_to(ROOT)}: looks like a live AWS access key")
        if path.suffix.lower() not in {".md", ".markdown"}:
            continue
        text = data.decode("utf-8")
        for target in MARKDOWN_LINK.findall(text):
            resolved = local_link_target(path, target)
            if resolved is not None and not resolved.exists():
                errors.append(
                    f"{path.relative_to(ROOT)}: local link {target!r} does not exist"
                )

    return name


def validate_plugin_metadata(skill_names: set[str], errors: list[str]) -> None:
    plugin_path = ROOT / ".claude-plugin" / "plugin.json"
    marketplace_path = ROOT / ".claude-plugin" / "marketplace.json"
    try:
        plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"plugin metadata is unreadable: {exc}")
        return

    version = str(plugin.get("version", ""))
    if not SEMVER.fullmatch(version):
        errors.append(f"{plugin_path.relative_to(ROOT)}: version {version!r} is not x.y.z")

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append(f"{marketplace_path.relative_to(ROOT)}: plugins must be a non-empty array")
        return

    seen: set[str] = set()
    for entry in plugins:
        if not isinstance(entry, dict):
            errors.append(f"{marketplace_path.relative_to(ROOT)}: plugin entry must be an object")
            continue
        name = str(entry.get("name", ""))
        if name in seen:
            errors.append(f"{marketplace_path.relative_to(ROOT)}: duplicate plugin {name!r}")
        seen.add(name)
        if name not in skill_names:
            errors.append(f"{marketplace_path.relative_to(ROOT)}: plugin {name!r} has no skill directory")
        if str(entry.get("version", "")) != version:
            errors.append(
                f"{marketplace_path.relative_to(ROOT)}: plugin {name!r} version must equal {version}"
            )


def main() -> int:
    errors: list[str] = []
    names: list[str] = []
    for skill_dir in sorted(path for path in SKILLS_DIR.iterdir() if path.is_dir()):
        name = validate_skill(skill_dir, errors)
        if name:
            names.append(name)

    duplicates = sorted({name for name in names if names.count(name) > 1})
    for name in duplicates:
        errors.append(f"duplicate skill frontmatter name: {name}")

    validate_plugin_metadata(set(names), errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(names)} public skill packages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
