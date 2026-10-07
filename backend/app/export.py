"""
Renders a completed ValidationRun as a filled Word (.docx) document,
table-for-table matching curation-validation_<UUID>.md, so the output is
a drop-in replacement for what curators currently produce by hand.
PDF export is offered as a conversion of the same .docx (via libreoffice
if present on the deployment image; falls back to docx-only otherwise).
"""
import io
import subprocess
import tempfile
import os
from docx import Document
from docx.shared import Pt

from .models import ValidationRun, CheckItem


def _add_heading(doc: Document, text: str, level: int = 1):
    doc.add_heading(text, level=level)


def _add_check_table(doc: Document, items: list[CheckItem]):
    table = doc.add_table(rows=1, cols=4)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "Item"
    hdr[1].text = "Answer"
    hdr[2].text = "Auto-check"
    hdr[3].text = "Comment"
    for item in items:
        row = table.add_row().cells
        row[0].text = item.label
        row[1].text = item.answer
        row[2].text = f"{item.auto_result or '-'}" + (f" ({item.auto_note})" if item.auto_note else "")
        row[3].text = item.comment


def render_docx(run: ValidationRun) -> bytes:
    doc = Document()
    doc.add_heading(f"Curation Validation — {run.dataset_info.dataset_title or run.id}", level=0)

    _add_heading(doc, "1. Dataset information")
    p = doc.add_paragraph()
    p.add_run(f"Primary curator: ").bold = True
    p.add_run(run.dataset_info.primary_curator_name)
    p = doc.add_paragraph()
    p.add_run("Dataset title: ").bold = True
    p.add_run(run.dataset_info.dataset_title)
    p = doc.add_paragraph()
    p.add_run("GitLab issue: ").bold = True
    p.add_run(run.dataset_info.gitlab_issue_url)
    p = doc.add_paragraph()
    p.add_run("Dataset version UUID: ").bold = True
    p.add_run(run.dataset_info.dataset_version_uuid)

    _add_heading(doc, "2. Secondary curator")
    p = doc.add_paragraph()
    p.add_run("Secondary curator: ").bold = True
    p.add_run(run.secondary_curator_info.secondary_curator_name)
    p = doc.add_paragraph()
    p.add_run("Validation date: ").bold = True
    p.add_run(run.secondary_curator_info.validation_date)

    _add_heading(doc, "3. Data Descriptor checks")
    _add_check_table(doc, run.data_descriptor_checks.items)

    _add_heading(doc, "4. Dataset structure & file storage checks")
    _add_check_table(doc, run.structure_checks.items)

    _add_heading(doc, "5. KGE metadata checklist")
    _add_heading(doc, "5a. Dataset / Dataset version", level=2)
    _add_check_table(doc, run.kge_metadata_checks.dataset_and_version)
    _add_heading(doc, "5b. Subject(group)(state)", level=2)
    _add_check_table(doc, run.kge_metadata_checks.subjects)
    _add_heading(doc, "5c. Tissue sample (collection)(state)", level=2)
    _add_check_table(doc, run.kge_metadata_checks.tissue_samples)
    _add_heading(doc, "5d. Project", level=2)
    _add_check_table(doc, run.kge_metadata_checks.project)

    _add_heading(doc, "6. File repository checks")
    _add_check_table(doc, run.file_repository_checks.items)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def render_pdf(run: ValidationRun) -> bytes:
    """Best-effort docx -> pdf via libreoffice (must be present on the
    container image; see Dockerfile). Raises if unavailable."""
    docx_bytes = render_docx(run)
    with tempfile.TemporaryDirectory() as tmp:
        docx_path = os.path.join(tmp, "validation.docx")
        with open(docx_path, "wb") as f:
            f.write(docx_bytes)
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmp, docx_path],
            check=True,
            timeout=60,
        )
        pdf_path = os.path.join(tmp, "validation.pdf")
        with open(pdf_path, "rb") as f:
            return f.read()
