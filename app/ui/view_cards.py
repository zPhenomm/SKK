from __future__ import annotations

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class ViewCardsView(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout()
        layout.addWidget(QLabel("View flashcards (placeholder for later)"))

        self.back_button = QPushButton("Back to menu")
        layout.addWidget(self.back_button)
        layout.addStretch()

        self.setLayout(layout)
