from __future__ import annotations

import sys

from compat import (
    OS, AlignCenter, AlignRight, CursorEnd, FontBold,
    QFileDialog, QFont, QGroupBox, QLabel, QMainWindow,
    QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QWidget,
)
from core.logger import Logger
from ui.tabs.keyboard_tab import KeyboardTab
from ui.tabs.monitor_tab import MonitorTab
from ui.tabs.printer_tab import PrinterTab


class App(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"ПЭМИН — Тестовый режим СВТ  [{OS}]")
        self.setMinimumSize(760, 660)
        self.resize(820, 700)

        self._logger = Logger()
        self._build_ui()
        self._logger.message.connect(self._append_log)

        self._logger.log(
            f"[Система] ОС: {OS} | Python {sys.version.split()[0]} | "
            "Инструмент готов к работе."
        )

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(14, 12, 14, 12)

        title = QLabel("ПЭМИН — Запуск тестового режима")
        title.setFont(QFont("Arial", 14, FontBold))
        title.setAlignment(AlignCenter)
        root.addWidget(title)

        sub = QLabel(
            "Создание детерминированного периодического сигнала "
            "на интерфейсах СВТ"
        )
        sub.setAlignment(AlignCenter)
        sub.setStyleSheet("color:#666; font-size:11px;")
        root.addWidget(sub)

        # Вкладки — каждая управляет своим тестовым модулем самостоятельно
        self._mon_tab = MonitorTab(self._logger)
        self._kbd_tab = KeyboardTab(self._logger)
        self._prt_tab = PrinterTab(self._logger)

        tabs = QTabWidget()
        tabs.addTab(self._mon_tab, "  Монитор  ")
        tabs.addTab(self._kbd_tab, "  Клавиатура  ")
        tabs.addTab(self._prt_tab, "  Принтер  ")
        root.addWidget(tabs)

        stop_all_btn = QPushButton("■  Остановить все тесты")
        stop_all_btn.setStyleSheet(
            "background:#b71c1c; color:white; padding:7px; "
            "font-size:13px; border-radius:4px;"
        )
        stop_all_btn.clicked.connect(self._stop_all)
        root.addWidget(stop_all_btn)

        log_box = QGroupBox("Журнал")
        log_layout = QVBoxLayout(log_box)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Courier", 9))
        self._log.setStyleSheet("background:#1e1e1e; color:#cccccc; border:none;")
        self._log.setMinimumHeight(130)
        log_layout.addWidget(self._log)

        save_btn = QPushButton("Сохранить журнал…")
        save_btn.setStyleSheet("padding:4px 10px;")
        save_btn.clicked.connect(self._save_log)
        log_layout.addWidget(save_btn, alignment=AlignRight)

        root.addWidget(log_box)

    def _append_log(self, msg: str) -> None:
        self._log.append(msg)
        self._log.moveCursor(CursorEnd)

    def _save_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить журнал", "pemin_log.txt",
            "Text files (*.txt);;All files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._log.toPlainText())

    def _stop_all(self) -> None:
        self._mon_tab.stop()
        self._kbd_tab.stop()
        self._prt_tab.stop()

    def closeEvent(self, event) -> None:
        self._stop_all()
        event.accept()
