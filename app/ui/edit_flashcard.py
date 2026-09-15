import sqlite3
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.data.repository import FlashcardRepository


class EditFlashcardDialog(QDialog):
    """Correct a card's text without changing its learning history or images."""

    def __init__(
        self, repository: FlashcardRepository, card: dict[str, Any], parent: QWidget
    ) -> None:
        super().__init__(parent)
        self.repository = repository
        self.card = card
        self.setWindowTitle("Edit card")
        self.resize(600, 450)

        self.question_input = QTextEdit()
        self.question_input.setAcceptRichText(False)
        self.question_input.setPlainText(card.get("question_text", ""))
        self.answer_input = QTextEdit()
        self.answer_input.setAcceptRichText(False)
        self.answer_input.setPlainText(card.get("answer_text", ""))
        form = QFormLayout()
        form.addRow("Question:", self.question_input)
        form.addRow("Answer:", self.answer_input)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

    def accept(self) -> None:
        question = self.question_input.toPlainText().strip()
        answer = self.answer_input.toPlainText().strip()
        if not question or not answer:
            QMessageBox.warning(self, "Invalid input", "Question and answer are required.")
            return

        try:
            self.repository.update_flashcard(
                flashcard_id=int(self.card["id"]),
                category=self.card["category"],
                subcategory=self.card["subcategory"],
                tier=int(self.card["tier"]),
                question_text=question,
                answer_text=answer,
            )
        except sqlite3.Error:
            QMessageBox.warning(
                self, "Save failed", "Could not save the card. Your edits are still here. Please try again."
            )
            return

        self.card.update(question_text=question, answer_text=answer)
        super().accept()
