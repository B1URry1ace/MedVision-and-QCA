from __future__ import annotations

from abc import ABC, abstractmethod


class Command(ABC):
    @abstractmethod
    def execute(self) -> None: ...

    @abstractmethod
    def undo(self) -> None: ...


class CompositeCommand(Command):
    def __init__(self, commands: list[Command]) -> None:
        self.commands = list(commands)

    def execute(self) -> None:
        for c in self.commands:
            c.execute()

    def undo(self) -> None:
        for c in reversed(self.commands):
            c.undo()


class CommandHistory:
    def __init__(self, capacity: int = 50) -> None:
        self.capacity = capacity
        self._undo: list[Command] = []
        self._redo: list[Command] = []

    def push(self, command: Command) -> None:
        self._undo.append(command)
        self._redo.clear()
        while len(self._undo) > self.capacity:
            self._undo.pop(0)

    def undo(self) -> bool:
        if not self._undo:
            return False
        cmd = self._undo.pop()
        cmd.undo()
        self._redo.append(cmd)
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        cmd = self._redo.pop()
        cmd.execute()
        self._undo.append(cmd)
        return True

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)
