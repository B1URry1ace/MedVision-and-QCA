from __future__ import annotations
import sys
from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QApplication, QLabel, QMainWindow, QMessageBox, QTabWidget,
)
from src.shared.app_paths import projects_dir
from src.shared.constants import APP_NAME, APP_ORG
from src.shared.i18n import (
    SUPPORTED_LANGUAGES, current_language, set_current_language, tr,
)
from src.shared.theme import apply_theme
from src.annotator.core.project import Project
from src.annotator.ui.project_view import ProjectViewWidget
from src.annotator.ui.welcome_widget import WelcomeWidget
from src.annotator.ui.help_dialog import HelpDialog
from src.analyzer.ui.analyzer_window import AnalyzerWindow


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1380, 860)
        self.current_project: Project | None = None
        self._build_central()
        self._build_menu()
        self._image_pos_label = QLabel("")
        self._image_pos_label.setStyleSheet("padding-right: 8px;")
        self.statusBar().addPermanentWidget(self._image_pos_label)
        self.statusBar().showMessage("Готово")

    # ── Центральный виджет: две вкладки ──────────────────────────────────
    def _build_central(self) -> None:
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(
            "QTabBar::tab { min-width: 160px; padding: 8px 24px; font-size: 11pt; }"
        )
        self.setCentralWidget(self.tabs)

        # Вкладка 1 — Разметка (модуль товарища)
        self._annotator_widget = QMainWindow()   # внутренний контейнер
        annot_container = _AnnotatorTab(self)
        self.tabs.addTab(annot_container, "🖊  Разметка")

        # Вкладка 2 — Анализ (твой модуль)
        self.analyzer = AnalyzerWindow()
        self.tabs.addTab(self.analyzer, "🔬  Анализ")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Сохраняем ссылки для меню
        self._annot_tab: _AnnotatorTab = annot_container

    def _on_tab_changed(self, idx: int) -> None:
        if idx == 0:
            self.setWindowTitle(f"{APP_NAME} — Разметка")
        else:
            self.setWindowTitle(f"{APP_NAME} — Анализ")

    # ── Меню ─────────────────────────────────────────────────────────────
    def _build_menu(self) -> None:
        settings = QSettings(APP_ORG, "Settings")
        current_theme = settings.value("theme", "light")
        current_lang  = current_language()

        # File
        file_menu = self.menuBar().addMenu(tr("&File"))

        new_act = self._action(tr("New Project..."), "Ctrl+N")
        new_act.triggered.connect(self._on_new_project)
        file_menu.addAction(new_act)

        open_act = self._action(tr("Open Project..."), "Ctrl+O")
        open_act.triggered.connect(self._on_open_project)
        file_menu.addAction(open_act)

        close_act = self._action(tr("Close Project"), "Ctrl+W")
        close_act.triggered.connect(self._on_close_project)
        file_menu.addAction(close_act)

        file_menu.addSeparator()
        exit_act = self._action(tr("Exit"), "Ctrl+Q")
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # View
        view_menu = self.menuBar().addMenu(tr("&View"))
        theme_menu = view_menu.addMenu(tr("Theme"))
        tg = QActionGroup(self)
        tg.setExclusive(True)
        for tid, tlabel in (("light", tr("Light")), ("dark", tr("Dark"))):
            act = QAction(tlabel, self)
            act.setCheckable(True)
            act.setChecked(current_theme == tid)
            act.triggered.connect(lambda _=False, t=tid: self._set_theme(t))
            tg.addAction(act)
            theme_menu.addAction(act)

        lang_menu = view_menu.addMenu(tr("Language"))
        lg = QActionGroup(self)
        lg.setExclusive(True)
        for lid, llabel in SUPPORTED_LANGUAGES.items():
            act = QAction(llabel, self)
            act.setCheckable(True)
            act.setChecked(current_lang == lid)
            act.triggered.connect(lambda _=False, l=lid: self._set_language(l))
            lg.addAction(act)
            lang_menu.addAction(act)

        # Help
        help_menu = self.menuBar().addMenu(tr("&Help"))
        hotkeys_act = self._action(tr("Hotkeys..."), "F1")
        hotkeys_act.triggered.connect(lambda: HelpDialog(self).exec())
        help_menu.addAction(hotkeys_act)

    def _action(self, text: str, shortcut: str = "") -> QAction:
        act = QAction(text, self)
        if shortcut:
            act.setShortcut(shortcut)
        return act

    def _set_theme(self, name: str) -> None:
        apply_theme(name)
        QSettings(APP_ORG, "Settings").setValue("theme", name)

    def _set_language(self, lang: str) -> None:
        s = QSettings(APP_ORG, "Settings")
        if s.value("language", "ru") == lang:
            return
        s.setValue("language", lang)
        QMessageBox.information(self, tr("Restart required"),
                                tr("Language will be applied after restart."))

    # ── Проект (меню File → делегируем во вкладку разметки) ──────────────
    def _on_new_project(self) -> None:
        self.tabs.setCurrentIndex(0)
        self._annot_tab.welcome.focus_name_input()

    def _on_open_project(self) -> None:
        self.tabs.setCurrentIndex(0)
        self._annot_tab.open_project()

    def _on_close_project(self) -> None:
        self._annot_tab.close_project()


class _AnnotatorTab(QMainWindow):
    """
    Обёртка вкладки разметки.
    Содержит WelcomeWidget + ProjectViewWidget — точная копия логики
    оригинального MainWindow товарища, но встроенная как вкладка.
    """

    def __init__(self, parent: MainWindow) -> None:
        super().__init__(parent)
        self._main = parent
        self.current_project: Project | None = None
        self._build()

    def _build(self) -> None:
        from PySide6.QtWidgets import QStackedWidget
        self.welcome = WelcomeWidget()
        self.welcome.new_project_requested.connect(self._create_project)
        self.welcome.open_requested.connect(self._open_at_path)

        self.project_view = ProjectViewWidget()
        self.project_view.thumbnail_progress.connect(self._on_thumb_progress)
        self.project_view.image_position_changed.connect(self._on_image_pos)
        self.project_view.close_project_requested.connect(self.close_project)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.project_view)
        self.setCentralWidget(self.stack)
        self._refresh()

    def _refresh(self) -> None:
        if self.current_project is None:
            self.project_view.set_project(None)
            self.welcome.refresh()
            self.stack.setCurrentWidget(self.welcome)
        else:
            self.project_view.set_project(self.current_project)
            self.stack.setCurrentWidget(self.project_view)

    def _create_project(self, name: str) -> None:
        name = name.strip()
        if not name:
            return
        path = projects_dir() / name
        if path.exists():
            QMessageBox.warning(self, "Уже существует",
                                f"Проект '{name}' уже существует.")
            return
        try:
            self._close_current()
            self.current_project = Project.create(path, name)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать проект:\n{e}")
            return
        self._refresh()

    def open_project(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите папку проекта", str(projects_dir())
        )
        if folder:
            self._open_at_path(__import__("pathlib").Path(folder))

    def _open_at_path(self, path) -> None:
        from pathlib import Path
        path = Path(path)
        if not (path / "project.db").exists():
            QMessageBox.warning(self, "Не проект",
                                f"В папке '{path.name}' нет project.db.")
            return
        try:
            self._close_current()
            project = Project.open(path)
            if not project.repo.is_valid_project():
                project.close()
                QMessageBox.warning(self, "Не проект",
                                    "project.db не принадлежит этому приложению.")
                return
            self.current_project = project
        except Exception as e:
            QMessageBox.critical(self, "Ошибка",
                                 f"Не удалось открыть проект:\n{e}")
            return
        self._refresh()

    def close_project(self) -> None:
        self.project_view.set_project(None)
        self._close_current()
        self._refresh()

    def _close_current(self) -> None:
        if self.current_project is not None:
            self.current_project.close()
            self.current_project = None

    def _on_thumb_progress(self, current: int, total: int) -> None:
        if total == 0:
            self._main.statusBar().showMessage("Миниатюры готовы", 3000)
        elif current >= total:
            self._main.statusBar().showMessage(f"Миниатюры: {total}", 3000)
        else:
            self._main.statusBar().showMessage(f"Миниатюры: {current}/{total}")

    def _on_image_pos(self, current: int, total: int, filename: str) -> None:
        lbl = self._main._image_pos_label
        lbl.setText(f"{current}/{total}" if total else "")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    app.setStyle("Fusion")

    settings = QSettings(APP_ORG, "Settings")
    apply_theme(settings.value("theme", "light"))
    set_current_language(settings.value("language", "ru"))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())