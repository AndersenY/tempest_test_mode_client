from __future__ import annotations

import threading

from compat import QThread, OS
from core.logger import Logger


class KeyboardWorker(QThread):
    def __init__(self, interval_ms: int, logger: Logger) -> None:
        super().__init__()
        self._interval_ms = interval_ms
        self._logger = logger
        self._stop = threading.Event()

    def run(self) -> None:
        freq = round(1000 / self._interval_ms, 1)
        self._logger.log(
            f"[Клавиатура] Тест запущен. Клавиша: Scroll Lock, "
            f"интервал: {self._interval_ms} мс, F_T ≈ {freq} Гц."
        )
        try:
            from pynput.keyboard import Key, Controller
            kbd = Controller()
            while not self._stop.is_set():
                kbd.press(Key.scroll_lock)
                kbd.release(Key.scroll_lock)
                self._stop.wait(self._interval_ms / 1000.0)
        except Exception as e:
            self._logger.log(f"[Клавиатура] Ошибка: {e}")

    def request_stop(self) -> None:
        self._stop.set()
        self.wait(2000)
        self._logger.log("[Клавиатура] Тест остановлен.")


class KeyboardTest:
    def __init__(self, logger: Logger) -> None:
        self._logger = logger
        self._worker: KeyboardWorker | None = None
        self.deps_ok = self._check_deps()

    def _check_deps(self) -> bool:
        try:
            import pynput  # noqa: F401
            return True
        except ImportError:
            self._logger.log(
                "[Клавиатура] ВНИМАНИЕ: pynput не найден. "
                "Установите: pip install pynput"
            )
            return False

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start(self, interval_ms: int) -> None:
        if not self.deps_ok:
            self._logger.log(
                "[Клавиатура] Запуск невозможен: установите pynput."
            )
            return
        if self.running:
            return
        self._worker = KeyboardWorker(interval_ms, self._logger)
        self._worker.start()

    def stop(self) -> None:
        if self._worker:
            self._worker.request_stop()
            self._worker = None
