from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget


def show_info(parent: QWidget, title: str, text: str) -> None:
    """Show an informational popup without the native info sound/beep."""
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.NoIcon)
    box.setStandardButtons(QMessageBox.Ok)
    box.exec()
