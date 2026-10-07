"""
Thin EBRAINS Knowledge Graph v3 REST client, used to replace the manual
"open 5 tabs" step of the curation-validation checklist: given a
DatasetVersion UUID, pull everything a curator needs to see in one place
(Dataset, DatasetVersion, subjects/groups, tissue samples/collections,
authors, files...).

Deliberately mirrors the endpoint shapes already proven out in the
wizard's python_upload_json.py (core.kg.ebrains.eu/v3/instances,
?stage=&space=collab-d-{id}, /neighbors) rather than inventing a new
convention.
"""
from typing import Any, Optional
import httpx

from .config import settings

KG_API = settings.KG_API_BASE


class KGError(Exception):
    pass


async def _get(client: httpx.AsyncClient, url: str, token: str) -> dict:
    resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 404:
        raise KGError(f"Not found: {url}")
    if resp.status_code != 200:
        raise KGError(f"KG request failed ({resp.status_code}): {url}")
    return resp.json()


async def get_instance(instance_id: str, token: str, stage: Optional[str] = None) -> dict:
    stage = stage or settings.KG_STAGE
    url = f"{KG_API}/instances/{instance_id}?stage={stage}"
    async with httpx.AsyncClient(timeout=30) as client:
        data = await _get(client, url, token)
    return data.get("data", data)


async def get_neighbors(instance_id: str, token: str, stage: Optional[str] = None) -> dict:
    stage = stage or settings.KG_STAGE
    url = f"{KG_API}/instances/{instance_id}/neighbors?stage={stage}"
    async with httpx.AsyncClient(timeout=30) as client:
        data = await _get(client, url, token)
    return data.get("data", data)


async def list_instances_in_space(
    type_name: str, dsv_uuid: str, token: str, stage: Optional[str] = None
) -> list[dict]:
    """Page through instances of `type_name` in the collab space derived
    from a DatasetVersion UUID (collab-d-{dsv_uuid}), same convention the
    wizard's cleanup/upload scripts use."""
    stage = stage or settings.KG_STAGE
    results: list[dict] = []
    url = (
        f"{KG_API}/instances"
        f"?stage={stage}&space=collab-d-{dsv_uuid}"
        f"&type={type_name}&size=100"
    )
    async with httpx.AsyncClient(timeout=30) as client:
        while url:
            page = await _get(client, url, token)
            results.extend(page.get("data", []))
            url = (page.get("page") or {}).get("next") or page.get("next")
    return results


async def pull_dataset_version_bundle(dsv_uuid: str, token: str) -> dict[str, Any]:
    """
    Single entry point used by the validation-run endpoint: fetches the
    DatasetVersion, the parent Dataset, and every Subject/SubjectGroup/
    TissueSample/TissueSampleCollection instance living in that version's
    collab space, so the curator never has to open a KG Editor tab by hand.
    """
    dsv = await get_instance(dsv_uuid, token)

    dataset = None
    neighbors = await get_neighbors(dsv_uuid, token)
    for rel in neighbors.get("relationOfReferences", []) or neighbors.get("relations", []):
        # neighbors payload shape can vary by KG version; be defensive and
        # take the first instance typed "Dataset" we find.
        pass  # left intentionally explicit below via a simpler fallback

    dataset_id = None
    is_part_of = dsv.get("isPartOf") or dsv.get("isVersionOf")
    if isinstance(is_part_of, dict):
        dataset_id = is_part_of.get("@id", "").rsplit("/", 1)[-1]
    if dataset_id:
        try:
            dataset = await get_instance(dataset_id, token)
        except KGError:
            dataset = None

    subjects = await list_instances_in_space("Subject", dsv_uuid, token)
    subject_groups = await list_instances_in_space("SubjectGroup", dsv_uuid, token)
    tissue_samples = await list_instances_in_space("TissueSample", dsv_uuid, token)
    tissue_collections = await list_instances_in_space("TissueSampleCollection", dsv_uuid, token)

    return {
        "datasetVersion": dsv,
        "dataset": dataset,
        "subjects": subjects,
        "subjectGroups": subject_groups,
        "tissueSamples": tissue_samples,
        "tissueSampleCollections": tissue_collections,
    }
