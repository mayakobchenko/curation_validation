"""
Mechanical (non-judgement) checks that can be run automatically against a
KG snapshot, to pre-fill as much of the Table 5 checklist as is safe to
pre-fill. Anything that requires reading prose (the Data Descriptor
content, Table 3) is deliberately left untouched here — those stay
"PENDING" for the secondary curator.

Each check returns (CheckAnswer, note). A check that can't run at all
(missing field to even test) returns ("NA", "...") rather than guessing.
"""
from __future__ import annotations
from typing import Optional
import httpx

from .models import CheckItem

REQUIRED_DS_DSV_FIELDS = {
    "Full name": "fullName",
    "Description": "description",
    "Custodian": "custodian",
    "Authors": "author",
    "Version identifier": "versionIdentifier",
    "Version innovation": "versionInnovation",
    "DOI": "doi",
    "How to cite": "howToCite",
    "Accessibility": "accessibility",
    "Licence": "license",
    "Ethics assessment": "ethicsAssessment",
    "Data type": "dataType",
    "Experimental approach": "experimentalApproach",
    "Technique": "technique",
    "Study target": "studyTarget",
    "Keywords": "keyword",
}

REQUIRED_SUBJECT_FIELDS = {
    "Internal identifier": "internalIdentifier",
    "Age": "age",
    "Age category": "ageCategory",
    "Sex": "biologicalSex",
    "Strain": "strain",
    "Attribute": "attribute",
}

REQUIRED_TISSUE_FIELDS = {
    "Internal identifier": "internalIdentifier",
    "Type": "type",
    "Strain": "strain",
    "Sex": "biologicalSex",
    "Origin": "origin",
    "Anatomical location": "anatomicalLocation",
    "Descended from": "descendedFrom",
}


def _has_value(instance: dict, prop: str) -> bool:
    val = instance.get(prop)
    if val is None:
        return False
    if isinstance(val, (list, dict)) and len(val) == 0:
        return False
    if isinstance(val, str) and val.strip() == "":
        return False
    return True


def check_required_field_presence(instance: dict, field_map: dict[str, str]) -> dict[str, tuple[str, str]]:
    """Returns {label: (answer, note)} for every field in field_map."""
    results = {}
    for label, prop in field_map.items():
        present = _has_value(instance, prop)
        results[label] = (
            ("YES" if present else "NO"),
            "" if present else f"'{prop}' is missing or empty on the KG instance",
        )
    return results


def check_ds_dsv_consistency(dataset: Optional[dict], dsv: dict, field_map: dict[str, str]) -> dict[str, tuple[str, str]]:
    """
    Implements the form's explicit inheritance rule: "If the information
    on the DS is the same as the information on the DSV, the information
    should be entered on the DS card. Information may change with a new
    version - this should be reflected on the DSV."
    i.e. flag fields that are IDENTICAL on both DS and DSV as a finding
    (should probably live only on the DS), and leave genuinely-different
    fields alone (expected when a version changed something).
    """
    results = {}
    if not dataset:
        return results
    for label, prop in field_map.items():
        ds_val = dataset.get(prop)
        dsv_val = dsv.get(prop)
        if ds_val is None or dsv_val is None:
            continue
        if ds_val == dsv_val:
            results[label] = (
                "NO",
                f"'{prop}' is duplicated identically on DS and DSV — per the inheritance "
                f"rule this should live on the DS card only",
            )
        else:
            results[label] = ("YES", "")
    return results


async def resolve_doi(doi: str, client: httpx.AsyncClient) -> tuple[str, str]:
    if not doi:
        return "NA", "no DOI present to check"
    url = doi if doi.startswith("http") else f"https://doi.org/{doi}"
    try:
        resp = await client.head(url, follow_redirects=True, timeout=15)
        if resp.status_code < 400:
            return "YES", f"resolves ({resp.status_code})"
        return "NO", f"DOI did not resolve cleanly ({resp.status_code})"
    except httpx.HTTPError as exc:
        return "NO", f"DOI lookup failed: {exc}"


async def resolve_url(url: str, client: httpx.AsyncClient) -> tuple[str, str]:
    if not url:
        return "NA", "no URL present to check"
    try:
        resp = await client.head(url, follow_redirects=True, timeout=15)
        if resp.status_code < 400:
            return "YES", f"resolves ({resp.status_code})"
        return "NO", f"URL returned {resp.status_code}"
    except httpx.HTTPError as exc:
        return "NO", f"URL lookup failed: {exc}"


def _apply(items: list[CheckItem], results: dict[str, tuple[str, str]]) -> None:
    by_label = {i.label: i for i in items}
    for label, (answer, note) in results.items():
        item = by_label.get(label)
        if item:
            item.auto_result = answer
            item.auto_note = note


async def run_mechanical_checks(run) -> None:
    """Mutates `run` (a ValidationRun) in place, filling auto_result/auto_note
    wherever a mechanical check applies. Leaves `answer` (the curator's own
    sign-off) untouched — the auto result is a suggestion, not a verdict."""
    snapshot = run.kg_snapshot or {}
    dsv = snapshot.get("datasetVersion") or {}
    dataset = snapshot.get("dataset")

    _apply(
        run.kge_metadata_checks.dataset_and_version,
        check_required_field_presence(dsv, REQUIRED_DS_DSV_FIELDS),
    )
    _apply(
        run.kge_metadata_checks.dataset_and_version,
        check_ds_dsv_consistency(dataset, dsv, REQUIRED_DS_DSV_FIELDS),
    )

    for subj in snapshot.get("subjects", []) or []:
        _apply(run.kge_metadata_checks.subjects, check_required_field_presence(subj, REQUIRED_SUBJECT_FIELDS))
        break  # one representative pass; UI can drill into per-subject detail

    for sample in snapshot.get("tissueSamples", []) or []:
        _apply(run.kge_metadata_checks.tissue_samples, check_required_field_presence(sample, REQUIRED_TISSUE_FIELDS))
        break

    async with httpx.AsyncClient() as client:
        doi_answer, doi_note = await resolve_doi(dsv.get("doi", ""), client)
        howtocite_item = next(
            (i for i in run.kge_metadata_checks.dataset_and_version if i.label == "DOI"), None
        )
        if howtocite_item:
            howtocite_item.auto_result = doi_answer
            howtocite_item.auto_note = doi_note
