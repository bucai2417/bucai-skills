#!/usr/bin/env python3
"""Build one combined bucai-skills bundle.

Outputs (in --out, default dist/):
  bucai-skills-<version>.zip                  All skills at the archive root
  bucai-skills-<version>-codex-plugin.zip     Codex plugin layout with every skill
  sha256sums.txt                              Checksums for both archives

The collection version comes from the repository-root VERSION file. Individual
skills keep their own versions in SKILL.md. Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
VERSION_FILE = ROOT / "VERSION"
DIST = ROOT / "dist"

SKIP_DIRS = {
    ".git", ".github", "dist", "build", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".idea", ".vscode", "node_modules",
}
SKIP_FILES = {".DS_Store", "Thumbs.db", ".gitignore", ".gitattributes"}
SKIP_SUFFIX = (".pyc", ".pyo", ".swp", ".tmp")

VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
FIXED_TIME = (1980, 1, 1, 0, 0, 0)


class BundleError(RuntimeError):
    pass


def read_version() -> str:
    if not VERSION_FILE.is_file():
        raise BundleError("VERSION file not found")
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not VERSION_RE.match(version):
        raise BundleError(f"VERSION must be semver, got: {version!r}")
    return version


def skill_dirs() -> list[Path]:
    skills = [
        p for p in ROOT.iterdir()
        if p.is_dir() and p.name not in SKIP_DIRS and (p / "SKILL.md").is_file()
    ]
    return sorted(skills, key=lambda p: p.name)


def read_skill_version(skill: Path) -> str:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not match:
        raise BundleError(f"{skill.name}: SKILL.md frontmatter is missing or unterminated")
    for line in match.group(1).splitlines():
        if line.startswith("version:"):
            value = line.partition(":")[2].strip().strip("\"'")
            if value:
                return value
    raise BundleError(f"{skill.name}: SKILL.md has no version field")


def validate_skills() -> list[Path]:
    sys.path.insert(0, str(TOOLS))
    from package_skill import validate  # noqa: WPS433 - local sibling module

    skills = skill_dirs()
    if not skills:
        raise BundleError("no skill directories found (expected <name>/SKILL.md)")

    problems: list[str] = []
    for skill in skills:
        _, errors = validate(str(skill))
        if errors:
            problems.extend(f"{skill.name}: {err}" for err in errors)
    if problems:
        raise BundleError("; ".join(problems))
    return skills


def iter_skill_files(skill: Path, skip_dirs: set[str] | None = None) -> list[tuple[Path, str]]:
    skip = SKIP_DIRS | (skip_dirs or set())
    files: list[tuple[Path, str]] = []
    for path in sorted(skill.rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(skill)
        if any(part in skip for part in rel.parts[:-1]):
            continue
        if path.name in SKIP_FILES or path.suffix in SKIP_SUFFIX:
            continue
        files.append((path, rel.as_posix()))
    return files


def write_entry(zf: zipfile.ZipFile, arcname: str, data: bytes) -> None:
    info = zipfile.ZipInfo(arcname, date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def add_file(zf: zipfile.ZipFile, path: Path, arcname: str) -> None:
    write_entry(zf, arcname, path.read_bytes())


def build_bundle(out: Path, version: str, skills: list[Path]) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)

    bundle = out / f"bucai-skills-{version}.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ("README.md", "LICENSE", "VERSION"):
            src = ROOT / name
            if src.is_file():
                add_file(zf, src, name)
        for skill in skills:
            for path, rel in iter_skill_files(skill):
                add_file(zf, path, f"{skill.name}/{rel}")

    codex = out / f"bucai-skills-{version}-codex-plugin.zip"
    plugin = {
        "name": "bucai-skills",
        "version": version,
        "description": "Collection of agent skills: multi-channel bot adapters and secure system development.",
        "author": {"name": "bucai2417"},
        "license": "MIT",
        "homepage": "https://github.com/bucai2417/bucai-skills",
        "repository": "https://github.com/bucai2417/bucai-skills",
        "skills": "./skills/",
        "interface": {
            "displayName": "bucai-skills",
            "shortDescription": "Multi-channel bot adapters and secure system development skills",
            "developerName": "bucai2417",
            "category": "Developer Tools",
            "capabilities": ["Read", "Write"],
        },
    }
    with zipfile.ZipFile(codex, "w", zipfile.ZIP_DEFLATED) as zf:
        write_entry(
            zf,
            ".codex-plugin/plugin.json",
            (json.dumps(plugin, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        for skill in skills:
            for path, rel in iter_skill_files(skill, skip_dirs={".codex-plugin"}):
                add_file(zf, path, f"skills/{skill.name}/{rel}")

    sums = out / "sha256sums.txt"
    lines = [
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
        for p in (bundle, codex)
    ]
    sums.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return [bundle, codex, sums]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the combined bucai-skills bundle.")
    parser.add_argument("--out", default=str(DIST), help="output directory (default: dist)")
    parser.add_argument("--check-only", action="store_true", help="validate only")
    parser.add_argument("--print-version", action="store_true", help="print the collection version and exit")
    args = parser.parse_args(argv)

    try:
        version = read_version()
        if args.print_version:
            print(version)
            return 0

        skills = validate_skills()
        skill_versions = ", ".join(f"{s.name}={read_skill_version(s)}" for s in skills)
        if args.check_only:
            print(f"valid: bundle={version} skills={len(skills)} ({skill_versions})")
            return 0

        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
        written = build_bundle(out, version, skills)
        print(f"built bucai-skills {version} with {len(skills)} skill(s): {skill_versions}")
        for path in written:
            print(f"  {path.name}  ({path.stat().st_size} bytes)")
        return 0
    except BundleError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
