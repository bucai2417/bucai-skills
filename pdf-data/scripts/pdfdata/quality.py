# -*- coding: utf-8 -*-
"""Text normalization, page quality signals, engine cross-check and table adjudication."""

from __future__ import annotations

import copy
import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[㐀-䶿一-鿿぀-ヿ가-힯]")
_CID_RE = re.compile(r"\(cid:\d+\)")
_ZERO_WIDTH_RE = re.compile("[​‌‍﻿]")
_CJK_RE = re.compile(r"[㐀-䶿一-鿿぀-ヿ가-힯]")

TEXT_LAYER_MIN_CHARS = 10
SCAN_IMAGE_COVERAGE = 0.8
CROSSCHECK_CHAR_RATIO = 0.15
CROSSCHECK_JACCARD = 0.80


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    value = unicodedata.normalize("NFKC", text)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = _ZERO_WIDTH_RE.sub("", value)
    lines = [" ".join(line.split()) for line in value.split("\n")]
    return "\n".join(lines).strip()


def token_set(text: Optional[str]) -> set:
    if not text:
        return set()
    return set(_TOKEN_RE.findall(text.lower()))


def _control_count(text: str) -> int:
    return sum(
        1
        for char in text
        if ord(char) < 32 and char not in ("\n", "\t", "\r")
    )


def _text_score(text: Optional[str]) -> int:
    if not text:
        return 0
    tokens = token_set(text)
    cid = len(_CID_RE.findall(text))
    replacement = text.count("�")
    control = _control_count(text)
    return len(tokens) - 5 * (cid + replacement + control)


def evaluate_page(
    raw: Dict[str, Any], text: str, text_engine: str
) -> Dict[str, Any]:
    normalized = normalize_text(text)
    char_count = len(normalized.replace("\n", ""))
    word_count = len(re.findall(r"\S+", normalized))
    cid = len(_CID_RE.findall(text or ""))
    replacement = (text or "").count("�")
    control = _control_count(text or "")
    image_coverage = float(raw.get("image_coverage") or 0.0)
    cjk_chars = len(_CJK_RE.findall(normalized))
    cjk_ratio = cjk_chars / float(max(1, char_count))

    text_layer = char_count >= TEXT_LAYER_MIN_CHARS
    scanned = (not text_layer) and image_coverage >= SCAN_IMAGE_COVERAGE

    flags: List[str] = []
    if char_count == 0:
        flags.append("empty_text")
    if not text_layer:
        flags.append("no_text_layer")
    if scanned:
        flags.append("scanned")
    if cid:
        flags.append("cid_glyphs")
    if replacement:
        flags.append("replacement_chars")
    if control:
        flags.append("control_chars")
    if cjk_ratio > 0.05:
        flags.append("cjk")

    return {
        "flags": flags,
        "char_count": char_count,
        "word_count": word_count,
        "text_layer": text_layer,
        "scanned": scanned,
        "cid_glyphs": cid,
        "replacement_chars": replacement,
        "control_chars": control,
        "image_coverage": round(image_coverage, 4),
        "cjk_ratio": round(cjk_ratio, 4),
        "text_engine": text_engine,
        "crosscheck": {"status": "skipped"},
    }


def crosscheck(
    mupdf_text: Optional[str], plumber_text: Optional[str]
) -> Dict[str, Any]:
    if plumber_text is None:
        return {
            "status": "unavailable",
            "char_ratio": None,
            "jaccard": None,
            "pdfplumber_char_count": None,
        }

    left = normalize_text(mupdf_text)
    right = normalize_text(plumber_text)
    left_chars = len(left.replace("\n", ""))
    right_chars = len(right.replace("\n", ""))
    denominator = max(1, left_chars, right_chars)
    char_ratio = abs(left_chars - right_chars) / float(denominator)

    left_tokens = token_set(left)
    right_tokens = token_set(right)
    union = left_tokens | right_tokens
    jaccard = (len(left_tokens & right_tokens) / float(len(union))) if union else 1.0

    if max(left_chars, right_chars) < TEXT_LAYER_MIN_CHARS:
        status = "match" if left == right else "mismatch"
    elif char_ratio > CROSSCHECK_CHAR_RATIO or jaccard < CROSSCHECK_JACCARD:
        status = "mismatch"
    else:
        status = "match"

    return {
        "status": status,
        "char_ratio": round(char_ratio, 4),
        "jaccard": round(jaccard, 4),
        "pdfplumber_char_count": right_chars,
    }


def choose_text(
    mupdf_text: Optional[str], plumber_text: Optional[str]
) -> Tuple[str, str]:
    if plumber_text is None:
        return mupdf_text or "", "mupdf"
    if _text_score(plumber_text) > _text_score(mupdf_text):
        return plumber_text, "pdfplumber"
    return mupdf_text or "", "mupdf"


def _iou(left: Optional[Sequence[float]], right: Optional[Sequence[float]]) -> float:
    if not left or not right:
        return 0.0
    x0 = max(float(left[0]), float(right[0]))
    y0 = max(float(left[1]), float(right[1]))
    x1 = min(float(left[2]), float(right[2]))
    y1 = min(float(left[3]), float(right[3]))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    intersection = (x1 - x0) * (y1 - y0)
    left_area = max(0.0, (float(left[2]) - float(left[0])) * (float(left[3]) - float(left[1])))
    right_area = max(0.0, (float(right[2]) - float(right[0])) * (float(right[3]) - float(right[1])))
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


def _matrix(rows: Sequence[Sequence[Any]]) -> List[List[str]]:
    return [
        [normalize_text("" if cell is None else str(cell)) for cell in row]
        for row in rows or []
    ]


def _same_matrix(left: Sequence[Sequence[Any]], right: Sequence[Sequence[Any]]) -> bool:
    return _matrix(left) == _matrix(right)


def _table_ok(table: Dict[str, Any]) -> bool:
    rows = table.get("rows") or []
    if len(rows) < 2:
        return False
    columns = max((len(row) for row in rows), default=0)
    if columns < 2:
        return False
    total = sum(len(row) for row in rows) or 1
    filled = sum(1 for row in rows for cell in row if normalize_text(str(cell)))
    return filled / float(total) >= 0.6


def merge_tables(
    rotation: int,
    mupdf_tables: Sequence[Dict[str, Any]],
    plumber_tables: Sequence[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    result = [copy.deepcopy(table) for table in mupdf_tables]
    mismatched: List[str] = []

    for extra in plumber_tables:
        match = None
        for table in result:
            same_position = (
                rotation == 0
                and _iou(table.get("bbox"), extra.get("bbox")) >= 0.5
            )
            if same_position or _same_matrix(
                table.get("rows") or [], extra.get("rows") or []
            ):
                match = table
                break
        if match is not None:
            equal = _same_matrix(match.get("rows") or [], extra.get("rows") or [])
            match["cross_check"] = {
                "status": "match" if equal else "mismatch",
                "engine": "pdfplumber",
            }
            if not equal:
                mismatched.append(str(match.get("id")))
        elif _table_ok(extra):
            result.append(copy.deepcopy(extra))

    deduped: List[Dict[str, Any]] = []
    for table in result:
        duplicate = any(
            table.get("engine") == kept.get("engine")
            and _iou(table.get("bbox"), kept.get("bbox")) >= 0.8
            for kept in deduped
        )
        if not duplicate:
            deduped.append(table)
    return deduped, mismatched
