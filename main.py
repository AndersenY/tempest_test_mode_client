"""
ПЭМИН — Запуск тестового режима СВТ
=====================================
Поддерживаемые ОС: Windows, Linux, macOS
Зависимости: Python 3.8+
  pip install PyQt6      (или PyQt5 для старых дистрибутивов)
  pip install pynput     (клавиатура на всех ОС)
Опционально:
  pip install pywin32    (принтер на Windows)

Запуск: python main.py
"""

import sys

from compat import QApplication
from ui.app import App

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = App()
    window.show()
    sys.exit(app.exec())
