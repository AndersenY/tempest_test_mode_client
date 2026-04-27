"""
PyQt6 / PyQt5 совместимость.
Импортируй отсюда все Qt-классы и константы — не из PyQt напрямую.
"""

from __future__ import annotations

import platform

try:
    from PyQt6.QtWidgets import (
        QApplication, QDialog, QFileDialog, QGroupBox,
        QHBoxLayout, QLabel, QLineEdit, QMainWindow,
        QPushButton, QSlider, QTabWidget, QTextEdit,
        QVBoxLayout, QWidget,
    )
    from PyQt6.QtCore import QObject, QThread, Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap, QTextCursor

    AlignCenter = Qt.AlignmentFlag.AlignCenter
    AlignRight  = Qt.AlignmentFlag.AlignRight
    Horizontal  = Qt.Orientation.Horizontal
    WinFlags    = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
    Key_Escape  = Qt.Key.Key_Escape
    FontBold    = QFont.Weight.Bold
    CursorEnd   = QTextCursor.MoveOperation.End

except ImportError:
    from PyQt5.QtWidgets import (  # type: ignore[no-redef]
        QApplication, QDialog, QFileDialog, QGroupBox,
        QHBoxLayout, QLabel, QLineEdit, QMainWindow,
        QPushButton, QSlider, QTabWidget, QTextEdit,
        QVBoxLayout, QWidget,
    )
    from PyQt5.QtCore import QObject, QThread, Qt, QTimer, pyqtSignal  # type: ignore[no-redef]
    from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap, QTextCursor  # type: ignore[no-redef]

    AlignCenter = Qt.AlignCenter  # type: ignore[attr-defined]
    AlignRight  = Qt.AlignRight  # type: ignore[attr-defined]
    Horizontal  = Qt.Horizontal  # type: ignore[attr-defined]
    WinFlags    = Qt.FramelessWindowHint | Qt.Window  # type: ignore[attr-defined]
    Key_Escape  = Qt.Key_Escape  # type: ignore[attr-defined]
    FontBold    = QFont.Bold  # type: ignore[attr-defined]
    CursorEnd   = QTextCursor.End  # type: ignore[attr-defined]

OS: str = platform.system()  # 'Windows' | 'Linux' | 'Darwin'
