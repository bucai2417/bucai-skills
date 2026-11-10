#!/usr/bin/env python3
"""Self-test for scripts/scan_redlines.py.

Asserts that every rule fires on a deliberately vulnerable sample and that the
inline suppression markers work. Run locally with:

    python tests/test_scanner_rules.py

Exit code 0 means all assertions passed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCANNER = os.path.join(ROOT, "scripts", "scan_redlines.py")

VULNERABLE_SAMPLE = r"""
const rows = await db.query("SELECT * FROM users WHERE email = '" + email + "'");
element.innerHTML = userInput;
eval(userInput);
res.setHeader('Access-Control-Allow-Origin', '*');
res.setHeader('Access-Control-Allow-Origin', req.headers.origin);
app.get('*', (req, res) => res.sendFile('index.html'));
const key = 'AKIAIOSFODNN7EXAMPLE';
crypto.createHash('md5').update(password).digest('hex');
const resetToken = Math.random().toString(36);
const opts = { rejectUnauthorized: false };
const cfg = { debug: true };
console.log('login', email, password);
exec('ls ' + req.query.dir);
"""

SUPPRESSED_SAMPLE = """
eval(a); // redline: ignore
eval(b); // redline: ignore XSS002
eval(c); // redline: ignore CORS001
"""

EXPECTED_RULES = {
    "SQL001", "XSS001", "XSS002", "CORS001", "CORS002", "ROUTE001",
    "SECRET001", "CRYPTO001", "CRYPTO002", "NET001", "DEBUG001",
    "LOG001", "CMD001",
}


def run_scan(path: str) -> dict:
    proc = subprocess.run(
        [sys.executable, SCANNER, path, "--format", "json"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode not in (0, 1):
        raise SystemExit("scanner failed:\n%s\n%s" % (proc.stdout, proc.stderr))
    return json.loads(proc.stdout)


def main() -> int:
    failures = []

    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "vuln.js"), "w", encoding="utf-8") as fh:
            fh.write(VULNERABLE_SAMPLE)
        data = run_scan(d)
        found = {f["rule_id"] for f in data["findings"]}
        missing = EXPECTED_RULES - found
        if missing:
            failures.append("rules not detected: %s" % sorted(missing))
        else:
            print("ok: detected %d rules" % len(found & EXPECTED_RULES))

        if data["summary"]["high"] == 0:
            failures.append("expected high-severity findings, got none")

    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "suppress.js"), "w", encoding="utf-8") as fh:
            fh.write(SUPPRESSED_SAMPLE)
        data = run_scan(d)
        lines = sorted(f["line"] for f in data["findings"] if f["rule_id"] == "XSS002")
        # line 2 fully suppressed, line 3 suppressed by id, line 4 not suppressed
        if lines != [4]:
            failures.append("inline suppression wrong, XSS002 lines=%s (expected [4])" % lines)
        else:
            print("ok: inline suppression")

    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "clean.js"), "w", encoding="utf-8") as fh:
            fh.write("console.log('hello')\n")
        proc = subprocess.run(
            [sys.executable, SCANNER, d, "--fail-on", "high"],
            capture_output=True, text=True, encoding="utf-8",
        )
        if proc.returncode != 0:
            failures.append("clean directory should exit 0, got %d" % proc.returncode)
        else:
            print("ok: clean directory exit code")

    if failures:
        for f in failures:
            print("FAIL: %s" % f, file=sys.stderr)
        return 1

    print("all scanner tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
