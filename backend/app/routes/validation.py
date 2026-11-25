import asyncio
import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Request, HTTPException

from ..auth import get_current_user
from ..models import ValidationRun, new_validation_run
from .. import storage, checks, kg_client, export, drive_client, bucket_client, descriptor, compare, llm, llm_review

router = APIRouter(prefix="/api/validations", tags=["validations"])
info_router = APIRouter(prefix="/api", tags=["validations"])

UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
# what the secondary curator edits; everything else on a run is written by the server
EDITABLE = ("dataset_info", "secondary_curator_info", "data_descriptor_checks", "structure_checks",
            "kge_metadata_checks", "file_repository_checks")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _first(value):
    return value[0] if isinstance(value, list) and value else value


async def _fetch_drive(run: ValidationRun, token: str) -> None:
    result = await drive_client.fetch_drive_sources(token, run.dataset_info.dataset_version_uuid)
    status = {"ok": result["error"] is None, "error": result["error"], "code": result["code"], "fetched_at": _now(),
              "library": result["library"], "files": result["files"],
              "descriptor": (result["descriptor"] or {}).get("name"), "draft": bool(result["draft"])}
    run.descriptor, run.draft = None, None
    if result["descriptor"]:
        try:
            text = await asyncio.to_thread(descriptor.descriptor_text, result["descriptor"]["bytes"], result["descriptor"]["name"])
            run.descriptor = {"name": result["descriptor"]["name"], "text": text}
        except Exception as exc:  # a file Word cannot be read from must not stop the validation
            status["descriptor_error"] = f"The data descriptor {result['descriptor']['name']} could not be read: {exc}"
    if result["draft"]:
        parsed, err = compare.parse_draft(result["draft"]["text"])
        run.draft = parsed
        if err:
            status["draft_error"] = err
    run.sources["drive"] = status


async def _fetch_bucket(run: ValidationRun, token: str) -> None:
    result = await bucket_client.fetch_bucket(token, run.dataset_info.dataset_version_uuid)
    run.bucket = result
    run.sources["bucket"] = {"ok": result["error"] is None, "error": result["error"], "code": result["code"], "fetched_at": _now(),
                             "bucket": result["bucket"], "files": (result["summary"] or {}).get("files")}


async def _fetch_kg(run: ValidationRun, token: str) -> None:
    try:
        run.kg_snapshot = await kg_client.pull_dataset_version_bundle(run.dataset_info.dataset_version_uuid, token)
    except kg_client.KGError as exc:
        run.sources["kg"] = {"ok": False, "error": str(exc), "fetched_at": _now()}
        raise HTTPException(status_code=exc.status if exc.status in (401, 403, 404) else 422, detail=f"Could not pull KG data: {exc}")
    snap = run.kg_snapshot
    dsv, ds = snap["datasetVersion"], snap.get("dataset") or {}
    info = run.dataset_info
    info.dataset_title = dsv.get("fullName") or ds.get("fullName") or info.dataset_title
    info.dataset_uuid = ds.get("id", "")
    info.version_identifier = str(dsv.get("versionIdentifier") or "")
    run.sources["kg"] = {"ok": True, "error": None, "fetched_at": _now(), "space": snap["space"],
                         "subjects": len(snap["subjects"]), "subject_groups": len(snap["subjectGroups"]),
                         "tissue_samples": len(snap["tissueSamples"]), "tissue_sample_collections": len(snap["tissueSampleCollections"]),
                         "people": len(snap["people"])}


def _compare(run: ValidationRun) -> None:
    snap = run.kg_snapshot or {}
    result = {"draft": None, "bucket": []}
    if run.draft:
        result["draft"] = compare.compare_draft_with_kg(run.draft, snap)
    result["bucket"] = compare.bucket_vs_metadata((run.bucket or {}).get("summary"), snap, run.draft)
    run.comparison = result


async def refresh_all(run: ValidationRun, token: str) -> None:
    """Pulls the KG, the Collab drive (data descriptor, metadata draft) and the bucket, compares them and runs the checks."""
    await _fetch_kg(run, token)
    await asyncio.gather(_fetch_drive(run, token), _fetch_bucket(run, token))
    _compare(run)
    await checks.run_mechanical_checks(run)


@router.get("")
async def list_runs(user=Depends(get_current_user)):
    return [_summary(r) for r in storage.list_all()]


def _summary(run: ValidationRun) -> dict:
    """A run for the dashboard list: without the fetched documents."""
    return run.model_dump(exclude={"kg_snapshot", "descriptor", "draft", "bucket", "comparison", "llm_review"})


@router.post("")
async def start_run(request: Request, user=Depends(get_current_user)):
    """
    Starts a validation for a DatasetVersion UUID (and the GitLab issue of the curation). Everything else is fetched:
    the title, version, dataset, persons, ORCIDs, subjects, groups, tissue samples and collections from the KG; the data
    descriptor and the metadata draft from the Collab drive; the file names of the bucket. The mechanical checks then
    pre-fill what can safely be pre-filled, and the draft is saved.
    """
    body = await request.json()
    dsv_uuid = str(body.get("dataset_version_uuid", "")).strip().lower()
    if not UUID.match(dsv_uuid):
        raise HTTPException(status_code=400, detail="dataset_version_uuid must be a dataset version UUID")

    run = new_validation_run(dsv_uuid)
    run.dataset_info.gitlab_issue_url = str(body.get("gitlab_issue_url", "")).strip()
    run.dataset_info.primary_curator_name = str(body.get("primary_curator_name", "")).strip()
    run.secondary_curator_info.secondary_curator_name = user.get("name") or ""
    run.secondary_curator_info.validation_date = date.today().isoformat()

    await refresh_all(run, user["kg_access_token"])
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
    """Saves the secondary curator's edits (answers/comments). Only the fields a curator edits are taken from the
    request; fetched data and AI suggestions are never overwritten by a copy held in the browser."""
    try:
        existing = storage.load(run_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Validation run not found")
    body = await request.json()
    merged = existing.model_dump()
    for key in EDITABLE:
        if key in body:
            merged[key] = body[key]
    updated = ValidationRun.model_validate({**merged, "id": run_id})
    # the automatic suggestions belong to the server too
    for group in ("data_descriptor_checks", "structure_checks", "file_repository_checks"):
        _keep_auto(getattr(existing, group).items, getattr(updated, group).items)
    for group in ("dataset_and_version", "subjects", "tissue_samples", "project"):
        _keep_auto(getattr(existing.kge_metadata_checks, group), getattr(updated.kge_metadata_checks, group))
    storage.save(updated)
    return updated.model_dump()


def _keep_auto(old, new) -> None:
    by_label = {i.label: i for i in old}
    for item in new:
        src = by_label.get(item.label)
        if src:
            item.auto_result, item.auto_note = src.auto_result, src.auto_note


@router.post("/{run_id}/refresh-sources")
@router.post("/{run_id}/refresh-checks")
async def refresh_sources(run_id: str, user=Depends(get_current_user)):
    """Fetches the KG, the Collab drive and the bucket again and re-runs the checks, without touching the curator's
    own answers and comments: useful when the primary curator fixes something mid-review."""
    run = storage.load(run_id)
    await refresh_all(run, user["kg_access_token"])
    storage.save(run)
    return run.model_dump()


@router.post("/{run_id}/llm-review")
async def run_llm_review(run_id: str, user=Depends(get_current_user)):
    """Asks the language model to read the data descriptor and check it against the KG metadata and the bucket. The
    result is a set of suggestions; the curator's answers are not changed."""
    run = storage.load(run_id)
    if not llm.available():
        raise HTTPException(status_code=503, detail="No language model is configured for this deployment.")
    try:
        run.llm_review = await llm_review.review((run.descriptor or {}).get("text", ""), run.kg_snapshot or {},
                                                 run.comparison and run.comparison.get("draft"), run.bucket)
    except llm.LLMError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    run.llm_review["requested_by"] = user.get("email") or user.get("name") or ""
    checks.apply_source_checks(run)
    storage.save(run)
    return run.model_dump()


@router.post("/{run_id}/submit")
async def submit_run(run_id: str, user=Depends(get_current_user)):
    run = storage.load(run_id)
    run.status = "submitted"
    storage.save(run)
    return run.model_dump()


@info_router.get("/llm")
async def llm_info(user=Depends(get_current_user)):
    return llm.info()
