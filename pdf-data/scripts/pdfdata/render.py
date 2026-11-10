# -*- coding: utf-8 -*-
"""Markdown and plain-text rendering from structured extraction results."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .layout import line_text
from .model import DocumentResult, PageResult
from .quality import normalize_text

_MARKDOWN_LEADING_RE = re.compile(r"^(\s*)(#{1,6}\s|[-*+>]\s|\d+\.\s)")
_LINK_SCHEMES = ("http://", "https://", "mailto:")


def _visible_lines(block: Dict[str, Any], keep_headers: bool) -> List[Dict[str, Any]]:
    lines = block.get("lines", []) or []
    if keep_headers:
        return lines
    return [line for line in lines if not line.get("furniture")]


def _join_lines(lines: Sequence[Dict[str, Any]]) -> str:
    output = ""
    for line in lines:
        text = line_text(line).strip()
        if not text:
            continue
        if not output:
            output = text
            continue
        previous = output[-1]
        first = text[0]
        if (
            output.endswith("-")
            and first.isascii()
            and first.islower()
        ):
            output = output[:-1] + text
        elif _is_cjk(previous) and _is_cjk(first):
            output += text
        else:
            output += " " + text
    return output.strip()


def _is_cjk(char: str) -> bool:
    return bool(char) and bool(re.match(r"[㐀-䶿一-鿿぀-ヿ가-힯]", char))


def _block_text(block: Dict[str, Any], keep_headers: bool) -> str:
    return _join_lines(_visible_lines(block, keep_headers))


def _escape_text(text: str) -> str:
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    match = _MARKDOWN_LEADING_RE.match(text)
    if match:
        text = match.group(1) + "\\" + text[len(match.group(1)):]
    return text


def _escape_cell(value: Any) -> str:
    text = normalize_text("" if value is None else str(value))
    text = text.replace("\\", "\\\\").replace("|", "\\|")
    text = text.replace("\n", "<br>")
    return text.replace("<", "&lt;").replace(">", "&gt;")


def _body_font_size(pages: Iterable[PageResult]) -> float:
    samples: List[Tuple[float, int]] = []
    for page in pages:
        for block in page.blocks:
            for line in block.get("lines", []) or []:
                for span in line.get("spans", []) or []:
                    text = (span.get("text") or "").strip()
                    if not text:
                        continue
                    try:
                        size = float(span.get("size") or 0)
                    except Exception:
                        size = 0.0
                    if size > 0:
                        samples.append((size, len(text)))
    if not samples:
        return 12.0
    samples.sort(key=lambda item: item[0])
    total = sum(weight for _, weight in samples)
    running = 0
    for size, weight in samples:
        running += weight
        if running >= total / 2.0:
            return size
    return samples[-1][0]


def _outline_map(result: DocumentResult) -> Dict[Tuple[Optional[int], str], int]:
    mapping: Dict[Tuple[Optional[int], str], int] = {}
    for item in result.document.get("outline", []) or []:
        try:
            level = int(item.get("level") or 1)
        except Exception:
            level = 1
        title = normalize_text(str(item.get("title") or "")).lower()
        page_index = item.get("page_index")
        if title:
            mapping[(page_index, title)] = level
    return mapping


def _table_center(block: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    bbox = block.get("bbox")
    if not bbox:
        return None
    return ((float(bbox[0]) + float(bbox[2])) / 2.0, (float(bbox[1]) + float(bbox[3])) / 2.0)


def _inside_any_table(block: Dict[str, Any], tables: Sequence[Dict[str, Any]]) -> bool:
    center = _table_center(block)
    if center is None:
        return False
    for table in tables:
        bbox = table.get("bbox")
        if not bbox:
            continue
        if (
            float(bbox[0]) <= center[0] <= float(bbox[2])
            and float(bbox[1]) <= center[1] <= float(bbox[3])
        ):
            return True
    return False


def _markdown_table(rows: Sequence[Sequence[Any]]) -> List[str]:
    matrix = [[_escape_cell(cell) for cell in row] for row in rows]
    if not matrix:
        return []
    columns = max(len(row) for row in matrix)
    matrix = [row + [""] * (columns - len(row)) for row in matrix]
    lines = ["| " + " | ".join(matrix[0]) + " |"]
    lines.append("| " + " | ".join(["---"] * columns) + " |")
    for row in matrix[1:]:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def _link_line(link: Dict[str, Any]) -> Optional[str]:
    uri = link.get("uri")
    if link.get("kind") == "goto" or (
        link.get("kind") == "gotor" and link.get("target_page_index") is not None
    ):
        target = link.get("target_page_index")
        if target is None:
            return None
        return "- 第 %d 页" % (int(target) + 1)
    if not uri:
        return None
    uri = str(uri)
    if not uri.lower().startswith(_LINK_SCHEMES):
        return "- %s" % uri
    label = (link.get("label") or "").strip() or uri
    label = label.replace("[", "\\[").replace("]", "\\]")
    target = "<%s>" % uri if any(char in uri for char in " ()<>") else uri
    return "- [%s](%s)" % (label, target)


def _unique_links(links: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    output = []
    for link in links:
        key = (link.get("kind"), link.get("uri"), link.get("target_page_index"))
        if key in seen:
            continue
        seen.add(key)
        output.append(link)
    return output


def to_markdown(result: DocumentResult, keep_headers: bool = False) -> str:
    document = result.document
    source = result.source
    metadata = document.get("metadata") or {}
    title = metadata.get("title") or source.get("file_name") or "PDF"
    body_size = _body_font_size(result.pages)
    outline = _outline_map(result)

    lines: List[str] = ["# %s" % title, ""]

    meta_lines = [
        "- 文件：%s" % (source.get("file_name") or source.get("path") or ""),
        "- 页数：%d" % int(document.get("page_count") or 0),
    ]
    for key, label in (
        ("author", "作者"),
        ("subject", "主题"),
        ("creator", "生成器"),
        ("source", "元数据来源"),
    ):
        value = metadata.get(key)
        if value:
            meta_lines.append("- %s：%s" % (label, value))
    lines.extend(meta_lines)
    lines.append("")

    if result.warnings:
        counts = Counter(warning.code for warning in result.warnings)
        summary = "、".join("%s×%d" % (code, count) for code, count in counts.items())
        lines.append("> 警告：%d 条（%s）" % (len(result.warnings), summary))
        lines.append("")

    outline_items = document.get("outline", []) or []
    if outline_items:
        lines.append("## 目录")
        for item in outline_items:
            level = max(1, min(6, int(item.get("level") or 1)))
            page_index = item.get("page_index")
            suffix = "（第 %d 页）" % (int(page_index) + 1) if page_index is not None else ""
            lines.append("%s- %s%s" % ("  " * (level - 1), item.get("title", ""), suffix))
        lines.append("")

    for page in result.pages:
        lines.append("<!-- page: %d -->" % page.number)
        lines.append("## Page %d" % page.number)
        lines.append("")
        if not page.text_layer:
            lines.append(
                "> 警告：第 %d 页无可提取文本层（疑似扫描件），未执行 OCR。" % page.number
            )
            lines.append("")
            if page.images:
                lines.append("> 本页含 %d 张图片，仅记录元数据。" % len(page.images))
                lines.append("")

        rendered_any = False
        for block in page.blocks:
            if block.get("furniture") and not keep_headers:
                continue
            if _inside_any_table(block, page.tables):
                continue
            text = _block_text(block, keep_headers)
            if not text:
                continue
            visible_lines = _visible_lines(block, keep_headers)
            max_size = max(
                (
                    float(span.get("size") or 0)
                    for line in visible_lines
                    for span in line.get("spans", []) or []
                ),
                default=0.0,
            )
            heading_level = 0
            key = (page.index, normalize_text(text).lower())
            if len(text) <= 80 and len(visible_lines) <= 2:
                if key in outline:
                    heading_level = max(3, min(6, 2 + int(outline[key])))
                elif max_size >= body_size * 1.6:
                    heading_level = 3
                elif max_size >= body_size * 1.25:
                    heading_level = 4
            if heading_level:
                lines.append("%s %s" % ("#" * heading_level, text))
            else:
                lines.append(_escape_text(text))
            lines.append("")
            rendered_any = True

        for index, table in enumerate(page.tables, start=1):
            rows = table.get("rows") or []
            if not rows:
                continue
            lines.append("**Table %d**" % index)
            lines.append("")
            lines.extend(_markdown_table(rows))
            lines.append("")
            rendered_any = True

        link_lines = [
            line
            for line in (_link_line(link) for link in _unique_links(page.links))
            if line
        ]
        if link_lines:
            lines.append("**Links**")
            lines.extend(link_lines)
            lines.append("")
            rendered_any = True

        if not rendered_any and page.text_layer:
            lines.append("（本页无可渲染文本）")
            lines.append("")

    engines = document.get("engines") or {}
    version_text = "、".join(
        "%s %s" % (name, version) for name, version in engines.items() if version
    )
    lines.append("---")
    lines.append("")
    footer = "生成：%s" % (result.extraction.get("generated_at") or "")
    if version_text:
        footer += " · 引擎：%s" % version_text
    footer += " · 警告：%d" % len(result.warnings)
    lines.append(footer)
    lines.append("")
    return "\n".join(lines)


def to_plain_text(result: DocumentResult, keep_headers: bool = False) -> str:
    chunks: List[str] = []
    for page in result.pages:
        chunks.append("===== Page %d =====" % page.number)
        if not page.text_layer:
            chunks.append("[无文本层，疑似扫描件；未执行 OCR]")
        for block in page.blocks:
            if block.get("furniture") and not keep_headers:
                continue
            if _inside_any_table(block, page.tables):
                continue
            text = _block_text(block, keep_headers)
            if text:
                chunks.append(text)
        for index, table in enumerate(page.tables, start=1):
            rows = table.get("rows") or []
            if not rows:
                continue
            chunks.append("[Table %d]" % index)
            for row in rows:
                chunks.append("\t".join("" if cell is None else str(cell) for cell in row))
        for link in _unique_links(page.links):
            uri = link.get("uri")
            if uri:
                chunks.append("[link] %s" % uri)
            elif link.get("target_page_index") is not None:
                chunks.append("[link] 第 %d 页" % (int(link["target_page_index"]) + 1))
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"
