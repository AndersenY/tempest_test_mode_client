from __future__ import annotations

from compat import QHBoxLayout, QLabel, QVBoxLayout, QWidget
from core.logger import Logger
from core.monitor import MonitorTest
from ui.helpers import green_btn, hint_label, red_btn, slider_row
from ui.status_indicator import StatusIndicator


class MonitorTab(QWidget):
    def __init__(self, logger: Logger) -> None:
        super().__init__()
        self._test = MonitorTest(logger)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(14, 14, 14, 14)

        self._desc = QLabel(
            "Паттерн: чередование чёрных/белых <b>горизонтальных</b> "
            "полос заданной высоты.<br>"
            "Создаёт меандр на видеоинтерфейсе — максимальная частота "
            "переключений пикселей."
        )
        self._desc.setWordWrap(True)
        self._desc.setStyleSheet("color:#444; padding:4px;")
        lay.addWidget(self._desc)

        self._stripe = slider_row(lay, "Высота полосы (px):", 1, 256, 32, " px")
        self._blink  = slider_row(lay, "Интервал инверсии (мс):", 50, 5000, 500, " мс")

        lay.addSpacing(4)
        self._status = StatusIndicator("Тест монитора не запущен")
        lay.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._start_btn = green_btn("▶  Запустить тест монитора", self._start)
        self._stop_btn  = red_btn("■  Остановить", self.stop)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        lay.addWidget(hint_label("Горячая клавиша для остановки: ESC (в окне теста)"))
        lay.addStretch()

    def set_theme(self, t: dict) -> None:
        self._desc.setStyleSheet(f"color:{t['text_muted']}; padding:4px;")
        self._status.set_theme(t)

    def _start(self) -> None:
        self._test.start(
            self._stripe.value(),
            self._blink.value(),
            on_stopped=self._on_stopped,
        )
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status.set_active(True, "Тест монитора запущен")

    def stop(self) -> None:
        self._test.stop()
        self._on_stopped()

    def _on_stopped(self) -> None:
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status.set_active(False, "Тест монитора не запущен")

    @property
    def running(self) -> bool:
        return self._test.running
