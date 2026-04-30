"""
Клиент удалённого управления от ПЭМИН-детектора.

Принимаемые команды:
  {"cmd": "test_start"}  — включить тестовый сигнал
  {"cmd": "test_stop"}   — выключить тестовый сигнал
  {"cmd": "ping"}        — проверка связи
"""

from __future__ import annotations

import json
import socket
import threading
from typing import Callable

PORT_DEFAULT = 62000


class RemoteClient:
    """
    Подключается к TCP-серверу детектора и получает команды.
    Потокобезопасен. on_command и on_disconnected вызываются из фонового потока —
    убедитесь, что обработчики используют Qt-сигналы для обновления UI.
    """

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self.on_command: Callable[[str], None] = lambda cmd: None
        self.on_disconnected: Callable[[], None] = lambda: None

    # ── Публичный интерфейс ────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._running and self._sock is not None

    def connect(self, host: str, port: int = PORT_DEFAULT) -> None:
        """Подключиться к серверу. Бросает OSError при ошибке."""
        if self._running:
            self.disconnect()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)
        sock.connect((host, port))
        sock.settimeout(None)
        self._sock = sock
        self._running = True
        self._thread = threading.Thread(
            target=self._recv_loop, daemon=True, name="rc-client-recv"
        )
        self._thread.start()

    def disconnect(self) -> None:
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    # ── Внутренняя реализация ──────────────────────────────────────────

    def _recv_loop(self) -> None:
        buf = ""
        try:
            while self._running:
                assert self._sock is not None
                chunk = self._sock.recv(512)
                if not chunk:
                    break
                buf += chunk.decode(errors="replace")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    cmd = msg.get("cmd", "")
                    if cmd == "ping":
                        continue
                    if cmd:
                        self.on_command(cmd)
        except OSError:
            pass
        finally:
            self._running = False
            self._sock = None
            self.on_disconnected()
