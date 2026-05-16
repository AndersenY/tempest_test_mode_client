from __future__ import annotations

from compat import QHBoxLayout, QLabel, QWidget
from ui.theme import DARK


class StatusIndicator(QWidget):
    def __init__(self, text: str, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._dot = QLabel()
        self._dot.setFixedSize(12, 12)
        self._lbl = QLabel(text)
        self._active = False
        self._theme = DARK
        self._refresh_dot()
        self._lbl.setStyleSheet(f"color:{self._theme['text_muted']}; font-size:12px;")

        layout.addWidget(self._dot)
        layout.addWidget(self._lbl)
        layout.addStretch()

    def _refresh_dot(self) -> None:
        color = "#4caf50" if self._active else "#9e9e9e"
        self._dot.setStyleSheet(
            f"background:{color}; border-radius:6px; border:1px solid {self._theme['dot_border']};"
        )

    def set_active(self, active: bool, label: str = "") -> None:
        self._active = active
        if label:
            self._lbl.setText(label)
        self._refresh_dot()

    def set_theme(self, t: dict) -> None:
        self._theme = t
        self._lbl.setStyleSheet(f"color:{t['text_muted']}; font-size:12px;")
        self._refresh_dot()
