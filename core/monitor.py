from __future__ import annotations

from typing import Callable, List, Optional

from compat import (
    QColor, QDialog, QLabel, QPainter, QPixmap, QTimer,
    Key_Escape, WinFlags, pyqtSignal,
)
from core.logger import Logger


class MonitorWindow(QDialog):
    """
    Полноэкранное окно с тестовым паттерном.
    Горизонтальные чёрно-белые полосы — меандр на видеоинтерфейсе.
    Обе фазы кешируются как QPixmap; переключение через QTimer.
    """

    stopped = pyqtSignal()

    def __init__(self, stripe_px: int, blink_ms: int, logger: Logger) -> None:
        super().__init__()
        self._stripe_px = stripe_px
        self._blink_ms = blink_ms
        self._logger = logger
        self._phase = 0
        self._cache: List[Optional[QPixmap]] = [None, None]

        self.setWindowTitle("ПЭМИН — Тест монитора")
        self.setWindowFlags(WinFlags)

        self._hint = QLabel("ESC — остановить", self)
        self._hint.setStyleSheet("color:#888; font:11px 'Courier';")
        self._hint.adjustSize()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._flip)
        self._timer.start(blink_ms)

        self.showFullScreen()
        logger.log(
            f"[Монитор] Тест запущен. Высота полосы: {stripe_px} px, "
            f"инверсия каждые {blink_ms} мс."
        )

    def _build_cache(self) -> None:
        w, h = self.width(), self.height()
        for phase in (0, 1):
            pm = QPixmap(w, h)
            painter = QPainter(pm)
            y, idx = 0, phase
            while y < h:
                bh = min(self._stripe_px, h - y)
                color = QColor(255, 255, 255) if idx % 2 == 0 else QColor(0, 0, 0)
                painter.fillRect(0, y, w, bh, color)
                y += self._stripe_px
                idx += 1
            painter.end()
            self._cache[phase] = pm

    def paintEvent(self, _) -> None:
        if self._cache[0] is None:
            self._build_cache()
        QPainter(self).drawPixmap(0, 0, self._cache[self._phase])
        self._hint.move(
            self.width() // 2 - self._hint.width() // 2,
            self.height() - 28,
        )

    def resizeEvent(self, event) -> None:
        self._cache = [None, None]
        super().resizeEvent(event)

    def _flip(self) -> None:
        self._phase = 1 - self._phase
        self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() == Key_Escape:
            self.close()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        self.stopped.emit()
        self._logger.log("[Монитор] Тест остановлен.")
        super().closeEvent(event)


class MonitorTest:
    def __init__(self, logger: Logger) -> None:
        self._logger = logger
        self._window: Optional[MonitorWindow] = None

    @property
    def running(self) -> bool:
        return self._window is not None and self._window.isVisible()

    def start(self, stripe_px: int, blink_ms: int,
              on_stopped: Optional[Callable] = None) -> None:
        if self.running:
            return
        self._window = MonitorWindow(stripe_px, blink_ms, self._logger)

        def _cleanup() -> None:
            self._window = None
            if on_stopped:
                on_stopped()

        self._window.stopped.connect(_cleanup)

    def stop(self) -> None:
        if self._window:
            self._window.close()
