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
