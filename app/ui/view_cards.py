from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.data.repository import FlashcardRepository


class ViewCardsView(QWidget):
    def __init__(self, repository: FlashcardRepository) -> None:
        super().__init__()
        self.repository = repository

        self.current_category: str | None = None
        self.current_subcategory: str | None = None
        self.current_cards: list[dict] = []
        self.current_card_id: int | None = None

        layout = QVBoxLayout()

        stats_group = QGroupBox("Statistics & Scope Selection")
        stats_layout = QVBoxLayout()

        self.stats_tree = QTreeWidget()
        self.stats_tree.setHeaderLabels(["Scope", "Card count", "Tiers"])
        self.stats_tree.setColumnWidth(0, 300)
        stats_layout.addWidget(self.stats_tree)

        stats_actions = QHBoxLayout()
        self.open_scope_button = QPushButton("Open selected scope")
        self.reset_scope_tier_button = QPushButton("Reset selected scope to tier 1")
        self.delete_scope_button = QPushButton("Delete selected scope")
        self.refresh_stats_button = QPushButton("Refresh statistics")
        stats_actions.addWidget(self.open_scope_button)
        stats_actions.addWidget(self.reset_scope_tier_button)
        stats_actions.addWidget(self.delete_scope_button)
        stats_actions.addWidget(self.refresh_stats_button)
        stats_layout.addLayout(stats_actions)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        cards_group = QGroupBox("Cards in selected scope")
        cards_layout = QVBoxLayout()

        self.scope_label = QLabel("No scope selected")
        cards_layout.addWidget(self.scope_label)

        self.cards_table = QTableWidget(0, 5)
        self.cards_table.setHorizontalHeaderLabels(
            ["ID", "Tier", "Category", "Subcategory", "Question"]
        )
        self.cards_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.cards_table.setEditTriggers(QTableWidget.NoEditTriggers)
        cards_layout.addWidget(self.cards_table)

        cards_group.setLayout(cards_layout)
        layout.addWidget(cards_group)

        editor_group = QGroupBox("Edit selected card")
        editor_layout = QVBoxLayout()

        form = QFormLayout()
        self.edit_category_input = QLineEdit()
        self.edit_subcategory_input = QLineEdit()
        self.edit_tier_input = QSpinBox()
        self.edit_tier_input.setRange(1, 5)
        self.edit_question_input = QTextEdit()
        self.edit_question_input.setMinimumHeight(90)
        self.edit_answer_input = QTextEdit()
        self.edit_answer_input.setMinimumHeight(90)

        form.addRow("Category:", self.edit_category_input)
        form.addRow("Subcategory:", self.edit_subcategory_input)
        form.addRow("Tier:", self.edit_tier_input)
        form.addRow("Question:", self.edit_question_input)
        form.addRow("Answer:", self.edit_answer_input)
        editor_layout.addLayout(form)

        editor_actions = QHBoxLayout()
        self.save_card_button = QPushButton("Save card changes")
        self.delete_card_button = QPushButton("Delete selected card")
        editor_actions.addWidget(self.save_card_button)
        editor_actions.addWidget(self.delete_card_button)
        editor_layout.addLayout(editor_actions)

        editor_group.setLayout(editor_layout)
        layout.addWidget(editor_group)

        self.back_button = QPushButton("Back to menu")
        layout.addWidget(self.back_button)

        self.setLayout(layout)

        self.open_scope_button.clicked.connect(self.open_selected_scope)
        self.reset_scope_tier_button.clicked.connect(self.reset_selected_scope_tier)
        self.delete_scope_button.clicked.connect(self.delete_selected_scope)
        self.refresh_stats_button.clicked.connect(self.refresh_statistics)
        self.cards_table.itemSelectionChanged.connect(self._on_card_selection_changed)
        self.save_card_button.clicked.connect(self.save_selected_card)
        self.delete_card_button.clicked.connect(self.delete_selected_card)

        self.refresh_statistics()
        self._set_editor_enabled(False)

    def refresh_statistics(self) -> None:
        self.stats_tree.clear()
        stats = self.repository.get_category_stats()
        for category_info in stats:
            category_item = QTreeWidgetItem(
                [
                    category_info["category"],
                    str(category_info["card_count"]),
                    ", ".join(map(str, category_info["tiers"])),
                ]
            )
            category_item.setData(0, Qt.UserRole, ("category", category_info["category"], None))
            self.stats_tree.addTopLevelItem(category_item)

            for sub_info in category_info["subcategories"]:
                sub_item = QTreeWidgetItem(
                    [
                        f"↳ {sub_info['subcategory']}",
                        str(sub_info["card_count"]),
                        ", ".join(map(str, sub_info["tiers"])),
                    ]
                )
                sub_item.setData(
                    0,
                    Qt.UserRole,
                    ("subcategory", category_info["category"], sub_info["subcategory"]),
                )
                category_item.addChild(sub_item)

        self.stats_tree.expandAll()

    def open_selected_scope(self) -> None:
        item = self.stats_tree.currentItem()
        if item is None:
            QMessageBox.information(self, "No selection", "Please select a category or subcategory.")
            return

        data = item.data(0, Qt.UserRole)
        if not data:
            return

        _, category, subcategory = data
        self.current_category = category
        self.current_subcategory = subcategory
        self._load_cards_for_current_scope()

    def _load_cards_for_current_scope(self) -> None:
        self.current_cards = self.repository.get_cards_for_scope(
            category=self.current_category,
            subcategory=self.current_subcategory,
        )

        scope_text = f"Category: {self.current_category}"
        if self.current_subcategory:
            scope_text += f" | Subcategory: {self.current_subcategory}"
        scope_text += f" | Cards: {len(self.current_cards)}"
        self.scope_label.setText(scope_text)

        self.cards_table.setRowCount(len(self.current_cards))
        for row, card in enumerate(self.current_cards):
            self.cards_table.setItem(row, 0, QTableWidgetItem(str(card["id"])))
            self.cards_table.setItem(row, 1, QTableWidgetItem(str(card["tier"])))
            self.cards_table.setItem(row, 2, QTableWidgetItem(card["category"]))
            self.cards_table.setItem(row, 3, QTableWidgetItem(card["subcategory"]))
            question_preview = (card["question_text"] or "").replace("\n", " ")[:80]
            self.cards_table.setItem(row, 4, QTableWidgetItem(question_preview))

        if self.current_cards:
            self.cards_table.selectRow(0)
        else:
            self.current_card_id = None
            self._clear_editor()
            self._set_editor_enabled(False)

    def _on_card_selection_changed(self) -> None:
        selected_rows = self.cards_table.selectionModel().selectedRows()
        if not selected_rows:
            self.current_card_id = None
            self._clear_editor()
            self._set_editor_enabled(False)
            return

        row = selected_rows[0].row()
        card = self.current_cards[row]
        self.current_card_id = int(card["id"])
        self.edit_category_input.setText(card["category"])
        self.edit_subcategory_input.setText(card["subcategory"])
        self.edit_tier_input.setValue(int(card["tier"]))
        self.edit_question_input.setPlainText(card["question_text"])
        self.edit_answer_input.setPlainText(card["answer_text"])
        self._set_editor_enabled(True)

    def save_selected_card(self) -> None:
        if self.current_card_id is None:
            return

        category = self.edit_category_input.text().strip()
        subcategory = self.edit_subcategory_input.text().strip()
        tier = int(self.edit_tier_input.value())
        question = self.edit_question_input.toPlainText().strip()
        answer = self.edit_answer_input.toPlainText().strip()

        if not category or not subcategory:
            QMessageBox.warning(self, "Invalid input", "Category and subcategory are required.")
            return
        if not question or not answer:
            QMessageBox.warning(self, "Invalid input", "Question and answer are required.")
            return

        self.repository.update_flashcard(
            flashcard_id=self.current_card_id,
            category=category,
            subcategory=subcategory,
            tier=tier,
            question_text=question,
            answer_text=answer,
        )
        QMessageBox.information(self, "Saved", "Card updated.")
        self.refresh_statistics()
        self._load_cards_for_current_scope()

    def delete_selected_card(self) -> None:
        if self.current_card_id is None:
            return

        reply = QMessageBox.question(
            self,
            "Delete card",
            "Delete selected card? This cannot be undone.",
        )
        if reply != QMessageBox.Yes:
            return

        self.repository.delete_flashcard(self.current_card_id)
        self.current_card_id = None
        self.refresh_statistics()
        self._load_cards_for_current_scope()

    def delete_selected_scope(self) -> None:
        item = self.stats_tree.currentItem()
        if item is None:
            QMessageBox.information(self, "No selection", "Please select a category or subcategory.")
            return
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        scope_type, category, subcategory = data
        scope_name = f"{category} / {subcategory}" if subcategory else category

        reply = QMessageBox.question(
            self,
            "Delete scope",
            f"Delete all cards in '{scope_name}'?",
        )
        if reply != QMessageBox.Yes:
            return

        deleted = self.repository.delete_scope(category=category, subcategory=subcategory)
        QMessageBox.information(self, "Deleted", f"Deleted {deleted} cards from selected {scope_type}.")
        self.current_category = None
        self.current_subcategory = None
        self.current_cards = []
        self.current_card_id = None
        self.scope_label.setText("No scope selected")
        self.cards_table.setRowCount(0)
        self._clear_editor()
        self._set_editor_enabled(False)
        self.refresh_statistics()

    def reset_selected_scope_tier(self) -> None:
        item = self.stats_tree.currentItem()
        if item is None:
            QMessageBox.information(self, "No selection", "Please select a category or subcategory.")
            return
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        scope_type, category, subcategory = data
        updated = self.repository.reset_scope_tier_to_one(category=category, subcategory=subcategory)
        QMessageBox.information(self, "Updated", f"Reset tier to 1 for {updated} cards in selected {scope_type}.")
        self.refresh_statistics()
        if self.current_category == category and self.current_subcategory == subcategory:
            self._load_cards_for_current_scope()

    def _clear_editor(self) -> None:
        self.edit_category_input.clear()
        self.edit_subcategory_input.clear()
        self.edit_tier_input.setValue(1)
        self.edit_question_input.clear()
        self.edit_answer_input.clear()

    def _set_editor_enabled(self, enabled: bool) -> None:
        self.edit_category_input.setEnabled(enabled)
        self.edit_subcategory_input.setEnabled(enabled)
        self.edit_tier_input.setEnabled(enabled)
        self.edit_question_input.setEnabled(enabled)
        self.edit_answer_input.setEnabled(enabled)
        self.save_card_button.setEnabled(enabled)
        self.delete_card_button.setEnabled(enabled)


