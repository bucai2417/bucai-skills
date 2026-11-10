#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end tests for the pdf-data skill. Run: python tests/test_extract.py

All fixtures are generated with PyMuPDF at runtime; no external PDFs needed.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import extract  # noqa: E402
from pdfdata import render  # noqa: E402

fitz.no_recommend_layout()


def _call(argv):
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = extract.main(argv)
    return code, stdout.getvalue(), stderr.getvalue()


def _save(doc, path):
    doc.save(str(path))
    doc.close()


def _cjk_font(page):
    font = fitz.Font("china-s")
    page.insert_font(fontname="F0", fontbuffer=font.buffer)
    return "F0"


class PdfDataTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.dir = Path(self._temp.name)
        self.counter = 0

    def tearDown(self):
        self._temp.cleanup()

    def run_cli(self, pdf, *extra):
        self.counter += 1
        out = self.dir / ("out%d" % self.counter)
        code, stdout, stderr = _call(
            [str(pdf), "--out-dir", str(out), *extra]
        )
        return code, out, stdout, stderr

    def load_json(self, out):
        return json.loads((out / "document.json").read_text(encoding="utf-8"))

    def make_text_pdf(self, name, text, size=12, pages=1):
        path = self.dir / name
        doc = fitz.open()
        for index in range(pages):
            page = doc.new_page()
            page.insert_text((72, 72), text, fontsize=size)
            if pages > 1:
                page.insert_text((72, 120), "unique body %d" % (index + 1), fontsize=11)
        _save(doc, path)
        return path

    # ---------- basic text ----------

    def test_english_text_json_and_markdown(self):
        path = self.dir / "en.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Senior Engineer Resume", fontsize=18)
        page.insert_text((72, 100), "Email: zhang@example.com", fontsize=11)
        doc.set_metadata({"title": "Resume", "author": "Zhang San"})
        _save(doc, path)

        code, out, _, _ = self.run_cli(path)
        self.assertEqual(code, 0)
        data = self.load_json(out)
        self.assertEqual(data["schema_version"], "1.0")
        self.assertIn("Senior Engineer Resume", data["pages"][0]["text"])
        self.assertEqual(data["document"]["metadata"]["title"], "Resume")
        self.assertGreaterEqual(data["pages"][0]["char_count"], 20)
        markdown = (out / "document.md").read_text(encoding="utf-8")
        self.assertIn("Senior Engineer Resume", markdown)
        self.assertIn("Email: zhang@example.com", markdown)

    def test_cjk_text_roundtrip(self):
        path = self.dir / "cjk.pdf"
        doc = fitz.open()
        page = doc.new_page()
        fontname = _cjk_font(page)
        page.insert_text((72, 72), "中文简历：张三", fontname=fontname, fontsize=16)
        page.insert_text((72, 100), "邮箱：zhang@example.com", fontname=fontname, fontsize=11)
        _save(doc, path)

        code, out, _, _ = self.run_cli(path)
        self.assertEqual(code, 0)
        data = self.load_json(out)
        self.assertIn("中文简历：张三", data["pages"][0]["text"])
        self.assertIn("cjk", data["pages"][0]["quality"]["flags"])
        markdown = (out / "document.md").read_text(encoding="utf-8")
        self.assertIn("中文简历：张三", markdown)

    def test_two_column_reading_order(self):
        path = self.dir / "columns.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 60), "FULL WIDTH TITLE", fontsize=18)
        left = {
            120: "LEFT_ONE resume content",
            170: "LEFT_TWO resume content",
            220: "LEFT_THREE resume content",
        }
        right = {
            130: "RIGHT_ONE resume content",
            180: "RIGHT_TWO resume content",
            230: "RIGHT_THREE resume content",
        }
        for y, text in left.items():
            page.insert_text((50, y), text, fontsize=11)
        for y, text in right.items():
            page.insert_text((330, y), text, fontsize=11)
        _save(doc, path)

        code, out, _, _ = self.run_cli(path)
        self.assertEqual(code, 0)
        data = self.load_json(out)
        self.assertGreaterEqual(data["pages"][0]["layout"]["columns"], 2)
        markdown = (out / "document.md").read_text(encoding="utf-8")
        positions = [markdown.index(token) for token in (
            "LEFT_ONE", "LEFT_TWO", "LEFT_THREE", "RIGHT_ONE", "RIGHT_TWO", "RIGHT_THREE"
        )]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(markdown.index("FULL WIDTH TITLE"), markdown.index("LEFT_ONE"))

    # ---------- tables ----------

    def make_table_pdf(self, name):
        path = self.dir / name
        doc = fitz.open()
        page = doc.new_page()
        for x in (72, 220, 360):
            page.draw_line((x, 150), (x, 250))
        for y in (150, 190, 220, 250):
            page.draw_line((72, y), (360, y))
        page.insert_text((80, 175), "Role", fontsize=11)
        page.insert_text((230, 175), "Engineer", fontsize=11)
        page.insert_text((80, 207), "Years", fontsize=11)
        page.insert_text((230, 207), "6", fontsize=11)
        _save(doc, path)
        return path

    def test_table_extraction_and_no_duplicate_text(self):
        path = self.make_table_pdf("table.pdf")
        code, out, _, _ = self.run_cli(path)
        self.assertEqual(code, 0)
        data = self.load_json(out)
        page = data["pages"][0]
        self.assertGreaterEqual(len(page["tables"]), 1)
        first = page["tables"][0]
        self.assertEqual(first["rows"][0][0], "Role")
        self.assertEqual(first["rows"][0][1], "Engineer")
        markdown = (out / "document.md").read_text(encoding="utf-8")
        self.assertIn("| Role | Engineer |", markdown)
        self.assertEqual(markdown.count("Role"), 1)

    def test_table_strategies(self):
        path = self.make_table_pdf("table_strategy.pdf")
        code, out, _, _ = self.run_cli(path, "--table-strategy", "off")
        self.assertEqual(code, 0)
        self.assertEqual(self.load_json(out)["pages"][0]["tables"], [])

        code, out, _, _ = self.run_cli(path, "--table-strategy", "mupdf")
        self.assertEqual(code, 0)
        self.assertGreaterEqual(len(self.load_json(out)["pages"][0]["tables"]), 1)

        code, out, _, _ = self.run_cli(path, "--table-strategy", "pdfplumber")
        self.assertEqual(code, 0)
        tables = self.load_json(out)["pages"][0]["tables"]
        self.assertGreaterEqual(len(tables), 1)
        self.assertTrue(all(table["engine"] == "pdfplumber" for table in tables))

    # ---------- images / scanned ----------

    def make_image_pdf(self, name):
        path = self.dir / name
        doc = fitz.open()
        page = doc.new_page()
        pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 400, 400), False)
        pixmap.set_rect(pixmap.irect, (180, 180, 180))
        page.insert_image(page.rect, pixmap=pixmap)
        _save(doc, path)
        return path

    def test_scanned_page_flags_and_exit_code(self):
        path = self.make_image_pdf("scan.pdf")
        code, out, _, _ = self.run_cli(path)
        self.assertEqual(code, 4)
        data = self.load_json(out)
        page = data["pages"][0]
        self.assertFalse(page["text_layer"])
        self.assertTrue(page["quality"]["scanned"])
        codes = {warning["code"] for warning in data["warnings"]}
        self.assertIn("NO_TEXT_LAYER", codes)
        self.assertIn("SCANNED_PDF", codes)
        self.assertTrue((out / "document.md").is_file())
        self.assertEqual(len(page["images"]), 1)

    def test_image_modes(self):
        path = self.make_image_pdf("image_modes.pdf")
        code, out, _, _ = self.run_cli(path, "--images", "none")
        self.assertEqual(code, 4)
        self.assertEqual(self.load_json(out)["pages"][0]["images"], [])

        code, out, _, _ = self.run_cli(path, "--images", "extract")
        self.assertEqual(code, 4)
        data = self.load_json(out)
        image = data["pages"][0]["images"][0]
        self.assertTrue(image["file"])
        self.assertTrue((out / image["file"]).is_file())

    # ---------- encryption ----------

    def test_encrypted_pdf(self):
        path = self.dir / "encrypted.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Encrypted resume content", fontsize=12)
        doc.save(
            str(path),
            encryption=fitz.PDF_ENCRYPT_AES_256,
            owner_pw="owner",
            user_pw="user",
        )
        doc.close()

        code, _, _, _ = self.run_cli(path)
        self.assertEqual(code, 3)

        code, out, _, _ = self.run_cli(path, "--password", "user")
        self.assertEqual(code, 0)
        data = self.load_json(out)
        self.assertEqual(data["document"]["access"], "user")
        self.assertTrue(data["document"]["encrypted"])
        self.assertIn("Encrypted resume content", data["pages"][0]["text"])

        code, out, _, _ = self.run_cli(path, "--password", "owner")
        self.assertEqual(code, 0)
        self.assertEqual(self.load_json(out)["document"]["access"], "owner")

    # ---------- metadata, outline, links ----------

    def test_metadata_outline_links(self):
        path = self.dir / "meta.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Example Site", fontsize=12)
        page.insert_link(
            {
                "kind": fitz.LINK_URI,
                "from": fitz.Rect(70, 60, 200, 80),
                "uri": "https://example.com/profile",
            }
        )
        doc.set_metadata({"title": "Profile", "author": "Zhang San"})
        doc.set_toc([[1, "Profile", 1]])
        _save(doc, path)

        code, out, _, _ = self.run_cli(path)
        self.assertEqual(code, 0)
        data = self.load_json(out)
        self.assertEqual(data["document"]["outline"][0]["title"], "Profile")
        self.assertEqual(data["document"]["outline"][0]["page_index"], 0)
        links = data["document"]["links"]
        self.assertTrue(any(link["uri"] == "https://example.com/profile" for link in links))
        markdown = (out / "document.md").read_text(encoding="utf-8")
        self.assertIn("https://example.com/profile", markdown)

    # ---------- headers / footers ----------

    def test_header_footer_detection(self):
        path = self.dir / "furniture.pdf"
        doc = fitz.open()
        for index in range(5):
            page = doc.new_page()
            page.insert_text((72, 30), "ACME CONFIDENTIAL", fontsize=9)
            page.insert_text((72, 200), "Body line %d" % (index + 1), fontsize=11)
            page.insert_text((72, 800), "Page %d" % (index + 1), fontsize=9)
        _save(doc, path)

        code, out, _, _ = self.run_cli(path)
        self.assertEqual(code, 0)
        data = self.load_json(out)
        self.assertTrue(
            any(warning["code"] == "FURNITURE_STRIPPED" for warning in data["warnings"])
        )
        self.assertTrue(data["pages"][0]["headers_footers"])
        markdown = (out / "document.md").read_text(encoding="utf-8")
        self.assertNotIn("ACME CONFIDENTIAL", markdown)
        self.assertEqual(markdown.count("Page 1"), 1)  # only the page heading

        code, out, _, _ = self.run_cli(path, "--keep-headers")
        self.assertEqual(code, 0)
        markdown = (out / "document.md").read_text(encoding="utf-8")
        self.assertIn("ACME CONFIDENTIAL", markdown)

    # ---------- normalization ----------

    def test_line_joining_and_cjk(self):
        hyphenated = render._join_lines(
            [{"spans": [{"text": "inter-"}]}, {"spans": [{"text": "national"}]}]
        )
        self.assertEqual(hyphenated, "international")
        cjk = render._join_lines(
            [{"spans": [{"text": "中文"}]}, {"spans": [{"text": "简历"}]}]
        )
        self.assertEqual(cjk, "中文简历")

    # ---------- rotation / coordinates ----------

    def test_rotated_page(self):
        path = self.dir / "rotated.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Rotated resume text", fontsize=12)
        page.set_rotation(90)
        _save(doc, path)

        code, out, _, _ = self.run_cli(path)
        self.assertEqual(code, 0)
        data = self.load_json(out)
        page = data["pages"][0]
        self.assertEqual(page["rotation"], 90)
        self.assertGreater(page["width"], page["height"])
        self.assertIn("Rotated resume text", page["text"])
        self.assertEqual(page["coordinate_space"], "mupdf_unrotated_top_left")

    def test_char_coords(self):
        path = self.make_text_pdf("chars.pdf", "Characters here")
        code, out, _, _ = self.run_cli(path, "--char-coords", "--no-crosscheck")
        self.assertEqual(code, 0)
        blocks = self.load_json(out)["pages"][0]["blocks"]
        spans = [span for block in blocks for line in block["lines"] for span in line["spans"]]
        self.assertTrue(any(span.get("chars") for span in spans))
        self.assertTrue(all("c" in char for span in spans for char in span.get("chars", [])))

    # ---------- page selection ----------

    def test_page_selection_and_clipping(self):
        path = self.make_text_pdf("pages.pdf", "Page one text", pages=3)
        code, out, _, _ = self.run_cli(path, "--pages", "2")
        self.assertEqual(code, 0)
        data = self.load_json(out)
        self.assertEqual(len(data["pages"]), 1)
        self.assertEqual(data["pages"][0]["number"], 2)

        code, out, _, _ = self.run_cli(path, "--pages", "2-9")
        self.assertEqual(code, 0)
        data = self.load_json(out)
        self.assertEqual(len(data["pages"]), 2)
        self.assertTrue(
            any(warning["code"] == "PAGE_RANGE_CLIPPED" for warning in data["warnings"])
        )

        code, _, _, _ = self.run_cli(path, "--pages", "9")
        self.assertEqual(code, 2)

        code, _, _, _ = self.run_cli(path, "--pages", "abc")
        self.assertEqual(code, 2)

    # ---------- failure modes ----------

    def test_missing_corrupt_and_zero_page(self):
        code, _, _, _ = self.run_cli(self.dir / "missing.pdf")
        self.assertEqual(code, 2)

        corrupt = self.dir / "corrupt.pdf"
        corrupt.write_bytes(b"this is not a pdf")
        code, _, _, _ = self.run_cli(corrupt)
        self.assertEqual(code, 2)

        try:
            from pypdf import PdfWriter
        except ImportError:
            self.skipTest("pypdf not installed")
        zero = self.dir / "zero.pdf"
        with zero.open("wb") as handle:
            PdfWriter().write(handle)
        code, _, _, _ = self.run_cli(zero)
        self.assertEqual(code, 2)

    # ---------- stdout / cross-check / output ----------

    def test_stdout_mode_does_not_write_files(self):
        path = self.make_text_pdf("stdout.pdf", "Stdout resume text")
        out = self.dir / "stdout_out"
        code, stdout, stderr = _call(
            [str(path), "--out-dir", str(out), "--format", "json", "--stdout"]
        )
        self.assertEqual(code, 0)
        self.assertTrue(stdout.lstrip().startswith("{"))
        self.assertIn("[pdf-data]", stderr)
        self.assertFalse((out / "document.json").exists())

    def test_crosscheck_controls(self):
        path = self.make_text_pdf("cross.pdf", "Cross check resume content")
        code, out, _, _ = self.run_cli(path)
        self.assertEqual(code, 0)
        data = self.load_json(out)
        self.assertIn(
            data["pages"][0]["quality"]["crosscheck"]["status"], ("match", "mismatch")
        )

        code, out, _, _ = self.run_cli(path, "--no-crosscheck")
        self.assertEqual(code, 0)
        data = self.load_json(out)
        self.assertEqual(data["pages"][0]["quality"]["crosscheck"]["status"], "skipped")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    unittest.main(verbosity=2)
