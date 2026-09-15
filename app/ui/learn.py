from typing import Any

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.data.repository import FlashcardRepository
from app.services.learning import LearningSession
from app.ui.edit_flashcard import EditFlashcardDialog
from app.ui.message_utils import show_info
from app.ui.image_viewer import ImagePreviewStrip, ImageViewer


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
        self.image_viewer: ImageViewer | None = None

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

        self.image_scroll = ImagePreviewStrip()
        self.image_scroll.image_clicked.connect(self.open_images)
        root.addWidget(self.image_scroll)
        self.open_images_button = QPushButton("Open images")
        self.open_images_button.clicked.connect(lambda: self.open_images(0))
        self.open_images_button.setEnabled(False)
        root.addWidget(self.open_images_button)

        answer_actions = QHBoxLayout()
        self.show_answer_button = QPushButton("Show answer")
        self.correct_button = QPushButton("Correct")
        self.wrong_button = QPushButton("Wrong")
        self.edit_button = QPushButton("Edit card")
        answer_actions.addWidget(self.show_answer_button)
        answer_actions.addWidget(self.correct_button)
        answer_actions.addWidget(self.wrong_button)
        answer_actions.addWidget(self.edit_button)
        root.addLayout(answer_actions)

        self.setLayout(root)

        self.start_button.clicked.connect(self.start_learning)
        self.refresh_button.clicked.connect(self.populate_filters)
        self.show_answer_button.clicked.connect(self.show_answer)
        self.edit_button.clicked.connect(self.edit_current_card)
        self.correct_button.clicked.connect(lambda: self.answer_current(True))
        self.wrong_button.clicked.connect(lambda: self.answer_current(False))
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)

        self.populate_filters()
        self._clear_card_display()

    @staticmethod
    def _populate_combo(combo: QComboBox, values: list) -> None:
        selected = combo.currentData()
        with QSignalBlocker(combo):
            combo.clear()
            combo.addItem("Any", None)
            for value in values:
                combo.addItem(str(value), value)
            combo.setCurrentIndex(max(0, combo.findData(selected)))

    def populate_filters(self) -> None:
        self._populate_combo(self.category_combo, self.repository.get_categories())
        self._populate_subcategories(self.category_combo.currentData())
        self._populate_combo(self.tier_combo, list(range(1, 6)))

    def _on_category_changed(self, _index: int) -> None:
        self._populate_subcategories(self.category_combo.currentData())

    def _populate_subcategories(self, category: str | None) -> None:
        self._populate_combo(self.subcategory_combo, self.repository.get_subcategories(category))

    def start_learning(self) -> None:
        self.load_threshold_settings()

        self.active_category = self.category_combo.currentData()
        self.active_subcategory = self.subcategory_combo.currentData()
        self.active_tier = self.tier_combo.currentData()
        self._clear_card_display()

        cards = self.repository.get_filtered_flashcards(
            category=self.active_category,
            subcategory=self.active_subcategory,
            tier=self.active_tier,
        )

        if not cards:
            show_info(self, "No cards", "No flashcards match your filters.")
            self.session = None
            self.current_card = None
            self.loop_count = 0
            self.progress_label.setText("No flashcards match your filters")
            self._clear_card_display()
            return

        self.session = LearningSession(cards)
        self.loop_count = 1
        self._show_next_card()

    def answer_current(self, is_correct: bool) -> None:
        if self.current_card is None or not self.answer_visible:
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

    def edit_current_card(self) -> None:
        if self.current_card is None:
            return
        dialog = EditFlashcardDialog(self.repository, self.current_card, self)
        if dialog.exec() == QDialog.Accepted:
            self.question_text.setPlainText(self.current_card.get("question_text", ""))
            if self.answer_visible:
                self.answer_text.setPlainText(self.current_card.get("answer_text", ""))
        dialog.deleteLater()

    def show_answer(self) -> None:
        if self.current_card is None:
            return
        self.answer_visible = True
        self.answer_text.setPlainText(self.current_card.get("answer_text", ""))
        self.image_scroll.set_images(self.current_card.get("images", []))
        self.open_images_button.setEnabled(bool(self.current_card.get("images")))
        self.correct_button.setEnabled(True)
        self.wrong_button.setEnabled(True)
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

        self._clear_card_display()
        self.current_card = next_card
        self.progress_label.setText(
            f"Loop {self.loop_count} • Card {self.session.current_position} / {self.session.total}"
        )
        self.card_meta_label.setText(
            f"Category: {next_card['category']} | Subcategory: {next_card['subcategory']} | Tier: {next_card['tier']}"
        )
        self.question_text.setPlainText(next_card.get("question_text", ""))
        self.answer_text.setPlainText("Answer is hidden. Click 'Show answer'.")
        self.show_answer_button.setEnabled(True)
        self.edit_button.setEnabled(True)

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

    def open_images(self, index: int = 0) -> None:
        if self.current_card is None or not self.answer_visible:
            return
        paths = self.current_card.get("images", [])
        if not paths:
            return
        if self.image_viewer is None:
            self.image_viewer = ImageViewer(paths, index, self)
        else:
            self.image_viewer.set_index(index)
        self.image_viewer.show()
        self.image_viewer.raise_()
        self.image_viewer.activateWindow()

    def _close_image_viewer(self) -> None:
        if self.image_viewer is not None:
            self.image_viewer.close()
            self.image_viewer.deleteLater()
            self.image_viewer = None

    def hideEvent(self, event) -> None:
        self._clear_card_display()
        self.session = None
        self.current_card = None
        self.loop_count = 0
        self.progress_label.setText("No active session")
        super().hideEvent(event)

    def _clear_card_display(self) -> None:
        self._close_image_viewer()
        self.answer_visible = False
        self.card_meta_label.clear()
        self.question_text.clear()
        self.answer_text.setPlainText("Answer is hidden. Click 'Show answer'.")
        self.image_scroll.clear_images()
        self.show_answer_button.setEnabled(False)
        self.edit_button.setEnabled(False)
        self.open_images_button.setEnabled(False)
        self.correct_button.setEnabled(False)
        self.wrong_button.setEnabled(False)
