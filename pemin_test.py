"""
ПЭМИН — Запуск тестового режима СВТ
=====================================
Поддерживаемые ОС: Windows, Linux, macOS
Зависимости: Python 3.8+
  pip install PyQt6      (или PyQt5 для старых дистрибутивов)
  pip install pynput     (клавиатура на всех ОС)
Опционально:
  pip install pywin32    (принтер на Windows)
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime
from typing import Callable, List, Optional

# ── PyQt6 / PyQt5 dual support ───────────────────────────────────────────────
try:
    from PyQt6.QtWidgets import (
        QApplication, QDialog, QFileDialog, QGroupBox, QHBoxLayout,
        QLabel, QLineEdit, QMainWindow, QPushButton, QSlider,
        QTabWidget, QTextEdit, QVBoxLayout, QWidget,
    )
    from PyQt6.QtCore import QObject, QThread, Qt, QTimer, pyqtSignal
    from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap, QTextCursor
    _AC   = Qt.AlignmentFlag.AlignCenter
    _AR   = Qt.AlignmentFlag.AlignRight
    _H    = Qt.Orientation.Horizontal
    _WF   = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
    _ESC  = Qt.Key.Key_Escape
    _BOLD = QFont.Weight.Bold
    _END  = QTextCursor.MoveOperation.End
except ImportError:
    from PyQt5.QtWidgets import (  # type: ignore[assignment]
        QApplication, QDialog, QFileDialog, QGroupBox, QHBoxLayout,
        QLabel, QLineEdit, QMainWindow, QPushButton, QSlider,
        QTabWidget, QTextEdit, QVBoxLayout, QWidget,
    )
    from PyQt5.QtCore import QObject, QThread, Qt, QTimer, pyqtSignal  # type: ignore[assignment]
    from PyQt5.QtGui import QColor, QFont, QPainter, QPixmap, QTextCursor  # type: ignore[assignment]
    _AC   = Qt.AlignCenter  # type: ignore[attr-defined]
    _AR   = Qt.AlignRight  # type: ignore[attr-defined]
    _H    = Qt.Horizontal  # type: ignore[attr-defined]
    _WF   = Qt.FramelessWindowHint | Qt.Window  # type: ignore[attr-defined]
    _ESC  = Qt.Key_Escape  # type: ignore[attr-defined]
    _BOLD = QFont.Bold  # type: ignore[attr-defined]
    _END  = QTextCursor.End  # type: ignore[attr-defined]

OS = platform.system()  # 'Windows' | 'Linux' | 'Darwin'


# ── Потокобезопасный лог ──────────────────────────────────────────────────────

class Logger(QObject):
    message = pyqtSignal(str)

    def log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.message.emit(f"[{ts}] {msg}")


# ── Модуль 1: Монитор ─────────────────────────────────────────────────────────

class MonitorWindow(QDialog):
    """
    Полноэкранное окно с тестовым паттерном.
    Паттерн: чередование чёрных/белых горизонтальных полос —
    меандр на видеоинтерфейсе, максимальная частота переключений.
    Обе фазы кешируются как QPixmap; смена фазы через QTimer.
    """

    stopped = pyqtSignal()

    def __init__(self, stripe_px: int, blink_ms: int, logger: Logger) -> None:
        super().__init__()
        self.stripe_px = stripe_px
        self.blink_ms = blink_ms
        self.logger = logger
        self.phase = 0
        self._cache: List[Optional[QPixmap]] = [None, None]

        self.setWindowTitle("ПЭМИН — Тест монитора")
        self.setWindowFlags(_WF)

        self._hint = QLabel("ESC — остановить", self)
        self._hint.setStyleSheet("color:#888; font:11px 'Courier';")
        self._hint.adjustSize()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._flip)
        self._timer.start(blink_ms)

        self.showFullScreen()
        logger.log(
            f"[Монитор] Тест запущен. Ширина полосы: {stripe_px} px, "
            f"инверсия каждые {blink_ms} мс."
        )

    def _build_cache(self) -> None:
        w, h = self.width(), self.height()
        for phase in (0, 1):
            pm = QPixmap(w, h)
            painter = QPainter(pm)
            y, idx = 0, phase
            while y < h:
                bh = min(self.stripe_px, h - y)
                color = QColor(255, 255, 255) if idx % 2 == 0 else QColor(0, 0, 0)
                painter.fillRect(0, y, w, bh, color)
                y += self.stripe_px
                idx += 1
            painter.end()
            self._cache[phase] = pm

    def paintEvent(self, _) -> None:
        if self._cache[0] is None:
            self._build_cache()
        QPainter(self).drawPixmap(0, 0, self._cache[self.phase])
        self._hint.move(
            self.width() // 2 - self._hint.width() // 2,
            self.height() - 28,
        )

    def resizeEvent(self, event) -> None:
        self._cache = [None, None]
        super().resizeEvent(event)

    def _flip(self) -> None:
        self.phase = 1 - self.phase
        self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() == _ESC:
            self.close()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        self.stopped.emit()
        self.logger.log("[Монитор] Тест остановлен.")
        super().closeEvent(event)


class MonitorTest:
    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self._window: Optional[MonitorWindow] = None

    @property
    def running(self) -> bool:
        return self._window is not None and self._window.isVisible()

    def start(self, stripe_px: int, blink_ms: int,
              on_stopped: Optional[Callable] = None) -> None:
        if self.running:
            return
        self._window = MonitorWindow(stripe_px, blink_ms, self.logger)

        def _cleanup() -> None:
            self._window = None
            if on_stopped:
                on_stopped()

        self._window.stopped.connect(_cleanup)

    def stop(self) -> None:
        if self._window:
            self._window.close()


# ── Модуль 2: Клавиатура ──────────────────────────────────────────────────────

class KeyboardWorker(QThread):
    def __init__(self, interval_ms: int, logger: Logger) -> None:
        super().__init__()
        self.interval_ms = interval_ms
        self.logger = logger
        self._stop = threading.Event()

    def run(self) -> None:
        freq = round(1000 / self.interval_ms, 1)
        self.logger.log(
            f"[Клавиатура] Тест запущен. Клавиша: Scroll Lock, "
            f"интервал: {self.interval_ms} мс, F_T ≈ {freq} Гц."
        )
        try:
            from pynput.keyboard import Key, Controller
            kbd = Controller()
            while not self._stop.is_set():
                kbd.press(Key.scroll_lock)
                kbd.release(Key.scroll_lock)
                self._stop.wait(self.interval_ms / 1000.0)
        except Exception as e:
            self.logger.log(f"[Клавиатура] Ошибка: {e}")

    def request_stop(self) -> None:
        self._stop.set()
        self.wait(2000)
        self.logger.log("[Клавиатура] Тест остановлен.")


class KeyboardTest:
    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self._worker: Optional[KeyboardWorker] = None
        self._deps_ok = self._check_deps()

    def _check_deps(self) -> bool:
        try:
            import pynput  # noqa: F401
            return True
        except ImportError:
            self.logger.log(
                "[Клавиатура] ВНИМАНИЕ: pynput не найден. "
                "Установите: pip install pynput"
            )
            return False

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start(self, interval_ms: int) -> None:
        if not self._deps_ok:
            self.logger.log(
                "[Клавиатура] Запуск невозможен: установите pynput."
            )
            return
        if self.running:
            return
        self._worker = KeyboardWorker(interval_ms, self.logger)
        self._worker.start()

    def stop(self) -> None:
        if self._worker:
            self._worker.request_stop()
            self._worker = None


# ── Модуль 3: Принтер ─────────────────────────────────────────────────────────

class PrinterWorker(QThread):
    PATTERN = bytes([0xFF, 0x00] * 64)

    def __init__(self, port: str, interval_ms: int, logger: Logger) -> None:
        super().__init__()
        self.port = port
        self.interval_ms = interval_ms
        self.logger = logger
        self._stop = threading.Event()

    def run(self) -> None:
        self.logger.log(
            f"[Принтер] Тест запущен. Порт: {self.port}, "
            f"интервал: {self.interval_ms} мс, паттерн: 0xFF/0x00×64."
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
            hp = win32print.OpenPrinter(self.port)
            win32print.StartDocPrinter(hp, 1, ("ПЭМИН-тест", None, "RAW"))
            win32print.StartPagePrinter(hp)
            count = 0
            while not self._stop.is_set():
                win32print.WritePrinter(hp, self.PATTERN)
                count += 1
                self._stop.wait(self.interval_ms / 1000.0)
            win32print.EndPagePrinter(hp)
            win32print.EndDocPrinter(hp)
            win32print.ClosePrinter(hp)
            self.logger.log(f"[Принтер] Отправлено посылок: {count}.")
        except ImportError:
            self.logger.log(
                "[Принтер] win32print не установлен. pip install pywin32"
            )
        except Exception as e:
            self.logger.log(f"[Принтер] Ошибка: {e}")

    def _loop_linux(self) -> None:
        try:
            count = 0
            with open(self.port, "wb") as f:
                while not self._stop.is_set():
                    f.write(self.PATTERN)
                    f.flush()
                    count += 1
                    self._stop.wait(self.interval_ms / 1000.0)
            self.logger.log(f"[Принтер] Отправлено посылок: {count}.")
        except PermissionError:
            self.logger.log(
                f"[Принтер] Нет доступа к {self.port}. "
                "Попробуйте: sudo adduser $USER lp"
            )
        except Exception as e:
            self.logger.log(f"[Принтер] Ошибка: {e}")

    def _loop_macos(self) -> None:
        try:
            count = 0
            while not self._stop.is_set():
                result = subprocess.run(
                    ["lp", "-d", self.port, "-o", "raw", "-"],
                    input=self.PATTERN, capture_output=True,
                )
                if result.returncode != 0:
                    self.logger.log(
                        "[Принтер] Ошибка lp: "
                        + result.stderr.decode(errors="replace").strip()
                    )
                    break
                count += 1
                self._stop.wait(self.interval_ms / 1000.0)
            self.logger.log(f"[Принтер] Отправлено посылок: {count}.")
        except FileNotFoundError:
            self.logger.log(
                "[Принтер] Команда lp не найдена (CUPS не установлен)."
            )
        except Exception as e:
            self.logger.log(f"[Принтер] Ошибка: {e}")

    def request_stop(self) -> None:
        self._stop.set()
        self.wait(3000)
        self.logger.log("[Принтер] Тест остановлен.")


class PrinterTest:
    PORTS_LINUX = [
        "/dev/usb/lp0", "/dev/lp0", "/dev/usb/lp1",
        "/dev/usb/lp2", "/dev/parport0",
    ]

    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self._worker: Optional[PrinterWorker] = None

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
            self.logger.log(
                "[Принтер] Порт не указан и не найден автоматически."
            )
            return
        self._worker = PrinterWorker(port, interval_ms, self.logger)
        self._worker.start()

    def stop(self) -> None:
        if self._worker:
            self._worker.request_stop()
            self._worker = None


# ── Виджет статуса ────────────────────────────────────────────────────────────

class StatusIndicator(QWidget):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._dot = QLabel()
        self._dot.setFixedSize(12, 12)
        self._lbl = QLabel(text)
        self._lbl.setStyleSheet("color:#555; font-size:12px;")
        self._active = False
        self._refresh_dot()

        layout.addWidget(self._dot)
        layout.addWidget(self._lbl)
        layout.addStretch()

    def _refresh_dot(self) -> None:
        color = "#4caf50" if self._active else "#9e9e9e"
        self._dot.setStyleSheet(
            f"background:{color}; border-radius:6px; border:1px solid #aaa;"
        )

    def set_active(self, active: bool, label: str = "") -> None:
        self._active = active
        if label:
            self._lbl.setText(label)
        self._refresh_dot()


# ── Главное окно ──────────────────────────────────────────────────────────────

class App(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"ПЭМИН — Тестовый режим СВТ  [{OS}]")
        self.setMinimumSize(760, 660)
        self.resize(820, 700)

        self.logger = Logger()

        self._build_ui()
        self.logger.message.connect(self._append_log)

        self.monitor_test = MonitorTest(self.logger)
        self.keyboard_test = KeyboardTest(self.logger)
        self.printer_test = PrinterTest(self.logger)

        self.logger.log(
            f"[Система] ОС: {OS} | Python {sys.version.split()[0]} | "
            "Инструмент готов к работе."
        )

    # ── Build UI ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(14, 12, 14, 12)

        title = QLabel("ПЭМИН — Запуск тестового режима")
        title.setFont(QFont("Arial", 14, _BOLD))
        title.setAlignment(_AC)
        root.addWidget(title)

        sub = QLabel(
            "Создание детерминированного периодического сигнала "
            "на интерфейсах СВТ"
        )
        sub.setAlignment(_AC)
        sub.setStyleSheet("color:#666; font-size:11px;")
        root.addWidget(sub)

        tabs = QTabWidget()
        tabs.addTab(self._tab_monitor(),  "  Монитор  ")
        tabs.addTab(self._tab_keyboard(), "  Клавиатура  ")
        tabs.addTab(self._tab_printer(),  "  Принтер  ")
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

        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setFont(QFont("Courier", 9))
        self.log_widget.setStyleSheet(
            "background:#1e1e1e; color:#cccccc; border:none;"
        )
        self.log_widget.setMinimumHeight(130)
        log_layout.addWidget(self.log_widget)

        save_btn = QPushButton("Сохранить журнал…")
        save_btn.setStyleSheet("padding:4px 10px;")
        save_btn.clicked.connect(self._save_log)
        log_layout.addWidget(save_btn, alignment=_AR)

        root.addWidget(log_box)

    def _slider_row(self, layout: QVBoxLayout, label: str,
                    lo: int, hi: int, default: int,
                    suffix: str = "") -> QSlider:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(210)
        slider = QSlider(_H)
        slider.setRange(lo, hi)
        slider.setValue(default)
        slider.setMinimumWidth(260)
        val_lbl = QLabel(f"{default}{suffix}")
        val_lbl.setFixedWidth(70)
        slider.valueChanged.connect(lambda v: val_lbl.setText(f"{v}{suffix}"))
        row.addWidget(lbl)
        row.addWidget(slider)
        row.addWidget(val_lbl)
        layout.addLayout(row)
        return slider

    @staticmethod
    def _green_btn(text: str, slot: Callable) -> QPushButton:
        btn = QPushButton(text)
        btn.setStyleSheet(
            "background:#2e7d32; color:white; "
            "padding:8px 14px; border-radius:4px;"
        )
        btn.clicked.connect(slot)
        return btn

    @staticmethod
    def _red_btn(text: str, slot: Callable) -> QPushButton:
        btn = QPushButton(text)
        btn.setStyleSheet(
            "background:#c62828; color:white; "
            "padding:8px 14px; border-radius:4px;"
        )
        btn.clicked.connect(slot)
        return btn

    @staticmethod
    def _warn(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#e65100; font-size:10px;")
        return lbl

    @staticmethod
    def _hint(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("color:#888; font-size:10px;")
        return lbl

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _tab_monitor(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)
        lay.setContentsMargins(14, 14, 14, 14)

        desc = QLabel(
            "Паттерн: чередование чёрных/белых <b>горизонтальных</b> полос "
            "заданной высоты.<br>"
            "Создаёт меандр на видеоинтерфейсе — максимальная частота "
            "переключений пикселей."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#444; padding:4px;")
        lay.addWidget(desc)

        self.mon_stripe = self._slider_row(
            lay, "Высота полосы (px):", 1, 256, 32, " px"
        )
        self.mon_blink = self._slider_row(
            lay, "Интервал инверсии (мс):", 50, 5000, 500, " мс"
        )

        lay.addSpacing(4)
        self.mon_status = StatusIndicator("Тест монитора не запущен")
        lay.addWidget(self.mon_status)

        btn_row = QHBoxLayout()
        self.mon_start_btn = self._green_btn(
            "▶  Запустить тест монитора", self._mon_start
        )
        self.mon_stop_btn = self._red_btn("■  Остановить", self._mon_stop)
        self.mon_stop_btn.setEnabled(False)
        btn_row.addWidget(self.mon_start_btn)
        btn_row.addWidget(self.mon_stop_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        lay.addWidget(self._hint("Горячая клавиша для остановки: ESC (в окне теста)"))
        lay.addStretch()
        return w

    def _tab_keyboard(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
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

        self.kbd_interval = self._slider_row(
            lay, "Интервал (мс):", 10, 500, 50, " мс"
        )

        self.kbd_freq_lbl = QLabel("F_T ≈ 20.0 Гц")
        self.kbd_freq_lbl.setStyleSheet("color:#1565c0; font-weight:bold;")
        self.kbd_interval.valueChanged.connect(self._update_kbd_freq)
        lay.addWidget(self.kbd_freq_lbl)

        lay.addWidget(self._warn("Требуется pynput  (pip install pynput)"))

        lay.addSpacing(4)
        self.kbd_status = StatusIndicator("Тест клавиатуры не запущен")
        lay.addWidget(self.kbd_status)

        btn_row = QHBoxLayout()
        self.kbd_start_btn = self._green_btn(
            "▶  Запустить тест клавиатуры", self._kbd_start
        )
        self.kbd_stop_btn = self._red_btn("■  Остановить", self._kbd_stop)
        self.kbd_stop_btn.setEnabled(False)
        btn_row.addWidget(self.kbd_start_btn)
        btn_row.addWidget(self.kbd_stop_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addStretch()
        return w

    def _tab_printer(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
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
        self.prt_port_edit = QLineEdit(PrinterTest.auto_port())
        self.prt_port_edit.setMaximumWidth(220)
        port_row.addWidget(self.prt_port_edit)
        port_row.addStretch()
        lay.addLayout(port_row)

        self.prt_interval = self._slider_row(
            lay, "Интервал (мс):", 50, 2000, 200, " мс"
        )

        if OS == "Windows":
            warn_text = "Windows: требуется pywin32  (pip install pywin32)"
        elif OS == "Darwin":
            warn_text = "macOS: используется lp (CUPS). Имя принтера определяется автоматически."
        else:
            warn_text = "Linux: нужен доступ к порту  (sudo adduser $USER lp)"
        lay.addWidget(self._warn(warn_text))

        lay.addSpacing(4)
        self.prt_status = StatusIndicator("Тест принтера не запущен")
        lay.addWidget(self.prt_status)

        btn_row = QHBoxLayout()
        self.prt_start_btn = self._green_btn(
            "▶  Запустить тест принтера", self._prt_start
        )
        self.prt_stop_btn = self._red_btn("■  Остановить", self._prt_stop)
        self.prt_stop_btn.setEnabled(False)
        btn_row.addWidget(self.prt_start_btn)
        btn_row.addWidget(self.prt_stop_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)
        lay.addStretch()
        return w

    # ── Log ───────────────────────────────────────────────────────────────────

    def _append_log(self, msg: str) -> None:
        self.log_widget.append(msg)
        self.log_widget.moveCursor(_END)

    def _save_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить журнал", "pemin_log.txt",
            "Text files (*.txt);;All files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.log_widget.toPlainText())

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _update_kbd_freq(self, ms: int) -> None:
        if ms > 0:
            self.kbd_freq_lbl.setText(f"F_T ≈ {round(1000 / ms, 1)} Гц")

    def _mon_start(self) -> None:
        self.monitor_test.start(
            self.mon_stripe.value(),
            self.mon_blink.value(),
            on_stopped=self._on_mon_stopped,
        )
        self.mon_start_btn.setEnabled(False)
        self.mon_stop_btn.setEnabled(True)
        self.mon_status.set_active(True, "Тест монитора запущен")

    def _mon_stop(self) -> None:
        self.monitor_test.stop()
        self._on_mon_stopped()

    def _on_mon_stopped(self) -> None:
        self.mon_start_btn.setEnabled(True)
        self.mon_stop_btn.setEnabled(False)
        self.mon_status.set_active(False, "Тест монитора не запущен")

    def _kbd_start(self) -> None:
        self.keyboard_test.start(self.kbd_interval.value())
        if not self.keyboard_test.running:
            return
        self.kbd_start_btn.setEnabled(False)
        self.kbd_stop_btn.setEnabled(True)
        self.kbd_status.set_active(True, "Тест клавиатуры запущен")

    def _kbd_stop(self) -> None:
        self.keyboard_test.stop()
        self.kbd_start_btn.setEnabled(True)
        self.kbd_stop_btn.setEnabled(False)
        self.kbd_status.set_active(False, "Тест клавиатуры не запущен")

    def _prt_start(self) -> None:
        port = self.prt_port_edit.text().strip()
        self.printer_test.start(port, self.prt_interval.value())
        if not self.printer_test.running:
            return
        self.prt_start_btn.setEnabled(False)
        self.prt_stop_btn.setEnabled(True)
        self.prt_status.set_active(True, "Тест принтера запущен")

    def _prt_stop(self) -> None:
        self.printer_test.stop()
        self.prt_start_btn.setEnabled(True)
        self.prt_stop_btn.setEnabled(False)
        self.prt_status.set_active(False, "Тест принтера не запущен")

    def _stop_all(self) -> None:
        if self.monitor_test.running:
            self._mon_stop()
        if self.keyboard_test.running:
            self._kbd_stop()
        if self.printer_test.running:
            self._prt_stop()

    def closeEvent(self, event) -> None:
        self._stop_all()
        event.accept()


# ─────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = App()
    window.show()
    sys.exit(app.exec())
