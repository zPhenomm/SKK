from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.data.repository import FlashcardRepository
from app.services.learning import LearningSession


class LearnView(QWidget):
    def __init__(self, repository: FlashcardRepository) -> None:
        super().__init__()
        self.repository = repository
        self.session: LearningSession | None = None
        self.current_card: dict[str, Any] | None = None

        root = QVBoxLayout()

        filters = QFormLayout()
        self.category_combo = QComboBox()
        self.subcategory_combo = QComboBox()
        self.tier_combo = QComboBox()

        filters.addRow("Category:", self.category_combo)
        filters.addRow("Subcategory:", self.subcategory_combo)
        filters.addRow("Tier:", self.tier_combo)
        root.addLayout(filters)

        top_actions = QHBoxLayout()
        self.start_button = QPushButton("Start learning")
        self.refresh_button = QPushButton("Refresh filters")
        self.back_button = QPushButton("Back to menu")
        top_actions.addWidget(self.start_button)
        top_actions.addWidget(self.refresh_button)
        top_actions.addWidget(self.back_button)
        root.addLayout(top_actions)

        self.progress_label = QLabel("No active session")
        root.addWidget(self.progress_label)

        self.card_meta_label = QLabel("")
        root.addWidget(self.card_meta_label)

        self.card_text = QTextEdit()
        self.card_text.setReadOnly(True)
        self.card_text.setPlaceholderText("Card text will appear here...")
        self.card_text.setMinimumHeight(140)
        root.addWidget(self.card_text)

        self.image_label = QLabel("")
        self.image_label.setMinimumHeight(220)
        self.image_label.setStyleSheet("border:1px solid #888; padding:6px;")
        root.addWidget(self.image_label)

        answer_actions = QHBoxLayout()
        self.correct_button = QPushButton("Correct")
        self.wrong_button = QPushButton("Wrong")
        answer_actions.addWidget(self.correct_button)
        answer_actions.addWidget(self.wrong_button)
        root.addLayout(answer_actions)

        self.setLayout(root)

        self.start_button.clicked.connect(self.start_learning)
        self.refresh_button.clicked.connect(self.populate_filters)
        self.correct_button.clicked.connect(lambda: self.answer_current(True))
        self.wrong_button.clicked.connect(lambda: self.answer_current(False))
        self.category_combo.currentTextChanged.connect(self._on_category_changed)

        self.populate_filters()

    def populate_filters(self) -> None:
        categories = self.repository.get_categories()
        self.category_combo.clear()
        self.category_combo.addItem("Any")
        self.category_combo.addItems(categories)

        self._populate_subcategories(None)

        self.tier_combo.clear()
        self.tier_combo.addItem("Any")
        for tier in range(1, 6):
            self.tier_combo.addItem(str(tier))

    def _on_category_changed(self, _text: str) -> None:
        selected = self.category_combo.currentText()
        self._populate_subcategories(None if selected == "Any" else selected)

    def _populate_subcategories(self, category: str | None) -> None:
        subcategories = self.repository.get_subcategories(category)
        self.subcategory_combo.clear()
        self.subcategory_combo.addItem("Any")
        self.subcategory_combo.addItems(subcategories)

    def start_learning(self) -> None:
        category = self.category_combo.currentText()
        subcategory = self.subcategory_combo.currentText()
        tier_text = self.tier_combo.currentText()

        cards = self.repository.get_filtered_flashcards(
            category=None if category == "Any" else category,
            subcategory=None if subcategory == "Any" else subcategory,
            tier=None if tier_text == "Any" else int(tier_text),
        )

        if not cards:
            QMessageBox.information(self, "No cards", "No flashcards match your filters.")
            self.session = None
            self.current_card = None
            self._clear_card_display()
            return

        self.session = LearningSession(cards)
        self._show_next_card()

    def answer_current(self, is_correct: bool) -> None:
        if self.current_card is None:
            return
        self.repository.update_after_answer(
            flashcard_id=int(self.current_card["id"]),
            is_correct=is_correct,
        )
        self._show_next_card()

    def _show_next_card(self) -> None:
        if self.session is None:
            return

        next_card = self.session.next_card()
        if next_card is None:
            QMessageBox.information(self, "Done", "Learning session completed.")
            self.current_card = None
            self.progress_label.setText("Session finished")
            self._clear_card_display()
            return

        self.current_card = next_card
        self.progress_label.setText(
            f"Card {self.session.current_position} / {self.session.total}"
        )
        self.card_meta_label.setText(
            f"Category: {next_card['category']} | Subcategory: {next_card['subcategory']} | Tier: {next_card['tier']}"
        )
        self.card_text.setPlainText(next_card.get("text_content", ""))
        self._display_first_image(next_card.get("images", []))

    def _display_first_image(self, image_paths: list[str]) -> None:
        if not image_paths:
            self.image_label.setText("No image")
            self.image_label.setPixmap(QPixmap())
            return

        first = Path(image_paths[0])
        if not first.exists():
            self.image_label.setText("Image not found")
            self.image_label.setPixmap(QPixmap())
            return

        pixmap = QPixmap(str(first))
        if pixmap.isNull():
            self.image_label.setText("Could not load image")
            self.image_label.setPixmap(QPixmap())
            return

        scaled = pixmap.scaled(
            self.image_label.size(),
            aspectMode=Qt.KeepAspectRatio,
            mode=Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.setText("")

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self.current_card:
            self._display_first_image(self.current_card.get("images", []))

    def _clear_card_display(self) -> None:
        self.card_meta_label.setText("")
        self.card_text.clear()
        self.image_label.setText("")
        self.image_label.setPixmap(QPixmap())
