from __future__ import annotations

from pathlib import Path

from src.annotator.storage.repository import ProjectRepository


class Project:
    def __init__(self, path: Path, repo: ProjectRepository, name: str) -> None:
        self.path = path
        self.repo = repo
        self.name = name

    @property
    def masks_dir(self) -> Path:
        return self.path / "masks"

    @property
    def thumbnails_dir(self) -> Path:
        return self.path / "thumbnails"

    @property
    def db_path(self) -> Path:
        return self.path / "project.db"

    def close(self) -> None:
        self.repo.close()

    @classmethod
    def create(cls, path: Path, name: str) -> "Project":
        path.mkdir(parents=True, exist_ok=True)
        (path / "masks").mkdir(exist_ok=True)
        (path / "thumbnails").mkdir(exist_ok=True)
        repo = ProjectRepository(path / "project.db")
        repo.initialize(name)
        return cls(path, repo, name)

    @classmethod
    def open(cls, path: Path) -> "Project":
        db_path = path / "project.db"
        if not db_path.exists():
            raise FileNotFoundError(f"No project.db in {path}")
        repo = ProjectRepository(db_path)
        name = repo.get_meta("project_name") or path.name
        return cls(path, repo, name)
