import io

import pdfplumber
import pypdf
from docx import Document

from app.core.exceptions import UnprocessableError, UnsupportedFileTypeError

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def _extract_pdf_text(content: bytes) -> str:
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    if text.strip():
        return text

    # pdfplumber can return empty text on some PDFs (e.g. unusual encodings);
    # fall back to pypdf before giving up.
    reader = pypdf.PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx_text(content: bytes) -> str:
    document = Document(io.BytesIO(content))
    return "\n".join(p.text for p in document.paragraphs)


def extract_text(filename: str, content: bytes) -> str:
    extension = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{extension}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if extension == ".pdf":
        text = _extract_pdf_text(content)
    elif extension == ".docx":
        text = _extract_docx_text(content)
    else:
        text = content.decode("utf-8", errors="ignore")

    if not text.strip():
        raise UnprocessableError("Could not extract any text from the uploaded file")

    return text
