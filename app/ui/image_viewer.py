from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.data.db import resolve_image_path


class ImagePreviewStrip(QScrollArea):
    image_clicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.row = QHBoxLayout(self.content)
        self.row.setContentsMargins(6, 6, 6, 6)
        self.setWidget(self.content)
        self._previews: list[tuple[QPushButton, QPixmap]] = []
        self.clear_images()

    def clear_images(self, message: str = "Answer images are hidden. Click 'Show answer'.") -> None:
        self._previews.clear()
        while self.row.count():
            widget = self.row.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.row.addWidget(QLabel(message))
        self.horizontalScrollBar().setValue(0)
        self._resize_previews()

    def set_images(self, paths: list[str]) -> None:
        self.clear_images("No images" if not paths else "")
        if paths:
            placeholder = self.row.takeAt(0).widget()
            placeholder.hide()
            placeholder.deleteLater()
        for index, path in enumerate(paths):
            pixmap = QPixmap(str(resolve_image_path(path)))
            button = QPushButton()
            button.setAccessibleName(f"Open image {index + 1}")
            button.setToolTip(f"Open image {index + 1} of {len(paths)}")
            button.clicked.connect(lambda _checked=False, i=index: self.image_clicked.emit(i))
            if pixmap.isNull():
                button.setText(f"Image {index + 1}\nMissing or unreadable")
            self.row.addWidget(button)
            self._previews.append((button, pixmap))
        self._resize_previews()

    def _resize_previews(self) -> None:
        height = max(30, self.viewport().height() - 12)
        for button, pixmap in self._previews:
            if pixmap.isNull():
                button.setFixedSize(180, height)
            else:
                scaled = pixmap.scaledToHeight(max(1, height - 8), Qt.SmoothTransformation)
                button.setIcon(QIcon(scaled))
                button.setIconSize(scaled.size())
                button.setFixedSize(scaled.width() + 8, height)
        width = (sum(button.width() for button, _ in self._previews)
                 + max(0, len(self._previews) - 1) * self.row.spacing() + 12)
        self.content.setFixedSize(max(self.viewport().width(), width), height + 12)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_previews"):
            self._resize_previews()


class ImageViewer(QDialog):
    """Non-modal viewer for an ordered set of answer attachments."""

    def __init__(self, image_paths: list[str], initial_index: int = 0,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Answer images")
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, True)
        self.image_paths = list(image_paths)
        self.index = max(0, min(initial_index, len(image_paths) - 1))
        self.pixmap = QPixmap()
        self.fit_mode = True
        self.scale = 1.0

        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.previous_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.counter = QLabel()
        self.fit_button = QPushButton("Fit")
        self.actual_size_button = QPushButton("100%")
        self.zoom_out_button = QPushButton("Zoom Out")
        self.zoom_in_button = QPushButton("Zoom In")
        self.zoom_label = QLabel()
        for widget in (self.previous_button, self.counter, self.next_button,
                       self.fit_button, self.actual_size_button, self.zoom_out_button,
                       self.zoom_in_button, self.zoom_label):
            controls.addWidget(widget)
        layout.addLayout(controls)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignCenter)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.scroll.setWidget(self.image_label)
        layout.addWidget(self.scroll)
        self.scroll.viewport().installEventFilter(self)

        self.previous_button.clicked.connect(lambda: self.navigate(-1))
        self.next_button.clicked.connect(lambda: self.navigate(1))
        self.fit_button.clicked.connect(self.fit)
        self.actual_size_button.clicked.connect(lambda: self.set_zoom(1.0))
        self.zoom_out_button.clicked.connect(lambda: self.set_zoom(self.scale - 0.25))
        self.zoom_in_button.clicked.connect(lambda: self.set_zoom(self.scale + 0.25))
        self._shortcuts = []
        for key, offset in ((Qt.Key_Left, -1), (Qt.Key_Right, 1)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda step=offset: self.navigate(step))
            self._shortcuts.append(shortcut)
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)

        available = self.screen().availableGeometry()
        self.resize(min(1200, int(available.width() * 0.9)),
                    min(900, int(available.height() * 0.9)))
        self._load_image()

    def navigate(self, offset: int) -> None:
        self.set_index(self.index + offset)

    def set_index(self, index: int) -> None:
        if 0 <= index < len(self.image_paths):
            self.index = index
            self._load_image()

    def _load_image(self) -> None:
        path = self.image_paths[self.index] if self.image_paths else None
        self.pixmap = QPixmap(str(resolve_image_path(path))) if path else QPixmap()
        self.counter.setText(f"{self.index + 1 if path else 0} / {len(self.image_paths)}")
        self.previous_button.setEnabled(self.index > 0)
        self.next_button.setEnabled(self.index < len(self.image_paths) - 1)
        for button in (self.fit_button, self.actual_size_button, self.zoom_in_button, self.zoom_out_button):
            button.setEnabled(not self.pixmap.isNull())
        self.fit()
        self.scroll.horizontalScrollBar().setValue(0)
        self.scroll.verticalScrollBar().setValue(0)

    def fit(self) -> None:
        self.fit_mode = True
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._render()

    def set_zoom(self, scale: float) -> None:
        if self.pixmap.isNull():
            return
        self.fit_mode = False
        self.scale = max(0.1, min(4.0, scale))
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._render()

    def _render(self) -> None:
        if self.pixmap.isNull():
            self.image_label.setText("Image missing or unreadable" if self.image_paths else "No images")
            self.image_label.resize(260, 80)
            self.zoom_label.clear()
            return
        if self.fit_mode:
            viewport = self.scroll.viewport().size()
            self.scale = min(max(1, viewport.width() - 2) / self.pixmap.width(),
                             max(1, viewport.height() - 2) / self.pixmap.height())
        size = QSize(max(1, round(self.pixmap.width() * self.scale)),
                     max(1, round(self.pixmap.height() * self.scale)))
        self.image_label.setPixmap(self.pixmap.scaled(size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.image_label.resize(size)
        self.zoom_label.setText(f"{self.scale:.0%}")

    def eventFilter(self, watched, event) -> bool:
        if watched is self.scroll.viewport() and event.type() == QEvent.Resize and self.fit_mode:
            self._render()
        return super().eventFilter(watched, event)
