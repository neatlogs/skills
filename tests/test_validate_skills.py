from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_skills", ROOT / "scripts" / "validate-skills.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


def guidance(language: str) -> str:
    local = "\n".join(f"`{command}`" for command in VALIDATOR.DOCTOR_COMMANDS[language])
    probe = "\n".join(
        f"`{command}`" for command in VALIDATOR.DOCTOR_PROBE_COMMANDS[language]
    )
    go_install = ""
    if language == "go":
        go_install = """
Resolve `go list -m -f '{{.Version}}' github.com/neatlogs/neatlogs-go`, then
obtain explicit user approval before `go install github.com/neatlogs/neatlogs-go/cmd/neatlogs@<resolved-module-version>`.
Require that the binary and project module versions match.
"""
    return f"""# Example skill

## Safety gate

Detect the package manager and verify the installed SDK. Use the latest published
stable release for upgrade guidance, but never downgrade a newer compatible
release. Fail closed when its capability is unsupported. Run these commands
from the installed SDK:
{local}
Require `neatlogs.doctor/v2` with matching `runtime.language` and
`runtime.schema_version`. Local mode is network-free. Report every `reason_code`
and `remediation_code`; only a code explicitly listed as safe/fixable may change
code. Keep reruns idempotent and provide rollback and manual recovery steps.
{go_install}
Run one matching command only with explicit user approval:
{probe}
The probe emits a controlled four-span trace through `/v1/traces` and reads
`/api/traces/v3/{{trace_id}}`. Never treat HTTP 2xx or exporter flush as proof.

## Next
"""


def doctor_schema() -> dict:
    return json.loads(
        (VALIDATOR.DOCTOR_CONTRACT_DIR / "neatlogs-doctor.schema.json").read_text()
    )


def doctor_fixture(name: str) -> dict:
    return json.loads((VALIDATOR.DOCTOR_CONTRACT_DIR / "fixtures" / name).read_text())


@pytest.mark.parametrize("language", ["python", "typescript", "go"])
def test_exact_installed_doctor_commands_are_accepted(language: str) -> None:
    name = {"python": "neatlogs-py", "typescript": "neatlogs-ts", "go": "neatlogs-go"}[
        language
    ]
    errors: list[str] = []
    VALIDATOR.validate_doctor_guidance(name, guidance(language), errors, "fixture")
    assert errors == []


@pytest.mark.parametrize(
    "download_command",
    [
        "npx neatlogs doctor --local --json",
        "pnpm dlx neatlogs doctor --local --json",
        "uvx neatlogs doctor --local --json",
        "go run example.com/neatlogs/cmd/neatlogs@latest doctor --local --json",
    ],
)
def test_download_based_doctor_commands_are_rejected(download_command: str) -> None:
    text = guidance("python").replace(
        VALIDATOR.DOCTOR_COMMANDS["python"][0], download_command
    )
    errors: list[str] = []
    VALIDATOR.validate_doctor_guidance("neatlogs-py", text, errors, "fixture")
    assert any("must not download" in error for error in errors)


def test_multiple_safety_gates_are_rejected() -> None:
    text = guidance("python") + "\n## Safety gate\nDuplicate.\n"
    errors: list[str] = []
    VALIDATOR.validate_doctor_guidance("neatlogs-py", text, errors, "fixture")
    assert errors == ["fixture: SDK skill must define exactly one Safety gate"]


def test_skill_command_credentials_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(VALIDATOR, "ROOT", tmp_path)
    skill_dir = tmp_path / "skills" / "neatlogs-example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        """---
name: neatlogs-example
description: Example skill.
---

# Example

`tool configure --api-key <PROJECT_KEY>`
"""
    )
    errors: list[str] = []
    VALIDATOR.validate_skill(skill_dir, errors)
    assert any("credentials in arguments" in error for error in errors)


@pytest.mark.parametrize("phrase", VALIDATOR.STALE_DOCTOR_PHRASES)
def test_stale_doctor_phrases_are_rejected(phrase: str) -> None:
    errors: list[str] = []
    VALIDATOR.validate_public_doctor_boundary(phrase, errors, "fixture")
    assert any("stale Doctor guidance" in error for error in errors)


@pytest.mark.parametrize("term", VALIDATOR.INTERNAL_DOCTOR_TERMS)
def test_internal_doctor_topology_is_rejected(term: str) -> None:
    errors: list[str] = []
    VALIDATOR.validate_public_doctor_boundary(term, errors, "fixture")
    assert any("internal Doctor term" in error for error in errors)


def test_canonical_doctor_fixtures_validate() -> None:
    errors: list[str] = []
    VALIDATOR.validate_doctor_contract(errors)
    assert errors == []


def test_nested_diagnostic_details_are_rejected() -> None:
    result = doctor_fixture("probe-failure-sanitized.json")
    result["checks"][0]["details"]["raw"] = {"secret": "value"}
    assert not Draft202012Validator(doctor_schema()).is_valid(result)
    errors: list[str] = []
    VALIDATOR.validate_doctor_result_semantics(result, errors, "fixture")
    assert any("sanitized primitive" in error for error in errors)


def test_first_failure_must_match_first_failed_check() -> None:
    result = doctor_fixture("probe-failure-sanitized.json")
    result["first_failure"] = "SOME_OTHER_FAILURE"
    errors: list[str] = []
    VALIDATOR.validate_doctor_result_semantics(result, errors, "fixture")
    assert errors == ["fixture: first_failure must match first failed check"]


@pytest.mark.parametrize(
    ("status", "check_status", "expected"),
    [
        ("pass", "warn", "pass can contain only passing checks"),
        ("warn", "pass", "warn requires warnings and no failed checks"),
        ("fail", "pass", "fail requires a failed check"),
    ],
)
def test_status_must_match_check_severity(
    status: str, check_status: str, expected: str
) -> None:
    result = doctor_fixture("local-warning.json")
    result["status"] = status
    result["checks"][0]["status"] = check_status
    result["first_failure"] = None
    errors: list[str] = []
    VALIDATOR.validate_doctor_result_semantics(result, errors, "fixture")
    assert any(expected in error for error in errors)


def test_passing_probe_requires_exact_four_span_readback() -> None:
    result = doctor_fixture("probe-pass.json")
    result["probe"]["readback_span_count"] = 3
    errors: list[str] = []
    VALIDATOR.validate_doctor_result_semantics(result, errors, "fixture")
    assert errors == ["fixture: passing probe must prove the exact four-span trace"]


def test_passing_result_rejects_unknown_check() -> None:
    result = doctor_fixture("local-pass.json")
    result["checks"][0]["status"] = "unknown"
    errors: list[str] = []
    VALIDATOR.validate_doctor_result_semantics(result, errors, "fixture")
    assert errors == ["fixture: pass can contain only passing checks"]


def test_probe_fixture_preserves_numeric_token_values() -> None:
    result = doctor_fixture("probe-pass.json")
    check = next(check for check in result["checks"] if check["name"] == "probe_typed_tokens")
    assert check["details"] == {
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "total_tokens": 18,
    }
    assert all(type(value) in {int, float} for value in check["details"].values())


def test_reason_codes_are_forward_compatible() -> None:
    result = doctor_fixture("local-warning.json")
    result["checks"][0]["reason_code"] = "FUTURE_REASON_2027"
    result["checks"][0]["remediation_code"] = "FUTURE_REMEDIATION_2027"
    assert Draft202012Validator(doctor_schema()).is_valid(result)


def test_launch_manifest_and_publishing_guards_validate() -> None:
    errors: list[str] = []
    VALIDATOR.validate_launch_support_manifest(errors)
    VALIDATOR.validate_publishing_workflow(errors)
    assert errors == []


def test_launch_manifest_uses_sdk_capabilities_without_wizard_coupling() -> None:
    manifest = json.loads(VALIDATOR.SUPPORT_MANIFEST.read_text())

    assert "wizard" not in manifest
    for language, sdk in manifest["sdks"].items():
        assert "supported_versions" not in sdk
        assert sdk["version_policy"] == "latest_published_stable"
        assert sdk["compatibility"] == "accept_newer_compatible_releases"
        assert sdk["never_downgrade"] is True
        assert sdk["doctor_capability"] == {
            "format_version": "neatlogs.doctor/v2",
            "runtime_language": language,
            "schema_version": "2",
        }


def test_success_fixtures_match_sdk_generated_success_codes() -> None:
    local = doctor_fixture("local-pass.json")
    probe = doctor_fixture("probe-pass.json")

    assert local["checks"][0]["reason_code"] == "LOCAL_ENVELOPE_VALID"
    assert local["checks"][0]["message"] == (
        "The final normalized local envelope is valid"
    )
    for result in (local, probe):
        for check in result["checks"]:
            assert check["status"] != "pass" or check["remediation_code"] == "NONE"


def test_sdk_skill_gates_do_not_pin_one_patch_release() -> None:
    pinned_versions = ("1.4.21", "1.1.19", "0.1.7")
    sdk_skills = [
        path
        for path in (ROOT / "skills").glob("*/SKILL.md")
        if VALIDATOR.doctor_language(path.parent.name) is not None
    ]

    for path in sdk_skills:
        text = path.read_text()
        normalized = " ".join(text.split())
        assert "latest published stable" in normalized
        assert "never downgrade" in normalized
        assert not any(version in text for version in pinned_versions)


def test_typescript_skills_use_cross_platform_local_runners() -> None:
    typescript_skills = sorted((ROOT / "skills").glob("neatlogs-ts*/SKILL.md"))
    expected_commands = (
        "npm exec --offline --no -- neatlogs doctor --local --json",
        "pnpm exec neatlogs doctor --local --json",
        "yarn run neatlogs doctor --local --json",
        "bun --no-install run neatlogs doctor --local --json",
    )

    for path in typescript_skills:
        text = path.read_text()
        assert "./node_modules/.bin/neatlogs" not in text
        for command in expected_commands:
            assert command in text


def test_go_skill_has_approved_version_matched_cli_installation() -> None:
    text = (ROOT / "skills" / "neatlogs-go" / "SKILL.md").read_text()
    normalized = " ".join(text.split())

    assert "go list -m -f '{{.Version}}' github.com/neatlogs/neatlogs-go" in text
    assert (
        "go install github.com/neatlogs/neatlogs-go/cmd/neatlogs@<resolved-module-version>"
        in text
    )
    assert "explicit user approval" in text
    assert "binary and project module versions match" in normalized
