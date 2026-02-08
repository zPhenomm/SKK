from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class MainMenuView(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout()
        layout.setSpacing(12)

        self.start_learning_button = QPushButton("Start learning")
        self.create_flashcard_button = QPushButton("Create flashcard")
        self.settings_button = QPushButton("Settings")
        self.view_flashcards_button = QPushButton("View flashcards")

        layout.addWidget(self.start_learning_button)
        layout.addWidget(self.create_flashcard_button)
        layout.addWidget(self.settings_button)
        layout.addWidget(self.view_flashcards_button)
        layout.addStretch()

        self.setLayout(layout)
