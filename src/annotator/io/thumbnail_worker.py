from __future__ import annotations

from pathlib import Path

from PIL import Image as PILImage
from PySide6.QtCore import QObject, Signal

from src.annotator.core.models import Image
from src.annotator.storage.repository import ProjectRepository

THUMBNAIL_SIZE = 200


class ThumbnailWorker(QObject):
    progress = Signal(int, int)
    finished = Signal()

    def __init__(self, db_path: Path, thumbnails_dir: Path) -> None:
        super().__init__()
        self._db_path = db_path
        self._thumbnails_dir = thumbnails_dir
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        repo = ProjectRepository(self._db_path)
        try:
            pending = list(repo.iter_images_without_thumbnails())
            total = len(pending)
            if total == 0:
                self.finished.emit()
                return
            for i, image in enumerate(pending):
                if self._stop:
                    break
                self._generate(image, repo)
                self.progress.emit(i + 1, total)
        finally:
            repo.close()
        self.finished.emit()

    def _generate(self, image: Image, repo: ProjectRepository) -> None:
        try:
            with PILImage.open(image.source_path) as im:
                w, h = im.size
                if im.mode != "RGB":
                    im = im.convert("RGB")
                im.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE),
                              PILImage.Resampling.LANCZOS)
                thumb_name = f"{image.id:08d}.png"
                thumb_path = self._thumbnails_dir / thumb_name
                im.save(thumb_path, "PNG", optimize=True)
        except Exception:
            return
        repo.update_image_metadata(image.id, w, h, thumb_name)
