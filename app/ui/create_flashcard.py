import shutil
import sqlite3
import uuid
from pathlib import Path

from PySide6.QtCore import QEvent, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QImage, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.data import db
from app.data.repository import FlashcardRepository
from app.ui.message_utils import show_info


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
        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.setInsertPolicy(QComboBox.NoInsert)

        self.subcategory_input = QComboBox()
        self.subcategory_input.setEditable(True)
        self.subcategory_input.setInsertPolicy(QComboBox.NoInsert)

        self.tier_input = QSpinBox()
        self.tier_input.setRange(1, 5)
        self.tier_input.setValue(1)

        self.question_input = QTextEdit()
        self.question_input.setPlaceholderText("Enter question text...")
        self.question_input.setMinimumHeight(100)

        self.answer_input = QTextEdit()
        self.answer_input.setPlaceholderText("Enter answer text...")
        self.answer_input.setMinimumHeight(140)

        form.addRow("Category:", self.category_input)
        form.addRow("Subcategory:", self.subcategory_input)
        form.addRow("Tier:", self.tier_input)
        form.addRow("Question:", self.question_input)
        form.addRow("Answer:", self.answer_input)

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
        self.category_input.currentTextChanged.connect(self._refresh_subcategory_options)

        self.setFocusPolicy(Qt.StrongFocus)
        for widget in (self, self.question_input, self.answer_input, self.image_list,
                       self.category_input.lineEdit(), self.subcategory_input.lineEdit()):
            widget.installEventFilter(self)
        self.refresh_category_options()

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.KeyPress and event.matches(QKeySequence.Paste):
            mime = QApplication.clipboard().mimeData()
            if mime and mime.hasImage():
                self._paste_image_from_clipboard()
                return True
        return super().eventFilter(watched, event)

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
        invalid: list[str] = []
        for path_str in file_paths:
            path = Path(path_str).resolve()
            if not path.is_file() or QImage(str(path)).isNull():
                invalid.append(path.name)
                continue
            self._image_items.append({"kind": "path", "value": str(path)})
            self.image_list.addItem(QListWidgetItem(f"FILE: {path.name}"))
        if invalid:
            QMessageBox.warning(self, "Invalid images", "Could not read these images:\n" + "\n".join(invalid))

    def _paste_image_from_clipboard(self) -> None:
        mime = QApplication.clipboard().mimeData()
        if mime and mime.hasImage():
            image = QApplication.clipboard().image()
            if isinstance(image, QImage) and not image.isNull():
                self._image_items.append({"kind": "qimage", "value": image})
                self.image_list.addItem(QListWidgetItem("PASTED IMAGE"))
                return

        show_info(
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
        category = self.category_input.currentText().strip()
        subcategory = self.subcategory_input.currentText().strip()
        tier = int(self.tier_input.value())
        question_text = self.question_input.toPlainText().strip()
        answer_text = self.answer_input.toPlainText().strip()

        if not category or not subcategory:
            QMessageBox.warning(self, "Missing data", "Category and subcategory are required.")
            return
        if not question_text:
            QMessageBox.warning(self, "Missing data", "Question text is required.")
            return
        if not answer_text:
            QMessageBox.warning(self, "Missing data", "Answer text is required.")
            return

        created_paths: list[Path] = []
        saved_paths: list[str] = []
        try:
            db.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
            for item in self._image_items:
                unique_name = uuid.uuid4().hex
                suffix = Path(item["value"]).suffix if item["kind"] == "path" else ".png"
                dst = db.IMAGES_DIR / f"{unique_name}{suffix or '.png'}"
                # Include partial copies in cleanup if an operation fails midway.
                created_paths.append(dst)
                if item["kind"] == "path":
                    shutil.copyfile(item["value"], dst)
                    if QImage(str(dst)).isNull():
                        raise OSError(f"Image is no longer readable: {Path(item['value']).name}")
                elif not item["value"].save(str(dst), "PNG"):
                    raise OSError("Could not save a pasted image.")
                saved_paths.append(dst.relative_to(db.PROJECT_ROOT).as_posix())

            self.repository.create_flashcard(
                category=category,
                subcategory=subcategory,
                tier=tier,
                question_text=question_text,
                answer_text=answer_text,
                image_paths=saved_paths,
            )
        except (OSError, sqlite3.Error) as error:
            cleanup_errors = []
            for path in created_paths:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    cleanup_errors.append(str(path))
            message = f"Flashcard was not saved. Your entries have been kept.\n\n{error}"
            if cleanup_errors:
                message += "\n\nCould not remove temporary image files:\n" + "\n".join(cleanup_errors)
            QMessageBox.warning(self, "Save failed", message)
            return

        show_info(self, "Saved", "Flashcard saved successfully.")
        self._reset_form()
        self.refresh_category_options()

    def _reset_form(self) -> None:
        # Keep the classification fields for creating more cards in the same group.
        self.question_input.clear()
        self.answer_input.clear()
        self.image_list.clear()
        self._image_items.clear()

    def refresh_category_options(self) -> None:
        current_category = self.category_input.currentText()
        categories = self.repository.get_categories()
        with QSignalBlocker(self.category_input):
            self.category_input.clear()
            self.category_input.addItems(categories)
            self.category_input.setCurrentText(current_category)

        self._refresh_subcategory_options()

    def _refresh_subcategory_options(self) -> None:
        selected_category = self.category_input.currentText().strip()
        current_subcategory = self.subcategory_input.currentText()
        subcategories = self.repository.get_subcategories(selected_category or None)
        with QSignalBlocker(self.subcategory_input):
            self.subcategory_input.clear()
            self.subcategory_input.addItems(subcategories)
            self.subcategory_input.setCurrentText(current_subcategory)
