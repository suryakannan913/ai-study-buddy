import pdfplumber


def extract_text_from_pdf(file_path: str) -> str:
    """Extract all text from a PDF file."""
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
            text += "\n"
    return text


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks by token count (approximate).
    Assumes ~1 word per 1.3 tokens, ~5 chars per word."""
    words = text.split()
    chunk_size_words = int(chunk_size / 0.77)  # rough conversion from tokens to words
    overlap_words = int(overlap / 0.77)

    chunks = []
    for i in range(0, len(words), chunk_size_words - overlap_words):
        chunk = " ".join(words[i : i + chunk_size_words])
        if chunk.strip():
            chunks.append(chunk)

    return chunks
