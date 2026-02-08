from __future__ import annotations

import random
from typing import Any

from app.data.db import get_connection


class FlashcardRepository:
    def get_setting_int(self, key: str, default: int) -> int:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return default
        try:
            return int(row["value"])
        except (TypeError, ValueError):
            return default

    def set_setting_int(self, key: str, value: int) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO app_settings (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, str(value)),
            )

    def create_flashcard(
        self,
        category: str,
        subcategory: str,
        tier: int,
        question_text: str,
        answer_text: str,
        image_paths: list[str],
    ) -> int:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO flashcards (category, subcategory, tier, question_text, answer_text)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    category.strip(),
                    subcategory.strip(),
                    tier,
                    question_text.strip(),
                    answer_text.strip(),
                ),
            )
            flashcard_id = int(cursor.lastrowid)

            for idx, image_path in enumerate(image_paths):
                conn.execute(
                    """
                    INSERT INTO flashcard_images (flashcard_id, image_path, sort_order)
                    VALUES (?, ?, ?)
                    """,
                    (flashcard_id, image_path, idx),
                )

            return flashcard_id

    def get_categories(self) -> list[str]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT DISTINCT category FROM flashcards ORDER BY category"
            ).fetchall()
        return [row["category"] for row in rows]

    def get_subcategories(self, category: str | None = None) -> list[str]:
        with get_connection() as conn:
            if category:
                rows = conn.execute(
                    """
                    SELECT DISTINCT subcategory
                    FROM flashcards
                    WHERE category = ?
                    ORDER BY subcategory
                    """,
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT DISTINCT subcategory FROM flashcards ORDER BY subcategory"
                ).fetchall()
        return [row["subcategory"] for row in rows]

    def get_filtered_flashcards(
        self,
        category: str | None,
        subcategory: str | None,
        tier: int | None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if category:
            clauses.append("category = ?")
            params.append(category)
        if subcategory:
            clauses.append("subcategory = ?")
            params.append(subcategory)
        if tier is not None:
            clauses.append("tier = ?")
            params.append(tier)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
            SELECT id, category, subcategory, tier, question_text, answer_text, correct_streak, times_correct, times_wrong
            FROM flashcards
            {where_sql}
        """

        with get_connection() as conn:
            cards = [dict(row) for row in conn.execute(query, params).fetchall()]
            for card in cards:
                image_rows = conn.execute(
                    """
                    SELECT image_path
                    FROM flashcard_images
                    WHERE flashcard_id = ?
                    ORDER BY sort_order ASC
                    """,
                    (card["id"],),
                ).fetchall()
                card["images"] = [r["image_path"] for r in image_rows]

        random.shuffle(cards)
        return cards

    def update_after_answer(
        self,
        flashcard_id: int,
        is_correct: bool,
        streak_to_tier_up: int = 3,
        streak_to_tier_down: int = 1,
    ) -> None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT tier, correct_streak, wrong_streak, times_correct, times_wrong FROM flashcards WHERE id = ?",
                (flashcard_id,),
            ).fetchone()

            if row is None:
                return

            tier = int(row["tier"])
            correct_streak = int(row["correct_streak"])
            wrong_streak = int(row["wrong_streak"])
            times_correct = int(row["times_correct"])
            times_wrong = int(row["times_wrong"])

            if is_correct:
                correct_streak += 1
                wrong_streak = 0
                times_correct += 1
                if correct_streak >= streak_to_tier_up:
                    tier = min(5, tier + 1)
                    correct_streak = 0
            else:
                times_wrong += 1
                correct_streak = 0
                wrong_streak += 1
                if wrong_streak >= streak_to_tier_down:
                    tier = max(1, tier - 1)
                    wrong_streak = 0

            conn.execute(
                """
                UPDATE flashcards
                SET tier = ?, correct_streak = ?, wrong_streak = ?, times_correct = ?, times_wrong = ?
                WHERE id = ?
                """,
                (
                    tier,
                    correct_streak,
                    wrong_streak,
                    times_correct,
                    times_wrong,
                    flashcard_id,
                ),
            )

    def get_category_stats(self) -> list[dict[str, Any]]:
        with get_connection() as conn:
            category_rows = conn.execute(
                """
                SELECT
                    category,
                    COUNT(*) AS card_count,
                    GROUP_CONCAT(DISTINCT tier) AS tiers
                FROM flashcards
                GROUP BY category
                ORDER BY category
                """
            ).fetchall()

            sub_rows = conn.execute(
                """
                SELECT
                    category,
                    subcategory,
                    COUNT(*) AS card_count,
                    GROUP_CONCAT(DISTINCT tier) AS tiers
                FROM flashcards
                GROUP BY category, subcategory
                ORDER BY category, subcategory
                """
            ).fetchall()

        sub_map: dict[str, list[dict[str, Any]]] = {}
        for row in sub_rows:
            sub_map.setdefault(row["category"], []).append(
                {
                    "subcategory": row["subcategory"],
                    "card_count": int(row["card_count"]),
                    "tiers": self._parse_tiers(row["tiers"]),
                }
            )

        result: list[dict[str, Any]] = []
        for row in category_rows:
            category = row["category"]
            result.append(
                {
                    "category": category,
                    "card_count": int(row["card_count"]),
                    "tiers": self._parse_tiers(row["tiers"]),
                    "subcategories": sub_map.get(category, []),
                }
            )
        return result

    def get_cards_for_scope(
        self,
        category: str | None,
        subcategory: str | None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []

        if category:
            clauses.append("category = ?")
            params.append(category)
        if subcategory:
            clauses.append("subcategory = ?")
            params.append(subcategory)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        with get_connection() as conn:
            rows = conn.execute(
                f"""
                SELECT id, category, subcategory, tier, question_text, answer_text
                FROM flashcards
                {where_sql}
                ORDER BY id ASC
                """,
                params,
            ).fetchall()

        return [dict(row) for row in rows]

    def update_flashcard(
        self,
        flashcard_id: int,
        category: str,
        subcategory: str,
        tier: int,
        question_text: str,
        answer_text: str,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE flashcards
                SET category = ?, subcategory = ?, tier = ?, question_text = ?, answer_text = ?
                WHERE id = ?
                """,
                (
                    category.strip(),
                    subcategory.strip(),
                    int(tier),
                    question_text.strip(),
                    answer_text.strip(),
                    int(flashcard_id),
                ),
            )

    def delete_flashcard(self, flashcard_id: int) -> None:
        with get_connection() as conn:
            conn.execute("DELETE FROM flashcards WHERE id = ?", (int(flashcard_id),))

    def delete_scope(self, category: str, subcategory: str | None = None) -> int:
        with get_connection() as conn:
            if subcategory is None:
                cursor = conn.execute(
                    "DELETE FROM flashcards WHERE category = ?",
                    (category,),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM flashcards WHERE category = ? AND subcategory = ?",
                    (category, subcategory),
                )
            return int(cursor.rowcount)

    def reset_scope_tier_to_one(self, category: str, subcategory: str | None = None) -> int:
        with get_connection() as conn:
            if subcategory is None:
                cursor = conn.execute(
                    """
                    UPDATE flashcards
                    SET tier = 1, correct_streak = 0, wrong_streak = 0
                    WHERE category = ?
                    """,
                    (category,),
                )
            else:
                cursor = conn.execute(
                    """
                    UPDATE flashcards
                    SET tier = 1, correct_streak = 0, wrong_streak = 0
                    WHERE category = ? AND subcategory = ?
                    """,
                    (category, subcategory),
                )
            return int(cursor.rowcount)

    @staticmethod
    def _parse_tiers(raw: Any) -> list[int]:
        if raw is None:
            return []
        tiers: list[int] = []
        for chunk in str(raw).split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                tiers.append(int(chunk))
            except ValueError:
                continue
        return sorted(set(tiers))


