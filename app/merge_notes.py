#!/usr/bin/env python3
"""Merge lecture slides into a printable notes PDF (2 slides per page)."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import anthropic
import fitz

ROOT = Path(__file__).resolve().parent.parent
SHARED_IMG_DIR = ROOT / "output/images"
NOTES_DIR = ROOT / "output/notes"

# Full transcript as one string — Claude will split it per slide.
FULL_TRANSCRIPT = """
Hello and welcome back to this new presentation. Today we're gonna look through very important topics
that are necessary to complete our mission. So first thing to begin is let me just take a moment.
So we are gonna walk through the value of innovation for investors and then today's focus is going to
be asset and equity story.

So how to prepare an elevator pitch. Let me give you a few remarks here. It's very important that
you are confident.

To see what's important to the people that actually invest in you, you need to really carefully
study them.

Another important thing is alpha and beta generation. You have any ideas what that means? So alpha
is the one that performs the best on the market. And beta is the most stable one.

And what is high growth and high risk? So high growth is the one that you can invest in and it has
a lot of potential to grow. High risk is the one that doesn't.

So for investors it's all about monetization. Buyback is to buy back. IPO is to make liquidity.
Acquisition deal is that somebody buys from you. License deal is that you are basically selling
to the person.

Think strategically.

And here is the comparison of asset story. So what's being developed? How defensible and
differentiated it is — it's all really important. And also the equity story. You need to know what
exactly you have to offer in order for investors to really believe in you.

And here also many stakeholders. I would recommend that you check all of these things — the slide
tells you what all of this means.

Innovation begins at adoption. That's the end of today's lecture. Thank you for being here.
"""

COVER = {
    "title": "Nucleate Villiger",
    "subtitle": "Asset + Equity Story",
    "meta_lines": [
        "Lecture test",
        "Villiger Valuation · Nucleate",
        "22 April 2026",
    ],
}


@dataclass
class Paths:
    slides_pdf: Path
    img_dir: Path
    img_prefix: str
    out_pdf: Path


@dataclass
class SlideNote:
    index: int
    title: str
    thumb: Path
    spoken: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build lecture notes PDF from slides.")
    parser.add_argument(
        "--slides",
        type=Path,
        default=ROOT / "input/slides/2026.04.22 Nucleate__Villiger Valuation_Asset Equity Story.pdf",
        help="Path to slides PDF",
    )
    parser.add_argument(
        "--name",
        default="Lecture test_notes",
        help="Output PDF base name (writes output/notes/<name>.pdf)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Anthropic API key (falls back to ANTHROPIC_API_KEY env var)",
    )
    parser.add_argument(
        "--transcript",
        type=Path,
        default=None,
        help="Path to a plain-text transcript file (overrides FULL_TRANSCRIPT constant)",
    )
    return parser.parse_args()


def _slug(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", name.lower()).strip("-")
    return slug or "lecture"


def resolve_paths(args: argparse.Namespace) -> Paths:
    stem = args.name
    return Paths(
        slides_pdf=args.slides,
        img_dir=SHARED_IMG_DIR,
        img_prefix=_slug(stem),
        out_pdf=NOTES_DIR / f"{stem}.pdf",
    )


def slide_title(lines: list[str]) -> str:
    skip = {"brainstorm", "your turn!", "your turn", "yes", "no", "??"}
    candidates: list[str] = []
    for line in lines:
        low = line.lower().strip()
        if low in skip or "@" in line or re.match(
            r"^(april|may|june|july|august|september|october|november|december|january|february|march)\b",
            low,
        ):
            continue
        if len(line) <= 3:
            continue
        if re.match(r"^(yes|no|\?\?|ip \?|uniqueness \?)$", low):
            continue
        candidates.append(line)

    if not candidates:
        return lines[0] if lines else "Slide"

    def score(line: str) -> tuple[int, int]:
        s = 0
        if line.endswith("?"):
            s += 4
        if "/" in line:
            s += 2
        if line.isupper() or (line[:1].isupper() and len(line) > 15):
            s += 2
        if "investor" in line.lower() or "story" in line.lower():
            s += 1
        return (s, len(line))

    return max(candidates, key=score)


def extract_thumb(page_index: int, page: fitz.Page, img_dir: Path, prefix: str) -> Path:
    thumb_path = img_dir / f"{prefix}-slide-{page_index + 1:02d}-thumb.jpg"
    zoom = 2.2
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    pix.save(thumb_path, jpg_quality=92)
    return thumb_path


def _page_to_base64(page: fitz.Page) -> str:
    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
    return base64.standard_b64encode(pix.tobytes("jpeg")).decode()


def analyze_slide_with_claude(
    page_index: int,
    page: fitz.Page,
    client: anthropic.Anthropic,
) -> dict:
    """Return {title, summary} for one slide via Claude vision."""
    page_text = page.get_text("text").strip()
    img_b64 = _page_to_base64(page)

    prompt = (
        "You are analyzing a lecture slide. "
        "The slide text (OCR) is given as a text block and the slide image is attached.\n\n"
        f"<slide_text>\n{page_text}\n</slide_text>\n\n"
        "Please respond with valid JSON only, no markdown fences, in this exact shape:\n"
        '{"title": "<short slide title, max 10 words>", "summary": "<2-4 sentence description of what this slide covers>"}'
    )

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=512,
        thinking={"type": "adaptive"},
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": img_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    text = next(
        (block.text for block in response.content if hasattr(block, "text")), "{}"
    )
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        lines = [ln.strip() for ln in page.get_text("text").strip().split("\n") if ln.strip()]
        return {"title": slide_title(lines) if lines else f"Slide {page_index + 1}", "summary": text}


def match_transcript_to_slides(
    slide_summaries: list[dict],
    full_transcript: str,
    client: anthropic.Anthropic,
) -> list[str]:
    """Return one transcript segment per slide, matched by content."""
    summaries_block = "\n".join(
        f"Slide {i + 1}: {s['title']} — {s['summary']}"
        for i, s in enumerate(slide_summaries)
    )

    prompt = (
        "You are given summaries for each lecture slide and a full spoken transcript.\n"
        "Your task: split the transcript into segments and assign each segment to the slide "
        "whose content it best matches. Every sentence must go to exactly one slide. "
        "If a slide has no matching speech, use an empty string for it.\n\n"
        f"<slide_summaries>\n{summaries_block}\n</slide_summaries>\n\n"
        f"<transcript>\n{full_transcript.strip()}\n</transcript>\n\n"
        f"Respond with valid JSON only — a list of {len(slide_summaries)} strings, one per slide, "
        "in slide order. No markdown, no extra keys."
    )

    response = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    )

    text = next(
        (block.text for block in response.content if hasattr(block, "text")), "[]"
    )
    try:
        result = json.loads(text)
        if isinstance(result, list) and len(result) == len(slide_summaries):
            return [str(s) for s in result]
    except json.JSONDecodeError:
        pass

    # Fallback: distribute transcript lines evenly
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", full_transcript.strip()) if s.strip()]
    n = len(slide_summaries)
    chunk = max(1, len(sentences) // n)
    return [
        " ".join(sentences[i * chunk: (i + 1) * chunk if i < n - 1 else None])
        for i in range(n)
    ]


def collect_slides(paths: Paths, client: anthropic.Anthropic, full_transcript: str) -> list[SlideNote]:
    paths.img_dir.mkdir(parents=True, exist_ok=True)
    paths.out_pdf.parent.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(paths.slides_pdf)
    slide_count = doc.page_count

    print(f"Analyzing {slide_count} slides with Claude…")
    slide_summaries: list[dict] = []
    thumbs: list[Path] = []

    for i in range(slide_count):
        page = doc[i]
        print(f"  Slide {i + 1}/{slide_count}…", end=" ", flush=True)
        info = analyze_slide_with_claude(i, page, client)
        slide_summaries.append(info)
        thumbs.append(extract_thumb(i, page, paths.img_dir, paths.img_prefix))
        print("done")

    print("Matching transcript to slides…")
    spoken_per_slide = match_transcript_to_slides(slide_summaries, full_transcript, client)

    slides: list[SlideNote] = []
    for i in range(slide_count):
        slides.append(
            SlideNote(
                index=i + 1,
                title=slide_summaries[i].get("title", f"Slide {i + 1}"),
                thumb=thumbs[i],
                spoken=spoken_per_slide[i] if i < len(spoken_per_slide) else "",
            )
        )

    doc.close()
    return slides


def _image_fit_size(path: Path, max_w: float, max_h: float) -> tuple[float, float]:
    pix = fitz.Pixmap(str(path))
    scale = min(max_w / pix.width, max_h / pix.height)
    return pix.width * scale, pix.height * scale


def _estimate_transcript_height(spoken: str, content_w: float, fontsize: float = 8) -> float:
    if not spoken.strip():
        return 0.0
    chars_per_line = max(24, int(content_w / (fontsize * 0.52)))
    lines = max(1, (len(spoken) + chars_per_line - 1) // chars_per_line)
    return 12 + lines * (fontsize + 2) + 2


def _slide_min_height(spoken: str, content_w: float, min_img_h: float = 90) -> float:
    return 22 + 3 + min_img_h + 3 + _estimate_transcript_height(spoken, content_w)


def _is_blank_page(page: fitz.Page) -> bool:
    return not page.get_text().strip() and not page.get_images() and not page.get_drawings()


def _trim_leading_blank_pages(doc: fitz.Document) -> None:
    while doc.page_count > 0 and _is_blank_page(doc[0]):
        doc.delete_page(0)


class _PdfLayout:
    GAP = 8
    SLOT_GAP = 10
    SLIDES_PER_PAGE = 2

    MIN_IMG_H = 90

    def __init__(self, doc: fitz.Document) -> None:
        self.doc = doc
        self.page_w, self.page_h = fitz.paper_size("a4")
        self.margin = 50
        self.bottom = self.page_h - self.margin
        self.content_w = self.page_w - 2 * self.margin
        self.page: fitz.Page | None = None
        self.y = self.margin

    def new_page(self) -> None:
        self.page = self.doc.new_page(width=self.page_w, height=self.page_h)
        self.y = self.margin

    def cover_page(self, title: str, subtitle: str, meta_lines: list[str]) -> None:
        if self.page is None:
            self.new_page()
        assert self.page is not None

        navy = (0.11, 0.16, 0.26)
        gold = (0.79, 0.64, 0.15)
        muted = (0.42, 0.42, 0.42)
        cream = (0.97, 0.96, 0.93)

        band_top = self.page_h * 0.30
        band_bottom = self.page_h * 0.72
        self.page.draw_rect(
            fitz.Rect(0, band_top, self.page_w, band_bottom),
            color=cream,
            fill=cream,
            width=0,
        )

        y = band_top + 36
        title_rect = fitz.Rect(self.margin, y, self.page_w - self.margin, y + 72)
        self.page.insert_textbox(
            title_rect,
            title,
            fontsize=28,
            fontname="hebo",
            align=fitz.TEXT_ALIGN_CENTER,
            color=navy,
        )

        y += 68
        subtitle_rect = fitz.Rect(self.margin, y, self.page_w - self.margin, y + 36)
        self.page.insert_textbox(
            subtitle_rect,
            subtitle,
            fontsize=17,
            fontname="helv",
            align=fitz.TEXT_ALIGN_CENTER,
            color=gold,
        )

        line_y = y + 48
        line_half = 70
        cx = self.page_w / 2
        self.page.draw_line(
            fitz.Point(cx - line_half, line_y),
            fitz.Point(cx + line_half, line_y),
            color=gold,
            width=2.2,
        )

        meta_text = "\n".join(meta_lines)
        meta_rect = fitz.Rect(
            self.margin, line_y + 22, self.page_w - self.margin, band_bottom - 16
        )
        self.page.insert_textbox(
            meta_rect,
            meta_text,
            fontsize=11,
            fontname="helv",
            align=fitz.TEXT_ALIGN_CENTER,
            color=muted,
        )

        self.y = self.bottom

    def _usable_height(self) -> float:
        return self.page_h - 2 * self.margin

    def _half_slot_height(self) -> float:
        return (self._usable_height() - self.SLOT_GAP) / self.SLIDES_PER_PAGE

    def fits_half_slot(self, slide: SlideNote) -> bool:
        need = _slide_min_height(slide.spoken, self.content_w, self.MIN_IMG_H)
        return need <= self._half_slot_height() + 2

    def _transcript_block_height(self, spoken: str, slot_h: float) -> float:
        est = _estimate_transcript_height(spoken, self.content_w)
        if est <= 0:
            return 0.0
        overhead = 22 + 3 + 3 + 12
        return min(est, max(slot_h - overhead - self.MIN_IMG_H, 24))

    def place_slide(self, slide: SlideNote, slot_y: float, slot_h: float) -> None:
        assert self.page is not None
        title_size = 11
        title_h = 22
        gap = 3
        label_h = 12 if slide.spoken.strip() else 0
        transcript_h = self._transcript_block_height(slide.spoken, slot_h)
        img_max_h = slot_h - title_h - gap - label_h - transcript_h - gap
        img_max_h = max(img_max_h, 40)

        title = f"{slide.index}. {slide.title}"
        title_rect = fitz.Rect(
            self.margin, slot_y, self.margin + self.content_w, slot_y + title_h
        )
        self.page.insert_textbox(
            title_rect, title, fontsize=title_size, fontname="hebo", align=0
        )

        img_y = slot_y + title_h + gap
        disp_w, disp_h = _image_fit_size(slide.thumb, self.content_w, img_max_h)
        x = self.margin + (self.content_w - disp_w) / 2
        img_rect = fitz.Rect(x, img_y, x + disp_w, img_y + disp_h)
        self.page.insert_image(img_rect, filename=str(slide.thumb))

        if slide.spoken.strip():
            ty = img_y + disp_h + 4
            tr_top = ty + label_h
            tr_bottom = slot_y + slot_h - 2
            if tr_bottom > tr_top + 8:
                muted = (0.42, 0.42, 0.42)
                self.page.insert_text(
                    (self.margin, ty + 8),
                    "Transcript",
                    fontsize=7.5,
                    fontname="hebo",
                    color=muted,
                )
                tr_rect = fitz.Rect(
                    self.margin, tr_top, self.margin + self.content_w, tr_bottom
                )
                self.page.insert_textbox(
                    tr_rect,
                    slide.spoken,
                    fontsize=8,
                    fontname="heit",
                    align=0,
                    color=(0.28, 0.28, 0.28),
                )

    def slides_page(self, top: SlideNote, bottom: SlideNote | None = None) -> None:
        self.new_page()
        if bottom is None:
            self.place_slide(top, self.margin, self._usable_height())
            return

        slot_h = self._half_slot_height()
        self.place_slide(top, self.margin, slot_h)
        slot_y = self.margin + slot_h + self.SLOT_GAP
        self.place_slide(bottom, slot_y, slot_h)


def _layout_slides(layout: _PdfLayout, slides: list[SlideNote]) -> None:
    i = 0
    while i < len(slides):
        if (
            i + 1 < len(slides)
            and layout.fits_half_slot(slides[i])
            and layout.fits_half_slot(slides[i + 1])
        ):
            layout.slides_page(slides[i], slides[i + 1])
            i += 2
        else:
            layout.slides_page(slides[i])
            i += 1


def build_pdf(slides: list[SlideNote], paths: Paths) -> None:
    doc = fitz.open()
    layout = _PdfLayout(doc)

    layout.cover_page(
        title=COVER["title"],
        subtitle=COVER["subtitle"],
        meta_lines=COVER["meta_lines"],
    )

    _layout_slides(layout, slides)

    _trim_leading_blank_pages(doc)
    doc.save(str(paths.out_pdf), deflate=True, garbage=4)
    doc.close()


def build_notes(paths: Paths, client: anthropic.Anthropic, full_transcript: str) -> Path:
    slides = collect_slides(paths, client, full_transcript)
    build_pdf(slides, paths)
    return paths.out_pdf


if __name__ == "__main__":
    args = parse_args()

    api_key = args.api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        api_key = input("Enter Anthropic API key: ").strip()

    client = anthropic.Anthropic(api_key=api_key)

    full_transcript = FULL_TRANSCRIPT
    if args.transcript:
        full_transcript = args.transcript.read_text(encoding="utf-8")

    paths = resolve_paths(args)
    pdf_path = build_notes(paths, client, full_transcript)
    print(f"Wrote {pdf_path}")
