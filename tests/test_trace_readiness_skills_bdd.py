"""Real-artifact Given/When/Then BDD tests for trace-readiness skills upgrades.

Zero fakes and zero undeclared test dependencies (matches requirements-ci.txt:
jsonschema + pytest + Python stdlib only).
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_skills_bdd", ROOT / "scripts" / "validate-skills.py"
)
assert SPEC and SPEC.loader
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def test_bdd_skills_pass_real_validator_and_preserve_public_boundaries() -> None:
    """Given the upgraded neatlogs-py-setup and neatlogs-py skills on disk,
    When scripts/validate-skills.py runs as a real subprocess,
    Then validation exits 0 with zero forbidden internal terms or broken safety gates."""
    # When: invoke the real CI validator script
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "validate-skills.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    # Then: exit 0 and every updated skill passes public-boundary checks
    assert proc.returncode == 0, f"validate-skills.py failed:\n{proc.stdout}\n{proc.stderr}"
    for rel in (
        "skills/neatlogs-py-setup/SKILL.md",
        "skills/neatlogs-py-setup/references/understand-first.md",
        "skills/neatlogs-py-setup/references/4-decorate-functions.md",
        "skills/neatlogs-py-setup/references/6-decorate-tools.md",
        "skills/neatlogs-py-setup/references/6b-retrievers-and-provenance.md",
        "skills/neatlogs-py/SKILL.md",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        errors: list[str] = []
        VALIDATOR.validate_public_doctor_boundary(text, errors, rel)
        assert errors == [], f"Public boundary violation in {rel}: {errors}"


def test_bdd_setup_skill_encodes_judge_and_backtrack_readiness_rules() -> None:
    """Given a developer following neatlogs-py-setup,
    When reading SKILL.md and its references,
    Then root I/O, retriever freshness, session hygiene, provenance, replay=True,
    and python -m neatlogs trace audit are all explicitly specified and linked."""
    setup_dir = ROOT / "skills" / "neatlogs-py-setup"
    skill_md = (setup_dir / "SKILL.md").read_text(encoding="utf-8")
    understand = (setup_dir / "references" / "understand-first.md").read_text(encoding="utf-8")
    decorate_fns = (setup_dir / "references" / "4-decorate-functions.md").read_text(encoding="utf-8")
    decorate_tools = (setup_dir / "references" / "6-decorate-tools.md").read_text(encoding="utf-8")
    step_6b = (setup_dir / "references" / "6b-retrievers-and-provenance.md").read_text(
        encoding="utf-8"
    )
    py_skill = (ROOT / "skills" / "neatlogs-py" / "SKILL.md").read_text(encoding="utf-8")

    # Then: Step 6b is wired into SKILL.md and all local links resolve cleanly
    assert "references/6b-retrievers-and-provenance.md" in skill_md
    assert "python -m neatlogs trace audit" in skill_md
    assert "python -m neatlogs trace audit" in py_skill
    assert "never pass `trace_id`" in skill_md.lower() or "never pass `trace_id`" in step_6b.lower()
    assert "per-request `neatlogs.flush()`" in skill_md

    # Phase 2 inventory hunts for RAG, sessions, provenance, and streaming boundaries
    for expected in ("updated_at", "session_id", "prompt_version", "StreamingResponse"):
        assert expected in understand

    # Step 4 encodes Clean Root I/O + streaming accumulation + prompt_version
    for expected in (
        'set_attribute("input.value"',
        'set_attribute("output.value"',
        "prompt_version",
        "6b-retrievers-and-provenance.md",
    ):
        assert expected in decorate_fns

    # Step 6 encodes replay=True and links to 6b
    assert "replay=True" in decorate_tools
    assert "(6b-retrievers-and-provenance.md)" in decorate_tools

    # Step 6b encodes retrievers, freshness, sessions, provenance, checkpoints, diagnostics
    for expected in (
        'kind="RETRIEVER"',
        'kind="RERANKER"',
        'kind="GUARDRAIL"',
        "updated_at",
        "replay=True",
        "NEATLOGS_ENVIRONMENT",
        "NEATLOGS_RELEASE",
        "neatlogs.checkpoint",
        "neatlogs.report_diagnostic",
    ):
        assert expected in step_6b

    # neatlogs-py SKILL.md documents init provenance, replayable kinds, and audit CLI
    for expected in (
        "`environment`",
        "`release`",
        "NEATLOGS_ENVIRONMENT",
        "NEATLOGS_RELEASE",
        "neatlogs.checkpoint",
        "neatlogs.report_diagnostic",
    ):
        assert expected in py_skill

    # Every relative markdown link in modified reference files resolves on disk
    for md_file in (
        setup_dir / "SKILL.md",
        setup_dir / "references" / "understand-first.md",
        setup_dir / "references" / "4-decorate-functions.md",
        setup_dir / "references" / "6-decorate-tools.md",
        setup_dir / "references" / "6b-retrievers-and-provenance.md",
        ROOT / "skills" / "neatlogs-py" / "SKILL.md",
    ):
        for target in LINK_RE.findall(md_file.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#")):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (md_file.parent / target_path).resolve()
            assert resolved.is_file(), f"Broken relative link {target!r} in {md_file}"


def test_bdd_packaged_skill_zips_are_clean_and_include_new_reference(tmp_path: Path) -> None:
    """Given the skills directory,
    When packaging neatlogs-py-setup and neatlogs-py into release zip archives,
    Then zip integrity passes and 6b-retrievers-and-provenance.md is bundled."""
    for skill_name in ("neatlogs-py-setup", "neatlogs-py"):
        skill_dir = ROOT / "skills" / skill_name
        archive_path = tmp_path / f"{skill_name}.zip"
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(skill_dir.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(ROOT / "skills"))
        with zipfile.ZipFile(archive_path, "r") as zf:
            assert zf.testzip() is None
            names = set(zf.namelist())
            assert f"{skill_name}/SKILL.md" in names
            if skill_name == "neatlogs-py-setup":
                assert f"{skill_name}/references/6b-retrievers-and-provenance.md" in names
