#!/usr/bin/env python3
"""Build deterministic, checksummed public Skill release assets."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
PLUGIN = ROOT / ".claude-plugin" / "plugin.json"
SUPPORT = ROOT / "contracts" / "skills-support-v1.json"
TELEMETRY_MANIFEST = ROOT / "contracts" / "v2" / "manifest.json"
TELEMETRY_SCHEMA = ROOT / "contracts" / "v2" / "neatlogs-telemetry.schema.json"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def zip_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    archive.writestr(info, data)


def skill_paths(skill_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(skill_dir.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Skill package cannot contain a symlink: {path}")
        if path.is_file():
            paths.append(path)
    return paths


def build_archive(
    skill_dir: Path,
    destination: Path,
    support_bytes: bytes,
    telemetry_manifest_bytes: bytes,
    telemetry_schema_bytes: bytes,
) -> dict[str, object]:
    skill_id = skill_dir.name
    archive_path = destination / f"{skill_id}.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        for path in skill_paths(skill_dir):
            relative = path.relative_to(skill_dir).as_posix()
            zip_entry(archive, f"{skill_id}/{relative}", path.read_bytes())
        zip_entry(
            archive,
            f"{skill_id}/.neatlogs/skills-support-v1.json",
            support_bytes,
        )
        zip_entry(
            archive,
            f"{skill_id}/.neatlogs/telemetry-v2-manifest.json",
            telemetry_manifest_bytes,
        )
        zip_entry(
            archive,
            f"{skill_id}/.neatlogs/neatlogs-telemetry.schema.json",
            telemetry_schema_bytes,
        )

    archive_bytes = archive_path.read_bytes()
    return {
        "id": skill_id,
        "name": skill_id,
        "downloadUrl": "",
        "sha256": sha256(archive_bytes),
        "bytes": len(archive_bytes),
    }


def build_release(destination: Path) -> dict[str, object]:
    plugin = json.loads(PLUGIN.read_text(encoding="utf-8"))
    support = json.loads(SUPPORT.read_text(encoding="utf-8"))
    version = str(plugin["version"])
    if support.get("skills_version") != version:
        raise ValueError("skills_version must match .claude-plugin/plugin.json")
    expected_tag = f"skills-v{version}"
    distribution = support.get("distribution", {})
    if distribution.get("release_tag") != expected_tag:
        raise ValueError("support contract release_tag does not match the Skill version")

    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError("release output directory must be empty")
    support_bytes = SUPPORT.read_bytes()
    telemetry_manifest_bytes = TELEMETRY_MANIFEST.read_bytes()
    telemetry_schema_bytes = TELEMETRY_SCHEMA.read_bytes()
    prefix = str(distribution["canonical_download_prefix"])
    entries: list[dict[str, object]] = []
    for skill_dir in sorted(path for path in SKILLS.iterdir() if path.is_dir()):
        if not (skill_dir / "SKILL.md").is_file():
            continue
        entry = build_archive(
            skill_dir,
            destination,
            support_bytes,
            telemetry_manifest_bytes,
            telemetry_schema_bytes,
        )
        entry["downloadUrl"] = f"{prefix}{entry['id']}.zip"
        entries.append(entry)

    support_asset = destination / str(distribution["support_contract_asset"])
    shutil.copyfile(SUPPORT, support_asset)
    shutil.copyfile(TELEMETRY_MANIFEST, destination / "telemetry-v2-manifest.json")
    shutil.copyfile(
        TELEMETRY_SCHEMA,
        destination / "neatlogs-telemetry.schema.json",
    )
    support_digest = sha256(support_bytes)
    menu = {
        "formatVersion": "neatlogs.skill-menu/v1",
        "version": version,
        "buildVersion": f"sha256:{support_digest}",
        "supportContract": {
            "formatVersion": support["format_version"],
            "downloadUrl": f"{prefix}{support_asset.name}",
            "sha256": support_digest,
            "bytes": len(support_bytes),
        },
        "categories": {"setup": entries},
    }
    menu_path = destination / str(distribution["menu_asset"])
    menu_path.write_text(
        json.dumps(menu, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    sums = [
        f"{sha256(path.read_bytes())}  {path.name}"
        for path in sorted(destination.iterdir())
        if path.is_file() and path.name != "SHA256SUMS"
    ]
    (destination / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    return menu


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    menu = build_release(args.output.resolve())
    print(
        f"Built {len(menu['categories']['setup'])} deterministic Skill archives "
        f"for {menu['version']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
