"""Text of the data descriptor Word file, in reading order (paragraphs and tables), for the checks and the language model."""
from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

MAX_CHARS = 200_000

# Text a descriptor that was not finished still carries from the template.
PLACEHOLDER = re.compile(
    r"\[\s*(todo|insert|enter|add|fill|your|xx)[^\]]*\]|<\s*(insert|enter|add|your)[^>]*>|lorem ipsum|\bTODO\b|\bTBD\b|\bXXX+\b|_{4,}",
    re.IGNORECASE,
)


def _docx_text(data: bytes) -> str:
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(io.BytesIO(data))
    lines: list[str] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = Paragraph(child, doc).text.strip()
            if text:
                lines.append(text)
        elif tag == "tbl":
            for row in Table(child, doc).rows:
                cells: list[str] = []
                for cell in row.cells:
                    t = " ".join(cell.text.split())
                    if t and (not cells or cells[-1] != t):   # merged cells repeat their text
                        cells.append(t)
                if cells:
                    lines.append(" | ".join(cells))
    return "\n".join(lines)


def _convert_with_libreoffice(data: bytes, suffix: str) -> bytes:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        raise RuntimeError("The file is an old Word format (.doc) and LibreOffice is not available to read it.")
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "in" + suffix)
        with open(src, "wb") as f:
            f.write(data)
        subprocess.run([exe, "--headless", "--convert-to", "docx", "--outdir", tmp, src],
                       check=True, capture_output=True, timeout=120)
        with open(os.path.join(tmp, "in.docx"), "rb") as f:
            return f.read()


def descriptor_text(data: bytes, filename: str = "") -> str:
    """Plain text of a .docx, or of a .doc (converted with LibreOffice); a .doc that really is a .docx is read directly."""
    suffix = os.path.splitext(filename)[1].lower() or ".docx"
    if zipfile.is_zipfile(io.BytesIO(data)):
        text = _docx_text(data)
    else:
        text = _docx_text(_convert_with_libreoffice(data, suffix))
    return text[:MAX_CHARS]


def placeholders(text: str, limit: int = 8) -> list[str]:
    found: list[str] = []
    for m in PLACEHOLDER.finditer(text):
        s = m.group(0).strip()
        if s not in found:
            found.append(s)
        if len(found) >= limit:
            break
    return found
