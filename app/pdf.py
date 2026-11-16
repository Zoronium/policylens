"""Turn an upload into a list of page texts. Page N of the list is page N+1 in citations."""

import re

import pymupdf

# Pasted text and samples mark pages with a line like "--- Page 2 ---" (or a form feed).
_PAGE_MARK = re.compile(r"^\s*-{2,}\s*page\s+\d+\s*-{2,}\s*$|\f", re.IGNORECASE | re.MULTILINE)


def split_pages(text: str) -> list[str]:
    pages = [p.strip() for p in _PAGE_MARK.split(text)]
    pages = [p for p in pages if p]
    return pages or [text.strip()]


def pdf_pages(data: bytes) -> list[str]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        pages = [page.get_text().strip() for page in doc]
    return pages
