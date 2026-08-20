#!/usr/bin/env python3
"""Validate public skill packages without executing skill content.

The release workflow packages every ``skills/*/SKILL.md`` directory. This
validator makes that implicit contract a PR gate: package identity, local links,
plugin metadata, and archive boundaries must be correct before publication.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
VALID_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
AWS_ACCESS_KEY = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
CONTRACT_DIR = ROOT / "contracts" / "v2"
EXPECTED_DIALECT_ORDER = [
    "native-v2",
    "neatlogs-direct",
    "otel-genai",
    "openinference",
    "provider-specific",
    "external-legacy",
    "unknown-raw",
]


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


def validate_contract(errors: list[str]) -> None:
    schema_path = CONTRACT_DIR / "neatlogs-telemetry.schema.json"
    manifest_path = CONTRACT_DIR / "manifest.json"
    try:
        schema_bytes = schema_path.read_bytes()
        schema = json.loads(schema_bytes)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"canonical telemetry contract is unreadable: {exc}")
        return

    actual_digest = hashlib.sha256(schema_bytes).hexdigest()
    if manifest.get("schema_sha256") != actual_digest:
        errors.append(
            f"{manifest_path.relative_to(ROOT)}: schema_sha256 must equal {actual_digest}"
        )
    if manifest.get("schema_version") != 2:
        errors.append(f"{manifest_path.relative_to(ROOT)}: schema_version must be 2")
    if schema.get("$id") != manifest.get("schema_id"):
        errors.append(f"{manifest_path.relative_to(ROOT)}: schema_id must equal schema $id")

    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # jsonschema includes the failing schema path.
        errors.append(f"{schema_path.relative_to(ROOT)}: invalid JSON Schema: {exc}")
        return

    policy = schema.get("x-neatlogs-policy", {})
    if policy.get("contract_version") != manifest.get("contract_version"):
        errors.append("contract version differs between schema policy and manifest")
    if policy.get("conflict_precedence") != EXPECTED_DIALECT_ORDER:
        errors.append("canonical conflict precedence changed without a v2 contract update")

    tool_policy = policy.get("tool_calls", {})
    required_tool_policy = {
        "assistant_requests_live_in_assistant_message": True,
        "execution_is_separate_tool_span": True,
        "retain_unlinked_execution": True,
        "forbid_name_timing_merge": True,
    }
    for key, expected in required_tool_policy.items():
        if tool_policy.get(key) is not expected:
            errors.append(f"tool-call policy {key} must remain {expected!r}")

    root_policy = policy.get("root_finalization", {})
    if root_policy.get("launch_sdk_auto_workflow_roots") is not True:
        errors.append("launch contract must retain automatic SDK workflow roots")
    if root_policy.get("launch_completion_markers") is not True:
        errors.append("launch contract must retain completion markers")
    if root_policy.get("recovered_root_status_must_not_be_fabricated_ok") is not True:
        errors.append("recovery contract must forbid fabricated OK status")

    validator = Draft202012Validator(schema)
    golden_paths = sorted((CONTRACT_DIR / "golden").glob("*.json"))
    if not golden_paths:
        errors.append("canonical telemetry contract has no golden fixtures")
        return

    fixtures: dict[str, dict] = {}
    for fixture_path in golden_paths:
        try:
            fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{fixture_path.relative_to(ROOT)}: unreadable: {exc}")
            continue
        fixtures[fixture_path.name] = fixture
        validation_errors = sorted(
            validator.iter_errors(fixture), key=lambda item: list(item.path)
        )
        for validation_error in validation_errors:
            location = ".".join(str(item) for item in validation_error.absolute_path) or "$"
            errors.append(
                f"{fixture_path.relative_to(ROOT)}:{location}: {validation_error.message}"
            )
        if fixture.get("schema_version") != manifest.get("schema_version"):
            errors.append(f"{fixture_path.relative_to(ROOT)}: wrong schema_version")
        semantic = fixture.get("semantic")
        if isinstance(semantic, dict) and semantic.get("kind") != fixture.get("kind"):
            errors.append(
                f"{fixture_path.relative_to(ROOT)}: semantic kind differs from envelope kind"
            )

    llm = fixtures.get("llm-tool-envelope.json", {})
    choices = llm.get("semantic", {}).get("response", {}).get("choices", [])
    if [choice.get("choice_index") for choice in choices] != [0, 1]:
        errors.append("LLM golden fixture must preserve its two indexed choices")
    tool_calls = choices[0].get("message", {}).get("tool_calls", []) if choices else []
    if not tool_calls or tool_calls[0].get("id_origin") != "neatlogs-direct":
        errors.append("LLM golden fixture must prove direct NeatLogs tool-call ID precedence")

    execution = fixtures.get("tool-execution-envelope.json", {})
    if (
        execution.get("kind") != "TOOL"
        or execution.get("semantic", {}).get("requesting_span_id") != llm.get("span_id")
    ):
        errors.append("tool execution golden fixture must be a separate linked TOOL span")
    expected_call_id = tool_calls[0].get("id") if tool_calls else None
    if execution.get("semantic", {}).get("call", {}).get("id") != expected_call_id:
        errors.append("assistant tool request and execution must retain the same call ID")

    unlinked = fixtures.get("unlinked-tool-envelope.json", {})
    if (
        unlinked.get("kind") != "TOOL"
        or unlinked.get("semantic", {}).get("requesting_span_id") is not None
    ):
        errors.append("unlinked TOOL fixture must remain standalone and explicitly unlinked")

    recovered = fixtures.get("recovered-root-envelope.json", {})
    recovery = recovered.get("semantic", {}).get("recovery", {})
    if recovered.get("status", {}).get("code") == "OK":
        errors.append("recovered root golden fixture must not fabricate OK")
    if recovery.get("synthetic") is not True or recovery.get("genuine_root_span_id") is not None:
        errors.append("recovered root golden fixture must preserve explicit recovery identity")

    reconciled = fixtures.get("reconciled-recovery-envelope.json", {})
    reconciliation = reconciled.get("semantic", {}).get("recovery", {})
    if (
        reconciliation.get("reconciled") is not True
        or not reconciliation.get("genuine_root_span_id")
        or reconciled.get("status", {}).get("code") == "OK"
    ):
        errors.append(
            "reconciled recovery fixture must reference the late genuine root without fabricating OK"
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
    validate_contract(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(names)} public skill packages and canonical telemetry contract v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
