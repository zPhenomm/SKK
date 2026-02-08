from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from app.data.db import initialize_database
from app.data.repository import FlashcardRepository
from app.ui.create_flashcard import CreateFlashcardView
from app.ui.learn import LearnView
from app.ui.main_menu import MainMenuView
from app.ui.settings import SettingsView
from app.ui.view_cards import ViewCardsView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Flashcard Study App")
        self.resize(900, 700)

        self.repository = FlashcardRepository()

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.main_menu_view = MainMenuView()
        self.create_view = CreateFlashcardView(self.repository)
        self.learn_view = LearnView(self.repository)
        self.settings_view = SettingsView()
        self.view_cards_view = ViewCardsView()

        self.stack.addWidget(self.main_menu_view)
        self.stack.addWidget(self.create_view)
        self.stack.addWidget(self.learn_view)
        self.stack.addWidget(self.settings_view)
        self.stack.addWidget(self.view_cards_view)

        self._wire_events()
        self._show_main_menu()

    def _wire_events(self) -> None:
        self.main_menu_view.create_flashcard_button.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.create_view)
        )
        self.main_menu_view.start_learning_button.clicked.connect(self._open_learning)
        self.main_menu_view.settings_button.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.settings_view)
        )
        self.main_menu_view.view_flashcards_button.clicked.connect(
            lambda: self.stack.setCurrentWidget(self.view_cards_view)
        )

        self.create_view.back_button.clicked.connect(self._show_main_menu)
        self.learn_view.back_button.clicked.connect(self._show_main_menu)
        self.settings_view.back_button.clicked.connect(self._show_main_menu)
        self.view_cards_view.back_button.clicked.connect(self._show_main_menu)

    def _open_learning(self) -> None:
        self.learn_view.populate_filters()
        self.stack.setCurrentWidget(self.learn_view)

    def _show_main_menu(self) -> None:
        self.stack.setCurrentWidget(self.main_menu_view)


def main() -> None:
    initialize_database()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
