from __future__ import annotations

import sys

from compat import (
    OS, AlignCenter, AlignRight, CursorEnd, FontBold,
    QFileDialog, QFont, QGroupBox, QLabel, QLineEdit, QMainWindow,
    QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QHBoxLayout,
    QWidget, QObject, pyqtSignal,
)
from core.logger import Logger
from core.remote_client import RemoteClient
from ui.tabs.keyboard_tab import KeyboardTab
from ui.tabs.monitor_tab import MonitorTab
from ui.tabs.printer_tab import PrinterTab


class _CommandRelay(QObject):
    """Ретранслятор команд из фонового потока в главный (через Qt-сигнал)."""
    command_received = pyqtSignal(str)
    disconnected = pyqtSignal()


class App(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"ПЭМИН — Тестовый режим СВТ  [{OS}]")
        self.setMinimumSize(760, 720)
        self.resize(820, 760)

        self._logger = Logger()
        self._remote = RemoteClient()
        self._relay = _CommandRelay()
        self._relay.command_received.connect(self._on_remote_command)
        self._relay.disconnected.connect(self._on_remote_disconnected)
        self._remote.on_command = self._relay.command_received.emit
        self._remote.on_disconnected = self._relay.disconnected.emit

        self._build_ui()
        self._logger.message.connect(self._append_log)

        self._logger.log(
            f"[Система] ОС: {OS} | Python {sys.version.split()[0]} | "
            "Инструмент готов к работе."
        )

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(14, 12, 14, 12)

        title = QLabel("ПЭМИН — Запуск тестового режима")
        title.setFont(QFont("Arial", 14, FontBold))
        title.setAlignment(AlignCenter)
        root.addWidget(title)

        sub = QLabel(
            "Создание детерминированного периодического сигнала "
            "на интерфейсах СВТ"
        )
        sub.setAlignment(AlignCenter)
        sub.setStyleSheet("color:#666; font-size:11px;")
        root.addWidget(sub)

        # Панель подключения к детектору
        conn_box = QGroupBox("Подключение к детектору ПЭМИН")
        conn_box.setStyleSheet(
            "QGroupBox { font-weight:bold; border:1px solid #bbb; border-radius:4px;"
            " margin-top:8px; padding-top:6px; }"
            " QGroupBox::title { subcontrol-origin:margin; left:8px; padding:0 4px; }"
        )
        conn_outer = QVBoxLayout(conn_box)   # корневой layout группы
        conn_outer.setSpacing(4)
        conn_outer.setContentsMargins(10, 4, 10, 8)

        conn_row = QHBoxLayout()
        conn_row.setSpacing(8)

        conn_row.addWidget(QLabel("Адрес сервера:"))
        self._host_edit = QLineEdit()
        self._host_edit.setPlaceholderText("192.168.1.X")
        self._host_edit.setMaximumWidth(160)
        conn_row.addWidget(self._host_edit)

        conn_row.addWidget(QLabel("Порт:"))
        self._port_edit = QLineEdit("62000")
        self._port_edit.setMaximumWidth(65)
        conn_row.addWidget(self._port_edit)

        self._conn_btn = QPushButton("Подключиться")
        self._conn_btn.setStyleSheet(
            "background:#1976D2; color:white; padding:5px 14px; border-radius:4px;"
        )
        self._conn_btn.clicked.connect(self._toggle_connection)
        conn_row.addWidget(self._conn_btn)

        self._conn_status = QLabel("● Не подключено")
        self._conn_status.setStyleSheet("color:#999; font-size:11px;")
        conn_row.addWidget(self._conn_status)

        self._remote_mode_lbl = QLabel("")
        self._remote_mode_lbl.setStyleSheet(
            "color:#1565C0; font-weight:bold; font-size:11px;"
        )
        conn_row.addWidget(self._remote_mode_lbl)
        conn_row.addStretch()
        conn_outer.addLayout(conn_row)

        hint = QLabel(
            "При подключении тесты запускаются/останавливаются автоматически "
            "по команде детектора. Активна вкладка, открытая в момент команды."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#777; font-size:10px;")
        conn_outer.addWidget(hint)

        root.addWidget(conn_box)

        # Вкладки — каждая управляет своим тестовым модулем
        self._mon_tab = MonitorTab(self._logger)
        self._kbd_tab = KeyboardTab(self._logger)
        self._prt_tab = PrinterTab(self._logger)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._mon_tab, "  Монитор  ")
        self._tabs.addTab(self._kbd_tab, "  Клавиатура  ")
        self._tabs.addTab(self._prt_tab, "  Принтер  ")
        root.addWidget(self._tabs)

        stop_all_btn = QPushButton("■  Остановить все тесты")
        stop_all_btn.setStyleSheet(
            "background:#b71c1c; color:white; padding:7px; "
            "font-size:13px; border-radius:4px;"
        )
        stop_all_btn.clicked.connect(self._stop_all)
        root.addWidget(stop_all_btn)

        log_box = QGroupBox("Журнал")
        log_layout = QVBoxLayout(log_box)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Courier", 9))
        self._log.setStyleSheet("background:#1e1e1e; color:#cccccc; border:none;")
        self._log.setMinimumHeight(110)
        log_layout.addWidget(self._log)

        save_btn = QPushButton("Сохранить журнал…")
        save_btn.setStyleSheet("padding:4px 10px;")
        save_btn.clicked.connect(self._save_log)
        log_layout.addWidget(save_btn, alignment=AlignRight)

        root.addWidget(log_box)

    # ── Подключение / отключение ───────────────────────────────────────

    def _toggle_connection(self) -> None:
        if self._remote.connected:
            self._remote.disconnect()
            self._set_conn_ui(connected=False)
            self._logger.log("[Сеть] Отключено от сервера.")
        else:
            host = self._host_edit.text().strip()
            if not host:
                self._conn_status.setText("● Введите адрес сервера")
                self._conn_status.setStyleSheet("color:#c62828; font-size:11px;")
                return
            try:
                port = int(self._port_edit.text().strip())
            except ValueError:
                port = 62000
            self._conn_status.setText("● Подключение…")
            self._conn_status.setStyleSheet("color:#F57C00; font-size:11px;")
            self._conn_btn.setEnabled(False)
            try:
                self._remote.connect(host, port)
                self._set_conn_ui(connected=True)
                self._logger.log(f"[Сеть] Подключено к {host}:{port}")
            except OSError as e:
                self._conn_btn.setEnabled(True)
                self._conn_status.setText(f"● Ошибка: {e}")
                self._conn_status.setStyleSheet("color:#c62828; font-size:11px;")
                self._logger.log(f"[Сеть] Ошибка подключения: {e}")

    def _set_conn_ui(self, *, connected: bool) -> None:
        self._conn_btn.setEnabled(True)
        if connected:
            self._conn_btn.setText("Отключиться")
            self._conn_btn.setStyleSheet(
                "background:#c62828; color:white; padding:5px 14px; border-radius:4px;"
            )
            self._conn_status.setText("● Подключено")
            self._conn_status.setStyleSheet("color:#2e7d32; font-size:11px; font-weight:bold;")
            self._remote_mode_lbl.setText("| Авто-управление активно")
            self._host_edit.setEnabled(False)
            self._port_edit.setEnabled(False)
        else:
            self._conn_btn.setText("Подключиться")
            self._conn_btn.setStyleSheet(
                "background:#1976D2; color:white; padding:5px 14px; border-radius:4px;"
            )
            self._conn_status.setText("● Не подключено")
            self._conn_status.setStyleSheet("color:#999; font-size:11px;")
            self._remote_mode_lbl.setText("")
            self._host_edit.setEnabled(True)
            self._port_edit.setEnabled(True)

    # ── Обработка команд от детектора ─────────────────────────────────

    def _on_remote_command(self, cmd: str) -> None:
        if cmd == "test_start":
            self._remote_start()
        elif cmd == "test_stop":
            self._stop_all()

    def _remote_start(self) -> None:
        """Запускает тест на активной вкладке."""
        idx = self._tabs.currentIndex()
        tab_names = {0: "монитора", 1: "клавиатуры", 2: "принтера"}
        self._logger.log(f"[Сеть] Команда: запуск теста {tab_names.get(idx, '?')}")
        if idx == 0:
            self._mon_tab._start()
        elif idx == 1:
            self._kbd_tab._start()
        elif idx == 2:
            self._prt_tab._start()

    def _on_remote_disconnected(self) -> None:
        self._set_conn_ui(connected=False)
        self._logger.log("[Сеть] Соединение с сервером потеряно.")

    # ── Общее управление ──────────────────────────────────────────────

    def _append_log(self, msg: str) -> None:
        self._log.append(msg)
        self._log.moveCursor(CursorEnd)

    def _save_log(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить журнал", "pemin_log.txt",
            "Text files (*.txt);;All files (*)"
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._log.toPlainText())

    def _stop_all(self) -> None:
        self._mon_tab.stop()
        self._kbd_tab.stop()
        self._prt_tab.stop()

    def closeEvent(self, event) -> None:
        self._remote.disconnect()
        self._stop_all()
        event.accept()
