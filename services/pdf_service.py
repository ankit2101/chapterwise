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


def _is_noise_line(line: str) -> bool:
    """Return True for lines that are watermarks, URLs, or garbled repeated-char text."""
    import itertools
    l = line.strip()
    # URLs / download watermarks (e.g. "Downloaded from https://...")
    if re.search(r'https?://', l, re.IGNORECASE):
        return True
    if re.match(r'downloaded\s+from', l, re.IGNORECASE):
        return True
    # Garbled column-layout headings (textbook titles rendered as visual grids).
    # Check 1 — token-level: ≥60% of space-separated tokens are all-same-char
    #   e.g. "IIIII MMMMM AAAAA UUUUU PPPPP"
    tokens = l.split()
    if len(tokens) >= 3:
        all_same = sum(1 for t in tokens if len(t) >= 3 and len(set(t.upper())) == 1)
        if all_same / len(tokens) >= 0.6:
            return True
    # Check 2 — clump ratio: ≥70% of non-space chars belong to runs of ≥3 identical chars
    #   e.g. "AAAAATTTTTTTTTTEEEEERRRRR" or "RRRRROOOOOUUUUUNNNNNDDDDD"
    letters = re.sub(r'[\s?!.,\-]', '', l)
    if len(letters) >= 8:
        in_clump = sum(
            run_len for _, g in itertools.groupby(letters.upper())
            for run_len in [len(list(g))] if run_len >= 3
        )
        if in_clump / len(letters) >= 0.70:
            return True
    return False


def _looks_like_title(line: str) -> bool:
    """Return True if the line could plausibly be a chapter title (not body prose)."""
    # Titles are concise
    if len(line) > 80:
        return False
    # Body text typically has mid-sentence breaks: ". Capital" or multiple commas
    if re.search(r'\.\s+[A-Z]', line):
        return False
    if line.count(',') > 2:
        return False
    # Titles don't end with a plain period (they may end with ? or !)
    if line.endswith('.'):
        return False
    # Titles don't start with a lowercase letter (body text continuation does)
    first_char = line.lstrip()[0] if line.lstrip() else ''
    if first_char and first_char.islower():
        return False
    return True


def _name_from_filename(pdf_path: str) -> str:
    """Derive a human-readable chapter name from the PDF filename as last resort."""
    import os
    base = os.path.splitext(os.path.basename(pdf_path))[0]
    # Replace hyphens/underscores with spaces and title-case
    name = re.sub(r'[-_]+', ' ', base).strip().title()
    return name if len(name) >= 3 else ''


def extract_chapter_name(pdf_path: str) -> str:
    """
    Extract the chapter name from the first page of a PDF.

    Strategy:
    1. Skip noise lines: URLs, download watermarks, garbled repeated-char artefacts.
    2. Rejoin split words (e.g. 'C' + 'hapter' on consecutive lines).
    3. Preserve standalone numbers adjacent to a 'Chapter' keyword so 'Chapter 2'
       is not lost when the number falls on its own line.
    4. Look for 'Chapter N' patterns; use title on same line or next clean line.
    5. Fall back to the first substantial clean line on the page.
    6. Ultimate fallback: derive from the PDF filename.

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
        return _name_from_filename(pdf_path)

    raw_lines = [l.strip() for l in page_text.split('\n')]

    # ── Step 1: rejoin lines split mid-word ──────────────────────────────────
    # e.g. ['C', 'hapter'] → ['Chapter']
    joined = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if (line and len(line) == 1 and line.isalpha()
                and i + 1 < len(raw_lines)
                and raw_lines[i + 1] and raw_lines[i + 1][0].islower()):
            joined.append(line + raw_lines[i + 1])
            i += 2
        else:
            joined.append(line)
            i += 1

    # ── Step 2: build clean lines, merging chapter numbers regardless of order ─
    # Some PDFs put the chapter number BEFORE the word "Chapter" on the page,
    # e.g. raw order: ["2", "Chapter", …].  We collect all standalone numbers
    # adjacent (within 2 positions) to a "chapter" token and merge them.
    chapter_word_re = re.compile(r'\bchapter\b', re.IGNORECASE)

    # Find positions of "chapter" tokens and nearby standalone numbers in joined
    chapter_positions = {i for i, l in enumerate(joined)
                         if chapter_word_re.search(l)}
    number_positions  = {i for i, l in enumerate(joined)
                         if re.match(r'^\d+$', l)}
    # Numbers within 2 slots of a chapter keyword are chapter numbers, not page nums
    chapter_adjacent_nums = {
        ni for ni in number_positions
        if any(abs(ni - ci) <= 2 for ci in chapter_positions)
    }

    lines = []
    pending_chapter_num = None   # a chapter number seen before "Chapter"
    for idx, l in enumerate(joined):
        if not l:
            continue
        if _is_noise_line(l):
            continue
        if re.match(r'^\d+$', l):
            if idx in chapter_adjacent_nums:
                if lines and chapter_word_re.search(lines[-1]):
                    lines[-1] = lines[-1] + ' ' + l  # "Chapter" already in lines
                else:
                    pending_chapter_num = l           # store to attach when we see "Chapter"
            # else: plain page number — drop
            continue
        # Normal content line
        if chapter_word_re.search(l) and pending_chapter_num:
            l = l + ' ' + pending_chapter_num        # "Chapter" + pre-seen "2"
            pending_chapter_num = None
        lines.append(l)

    if not lines:
        return _name_from_filename(pdf_path)

    chapter_re = re.compile(r'chapter\s+\d+', re.IGNORECASE)

    # ── Step 3: look for 'Chapter N' pattern ─────────────────────────────────
    for i, line in enumerate(lines):
        if chapter_re.search(line):
            # Title on the same line after "Chapter N[:.–-]?"
            title_after = re.sub(
                r'chapter\s+\d+\s*[:\.\-–—]?\s*', '', line, flags=re.IGNORECASE
            ).strip()
            if title_after and len(title_after) > 3:
                return title_after[:200]

            # Title on the next clean non-numeric heading-like line
            for j in range(i + 1, min(i + 4, len(lines))):
                next_line = lines[j].strip()
                if (next_line and 4 < len(next_line)
                        and not re.match(r'^\d+$', next_line)
                        and _looks_like_title(next_line)):
                    return next_line[:200]

            # No clean title found — derive from filename, else return "Chapter N"
            fname = _name_from_filename(pdf_path)
            return fname if fname else line[:200]

    # ── Step 4: fallback — first substantial clean line that looks like a title ─
    for line in lines:
        if 5 <= len(line) <= 200 and _looks_like_title(line):
            return line

    # ── Step 5: derive from filename ─────────────────────────────────────────
    return _name_from_filename(pdf_path)
