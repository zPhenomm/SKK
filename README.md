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
  - Edit card button to correct question and answer text without leaving learning
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

- Python 3.14
- PySide6 (UI)
- SQLite (local DB)

## Setup

From the project folder in PowerShell, create a Python 3.14 environment:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Run

```powershell
.\.venv\Scripts\python.exe -m app.main
```

From another working directory, use the full path to `.venv\Scripts\python.exe`
with `-c "from app.main import main; main()"` and set `PYTHONPATH` to this project
folder first. Data is always read from the project folder, independent of the
working directory.

On first launch, the app creates these paths inside the project folder:

- `data/flashcards.db`
- `data/images/`

## Answer images and learning

- Reveal the answer before grading it Correct or Wrong.
- **Edit card** opens the current question and answer for correction. Save applies
  changes immediately; Cancel or Escape discards them. Editing keeps your place,
  answer reveal state, attached images, tier, and learning history.
- All attached images appear in a horizontal strip; scroll sideways to see more.
- Click **Open images** to start at the first image, or click a preview to open it.
- The separate viewer supports Previous/Next, Left/Right arrow keys, Fit, 100%,
  and zoom in/out in 25 percentage-point steps (10–400%). Enlarged images have scrollbars.
- Moving to another card or leaving learning closes the viewer and hides images.
- Failed saves keep your form entries and remove images created by that attempt.
- Saving a card keeps its category, subcategory, and tier selected for the next card.

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use temporary databases and images. Qt tests run offscreen by default.
Set `$env:QT_QPA_PLATFORM = "windows"` to exercise visible windows instead.

To try the image features with temporary example cards:

```powershell
.\.venv\Scripts\python.exe -m tests.preview_demo
```

Add `--smoke` to run the viewer checks automatically and save screenshots to
`build/ui-check/`. The demo leaves your study database untouched.

## Distribute

To build a self contained Windows .exe of the app, install pyinstaller into the project venv:
```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pyinstaller
```
Build the release folder:
```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --onedir --windowed --name FlashcardStudy --paths . app/main.py
```

Deliver the release folder to the end user, existing databases can be copied into its root as /data

## Notes

- This is designed for **personal/local use**.
- Settings and view-cards are now functional MVP screens and can be expanded further.
