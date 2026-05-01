from __future__ import annotations

from typing import Callable

from compat import (
    QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, Horizontal,
)


def slider_row(layout: QVBoxLayout, label: str, lo: int, hi: int,
               default: int, suffix: str = "") -> QSlider:
    row = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setFixedWidth(210)
    slider = QSlider(Horizontal)
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


def green_btn(text: str, slot: Callable) -> QPushButton:
    btn = QPushButton(text)
    btn.setStyleSheet(
        "QPushButton {"
        "  background:#2e7d32; color:white;"
        "  padding:8px 14px; border-radius:4px;"
        "  border:none;"
        "}"
        "QPushButton:hover {"
        "  background:#43a047;"
        "}"
        "QPushButton:pressed {"
        "  background:#1b5e20;"
        "  padding:9px 13px 7px 15px;"
        "}"
        "QPushButton:disabled {"
        "  background:#a5d6a7; color:#eee;"
        "}"
    )
    btn.clicked.connect(slot)
    return btn


def red_btn(text: str, slot: Callable) -> QPushButton:
    btn = QPushButton(text)
    btn.setStyleSheet(
        "QPushButton {"
        "  background:#c62828; color:white;"
        "  padding:8px 14px; border-radius:4px;"
        "  border:none;"
        "}"
        "QPushButton:hover {"
        "  background:#e53935;"
        "}"
        "QPushButton:pressed {"
        "  background:#7f0000;"
        "  padding:9px 13px 7px 15px;"
        "}"
        "QPushButton:disabled {"
        "  background:#ef9a9a; color:#eee;"
        "}"
    )
    btn.clicked.connect(slot)
    return btn


def warn_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color:#e65100; font-size:10px;")
    return lbl


def hint_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color:#888; font-size:10px;")
    return lbl
