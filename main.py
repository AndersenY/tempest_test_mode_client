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
import os

# Иконка в таскбаре Windows
if sys.platform == "win32":
    import ctypes
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("pemin.client")

from compat import QApplication, QIcon
from ui.app import App


def _install_desktop_entry():
    base = os.path.dirname(os.path.abspath(__file__))
    icon = os.path.join(base, "image", "icon.png")
    desktop_dir = os.path.join(os.path.expanduser("~"), ".local", "share", "applications")
    os.makedirs(desktop_dir, exist_ok=True)
    with open(os.path.join(desktop_dir, "pemin-client.desktop"), "w", encoding="utf-8") as f:
        f.write(f"""[Desktop Entry]
Name=ПЭМИН Тест
Exec=python3 {base}/main.py
Icon={icon}
Type=Application
StartupWMClass=main
Categories=Science;
""")
    os.system("update-desktop-database " + desktop_dir)


if __name__ == "__main__":
    if sys.platform == "linux":
        _install_desktop_entry()
    app = QApplication(sys.argv)
    app.setDesktopFileName("pemin-client")
    _icon = QIcon(os.path.join(os.path.dirname(os.path.abspath(__file__)), "image", "icon.png"))
    app.setWindowIcon(_icon)
    app.setStyle("Fusion")
    window = App()
    window.setWindowIcon(_icon)
    window.show()
    sys.exit(app.exec())
