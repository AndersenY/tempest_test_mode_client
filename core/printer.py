from __future__ import annotations

import os
import subprocess
import threading

from compat import QThread, OS
from core.logger import Logger


class PrinterWorker(QThread):
    PATTERN = bytes([0xFF, 0x00] * 64)

    def __init__(self, port: str, interval_ms: int, logger: Logger) -> None:
        super().__init__()
        self._port = port
        self._interval_ms = interval_ms
        self._logger = logger
        self._stop = threading.Event()

    def run(self) -> None:
        self._logger.log(
            f"[Принтер] Тест запущен. Порт: {self._port}, "
            f"интервал: {self._interval_ms} мс, паттерн: 0xFF/0x00×64."
        )
        if OS == "Windows":
            self._loop_windows()
        elif OS == "Darwin":
            self._loop_macos()
        else:
            self._loop_linux()

    def _loop_windows(self) -> None:
        try:
            import win32print
            hp = win32print.OpenPrinter(self._port)
            win32print.StartDocPrinter(hp, 1, ("ПЭМИН-тест", None, "RAW"))
            win32print.StartPagePrinter(hp)
            count = 0
            while not self._stop.is_set():
                win32print.WritePrinter(hp, self.PATTERN)
                count += 1
                self._stop.wait(self._interval_ms / 1000.0)
            win32print.EndPagePrinter(hp)
            win32print.EndDocPrinter(hp)
            win32print.ClosePrinter(hp)
            self._logger.log(f"[Принтер] Отправлено посылок: {count}.")
        except ImportError:
            self._logger.log(
                "[Принтер] win32print не установлен. pip install pywin32"
            )
        except Exception as e:
            self._logger.log(f"[Принтер] Ошибка: {e}")

    def _loop_linux(self) -> None:
        try:
            count = 0
            with open(self._port, "wb") as f:
                while not self._stop.is_set():
                    f.write(self.PATTERN)
                    f.flush()
                    count += 1
                    self._stop.wait(self._interval_ms / 1000.0)
            self._logger.log(f"[Принтер] Отправлено посылок: {count}.")
        except PermissionError:
            self._logger.log(
                f"[Принтер] Нет доступа к {self._port}. "
                "Попробуйте: sudo adduser $USER lp"
            )
        except Exception as e:
            self._logger.log(f"[Принтер] Ошибка: {e}")

    def _loop_macos(self) -> None:
        try:
            count = 0
            while not self._stop.is_set():
                result = subprocess.run(
                    ["lp", "-d", self._port, "-o", "raw", "-"],
                    input=self.PATTERN, capture_output=True,
                )
                if result.returncode != 0:
                    self._logger.log(
                        "[Принтер] Ошибка lp: "
                        + result.stderr.decode(errors="replace").strip()
                    )
                    break
                count += 1
                self._stop.wait(self._interval_ms / 1000.0)
            self._logger.log(f"[Принтер] Отправлено посылок: {count}.")
        except FileNotFoundError:
            self._logger.log(
                "[Принтер] Команда lp не найдена (CUPS не установлен)."
            )
        except Exception as e:
            self._logger.log(f"[Принтер] Ошибка: {e}")

    def request_stop(self) -> None:
        self._stop.set()
        self.wait(3000)
        self._logger.log("[Принтер] Тест остановлен.")


class PrinterTest:
    PORTS_LINUX = [
        "/dev/usb/lp0", "/dev/lp0", "/dev/usb/lp1",
        "/dev/usb/lp2", "/dev/parport0",
    ]

    def __init__(self, logger: Logger) -> None:
        self._logger = logger
        self._worker: PrinterWorker | None = None

    @staticmethod
    def auto_port() -> str:
        if OS == "Windows":
            return "LPT1"
        if OS == "Darwin":
            r = subprocess.run(
                ["lpstat", "-d"], capture_output=True, text=True
            )
            if r.returncode == 0 and "destination:" in r.stdout:
                return r.stdout.split("destination:")[-1].strip()
            return ""
        for p in PrinterTest.PORTS_LINUX:
            if os.path.exists(p):
                return p
        return ""

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start(self, port: str, interval_ms: int) -> None:
        if self.running:
            return
        if not port:
            self._logger.log(
                "[Принтер] Порт не указан и не найден автоматически."
            )
            return
        self._worker = PrinterWorker(port, interval_ms, self._logger)
        self._worker.start()

    def stop(self) -> None:
        if self._worker:
            self._worker.request_stop()
            self._worker = None
