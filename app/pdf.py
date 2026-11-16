"""Turn an upload into a list of page texts. Page N of the list is page N+1 in citations."""

import re

import pymupdf

# Pasted text and samples mark pages with a line like "--- Page 2 ---", or use form feeds.
_PAGE_LINE = re.compile(
    r"^[ \t]*-{2,}[ \t]*page[ \t]+\d+[ \t]*-{2,}[ \t]*$", re.IGNORECASE | re.MULTILINE
)


def split_pages(text: str) -> list[str]:
    """Markers number the pages; a title block before "Page 1" belongs to page 1."""
    if _PAGE_LINE.search(text):
        head, *rest = _PAGE_LINE.split(text)
        rest[0] = f"{head.strip()}\n{rest[0]}"
        return [p.strip() for p in rest]
    return [p.strip() for p in text.split("\f")]


def pdf_pages(data: bytes) -> list[str]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [page.get_text().strip() for page in doc]
