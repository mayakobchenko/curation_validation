"""
Mechanical (non-judgement) checks run against the KG snapshot, the data descriptor, the metadata draft and the bucket
listing, to pre-fill what can safely be pre-filled. Each result is a SUGGESTION shown next to the item (auto_result and
auto_note); the secondary curator's own answer is never touched. Prose judgement (does the descriptor match the
dataset?) is left to the curator, or to the language-model review, which also only suggests.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

import httpx

from .descriptor import placeholders
from .models import CheckItem

# label -> (properties on the dataset version, also looked for on the parent dataset, only suggest NA when empty)
DS_DSV_FIELDS: dict[str, tuple[str, bool, bool]] = {
    "Full name": ("fullName", True, False),
    "Description": ("description", True, False),
    "Custodian": ("custodian", True, False),
    "Authors": ("author", True, False),
    "Version identifier": ("versionIdentifier", False, False),
    "Version innovation": ("versionInnovation", False, False),
    "File repository": ("repository", False, False),
    "DOI": ("digitalIdentifier", False, True),
    "How to cite": ("howToCite", False, True),
    "Accessibility": ("accessibility", False, False),
    "Licence": ("license", False, False),
    "Full documentation": ("fullDocumentation", False, False),
    "Ethics assessment": ("ethicsAssessment", False, False),
    "Related publication": ("relatedPublication", False, True),
    "Data type": ("dataType", False, False),
    "Experimental approach": ("experimentalApproach", False, False),
    "Technique": ("technique", False, False),
    "Behavioral protocol": ("behavioralProtocol", False, True),
    "Preparation design": ("preparationDesign", False, False),
    "Study target": ("studyTarget", False, False),
    "Keywords": ("keyword", False, False),
}
INHERITED = ("Full name", "Description", "Custodian", "Authors")


def has_value(val: Any) -> bool:
    if val is None:
        return False
    if isinstance(val, (list, dict)) and len(val) == 0:
        return False
    if isinstance(val, str) and val.strip() == "":
        return False
    return True


def shown(val: Any, limit: int = 220) -> str:
    """A value of the snapshot as one short line for the note next to an item."""
    if isinstance(val, list):
        text = "; ".join(shown(v, 80) for v in val[:8]) + (f"; … (+{len(val) - 8})" if len(val) > 8 else "")
    elif isinstance(val, dict):
        if "value" in val:
            text = f"{val.get('value')} {val.get('unit', '')}".strip()
        elif "minValue" in val or "maxValue" in val:
            text = f"{val.get('minValue', '')}–{val.get('maxValue', '')} {val.get('unit', '')}".strip()
        else:
            text = ", ".join(f"{k}: {shown(v, 40)}" for k, v in val.items() if k not in ("id", "types"))
    else:
        text = str(val)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def ds_dsv_results(dsv: dict, dataset: Optional[dict]) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    for label, (prop, on_dataset, conditional) in DS_DSV_FIELDS.items():
        v_dsv = dsv.get(prop)
        v_ds = (dataset or {}).get(prop) if on_dataset else None
        val = v_dsv if has_value(v_dsv) else v_ds
        where = "" if has_value(v_dsv) or not has_value(v_ds) else " (on the dataset)"
        if has_value(val):
            out[label] = ("YES", shown(val) + where)
        elif conditional:
            out[label] = ("NA", f"'{prop}' is empty; check if it applies to this dataset")
        else:
            out[label] = ("NO", f"'{prop}' is missing or empty in the KG")
    # the form's inheritance rule: the same value on the dataset and its version belongs on the dataset card only
    if dataset:
        for label in INHERITED:
            prop = DS_DSV_FIELDS[label][0]
            if has_value(dsv.get(prop)) and dsv.get(prop) == dataset.get(prop):
                out[label] = ("NO", f"'{prop}' is identical on the dataset and its version; per the inheritance rule it should be on the dataset card only")
    return out


# --------------------------------------------------------------------------------------------- specimens -------

def _states(item: dict) -> list[dict]:
    return [s for s in item.get("states", []) if isinstance(s, dict)]


def _ident(item: dict) -> str:
    return str(item.get("lookupLabel") or item.get("internalIdentifier") or item.get("id") or "?")


Rule = Callable[[dict], bool]


def _aggregate(kind: str, items: list[dict], rule: Rule, applies: Callable[[dict], bool] = lambda i: True) -> tuple[str, str]:
    subset = [i for i in items if applies(i)]
    if not subset:
        return "NA", f"no {kind} in the collab space"
    bad = [_ident(i) for i in subset if not rule(i)]
    if not bad:
        return "YES", f"all {len(subset)} {kind} have it"
    more = f", … (+{len(bad) - 8})" if len(bad) > 8 else ""
    return "NO", f"{len(bad)} of {len(subset)} {kind} lack it: {', '.join(bad[:8])}{more}"


def subject_results(subjects: list[dict], groups: list[dict]) -> dict[str, tuple[str, str]]:
    items = subjects + groups
    is_subject = lambda i: "Subject" in i.get("types", [])  # noqa: E731
    state_has = lambda prop: (lambda i: bool(_states(i)) and all(has_value(s.get(prop)) for s in _states(i)))  # noqa: E731
    label = "subjects and groups" if groups else "subjects"
    return {
        "Internal identifier": _aggregate(label, items, lambda i: has_value(i.get("internalIdentifier") or i.get("lookupLabel"))),
        "Age": _aggregate(label, items, lambda i: bool(_states(i)) and all(
            has_value(s.get("age")) or has_value(s.get("ageCategory")) for s in _states(i)) and any(has_value(s.get("age")) for s in _states(i))),
        "Age category": _aggregate(label, items, state_has("ageCategory")),
        "Sex": _aggregate("subjects", items, lambda i: has_value(i.get("biologicalSex")), is_subject),
        "Strain": _aggregate("subjects", items, lambda i: has_value(i.get("species")), is_subject),
        "Attribute": _aggregate(label, items, state_has("attribute")),
    }


def tissue_results(samples: list[dict], collections: list[dict]) -> dict[str, tuple[str, str]]:
    items = samples + collections
    is_sample = lambda i: "TissueSample" in i.get("types", [])  # noqa: E731
    label = "tissue samples and collections" if collections else "tissue samples"
    return {
        "Internal identifier": _aggregate(label, items, lambda i: has_value(i.get("internalIdentifier") or i.get("lookupLabel"))),
        "Type": _aggregate("tissue samples", items, lambda i: has_value(i.get("type")), is_sample),
        "Strain": _aggregate("tissue samples", items, lambda i: has_value(i.get("species")), is_sample),
        "Sex": _aggregate("tissue samples", items, lambda i: has_value(i.get("biologicalSex")), is_sample),
        "Origin": _aggregate("tissue samples", items, lambda i: has_value(i.get("origin")), is_sample),
        "Descended from": _aggregate(label, items, lambda i: any(has_value(s.get("descendedFrom")) for s in _states(i))),
    }


# ----------------------------------------------------------------------------------------------- sources -------

def descriptor_results(run) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    drive = run.sources.get("drive", {})
    desc = run.descriptor
    if desc and desc.get("text"):
        out["Data Descriptor present and uploaded"] = ("YES", f"{desc['name']} found in the Collab drive")
        found = placeholders(desc["text"])
        out["Data Descriptor free of placeholder/template text"] = (
            ("NO", "template text found: " + "; ".join(found)) if found else ("YES", "no template placeholders found (typos are not checked here)"))
    elif drive.get("ok") and not drive.get("error"):
        out["Data Descriptor present and uploaded"] = ("NO", "no data-descriptor_*.doc(x) file at the top of the Collab drive")
    bucket = (run.bucket or {}).get("summary")
    if desc and desc.get("text") and bucket is not None and not bucket.get("has_descriptor_pdf"):
        out["Data Descriptor present and uploaded"] = ("NO", f"{desc['name']} is in the Collab drive, but no data descriptor PDF is in the bucket")
    review = run.llm_review or {}
    t3 = review.get("table3") or {}
    if t3.get("matches_dataset_content"):
        v = t3["matches_dataset_content"]
        out["Data Descriptor matches the dataset content"] = ({"ok": "YES", "issue": "NO"}.get(v["verdict"], "NA"), "AI suggestion: " + v.get("note", ""))
    if t3.get("proofread"):
        v = t3["proofread"]
        out["Data Descriptor is proofread (no flaws or typos)"] = ({"ok": "YES", "issue": "NO"}.get(v["verdict"], "NA"), "AI suggestion: " + v.get("note", ""))
    return out


def repository_results(run) -> dict[str, tuple[str, str]]:
    out: dict[str, tuple[str, str]] = {}
    bucket = run.bucket or {}
    s = bucket.get("summary")
    if s is None:
        return out
    out["Naming convention followed"] = ("YES", f"bucket {bucket.get('bucket')} exists with {s['files']} files")
    missing = [n for n, ok in (("data descriptor PDF", s.get("has_descriptor_pdf")), ("licence file", s.get("has_license"))) if not ok]
    out["Licence / Data Descriptor PDF uploaded"] = (("NO", "not found in the bucket: " + ", ".join(missing)) if missing
                                                     else ("YES", "data descriptor PDF and licence file are in the bucket"))
    return out


# ------------------------------------------------------------------------------------------------- runner ------

def _apply(items: list[CheckItem], results: dict[str, tuple[str, str]]) -> None:
    by_label = {i.label: i for i in items}
    for label, (answer, note) in results.items():
        item = by_label.get(label)
        if item:
            item.auto_result = answer
            item.auto_note = note


async def resolve_doi(doi: str, client: httpx.AsyncClient) -> tuple[str, str]:
    if not doi:
        return "NA", "no DOI present to check"
    url = doi if doi.startswith("http") else f"https://doi.org/{doi}"
    try:
        resp = await client.head(url, follow_redirects=True, timeout=15)
        if resp.status_code < 400:
            return "YES", f"{doi}: resolves ({resp.status_code})"
        return "NO", f"DOI did not resolve cleanly ({resp.status_code})"
    except httpx.HTTPError as exc:
        return "NO", f"DOI lookup failed: {exc}"


def apply_source_checks(run) -> None:
    """Everything that needs no network call: the KG snapshot, the descriptor, the bucket."""
    snapshot = run.kg_snapshot or {}
    dsv = snapshot.get("datasetVersion") or {}
    if dsv:
        _apply(run.kge_metadata_checks.dataset_and_version, ds_dsv_results(dsv, snapshot.get("dataset")))
        _apply(run.kge_metadata_checks.subjects, subject_results(snapshot.get("subjects", []), snapshot.get("subjectGroups", [])))
        _apply(run.kge_metadata_checks.tissue_samples, tissue_results(snapshot.get("tissueSamples", []), snapshot.get("tissueSampleCollections", [])))
    _apply(run.data_descriptor_checks.items, descriptor_results(run))
    _apply(run.file_repository_checks.items, repository_results(run))


async def run_mechanical_checks(run) -> None:
    """Fills auto_result/auto_note wherever a check applies; leaves `answer` (the curator's own sign-off) untouched."""
    apply_source_checks(run)
    dsv = (run.kg_snapshot or {}).get("datasetVersion") or {}
    doi = dsv.get("digitalIdentifier")
    doi = doi[0] if isinstance(doi, list) and doi else doi
    if isinstance(doi, str) and doi:
        async with httpx.AsyncClient() as client:
            answer, note = await resolve_doi(doi, client)
        _apply(run.kge_metadata_checks.dataset_and_version, {"DOI": (answer, note)})
