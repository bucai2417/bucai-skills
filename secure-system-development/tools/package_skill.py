#!/usr/bin/env python3
"""Package a skill directory for distribution.

Produces three artifacts from one source tree:
  1. <name>-<version>.skill      Claud / Claud Code skill package (zip, SKILL.md at root)
  2. <name>-<version>.zip        Generic distribution zip (same layout)
  3. codex-plugin/               Codex/OpenAI plugin layout (plugin.json + skills/<name>/)

Pure standard library. Usage:
    python package_skill.py --src secure-system-development --out dist
    python package_skill.py --src secure-system-development --out dist --check-only

Exit codes:
    0 success
    1 validation failed
    2 bad arguments / path
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import zipfile
from typing import Dict, List, Optional, Sequence, Tuple

NAME_RE = re.compile(r"^[a-z0-9-]+$")
SKILL_NAME_MAX = 64
DESC_MAX = 1024

EXCLUDE_DIRS = {
    "__pycache__", ".git", ".svn", ".hg", "dist", "node_modules", ".idea", ".vscode",
    ".github", "tools", "docs", "tests",
}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIX = (".pyc", ".pyo", ".swp", ".tmp")


def read_frontmatter(skill_md: str) -> Dict[str, str]:
    with io.open(skill_md, encoding="utf-8") as fh:
        text = fh.read()
    if not text.startswith("---"):
        raise ValueError("SKILL.md does not start with YAML frontmatter")
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    if not m:
        raise ValueError("SKILL.md frontmatter is not terminated")
    fm_text = m.group(1)
    data: Dict[str, str] = {}
    for line in fm_text.splitlines():
        if not line.strip() or line.startswith("#") or line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        data[key.strip()] = value
    return data


def validate(skill_dir: str) -> Tuple[Dict[str, str], List[str]]:
    errors: List[str] = []
    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        return {}, ["SKILL.md not found in %s" % skill_dir]

    fm = read_frontmatter(skill_md)
    name = fm.get("name", "")
    desc = fm.get("description", "")
    desc_zh = fm.get("description_zh", "")
    desc_en = fm.get("description_en", "")
    version = fm.get("version", "")
    author = fm.get("author", "")
    display_name = fm.get("display_name", "")
    display_name_en = fm.get("display_name_en", "")

    if not name:
        errors.append("missing 'name' in frontmatter")
    elif not NAME_RE.match(name):
        errors.append("name '%s' must be hyphen-case (lowercase letters, digits, hyphens)" % name)
    elif name.startswith("-") or name.endswith("-") or "--" in name:
        errors.append("name '%s' cannot start/end with hyphen or contain '--'" % name)
    elif len(name) > SKILL_NAME_MAX:
        errors.append("name is too long (%d > %d)" % (len(name), SKILL_NAME_MAX))

    for field, value in (("description", desc), ("description_zh", desc_zh), ("description_en", desc_en)):
        if not value:
            errors.append("missing '%s' in frontmatter (required by skill platforms)" % field)
            continue
        if "<" in value or ">" in value:
            errors.append("%s cannot contain angle brackets" % field)
        if len(value) > DESC_MAX:
            errors.append("%s too long (%d > %d characters)" % (field, len(value), DESC_MAX))

    if not version:
        errors.append("missing top-level 'version' in frontmatter")
    elif not re.match(r"^\d+\.\d+\.\d+", version):
        errors.append("version '%s' should look like 1.2.3" % version)

    if not author:
        errors.append("missing 'author' in frontmatter")

    for field, value in (("display_name", display_name), ("display_name_en", display_name_en)):
        if not value:
            errors.append("missing '%s' in frontmatter (required by skill platforms)" % field)
        elif len(value) > 64:
            errors.append("%s too long (%d > 64 characters)" % (field, len(value)))

    return {
        "name": name,
        "version": version or "0.0.0",
        "description": desc,
        "description_zh": desc_zh,
        "description_en": desc_en,
        "author": author,
        "display_name": display_name,
        "display_name_en": display_name_en,
    }, errors


PLATFORM_EXCLUDE_DIRS = {".codex-plugin", "agents"}
PLATFORM_EXCLUDE_FILES = {".gitignore", ".gitattributes"}


def iter_platform_files(skill_dir: str) -> List[str]:
    return [
        rel for rel in iter_skill_files(skill_dir)
        if rel.split(os.sep)[0] not in PLATFORM_EXCLUDE_DIRS
        and os.path.basename(rel) not in PLATFORM_EXCLUDE_FILES
    ]


def iter_skill_files(skill_dir: str) -> List[str]:
    out: List[str] = []
    for root, dirs, files in os.walk(skill_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for name in files:
            if name in EXCLUDE_FILES or name.endswith(EXCLUDE_SUFFIX):
                continue
            full = os.path.join(root, name)
            out.append(os.path.relpath(full, skill_dir))
    out.sort()
    return out


def build_zip(skill_dir: str, dest: str, files: Optional[List[str]] = None, prefix: str = "") -> List[str]:
    files = files if files is not None else iter_skill_files(skill_dir)
    written: List[str] = []
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            arc = (prefix + rel.replace(os.sep, "/")) if prefix else rel.replace(os.sep, "/")
            zf.write(os.path.join(skill_dir, rel), arc)
            written.append(arc)
    return written


def build_codex_plugin(skill_dir: str, out_dir: str, meta: Dict[str, str]) -> str:
    plugin_root = os.path.join(out_dir, "codex-plugin")
    skill_target = os.path.join(plugin_root, "skills", meta["name"])
    if os.path.isdir(plugin_root):
        shutil.rmtree(plugin_root)
    os.makedirs(skill_target, exist_ok=True)

    for rel in iter_skill_files(skill_dir):
        src = os.path.join(skill_dir, rel)
        dst = os.path.join(skill_target, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    src_plugin_json = os.path.join(skill_dir, ".codex-plugin", "plugin.json")
    plugin_json: Dict = {}
    if os.path.isfile(src_plugin_json):
        with io.open(src_plugin_json, encoding="utf-8") as fh:
            plugin_json = json.load(fh)
    plugin_json.setdefault("name", meta["name"])
    plugin_json["version"] = meta["version"]
    plugin_json.setdefault("description", meta["description"])
    plugin_json.setdefault("license", "MIT")
    plugin_json["skills"] = "./skills/"

    target_plugin_json = os.path.join(plugin_root, ".codex-plugin", "plugin.json")
    os.makedirs(os.path.dirname(target_plugin_json), exist_ok=True)
    with io.open(target_plugin_json, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(plugin_json, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    return plugin_root


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_zip_layout(path: str) -> Tuple[bool, str]:
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
    if "SKILL.md" not in names:
        return False, "SKILL.md is not at the archive root"
    if not any(n.startswith("references/") for n in names):
        return False, "references/ missing from archive"
    return True, "ok (%d entries)" % len(names)


def main(argv: Optional[Sequence[str]] = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(description="Package a skill for distribution.")
    parser.add_argument("--src", default=".", help="path to the skill directory (default: .)")
    parser.add_argument("--out", default="dist", help="output directory (default: dist)")
    parser.add_argument("--check-only", action="store_true", help="validate only, do not package")
    parser.add_argument("--print-version", action="store_true",
                        help="print the version from SKILL.md and exit")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.src):
        print("error: skill directory not found: %s" % args.src, file=sys.stderr)
        return 2

    meta, errors = validate(args.src)
    if errors:
        print("validation failed:", file=sys.stderr)
        for e in errors:
            print("  - %s" % e, file=sys.stderr)
        return 1

    if args.print_version:
        print(meta["version"])
        return 0

    print("valid: name=%s version=%s author=%s display=%s / %s description=%d/%d/%d chars" % (
        meta["name"], meta["version"], meta["author"],
        meta["display_name"], meta["display_name_en"],
        len(meta["description"]), len(meta["description_zh"]), len(meta["description_en"])))

    if args.check_only:
        return 0

    os.makedirs(args.out, exist_ok=True)
    base = "%s-%s" % (meta["name"], meta["version"])
    skill_path = os.path.join(args.out, base + ".skill")
    zip_path = os.path.join(args.out, base + ".zip")

    entries = build_zip(args.src, zip_path, files=iter_platform_files(args.src))
    shutil.copyfile(zip_path, skill_path)

    for label, path in (("skill", skill_path), ("zip", zip_path)):
        ok, msg = verify_zip_layout(path)
        if not ok:
            print("error: %s layout invalid: %s" % (label, msg), file=sys.stderr)
            return 1
        print("  %-5s %s  %s  sha256=%s" % (label, path, msg, sha256(path)[:16]))

    plugin_root = build_codex_plugin(args.src, args.out, meta)
    print("  codex %s  (skills/%s/SKILL.md)" % (plugin_root, meta["name"]))

    print("packaged %d files" % len(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
