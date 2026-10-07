from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import io

from ..auth import get_current_user
from .. import storage, export

router = APIRouter(prefix="/api/validations", tags=["export"])


@router.get("/{run_id}/export.docx")
async def export_docx(run_id: str, user=Depends(get_current_user)):
    try:
        run = storage.load(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Validation run not found")
    content = export.render_docx(run)
    filename = f"curation-validation_{run_id}.docx"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{run_id}/export.pdf")
async def export_pdf(run_id: str, user=Depends(get_current_user)):
    try:
        run = storage.load(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Validation run not found")
    try:
        content = export.render_pdf(run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF conversion unavailable: {exc}")
    filename = f"curation-validation_{run_id}.pdf"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
