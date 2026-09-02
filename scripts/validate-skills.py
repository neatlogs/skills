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
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import unquote

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
MARKDOWN_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
VALID_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SECRET_PATTERNS = {
    "AWS access key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "provider API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
CONTRACT_DIR = ROOT / "contracts" / "v2"
SUPPORT_PATH = ROOT / "contracts" / "skills-support-v1.json"
RELEASE_BUILDER = ROOT / "scripts" / "build-skill-release.py"
READINESS_MARKER = "<!-- neatlogs-readiness-v1 -->"
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

    manifest_text = manifest.read_text(encoding="utf-8")
    if READINESS_MARKER not in manifest_text:
        errors.append(
            f"{manifest.relative_to(ROOT)}: missing the public compatibility and readiness gate"
        )
    if "@neatlogs/wizard@latest doctor" in manifest_text:
        errors.append(
            f"{manifest.relative_to(ROOT)}: must not substitute the Wizard's bundled Doctor for an SDK Doctor"
        )

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
        decoded = data.decode("utf-8", errors="ignore")
        for secret_name, pattern in SECRET_PATTERNS.items():
            if pattern.search(decoded):
                errors.append(
                    f"{path.relative_to(ROOT)}: looks like a live {secret_name}"
                )
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


def validate_support_contract(skill_names: set[str], errors: list[str]) -> None:
    try:
        support = json.loads(SUPPORT_PATH.read_text(encoding="utf-8"))
        plugin = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        telemetry = json.loads(
            (CONTRACT_DIR / "manifest.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"public Skill support contract is unreadable: {exc}")
        return

    if support.get("format_version") != "neatlogs.skills-support/v1":
        errors.append("skills-support-v1.json: wrong format_version")
    if support.get("skills_version") != plugin.get("version"):
        errors.append("skills-support-v1.json: skills_version must match plugin version")

    public_telemetry = support.get("telemetry_contract", {})
    for key in ("contract_version", "schema_version", "schema_sha256"):
        if public_telemetry.get(key) != telemetry.get(key):
            errors.append(f"skills-support-v1.json: telemetry {key} is out of sync")

    distribution = support.get("distribution", {})
    version = str(support.get("skills_version", ""))
    if distribution.get("repository") != "neatlogs/skills":
        errors.append("skills-support-v1.json: distribution repository is not canonical")
    if distribution.get("release_tag") != f"skills-v{version}":
        errors.append("skills-support-v1.json: release tag does not match skills_version")
    expected_prefix = (
        f"https://github.com/neatlogs/skills/releases/download/skills-v{version}/"
    )
    if distribution.get("canonical_download_prefix") != expected_prefix:
        errors.append("skills-support-v1.json: canonical download prefix is invalid")

    doctor = support.get("doctor", {})
    if doctor.get("required_format") != "neatlogs.doctor/v2":
        errors.append("skills-support-v1.json: Doctor v2 must remain the required contract")
    if doctor.get("availability") != "not_released":
        errors.append(
            "skills-support-v1.json: do not claim Doctor availability before Phase 9 releases"
        )
    if doctor.get("reason_code") != "DOCTOR_UNAVAILABLE":
        errors.append("skills-support-v1.json: missing stable Doctor unavailable reason")
    if any(
        stack.get("doctor_command") is not None
        for stack in support.get("stacks", {}).values()
        if isinstance(stack, dict)
    ):
        errors.append(
            "skills-support-v1.json: SDK Doctor commands must stay null until released"
        )

    expected_sdk_ranges = {
        "python": ("neatlogs", ">=1.4.21 <2.0.0"),
        "typescript": ("neatlogs", ">=1.1.19 <2.0.0"),
        "go": ("github.com/neatlogs/neatlogs-go", ">=0.1.7 <0.2.0"),
    }
    stacks = support.get("stacks", {})
    for stack_name, (package, version_range) in expected_sdk_ranges.items():
        sdk = stacks.get(stack_name, {}).get("sdk", {})
        if sdk.get("package") != package or sdk.get("version_range") != version_range:
            errors.append(
                f"skills-support-v1.json: {stack_name} SDK range is not the launch baseline"
            )

    expected_typescript_integrations = {
        "anthropic",
        "azure-openai",
        "bedrock",
        "browser",
        "claude-agent-sdk",
        "google-genai",
        "langchain",
        "mastra",
        "openai",
        "openai-agents",
        "opencode",
        "openrouter-agent",
        "pi-agent",
        "vercel-ai",
        "vertex-ai",
    }
    if set(stacks.get("typescript", {}).get("integrations", [])) != expected_typescript_integrations:
        errors.append("skills-support-v1.json: TypeScript integration support drifted")
    unsupported_typescript = set(
        stacks.get("typescript", {}).get("unsupported_surfaces", [])
    )
    if not {
        "edge-runtime",
        "instrumentations-init-option",
        "strands-global-context-hooks",
    }.issubset(unsupported_typescript):
        errors.append("skills-support-v1.json: TypeScript unsupported surfaces drifted")

    backend = support.get("backend_diagnostic", {})
    if (
        backend.get("availability") != "not_deployed"
        or backend.get("reason_code") != "BACKEND_DIAGNOSTIC_UNAVAILABLE"
    ):
        errors.append("skills-support-v1.json: backend probe availability is overstated")

    targets = support.get("skill_targets", {})
    if set(targets) != skill_names:
        missing = sorted(skill_names - set(targets))
        extra = sorted(set(targets) - skill_names)
        errors.append(
            f"skills-support-v1.json: skill_targets mismatch; missing={missing}, extra={extra}"
        )
    for skill_name, target in targets.items():
        if not isinstance(target, dict):
            errors.append(f"skills-support-v1.json: invalid target for {skill_name}")
            continue
        stack_name = target.get("stack")
        integration = target.get("integration")
        if stack_name in {"python", "typescript", "go", "direct-ingest"}:
            supported = set(stacks.get(stack_name, {}).get("integrations", []))
            if integration != "generic" and integration not in supported:
                errors.append(
                    f"skills-support-v1.json: {skill_name} targets unsupported {integration!r}"
                )
        elif stack_name != "multi":
            errors.append(f"skills-support-v1.json: {skill_name} has unknown stack {stack_name!r}")

    allowlist = support.get("safe_fix_allowlist", {})
    if allowlist.get("requires_doctor_format") != "neatlogs.doctor/v2":
        errors.append("skills-support-v1.json: safe fixes must require Doctor v2")
    allowed_codes = {
        item.get("reason_code")
        for item in allowlist.get("entries", [])
        if isinstance(item, dict)
    }
    if allowed_codes != {
        "SDK_VERSION_UNSUPPORTED",
        "INSTRUMENTOR_NOT_ACTIVE",
        "ATTRIBUTE_CONFLICT",
    }:
        errors.append("skills-support-v1.json: safe fix allowlist changed unexpectedly")
    if any(
        not item.get("requires_user_approval")
        for item in allowlist.get("entries", [])
        if isinstance(item, dict)
    ):
        errors.append("skills-support-v1.json: every safe fix must require approval")


def validate_release_assets(skill_names: set[str], errors: list[str]) -> None:
    try:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            for output in (first, second):
                subprocess.run(
                    [sys.executable, str(RELEASE_BUILDER), "--output", output],
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            first_dir = Path(first)
            second_dir = Path(second)
            first_files = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in first_dir.iterdir()
                if path.is_file()
            }
            second_files = {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                for path in second_dir.iterdir()
                if path.is_file()
            }
            if first_files != second_files:
                errors.append("Skill release assets are not reproducible")
                return

            menu = json.loads((first_dir / "skill-menu.json").read_text(encoding="utf-8"))
            if menu.get("formatVersion") != "neatlogs.skill-menu/v1":
                errors.append("skill-menu.json: wrong formatVersion")
            entries = menu.get("categories", {}).get("setup", [])
            if {entry.get("id") for entry in entries} != skill_names:
                errors.append("skill-menu.json: packaged Skill set is incomplete")
            for entry in entries:
                archive = first_dir / f"{entry['id']}.zip"
                data = archive.read_bytes()
                if entry.get("sha256") != hashlib.sha256(data).hexdigest():
                    errors.append(f"skill-menu.json: wrong digest for {entry['id']}")
                if entry.get("bytes") != len(data):
                    errors.append(f"skill-menu.json: wrong byte length for {entry['id']}")
                with zipfile.ZipFile(archive) as package:
                    names = set(package.namelist())
                    expected_support = (
                        f"{entry['id']}/.neatlogs/skills-support-v1.json"
                    )
                    if expected_support not in names:
                        errors.append(f"{archive.name}: missing packaged support contract")
                    if any(
                        name.startswith("/") or ".." in Path(name).parts for name in names
                    ):
                        errors.append(f"{archive.name}: unsafe archive path")

            clean_projects = {
                "python": (
                    "neatlogs-py",
                    {
                        "pyproject.toml": '[project]\nname = "clean-python"\nversion = "0.1.0"\n',
                        "app.py": "def main():\n    return 'clean'\n",
                    },
                    "import neatlogs\nneatlogs.init()\n",
                ),
                "node": (
                    "neatlogs-ts",
                    {
                        "package.json": '{"name":"clean-node","version":"0.1.0"}\n',
                        "index.ts": "export const main = () => 'clean';\n",
                    },
                    "import { init } from 'neatlogs';\nawait init();\n",
                ),
                "go": (
                    "neatlogs-go",
                    {
                        "go.mod": "module example.com/clean\n\ngo 1.25.0\n",
                        "main.go": "package main\n\nfunc main() {}\n",
                    },
                    'package main\n\nimport neatlogs "github.com/neatlogs/neatlogs-go"\n\nvar _ = neatlogs.Version\n',
                ),
            }
            for stack, (skill_id, clean_files, instrumented_source) in clean_projects.items():
                for state in ("clean", "already-instrumented"):
                    with tempfile.TemporaryDirectory() as project_directory:
                        project = Path(project_directory)
                        files = dict(clean_files)
                        source_name = next(
                            name
                            for name in files
                            if name.endswith((".py", ".ts", ".go"))
                        )
                        if state == "already-instrumented":
                            files[source_name] = instrumented_source
                        for relative, content in files.items():
                            target = project / relative
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_text(content, encoding="utf-8")
                        source_digests = {
                            relative: hashlib.sha256((project / relative).read_bytes()).hexdigest()
                            for relative in files
                        }
                        destination = project / ".claude" / "skills"
                        destination.mkdir(parents=True)
                        archive = first_dir / f"{skill_id}.zip"
                        with zipfile.ZipFile(archive) as package:
                            package.extractall(destination)
                        first_install = {
                            path.relative_to(destination).as_posix(): hashlib.sha256(
                                path.read_bytes()
                            ).hexdigest()
                            for path in destination.rglob("*")
                            if path.is_file()
                        }
                        with zipfile.ZipFile(archive) as package:
                            package.extractall(destination)
                        second_install = {
                            path.relative_to(destination).as_posix(): hashlib.sha256(
                                path.read_bytes()
                            ).hexdigest()
                            for path in destination.rglob("*")
                            if path.is_file()
                        }
                        if first_install != second_install:
                            errors.append(
                                f"{stack} {state} Skill installation is not idempotent"
                            )
                        for relative, expected in source_digests.items():
                            actual = hashlib.sha256((project / relative).read_bytes()).hexdigest()
                            if actual != expected:
                                errors.append(
                                    f"{stack} {state} Skill installation modified {relative}"
                                )
    except (OSError, KeyError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        errors.append(f"Skill release asset validation failed: {exc}")


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
    validate_support_contract(set(names), errors)
    validate_release_assets(set(names), errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(names)} public skill packages and canonical telemetry contract v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
