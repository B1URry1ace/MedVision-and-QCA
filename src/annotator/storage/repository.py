from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from src.annotator.core.models import AnnotationInstance, Image, Label, Task
from src.annotator.storage.schema import APP_NAME_TAG, SCHEMA_SQL, SCHEMA_VERSION


def _row_to_image(r: sqlite3.Row) -> Image:
    return Image(id=r["id"], task_id=r["task_id"], filename=r["filename"],
                 source_path=r["source_path"], width=r["width"],
                 height=r["height"], mask_filename=r["mask_filename"],
                 thumbnail_filename=r["thumbnail_filename"],
                 order_index=r["order_index"],
                 is_annotated=bool(r["is_annotated"]))


def _row_to_task(r: sqlite3.Row) -> Task:
    return Task(id=r["id"], name=r["name"],
                created_at=datetime.fromisoformat(r["created_at"]),
                source_dir=r["source_dir"])


def _row_to_label(r: sqlite3.Row) -> Label:
    return Label(id=r["id"], name=r["name"], color=r["color"],
                 sort_order=r["sort_order"])


def _row_to_instance(r: sqlite3.Row) -> AnnotationInstance:
    return AnnotationInstance(instance_id=r["instance_id"],
                               image_id=r["image_id"], label_id=r["label_id"],
                               created_at=datetime.fromisoformat(r["created_at"]))


class ProjectRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def initialize(self, project_name: str) -> None:
        self.conn.executescript(SCHEMA_SQL)
        now = datetime.now(timezone.utc).isoformat()
        self._set_meta("app_name", APP_NAME_TAG)
        self._set_meta("schema_version", str(SCHEMA_VERSION))
        self._set_meta("project_name", project_name)
        self._set_meta("created_at", now)
        self.conn.execute(
            "INSERT OR IGNORE INTO labels (id, name, color, sort_order) VALUES (?, ?, ?, ?)",
            (0, "background", "#000000", 0),
        )
        self.conn.commit()

    def _set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value))

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def set_meta(self, key: str, value: str) -> None:
        self._set_meta(key, value)
        self.conn.commit()

    def is_valid_project(self) -> bool:
        try:
            return self.get_meta("app_name") == APP_NAME_TAG
        except sqlite3.DatabaseError:
            return False

    def create_task(self, name: str, source_dir: str | None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self.conn.execute(
            "INSERT INTO tasks (name, created_at, source_dir) VALUES (?, ?, ?)",
            (name, now, source_dir))
        self.conn.commit()
        return int(cursor.lastrowid)

    def list_tasks(self) -> list[Task]:
        rows = self.conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
        return [_row_to_task(r) for r in rows]

    def rename_task(self, task_id: int, new_name: str) -> None:
        self.conn.execute("UPDATE tasks SET name = ? WHERE id = ?", (new_name, task_id))
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()

    def list_thumbnails_for_task(self, task_id: int) -> list[str]:
        rows = self.conn.execute(
            "SELECT thumbnail_filename FROM images "
            "WHERE task_id = ? AND thumbnail_filename IS NOT NULL", (task_id,)).fetchall()
        return [r[0] for r in rows]

    def add_images(self, task_id: int, images: list[tuple[str, str]]) -> None:
        rows = [(task_id, fn, src, idx) for idx, (fn, src) in enumerate(images)]
        self.conn.executemany(
            "INSERT INTO images (task_id, filename, source_path, order_index) "
            "VALUES (?, ?, ?, ?)", rows)
        self.conn.commit()

    def count_images(self, task_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM images WHERE task_id = ?", (task_id,)).fetchone()
        return row[0] if row else 0

    def count_thumbnails(self, task_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM images "
            "WHERE task_id = ? AND thumbnail_filename IS NOT NULL", (task_id,)).fetchone()
        return row[0] if row else 0

    def count_annotated_images(self, task_id: int) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) FROM images WHERE task_id = ? AND is_annotated = 1",
            (task_id,)).fetchone()
        return row[0] if row else 0

    def iter_images_without_thumbnails(self) -> Iterator[Image]:
        rows = self.conn.execute(
            "SELECT * FROM images WHERE thumbnail_filename IS NULL ORDER BY id").fetchall()
        for r in rows:
            yield _row_to_image(r)

    def update_image_metadata(self, image_id: int, width: int, height: int,
                               thumbnail_filename: str) -> None:
        self.conn.execute(
            "UPDATE images SET width=?, height=?, thumbnail_filename=? WHERE id=?",
            (width, height, thumbnail_filename, image_id))
        self.conn.commit()

    def update_image_annotated(self, image_id: int, is_annotated: bool) -> None:
        self.conn.execute("UPDATE images SET is_annotated=? WHERE id=?",
                          (1 if is_annotated else 0, image_id))
        self.conn.commit()

    def get_image(self, image_id: int) -> Image | None:
        row = self.conn.execute(
            "SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
        return _row_to_image(row) if row else None

    def create_instance(self, image_id: int, label_id: int | None,
                        instance_id: int | None = None,
                        created_at: str | None = None) -> tuple[int, str]:
        if created_at is None:
            created_at = datetime.now(timezone.utc).isoformat()
        if instance_id is None:
            cur = self.conn.execute(
                "INSERT INTO annotation_instances (image_id, label_id, created_at) "
                "VALUES (?, ?, ?)", (image_id, label_id, created_at))
            instance_id = int(cur.lastrowid)
        else:
            self.conn.execute(
                "INSERT INTO annotation_instances "
                "(instance_id, image_id, label_id, created_at) VALUES (?, ?, ?, ?)",
                (instance_id, image_id, label_id, created_at))
        self.conn.commit()
        return instance_id, created_at

    def get_instance(self, instance_id: int) -> AnnotationInstance | None:
        row = self.conn.execute(
            "SELECT * FROM annotation_instances WHERE instance_id=?",
            (instance_id,)).fetchone()
        return _row_to_instance(row) if row else None

    def list_instances_for_image(self, image_id: int) -> list[AnnotationInstance]:
        rows = self.conn.execute(
            "SELECT * FROM annotation_instances WHERE image_id=? ORDER BY instance_id",
            (image_id,)).fetchall()
        return [_row_to_instance(r) for r in rows]

    def delete_instance(self, instance_id: int) -> None:
        self.conn.execute(
            "DELETE FROM annotation_instances WHERE instance_id=?", (instance_id,))
        self.conn.commit()

    def update_instance_label(self, instance_id: int, label_id: int | None) -> None:
        self.conn.execute(
            "UPDATE annotation_instances SET label_id=? WHERE instance_id=?",
            (label_id, instance_id))
        self.conn.commit()

    def image_has_instances(self, image_id: int) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM annotation_instances WHERE image_id=? LIMIT 1",
            (image_id,)).fetchone()
        return row is not None

    def has_pending_thumbnails(self) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM images WHERE thumbnail_filename IS NULL LIMIT 1").fetchone()
        return row is not None

    def list_images_for_task(self, task_id: int) -> list[Image]:
        rows = self.conn.execute(
            "SELECT * FROM images WHERE task_id=? ORDER BY order_index",
            (task_id,)).fetchall()
        return [_row_to_image(r) for r in rows]

    def list_labels(self) -> list[Label]:
        rows = self.conn.execute(
            "SELECT * FROM labels ORDER BY sort_order").fetchall()
        return [_row_to_label(r) for r in rows]

    def create_label(self, name: str, color: str) -> int:
        row = self.conn.execute(
            "SELECT COALESCE(MAX(id),0), COALESCE(MAX(sort_order),0) FROM labels"
        ).fetchone()
        new_id = (row[0] or 0) + 1
        new_sort = (row[1] or 0) + 1
        self.conn.execute(
            "INSERT INTO labels (id, name, color, sort_order) VALUES (?, ?, ?, ?)",
            (new_id, name, color, new_sort))
        self.conn.commit()
        return new_id

    def update_label(self, label_id: int, name: str, color: str) -> None:
        if label_id == 0:
            raise ValueError("Cannot modify background class")
        self.conn.execute("UPDATE labels SET name=?, color=? WHERE id=?",
                          (name, color, label_id))
        self.conn.commit()

    def delete_label(self, label_id: int) -> None:
        if label_id == 0:
            raise ValueError("Cannot delete background class")
        self.conn.execute("DELETE FROM labels WHERE id=?", (label_id,))
        self.conn.commit()

    def label_name_exists(self, name: str, exclude_id: int | None = None) -> bool:
        if exclude_id is not None:
            row = self.conn.execute(
                "SELECT 1 FROM labels WHERE name=? AND id!=?",
                (name, exclude_id)).fetchone()
        else:
            row = self.conn.execute(
                "SELECT 1 FROM labels WHERE name=?", (name,)).fetchone()
        return row is not None

    def set_last_image(self, task_id: int, image_id: int) -> None:
        self.set_meta(f"task:{task_id}:last_image", str(image_id))

    def get_last_image(self, task_id: int) -> int | None:
        val = self.get_meta(f"task:{task_id}:last_image")
        if val is None:
            return None
        try:
            return int(val)
        except ValueError:
            return None

    def close(self) -> None:
        self.conn.close()
