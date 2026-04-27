from __future__ import annotations

from compat import OS, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget
from core.logger import Logger
from core.printer import PrinterTest
from ui.helpers import green_btn, red_btn, slider_row, warn_label
from ui.status_indicator import StatusIndicator


class PrinterTab(QWidget):
    def __init__(self, logger: Logger) -> None:
        super().__init__()
        self._test = PrinterTest(logger)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(14, 14, 14, 14)

        desc = QLabel(
            "Непрерывная посылка паттерна <b>0xFF/0x00×64</b> на "
            "принтерный порт.<br>"
            "Меандр на уровне байт — максимальная частота переключений "
            "на шине."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#444; padding:4px;")
        lay.addWidget(desc)

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Порт / имя принтера:"))
        self._port_edit = QLineEdit(PrinterTest.auto_port())
        self._port_edit.setMaximumWidth(220)
        port_row.addWidget(self._port_edit)
        port_row.addStretch()
        lay.addLayout(port_row)

        self._interval = slider_row(
            lay, "Интервал (мс):", 50, 2000, 200, " мс"
        )

        if OS == "Windows":
            warn_text = "Windows: требуется pywin32  (pip install pywin32)"
        elif OS == "Darwin":
            warn_text = "macOS: используется lp (CUPS). Имя принтера определяется автоматически."
        else:
            warn_text = "Linux: нужен доступ к порту  (sudo adduser $USER lp)"
        lay.addWidget(warn_label(warn_text))

        lay.addSpacing(4)
        self._status = StatusIndicator("Тест принтера не запущен")
        lay.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._start_btn = green_btn("▶  Запустить тест принтера", self._start)
        self._stop_btn  = red_btn("■  Остановить", self.stop)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addStretch()

    def _start(self) -> None:
        self._test.start(
            self._port_edit.text().strip(),
            self._interval.value(),
        )
        if not self._test.running:
            return
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status.set_active(True, "Тест принтера запущен")

    def stop(self) -> None:
        self._test.stop()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status.set_active(False, "Тест принтера не запущен")

    @property
    def running(self) -> bool:
        return self._test.running
