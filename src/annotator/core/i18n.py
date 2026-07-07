from __future__ import annotations


SUPPORTED_LANGUAGES = {
    "ru": "Русский",
    "en": "English",
}


_translations: dict[str, dict[str, str]] = {
    "en": {
        "Проекты": "Projects",
        "Задачи": "Tasks",
        "Название нового проекта…": "New project name…",
        "Название новой задачи…": "New task name…",
        "+ Создать": "+ Create",
        "+ Создать задачу": "+ Create task",
        "Открыть": "Open",
        "Переименовать": "Rename",
        "Удалить": "Delete",
        "Экспорт…": "Export…",
        "Закрыть проект": "Close project",
        "Объекты": "Objects",
        "Классы": "Classes",
        "Отображение": "Display",
        "Выбрать [V]": "Select [V]",
        "Полигон [P]": "Polygon [P]",
        "Полигон-ластик [L]": "Polygon eraser [L]",
        "Кисть [B]": "Brush [B]",
        "Ластик [E]": "Eraser [E]",
        "Замкнуть [Enter]": "Close [Enter]",
        "🤖 AI разметка…": "🤖 AI annotation…",
        "Размер:": "Size:",
        "Класс:": "Class:",
        "Яркость: 0": "Brightness: 0",
        "Контраст: 0": "Contrast: 0",
        "Гамма: 1.00": "Gamma: 1.00",
        "Сбросить яркость/контраст/гамму": "Reset brightness/contrast/gamma",
        "Адаптивно": "Adaptive",
        "CLAHE (адаптивная гистограммная коррекция)": "CLAHE (adaptive histogram equalization)",
        "Clip limit:": "Clip limit:",
        "Размер сетки:": "Grid size:",
        "Frangi (выделение трубчатых структур)": "Frangi (tubular structure enhancement)",
        "Маски": "Masks",
        "Прозрачность: 55%": "Opacity: 55%",
        "Карта диаметров (вместо цветов классов)": "Diameter map (instead of class colors)",
        "&File": "&File",
        "&Help": "&Help",
        "&View": "&View",
        "Theme": "Theme",
        "Light": "Light",
        "Dark": "Dark",
        "Language": "Language",
        "Restart required": "Restart required",
        "Language will be applied after restart.": "Language will be applied after restart.",
        "New Project...": "New Project...",
        "Open Project...": "Open Project...",
        "Close Project": "Close Project",
        "Save": "Save",
        "Exit": "Exit",
        "Hotkeys...": "Hotkeys...",
        "Image Annotator": "Image Annotator",
        "Готово": "Ready",
        "Проектов пока нет. Введи название и нажми «Создать».":
            "No projects yet. Enter a name and click \"Create\".",
        "Задач пока нет. Нажми «Новая задача», чтобы добавить.":
            "No tasks yet. Click \"+ Create task\" to add one.",
        "+ Добавить класс": "+ Add class",
        "Изменить": "Edit",
        "Классов пока нет.\nДобавь свой первый класс.":
            "No classes yet.\nAdd your first class.",
        "Объектов на этом изображении пока нет.\nИспользуй инструмент «Полигон» или «Кисть».":
            "No objects on this image yet.\nUse the Polygon or Brush tool.",
        "Объекты на изображении": "Objects on image",
        "Сменить класс": "Change class",
        "← К задачам": "← Back to tasks",
        "К первому изображению": "First image",
        "Предыдущее": "Previous",
        "Следующее": "Next",
        "К последнему изображению": "Last image",
        "Изображений": "Images",
        "Изменён": "Modified",
        "Папка": "Folder",
        "Миниатюры": "Thumbnails",
        "Создана": "Created",
    },
}


_current_lang: str = "ru"


def set_current_language(lang: str) -> None:
    global _current_lang
    if lang in SUPPORTED_LANGUAGES:
        _current_lang = lang


def current_language() -> str:
    return _current_lang


def tr(text: str) -> str:
    if _current_lang == "ru":
        return text
    table = _translations.get(_current_lang, {})
    return table.get(text, text)
