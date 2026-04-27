"""
ПЭМИН — Запуск тестового режима СВТ
=====================================
Поддерживаемые ОС: Windows, Linux
Зависимости: python 3.8+, PyQt6 (pip install PyQt6)
Опционально: pywin32 (pip install pywin32) — для принтера на Windows
"""

import os
import platform
import subprocess
import sys
import threading
import time
from datetime import datetime

from PyQt6.QtCore import QObject, QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap, QTextCursor
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSlider,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

OS = platform.system()


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
    Паттерн: чередование чёрных/белых вертикальных полос —
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
        self._cache: list[QPixmap | None] = [None, None]

        self.setWindowTitle("ПЭМИН — Тест монитора")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )

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
        if event.key() == Qt.Key.Key_Escape:
            self.close()

    def closeEvent(self, event) -> None:
        self._timer.stop()
        self.stopped.emit()
        self.logger.log("[Монитор] Тест остановлен.")
        super().closeEvent(event)


class MonitorTest:
    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self._window: MonitorWindow | None = None

    @property
    def running(self) -> bool:
        return self._window is not None and self._window.isVisible()

    def start(self, stripe_px: int, blink_ms: int,
              on_stopped=None) -> None:
        if self.running:
            return
        self._window = MonitorWindow(stripe_px, blink_ms, self.logger)

        def _cleanup():
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
        if OS == "Windows":
            self._loop_windows()
        else:
            self._loop_linux()

    def _loop_windows(self) -> None:
        import ctypes
        VK_SCROLL, KEYEVENTF_KEYUP = 0x91, 0x0002
        while not self._stop.is_set():
            ctypes.windll.user32.keybd_event(VK_SCROLL, 0, 0, 0)
            time.sleep(0.005)
            ctypes.windll.user32.keybd_event(VK_SCROLL, 0, KEYEVENTF_KEYUP, 0)
            self._stop.wait(self.interval_ms / 1000.0)

    def _loop_linux(self) -> None:
        try:
            while not self._stop.is_set():
                subprocess.run(
                    ["xdotool", "key", "Scroll_Lock"], capture_output=True
                )
                self._stop.wait(self.interval_ms / 1000.0)
        except FileNotFoundError:
            self.logger.log(
                "[Клавиатура] xdotool не найден. "
                "Установите: sudo apt install xdotool"
            )

    def request_stop(self) -> None:
        self._stop.set()
        self.wait(2000)
        self.logger.log("[Клавиатура] Тест остановлен.")


class KeyboardTest:
    def __init__(self, logger: Logger) -> None:
        self.logger = logger
        self._worker: KeyboardWorker | None = None
        self._deps_ok = self._check_deps()

    def _check_deps(self) -> bool:
        if OS != "Linux":
            return True
        for tool in ("xdotool", "evemu-event"):
            if subprocess.run(["which", tool], capture_output=True).returncode == 0:
                return True
        self.logger.log(
            "[Клавиатура] ВНИМАНИЕ: xdotool не найден. "
            "Установите: sudo apt install xdotool"
        )
        return False

    @property
    def running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def start(self, interval_ms: int) -> None:
        if not self._deps_ok:
            self.logger.log(
                "[Клавиатура] Запуск невозможен: xdotool не установлен."
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
        self._worker: PrinterWorker | None = None

    @staticmethod
    def auto_port() -> str:
        if OS == "Windows":
            return "LPT1"
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
        title.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        sub = QLabel(
            "Создание детерминированного периодического сигнала "
            "на интерфейсах СВТ"
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        log_layout.addWidget(
            save_btn, alignment=Qt.AlignmentFlag.AlignRight
        )

        root.addWidget(log_box)

    def _slider_row(self, layout: QVBoxLayout, label: str,
                    lo: int, hi: int, default: int,
                    suffix: str = "") -> QSlider:
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(210)
        slider = QSlider(Qt.Orientation.Horizontal)
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
    def _green_btn(text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setStyleSheet(
            "background:#2e7d32; color:white; "
            "padding:8px 14px; border-radius:4px;"
        )
        btn.clicked.connect(slot)
        return btn

    @staticmethod
    def _red_btn(text: str, slot) -> QPushButton:
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

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _tab_monitor(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)
        lay.setContentsMargins(14, 14, 14, 14)

        desc = QLabel(
            "Паттерн: чередование чёрных/белых <b>вертикальных</b> полос "
            "заданной ширины.<br>"
            "Создаёт меандр на видеоинтерфейсе — максимальная частота "
            "переключений пикселей."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#444; padding:4px;")
        lay.addWidget(desc)

        self.mon_stripe = self._slider_row(
            lay, "Ширина полосы (px):", 1, 256, 32, " px"
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

        lay.addWidget(
            self._warn("Горячая клавиша для остановки: ESC (в окне теста)")
        )
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
            "Создаёт детерминированный импульсный сигнал на шине USB/PS2."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color:#444; padding:4px;")
        lay.addWidget(desc)

        self.kbd_interval = self._slider_row(
            lay, "Интервал (мс):", 10, 500, 50, " мс"
        )

        self.kbd_freq_lbl = QLabel("F_T ≈ 20.0 Гц")
        self.kbd_freq_lbl.setStyleSheet(
            "color:#1565c0; font-weight:bold;"
        )
        self.kbd_interval.valueChanged.connect(self._update_kbd_freq)
        lay.addWidget(self.kbd_freq_lbl)

        if OS == "Linux":
            lay.addWidget(
                self._warn(
                    "Linux: требуется xdotool  (sudo apt install xdotool)"
                )
            )

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
        port_row.addWidget(QLabel("Порт:"))
        self.prt_port_edit = QLineEdit(PrinterTest.auto_port())
        self.prt_port_edit.setMaximumWidth(200)
        port_row.addWidget(self.prt_port_edit)
        port_row.addStretch()
        lay.addLayout(port_row)

        self.prt_interval = self._slider_row(
            lay, "Интервал (мс):", 50, 2000, 200, " мс"
        )

        warn_text = (
            "Windows: требуется pywin32  (pip install pywin32)"
            if OS == "Windows"
            else "Linux: нужен доступ к порту  (sudo adduser $USER lp)"
        )
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
        self.log_widget.moveCursor(QTextCursor.MoveOperation.End)

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
        if self.printer_test.running:
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
