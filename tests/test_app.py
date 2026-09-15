import gc
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QMimeData, Qt, QTimer
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from app.data import db
from app.data.repository import FlashcardRepository
from app.main import MainWindow
from app.services.learning import LearningSession
from app.ui.create_flashcard import CreateFlashcardView
from app.ui.edit_flashcard import EditFlashcardDialog
from app.ui.image_viewer import ImageViewer
from app.ui.learn import LearnView
from app.ui.view_cards import ViewCardsView


class DatabaseFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skk-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        for name, value in {
            "PROJECT_ROOT": self.root,
            "DATA_DIR": self.root / "data",
            "IMAGES_DIR": self.root / "data" / "images",
            "DB_PATH": self.root / "data" / "flashcards.db",
        }.items():
            patch.object(db, name, value).start()
        db.initialize_database()
        self.repo = FlashcardRepository()

    def card(self, category="Category", subcategory="Sub", tier=1, images=()):
        return self.repo.create_flashcard(category, subcategory, tier, "Question", "Answer", list(images))

    def state(self, card_id):
        with db.get_connection() as conn:
            return dict(conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,)).fetchone())


class DatabaseTests(DatabaseFixture):
    def test_transactions_close_commit_rollback_and_cascade(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            card_id = self.card(images=["data/images/a.png", "data/images/b.png"])
            with db.get_connection() as conn:
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")
            with self.assertRaises(sqlite3.IntegrityError):
                self.card(images=[None])
            self.assertEqual(len(self.repo.get_cards_for_scope(None, None)), 1)
            with self.assertRaises(RuntimeError):
                with db.get_connection() as failed_conn:
                    failed_conn.execute("UPDATE flashcards SET tier = 4")
                    raise RuntimeError("Rollback")
            with self.assertRaises(sqlite3.ProgrammingError):
                failed_conn.execute("SELECT 1")
            self.assertEqual(self.state(card_id)["tier"], 1)
            self.repo.delete_flashcard(card_id)
            with db.get_connection() as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM flashcard_images").fetchone()[0], 0)
            gc.collect()
            self.assertEqual([w for w in caught if issubclass(w.category, ResourceWarning)], [])
        # Windows rejects this operation while a database handle remains open.
        moved = db.DB_PATH.with_suffix(".moved")
        db.DB_PATH.rename(moved)
        moved.unlink()

    def test_streak_thresholds_boundaries_and_reset(self):
        card_id = self.card()
        for _ in range(2):
            self.repo.update_after_answer(card_id, True)
        self.assertEqual(self.state(card_id)["tier"], 1)
        self.repo.update_after_answer(card_id, True)
        self.assertEqual(self.state(card_id)["tier"], 2)
        self.repo.update_after_answer(card_id, False, streak_to_tier_down=2)
        self.assertEqual(self.state(card_id)["tier"], 2)
        self.repo.update_after_answer(card_id, True)
        self.assertEqual(self.state(card_id)["wrong_streak"], 0)
        for _ in range(10):
            self.repo.update_after_answer(card_id, True, streak_to_tier_up=1)
        self.assertEqual(self.state(card_id)["tier"], 5)
        for _ in range(10):
            self.repo.update_after_answer(card_id, False)
        self.assertEqual(self.state(card_id)["tier"], 1)
        self.repo.reset_scope_tier_to_one("Category")
        self.assertEqual(self.state(card_id)["correct_streak"], 0)
        self.assertEqual(self.state(card_id)["wrong_streak"], 0)

    def test_settings_filters_and_attachment_order(self):
        self.repo.set_setting_int("tier_up_threshold", 4)
        self.assertEqual(self.repo.get_setting_int("tier_up_threshold", 3), 4)
        with db.get_connection() as conn:
            conn.execute("UPDATE app_settings SET value = 'invalid'")
        self.assertEqual(self.repo.get_setting_int("tier_up_threshold", 3), 3)
        card_id = self.card("Any", "Any", 3, ["b.png", "a.png"])
        self.card("Other", "Other", 1)
        result = self.repo.get_filtered_flashcards("Any", "Any", 3)
        self.assertEqual([c["id"] for c in result], [card_id])
        self.assertEqual(result[0]["images"], ["b.png", "a.png"])

    def test_learning_session_shuffles_once_without_mutating_input(self):
        cards = [{"id": n} for n in range(3)]
        with patch("app.services.learning.random.shuffle", side_effect=lambda rows: rows.reverse()) as shuffle:
            session = LearningSession(cards)
        shuffle.assert_called_once()
        self.assertEqual([session.next_card()["id"] for _ in range(3)], [2, 1, 0])
        self.assertIsNone(session.next_card())
        self.assertEqual(cards, [{"id": n} for n in range(3)])

    def test_import_and_path_resolution_from_another_directory(self):
        project = Path(__file__).resolve().parents[1]
        env = os.environ | {"PYTHONPATH": str(project), "PYTHONDONTWRITEBYTECODE": "1"}
        code = (
            "from app.main import MainWindow; from app.data.db import DB_PATH, resolve_image_path; "
            "print(DB_PATH); print(resolve_image_path('data/images/test.png'))"
        )
        result = subprocess.run([sys.executable, "-c", code], cwd=self.root, env=env,
                                text=True, capture_output=True, check=True)
        self.assertIn(str(project / "data" / "flashcards.db"), result.stdout)
        self.assertIn(str(project / "data" / "images" / "test.png"), result.stdout)
        absolute = self.root / "existing.png"
        self.assertEqual(db.resolve_image_path(str(absolute)), absolute)


class GuiTests(DatabaseFixture):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.widgets = []
        self.addCleanup(self.dispose_widgets)
        patch("app.ui.create_flashcard.show_info").start()
        patch("app.ui.learn.show_info").start()
        patch("app.ui.view_cards.show_info").start()
        self.warning = patch("app.ui.create_flashcard.QMessageBox.warning").start()

    def dispose_widgets(self):
        for widget in self.widgets:
            widget.close()
            widget.deleteLater()
        self.app.sendPostedEvents(None, QEvent.DeferredDelete)
        self.app.processEvents()
        gc.collect()

    def widget(self, widget):
        self.widgets.append(widget)
        widget.resize(900, 800)
        widget.show()
        self.app.processEvents()
        return widget

    def image(self, name="source.png", width=1600, height=900):
        path = self.root / name
        image = QImage(width, height, QImage.Format_RGB32)
        image.fill(Qt.blue)
        self.assertTrue(image.save(str(path)))
        return path

    def create_form(self):
        form = self.widget(CreateFlashcardView(self.repo))
        form.category_input.setCurrentText("Category")
        form.subcategory_input.setCurrentText("Sub")
        form.tier_input.setValue(3)
        form.question_input.setPlainText("Question")
        form.answer_input.setPlainText("Answer")
        return form

    def test_file_and_clipboard_save_retains_classification(self):
        form = self.create_form()
        source = self.image()
        form._add_image_paths([str(source)])
        saved_clipboard = QMimeData()
        mime = self.app.clipboard().mimeData()
        if mime:
            for fmt in mime.formats():
                saved_clipboard.setData(fmt, mime.data(fmt))
        try:
            self.app.clipboard().setImage(QImage(str(source)))
            form.question_input.setFocus()
            QTest.keyClick(form.question_input, Qt.Key_V, Qt.ControlModifier)
            self.assertEqual(len(form._image_items), 2)
            self.assertEqual(form.question_input.toPlainText(), "Question")
            self.app.clipboard().setText(" pasted text")
            QTest.keyClick(form.question_input, Qt.Key_End)
            QTest.keyClick(form.question_input, Qt.Key_V, Qt.ControlModifier)
            self.assertIn("pasted text", form.question_input.toPlainText())
        finally:
            if saved_clipboard.formats():
                self.app.clipboard().setMimeData(saved_clipboard)
            else:
                self.app.clipboard().clear()
        form._save_flashcard()
        cards = self.repo.get_filtered_flashcards(None, None, None)
        self.assertEqual(len(cards), 1)
        self.assertEqual(len(cards[0]["images"]), 2)
        for image in cards[0]["images"]:
            self.assertFalse(Path(image).is_absolute())
            self.assertTrue(db.resolve_image_path(image).is_file())
        self.assertEqual(form.category_input.currentText(), "Category")
        self.assertEqual(form.subcategory_input.currentText(), "Sub")
        self.assertEqual(form.tier_input.value(), 3)
        self.assertEqual(form.question_input.toPlainText(), "")
        self.assertEqual(form._image_items, [])
        self.warning.assert_not_called()

    def test_invalid_image_rejected_and_save_failures_keep_form(self):
        form = self.create_form()
        invalid = self.root / "invalid.png"
        invalid.write_text("not an image", encoding="utf-8")
        form._add_image_paths([str(invalid), str(self.root / "missing.png")])
        self.assertEqual(form._image_items, [])
        self.warning.assert_called_once()
        source = self.image()
        form._add_image_paths([str(source)])
        import shutil
        real_copy = shutil.copyfile

        def partial_copy(src, dst):
            real_copy(src, dst)
            raise OSError("Disk full after partial copy")

        for target, failure in (
            ("app.ui.create_flashcard.shutil.copyfile", partial_copy),
            ("app.ui.create_flashcard.FlashcardRepository.create_flashcard", sqlite3.OperationalError("DB locked")),
        ):
            with self.subTest(target=target), patch(target, side_effect=failure):
                form._save_flashcard()
            self.assertEqual(list(db.IMAGES_DIR.iterdir()), [])
            self.assertEqual(self.repo.get_cards_for_scope(None, None), [])
            self.assertEqual(form.question_input.toPlainText(), "Question")
            self.assertEqual(len(form._image_items), 1)
        source.unlink()
        form._save_flashcard()
        self.assertEqual(list(db.IMAGES_DIR.iterdir()), [])

    def test_pasted_image_failure_cleans_preceding_copy(self):
        form = self.create_form()
        form._add_image_paths([str(self.image())])
        form._image_items.append({"kind": "qimage", "value": QImage()})
        form._save_flashcard()
        self.assertEqual(list(db.IMAGES_DIR.iterdir()), [])
        self.assertEqual(self.repo.get_cards_for_scope(None, None), [])
        self.assertEqual(form.question_input.toPlainText(), "Question")

    def test_filters_preserve_values_and_literal_any(self):
        card_id = self.card("Any", "Any", 3)
        self.card("Other", "Other")
        learn = self.widget(LearnView(self.repo))
        learn.category_combo.setCurrentIndex(learn.category_combo.findData("Any"))
        learn.subcategory_combo.setCurrentIndex(learn.subcategory_combo.findData("Any"))
        learn.tier_combo.setCurrentIndex(learn.tier_combo.findData(3))
        learn.populate_filters()
        learn.start_learning()
        self.assertEqual(learn.current_card["id"], card_id)
        self.assertEqual(learn.category_combo.currentData(), "Any")
        self.assertEqual(learn.subcategory_combo.currentData(), "Any")
        self.assertEqual(learn.tier_combo.currentData(), 3)
        self.repo.delete_flashcard(card_id)
        learn.populate_filters()
        self.assertIsNone(learn.category_combo.currentData())
        self.assertIsNone(learn.subcategory_combo.currentData())
        learn.start_learning()
        self.assertIsNone(learn.current_card)
        self.assertIn("No flashcards", learn.progress_label.text())

    def test_reveal_grading_preview_order_and_viewer_lifetime(self):
        paths = [str(self.image(f"image{i}.png")) for i in range(3)]
        card_id = self.card(images=paths)
        learn = self.widget(LearnView(self.repo))
        learn.start_learning()
        learn.answer_current(True)
        self.assertEqual(self.state(card_id)["times_correct"], 0)
        self.assertFalse(learn.correct_button.isEnabled())
        learn.show_answer()
        self.assertTrue(learn.correct_button.isEnabled())
        self.app.processEvents()
        previews = learn.image_scroll._previews
        self.assertEqual(len(previews), 3)
        self.assertGreater(learn.image_scroll.horizontalScrollBar().maximum(), 0)
        spy = QSignalSpy(learn.image_scroll.image_clicked)
        previews[2][0].click()
        self.assertEqual(spy.at(0), [2])
        self.assertEqual(learn.image_viewer.index, 2)
        self.assertEqual(learn.image_viewer.image_paths, paths)
        learn.open_images_button.click()
        self.assertEqual(learn.image_viewer.index, 0)
        viewer = learn.image_viewer
        learn.answer_current(True)
        self.assertFalse(viewer.isVisible())
        self.assertIsNone(learn.image_viewer)
        self.assertFalse(learn.answer_visible)
        self.assertFalse(learn.correct_button.isEnabled())
        self.assertEqual(learn.image_scroll._previews, [])
        self.assertEqual(self.state(card_id)["times_correct"], 1)
        self.assertEqual(learn.loop_count, 2)
        learn.show_answer()
        learn.open_images()
        viewer = learn.image_viewer
        learn.hide()
        self.assertFalse(viewer.isVisible())
        self.assertIsNone(learn.current_card)

    def test_edit_during_learning_preserves_session_and_reveal_state(self):
        paths = [str(self.image())]
        card_id = self.card(tier=3, images=paths)
        self.repo.update_after_answer(card_id, True)
        before = self.state(card_id)
        learn = self.widget(LearnView(self.repo))
        self.assertFalse(learn.edit_button.isEnabled())
        learn.start_learning()
        session = learn.session
        progress = learn.progress_label.text()

        for revealed in (False, True):
            if revealed:
                learn.show_answer()

            def save_dialog():
                dialog = self.app.activeModalWidget()
                dialog.question_input.setPlainText(f"Corrected question {revealed}")
                dialog.answer_input.setPlainText(f"Corrected answer {revealed}")
                dialog.buttons.button(QDialogButtonBox.Save).click()

            QTimer.singleShot(0, save_dialog)
            learn.edit_button.click()
            self.assertIs(learn.session, session)
            self.assertEqual(learn.progress_label.text(), progress)
            self.assertEqual(learn.current_card["id"], card_id)
            self.assertEqual(learn.question_text.toPlainText(), f"Corrected question {revealed}")
            self.assertEqual(learn.answer_visible, revealed)
            self.assertEqual(learn.correct_button.isEnabled(), revealed)
            self.assertEqual(learn.wrong_button.isEnabled(), revealed)
            self.assertEqual(learn.show_answer_button.isEnabled(), not revealed)
            if revealed:
                self.assertEqual(learn.answer_text.toPlainText(), "Corrected answer True")
            else:
                self.assertIn("Answer is hidden", learn.answer_text.toPlainText())
            saved = self.state(card_id)
            for key in before.keys() - {"question_text", "answer_text"}:
                self.assertEqual(saved[key], before[key])
            self.assertEqual(saved["answer_text"], f"Corrected answer {revealed}")
            self.assertEqual(self.repo.get_filtered_flashcards(None, None, None)[0]["images"], paths)

        learn.answer_current(True)
        self.assertEqual(learn.loop_count, 2)
        self.assertEqual(learn.question_text.toPlainText(), "Corrected question True")
        self.assertEqual(self.state(card_id)["times_correct"], before["times_correct"] + 1)
        learn.hide()
        self.assertFalse(learn.edit_button.isEnabled())

    def test_edit_cancel_validation_and_save_failure(self):
        card_id = self.card()
        learn = self.widget(LearnView(self.repo))
        learn.start_learning()
        before = self.state(card_id)

        for cancel in ("button", "escape", "close"):
            def cancel_dialog():
                dialog = self.app.activeModalWidget()
                dialog.question_input.setPlainText("Discard this")
                if cancel == "button":
                    dialog.buttons.button(QDialogButtonBox.Cancel).click()
                elif cancel == "escape":
                    QTest.keyClick(dialog, Qt.Key_Escape)
                else:
                    dialog.close()

            QTimer.singleShot(0, cancel_dialog)
            learn.edit_button.click()
            self.assertEqual(self.state(card_id), before)
            self.assertEqual(learn.question_text.toPlainText(), "Question")

        dialog = self.widget(EditFlashcardDialog(self.repo, learn.current_card, learn))
        for field in (dialog.question_input, dialog.answer_input):
            field.setPlainText("  ")
            dialog.buttons.button(QDialogButtonBox.Save).click()
            self.assertTrue(dialog.isVisible())
            self.assertEqual(self.state(card_id), before)
            field.setPlainText("Correction")

        with patch.object(self.repo, "update_flashcard", side_effect=sqlite3.OperationalError("locked")):
            dialog.buttons.button(QDialogButtonBox.Save).click()
        self.assertTrue(dialog.isVisible())
        self.assertEqual(dialog.answer_input.toPlainText(), "Correction")
        self.assertEqual(learn.current_card["answer_text"], "Answer")
        self.assertEqual(self.state(card_id), before)
        dialog.buttons.button(QDialogButtonBox.Save).click()
        self.assertFalse(dialog.isVisible())
        self.assertEqual(self.state(card_id)["answer_text"], "Correction")

    def test_tier_filter_exhaustion(self):
        self.card()
        self.repo.set_setting_int("tier_up_threshold", 1)
        learn = self.widget(LearnView(self.repo))
        learn.tier_combo.setCurrentIndex(learn.tier_combo.findData(1))
        learn.start_learning()
        learn.show_answer()
        learn.answer_current(True)
        self.assertIsNone(learn.current_card)
        self.assertIsNone(learn.session)
        self.assertIn("No matching cards", learn.progress_label.text())
        self.assertFalse(learn.correct_button.isEnabled())

        self.assertFalse(learn.edit_button.isEnabled())

    def test_viewer_navigation_zoom_resize_and_missing_images(self):
        paths = [str(self.image()), str(self.root / "missing.png"), str(self.image("portrait.png", 900, 1600))]
        viewer = self.widget(ImageViewer(paths))
        viewer.activateWindow()
        QTest.qWait(30)
        self.assertFalse(viewer.previous_button.isEnabled())
        self.assertTrue(viewer.fit_mode)
        self.assertFalse(viewer.image_label.pixmap().isNull())
        viewer.actual_size_button.click()
        self.app.processEvents()
        self.assertEqual(viewer.scale, 1)
        self.assertGreater(viewer.scroll.horizontalScrollBar().maximum(), 0)
        viewer.zoom_in_button.click()
        self.assertEqual(viewer.scale, 1.25)
        viewer.zoom_out_button.click()
        self.assertEqual(viewer.scale, 1)
        viewer.set_zoom(20)
        self.assertEqual(viewer.scale, 4)
        viewer.set_zoom(0)
        self.assertEqual(viewer.scale, 0.1)
        viewer.fit_button.click()
        viewer.resize(700, 600)
        self.app.processEvents()
        self.assertLessEqual(viewer.image_label.width(), viewer.scroll.viewport().width())
        self.assertLessEqual(viewer.image_label.height(), viewer.scroll.viewport().height())
        QTest.keyClick(viewer, Qt.Key_Right)
        self.assertEqual(viewer.index, 1)
        self.assertIn("missing", viewer.image_label.text())
        self.assertFalse(viewer.zoom_in_button.isEnabled())
        viewer.next_button.click()
        self.assertEqual(viewer.index, 2)
        self.assertTrue(viewer.fit_mode)
        self.assertFalse(viewer.next_button.isEnabled())
        QTest.keyClick(viewer, Qt.Key_Left)
        self.assertEqual(viewer.index, 1)

    def test_scope_reset_refreshes_overlapping_table(self):
        self.card(tier=4)
        self.card(subcategory="Other", tier=3)
        view = self.widget(ViewCardsView(self.repo))
        for displayed_sub, reset_sub in (("Sub", None), (None, "Sub")):
            with self.subTest(displayed_sub=displayed_sub, reset_sub=reset_sub):
                with db.get_connection() as conn:
                    conn.execute("UPDATE flashcards SET tier = 4")
                view.refresh_statistics()
                view.current_category = "Category"
                view.current_subcategory = displayed_sub
                view._load_cards_for_current_scope()
                item = view.stats_tree.topLevelItem(0)
                if reset_sub:
                    item = next(item.child(i) for i in range(item.childCount())
                                if item.child(i).data(0, Qt.UserRole)[2] == reset_sub)
                view.stats_tree.setCurrentItem(item)
                view.reset_selected_scope_tier()
                card = next(c for c in view.current_cards if c["subcategory"] == "Sub")
                self.assertEqual(card["tier"], 1)

    def test_all_screens_and_signal_connections(self):
        window = self.widget(MainWindow())
        for button, expected in (
            (window.main_menu_view.create_flashcard_button, window.create_view),
            (window.main_menu_view.start_learning_button, window.learn_view),
            (window.main_menu_view.settings_button, window.settings_view),
            (window.main_menu_view.view_flashcards_button, window.view_cards_view),
        ):
            button.click()
            self.assertIs(window.stack.currentWidget(), expected)
            expected.back_button.click()
            self.assertIs(window.stack.currentWidget(), window.main_menu_view)


if __name__ == "__main__":
    unittest.main()
