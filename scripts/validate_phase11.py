#!/usr/bin/env python3
"""Validate public Skill packaging and Phase 11 support invariants."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SUPPORT = ROOT / "contracts" / "skills-support-v1.json"
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FRONTMATTER_FIELD = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
LIVE_SECRET_PATTERNS = {
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Neatlogs API key assignment": re.compile(
        r"NEATLOGS_API_KEY\s*=\s*['\"]?[A-Za-z0-9_-]{24,}"
    ),
}
COPYABLE_UNSUPPORTED_TS = re.compile(
    r"(?:await\s+)?init\s*\(\s*\{[^}]*instrumentations\s*:", re.DOTALL
)
EDGE_IMPORT = re.compile(r"from\s+['\"]neatlogs/(?:edge|browser-edge)['\"]")


def parse_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("missing opening frontmatter delimiter")
    result: dict[str, str] = {}
    current: str | None = None
    for line in lines[1:]:
        if line.strip() == "---":
            return result
        if line[:1].isspace() and current:
            result[current] = f"{result[current]} {line.strip()}".strip()
            continue
        match = FRONTMATTER_FIELD.match(line)
        if match:
            current, value = match.groups()
            result[current] = "" if value in {">", "|"} else value.strip("'\" ")
        elif line.strip():
            current = None
    raise ValueError("missing closing frontmatter delimiter")


def local_target(markdown: Path, raw: str) -> Path | None:
    target = raw.strip().strip("<>")
    if not target or target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    target = unquote(target.split("#", 1)[0].split("?", 1)[0])
    return (markdown.parent / target).resolve() if target else None


def validate_support_manifest(errors: list[str]) -> dict:
    try:
        manifest = json.loads(SUPPORT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"support manifest is unreadable: {exc}")
        return {}
    if manifest.get("format_version") != "neatlogs.skills-support/v1":
        errors.append("support manifest format_version must be neatlogs.skills-support/v1")
    contracts = manifest.get("contracts", {})
    expected = {
        "telemetry_schema": 2,
        "doctor_format": "neatlogs.doctor/v2",
        "backend_trace_context": 2,
        "wizard_doctor": "neatlogs.doctor/v2",
    }
    for key, value in expected.items():
        if contracts.get(key) != value:
            errors.append(f"support manifest contract {key} must equal {value!r}")
    ts = manifest.get("stacks", {}).get("typescript", {})
    doctor = ts.get("doctor", {})
    for command in (doctor.get("local_command", ""), doctor.get("probe_command", "")):
        if "npx --no-install neatlogs doctor" not in command:
            errors.append("TypeScript Doctor commands must forbid implicit npx downloads")
    integrations = ts.get("integrations", [])
    ids = [item.get("id") for item in integrations if isinstance(item, dict)]
    if len(ids) != len(set(ids)) or not ids:
        errors.append("TypeScript support integrations must be non-empty and unique")
    if any(item.get("classification") not in {"automatic", "explicit-wrapper", "explicit-hook", "unsupported"} for item in integrations if isinstance(item, dict)):
        errors.append("integration classification is invalid")
    if ts.get("sdk", {}).get("release_state") not in {"released", "pending"}:
        errors.append("TypeScript SDK release_state must be released or pending")
    return manifest


def validate_projection(manifest: dict, errors: list[str]) -> None:
    path = SKILLS / "neatlogs-ts" / "references" / "support-manifest.json"
    try:
        projected = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"TypeScript packaged support manifest is unreadable: {exc}")
        return
    source = manifest.get("stacks", {}).get("typescript", {})
    expected = {
        "format_version": manifest.get("format_version"),
        "skills_version": manifest.get("skills_version"),
        "telemetry_schema": manifest.get("contracts", {}).get("telemetry_schema"),
        "doctor_format": manifest.get("contracts", {}).get("doctor_format"),
        "backend_trace_context": manifest.get("contracts", {}).get("backend_trace_context"),
        "runtime": source.get("runtime"),
        "sdk": {
            "package": source.get("sdk", {}).get("package"),
            "minimum_version": source.get("sdk", {}).get("minimum_version"),
            "release_state": source.get("sdk", {}).get("release_state"),
        },
        "doctor": {
            "local_command": source.get("doctor", {}).get("local_command"),
            "probe_command": source.get("doctor", {}).get("probe_command"),
        },
        "unsupported_surfaces": source.get("unsupported_surfaces"),
    }
    if projected != expected:
        errors.append("packaged TypeScript support manifest differs from canonical projection")


def validate_skills(errors: list[str]) -> int:
    count = 0
    for skill in sorted(path for path in SKILLS.iterdir() if path.is_dir()):
        entry = skill / "SKILL.md"
        if not entry.is_file():
            continue
        count += 1
        try:
            metadata = parse_frontmatter(entry)
        except ValueError as exc:
            errors.append(f"{entry.relative_to(ROOT)}: {exc}")
            continue
        name = metadata.get("name", "")
        if name != skill.name or not NAME.fullmatch(name):
            errors.append(f"{entry.relative_to(ROOT)}: invalid or mismatched name {name!r}")
        if not metadata.get("description"):
            errors.append(f"{entry.relative_to(ROOT)}: description is required")
        root = skill.resolve()
        for path in sorted(skill.rglob("*")):
            if path.is_symlink() and not path.resolve().is_relative_to(root):
                errors.append(f"{path.relative_to(ROOT)}: symlink escapes package")
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for label, pattern in LIVE_SECRET_PATTERNS.items():
                if pattern.search(text):
                    errors.append(f"{path.relative_to(ROOT)}: possible live {label}")
            if skill.name.startswith("neatlogs-ts"):
                if COPYABLE_UNSUPPORTED_TS.search(text):
                    errors.append(f"{path.relative_to(ROOT)}: copyable unsupported instrumentations init")
                if EDGE_IMPORT.search(text):
                    errors.append(f"{path.relative_to(ROOT)}: unsupported Edge import")
            if path.suffix.lower() not in {".md", ".markdown"}:
                continue
            for raw in LINK.findall(text):
                target = local_target(path, raw)
                if target is not None and not target.exists():
                    errors.append(f"{path.relative_to(ROOT)}: broken local link {raw!r}")
    return count


def main() -> int:
    errors: list[str] = []
    manifest = validate_support_manifest(errors)
    validate_projection(manifest, errors)
    count = validate_skills(errors)
    if count != 21:
        errors.append(f"expected 21 public Skills, found {count}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    digest = hashlib.sha256(SUPPORT.read_bytes()).hexdigest()
    print(f"Validated {count} public Skills; support contract sha256:{digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
