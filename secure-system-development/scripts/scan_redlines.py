#!/usr/bin/env python3
"""Red-line scanner for the secure-system-development skill.

Pure standard library. No third-party dependencies.

Usage:
    python scripts/scan_redlines.py <path>
    python scripts/scan_redlines.py <path> --format sarif --fail-on high
    python scripts/scan_redlines.py <path> --exclude node_modules,dist --min-severity medium

Exit codes:
    0  no finding at or above --fail-on
    1  findings at or above --fail-on
    2  bad arguments / path
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

TOOL_NAME = "secure-system-development redline scanner"
TOOL_VERSION = "1.0.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

SEVERITY_ORDER = {"low": 1, "medium": 2, "high": 3}
SARIF_LEVEL = {"high": "error", "medium": "warning", "low": "note"}

SKIP_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "bower_components", "vendor",
    "dist", "build", "out", "target", "bin", "obj", ".next", ".nuxt",
    "__pycache__", ".venv", "venv", "env", ".tox", ".mypy_cache",
    ".pytest_cache", "site-packages", ".gradle", ".idea", ".vs",
    "coverage", ".cache", ".terraform", "Pods", "DerivedData",
}

SKIP_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".svg",
    ".pdf", ".zip", ".gz", ".tar", ".bz2", ".xz", ".7z", ".rar",
    ".mp3", ".mp4", ".avi", ".mov", ".wav", ".woff", ".woff2", ".ttf",
    ".eot", ".otf", ".exe", ".dll", ".so", ".dylib", ".class", ".jar",
    ".pyc", ".pyo", ".o", ".a", ".lib", ".wasm", ".db", ".sqlite",
}

SKIP_FILE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock",
}

# Extensions treated as documentation when --code-only is set.
DOC_EXT = {".md", ".mdx", ".markdown", ".rst", ".txt", ".adoc"}

MAX_FILE_BYTES = 1_000_000

# Inline suppression: a line containing this marker is skipped.
#   // redline: ignore
#   // redline: ignore SQL001,CORS001
#   # redline: ignore
IGNORE_MARKER = re.compile(r"redline:\s*ignore(?:[:\s]+([A-Z0-9,\s]+))?", re.I)


@dataclass
class Rule:
    id: str
    severity: str
    pattern: "re.Pattern[str]"
    message: str
    ref: str


@dataclass
class ContextRule:
    """Report when a trigger pattern and a context word appear on the same line."""
    id: str
    severity: str
    trigger: "re.Pattern[str]"
    context: Sequence["re.Pattern[str]"]
    message: str
    ref: str


@dataclass
class Finding:
    rule_id: str
    severity: str
    path: str
    line: int
    column: int
    message: str
    ref: str
    snippet: str = ""


def _c(pattern: str, flags: int = 0) -> "re.Pattern[str]":
    return re.compile(pattern, flags)


RULES: List[Rule] = [
    # ---- SQL injection -------------------------------------------------
    Rule(
        "SQL001", "high",
        _c(r"""["'`][^\n]{0,500}\b(SELECT|INSERT|UPDATE|DELETE)\b[^\n]{0,500}["'`]\s*["'`]?\s*\+"""),
        "Possible SQL string concatenation (left) - use parameterized queries/ORM binding",
        "references/web-vulnerability-prevention.md#2-sql-注入",
    ),
    Rule(
        "SQL002", "high",
        _c(r"""\+\s*["'`][^\n]{0,300}\b(FROM|WHERE|VALUES|SET|ORDER BY|GROUP BY)\b"""),
        "Possible SQL string concatenation (right) - use parameterized queries",
        "references/web-vulnerability-prevention.md#2-sql-注入",
    ),
    Rule(
        "SQL003", "high",
        _c(r"""f["'][^"'\n]{0,300}\b(SELECT|INSERT|UPDATE|DELETE)\b[^"'\n]{0,300}\{"""),
        "Possible f-string SQL interpolation - use parameterized queries",
        "references/web-vulnerability-prevention.md#2-sql-注入",
    ),
    Rule(
        "SQL004", "medium",
        _c(r"""`[^`\n]{0,300}\b(SELECT|INSERT|UPDATE|DELETE)\b[^`\n]{0,300}\$\{"""),
        "Template literal contains SQL with interpolation - if this is a tagged template (sql`...`) it is safe; otherwise use parameters",
        "references/web-vulnerability-prevention.md#2-sql-注入",
    ),
    Rule(
        "SQL005", "high",
        _c(r"""\b(query|execute|prepare|raw|all|get)\s*\(\s*["'`][^"'`\n]{0,400}\b(SELECT|INSERT|UPDATE|DELETE)\b[^"'`\n]{0,400}["'`]\s*\+"""),
        "SQL call with inline concatenation - use parameterized queries",
        "references/web-vulnerability-prevention.md#2-sql-注入",
    ),

    # ---- XSS / code execution -----------------------------------------
    Rule(
        "XSS001", "high",
        _c(r"dangerouslySetInnerHTML|\.innerHTML\s*=|document\.write\s*\(|\bv-html\b"),  # redline: ignore
        "Dangerous HTML sink - sanitize with DOMPurify or render as text",
        "references/web-vulnerability-prevention.md#3-xss",
    ),
    Rule(
        "XSS002", "high",
        _c(r"\beval\s*\(|\bnew\s+Function\s*\("),
        "Dynamic code execution - never eval/new Function on untrusted input",
        "references/web-vulnerability-prevention.md#8-命令执行--代码执行",
    ),
    Rule(
        "TEMPLATE001", "high",
        _c(r"render_template_string\s*\(|from_string\s*\("),
        "Server-side template string rendering - SSTI risk, never interpolate user input",
        "references/web-vulnerability-prevention.md#8-命令执行--代码执行",
    ),

    # ---- CORS ---------------------------------------------------------
    Rule(
        "CORS001", "medium",
        _c(r"""Access-Control-Allow-Origin['"]?\s*[:=,]\s*['"]?\*""", re.I),
        "CORS allows any origin - use an exact Origin allowlist",
        "references/http-routing-cors-seo.md#3-cors精确白名单",
    ),
    Rule(
        "CORS002", "high",
        _c(r"""Access-Control-Allow-Origin[^\n]{0,120}(headers\.origin|headers\[['"]origin['"]\]|headers\.get\(['"]origin['"]\))""", re.I),
        "CORS reflects request Origin - equivalent to allowing any origin",
        "references/http-routing-cors-seo.md#3-cors精确白名单",
    ),

    # ---- Routing / soft 404 -------------------------------------------
    Rule(
        "ROUTE001", "medium",
        _c(r"""app\.get\s*\(\s*['"]\*['"]|app\.use\s*\(\s*['"]\*['"]"""),
        "Express wildcard route - ensure unknown paths do not fall back to 200 (soft 404)",
        "references/http-routing-cors-seo.md#1-404-必须是-404不跳首页",
    ),
    Rule(
        "ROUTE002", "medium",
        _c(r"try_files\s+\$uri\s+\$uri/\s+/index\.html"),
        "Nginx unconditional index.html fallback - unknown paths return 200 (soft 404)",
        "references/http-routing-cors-seo.md#1-404-必须是-404不跳首页",
    ),
    Rule(
        "ROUTE003", "medium",
        _c(r"error_page\s+404\s+/index\.html"),
        "404 redirected to homepage - return a real 404 page",
        "references/http-routing-cors-seo.md#1-404-必须是-404不跳首页",
    ),

    # ---- Secrets ------------------------------------------------------
    Rule(
        "SECRET001", "high",
        _c(r"\bAKIA[0-9A-Z]{16}\b"),
        "Hardcoded AWS Access Key ID",
        "references/operations-and-secrets.md#1-密钥管理",
    ),
    Rule(
        "SECRET002", "high",
        _c(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
        "Hardcoded GitHub token",
        "references/operations-and-secrets.md#1-密钥管理",
    ),
    Rule(
        "SECRET003", "high",
        _c(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "Hardcoded Slack token",
        "references/operations-and-secrets.md#1-密钥管理",
    ),
    Rule(
        "SECRET004", "high",
        _c(r"-----BEGIN\s+(RSA|EC|OPENSSH|DSA|PGP)?\s*PRIVATE KEY-----"),
        "Private key material in file",
        "references/operations-and-secrets.md#1-密钥管理",
    ),
    Rule(
        "SECRET005", "high",
        _c(r"""\b(AIza[0-9A-Za-z\-_]{35})\b"""),
        "Hardcoded Google API key",
        "references/operations-and-secrets.md#1-密钥管理",
    ),
    Rule(
        "SECRET006", "medium",
        _c(r"""\b(api_key|apikey|api_secret|secret_key|access_key|private_key|auth_token)\b\s*[:=]\s*["'][A-Za-z0-9_\-/+.]{16,}["']""", re.I),
        "Hardcoded secret/credential - move to env vars or a secret manager",
        "references/operations-and-secrets.md#1-密钥管理",
    ),

    # ---- Command injection -------------------------------------------
    Rule(
        "CMD001", "high",
        _c(r"\bchild_process\.exec\s*\(|\bos\.system\s*\(|\bexecSync\s*\(|\bsubprocess\.\w+\s*\([^)]*shell\s*=\s*True|\bRuntime\.getRuntime\(\)\.exec\s*\(|\bexec\s*\(\s*['\"][^'\"\n]{0,200}\b(ls|cd|cat|rm|cp|mv|curl|wget|sh|bash|powershell|cmd|git|npm|python|java|docker)\b"),
        "Command execution - verify inputs are trusted; use argument arrays",
        "references/web-vulnerability-prevention.md#8-命令执行--代码执行",
    ),

    # ---- TLS verification off ----------------------------------------
    Rule(
        "NET001", "high",
        _c(r"rejectUnauthorized\s*:\s*false|verify\s*=\s*False|InsecureSkipVerify\s*:\s*true|CERT_NONE|ssl\._create_unverified_context|checkServerTrusted\s*\([^)]*\)\s*\{\s*\}", re.I),  # redline: ignore
        "TLS certificate verification disabled - forbidden in production",
        "references/api-integrity-and-tampering.md#2-传输层",
    ),

    # ---- Debug in prod ------------------------------------------------
    Rule(
        "DEBUG001", "medium",
        _c(r"\bDEBUG\s*=\s*True|\bdebug\s*:\s*true|\bapp\.run\s*\([^)]*debug\s*=\s*True"),
        "Debug mode enabled - must be off in production",
        "references/operations-and-secrets.md#2-配置与多环境",
    ),

    # ---- Upload path --------------------------------------------------
    Rule(
        "UPLOAD001", "medium",
        _c(r"""path\.join\s*\([^)]{0,80}(req\.file|file\.originalname|originalname|filename|upload\.name)|\bos\.path\.join\s*\([^)]{0,80}(filename|originalname)""", re.I),
        "Uploaded filename used in path join - validate prefix and randomize the name",
        "references/web-vulnerability-prevention.md#7-文件上传",
    ),

    # ---- NoSQL injection ----------------------------------------------
    Rule(
        "NOSQL001", "high",
        _c(r"""\$(where|ne|gt|regex)\s*['"]?\s*:"""),
        "Possible NoSQL operator injection - take fields individually and validate types",
        "references/web-vulnerability-prevention.md#2-sql-注入",
    ),
]


CONTEXT_RULES: List[ContextRule] = [
    ContextRule(
        "CRYPTO001", "high",
        _c(r"createHash\s*\(\s*['\"](?:md5|sha1)['\"]|hashlib\.(?:md5|sha1)\s*\(|MessageDigest\.getInstance\s*\(\s*['\"](?:MD5|SHA-?1)['\"]|md5\s*\(|sha1\s*\(", re.I),
        [_c(r"password|passwd|pwd|passphrase", re.I), _c(r"user|login|auth", re.I)],
        "MD5/SHA1 used on a password - use Argon2id / bcrypt / scrypt",
        "references/auth-and-session.md#1-密码存储",
    ),
    ContextRule(
        "CRYPTO002", "high",
        _c(r"Math\.random\s*\(\s*\)"),  # redline: ignore
        [_c(r"token|secret|nonce|session|otp|captcha|reset|invite|code", re.I)],
        "Math.random() used for a security token - use a CSPRNG",  # redline: ignore
        "references/auth-and-session.md#4-会话",
    ),
    ContextRule(
        "LOG001", "medium",
        _c(r"(?:console\.(?:log|info|debug|error)|logger\.\w+|log\.\w+|fmt\.Print|print)\s*\(|log\.(?:info|debug|error|warn)\s*\(", re.I),
        [_c(r"password|passwd|token|cookie|authorization|secret|credential", re.I)],
        "Log statement may include sensitive fields - redact before logging",
        "references/operations-and-secrets.md#6-日志与审计",
    ),
    ContextRule(
        "CMP001", "medium",
        _c(r"===\s*signature|signature\s*===|==\s*signature|signature\s*=="),
        [_c(r"signature|hmac|digest", re.I)],
        "Signature compared with == - use constant-time comparison",
        "references/api-integrity-and-tampering.md#3-请求签名",
    ),
]


def _is_skipped_dir(name: str) -> bool:
    return name in SKIP_DIRS or name.startswith(".")


def iter_files(root: str, excludes: Sequence[str], code_only: bool = False) -> Iterable[str]:
    root = os.path.abspath(root)
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _is_skipped_dir(d)]
        for name in filenames:
            if name in SKIP_FILE_NAMES:
                continue
            ext = os.path.splitext(name)[1].lower()
            if ext in SKIP_EXT:
                continue
            if code_only and ext in DOC_EXT:
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if any(rel.startswith(e) or os.sep + e + os.sep in rel for e in excludes):
                continue
            try:
                if os.path.getsize(full) > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            yield full


def read_text(path: str) -> Optional[str]:
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    # crude binary check: too many NUL bytes
    if b"\x00" in raw[:4096]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("latin-1")
        except UnicodeDecodeError:
            return None


def _ignored_ids(line: str) -> Optional[set]:
    """Return the set of suppressed rule ids for this line.

    ``None`` means "not suppressed". An empty set means "suppress everything
    on this line" (bare ``redline: ignore``).
    """
    m = IGNORE_MARKER.search(line)
    if not m:
        return None
    ids = (m.group(1) or "").strip()
    if not ids:
        return set()
    return {t.strip().upper() for t in ids.split(",") if t.strip()}


def scan_text(path: str, text: str, min_sev: int) -> List[Finding]:
    findings: List[Finding] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if len(line) > 4000:
            line = line[:4000]
        ignored = _ignored_ids(line)
        for rule in RULES:
            if SEVERITY_ORDER[rule.severity] < min_sev:
                continue
            if ignored is not None and (not ignored or rule.id.upper() in ignored):
                continue
            m = rule.pattern.search(line)
            if m:
                findings.append(Finding(
                    rule_id=rule.id, severity=rule.severity, path=path,
                    line=lineno, column=m.start() + 1, message=rule.message,
                    ref=rule.ref, snippet=line.strip()[:200],
                ))
        for crule in CONTEXT_RULES:
            if SEVERITY_ORDER[crule.severity] < min_sev:
                continue
            if ignored is not None and (not ignored or crule.id.upper() in ignored):
                continue
            m = crule.trigger.search(line)
            if not m:
                continue
            if any(ctx.search(line) for ctx in crule.context):
                findings.append(Finding(
                    rule_id=crule.id, severity=crule.severity, path=path,
                    line=lineno, column=m.start() + 1, message=crule.message,
                    ref=crule.ref, snippet=line.strip()[:200],
                ))
    return findings


def collect(root: str, excludes: Sequence[str], min_sev: int, code_only: bool = False) -> List[Finding]:
    out: List[Finding] = []
    for path in iter_files(root, excludes, code_only):
        text = read_text(path)
        if text is None:
            continue
        out.extend(scan_text(path, text, min_sev))
    out.sort(key=lambda f: (f.path, f.line, f.column, f.rule_id))
    return out


def emit_text(findings: List[Finding], root: str, ascii_only: bool) -> None:
    base = os.path.abspath(root)
    base = base if os.path.isdir(base) else os.path.dirname(base)
    for f in findings:
        rel = os.path.relpath(f.path, base)
        print("%s:%d:%d  [%s] %s  %s" % (rel, f.line, f.column, f.rule_id, f.severity.upper(), f.message))
        if f.snippet:
            print("    > %s" % f.snippet)
        print("    fix: %s" % f.ref)
    counts = {"high": 0, "medium": 0, "low": 0}
    for f in findings:
        counts[f.severity] += 1
    print()
    print("Scanned. Findings: high=%d medium=%d low=%d total=%d" % (
        counts["high"], counts["medium"], counts["low"], len(findings)))


def emit_json(findings: List[Finding]) -> None:
    print(json.dumps({
        "tool": TOOL_NAME,
        "version": TOOL_VERSION,
        "findings": [f.__dict__ for f in findings],
        "summary": {
            "high": sum(1 for f in findings if f.severity == "high"),
            "medium": sum(1 for f in findings if f.severity == "medium"),
            "low": sum(1 for f in findings if f.severity == "low"),
            "total": len(findings),
        },
    }, ensure_ascii=False, indent=2))


def emit_sarif(findings: List[Finding], root: str) -> None:
    base = os.path.abspath(root)
    base = base if os.path.isdir(base) else os.path.dirname(base)
    rule_ids = sorted({f.rule_id for f in findings})
    rules_meta = [{
        "id": rid,
        "shortDescription": {"text": rid},
        "helpUri": "references/",
    } for rid in rule_ids]
    results = []
    for f in findings:
        results.append({
            "ruleId": f.rule_id,
            "level": SARIF_LEVEL[f.severity],
            "message": {"text": "%s (fix: %s)" % (f.message, f.ref)},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": os.path.relpath(f.path, base).replace(os.sep, "/"),
                    },
                    "region": {"startLine": f.line, "startColumn": f.column},
                },
            }],
        })
    print(json.dumps({
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": TOOL_NAME, "version": TOOL_VERSION, "rules": rules_meta}},
            "results": results,
        }],
    }, ensure_ascii=False, indent=2))


def main(argv: Optional[Sequence[str]] = None) -> int:
    # Emit UTF-8 regardless of platform console encoding so CI can parse output.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(
        description="Scan source trees for security red-line violations.")
    parser.add_argument("path", help="file or directory to scan")
    parser.add_argument("--format", choices=["text", "json", "sarif"], default="text")
    parser.add_argument("--exclude", default="", help="comma-separated relative paths to skip")
    parser.add_argument("--fail-on", choices=["none", "low", "medium", "high"], default="high")
    parser.add_argument("--min-severity", choices=["low", "medium", "high"], default="low")
    parser.add_argument("--code-only", action="store_true",
                        help="skip documentation files (.md/.mdx/.rst/.txt/.adoc)")
    args = parser.parse_args(argv)

    if not os.path.exists(args.path):
        print("error: path not found: %s" % args.path, file=sys.stderr)
        return 2

    excludes = [e.strip() for e in args.exclude.split(",") if e.strip()]
    min_sev = SEVERITY_ORDER[args.min_severity]
    findings = collect(args.path, excludes, min_sev, args.code_only)

    if args.format == "json":
        emit_json(findings)
    elif args.format == "sarif":
        emit_sarif(findings, args.path)
    else:
        emit_text(findings, args.path, True)

    if args.fail_on == "none":
        return 0
    threshold = SEVERITY_ORDER[args.fail_on]
    worst = max((SEVERITY_ORDER[f.severity] for f in findings), default=0)
    return 1 if worst >= threshold else 0


if __name__ == "__main__":
    sys.exit(main())
