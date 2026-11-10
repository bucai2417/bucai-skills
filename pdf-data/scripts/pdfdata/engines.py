# -*- coding: utf-8 -*-
"""Engine adapters: PyMuPDF (primary), pdfplumber (tables/cross-check), pypdf (metadata/forms)."""

from __future__ import annotations

import datetime as _dt
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - exercised only on missing dependency
    fitz = None

try:
    import pdfplumber
except ImportError:  # pragma: no cover
    pdfplumber = None

try:
    import pypdf
    from pypdf import PdfReader
except ImportError:  # pragma: no cover
    pypdf = None
    PdfReader = None

try:
    from pypdf import PasswordType
except ImportError:  # pragma: no cover
    try:
        from pypdf.constants import PasswordType
    except Exception:
        PasswordType = None


class PdfDataError(Exception):
    """Expected, user-facing failure. exit_code tells the CLI what to return."""

    exit_code = 2

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class EncryptedPdfError(PdfDataError):
    exit_code = 3


def lib_versions() -> Dict[str, Optional[str]]:
    return {
        "pymupdf": getattr(fitz, "VersionBind", None) if fitz is not None else None,
        "pdfplumber": getattr(pdfplumber, "__version__", None) if pdfplumber is not None else None,
        "pypdf": getattr(pypdf, "__version__", None) if pypdf is not None else None,
    }


def optional_dependency_warnings() -> List[str]:
    missing: List[str] = []
    if pdfplumber is None:
        missing.append("pdfplumber")
    if pypdf is None:
        missing.append("pypdf")
    return missing


def open_mupdf(path: Path, password: Optional[str] = None):
    if fitz is None:
        raise PdfDataError("缺少依赖 pymupdf：pip install pymupdf")
    if not os.path.isfile(path):
        raise PdfDataError("文件不存在：%s" % path)
    try:
        if hasattr(fitz, "no_recommend_layout"):
            fitz.no_recommend_layout()
        doc = fitz.open(str(path))
    except Exception as exc:
        raise PdfDataError("无法打开 PDF：%s" % exc)

    if doc.page_count == 0:
        doc.close()
        raise PdfDataError("PDF 为零页")

    if doc.needs_pass:
        authenticated = bool(doc.authenticate(""))
        if not authenticated and password:
            try:
                authenticated = bool(doc.authenticate(password))
            except Exception:
                authenticated = False
        if not authenticated:
            doc.close()
            raise EncryptedPdfError(
                "PDF 已加密，未提供有效密码；使用 --password 传入后重试"
            )
    return doc


def _rect(value: Any) -> Optional[List[float]]:
    if value is None:
        return None
    try:
        x0, y0, x1, y1 = float(value[0]), float(value[1]), float(value[2]), float(value[3])
    except Exception:
        return None
    return [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)]


def _as_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def _pypdf_meta(reader) -> Dict[str, Any]:
    meta = {
        "title": None,
        "author": None,
        "subject": None,
        "keywords": None,
        "creator": None,
        "producer": None,
        "creation_date": None,
        "modification_date": None,
        "source": None,
    }
    try:
        md = reader.metadata
    except Exception:
        return meta
    if md is None:
        return meta

    def get(*keys: str) -> Optional[str]:
        for key in keys:
            try:
                value = md.get(key)
            except Exception:
                value = None
            text = _as_text(value)
            if text:
                return text
        return None

    meta.update(
        {
            "title": get("/Title", "Title"),
            "author": get("/Author", "Author"),
            "subject": get("/Subject", "Subject"),
            "keywords": get("/Keywords", "Keywords"),
            "creator": get("/Creator", "Creator"),
            "producer": get("/Producer", "Producer"),
            "source": "pypdf",
        }
    )
    for attr, key in (
        ("creation_date", "creation_date"),
        ("modification_date", "modification_date"),
    ):
        try:
            value = getattr(md, attr, None)
            meta[key] = _as_text(value)
        except Exception:
            pass
    if not meta["creation_date"]:
        meta["creation_date"] = get("/CreationDate", "CreationDate")
    if not meta["modification_date"]:
        meta["modification_date"] = get("/ModDate", "ModDate")
    return meta


def _fitz_meta(doc) -> Dict[str, Any]:
    raw = {}
    try:
        raw = doc.metadata or {}
    except Exception:
        pass
    return {
        "title": _as_text(raw.get("title")),
        "author": _as_text(raw.get("author")),
        "subject": _as_text(raw.get("subject")),
        "keywords": _as_text(raw.get("keywords")),
        "creator": _as_text(raw.get("creator")),
        "producer": _as_text(raw.get("producer")),
        "creation_date": _as_text(raw.get("creationDate")),
        "modification_date": _as_text(raw.get("modDate")),
        "source": "fitz",
    }


def _outline_fitz(doc) -> List[Dict[str, Any]]:
    try:
        toc = doc.get_toc(simple=True) or []
    except Exception:
        return []
    outline: List[Dict[str, Any]] = []
    for item in toc:
        if len(item) < 3:
            continue
        level, title, page = item[0], item[1], item[2]
        try:
            page_index = int(page) - 1 if int(page) > 0 else None
        except Exception:
            page_index = None
        outline.append(
            {"level": int(level), "title": str(title), "page_index": page_index}
        )
    return outline


def _outline_pypdf(reader) -> List[Dict[str, Any]]:
    outline: List[Dict[str, Any]] = []

    def walk(items: Sequence[Any], level: int) -> None:
        for item in items:
            if isinstance(item, list):
                walk(item, level + 1)
                continue
            title = getattr(item, "title", None)
            try:
                page_index = int(reader.get_destination_page_number(item))
            except Exception:
                page_index = None
            if title:
                outline.append(
                    {"level": level, "title": str(title), "page_index": page_index}
                )

    try:
        walk(reader.outline or [], 1)
    except Exception:
        return []
    return outline


def _field_value(field: Dict[str, Any]) -> str:
    for key in ("/V", "V"):
        try:
            value = field.get(key)
        except Exception:
            value = None
        if value is None:
            continue
        try:
            return str(value)
        except Exception:
            return ""
    return ""


def _form_fields(reader, doc) -> List[Dict[str, Any]]:
    fields: List[Dict[str, Any]] = []
    if reader is not None:
        try:
            for name, field in (reader.get_fields() or {}).items():
                field_type = ""
                for key in ("/FT", "FT"):
                    try:
                        field_type = str(field.get(key) or "")
                    except Exception:
                        field_type = ""
                    if field_type:
                        break
                fields.append(
                    {
                        "name": str(name),
                        "field_type": field_type,
                        "value": _field_value(field),
                    }
                )
        except Exception:
            fields = []
    if fields or doc is None:
        return fields
    try:
        for page in doc:
            for widget in page.widgets() or []:
                try:
                    fields.append(
                        {
                            "name": str(widget.field_name or ""),
                            "field_type": str(widget.field_type_string or ""),
                            "value": str(widget.field_value or ""),
                        }
                    )
                except Exception:
                    continue
    except Exception:
        return fields
    return fields


def _attachments(doc) -> List[Dict[str, Any]]:
    attachments: List[Dict[str, Any]] = []
    try:
        names = doc.embfile_names() or []
    except Exception:
        return attachments
    for name in names:
        info: Dict[str, Any] = {}
        try:
            info = doc.embfile_info(name) or {}
        except Exception:
            info = {}
        size = info.get("length") or info.get("size")
        try:
            size = int(size) if size is not None else None
        except Exception:
            size = None
        attachments.append({"name": str(name), "size_bytes": size})
    return attachments


def _access_mode(path: Path, password: Optional[str]) -> str:
    if PdfReader is None:
        return "unknown"
    try:
        reader = PdfReader(str(path))
        if not getattr(reader, "is_encrypted", False):
            return "none"
        result = reader.decrypt(password or "")
        if PasswordType is not None:
            if result == PasswordType.OWNER_PASSWORD:
                return "owner"
            if result == PasswordType.USER_PASSWORD:
                return "user"
            if result == PasswordType.NOT_DECRYPTED:
                return "unknown"
        return "unknown"
    except Exception:
        return "unknown"


def collect_document_meta(doc, path: Path, password: Optional[str] = None) -> Dict[str, Any]:
    reader = None
    if PdfReader is not None:
        try:
            reader = PdfReader(str(path))
        except Exception:
            reader = None

    metadata = _pypdf_meta(reader) if reader is not None else _fitz_meta(doc)
    if reader is not None and not any(
        metadata.get(key)
        for key in ("title", "author", "subject", "keywords", "creator", "producer")
    ):
        metadata = _fitz_meta(doc)

    outline = _outline_fitz(doc)
    if not outline and reader is not None:
        outline = _outline_pypdf(reader)

    return {
        "page_count": doc.page_count,
        "encrypted": bool(getattr(doc, "is_encrypted", False) or doc.needs_pass),
        "access": _access_mode(path, password),
        "metadata": metadata,
        "outline": outline,
        "form_fields": _form_fields(reader, doc),
        "attachments": _attachments(doc),
        "engines": lib_versions(),
    }


_LINK_KINDS = {}
if fitz is not None:
    _LINK_KINDS = {
        getattr(fitz, "LINK_GOTO", 1): "goto",
        getattr(fitz, "LINK_URI", 2): "uri",
        getattr(fitz, "LINK_LAUNCH", 3): "launch",
        getattr(fitz, "LINK_NAMED", 4): "named",
        getattr(fitz, "LINK_GOTOR", 5): "gotor",
    }


def _links(page) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    try:
        raw_links = page.get_links() or []
    except Exception:
        return links
    for link in raw_links:
        kind = _LINK_KINDS.get(link.get("kind"), "other")
        rect = link.get("from")
        label = ""
        if rect is not None:
            try:
                label = (page.get_textbox(rect) or "").strip()
            except Exception:
                label = ""
        target = link.get("page")
        target_index = None
        if kind in ("goto", "gotor") and target is not None:
            try:
                target_index = int(target) if int(target) >= 0 else None
            except Exception:
                target_index = None
        links.append(
            {
                "kind": kind,
                "uri": link.get("uri"),
                "target_page_index": target_index,
                "bbox": _rect(rect),
                "label": label,
            }
        )
    return links


def _images(page) -> Tuple[List[Dict[str, Any]], float]:
    images: List[Dict[str, Any]] = []
    area = 0.0
    try:
        infos = page.get_image_info(xrefs=True) or []
    except Exception:
        return images, 0.0
    for index, info in enumerate(infos):
        bbox = _rect(info.get("bbox"))
        if bbox is not None:
            area += max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
        images.append(
            {
                "id": "p%d-i%d" % (page.number + 1, index),
                "xref": info.get("xref"),
                "bbox": bbox,
                "width": info.get("width"),
                "height": info.get("height"),
                "colorspace": info.get("colorspace"),
                "bpc": info.get("bpc"),
                "ext": None,
                "file": None,
            }
        )
    page_area = float(page.rect.width) * float(page.rect.height)
    coverage = min(1.0, area / page_area) if page_area > 0 else 0.0
    return images, round(coverage, 4)


def _mupdf_tables(page) -> List[Dict[str, Any]]:
    if not hasattr(page, "find_tables"):
        return []
    try:
        finder = page.find_tables(strategy="lines")
    except Exception:
        return []
    tables: List[Dict[str, Any]] = []
    for index, table in enumerate(getattr(finder, "tables", []) or []):
        rows: List[List[str]] = []
        try:
            for row in table.extract() or []:
                rows.append(["" if cell is None else str(cell).strip() for cell in row])
        except Exception:
            continue
        cell_bboxes: List[Optional[List[float]]] = []
        try:
            for row in table.rows:
                for cell in row.cells:
                    cell_bboxes.append(_rect(cell) if cell is not None else None)
        except Exception:
            try:
                cell_bboxes = [_rect(cell) if cell is not None else None for cell in table.cells]
            except Exception:
                cell_bboxes = []
        tables.append(
            {
                "id": "p%d-t%d" % (page.number + 1, index),
                "engine": "mupdf",
                "bbox": _rect(table.bbox),
                "rows": rows,
                "cell_bboxes": cell_bboxes,
                "cross_check": {"status": "unverified", "engine": "none"},
            }
        )
    return tables


def _span_dict(span: Dict[str, Any], char_coords: bool) -> Dict[str, Any]:
    if char_coords:
        chars = []
        for char in span.get("chars", []) or []:
            chars.append(
                {
                    "bbox": _rect(char.get("bbox")),
                    "origin": list(char.get("origin", (0.0, 0.0))),
                    "c": char.get("c", ""),
                }
            )
        text = "".join(char["c"] for char in chars)
    else:
        chars = None
        text = span.get("text", "")
    data: Dict[str, Any] = {
        "bbox": _rect(span.get("bbox")),
        "text": text,
        "font": span.get("font", ""),
        "size": round(float(span.get("size", 0) or 0), 2),
        "flags": span.get("flags", 0),
        "color": span.get("color", 0),
    }
    if chars is not None:
        data["chars"] = chars
    return data


def read_page_raw(
    page, char_coords: bool = False, table_strategy: str = "auto"
) -> Dict[str, Any]:
    mode = "rawdict" if char_coords else "dict"
    try:
        page_dict = page.get_text(mode, sort=False) or {}
    except Exception:
        page_dict = {}

    blocks: List[Dict[str, Any]] = []
    for block in page_dict.get("blocks", []) or []:
        if block.get("type") != 0:
            continue
        lines: List[Dict[str, Any]] = []
        for line in block.get("lines", []) or []:
            spans = [_span_dict(span, char_coords) for span in line.get("spans", []) or []]
            if not spans:
                continue
            lines.append(
                {
                    "bbox": _rect(line.get("bbox")),
                    "spans": spans,
                    "text": "".join(span["text"] for span in spans),
                }
            )
        if not lines:
            continue
        blocks.append(
            {"bbox": _rect(block.get("bbox")), "lines": lines, "furniture": False}
        )

    words: List[List[Any]] = []
    try:
        for word in page.get_text("words") or []:
            words.append(
                [float(word[0]), float(word[1]), float(word[2]), float(word[3]), word[4]]
            )
    except Exception:
        words = []

    try:
        text = page.get_text("text") or ""
    except Exception:
        text = ""

    links = _links(page)
    images, image_coverage = _images(page)
    tables = _mupdf_tables(page) if table_strategy in ("auto", "mupdf") else []
    return {
        "index": int(page.number),
        "rect": page.rect,
        "layout_rect": page.mediabox,
        "rotation": int(page.rotation),
        "text": text,
        "blocks": blocks,
        "words": words,
        "links": links,
        "images": images,
        "image_coverage": image_coverage,
        "tables": tables,
    }


def _plumber_bbox(cell: Any) -> Optional[List[float]]:
    direct = _rect(cell)
    if direct is not None:
        return direct
    try:
        return _rect(cell.bbox)
    except Exception:
        pass
    try:
        return _rect(
            (cell.get("x0"), cell.get("top"), cell.get("x1"), cell.get("bottom"))
        )
    except Exception:
        return None


class PlumberSession:
    """One pdfplumber document reused across pages; closed by the caller."""

    def __init__(self, path: Path, password: Optional[str] = None) -> None:
        self.path = str(path)
        self.password = password or ""
        self.pdf = None

    def open(self) -> bool:
        if pdfplumber is None:
            return False
        try:
            self.pdf = pdfplumber.open(self.path, password=self.password)
            return True
        except Exception:
            self.pdf = None
            return False

    def close(self) -> None:
        if self.pdf is not None:
            try:
                self.pdf.close()
            except Exception:
                pass
            self.pdf = None

    def __enter__(self) -> "PlumberSession":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def page_data(self, index: int) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        if self.pdf is None:
            return None, []
        try:
            page = self.pdf.pages[index]
        except Exception:
            return None, []
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        tables: List[Dict[str, Any]] = []
        try:
            raw_tables = page.find_tables()
        except Exception:
            raw_tables = []
        for table_index, table in enumerate(raw_tables or []):
            rows: List[List[str]] = []
            try:
                for row in table.extract() or []:
                    rows.append(["" if cell is None else str(cell).strip() for cell in row])
            except Exception:
                continue
            cell_bboxes: List[Optional[List[float]]] = []
            try:
                for row in table.rows:
                    for cell in row.cells:
                        cell_bboxes.append(_plumber_bbox(cell) if cell is not None else None)
            except Exception:
                cell_bboxes = []
            bbox = None
            try:
                bbox = _rect(table.bbox)
            except Exception:
                bbox = None
            tables.append(
                {
                    "id": "p%d-pt%d" % (index + 1, table_index),
                    "engine": "pdfplumber",
                    "bbox": bbox,
                    "rows": rows,
                    "cell_bboxes": cell_bboxes,
                    "cross_check": {"status": "unverified", "engine": "none"},
                }
            )
        return text, tables
