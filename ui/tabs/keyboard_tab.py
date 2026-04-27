from __future__ import annotations

from compat import OS, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget
from core.keyboard import KeyboardTest
from core.logger import Logger
from ui.helpers import green_btn, red_btn, slider_row, warn_label
from ui.status_indicator import StatusIndicator


class KeyboardTab(QWidget):
    def __init__(self, logger: Logger) -> None:
        super().__init__()
        self._test = KeyboardTest(logger)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(14, 14, 14, 14)

        desc = QLabel(
            "Периодические нажатия клавиши <b>Scroll Lock</b> с "
            "фиксированным интервалом.<br>"
            "Создаёт детерминированный импульсный сигнал на шине USB/PS2.<br>"
            "Поддерживаемые ОС: Windows, Linux (X11/Wayland), macOS."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#444; padding:4px;")
        lay.addWidget(desc)

        self._interval: QSlider = slider_row(
            lay, "Интервал (мс):", 10, 500, 50, " мс"
        )

        self._freq_lbl = QLabel("F_T ≈ 20.0 Гц")
        self._freq_lbl.setStyleSheet("color:#1565c0; font-weight:bold;")
        self._interval.valueChanged.connect(self._update_freq)
        lay.addWidget(self._freq_lbl)

        lay.addWidget(warn_label("Требуется pynput  (pip install pynput)"))

        lay.addSpacing(4)
        self._status = StatusIndicator("Тест клавиатуры не запущен")
        lay.addWidget(self._status)

        btn_row = QHBoxLayout()
        self._start_btn = green_btn("▶  Запустить тест клавиатуры", self._start)
        self._stop_btn  = red_btn("■  Остановить", self.stop)
        self._stop_btn.setEnabled(False)
        btn_row.addWidget(self._start_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addStretch()

    def _update_freq(self, ms: int) -> None:
        if ms > 0:
            self._freq_lbl.setText(f"F_T ≈ {round(1000 / ms, 1)} Гц")

    def _start(self) -> None:
        self._test.start(self._interval.value())
        if not self._test.running:
            return
        self._start_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status.set_active(True, "Тест клавиатуры запущен")

    def stop(self) -> None:
        self._test.stop()
        self._start_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._status.set_active(False, "Тест клавиатуры не запущен")

    @property
    def running(self) -> bool:
        return self._test.running
