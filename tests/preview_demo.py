"""Run with `python -m tests.preview_demo [--smoke]` from the project folder.

Uses temporary cards and images only. --smoke exercises Qt interactions and
writes screenshots to build/ui-check before closing its windows.
"""

import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.data import db
from app.main import MainWindow


def main():
    smoke = "--smoke" in sys.argv
    project_root = db.PROJECT_ROOT
    app = QApplication([])
    with tempfile.TemporaryDirectory(prefix="skk-preview-") as temp:
        db.PROJECT_ROOT = Path(temp)
        db.DATA_DIR = db.PROJECT_ROOT / "data"
        db.IMAGES_DIR = db.DATA_DIR / "images"
        db.DB_PATH = db.DATA_DIR / "flashcards.db"
        db.initialize_database()
        paths = []
        for index, (width, height) in enumerate(((1800, 1000), (1000, 1800), (2200, 900))):
            image = QImage(width, height, QImage.Format_RGB32)
            image.fill(QColor("#f3f6fa"))
            painter = QPainter(image)
            painter.setPen(QColor("#ced9e5"))
            for x in range(0, width, 50):
                painter.drawLine(x, 0, x, height)
            for y in range(0, height, 50):
                painter.drawLine(0, y, width, y)
            painter.setPen(QColor("#17365d"))
            painter.setFont(QFont("Arial", 48))
            painter.drawText(80, 120, f"Example diagram {index + 1}")
            painter.setFont(QFont("Arial", 24))
            painter.drawText(80, 200, f"{width} x {height} pixels - inspect at 100%")
            painter.setBrush(QColor(("#648dd2", "#68aa8c", "#ddaa62")[index]))
            painter.drawEllipse(120, 300, 400, 400)
            painter.drawRect(650, 350, 220, 300)
            painter.end()
            path = db.IMAGES_DIR / f"example-{index + 1}.png"
            image.save(str(path))
            paths.append(path.relative_to(db.PROJECT_ROOT).as_posix())

        window = MainWindow()
        window.setWindowTitle("Flashcard Study App - temporary preview")
        window.repository.create_flashcard("Demo", "Images", 1,
                                          "Inspect the three example diagrams.",
                                          "Reveal all attachments, scroll horizontally, and open the image viewer.", paths)
        window.show()
        window._open_learning()
        learn = window.learn_view
        learn.start_learning()
        if not smoke:
            app.exec()
        else:
            output = project_root / "build" / "ui-check"
            output.mkdir(parents=True, exist_ok=True)
            QTest.qWait(200)
            learn.show_answer_button.click()
            QTest.qWait(200)
            window.grab().save(str(output / "learning.png"))
            bar = learn.image_scroll.horizontalScrollBar()
            assert bar.maximum() > 0
            bar.setValue(bar.maximum())
            assert bar.value() > 0
            learn.open_images_button.click()
            QTest.qWait(200)
            viewer = learn.image_viewer
            viewer.grab().save(str(output / "viewer-fit.png"))
            QTest.keyClick(viewer, Qt.Key_Right)
            assert viewer.index == 1
            QTest.keyClick(viewer, Qt.Key_Left)
            assert viewer.index == 0
            viewer.actual_size_button.click()
            QTest.qWait(100)
            assert viewer.scroll.horizontalScrollBar().maximum() > 0
            viewer.grab().save(str(output / "viewer-100.png"))
            learn.answer_current(True)
            assert learn.image_viewer is None
            assert not learn.answer_visible
            window.close()
            print(f"Windows Qt smoke check passed. Screenshots: {output}", flush=True)
        app.processEvents()


if __name__ == "__main__":
    main()
