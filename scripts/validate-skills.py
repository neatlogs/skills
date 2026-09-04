#!/usr/bin/env python3
"""Validate public skill packages without executing skill content.

The release workflow packages every ``skills/*/SKILL.md`` directory. This
validator makes that implicit contract a PR gate: package identity, local links,
plugin metadata, and archive boundaries must be correct before publication.
"""

from __future__ import annotations

import hashlib
import json
import math
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
DOCTOR_CONTRACT_DIR = ROOT / "contracts" / "doctor" / "v2"
SUPPORT_MANIFEST = ROOT / "contracts" / "launch-support-manifest.json"
EXPECTED_DIALECT_ORDER = [
    "native-v2",
    "neatlogs-direct",
    "otel-genai",
    "openinference",
    "provider-specific",
    "external-legacy",
    "unknown-raw",
]
DOCTOR_COMMANDS = {
    "python": ("python -m neatlogs doctor --local --json",),
    "typescript": (
        "npm exec --offline --no -- neatlogs doctor --local --json",
        "pnpm exec neatlogs doctor --local --json",
        "yarn run neatlogs doctor --local --json",
        "bun --no-install run neatlogs doctor --local --json",
    ),
    "go": ("neatlogs doctor --local --json",),
}
DOCTOR_PROBE_COMMANDS = {
    language: tuple(command.replace("--local", "--probe") for command in commands)
    for language, commands in DOCTOR_COMMANDS.items()
}
DOWNLOAD_DOCTOR_COMMAND = re.compile(
    r"(?:\bnpx\b|\bpnpm\s+dlx\b|\byarn\s+dlx\b|\bbunx\b|\buvx\b|"
    r"\bpipx\s+run\b|\bgo\s+run\b)[^\n`]*\bdoctor\b",
    re.IGNORECASE,
)
STALE_DOCTOR_PHRASES = (
    "doctor_version: 1",
    "neatlogs.doctor/v1",
    "wizard_sdk_fixture",
    "@neatlogs/wizard@latest doctor",
    "/api/diagnostics/",
    "get_trace_context(verification_marker",
    "neatlogs.verification.marker",
    "neatlogs-verification:",
    "trace_context_contract_version",
    "candidate_offset",
)
INTERNAL_DOCTOR_TERMS = (
    "diagnostic-session",
    "diagnostic-receipt",
    "doctor_probe_stage_receipts",
    "ingestiondiagnostics",
    "kafka topic",
    "clickhouse",
    "postgresql",
    "object key",
    "consumer offset",
    "redis",
    "trace finalizer",
    "raw_durable",
    "storage_consumer",
    "raw_write_failed",
)
EXPECTED_DOCTOR_FIXTURES = {
    "local-pass.json",
    "local-warning.json",
    "probe-pass.json",
    "probe-failure-sanitized.json",
}
SDK_GENERATED_LOCAL_PASS_CHECKS = (
    (
        "local_envelope",
        "LOCAL_ENVELOPE_VALID",
        "NONE",
        "The final normalized local envelope is valid",
    ),
    (
        "controlled_fixture_spans",
        "CONTROLLED_SPANS_VALID",
        "NONE",
        "Doctor captured exactly the four expected semantic spans",
    ),
    (
        "controlled_fixture_hierarchy",
        "CONTROLLED_HIERARCHY_VALID",
        "NONE",
        "Doctor captured the exact root-agent-LLM and root-tool edges",
    ),
    (
        "controlled_fixture_io",
        "CONTROLLED_IO_VALID",
        "NONE",
        "Doctor captured the deterministic non-null input and output values",
    ),
    (
        "controlled_fixture_metadata",
        "CONTROLLED_METADATA_VALID",
        "NONE",
        "Doctor captured all versioned metadata on every semantic span",
    ),
    (
        "controlled_fixture_tokens",
        "CONTROLLED_TOKENS_VALID",
        "NONE",
        "Doctor captured the exact numeric token values",
    ),
    (
        "controlled_fixture_bounds",
        "CONTROLLED_BOUNDS_VALID",
        "NONE",
        "Doctor stayed inside the bounded capture budget",
    ),
)


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
            fields[current_key] = "" if value in {">", "|"} else value.strip("\"' ")
        elif line.strip():
            current_key = None

    raise ValueError("missing closing YAML frontmatter delimiter")


def doctor_language(name: str) -> str | None:
    if name == "neatlogs-go":
        return "go"
    if name == "neatlogs-py" or name.startswith("neatlogs-py-"):
        return "python"
    if name == "neatlogs-ts" or name.startswith("neatlogs-ts-"):
        return "typescript"
    return None


def validate_public_doctor_boundary(text: str, errors: list[str], label: str) -> None:
    lowered = text.lower()
    for phrase in STALE_DOCTOR_PHRASES:
        if phrase.lower() in lowered:
            errors.append(f"{label}: contains stale Doctor guidance {phrase!r}")
    for term in INTERNAL_DOCTOR_TERMS:
        if term.lower() in lowered:
            errors.append(f"{label}: exposes internal Doctor term {term!r}")


def validate_doctor_guidance(
    name: str, manifest_text: str, errors: list[str], label: str
) -> None:
    language = doctor_language(name)
    if language is None:
        return
    gates = list(re.finditer(r"(?m)^## Safety gate\s*$", manifest_text))
    if len(gates) != 1:
        errors.append(f"{label}: SDK skill must define exactly one Safety gate")
        return
    if re.search(r"(?m)^## Doctor gate\s*$", manifest_text):
        errors.append(f"{label}: superseded Doctor gate heading must be removed")
    first_h1 = re.search(r"(?m)^#\s+", manifest_text)
    if first_h1 is None or first_h1.start() > gates[0].start():
        errors.append(f"{label}: Safety gate must follow the skill H1")
    body_match = re.search(
        r"(?ms)^## Safety gate\s*$\n(?P<body>.*?)(?=^#{1,2}\s|\Z)", manifest_text
    )
    if body_match is None:
        errors.append(f"{label}: Safety gate body is unreadable")
        return
    guidance = body_match.group("body")
    for command in (*DOCTOR_COMMANDS[language], *DOCTOR_PROBE_COMMANDS[language]):
        if command not in guidance:
            errors.append(
                f"{label}: Doctor guidance must use installed command {command!r}"
            )
    if DOWNLOAD_DOCTOR_COMMAND.search(guidance):
        errors.append(
            f"{label}: Doctor guidance must not download or execute a remote CLI"
        )
    normalized_guidance = " ".join(guidance.split()).casefold()
    for required in (
        "package manager",
        "installed SDK",
        "latest published stable",
        "never downgrade",
        "fail closed",
        "neatlogs.doctor/v2",
        "runtime.language",
        "runtime.schema_version",
        "reason_code",
        "remediation_code",
        "safe/fixable",
        "explicit user approval",
        "network-free",
        "four-span",
        "/v1/traces",
        "/api/traces/v3/{trace_id}",
        "HTTP 2xx",
        "exporter flush",
        "idempotent",
        "rollback",
        "manual recovery",
    ):
        if required.casefold() not in normalized_guidance:
            errors.append(f"{label}: Doctor guidance must include {required!r}")
    if language == "go":
        for required in (
            "go list -m -f '{{.Version}}' github.com/neatlogs/neatlogs-go",
            "go install github.com/neatlogs/neatlogs-go/cmd/neatlogs@<resolved-module-version>",
            "binary and project module versions match",
        ):
            if required.casefold() not in normalized_guidance:
                errors.append(f"{label}: Go Doctor guidance must include {required!r}")
    if "--api-key" in guidance:
        errors.append(f"{label}: Doctor guidance must not put credentials in arguments")
    validate_public_doctor_boundary(guidance, errors, label)


def local_link_target(markdown: Path, raw_target: str) -> Path | None:
    target = raw_target.strip().strip("<>")
    if not target or target.startswith(
        ("#", "http://", "https://", "mailto:", "app://")
    ):
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

    label = str(manifest.relative_to(ROOT))
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
        errors.append(
            f"{manifest.relative_to(ROOT)}: description exceeds 1024 characters"
        )

    skill_root = skill_dir.resolve()
    manifest_text = manifest.read_text(encoding="utf-8")
    validate_doctor_guidance(name, manifest_text, errors, label)
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
        path_label = str(path.relative_to(ROOT))
        if AWS_ACCESS_KEY.search(decoded):
            errors.append(f"{path.relative_to(ROOT)}: looks like a live AWS access key")
        if "--api-key" in decoded:
            errors.append(
                f"{path_label}: skill commands must not put project credentials in arguments"
            )
        for phrase in STALE_DOCTOR_PHRASES:
            if phrase.lower() in decoded.lower():
                errors.append(
                    f"{path_label}: contains stale Doctor guidance {phrase!r}"
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
        errors.append(
            f"{plugin_path.relative_to(ROOT)}: version {version!r} is not x.y.z"
        )

    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append(
            f"{marketplace_path.relative_to(ROOT)}: plugins must be a non-empty array"
        )
        return

    seen: set[str] = set()
    for entry in plugins:
        if not isinstance(entry, dict):
            errors.append(
                f"{marketplace_path.relative_to(ROOT)}: plugin entry must be an object"
            )
            continue
        name = str(entry.get("name", ""))
        if name in seen:
            errors.append(
                f"{marketplace_path.relative_to(ROOT)}: duplicate plugin {name!r}"
            )
        seen.add(name)
        if name not in skill_names:
            errors.append(
                f"{marketplace_path.relative_to(ROOT)}: plugin {name!r} has no skill directory"
            )
        if str(entry.get("version", "")) != version:
            errors.append(
                f"{marketplace_path.relative_to(ROOT)}: plugin {name!r} version must equal {version}"
            )


def validate_doctor_result_semantics(
    result: dict, errors: list[str], label: str
) -> None:
    checks = result.get("checks", [])
    failed = [
        check
        for check in checks
        if isinstance(check, dict) and check.get("status") == "fail"
    ]
    warned = [
        check
        for check in checks
        if isinstance(check, dict) and check.get("status") == "warn"
    ]
    unknown = [
        check
        for check in checks
        if isinstance(check, dict) and check.get("status") == "unknown"
    ]
    expected_failure = failed[0].get("reason_code") if failed else None
    if result.get("first_failure") != expected_failure:
        errors.append(f"{label}: first_failure must match first failed check")
    status = result.get("status")
    if status == "pass" and (failed or warned or unknown):
        errors.append(f"{label}: pass can contain only passing checks")
    elif status == "warn" and (failed or not warned):
        errors.append(f"{label}: warn requires warnings and no failed checks")
    elif status == "fail" and not failed:
        errors.append(f"{label}: fail requires a failed check")
    for check in checks:
        details = check.get("details") if isinstance(check, dict) else None
        if details is not None and (
            not isinstance(details, dict)
            or any(
                value is not None
                and (
                    not isinstance(value, (str, int, float, bool))
                    or (
                        isinstance(value, float)
                        and not math.isfinite(value)
                    )
                )
                for value in details.values()
            )
        ):
            errors.append(
                f"{label}: check details must contain sanitized primitive values only"
            )
    if result.get("mode") == "probe" and status == "pass":
        probe = result.get("probe", {})
        capture = result.get("capture", {})
        required_true = (
            "visible",
            "finalized",
            "hierarchy_valid",
            "attributes_valid",
            "input_output_valid",
            "metadata_valid",
            "typed_tokens_valid",
        )
        if (
            capture.get("span_count") != 4
            or probe.get("readback_span_count") != 4
            or probe.get("meaningful_root_count") != 1
            or probe.get("duplicate_span_count") != 0
            or probe.get("readback_trace_id") != capture.get("trace_id")
            or any(probe.get(field) is not True for field in required_true)
        ):
            errors.append(
                f"{label}: passing probe must prove the exact four-span trace"
            )


def validate_doctor_contract(errors: list[str]) -> None:
    schema_path = DOCTOR_CONTRACT_DIR / "neatlogs-doctor.schema.json"
    fixture_dir = DOCTOR_CONTRACT_DIR / "fixtures"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"Doctor v2 schema is unreadable: {exc}")
        return
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        errors.append(f"{schema_path.relative_to(ROOT)}: invalid JSON Schema: {exc}")
        return
    for path in sorted(DOCTOR_CONTRACT_DIR.rglob("*")):
        if path.is_file():
            validate_public_doctor_boundary(
                path.read_text(encoding="utf-8"),
                errors,
                str(path.relative_to(ROOT)),
            )

    fixture_paths = sorted(fixture_dir.glob("*.json"))
    names = {path.name for path in fixture_paths}
    if names != EXPECTED_DOCTOR_FIXTURES:
        errors.append(
            "Doctor v2 fixtures must be exactly "
            + ", ".join(sorted(EXPECTED_DOCTOR_FIXTURES))
        )
    validator = Draft202012Validator(schema)
    fixtures: dict[str, dict] = {}
    for path in fixture_paths:
        try:
            fixture = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: unreadable: {exc}")
            continue
        fixtures[path.name] = fixture
        for validation_error in sorted(
            validator.iter_errors(fixture), key=lambda item: list(item.path)
        ):
            location = (
                ".".join(str(item) for item in validation_error.absolute_path) or "$"
            )
            errors.append(
                f"{path.relative_to(ROOT)}:{location}: {validation_error.message}"
            )
        validate_doctor_result_semantics(fixture, errors, str(path.relative_to(ROOT)))

    local_pass = fixtures.get("local-pass.json", {})
    if local_pass.get("mode") != "local" or local_pass.get("status") != "pass":
        errors.append("local-pass Doctor fixture must be a passing local result")
    emitted_checks = tuple(
        (
            check.get("name"),
            check.get("reason_code"),
            check.get("remediation_code"),
            check.get("message"),
        )
        for check in local_pass.get("checks", [])
    )
    if emitted_checks != SDK_GENERATED_LOCAL_PASS_CHECKS:
        errors.append(
            "local-pass Doctor fixture must match the SDK-generated success checks"
        )
    local_warning = fixtures.get("local-warning.json", {})
    if (
        local_warning.get("status") != "warn"
        or local_warning.get("first_failure") is not None
    ):
        errors.append("local-warning Doctor fixture must warn without first_failure")
    probe_pass = fixtures.get("probe-pass.json", {})
    probe = probe_pass.get("probe", {})
    capture = probe_pass.get("capture", {})
    if (
        probe_pass.get("mode") != "probe"
        or probe_pass.get("status") != "pass"
        or capture.get("span_count") != 4
        or probe.get("readback_span_count") != 4
        or probe.get("meaningful_root_count") != 1
        or probe.get("duplicate_span_count") != 0
        or probe.get("readback_trace_id") != capture.get("trace_id")
    ):
        errors.append("probe-pass Doctor fixture must prove the exact four-span trace")
    for fixture_name in ("local-pass.json", "probe-pass.json"):
        for check in fixtures.get(fixture_name, {}).get("checks", []):
            if (
                check.get("status") == "pass"
                and check.get("remediation_code") != "NONE"
            ):
                errors.append(
                    f"{fixture_name}: passing SDK checks must use remediation NONE"
                )
    token_check = next(
        (
            check
            for check in probe_pass.get("checks", [])
            if check.get("name") == "probe_typed_tokens"
        ),
        {},
    )
    token_details = token_check.get("details", {})
    if token_details != {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    } or any(isinstance(value, bool) for value in token_details.values()):
        errors.append("probe-pass Doctor fixture must preserve numeric 11/7/18 tokens")
    # Reason/remediation codes are open for forward-compatible SDK additions.
    future = json.loads(json.dumps(local_warning))
    if future.get("checks"):
        future["checks"][0]["reason_code"] = "FUTURE_REASON_2027"
        future["checks"][0]["remediation_code"] = "FUTURE_REMEDIATION_2027"
        if not validator.is_valid(future):
            errors.append(
                "Doctor v2 schema must accept forward-compatible reason codes"
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
        errors.append(
            f"{manifest_path.relative_to(ROOT)}: schema_id must equal schema $id"
        )

    try:
        Draft202012Validator.check_schema(schema)
    except Exception as exc:  # jsonschema includes the failing schema path.
        errors.append(f"{schema_path.relative_to(ROOT)}: invalid JSON Schema: {exc}")
        return

    policy = schema.get("x-neatlogs-policy", {})
    if policy.get("contract_version") != manifest.get("contract_version"):
        errors.append("contract version differs between schema policy and manifest")
    if policy.get("conflict_precedence") != EXPECTED_DIALECT_ORDER:
        errors.append(
            "canonical conflict precedence changed without a v2 contract update"
        )
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
            location = (
                ".".join(str(item) for item in validation_error.absolute_path) or "$"
            )
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
        errors.append(
            "LLM golden fixture must prove direct NeatLogs tool-call ID precedence"
        )

    execution = fixtures.get("tool-execution-envelope.json", {})
    if execution.get("kind") != "TOOL" or execution.get("semantic", {}).get(
        "requesting_span_id"
    ) != llm.get("span_id"):
        errors.append(
            "tool execution golden fixture must be a separate linked TOOL span"
        )
    expected_call_id = tool_calls[0].get("id") if tool_calls else None
    if execution.get("semantic", {}).get("call", {}).get("id") != expected_call_id:
        errors.append(
            "assistant tool request and execution must retain the same call ID"
        )

    unlinked = fixtures.get("unlinked-tool-envelope.json", {})
    if (
        unlinked.get("kind") != "TOOL"
        or unlinked.get("semantic", {}).get("requesting_span_id") is not None
    ):
        errors.append(
            "unlinked TOOL fixture must remain standalone and explicitly unlinked"
        )

    recovered = fixtures.get("recovered-root-envelope.json", {})
    recovery = recovered.get("semantic", {}).get("recovery", {})
    if recovered.get("status", {}).get("code") == "OK":
        errors.append("recovered root golden fixture must not fabricate OK")
    if (
        recovery.get("synthetic") is not True
        or recovery.get("genuine_root_span_id") is not None
    ):
        errors.append(
            "recovered root golden fixture must preserve explicit recovery identity"
        )

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


def validate_launch_support_manifest(errors: list[str]) -> None:
    try:
        support = json.loads(SUPPORT_MANIFEST.read_text(encoding="utf-8"))
        plugin = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"launch support manifest is unreadable: {exc}")
        return
    if support.get("format_version") != "neatlogs.launch-support/v1":
        errors.append("launch support manifest has an unsupported format_version")
    if support.get("skills_version") != plugin.get("version"):
        errors.append("launch support manifest skills version is stale")
    if support.get("doctor_contract") != "neatlogs.doctor/v2":
        errors.append("launch support manifest must pin Doctor v2")
    validate_public_doctor_boundary(
        SUPPORT_MANIFEST.read_text(encoding="utf-8"),
        errors,
        str(SUPPORT_MANIFEST.relative_to(ROOT)),
    )
    schema_path = ROOT / "contracts" / str(support.get("doctor_schema", ""))
    if not schema_path.is_file():
        errors.append("launch support manifest Doctor schema path is invalid")
    elif (
        support.get("doctor_schema_sha256")
        != hashlib.sha256(schema_path.read_bytes()).hexdigest()
    ):
        errors.append("launch support manifest Doctor schema digest is stale")
    if "wizard" in support:
        errors.append("launch support manifest must not depend on Wizard")
    if support.get("doctor_transport") != {
        "ingest_route": "/v1/traces",
        "read_route": "/api/traces/v3/{trace_id}",
        "marker_header": "x-neatlogs-doctor",
        "marker_value": "v1",
    }:
        errors.append("launch support manifest has a stale public Doctor transport")
    if support.get("integration_classes") != [
        "automatic",
        "wrapper",
        "unsupported",
    ]:
        errors.append("launch support manifest integration classes changed")
    expected_packages = {
        "python": "neatlogs",
        "typescript": "neatlogs",
        "go": "github.com/neatlogs/neatlogs-go",
    }
    sdks = support.get("sdks", {})
    if set(sdks) != set(expected_packages):
        errors.append("launch support manifest SDK language set changed")
    for language in expected_packages:
        sdk = support.get("sdks", {}).get(language, {})
        if sdk.get("package") != expected_packages[language]:
            errors.append(f"launch support manifest has the wrong {language} package")
        if "supported_versions" in sdk:
            errors.append(
                f"launch support manifest must not pin {language} patch versions"
            )
        if sdk.get("version_policy") != "latest_published_stable":
            errors.append(
                f"launch support manifest has the wrong {language} version policy"
            )
        if sdk.get("compatibility") != "accept_newer_compatible_releases":
            errors.append(
                f"launch support manifest must accept newer compatible {language} releases"
            )
        if sdk.get("never_downgrade") is not True:
            errors.append(
                f"launch support manifest must never downgrade {language}"
            )
        if sdk.get("doctor_capability") != {
            "format_version": "neatlogs.doctor/v2",
            "runtime_language": language,
            "schema_version": "2",
        }:
            errors.append(
                f"launch support manifest has the wrong {language} Doctor capability"
            )
        if sdk.get("transport") != "otlp_http_protobuf":
            errors.append(f"launch support manifest has the wrong {language} transport")
    if support.get("unsupported_version_behavior") != {
        "mode": "fail_closed",
        "action": "upgrade_to_latest_published_stable_and_rerun_local_doctor",
        "when_latest_lacks_capability": "manual_or_support_remediation",
        "preserve_newer_compatible_versions": True,
    }:
        errors.append("launch support manifest must fail closed for unsupported versions")


def validate_publishing_workflow(errors: list[str]) -> None:
    path = ROOT / ".github" / "workflows" / "publish-skills.yml"
    try:
        workflow = path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"publishing workflow is unreadable: {exc}")
        return
    for required in (
        "git ls-remote --exit-code --tags origin",
        "Release tag ${RELEASE_TAG} already exists",
        "python scripts/validate-skills.py",
        "python -m pytest -q",
    ):
        if required not in workflow:
            errors.append(f"publishing workflow lacks protection {required!r}")


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
    validate_doctor_contract(errors)
    validate_launch_support_manifest(errors)
    validate_publishing_workflow(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Validated {len(names)} public skill packages, telemetry v2, and Doctor v2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
