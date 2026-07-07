from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from src.annotator.core.commands import Command
from src.annotator.core.mask_storage import (
    delete_mask_file,
    instance_mask_filename,
    save_binary_mask,
)

if TYPE_CHECKING:
    from src.annotator.ui.task_workspace import TaskWorkspace


class CreateInstanceCommand(Command):
    def __init__(self, workspace: "TaskWorkspace", instance_id: int,
                 image_id: int, label_id: int | None,
                 mask: np.ndarray, created_at: str) -> None:
        self.ws = workspace
        self.instance_id = instance_id
        self.image_id = image_id
        self.label_id = label_id
        self.mask = mask.copy()
        self.created_at = created_at

    def execute(self) -> None:
        ws = self.ws
        if ws._project is None:
            return
        ws._project.repo.create_instance(
            self.image_id, self.label_id,
            instance_id=self.instance_id, created_at=self.created_at,
        )
        filename = instance_mask_filename(self.image_id, self.instance_id)
        save_binary_mask(ws._project.masks_dir / filename, self.mask)
        if ws._current_image and ws._current_image.id == self.image_id:
            ws._current_instances[self.instance_id] = (self.label_id, self.mask.copy())
            ws._visible_instances.add(self.instance_id)
        ws._ensure_image_annotated(True)

    def undo(self) -> None:
        ws = self.ws
        if ws._project is None:
            return
        filename = instance_mask_filename(self.image_id, self.instance_id)
        delete_mask_file(ws._project.masks_dir / filename)
        ws._project.repo.delete_instance(self.instance_id)
        if ws._current_image and ws._current_image.id == self.image_id:
            ws._current_instances.pop(self.instance_id, None)
            ws._visible_instances.discard(self.instance_id)
        still_has = ws._project.repo.image_has_instances(self.image_id)
        ws._ensure_image_annotated(still_has)


class DeleteInstanceCommand(Command):
    def __init__(self, workspace: "TaskWorkspace", instance_id: int,
                 image_id: int, label_id: int | None,
                 mask: np.ndarray, created_at: str) -> None:
        self.ws = workspace
        self.instance_id = instance_id
        self.image_id = image_id
        self.label_id = label_id
        self.mask = mask.copy()
        self.created_at = created_at

    def execute(self) -> None:
        ws = self.ws
        if ws._project is None:
            return
        filename = instance_mask_filename(self.image_id, self.instance_id)
        delete_mask_file(ws._project.masks_dir / filename)
        ws._project.repo.delete_instance(self.instance_id)
        if ws._current_image and ws._current_image.id == self.image_id:
            ws._current_instances.pop(self.instance_id, None)
            ws._visible_instances.discard(self.instance_id)
        still_has = ws._project.repo.image_has_instances(self.image_id)
        ws._ensure_image_annotated(still_has)

    def undo(self) -> None:
        ws = self.ws
        if ws._project is None:
            return
        ws._project.repo.create_instance(
            self.image_id, self.label_id,
            instance_id=self.instance_id, created_at=self.created_at,
        )
        filename = instance_mask_filename(self.image_id, self.instance_id)
        save_binary_mask(ws._project.masks_dir / filename, self.mask)
        if ws._current_image and ws._current_image.id == self.image_id:
            ws._current_instances[self.instance_id] = (self.label_id, self.mask.copy())
            ws._visible_instances.add(self.instance_id)
        ws._ensure_image_annotated(True)


class ModifyMaskCommand(Command):
    def __init__(self, workspace: "TaskWorkspace", instance_id: int,
                 image_id: int, region: tuple[int, int, int, int],
                 before_region: np.ndarray, after_region: np.ndarray) -> None:
        self.ws = workspace
        self.instance_id = instance_id
        self.image_id = image_id
        self.region = region
        self.before = before_region.copy()
        self.after = after_region.copy()

    def _apply(self, data: np.ndarray) -> None:
        ws = self.ws
        if ws._project is None or self.instance_id not in ws._current_instances:
            return
        _lid, mask = ws._current_instances[self.instance_id]
        y1, y2, x1, x2 = self.region
        mask[y1:y2, x1:x2] = data
        filename = instance_mask_filename(self.image_id, self.instance_id)
        save_binary_mask(ws._project.masks_dir / filename, mask)

    def execute(self) -> None:
        self._apply(self.after)

    def undo(self) -> None:
        self._apply(self.before)


class ChangeClassCommand(Command):
    def __init__(self, workspace: "TaskWorkspace", instance_id: int,
                 old_label_id: int | None, new_label_id: int | None) -> None:
        self.ws = workspace
        self.instance_id = instance_id
        self.old_label_id = old_label_id
        self.new_label_id = new_label_id

    def _apply(self, label_id: int | None) -> None:
        ws = self.ws
        if ws._project is None:
            return
        ws._project.repo.update_instance_label(self.instance_id, label_id)
        if self.instance_id in ws._current_instances:
            _, mask = ws._current_instances[self.instance_id]
            ws._current_instances[self.instance_id] = (label_id, mask)

    def execute(self) -> None:
        self._apply(self.new_label_id)

    def undo(self) -> None:
        self._apply(self.old_label_id)
