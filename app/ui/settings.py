from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class SettingsView(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Settings (placeholder)"))

        self.back_button = QPushButton("Back to menu")
        layout.addWidget(self.back_button)
        layout.addStretch()

        self.setLayout(layout)
