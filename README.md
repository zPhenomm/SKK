# Flashcard Study App (Windows, Python)

A lightweight desktop flashcard app built with **PySide6 + SQLite**.

## Features in this MVP

- Main menu with:
  - Start learning
  - Create flashcard
  - Settings
  - View flashcards
- Create flashcard screen:
  - Category
  - Subcategory
  - Tier (1-5)
  - Question text
  - Answer text
  - Image support (drag & drop files or paste from clipboard)
- Learning screen:
  - Filter by category, subcategory, tier
  - Random flashcards from matching filters
  - Shows question first
  - "Show answer" button reveals answer text + answer images
  - Correct/Wrong buttons
  - Tier progression logic:
    - Correct streak threshold -> tier up
    - Wrong streak threshold -> tier down
- Settings screen:
  - Configure how many correct answers are required to move a card up a tier
  - Configure how many wrong answers are required to move a card down a tier
- View flashcards screen:
  - Statistics overview by category/subcategory
  - Card counts and tiers shown per scope
  - Drill down into category/subcategory to list all cards
  - Edit card fields (question, answer, category, subcategory, tier)
  - Delete a single card
  - Delete entire category or subcategory (all cards inside)
  - Reset all cards in selected category/subcategory to tier 1

## Tech stack

- Python 3.10+
- PySide6 (UI)
- SQLite (local DB)

## Setup

1. Create & activate a virtual environment (recommended)
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m app.main
```

On first launch, the app creates:

- `data/flashcards.db`
- `data/images/`

## Notes

- This is designed for **personal/local use**.
- Settings and view-cards are now functional MVP screens and can be expanded further.