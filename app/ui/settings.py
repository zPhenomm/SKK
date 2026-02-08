from __future__ import annotations

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.data.repository import FlashcardRepository
from app.ui.message_utils import show_info


class SettingsView(QWidget):
    def __init__(self, repository: FlashcardRepository) -> None:
        super().__init__()
        self.repository = repository

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Learning Settings"))

        form = QFormLayout()
        self.tier_up_threshold_input = QSpinBox()
        self.tier_up_threshold_input.setRange(1, 20)

        self.tier_down_threshold_input = QSpinBox()
        self.tier_down_threshold_input.setRange(1, 20)

        form.addRow("Correct answers to move up a tier:", self.tier_up_threshold_input)
        form.addRow("Wrong answers to move down a tier:", self.tier_down_threshold_input)
        layout.addLayout(form)

        self.save_button = QPushButton("Save settings")
        layout.addWidget(self.save_button)

        self.back_button = QPushButton("Back to menu")
        layout.addWidget(self.back_button)
        layout.addStretch()

        self.setLayout(layout)

        self.save_button.clicked.connect(self.save_settings)
        self.load_settings()

    def load_settings(self) -> None:
        up = self.repository.get_setting_int("tier_up_threshold", 3)
        down = self.repository.get_setting_int("tier_down_threshold", 1)
        self.tier_up_threshold_input.setValue(max(1, up))
        self.tier_down_threshold_input.setValue(max(1, down))

    def save_settings(self) -> None:
        up = int(self.tier_up_threshold_input.value())
        down = int(self.tier_down_threshold_input.value())
        self.repository.set_setting_int("tier_up_threshold", up)
        self.repository.set_setting_int("tier_down_threshold", down)
        show_info(self, "Saved", "Learning thresholds saved.")
