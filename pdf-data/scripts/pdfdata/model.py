# -*- coding: utf-8 -*-
"""Data containers shared by the PDF extraction pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Options:
    out_dir: Optional[str] = None
    fmt: str = "both"
    pages: Optional[List[int]] = None
    pages_spec: Optional[str] = None
    password: Optional[str] = None
    table_strategy: str = "auto"
    images: str = "meta"
    keep_headers: bool = False
    char_coords: bool = False
    crosscheck: bool = True
    stdout: bool = False

    def public(self) -> Dict[str, Any]:
        return {
            "format": self.fmt,
            "pages": self.pages,
            "table_strategy": self.table_strategy,
            "images": self.images,
            "keep_headers": self.keep_headers,
            "char_coords": self.char_coords,
            "crosscheck": self.crosscheck,
        }


@dataclass
class WarningItem:
    code: str
    message: str
    page_index: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "page_index": self.page_index,
            "message": self.message,
        }


@dataclass
class PageResult:
    index: int
    number: int
    width: float
    height: float
    rotation: int
    coordinate_space: str
    text_layer: bool
    char_count: int
    word_count: int
    layout: Dict[str, Any]
    quality: Dict[str, Any]
    blocks: List[Dict[str, Any]]
    text: str
    tables: List[Dict[str, Any]]
    links: List[Dict[str, Any]]
    images: List[Dict[str, Any]]
    headers_footers: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "number": self.number,
            "width": round(self.width, 2),
            "height": round(self.height, 2),
            "rotation": self.rotation,
            "coordinate_space": self.coordinate_space,
            "text_layer": self.text_layer,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "layout": self.layout,
            "quality": self.quality,
            "blocks": self.blocks,
            "text": self.text,
            "tables": self.tables,
            "links": self.links,
            "images": self.images,
            "headers_footers": self.headers_footers,
        }


@dataclass
class DocumentResult:
    source: Dict[str, Any]
    document: Dict[str, Any]
    pages: List[PageResult] = field(default_factory=list)
    warnings: List[WarningItem] = field(default_factory=list)
    extraction: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "1.0",
            "source": self.source,
            "document": self.document,
            "pages": [page.to_dict() for page in self.pages],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "extraction": self.extraction,
        }
