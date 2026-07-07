#help_dialog.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)


HOTKEYS: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "Навигация",
        [
            ("← / →", "Предыдущее / следующее изображение"),
            ("Home / End", "Первое / последнее изображение"),
            ("Колесо мыши", "Зум к курсору"),
            ("Ctrl + = / Ctrl + −", "Зум in/out с клавиатуры"),
            ("Ctrl + 0", "Подогнать в окно"),
            ("ЛКМ + перетаскивание (Select)", "Панорама холста"),
        ],
    ),
    (
        "Инструменты",
        [
            ("V", "Выбрать (панорама)"),
            ("P", "Полигон"),
            ("L", "Полигон-ластик"),
            ("B", "Кисть"),
            ("E", "Ластик"),
            ("[ / ]", "Уменьшить / увеличить размер кисти"),
        ],
    ),
    (
        "Полигон / Полигон-ластик",
        [
            ("ЛКМ", "Добавить узел"),
            ("Shift + ЛКМ-drag", "Лассо (непрерывная линия)"),
            ("ПКМ (тап)", "Удалить последний узел"),
            ("ПКМ (зажать)", "Удалять узлы по очереди (после небольшой задержки)"),
            ("Enter", "Замкнуть полигон"),
            ("Esc", "Отменить текущий полигон"),
            (
                "Авто-скролл",
                "Курсор у края холста смещает изображение в эту сторону",
            ),
        ],
    ),
    (
        "Файл",
        [
            ("Ctrl + N", "Новый проект (фокус на поле имени)"),
            ("Ctrl + O", "Открыть проект"),
            ("Ctrl + W", "Закрыть проект"),
            ("Ctrl + S", "Сохранить (автосохранение тоже работает)"),
            ("Ctrl + Q", "Выход"),
        ],
    ),
    (
        "Правка",
        [
            ("Ctrl + Z", "Отменить"),
            ("Ctrl + Shift + Z / Ctrl + Y", "Повторить"),
        ],
    ),
    (
        "Прочее",
        [
            ("F1", "Эта справка"),
        ],
    ),
]


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Горячие клавиши — Image Annotator")
        self.setMinimumSize(640, 620)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(False)
        browser.setHtml(self._build_html())
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _build_html(self) -> str:
        parts: list[str] = []
        parts.append(
            "<style>"
            "h3 { margin-top: 16px; margin-bottom: 6px; }"
            "table { border-collapse: collapse; width: 100%; }"
            "td { padding: 4px 12px; vertical-align: top; }"
            "td.k { font-family: 'Consolas', 'Courier New', monospace;"
            " font-weight: bold; white-space: nowrap; }"
            "tr:nth-child(odd) td { background: #f6f6f6; }"
            "</style>"
        )
        for title, items in HOTKEYS:
            parts.append(f"<h3>{title}</h3>")
            parts.append("<table>")
            for key, desc in items:
                parts.append(
                    f"<tr><td class='k'>{key}</td><td>{desc}</td></tr>"
                )
            parts.append("</table>")
        return "".join(parts)
