# Flashcard Study App (Windows, Python)

A lightweight desktop flashcard app built with **PySide6 + SQLite**.

## Features in this MVP

- Main menu with:
  - Start learning
  - Create flashcard
  - Settings (placeholder)
  - View flashcards (placeholder)
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
    - Correct several times (default 3 streak) -> tier up
    - Wrong -> tier down

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
- Settings and view-cards screens are placeholders for later expansion.