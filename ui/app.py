from __future__ import annotations

import sys

from compat import (
    OS, AlignCenter, AlignRight, CursorEnd, FontBold,
    QFileDialog, QFont, QGroupBox, QLabel, QLineEdit, QMainWindow,
    QPushButton, QTabWidget, QTextEdit, QVBoxLayout, QHBoxLayout,
    QWidget, QObject, QThread, pyqtSignal,
)
from core.logger import Logger
from core.remote_client import RemoteClient
from ui.tabs.keyboard_tab import KeyboardTab
from ui.tabs.monitor_tab import MonitorTab
from ui.tabs.printer_tab import PrinterTab
from ui.theme import DARK, LIGHT


class _ConnectWorker(QThread):
    success = pyqtSignal()
    failure = pyqtSignal(str)

    def __init__(self, remote, host: str, port: int) -> None:
        super().__init__()
        self._remote = remote
        self._host = host
        self._port = port

    def run(self) -> None:
        try:
            self._remote.connect(self._host, self._port)
            self.success.emit()
        except OSError as e:
            self.failure.emit(str(e))


class _CommandRelay(QObject):
    """Ретранслятор команд из фонового потока в главный (через Qt-сигнал)."""
    command_received = pyqtSignal(str)
    disconnected = pyqtSignal()
    ready = pyqtSignal()
    mode_changed = pyqtSignal(str)


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
        self._relay.ready.connect(self._on_remote_ready)
        self._relay.mode_changed.connect(self._on_mode_changed)
        self._remote.on_command = self._relay.command_received.emit
        self._remote.on_disconnected = self._relay.disconnected.emit
        self._remote.on_ready = self._relay.ready.emit
        self._remote.on_mode_changed = self._relay.mode_changed.emit

        self._theme = DARK
        self._build_ui()
        self.set_theme(DARK)
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

        header_row = QHBoxLayout()
        self._theme_btn = QPushButton("☀")
        self._theme_btn.setFixedSize(32, 32)
        self._theme_btn.setToolTip("Переключить тему")
        self._theme_btn.clicked.connect(self._toggle_theme)
        header_row.addWidget(self._theme_btn)

        title = QLabel("ПЭМИН — Запуск тестового режима")
        title.setFont(QFont("Arial", 14, FontBold))
        title.setAlignment(AlignCenter)
        header_row.addWidget(title, stretch=1)
        header_row.addSpacing(32)
        root.addLayout(header_row)

        sub = QLabel(
            "Создание детерминированного периодического сигнала "
            "на интерфейсах СВТ"
        )
        sub.setAlignment(AlignCenter)
        self._sub_lbl = sub
        root.addWidget(sub)

        # Панель подключения к детектору
        conn_box = QGroupBox("Подключение к детектору ПЭМИН")
        conn_outer = QVBoxLayout(conn_box)
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
        self._conn_btn.clicked.connect(self._toggle_connection)
        conn_row.addWidget(self._conn_btn)

        self._conn_status = QLabel("● Не подключено")
        self._conn_status.setStyleSheet("color:#999; font-size:11px;")
        conn_row.addWidget(self._conn_status)

        self._remote_mode_lbl = QLabel("")
        conn_row.addWidget(self._remote_mode_lbl)
        conn_row.addStretch()
        conn_outer.addLayout(conn_row)

        hint = QLabel(
            "При подключении тесты запускаются/останавливаются автоматически "
            "по команде детектора. Активна вкладка, открытая в момент команды."
        )
        hint.setWordWrap(True)
        self._hint_lbl = hint
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

        log_box = QGroupBox("Журнал")
        log_layout = QVBoxLayout(log_box)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFont(QFont("Courier", 9))
        self._log.setMinimumHeight(110)
        log_layout.addWidget(self._log)

        save_btn = QPushButton("Сохранить журнал…")
        save_btn.setStyleSheet(
            "QPushButton { padding:4px 10px; border-radius:4px;"
            " background:#455a64; color:white; border:none; }"
            "QPushButton:hover { background:#546e7a; }"
            "QPushButton:pressed { background:#263238; padding:5px 9px 3px 11px; }"
        )
        save_btn.clicked.connect(self._save_log)
        log_layout.addWidget(save_btn, alignment=AlignRight)

        root.addWidget(log_box)

    def _toggle_theme(self) -> None:
        self.set_theme(LIGHT if self._theme is DARK else DARK)

    def _build_qss(self, t: dict) -> str:
        return f"""
        QMainWindow, QWidget {{
            background-color: {t['bg_window']};
            color: {t['text']};
        }}
        QGroupBox {{
            font-weight: bold;
            border: 1px solid {t['border']};
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 6px;
            color: {t['text']};
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
        }}
        QLabel {{ color: {t['text']}; background: transparent; }}
        QLineEdit {{
            background: {t['bg_input']};
            color: {t['text']};
            border: 1px solid {t['border_input']};
            border-radius: 3px;
            padding: 2px 4px;
        }}
        QTextEdit {{
            background: {t['bg_log']};
            color: {t['text_dim']};
            border: none;
        }}
        QTabWidget::pane {{
            border: 1px solid {t['border']};
            background: {t['bg_widget']};
        }}
        QTabBar::tab {{
            background: {t['bg_window']};
            color: {t['text_muted']};
            border: 1px solid {t['border']};
            border-bottom: none;
            padding: 6px 14px;
            border-radius: 3px 3px 0 0;
        }}
        QTabBar::tab:selected {{
            background: {t['tab_sel']};
            color: {t['text']};
        }}
        QTabBar::tab:hover {{ background: {t['bg_widget']}; }}
        QSlider::groove:horizontal {{
            height: 4px;
            background: {t['border']};
            border-radius: 2px;
        }}
        QSlider::handle:horizontal {{
            background: {t['conn_btn_bg']};
            width: 14px; height: 14px;
            margin: -5px 0;
            border-radius: 7px;
        }}
        QScrollBar:vertical {{
            background: {t['bg_widget']};
            width: 10px;
        }}
        QScrollBar::handle:vertical {{
            background: {t['border']};
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QMenuBar {{
            background: {t['bg_widget']};
            color: {t['text']};
        }}
        QMenuBar::item:selected {{ background: {t['border']}; }}
        QMenu {{
            background: {t['bg_widget']};
            color: {t['text']};
            border: 1px solid {t['border']};
        }}
        QMenu::item:selected {{ background: {t['border']}; }}
    """

    def set_theme(self, t: dict) -> None:
        self._theme = t
        self._theme_btn.setText("☀" if t is DARK else "🌙")
        self.setStyleSheet(self._build_qss(t))
        self._sub_lbl.setStyleSheet(f"color:{t['text_muted']}; font-size:11px;")
        self._hint_lbl.setStyleSheet(f"color:{t['text_muted']}; font-size:10px;")
        self._log.setStyleSheet(f"background:{t['bg_log']}; color:{t['text_dim']}; border:none;")
        self._set_conn_ui(connected=self._remote.connected)
        self._mon_tab.set_theme(t)
        self._kbd_tab.set_theme(t)
        self._prt_tab.set_theme(t)

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
            self._host_edit.setEnabled(False)
            self._port_edit.setEnabled(False)
            self._connect_host = host
            self._connect_port = port
            self._worker = _ConnectWorker(self._remote, host, port)
            self._worker.success.connect(self._on_connect_success)
            self._worker.failure.connect(self._on_connect_failure)
            self._worker.start()

    def _on_connect_success(self) -> None:
        self._ever_ready = False

    def _on_remote_ready(self) -> None:
        self._ever_ready = True
        self._set_conn_ui(connected=True)
        self._logger.log(f"[Сеть] Подключено к {self._connect_host}:{self._connect_port}")

    def _on_connect_failure(self, error: str) -> None:
        self._set_conn_ui(connected=False)
        self._conn_status.setText(f"● Ошибка: {error}")
        self._conn_status.setStyleSheet("color:#c62828; font-size:11px;")
        self._logger.log(f"[Сеть] Ошибка подключения: {error}")

    def _set_conn_ui(self, *, connected: bool) -> None:
        t = self._theme
        self._conn_btn.setEnabled(True)
        if connected:
            self._conn_btn.setText("Отключиться")
            self._conn_btn.setStyleSheet(
                "QPushButton { background:#c62828; color:white; padding:5px 14px;"
                " border-radius:4px; border:none; }"
                "QPushButton:hover { background:#e53935; }"
                "QPushButton:pressed { background:#7f0000; padding:6px 13px 4px 15px; }"
            )
            self._conn_status.setText("● Подключено")
            self._conn_status.setStyleSheet("color:#2e7d32; font-size:11px; font-weight:bold;")
            self._host_edit.setEnabled(False)
            self._port_edit.setEnabled(False)
        else:
            self._conn_btn.setText("Подключиться")
            self._conn_btn.setStyleSheet(
                f"QPushButton {{ background:{t['conn_btn_bg']}; color:white; padding:5px 14px;"
                f" border-radius:4px; border:none; }}"
                f"QPushButton:hover {{ background:{t['conn_btn_hover']}; }}"
                f"QPushButton:pressed {{ background:{t['conn_btn_bg']}; padding:6px 13px 4px 15px; }}"
                f"QPushButton:disabled {{ background:{t['conn_btn_dis']}; color:{t['conn_btn_dis_text']}; }}"
            )
            self._conn_status.setText("● Не подключено")
            self._conn_status.setStyleSheet("color:#999; font-size:11px;")
            self._remote_mode_lbl.setText("")
            self._host_edit.setEnabled(True)
            self._port_edit.setEnabled(True)

    def _on_mode_changed(self, mode: str) -> None:
        t = self._theme
        if mode in ("semi_auto", "auto"):
            self._remote_mode_lbl.setText("| Авто-управление активно")
            self._remote_mode_lbl.setStyleSheet(
                f"color:{t['remote_lbl_color']}; font-weight:bold; font-size:11px;"
            )
        else:
            self._remote_mode_lbl.setText("")

    # ── Обработка команд от детектора ─────────────────────────────────

    def _on_remote_command(self, cmd: str) -> None:
        if cmd == "test_start":
            self._remote_start()
        elif cmd == "test_stop":
            self._remote_stop()

    def _remote_start(self) -> None:
        """Запускает тест на активной вкладке и подтверждает серверу."""
        idx = self._tabs.currentIndex()
        tab_names = {0: "монитора", 1: "клавиатуры", 2: "принтера"}
        self._logger.log(f"[Сеть] Команда: запуск теста {tab_names.get(idx, '?')}")
        if idx == 0:
            self._mon_tab._start()
        elif idx == 1:
            self._kbd_tab._start()
        elif idx == 2:
            self._prt_tab._start()
        self._remote.send_ack(active=True)
        self._logger.log("[Сеть] ACK отправлен серверу (тест запущен).")

    def _remote_stop(self) -> None:
        """Останавливает все тесты и подтверждает серверу."""
        self._stop_all()
        self._remote.send_ack(active=False)
        self._logger.log("[Сеть] ACK отправлен серверу (тест остановлен).")

    def _on_remote_disconnected(self) -> None:
        if not getattr(self, "_ever_ready", False):
            self._set_conn_ui(connected=False)
            self._conn_status.setText("● Нет ответа от сервера")
            self._conn_status.setStyleSheet("color:#c62828; font-size:11px;")
            self._logger.log("[Сеть] Нет ответа от сервера ПЭМИН.")
        else:
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
