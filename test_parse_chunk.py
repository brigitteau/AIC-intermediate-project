"""Lightweight parser and chunker tests; no external services required."""

import io
import unittest
from unittest.mock import patch

import chunk
import parse


class _Page:
    def __init__(self, text):
        self.text = text

    def extract_text(self):
        return self.text


class _PDF:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ParseTests(unittest.TestCase):
    def test_page_records_skip_empty_and_keep_original_page_numbers(self):
        pdf = _PDF([_Page("  Intro text  "), _Page(" \n "), _Page("Final exam")])
        with patch.object(parse.pdfplumber, "open", return_value=pdf):
            self.assertEqual(parse.parse_pdf(io.BytesIO(b"pdf")), [
                {"page": 1, "text": "Intro text"},
                {"page": 3, "text": "Final exam"},
            ])

    def test_invalid_source_has_useful_error(self):
        with self.assertRaisesRegex(ValueError, "source must be"):
            parse.parse_pdf(123)

    def test_malformed_pdf_has_extraction_error(self):
        with self.assertRaisesRegex(RuntimeError, "Failed to extract text"):
            parse.parse_pdf(io.BytesIO(b"not a pdf"))


class ChunkTests(unittest.TestCase):
    def test_headings_sections_and_page_metadata(self):
        result = chunk.chunk_text([
            {"page": 1, "text": "ATTENDANCE POLICY:\nStudents should attend.\n\nLate Work: Work loses ten points."},
            {"page": 2, "text": "Academic Integrity\nDo your own work."},
        ], chunk_size=300)
        self.assertEqual([item["section"] for item in result],
                         ["Attendance", "Late Work", "Academic Integrity"])
        self.assertEqual([item["pages"] for item in result], [[1], [1], [2]])
        self.assertIn("Students should attend", result[0]["text"])
        self.assertTrue(all(item["chunk_id"] for item in result))

    def test_heading_variations_and_unknown_heading_boundary(self):
        result = chunk.chunk_text([{"page": 1, "text": (
            "Criteria for Grading.\nScores use the scale below.\n\n"
            "Topical Outline\nTopics include writing and revision.\n\n"
            "Accessibility Resources\nContact the instructor if materials are inaccessible."
        )}], chunk_size=300)
        self.assertEqual([item["section"] for item in result],
                         ["Grading", "Course Content", "Accessibility Resources"])
        self.assertIn("Scores use the scale below", result[0]["text"])
        self.assertIn("Topics include", result[1]["text"])

    def test_inline_heading_keeps_its_content(self):
        result = chunk.chunk_text([{"page": 1, "text": (
            "In-class Writing: Diagnostic Writing Assignment"
        )}])
        self.assertEqual(len(result), 1)
        self.assertIn("Diagnostic Writing Assignment", result[0]["text"])

    def test_long_section_splits_and_preserves_all_words(self):
        text = " ".join(f"word{i}" for i in range(120))
        result = chunk.chunk_text([{"page": 4, "text": f"Grading:\n{text}"}],
                                  chunk_size=100, overlap=10)
        self.assertGreater(len(result), 1)
        self.assertTrue(all(len(item["text"]) <= 100 for item in result))
        self.assertTrue(all(item["section"] == "Grading" for item in result))
        for i in range(120):
            self.assertIn(f"word{i}", " ".join(item["text"] for item in result))
        self.assertTrue(all(item["pages"] == [4] for item in result))

    def test_unrecognized_heading_falls_back_to_paragraph_chunking(self):
        result = chunk.chunk_text([{"page": 7, "text": "A unique topic\n\n" + "x" * 65}],
                                  chunk_size=30, overlap=5)
        self.assertTrue(result)
        self.assertTrue(all(item["section"] is None for item in result))
        self.assertTrue(all("A unique topic" in item["text"] or len(item["text"]) <= 30
                            for item in result))

    def test_empty_text_and_bad_chunk_size(self):
        self.assertEqual(chunk.chunk_text([{"page": 1, "text": "  "}]), [])
        with self.assertRaises(ValueError):
            chunk.chunk_text([], chunk_size=0)


if __name__ == "__main__":
    unittest.main()
