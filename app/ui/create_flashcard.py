from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.data.db import IMAGES_DIR
from app.data.repository import FlashcardRepository


class ImageDropListWidget(QListWidget):
    file_paths_dropped = Signal(list)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DropOnly)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        urls = event.mimeData().urls()
        file_paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if file_paths:
            self.file_paths_dropped.emit(file_paths)
            event.acceptProposedAction()
        else:
            event.ignore()


class CreateFlashcardView(QWidget):
    def __init__(self, repository: FlashcardRepository) -> None:
        super().__init__()
        self.repository = repository
        self._image_items: list[dict] = []

        root = QVBoxLayout()

        form = QFormLayout()
        self.category_input = QLineEdit()
        self.subcategory_input = QLineEdit()
        self.tier_input = QSpinBox()
        self.tier_input.setRange(1, 5)
        self.tier_input.setValue(1)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Enter flashcard text...")
        self.text_input.setMinimumHeight(140)

        form.addRow("Category:", self.category_input)
        form.addRow("Subcategory:", self.subcategory_input)
        form.addRow("Tier:", self.tier_input)
        form.addRow("Text:", self.text_input)

        root.addLayout(form)

        root.addWidget(QLabel("Images (drag & drop files here, or use buttons below):"))
        self.image_list = ImageDropListWidget()
        self.image_list.file_paths_dropped.connect(self._add_image_paths)
        self.image_list.setMinimumHeight(140)
        root.addWidget(self.image_list)

        image_buttons = QHBoxLayout()
        self.add_images_button = QPushButton("Add image files")
        self.paste_image_button = QPushButton("Paste image from clipboard (Ctrl+V)")
        self.remove_selected_image_button = QPushButton("Remove selected image")
        image_buttons.addWidget(self.add_images_button)
        image_buttons.addWidget(self.paste_image_button)
        image_buttons.addWidget(self.remove_selected_image_button)
        root.addLayout(image_buttons)

        actions = QHBoxLayout()
        self.save_button = QPushButton("Save flashcard")
        self.back_button = QPushButton("Back to menu")
        actions.addWidget(self.save_button)
        actions.addWidget(self.back_button)
        root.addLayout(actions)

        self.setLayout(root)

        self.add_images_button.clicked.connect(self._pick_image_files)
        self.paste_image_button.clicked.connect(self._paste_image_from_clipboard)
        self.remove_selected_image_button.clicked.connect(self._remove_selected_image)
        self.save_button.clicked.connect(self._save_flashcard)

        self.setFocusPolicy(Qt.StrongFocus)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event.matches(QKeySequence.Paste):
            self._paste_image_from_clipboard()
            return
        super().keyPressEvent(event)

    def _pick_image_files(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose images",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp)",
        )
        if file_paths:
            self._add_image_paths(file_paths)

    def _add_image_paths(self, file_paths: list[str]) -> None:
        for path_str in file_paths:
            path = Path(path_str)
            if not path.exists() or not path.is_file():
                continue
            self._image_items.append({"kind": "path", "value": str(path)})
            self.image_list.addItem(QListWidgetItem(f"FILE: {path.name}"))

    def _paste_image_from_clipboard(self) -> None:
        from PySide6.QtWidgets import QApplication

        mime = QApplication.clipboard().mimeData()
        if mime and mime.hasImage():
            image = QApplication.clipboard().image()
            if isinstance(image, QImage) and not image.isNull():
                self._image_items.append({"kind": "qimage", "value": image})
                self.image_list.addItem(QListWidgetItem("PASTED IMAGE"))
                return

        QMessageBox.information(
            self,
            "No image in clipboard",
            "Clipboard does not currently contain an image.",
        )

    def _remove_selected_image(self) -> None:
        row = self.image_list.currentRow()
        if row < 0:
            return
        self.image_list.takeItem(row)
        del self._image_items[row]

    def _save_flashcard(self) -> None:
        category = self.category_input.text().strip()
        subcategory = self.subcategory_input.text().strip()
        tier = int(self.tier_input.value())
        text_content = self.text_input.toPlainText().strip()

        if not category or not subcategory:
            QMessageBox.warning(self, "Missing data", "Category and subcategory are required.")
            return
        if not text_content:
            QMessageBox.warning(self, "Missing data", "Text content is required.")
            return

        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        saved_paths: list[str] = []
        for item in self._image_items:
            unique_name = f"{uuid.uuid4().hex}"
            if item["kind"] == "path":
                src = Path(item["value"])
                suffix = src.suffix or ".png"
                dst = IMAGES_DIR / f"{unique_name}{suffix}"
                try:
                    dst.write_bytes(src.read_bytes())
                    saved_paths.append(dst.as_posix())
                except OSError:
                    continue
            elif item["kind"] == "qimage":
                dst = IMAGES_DIR / f"{unique_name}.png"
                image: QImage = item["value"]
                if image.save(str(dst), "PNG"):
                    saved_paths.append(dst.as_posix())

        self.repository.create_flashcard(
            category=category,
            subcategory=subcategory,
            tier=tier,
            text_content=text_content,
            image_paths=saved_paths,
        )

        QMessageBox.information(self, "Saved", "Flashcard saved successfully.")
        self._reset_form()

    def _reset_form(self) -> None:
        self.category_input.clear()
        self.subcategory_input.clear()
        self.tier_input.setValue(1)
        self.text_input.clear()
        self.image_list.clear()
        self._image_items.clear()
