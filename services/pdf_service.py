import pdfplumber
import re


def extract_text(pdf_path: str) -> str:
    """
    Extract all text from a PDF using pdfplumber.
    Returns cleaned text string.
    Raises ValueError on failure.
    """
    full_text = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    full_text.append(page_text)
    except Exception as e:
        raise ValueError(f"PDF extraction failed: {str(e)}")

    if not full_text:
        return ''

    raw = '\n'.join(full_text)
    return _clean_text(raw)


def _clean_text(text: str) -> str:
    lines = text.split('\n')
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Skip lines that are only digits (page numbers)
        if stripped and not re.match(r'^\d+$', stripped):
            cleaned.append(stripped)

    result = '\n'.join(cleaned)
    # Collapse multiple spaces/tabs into single space
    result = re.sub(r'[ \t]{2,}', ' ', result)
    return result.strip()


def is_content_sufficient(text: str, min_chars: int = 300) -> bool:
    return len(text.strip()) >= min_chars


def extract_chapter_name(pdf_path: str) -> str:
    """
    Extract the chapter name from the first page of a PDF.

    Strategy:
    1. Look for 'Chapter N' patterns (e.g. 'Chapter 1 – The French Revolution',
       or 'Chapter 1' on one line and the title on the next).
    2. Fall back to the first substantial non-trivial line on the page.

    Returns empty string if nothing useful is found.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return ''
            page_text = pdf.pages[0].extract_text()
            if not page_text:
                return ''
    except Exception:
        return ''

    lines = [l.strip() for l in page_text.split('\n')]
    # Remove empty lines and standalone page numbers
    lines = [l for l in lines if l and not re.match(r'^\d+$', l)]
    if not lines:
        return ''

    chapter_re = re.compile(r'chapter\s+\d+', re.IGNORECASE)

    for i, line in enumerate(lines):
        if chapter_re.search(line):
            # Title follows on the same line after "Chapter N[:.–-]?"
            title_after = re.sub(
                r'chapter\s+\d+\s*[:\.\-–—]?\s*', '', line, flags=re.IGNORECASE
            ).strip()
            if title_after and len(title_after) > 3:
                return title_after[:200]

            # Title is on the next line
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and len(next_line) > 3 and not re.match(r'^\d+$', next_line):
                    return next_line[:200]

            # Whole line is the best we have (e.g. "Chapter 1")
            return line[:200]

    # Fallback: first substantial line (likely the heading/title)
    for line in lines:
        if 5 <= len(line) <= 200:
            return line

    return ''
