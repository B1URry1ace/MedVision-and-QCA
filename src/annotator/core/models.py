from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Label:
    id: int
    name: str
    color: str
    sort_order: int


@dataclass
class Task:
    id: int
    name: str
    created_at: datetime
    source_dir: str | None


@dataclass
class Image:
    id: int
    task_id: int
    filename: str
    source_path: str
    width: int | None
    height: int | None
    mask_filename: str | None
    thumbnail_filename: str | None
    order_index: int
    is_annotated: bool


@dataclass
class AnnotationInstance:
    instance_id: int
    image_id: int
    label_id: int | None
    created_at: datetime
