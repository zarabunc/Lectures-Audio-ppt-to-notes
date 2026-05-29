# Lectures-Audio-ppt-to-notes

Merge lecture slide PDFs into printable **notes PDFs** and Markdown.

## Features

- High-quality slide thumbnails embedded in PDF
- Styled cover page (centered title, gold accent)
- **2 slides per page** with title directly above each slide
- Markdown export with images in `output/notes/images/`

## Setup

```bash
git clone https://github.com/zarabunc/Lectures-Audio-ppt-to-notes.git
cd Lectures-Audio-ppt-to-notes
./setup.sh
```

## Usage

1. Put your slides PDF in `input/slides/`
2. Edit `SLIDE_TITLES`, `TRANSCRIPT_BY_SLIDE`, and `COVER` in `merge_notes.py` for your lecture (optional)
3. Run:

```bash
.venv/bin/python3 merge_notes.py \
  --slides "input/slides/your-deck.pdf" \
  --name "my_lecture_notes"
```

Output:

- `output/notes/my_lecture_notes.pdf`
- `output/notes/my_lecture_notes.md`

## Requirements

- Python 3.10+
- [PyMuPDF](https://pypi.org/project/PyMuPDF/)
