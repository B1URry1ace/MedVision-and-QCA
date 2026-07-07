# MedVision: Coronary Angiography Segmentation & QCA Analysis

![Python](https://img.shields.io/badge/python-3.11-blue.svg)
![PySide6](https://img.shields.io/badge/PySide6-GUI-green.svg)
![YOLO](https://img.shields.io/badge/YOLO-Segmentation-yellow.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-Image_Processing-red.svg)

**MedVision** — это десктопное приложение для автономной разметки медицинских изображений (коронарных ангиограмм) и автоматического количественного анализа коронарных сосудов (QCA - Quantitative Coronary Angiography) с использованием нейросетей.

## 🚀 Основные возможности

Проект состоит из двух интегрированных модулей:

### 1. Модуль разметки (Annotator)
Предназначен для подготовки обучающих выборок с пиксельной точностью:
* **Инструменты сегментации:** кисть, ластик, полигон, лассо.
* **Авторазметка (AI-Assisted):** встроенный инференс YOLO для предразметки кадров с поддержкой CPU/GPU (CUDA).
* **Управление проектами:** ленивая подгрузка данных, фоновая генерация миниатюр, поддержка датасетов >2000 изображений. База данных на SQLite.
* **Предобработка (Image Processing):** Auto-windowing, адаптивное выравнивание гистограммы (CLAHE), фильтр Франги (Vesselness) для выделения трубчатых структур.
* **Экспорт:** совместимость с форматом CVAT Segmentation Mask 1.1.

### 2. Модуль анализа (Analyzer)
Автоматический расчет клинических метрик по маскам:
* **Пакетная обработка:** автоматический инференс YOLO по всему загруженному датасету (работает в фоновом потоке `QThread`, интерфейс не блокируется).
* **QCA-анализ:** 
  * Скелетонизация маски (алгоритм Чжана–Суэня) и построение центральной оси сосуда.
  * Построение карты расстояний (Distance Transform) для расчета радиуса и профиля диаметров.
  * Определение референсного диаметра и глобального минимума (места стеноза).
* **Метрики:** расчет степени стеноза (%) с градацией тяжести, извитость сосуда.
* **Ручная коррекция:** возможность править маску нейросети кистью/полигоном с моментальным пересчетом QCA-метрик.
* **Отчеты:** генерация сводных отчетов и графиков с выгрузкой в CSV, HTML, PDF.

## 🏗 Архитектура и технологии

Приложение построено на строгой модульной архитектуре:
* **UI:** PySide6 (QGraphicsView, QSS-стилизация).
* **Core & Processing:** NumPy, OpenCV, Pillow, scikit-image, SciPy.
* **Deep Learning:** Ultralytics YOLO (PyTorch).
* **Storage:** SQLite (внешние ключи, транзакции, WAL).

## 🛠 Установка и запуск

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/ВАШ_ЛОГИН/MedVision.git
   cd MedVision
   ```

2. Создайте виртуальное окружение и активируйте его:
   ```bash
   python -m venv venv
   source venv/bin/activate  # Для Linux/Mac
   venv\Scripts\activate     # Для Windows
   ```

3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

4. Скачайте веса модели YOLO:
   * Скачайте файл `yolo26x-seg.pt` по [этой ссылке на Google disk](https://drive.google.com/file/d/1MW3fL-T0LeR3BGsW9jIBNhFtK4ka1YaS/view?usp=sharing)
   * Поместите его в корень проекта.

5. Запустите приложение:
   ```bash
   python src/main.py
   ```

## 📸 Скриншоты работы

* <img width="819" height="885" alt="image" src="https://github.com/user-attachments/assets/0357fda4-3742-46e3-ada4-70c55c60ed18" />
 - Панель разметки и фильтры.

* <img width="1098" height="982" alt="12312312" src="https://github.com/user-attachments/assets/efa88991-c74a-43ae-a595-1cf416c03504" />
 - Профиль диаметров и расчет стеноза.

* <img width="890" height="805" alt="image" src="https://github.com/user-attachments/assets/b5c4b8b1-464a-41a8-81e7-612f9814dbb0" />
 - Пример работы метрик.

## 👥 Авторы
* Кажаненко Андрей 
* Веремеенко Кирилл
```
