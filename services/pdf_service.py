import subprocess
import shutil
import pdfplumber
import pypdf
import re

# Resolve pdftotext binary path once at import time (handles macOS Homebrew paths)
_PDFTOTEXT = shutil.which('pdftotext') or _PDFTOTEXT


def extract_text(pdf_path: str, max_chars: int = 100_000) -> str:
    """
    Extract text from a PDF.  Three strategies, fastest first:
      1. pdftotext (poppler C binary) — handles complex/large PDFs in seconds
      2. pypdf — pure-Python fallback, good for standard PDFs
      3. pdfplumber — last resort, slowest but broadest format support
    Stops once max_chars of raw text have been collected.
    Raises ValueError if all strategies fail.
    """
    # --- Strategy 1: pdftotext (fastest) ---
    try:
        result = subprocess.run(
            [_PDFTOTEXT, '-layout', '-enc', 'UTF-8', pdf_path, '-'],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return _clean_text(result.stdout[:max_chars])
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # --- Strategy 2: pypdf ---
    try:
        full_text = []
        total_chars = 0
        with open(pdf_path, 'rb') as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text() or ''
                if page_text:
                    full_text.append(page_text)
                    total_chars += len(page_text)
                    if total_chars >= max_chars:
                        break
        if full_text:
            return _clean_text('\n'.join(full_text))
    except Exception:
        pass

    # --- Strategy 3: pdfplumber (last resort) ---
    try:
        full_text = []
        total_chars = 0
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                page.flush_cache()
                if page_text:
                    full_text.append(page_text)
                    total_chars += len(page_text)
                    if total_chars >= max_chars:
                        break
        return _clean_text('\n'.join(full_text))
    except Exception as e:
        raise ValueError(f"PDF extraction failed: {str(e)}")


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
    Uses pdftotext for the first page (fastest), falls back to pdfplumber.
    """
    page_text = ''

    # --- Try pdftotext first page ---
    try:
        result = subprocess.run(
            [_PDFTOTEXT, '-f', '1', '-l', '1', '-enc', 'UTF-8', pdf_path, '-'],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            page_text = result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass

    # --- Fallback: pdfplumber first page ---
    if not page_text.strip():
        try:
            with pdfplumber.open(pdf_path) as pdf:
                if not pdf.pages:
                    return ''
                page_text = pdf.pages[0].extract_text() or ''
        except Exception:
            return ''

    if not page_text.strip():
        return ''

    lines = [l.strip() for l in page_text.split('\n')]
    # Remove empty lines and standalone page numbers
    lines = [l for l in lines if l and not re.match(r'^\d+$', l)]
    if not lines:
        return ''

    chapter_re = re.compile(r'chapter\s*\d+', re.IGNORECASE)

    for i, line in enumerate(lines):
        # Normalise spaces so "C hapter 1" → "Chapter 1"
        normalised = re.sub(r'\s+', ' ', line)
        if chapter_re.search(normalised):
            # Title follows on the same line after "Chapter N[:.–-]?"
            title_after = re.sub(
                r'chapter\s*\d+\s*[:\.\-–—]?\s*', '', normalised, flags=re.IGNORECASE
            ).strip()
            if title_after and len(title_after) > 3:
                return title_after[:200]

            # Title is on the next line
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and len(next_line) > 3 and not re.match(r'^\d+$', next_line):
                    return next_line[:200]

            # Whole line is the best we have (e.g. "Chapter 1")
            return normalised[:200]

    # Fallback: first substantial line (likely the heading/title)
    for line in lines:
        if 5 <= len(line) <= 200:
            return line

    return ''
