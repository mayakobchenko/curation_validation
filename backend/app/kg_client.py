"""
EBRAINS Knowledge Graph v3 reader for the curation validation.

Given a DatasetVersion UUID it pulls everything the curator used to open in the KG Editor: the dataset version, its
parent Dataset, every Subject / SubjectGroup / TissueSample / TissueSampleCollection and all their states in the
collab space "collab-d-<uuid>", and the instances they point to (persons, ORCIDs, species, strains, licences,
techniques ...), with the logged-in curator's own token.

The KG answers with full property IRIs ("https://openminds.om-i.org/props/fullName") and references as
{"@id": "https://kg.ebrains.eu/api/instances/<uuid>"}. `build_snapshot` turns that into plain dictionaries with
short property names and references replaced by readable labels, which is what the checks, the comparison with the
metadata draft and the language model read.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

import httpx

from .config import settings

PROPS = "https://openminds.om-i.org/props/"
TYPES = "https://openminds.om-i.org/types/"
KG_PREFIX = "https://kg.ebrains.eu/api/instances/"

SPECIMEN_TYPES = ["Subject", "SubjectGroup", "TissueSample", "TissueSampleCollection"]
STATE_TYPES = ["SubjectState", "SubjectGroupState", "TissueSampleState", "TissueSampleCollectionState"]

# How many instances are read to name what the metadata points to, and how many requests run at the same time.
MAX_REFERENCED = 800
CONCURRENCY = 8


class KGError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


def uuid_of(value: Any) -> str:
    """The UUID in a KG reference ({"@id": ...}), an IRI or a bare id; '' when there is none."""
    if isinstance(value, dict):
        value = value.get("@id", "")
    if not isinstance(value, str) or not value:
        return ""
    return value.rsplit("/", 1)[-1].lower()


def _types(inst: dict) -> list[str]:
    raw = inst.get("@type") or []
    return [t[len(TYPES):] if t.startswith(TYPES) else t for t in (raw if isinstance(raw, list) else [raw])]


def _refs(value: Any) -> list[str]:
    """Every reference (UUID) found anywhere inside a property value."""
    out: list[str] = []
    if isinstance(value, dict):
        if "@id" in value and value["@id"]:
            out.append(uuid_of(value))
        for k, v in value.items():
            if k != "@id":
                out.extend(_refs(v))
    elif isinstance(value, list):
        for v in value:
            out.extend(_refs(v))
    return [r for r in out if r]


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else ([value] if value else [])


def instance_refs(inst: dict) -> list[str]:
    out: list[str] = []
    for k, v in inst.items():
        if k.startswith(PROPS):
            out.extend(_refs(v))
    return out


# --------------------------------------------------------------------------------------------------- reading ----

async def _get(client: httpx.AsyncClient, url: str, token: str, tries: int = 3) -> httpx.Response:
    last = ""
    for attempt in range(1, tries + 1):
        try:
            resp = await client.get(url, headers={"Authorization": f"Bearer {token}", "accept": "application/json"})
            if resp.status_code < 500:
                return resp
            last = f"HTTP {resp.status_code}"
        except httpx.HTTPError as exc:
            last = str(exc)
        if attempt < tries:
            await asyncio.sleep(attempt)
    raise KGError(f"The Knowledge Graph could not be reached ({last}).", 502)


def _check(resp: httpx.Response, what: str) -> None:
    if resp.status_code == 401:
        raise KGError("Your EBRAINS login has ended. Please log in again.", 401)
    if resp.status_code == 403:
        raise KGError(f"Your account is not allowed to read {what} in the Knowledge Graph.", 403)
    if resp.status_code == 404:
        raise KGError(f"{what} was not found in the Knowledge Graph.", 404)
    if resp.status_code != 200:
        raise KGError(f"The Knowledge Graph answered {resp.status_code} for {what}.", 502)


async def get_instance(client: httpx.AsyncClient, instance_id: str, token: str) -> Optional[dict]:
    resp = await _get(client, f"{settings.KG_API_BASE}/instances/{instance_id}?stage={settings.KG_STAGE}", token)
    if resp.status_code == 404:
        return None
    _check(resp, instance_id)
    body = resp.json()
    return body.get("data", body)


async def list_space(client: httpx.AsyncClient, space: str, type_name: str, token: str) -> list[dict]:
    out: list[dict] = []
    for start in range(0, 100000, 100):
        url = (f"{settings.KG_API_BASE}/instances?stage={settings.KG_STAGE}&space={space}"
               f"&type={TYPES}{type_name}&size=100&from={start}")
        resp = await _get(client, url, token)
        _check(resp, f"the collab space {space}")
        page = resp.json().get("data", []) or []
        out.extend(page)
        if len(page) < 100:
            return out
    return out


async def parent_dataset(client: httpx.AsyncClient, dsv_id: str, token: str) -> Optional[dict]:
    """The Dataset that points to this dataset version (hasVersion), found through the neighbours of the version."""
    resp = await _get(client, f"{settings.KG_API_BASE}/instances/{dsv_id}/neighbors?stage={settings.KG_STAGE}", token)
    if resp.status_code != 200:
        return None
    data = resp.json().get("data", {}) or {}
    for found in data.get("inbound", []) or []:
        if f"{TYPES}Dataset" in (found.get("types") or []):
            return await get_instance(client, uuid_of(found.get("id")), token)
    return None


async def _fetch_many(client: httpx.AsyncClient, ids: list[str], known: dict[str, Optional[dict]], token: str) -> None:
    todo = [i for i in dict.fromkeys(ids) if i and i not in known][:MAX_REFERENCED]
    sem = asyncio.Semaphore(CONCURRENCY)

    async def one(i: str) -> None:
        async with sem:
            try:
                known[i] = await get_instance(client, i, token)
            except KGError as exc:
                if exc.status == 401:
                    raise
                known[i] = None

    await asyncio.gather(*(one(i) for i in todo))


# ------------------------------------------------------------------------------------------ simplifying ----

def label_of(inst: Optional[dict], fallback: str = "") -> str:
    """A readable name for an instance: a person's name, a term's name, an identifier."""
    if not inst:
        return fallback
    g = lambda name: inst.get(PROPS + name)  # noqa: E731
    types = _types(inst)
    if "Person" in types:
        name = " ".join(x for x in (g("givenName"), g("familyName")) if x)
        if name:
            return name
    for name in ("fullName", "name", "lookupLabel", "shortName", "identifier", "internalIdentifier"):
        val = g(name)
        if isinstance(val, str) and val.strip():
            return val.strip()
    syn = g("synonym")
    if isinstance(syn, list) and syn and isinstance(syn[0], str):
        return syn[0]
    return fallback


def _simplify(value: Any, labels: dict[str, str], embed: dict[str, dict]) -> Any:
    if isinstance(value, list):
        return [_simplify(v, labels, embed) for v in value]
    if isinstance(value, dict):
        if "@id" in value:
            uid = uuid_of(value)
            if uid in embed:
                return embed[uid]
            return labels.get(uid) or uid
        out: dict[str, Any] = {}
        for k, v in value.items():
            if k == "@type":
                out["types"] = [t[len(TYPES):] if isinstance(t, str) and t.startswith(TYPES) else t
                               for t in (v if isinstance(v, list) else [v])]
            elif k.startswith(PROPS):
                out[k[len(PROPS):]] = _simplify(v, labels, embed)
            elif not k.startswith("@") and not k.startswith("https://"):
                out[k] = _simplify(v, labels, embed)
        return out
    return value


def plain(inst: dict, labels: dict[str, str], embed: Optional[dict[str, dict]] = None) -> dict:
    """One KG instance as {"id", "types", <short property>: value} with references named."""
    out: dict[str, Any] = {"id": uuid_of(inst.get("@id")), "types": _types(inst)}
    for k, v in inst.items():
        if k.startswith(PROPS):
            out[k[len(PROPS):]] = _simplify(v, labels, embed or {})
    return out


def _orcid(person: Optional[dict], known: dict[str, Optional[dict]]) -> str:
    if not person:
        return ""
    for ref in _refs(person.get(PROPS + "digitalIdentifier")):
        ident = known.get(ref)
        if ident and "ORCID" in _types(ident):
            return str(ident.get(PROPS + "identifier") or "")
    return ""


def build_snapshot(dsv_id: str, dsv: dict, dataset: Optional[dict], space: dict[str, list[dict]],
                   known: dict[str, Optional[dict]]) -> dict:
    """The plain picture of one dataset version that the checks, the comparison and the language model read."""
    labels = {i: label_of(inst, i) for i, inst in known.items() if inst}
    for items in space.values():
        for inst in items:
            labels.setdefault(uuid_of(inst.get("@id")), label_of(inst, uuid_of(inst.get("@id"))))

    # states are embedded into the subject / sample / group / collection that studied them
    state_plain: dict[str, dict] = {}
    for kind in STATE_TYPES:
        for st in space.get(kind, []):
            state_plain[uuid_of(st.get("@id"))] = plain(st, labels)
    for uid, inst in known.items():
        if inst and uid not in state_plain and any(t.endswith("State") for t in _types(inst)):
            state_plain[uid] = plain(inst, labels)

    def with_states(inst: dict) -> dict:
        out = plain(inst, labels, embed=state_plain)
        out["states"] = out.pop("studiedState", []) or []
        return out

    people: list[dict] = []

    def add_people(role: str, owner: Optional[dict], prop: str) -> None:
        for ref in _refs((owner or {}).get(PROPS + prop)):
            person = known.get(ref)
            people.append({"role": role, "id": ref, "name": label_of(person, ref), "orcid": _orcid(person, known)})

    add_people("author", dataset, "author")
    add_people("author (version)", dsv, "author")
    add_people("custodian", dataset, "custodian")
    add_people("custodian (version)", dsv, "custodian")
    for contribution in _as_list(dsv.get(PROPS + "otherContribution")):
        add_people("other contribution", contribution if isinstance(contribution, dict) else None, "contributor")
    for holder in _as_list(dsv.get(PROPS + "copyright")):
        add_people("copyright holder", holder if isinstance(holder, dict) else None, "holder")

    return {
        "space": f"collab-d-{dsv_id}",
        "datasetVersion": plain(dsv, labels),
        "dataset": plain(dataset, labels) if dataset else None,
        "people": people,
        "subjects": [with_states(i) for i in space.get("Subject", [])],
        "subjectGroups": [with_states(i) for i in space.get("SubjectGroup", [])],
        "tissueSamples": [with_states(i) for i in space.get("TissueSample", [])],
        "tissueSampleCollections": [with_states(i) for i in space.get("TissueSampleCollection", [])],
    }


async def pull_dataset_version_bundle(dsv_uuid: str, token: str,
                                      transport: Optional[httpx.AsyncBaseTransport] = None) -> dict[str, Any]:
    """Everything the KG holds for this dataset version and its collab space, as a plain snapshot."""
    dsv_id = dsv_uuid.strip().lower()
    async with httpx.AsyncClient(timeout=30, transport=transport) as client:
        dsv = await get_instance(client, dsv_id, token)
        if not dsv:
            raise KGError(f"The dataset version {dsv_id} was not found in the Knowledge Graph.", 404)
        dataset = await parent_dataset(client, dsv_id, token)

        space_name = f"collab-d-{dsv_id}"
        space: dict[str, list[dict]] = {}
        for type_name in SPECIMEN_TYPES + STATE_TYPES:
            space[type_name] = await list_space(client, space_name, type_name, token)

        known: dict[str, Optional[dict]] = {}
        for items in space.values():
            for inst in items:
                known[uuid_of(inst.get("@id"))] = inst
        known[dsv_id] = dsv
        if dataset:
            known[uuid_of(dataset.get("@id"))] = dataset

        # two rounds: what the metadata points to, then what those point to (a person's ORCID, a strain's species)
        for _ in range(2):
            ids: list[str] = []
            for inst in list(known.values()):
                if inst:
                    ids.extend(instance_refs(inst))
            await _fetch_many(client, ids, known, token)

    return build_snapshot(dsv_id, dsv, dataset, space, known)
