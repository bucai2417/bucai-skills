# -*- coding: utf-8 -*-
"""Layout analysis: column-aware reading order and repeated header/footer detection."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Sequence, Tuple

_CJK_RE = re.compile(r"[㐀-䶿一-鿿぀-ヿ가-힯]")
_PAGE_NUMBER_RES = (
    re.compile(r"^(?:page|p\.?)\s*\d+(?:\s*(?:of|/)\s*\d+)?$", re.I),
    re.compile(r"^-\s*\d+\s*-$"),
    re.compile(r"^第\s*\d+\s*页(?:\s*[/／]\s*共\s*\d+\s*页)?$"),
    re.compile(r"^\d{1,4}$"),
)


def line_text(line: Dict[str, Any]) -> str:
    return "".join(span.get("text", "") for span in line.get("spans", []) or [])


def block_text(block: Dict[str, Any]) -> str:
    return "\n".join(line_text(line) for line in block.get("lines", []) or [])


def is_cjk_char(char: str) -> bool:
    return bool(char) and bool(_CJK_RE.match(char))


def _norm_key(text: str) -> str:
    key = re.sub(r"\d+", "#", text.lower())
    key = re.sub(r"\s+", " ", key).strip()
    return key


def _is_page_number(text: str) -> bool:
    stripped = text.strip()
    return any(pattern.match(stripped) for pattern in _PAGE_NUMBER_RES)


def _find_gutters(
    words: Sequence[Sequence[Any]], rect
) -> Tuple[List[float], float]:
    if len(words) < 20:
        return [], 1.0

    page_width = max(1.0, float(rect.width))
    lo = float(rect.x0) + page_width * 0.10
    hi = float(rect.x0) + page_width * 0.90
    step = 1.0 if page_width <= 2000 else page_width / 2000.0
    cells = max(1, int((hi - lo) / step))
    coverage = [0] * cells

    for word in words:
        left = max(lo, float(word[0]))
        right = min(hi, float(word[2]))
        if right <= left:
            continue
        first = max(0, int((left - lo) / step))
        last = min(cells - 1, int((right - lo) / step))
        for index in range(first, last + 1):
            coverage[index] += 1

    bands: List[Tuple[float, float]] = []
    start: Optional[int] = None
    for index, count in enumerate(coverage):
        if count == 0 and start is None:
            start = index
        elif count != 0 and start is not None:
            if (index - start) * step >= 8:
                bands.append((lo + start * step, lo + index * step))
            start = None
    if start is not None and (cells - start) * step >= 8:
        bands.append((lo + start * step, lo + cells * step))

    minimum_side = max(3, int(len(words) * 0.15))
    valid: List[Tuple[float, float]] = []
    for left_edge, right_edge in bands:
        gutter = (left_edge + right_edge) / 2.0
        left_words = [word for word in words if float(word[2]) <= gutter]
        right_words = [word for word in words if float(word[0]) >= gutter]
        if len(left_words) < minimum_side or len(right_words) < minimum_side:
            continue
        left_lines = {round(float(word[1])) for word in left_words}
        right_lines = {round(float(word[1])) for word in right_words}
        if len(left_lines) < 3 or len(right_lines) < 3:
            continue
        valid.append((right_edge - left_edge, gutter))

    valid.sort(reverse=True)
    chosen: List[Tuple[float, float]] = []
    for width, gutter in valid:
        if all(abs(gutter - other) >= 20 for _, other in chosen):
            chosen.append((width, gutter))
        if len(chosen) == 2:
            break

    if not chosen:
        return [], 1.0

    gutters = sorted(gutter for _, gutter in chosen)
    classified = 0
    for word in words:
        left, right = float(word[0]), float(word[2])
        if not any(left < gutter < right for gutter in gutters):
            classified += 1
    confidence = classified / float(len(words))
    if confidence < 0.7:
        return [], confidence
    return gutters, confidence


def order_blocks(
    blocks: List[Dict[str, Any]],
    words: Sequence[Sequence[Any]],
    rect,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    gutters, confidence = _find_gutters(words, rect)
    if not gutters:
        ordered = sorted(
            blocks,
            key=lambda block: (
                round((block.get("bbox") or [0, 0, 0, 0])[1], 1),
                round((block.get("bbox") or [0, 0, 0, 0])[0], 1),
            ),
        )
        return ordered, {
            "columns": 1,
            "gutter_x": None,
            "gutters": [],
            "method": "mupdf_sort",
            "confidence": round(confidence, 3),
        }

    def is_full_width(block: Dict[str, Any]) -> bool:
        bbox = block.get("bbox") or [0, 0, 0, 0]
        return any(bbox[0] < gutter - 1 and bbox[2] > gutter + 1 for gutter in gutters)

    def column_of(block: Dict[str, Any]) -> int:
        bbox = block.get("bbox") or [0, 0, 0, 0]
        center = (bbox[0] + bbox[2]) / 2.0
        column = 0
        for gutter in gutters:
            if center > gutter:
                column += 1
        return column

    anchors = [block for block in blocks if is_full_width(block)]
    column_blocks = [block for block in blocks if not is_full_width(block)]
    for block in column_blocks:
        block["_column"] = column_of(block)

    anchors.sort(
        key=lambda block: (
            round((block.get("bbox") or [0, 0, 0, 0])[1], 1),
            round((block.get("bbox") or [0, 0, 0, 0])[0], 1),
        )
    )

    ordered: List[Dict[str, Any]] = []
    placed = set()
    for anchor in anchors:
        anchor_y = (anchor.get("bbox") or [0, 0, 0, 0])[1]
        pending = [
            block
            for block in column_blocks
            if id(block) not in placed
            and (block.get("bbox") or [0, 0, 0, 0])[3] <= anchor_y + 1
        ]
        pending.sort(
            key=lambda block: (
                block.get("_column", 0),
                round((block.get("bbox") or [0, 0, 0, 0])[1], 1),
                round((block.get("bbox") or [0, 0, 0, 0])[0], 1),
            )
        )
        ordered.extend(pending)
        placed.update(id(block) for block in pending)
        ordered.append(anchor)

    remaining = [block for block in column_blocks if id(block) not in placed]
    remaining.sort(
        key=lambda block: (
            block.get("_column", 0),
            round((block.get("bbox") or [0, 0, 0, 0])[1], 1),
            round((block.get("bbox") or [0, 0, 0, 0])[0], 1),
        )
    )
    ordered.extend(remaining)
    for block in ordered:
        block.pop("_column", None)

    return ordered, {
        "columns": len(gutters) + 1,
        "gutter_x": round(gutters[0], 2),
        "gutters": [round(gutter, 2) for gutter in gutters],
        "method": "columns",
        "confidence": round(confidence, 3),
    }


def _zone_of(line: Dict[str, Any], page_height: float) -> Optional[str]:
    bbox = line.get("bbox") or [0, 0, 0, 0]
    center_y = (bbox[1] + bbox[3]) / 2.0
    if center_y < page_height * 0.12:
        return "header"
    if center_y > page_height * 0.88:
        return "footer"
    return None


def detect_furniture(
    raw_pages: Sequence[Dict[str, Any]], threshold: float = 0.6
) -> Dict[int, List[Dict[str, Any]]]:
    page_count = len(raw_pages)
    if page_count < 3:
        return {}

    candidates: Dict[int, List[Dict[str, Any]]] = {}
    pages_per_key: Counter = Counter()

    for raw in raw_pages:
        page_index = int(raw["index"])
        page_height = float((raw.get("layout_rect") or raw["rect"]).height)
        seen: set = set()
        records: List[Dict[str, Any]] = []
        for block in raw.get("blocks", []) or []:
            for line in block.get("lines", []) or []:
                text = line_text(line).strip()
                if not text:
                    continue
                zone = _zone_of(line, page_height)
                if zone is None:
                    continue
                key = _norm_key(text)
                records.append(
                    {
                        "zone": zone,
                        "text": text,
                        "bbox": line.get("bbox"),
                        "key": key,
                        "is_page_number": _is_page_number(text),
                    }
                )
                if (zone, key) not in seen:
                    seen.add((zone, key))
                    pages_per_key[key] += 1
        candidates[page_index] = records

    furniture_keys = {
        key
        for key, count in pages_per_key.items()
        if count / float(page_count) >= threshold
    }
    if not furniture_keys:
        return {}

    result: Dict[int, List[Dict[str, Any]]] = {}
    for page_index, records in candidates.items():
        kept = [record for record in records if record["key"] in furniture_keys]
        if kept:
            result[page_index] = kept
    return result


def _bbox_key(bbox: Optional[Sequence[float]]) -> Optional[Tuple[float, ...]]:
    if not bbox:
        return None
    try:
        return tuple(round(float(value), 1) for value in bbox[:4])
    except Exception:
        return None


def mark_furniture(
    blocks: List[Dict[str, Any]], page_furniture: Sequence[Dict[str, Any]]
) -> int:
    if not page_furniture:
        return 0
    boxes: Dict[str, set] = {}
    for record in page_furniture:
        bbox_key = _bbox_key(record.get("bbox"))
        if bbox_key is not None:
            boxes.setdefault(record["key"], set()).add(bbox_key)
    keys = set(boxes) | {record["key"] for record in page_furniture}
    marked = 0
    for block in blocks:
        lines = block.get("lines", []) or []
        hits = 0
        for line in lines:
            text = line_text(line).strip()
            if not text:
                continue
            key = _norm_key(text)
            if key not in keys:
                continue
            expected = boxes.get(key)
            line_key = _bbox_key(line.get("bbox"))
            if expected and line_key is not None and line_key not in expected:
                continue
            if expected and line_key is None:
                continue
            line["furniture"] = True
            hits += 1
            marked += 1
        block["furniture"] = bool(lines) and hits == len(lines)
    return marked
