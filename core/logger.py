from __future__ import annotations

from datetime import datetime

from compat import QObject, pyqtSignal


class Logger(QObject):
    message = pyqtSignal(str)

    def log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.message.emit(f"[{ts}] {msg}")
