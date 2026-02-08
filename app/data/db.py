from __future__ import annotations

import sqlite3
from pathlib import Path


DATA_DIR = Path("data")
IMAGES_DIR = DATA_DIR / "images"
DB_PATH = DATA_DIR / "flashcards.db"


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    ensure_data_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def initialize_database() -> None:
    with get_connection() as conn:
        # If legacy schema is detected, reset to a clean DB schema for current MVP.
        table_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='flashcards'"
        ).fetchone()
        if table_exists:
            existing_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(flashcards)").fetchall()
            }
            if "text_content" in existing_columns:
                conn.executescript(
                    """
                    DROP TABLE IF EXISTS flashcard_images;
                    DROP TABLE IF EXISTS flashcards;
                    DROP TABLE IF EXISTS app_settings;
                    """
                )

        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS flashcards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                subcategory TEXT NOT NULL,
                tier INTEGER NOT NULL CHECK (tier BETWEEN 1 AND 5),
                question_text TEXT NOT NULL DEFAULT '',
                answer_text TEXT NOT NULL DEFAULT '',
                correct_streak INTEGER NOT NULL DEFAULT 0,
                wrong_streak INTEGER NOT NULL DEFAULT 0,
                times_correct INTEGER NOT NULL DEFAULT 0,
                times_wrong INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS flashcard_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flashcard_id INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (flashcard_id) REFERENCES flashcards(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        conn.execute(
            "INSERT OR IGNORE INTO app_settings (key, value) VALUES ('tier_up_threshold', '3')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO app_settings (key, value) VALUES ('tier_down_threshold', '1')"
        )
