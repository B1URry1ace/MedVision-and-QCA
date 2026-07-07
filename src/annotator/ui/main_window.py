#main_window.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction, QActionGroup, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
)

from src.annotator.core.app_paths import projects_dir
from src.annotator.core.i18n import SUPPORTED_LANGUAGES, current_language, tr
from src.annotator.core.project import Project
from src.annotator.ui.help_dialog import HelpDialog
from src.annotator.ui.project_view import ProjectViewWidget
from src.annotator.ui.theme import apply_theme
from src.annotator.ui.welcome_widget import WelcomeWidget


APP_NAME = "Image Annotator"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.current_project: Project | None = None
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 800)
        self._build_central()
        self._build_menu()
        self.statusBar().showMessage("Готово")
        self._refresh_view()

    def _build_central(self) -> None:
        self.welcome = WelcomeWidget()
        self.welcome.new_project_requested.connect(self._create_project)
        self.welcome.open_requested.connect(self._open_project_at_path)
        self.project_view = ProjectViewWidget()
        self.project_view.thumbnail_progress.connect(self._on_thumb_progress)
        self.project_view.image_position_changed.connect(self._on_image_position)
        self.project_view.close_project_requested.connect(self._on_close_project)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.project_view)
        self.setCentralWidget(self.stack)
        self._image_pos_label = QLabel("")
        self._image_pos_label.setStyleSheet("padding-right: 8px;")
        self.statusBar().addPermanentWidget(self._image_pos_label)

    def _build_menu(self) -> None:
        settings = QSettings("ImageAnnotator", "Settings")
        current_theme = settings.value("theme", "light")
        current_lang = current_language()

        file_menu = self.menuBar().addMenu(tr("&File"))

        new_action = self._action(tr("New Project..."), "Ctrl+N")
        new_action.triggered.connect(self._on_new_project_menu)
        file_menu.addAction(new_action)

        open_action = self._action(tr("Open Project..."), "Ctrl+O")
        open_action.triggered.connect(self._on_open_project)
        file_menu.addAction(open_action)

        close_action = self._action(tr("Close Project"), "Ctrl+W")
        close_action.triggered.connect(self._on_close_project)
        file_menu.addAction(close_action)

        file_menu.addSeparator()
        file_menu.addAction(self._action(tr("Save"), "Ctrl+S"))
        file_menu.addSeparator()

        exit_action = self._action(tr("Exit"), "Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = self.menuBar().addMenu(tr("&View"))
        theme_menu = view_menu.addMenu(tr("Theme"))
        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)
        for theme_id, label in (("light", tr("Light")), ("dark", tr("Dark"))):
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(current_theme == theme_id)
            act.triggered.connect(
                lambda _checked=False, t=theme_id: self._set_theme(t)
            )
            theme_group.addAction(act)
            theme_menu.addAction(act)

        lang_menu = view_menu.addMenu(tr("Language"))
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)
        for lang_id, label in SUPPORTED_LANGUAGES.items():
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(current_lang == lang_id)
            act.triggered.connect(
                lambda _checked=False, lid=lang_id: self._set_language(lid)
            )
            lang_group.addAction(act)
            lang_menu.addAction(act)

        help_menu = self.menuBar().addMenu(tr("&Help"))
        hotkeys_action = self._action(tr("Hotkeys..."), "F1")
        hotkeys_action.triggered.connect(self._on_show_help)
        help_menu.addAction(hotkeys_action)

    def _set_theme(self, name: str) -> None:
        apply_theme(name)
        settings = QSettings("ImageAnnotator", "Settings")
        settings.setValue("theme", name)

    def _set_language(self, lang: str) -> None:
        settings = QSettings("ImageAnnotator", "Settings")
        if settings.value("language", "ru") == lang:
            return
        settings.setValue("language", lang)
        QMessageBox.information(
            self,
            tr("Restart required"),
            tr("Language will be applied after restart."),
        )

    def _action(self, text: str, shortcut: str = "") -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        return action

    def _on_new_project_menu(self) -> None:
        self._close_current_project()
        self._refresh_view()
        self.welcome.focus_name_input()

    def _create_project(self, name: str) -> None:
        name = name.strip()
        if not name:
            return
        if any(c in '\\/:*?"<>|' for c in name) or name.endswith(('.', ' ')):
            QMessageBox.warning(
                self,
                "Недопустимое имя",
                'Имя не должно содержать символы \\ / : * ? " < > |\n'
                "и не должно заканчиваться точкой или пробелом.",
            )
            return
        path = projects_dir() / name
        if path.exists():
            QMessageBox.warning(
                self, "Уже существует", f"Проект '{name}' уже существует."
            )
            return
        try:
            self._close_current_project()
            self.current_project = Project.create(path, name)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать проект:\n{e}")
            return
        self.statusBar().showMessage(f"Проект создан: {path}")
        self._refresh_view()

    def _on_open_project(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите папку проекта", str(projects_dir())
        )
        if not folder:
            return
        self._open_project_at_path(Path(folder))

    def _open_project_at_path(self, path: Path) -> None:
        if not (path / "project.db").exists():
            QMessageBox.warning(
                self, "Не проект", f"В папке '{path.name}' нет project.db."
            )
            return
        try:
            self._close_current_project()
            project = Project.open(path)
            if not project.repo.is_valid_project():
                project.close()
                QMessageBox.warning(
                    self, "Не проект", "project.db не принадлежит этому приложению."
                )
                return
            self.current_project = project
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось открыть проект:\n{e}")
            return
        self.statusBar().showMessage(f"Открыт проект: {path}")
        self._refresh_view()

    def _on_close_project(self) -> None:
        if self.current_project is None:
            return
        self.project_view.set_project(None)
        self._close_current_project()
        self.statusBar().showMessage("Проект закрыт")
        self._refresh_view()

    def _close_current_project(self) -> None:
        if self.current_project is not None:
            self.current_project.close()
            self.current_project = None

    def _refresh_view(self) -> None:
        if self.current_project is None:
            self.project_view.set_project(None)
            self.welcome.refresh()
            self.stack.setCurrentWidget(self.welcome)
            self.setWindowTitle(APP_NAME)
        else:
            self.project_view.set_project(self.current_project)
            self.stack.setCurrentWidget(self.project_view)
            self.setWindowTitle(f"{self.current_project.name} — {APP_NAME}")

    def _on_thumb_progress(self, current: int, total: int) -> None:
        if total == 0:
            self.statusBar().showMessage("Готово", 3000)
        elif current >= total:
            self.statusBar().showMessage(f"Миниатюры готовы: {total}", 3000)
        else:
            self.statusBar().showMessage(f"Миниатюры: {current}/{total}")

    def _on_image_position(self, current: int, total: int, filename: str) -> None:
        if total == 0:
            self._image_pos_label.setText("")
        else:
            self._image_pos_label.setText(f"{current}/{total}")

    def _on_show_help(self) -> None:
        dialog = HelpDialog(self)
        dialog.exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.project_view.set_project(None)
        self._close_current_project()
        super().closeEvent(event)
