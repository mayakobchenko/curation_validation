from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
import io

from ..auth import get_current_user
from ..models import ValidationRun, new_validation_run
from .. import storage, checks, kg_client, export

router = APIRouter(prefix="/api/validations", tags=["validations"])


@router.get("")
async def list_runs(user=Depends(get_current_user)):
    return [r.model_dump() for r in storage.list_all()]


@router.post("")
async def start_run(request: Request, user=Depends(get_current_user)):
    """
    Starts a new validation run for a given DatasetVersion UUID: pulls the
    live KG bundle (replacing the "open 5 tabs" step), runs the mechanical
    checks to pre-fill what can be safely pre-filled, and saves a draft.
    """
    body = await request.json()
    dsv_uuid = body.get("dataset_version_uuid", "").strip()
    if not dsv_uuid:
        raise HTTPException(status_code=400, detail="dataset_version_uuid is required")

    run = new_validation_run(dsv_uuid)
    run.dataset_info.primary_curator_name = body.get("primary_curator_name", "")
    run.dataset_info.dataset_title = body.get("dataset_title", "")
    run.dataset_info.gitlab_issue_url = body.get("gitlab_issue_url", "")

    try:
        run.kg_snapshot = await kg_client.pull_dataset_version_bundle(
            dsv_uuid, user["kg_access_token"]
        )
    except kg_client.KGError as exc:
        raise HTTPException(status_code=422, detail=f"Could not pull KG data: {exc}")

    await checks.run_mechanical_checks(run)

    storage.create(run, created_by=user.get("email") or user.get("name") or "unknown")
    return run.model_dump()


@router.get("/{run_id}")
async def get_run(run_id: str, user=Depends(get_current_user)):
    try:
        return storage.load(run_id).model_dump()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Validation run not found")


@router.put("/{run_id}")
async def update_run(run_id: str, request: Request, user=Depends(get_current_user)):
    """Saves the secondary curator's edits (answers/comments) to the draft."""
    existing = storage.load(run_id)
    body = await request.json()
    updated = ValidationRun.model_validate({**existing.model_dump(), **body, "id": run_id})
    storage.save(updated)
    return updated.model_dump()


@router.post("/{run_id}/refresh-checks")
async def refresh_checks(run_id: str, user=Depends(get_current_user)):
    """Re-pulls the KG snapshot and re-runs mechanical checks without
    touching the curator's own answers/comments — useful if the primary
    curator fixes something in the KG mid-review."""
    run = storage.load(run_id)
    try:
        run.kg_snapshot = await kg_client.pull_dataset_version_bundle(
            run.dataset_info.dataset_version_uuid, user["kg_access_token"]
        )
    except kg_client.KGError as exc:
        raise HTTPException(status_code=422, detail=f"Could not pull KG data: {exc}")
    await checks.run_mechanical_checks(run)
    storage.save(run)
    return run.model_dump()


@router.post("/{run_id}/submit")
async def submit_run(run_id: str, user=Depends(get_current_user)):
    run = storage.load(run_id)
    run.status = "submitted"
    storage.save(run)
    return run.model_dump()
