"""Simple, page-aware syllabus chunking for semantic retrieval."""

import re
from collections.abc import Iterable, Mapping


# Known heading spellings are mapped to stable section labels. Other likely
# standalone headings keep their own cleaned title as the section label.
_HEADING_ALIASES = {
    "attendance": "Attendance",
    "attendance policy": "Attendance",
    "absences": "Attendance",
    "late work": "Late Work",
    "late assignments": "Late Work",
    "late submission": "Late Work",
    "grading": "Grading",
    "grades": "Grading",
    "grading policy": "Grading",
    "assignments": "Assignments",
    "coursework": "Assignments",
    "exams": "Exams",
    "examination": "Exams",
    "exam policy": "Exams",
    "academic integrity": "Academic Integrity",
    "academic honesty": "Academic Integrity",
    "course schedule": "Course Schedule",
    "schedule": "Course Schedule",
    "participation": "Participation",
    "class participation": "Participation",
    "discussion": "Discussion",
    "discussion sections": "Discussion",
    "ta": "TA Information",
    "ta information": "TA Information",
    "teaching assistant": "TA Information",
    "teaching assistants": "TA Information",
    "professor contact information": "Professor Contact Information",
    "professor contact": "Professor Contact Information",
    "instructor contact information": "Professor Contact Information",
    "office hours": "Office Hours",
    "prerequisites": "Prerequisites",
    "prerequisite": "Prerequisites",
    "textbooks": "Textbooks",
    "textbook": "Textbooks",
    "course content": "Course Content",
    "criteria for grading": "Grading",
    "grades and grading": "Grading",
    "final examination": "Exams",
    "final exam": "Exams",
    "missed exam policy": "Exams",
    "exam policy": "Exams",
    "collaboration and academic integrity": "Academic Integrity",
    "instructor office hours": "Office Hours",
    "ta office hours": "Office Hours",
    "required textbook": "Textbooks",
    "required textbooks": "Textbooks",
    "suggested textbook": "Textbooks",
    "suggested textbooks": "Textbooks",
    "course assignments": "Assignments",
    "written assignments": "Assignments",
    "assignment revision policy": "Assignments",
    "topical outline": "Course Content",
    "sessions": "Course Schedule",
    "learning outcomes": "Course Content",
    "course resources": "Course Resources",
    "evaluations": "Grading",
    "problem sets": "Assignments",
    "plagiarism": "Academic Integrity",
}

_HEADING_CUES = {
    "academic", "assignment", "attendance", "course", "discussion", "exam",
    "grade", "grading", "hours", "information", "integrity", "office", "outcome",
    "policy", "prerequisite", "resource", "responsibility", "schedule", "session",
    "textbook", "topic",
}


def _clean_heading(line: str) -> str:
    cleaned = line.strip()
    cleaned = re.sub(r"^[#*\s]+|[#*_\s]+$", "", cleaned)
    cleaned = re.sub(r"[\s:.,;]+$", "", cleaned)
    return re.sub(r"\s+", " ", cleaned)


def _heading(line: str) -> str | None:
    """Return a canonical label for a recognized heading spelling."""
    cleaned = _clean_heading(line)
    return _HEADING_ALIASES.get(cleaned.lower())


def _likely_unlisted_heading(line: str) -> str | None:
    """Conservatively recognize short, standalone title-like heading lines."""
    cleaned = _clean_heading(line)
    words = cleaned.split()
    if not cleaned or len(cleaned) > 60 or len(words) > 8 or any(ch.isdigit() for ch in cleaned):
        return None
    if cleaned.startswith(("•", "-", "o ")) or re.match(r"^\d+[.)]", cleaned):
        return None
    # A colon followed by same-line content is not a standalone heading; keep
    # the full line and let the recognized inline-heading path handle it.
    if ":" in cleaned and not line.strip().endswith(":"):
        return None
    # Require heading-like capitalization even when a line ends in a colon;
    # prose fragments such as "in this order:" should not become section names.
    if cleaned.isupper() and any(char.isalpha() for char in cleaned):
        return cleaned.title()
    title_case = len(words) >= 2 and all(word[:1].isupper() for word in words)
    has_heading_cue = any(
        any(cue in re.sub(r"[^a-z]", "", word.lower()) for cue in _HEADING_CUES)
        for word in words
    )
    if title_case and has_heading_cue and not cleaned.endswith((".", "?", "!")):
        return cleaned
    return None


def _split_long(text: str, size: int, overlap: int) -> list[str]:
    """Split oversized text near whitespace, retaining a small character overlap."""
    parts = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + size // 2, end)
            if boundary > start:
                end = boundary
        part = text[start:end].strip()
        if part:
            parts.append(part)
        if end >= len(text):
            break
        next_start = max(start + 1, end - overlap)
        start = next_start
    return parts


def chunk_text(pages: Iterable[Mapping], chunk_size: int = 1000,
               overlap: int = 100) -> list[dict[str, object]]:
    """Turn parse_pdf page records into retrieval chunks.

    Args:
        pages: Iterable of ``{"page": one_based_number, "text": content}``.
        chunk_size: Maximum approximate characters per chunk (must be > 0).
        overlap: Character overlap for splitting a long paragraph.

    Returns dictionaries with ``chunk_id``, ``text``, ``section``, and
    ``pages`` (unique source page numbers). Known headings receive canonical
    labels; likely standalone unlisted headings start sections with their own
    title as the label. Remaining text is chunked by paragraphs and size.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    # Group contiguous text by recognized section while keeping page provenance.
    blocks: list[tuple[str | None, str, int]] = []
    current_section = None
    for record in pages:
        if not isinstance(record, Mapping) or "text" not in record:
            raise ValueError("each page must be a mapping containing 'text' and 'page'")
        page_number = record.get("page")
        if page_number is None:
            raise ValueError("each page record must include a page number")
        text = str(record.get("text") or "").strip()
        if not text:
            continue
        for paragraph in re.split(r"\n\s*\n", text):
            lines = paragraph.splitlines()
            # Recognize standalone headings, including headings followed by content
            # on the same line (e.g. "Attendance: Students must...").
            for line in lines:
                stripped = line.strip()
                match = _heading(stripped)
                if match:
                    current_section = match
                    continue
                unlisted_heading = _likely_unlisted_heading(stripped)
                if unlisted_heading:
                    current_section = unlisted_heading
                    continue
                inline = re.match(r"^([^:]{2,60}):\s+(.+)$", stripped)
                inline_heading = _heading(inline.group(1)) if inline else None
                if inline_heading:
                    current_section = inline_heading
                    blocks.append((current_section, inline.group(2).strip(), int(page_number)))
                else:
                    blocks.append((current_section, stripped, int(page_number)))

    # Pack neighboring paragraphs of the same section up to the size limit.
    grouped: list[dict[str, object]] = []
    for section, paragraph, page in blocks:
        if not paragraph:
            continue
        pieces = _split_long(paragraph, chunk_size, overlap)
        for piece in pieces:
            if grouped and grouped[-1]["section"] == section:
                combined = str(grouped[-1]["text"]) + "\n\n" + piece
                if len(combined) <= chunk_size:
                    grouped[-1]["text"] = combined
                    grouped[-1]["pages"].append(page)
                    continue
            grouped.append({"section": section, "text": piece, "pages": [page]})

    chunks = []
    for index, item in enumerate(grouped, start=1):
        unique_pages = list(dict.fromkeys(item["pages"]))
        chunks.append({
            "chunk_id": f"chunk-{index:04d}",
            "text": item["text"],
            "section": item["section"],
            "pages": unique_pages,
        })
    return chunks
