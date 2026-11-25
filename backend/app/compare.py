"""
Compares the metadata draft that the Metadata Wizard saved in the Collab drive with what the Knowledge Graph holds for
the dataset version (the snapshot of kg_client). Every finding is a plain statement of what differs, so the secondary
curator can see at a glance whether the submission reached the KG complete and unchanged.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional


def norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _name(first: Any, last: Any) -> str:
    return norm(f"{first or ''} {last or ''}")


def _orcid(value: Any) -> str:
    return re.sub(r"^https?://orcid\.org/", "", str(value or "").strip(), flags=re.IGNORECASE).lower()


def parse_draft(text: str) -> tuple[Optional[dict], Optional[str]]:
    try:
        data = json.loads(text)
    except ValueError as exc:
        return None, f"The draft file is not valid JSON ({exc})."
    # the draft file is the form data itself, or {"payload": ...} / {"data": ...}
    for key in ("payload", "data", "formData"):
        if isinstance(data, dict) and isinstance(data.get(key), dict) and "dataset1" in data[key]:
            return data[key], None
    return (data, None) if isinstance(data, dict) else (None, "The draft file does not hold the form data.")


def _finding(area: str, item: str, status: str, draft: Any = "", kg: Any = "") -> dict:
    return {"area": area, "item": item, "status": status, "draft": draft, "kg": kg}


def _set_compare(area: str, draft_items: dict[str, str], kg_items: dict[str, str]) -> list[dict]:
    """draft_items / kg_items: normalised key -> display value."""
    out: list[dict] = []
    for key in sorted(set(draft_items) | set(kg_items)):
        if key in draft_items and key in kg_items:
            out.append(_finding(area, kg_items[key], "match"))
        elif key in draft_items:
            out.append(_finding(area, draft_items[key], "only_in_draft", draft_items[key], ""))
        else:
            out.append(_finding(area, kg_items[key], "only_in_kg", "", kg_items[key]))
    return out


def _text_compare(area: str, item: str, draft: Any, kg: Any) -> list[dict]:
    if not norm(draft) and not norm(kg):
        return []
    if norm(draft) == norm(kg):
        return [_finding(area, item, "match")]
    return [_finding(area, item, "differs", str(draft or ""), str(kg or ""))]


def _kg_ids(items: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for inst in items:
        for prop in ("lookupLabel", "internalIdentifier"):
            if inst.get(prop):
                out[norm(inst[prop])] = str(inst[prop])
                break
    return out


def compare_draft_with_kg(draft: dict, snapshot: dict) -> dict:
    dsv = snapshot.get("datasetVersion") or {}
    findings: list[dict] = []

    d1 = draft.get("dataset1") or {}
    findings += _text_compare("Dataset", "Title", d1.get("dataTitle"), dsv.get("fullName") or (snapshot.get("dataset") or {}).get("fullName"))
    findings += _text_compare("Dataset", "Description", d1.get("briefSummary"),
                              dsv.get("description") or (snapshot.get("dataset") or {}).get("description"))

    # persons: authors of the draft (the custodian is also an author) against the authors of the KG
    draft_people: dict[str, str] = {}
    for a in (draft.get("contribution") or {}).get("authors") or []:
        n = _name(a.get("firstName"), a.get("lastName"))
        if n:
            draft_people[n] = f"{a.get('firstName', '')} {a.get('lastName', '')}".strip()
    cust = draft.get("custodian") or {}
    if _name(cust.get("firstName"), cust.get("familyName")):
        draft_people[_name(cust.get("firstName"), cust.get("familyName"))] = f"{cust.get('firstName', '')} {cust.get('familyName', '')}".strip()
    kg_people = {norm(p["name"]): p["name"] for p in snapshot.get("people", []) if str(p.get("role", "")).startswith(("author", "custodian"))}
    findings += _set_compare("Persons", draft_people, kg_people)

    # ORCIDs of persons that both have
    kg_orcid = {norm(p["name"]): _orcid(p.get("orcid")) for p in snapshot.get("people", [])}
    for a in (draft.get("contribution") or {}).get("authors") or []:
        n = _name(a.get("firstName"), a.get("lastName"))
        if n in kg_orcid and (_orcid(a.get("orcid")) or kg_orcid[n]) and _orcid(a.get("orcid")) != kg_orcid[n]:
            findings.append(_finding("Persons", f"ORCID of {draft_people.get(n, n)}", "differs", a.get("orcid") or "", kg_orcid[n]))

    sm = draft.get("subjectMetadata") or {}
    draft_subjects = {norm(s.get("subjectID")): s.get("subjectID") for s in sm.get("subjects") or [] if s.get("subjectID")}
    for g in sm.get("subjectGroups") or []:
        for s in g.get("subjects") or []:
            if s.get("subjectID"):
                draft_subjects.setdefault(norm(s["subjectID"]), s["subjectID"])
    findings += _set_compare("Subjects", draft_subjects, _kg_ids(snapshot.get("subjects", [])))

    # number of states of the subjects that both have
    kg_by_id = {k: s for s in snapshot.get("subjects", []) for k in [norm(s.get("lookupLabel") or s.get("internalIdentifier"))]}
    for s in sm.get("subjects") or []:
        k = norm(s.get("subjectID"))
        if k in kg_by_id and len(s.get("states") or []) != len(kg_by_id[k].get("states") or []):
            findings.append(_finding("Subjects", f"Number of states of {s.get('subjectID')}", "differs",
                                     str(len(s.get("states") or [])), str(len(kg_by_id[k].get("states") or []))))

    draft_groups = {norm(g.get("name")): g.get("name") for g in sm.get("subjectGroups") or [] if g.get("name")}
    findings += _set_compare("Subject groups", draft_groups, _kg_ids(snapshot.get("subjectGroups", [])))
    draft_samples = {norm(t.get("sampleID")): t.get("sampleID") for t in sm.get("tissueSamples") or [] if t.get("sampleID")}
    for c in sm.get("tissueCollections") or []:
        for t in c.get("samples") or []:
            if t.get("sampleID"):
                draft_samples.setdefault(norm(t["sampleID"]), t["sampleID"])
    findings += _set_compare("Tissue samples", draft_samples, _kg_ids(snapshot.get("tissueSamples", [])))
    draft_coll = {norm(c.get("collectionID")): c.get("collectionID") for c in sm.get("tissueCollections") or [] if c.get("collectionID")}
    findings += _set_compare("Tissue sample collections", draft_coll, _kg_ids(snapshot.get("tissueSampleCollections", [])))

    counts = {"match": 0, "differs": 0, "only_in_draft": 0, "only_in_kg": 0}
    for f in findings:
        counts[f["status"]] += 1
    return {"counts": counts, "findings": findings}


def bucket_vs_metadata(bucket_summary: dict, snapshot: dict, draft: Optional[dict]) -> list[dict]:
    """Subject and sample identifiers that the bucket's folder and file names carry, against the KG (and the draft)."""
    if not bucket_summary:
        return []
    found = bucket_summary.get("identifiers") or {}
    in_bucket = {v: v for kind in ("sub", "subj", "subject") for v in found.get(kind, [])}
    out: list[dict] = []
    if in_bucket:
        # the KG label may carry a prefix the folders do not (FDG-PET_sub-01 against sub-01): compare the sub-xxx part
        def core(label: str) -> str:
            m = re.search(r"(?<![A-Za-z0-9])(?:sub|subj|subject)[-_]([A-Za-z0-9]+)", label, re.IGNORECASE)
            return norm("sub-" + m.group(1)) if m else norm(label)
        kg = {core(v): v for v in _kg_ids(snapshot.get("subjects", [])).values()}
        in_b = {core(v): v for v in in_bucket.values()}
        out += _set_compare("Bucket vs KG: subjects", in_b, kg)
    return out
