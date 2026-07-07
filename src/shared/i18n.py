"""Интернационализация.

Расширяет оригинальный i18n товарища строками анализатора.
Annotator-код может импортировать tr/set_current_language отсюда напрямую.
"""
from __future__ import annotations


SUPPORTED_LANGUAGES: dict[str, str] = {
    "ru": "Русский",
    "en": "English",
}

_ANNOTATOR_EN: dict[str, str] = {
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
}

_ANALYZER_EN: dict[str, str] = {
    # Панели
    "Модель YOLO": "YOLO Model",
    "Изображения": "Images",
    "Список файлов": "File list",
    "Качество кадра": "Frame quality",
    "Масштаб": "Scale",
    "QCA-метрики": "QCA Metrics",
    "Запуск": "Run",
    "Предобработка изображения": "Image Preprocessing",
    # Кнопки
    "Выбрать .pt файл": "Select .pt file",
    "Добавить файлы": "Add files",
    "Добавить папку": "Add folder",
    "Очистить": "Clear",
    "▶  Анализировать текущее": "▶  Analyse current",
    "⚡  Пакетный анализ (все)": "⚡  Batch analysis (all)",
    "✕  Отмена": "✕  Cancel",
    "📊  Сводный отчёт": "📊  Summary report",
    "Авто-windowing (отбросить 1%/99% гистограммы)": "Auto-windowing (clip 1%/99% histogram)",
    "Vesselness (Frangi) — только для просмотра": "Vesselness (Frangi) — view only",
    "Сбросить": "Reset",
    # Вкладки вида
    "Оригинал": "Original",
    "Предобработанное": "Preprocessed",
    "Overlay (маски+скелет)": "Overlay (masks+skeleton)",
    "Vesselness": "Vesselness",
    # Метрики
    "Качество кадра (σ²Lap):": "Frame quality (σ²Lap):",
    "Класс:": "Class:",
    "Площадь маски (px²):": "Mask area (px²):",
    "Длина скелета (px):": "Skeleton length (px):",
    "Длина сосуда (мм):": "Vessel length (mm):",
    "Мин. диаметр (px):": "Min diameter (px):",
    "Макс. диаметр (px):": "Max diameter (px):",
    "Средн. диаметр (px):": "Mean diameter (px):",
    "Реф. диаметр, проксим. (px):": "Ref. diameter, proximal (px):",
    "% стеноза:": "Stenosis %:",
    "Степень стеноза:": "Stenosis grade:",
    "Извитость (L/d):": "Tortuosity (L/d):",
    "Диам. проксим. (px):": "Prox. diameter (px):",
    "Диам. дистал. (px):": "Dist. diameter (px):",
    # Степени стеноза
    "Норма (<25%)": "Normal (<25%)",
    "Мягкий (25–50%)": "Mild (25–50%)",
    "Умеренный (50–70%)": "Moderate (50–70%)",
    "Тяжёлый (70–90%)": "Severe (70–90%)",
    "Критический (≥90%)": "Critical (≥90%)",
    # Статусы файлов
    "Ожидание": "Pending",
    "Загружен": "Loaded",
    "Готово": "Done",
    "Ошибка": "Error",
    "Пропущен(кач.)": "Skipped(qual.)",
    # Отчёт
    "Экспорт CSV": "Export CSV",
    "Экспорт PDF": "Export PDF",
    "Экспорт HTML": "Export HTML",
    "Сводка": "Summary",
    "Все метрики": "All metrics",
    "Графики": "Charts",
    # Вкладки главного окна
    "Разметка": "Annotation",
    "Анализ": "Analysis",
}

_translations: dict[str, dict[str, str]] = {
    "en": {**_ANNOTATOR_EN, **_ANALYZER_EN},
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
