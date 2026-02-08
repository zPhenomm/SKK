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
        self.answer_visible = False
        self.tier_up_threshold = 3
        self.tier_down_threshold = 1
        self.active_category: str | None = None
        self.active_subcategory: str | None = None
        self.active_tier: int | None = None
        self.loop_count = 0

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

        self.question_text = QTextEdit()
        self.question_text.setReadOnly(True)
        self.question_text.setPlaceholderText("Question will appear here...")
        self.question_text.setMinimumHeight(120)
        root.addWidget(self.question_text)

        self.answer_text = QTextEdit()
        self.answer_text.setReadOnly(True)
        self.answer_text.setPlaceholderText("Answer is hidden. Click 'Show answer'.")
        self.answer_text.setMinimumHeight(120)
        root.addWidget(self.answer_text)

        self.image_label = QLabel("")
        self.image_label.setMinimumHeight(220)
        self.image_label.setStyleSheet("border:1px solid #888; padding:6px;")
        root.addWidget(self.image_label)

        answer_actions = QHBoxLayout()
        self.show_answer_button = QPushButton("Show answer")
        self.correct_button = QPushButton("Correct")
        self.wrong_button = QPushButton("Wrong")
        answer_actions.addWidget(self.show_answer_button)
        answer_actions.addWidget(self.correct_button)
        answer_actions.addWidget(self.wrong_button)
        root.addLayout(answer_actions)

        self.setLayout(root)

        self.start_button.clicked.connect(self.start_learning)
        self.refresh_button.clicked.connect(self.populate_filters)
        self.show_answer_button.clicked.connect(self.show_answer)
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
        self.load_threshold_settings()

        category = self.category_combo.currentText()
        subcategory = self.subcategory_combo.currentText()
        tier_text = self.tier_combo.currentText()

        self.active_category = None if category == "Any" else category
        self.active_subcategory = None if subcategory == "Any" else subcategory
        self.active_tier = None if tier_text == "Any" else int(tier_text)

        cards = self.repository.get_filtered_flashcards(
            category=self.active_category,
            subcategory=self.active_subcategory,
            tier=self.active_tier,
        )

        if not cards:
            QMessageBox.information(self, "No cards", "No flashcards match your filters.")
            self.session = None
            self.current_card = None
            self.loop_count = 0
            self._clear_card_display()
            return

        self.session = LearningSession(cards)
        self.loop_count = 1
        self._show_next_card()

    def answer_current(self, is_correct: bool) -> None:
        if self.current_card is None:
            return
        self.repository.update_after_answer(
            flashcard_id=int(self.current_card["id"]),
            is_correct=is_correct,
            streak_to_tier_up=self.tier_up_threshold,
            streak_to_tier_down=self.tier_down_threshold,
        )
        self._show_next_card()

    def load_threshold_settings(self) -> None:
        self.tier_up_threshold = max(
            1, self.repository.get_setting_int("tier_up_threshold", 3)
        )
        self.tier_down_threshold = max(
            1, self.repository.get_setting_int("tier_down_threshold", 1)
        )

    def show_answer(self) -> None:
        if self.current_card is None:
            return
        self.answer_visible = True
        self.answer_text.setPlainText(self.current_card.get("answer_text", ""))
        self._display_first_image(self.current_card.get("images", []))
        self.show_answer_button.setEnabled(False)

    def _show_next_card(self) -> None:
        if self.session is None:
            return

        next_card = self.session.next_card()
        if next_card is None:
            if not self._refresh_loop_session():
                self.current_card = None
                self.progress_label.setText("No matching cards left for current filters")
                self._clear_card_display()
                return
            next_card = self.session.next_card() if self.session else None
            if next_card is None:
                self.current_card = None
                self.progress_label.setText("No matching cards left for current filters")
                self._clear_card_display()
                return

        self.current_card = next_card
        self.answer_visible = False
        self.progress_label.setText(
            f"Loop {self.loop_count} • Card {self.session.current_position} / {self.session.total}"
        )
        self.card_meta_label.setText(
            f"Category: {next_card['category']} | Subcategory: {next_card['subcategory']} | Tier: {next_card['tier']}"
        )
        self.question_text.setPlainText(next_card.get("question_text", ""))
        self.answer_text.setPlainText("Answer is hidden. Click 'Show answer'.")
        self.image_label.setText("Answer images are hidden. Click 'Show answer'.")
        self.image_label.setPixmap(QPixmap())
        self.show_answer_button.setEnabled(True)

    def _refresh_loop_session(self) -> bool:
        cards = self.repository.get_filtered_flashcards(
            category=self.active_category,
            subcategory=self.active_subcategory,
            tier=self.active_tier,
        )
        if not cards:
            self.session = None
            return False
        self.session = LearningSession(cards)
        self.loop_count += 1
        return True

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
        if self.current_card and self.answer_visible:
            self._display_first_image(self.current_card.get("images", []))

    def _clear_card_display(self) -> None:
        self.card_meta_label.setText("")
        self.question_text.clear()
        self.answer_text.setPlainText("Answer is hidden. Click 'Show answer'.")
        self.image_label.setText("Answer images are hidden. Click 'Show answer'.")
        self.image_label.setPixmap(QPixmap())
        self.show_answer_button.setEnabled(False)
