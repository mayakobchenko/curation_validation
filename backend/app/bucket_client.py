"""
Names-only listing of the dataset's Data Proxy bucket (d-<dataset version UUID>), the same read-only listing the
Metadata Wizard's data descriptor page uses: the curator's token, pages through `marker`, file contents are never
downloaded. The summary says what is in the bucket (folders, extensions, sizes) and which subject / sample
identifiers its folders and file names carry, so they can be compared with the metadata.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import quote

import httpx

from .config import settings

MAX_OBJECTS = 20000
ID_IN_NAME = re.compile(r"(?<![A-Za-z0-9])(sub|subj|subject|sample|sam|spec|specimen)[-_]([A-Za-z0-9]+)", re.IGNORECASE)


class BucketError(Exception):
    def __init__(self, message: str, code: str = "BUCKET_ERROR"):
        super().__init__(message)
        self.code = code


def bucket_name(dsv_uuid: str) -> str:
    return f"d-{dsv_uuid.strip().lower()}"


async def list_objects(token: str, bucket: str, max_objects: int = MAX_OBJECTS,
                       transport: Optional[httpx.AsyncBaseTransport] = None) -> tuple[list[dict], bool]:
    objects: list[dict] = []
    marker = ""
    truncated = False
    async with httpx.AsyncClient(timeout=60, transport=transport) as client:
        while True:
            url = f"{settings.DATA_PROXY_BASE}/buckets/{quote(bucket)}?limit=0"
            if marker:
                url += f"&marker={quote(marker)}"
            try:
                resp = await client.get(url, headers={"Authorization": f"Bearer {token}", "accept": "application/json"})
            except httpx.HTTPError as exc:
                raise BucketError(f"The Data Proxy could not be reached ({exc}).", "BUCKET_UNREACHABLE")
            if resp.status_code in (401, 403):
                raise BucketError(f"Your account may not list the bucket {bucket}.", "NO_BUCKET_ACCESS")
            if resp.status_code == 404:
                raise BucketError(f"There is no bucket named {bucket}.", "NO_BUCKET")
            if resp.status_code != 200:
                raise BucketError(f"The Data Proxy answered {resp.status_code} for the bucket {bucket}.")
            page = resp.json().get("objects", []) or []
            if not page:
                break
            for o in page:
                objects.append({"name": o.get("name", ""), "bytes": int(o.get("bytes") or 0)})
            marker = page[-1].get("name", "")
            if len(objects) >= max_objects:
                truncated = True
                break
    return objects, truncated


def _ext(name: str) -> str:
    low = name.lower()
    for compound in ("nii.gz", "ome.tif", "ome.tiff", "tar.gz", "func.gii", "ome.zarr"):
        if low.endswith("." + compound):
            return compound
    m = re.search(r"\.([^./]+)$", low)
    return m.group(1) if m else "(none)"


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n} B"


def summarize(objects: list[dict], truncated: bool = False, depth: int = 3) -> dict:
    exts: dict[str, int] = {}
    folders: dict[str, dict] = {}
    ids: dict[str, set] = {}
    total = 0
    for o in objects:
        name, size = o["name"], o["bytes"]
        total += size
        parts = name.split("/")
        fname = parts.pop()
        exts[_ext(fname)] = exts.get(_ext(fname), 0) + 1
        folder = "/".join(parts[:depth]) or "(top level)"
        f = folders.setdefault(folder, {"files": 0, "bytes": 0, "examples": []})
        f["files"] += 1
        f["bytes"] += size
        if len(f["examples"]) < 3:
            f["examples"].append(fname)
        for m in ID_IN_NAME.finditer(name):
            ids.setdefault(m.group(1).lower(), set()).add(f"{m.group(1).lower()}-{m.group(2)}")
    return {
        "files": len(objects),
        "truncated": truncated,
        "bytes": total,
        "size": human_size(total),
        "extensions": dict(sorted(exts.items(), key=lambda kv: -kv[1])),
        "folders": [{"path": p, **v, "size": human_size(v["bytes"])} for p, v in sorted(folders.items())][:150],
        "identifiers": {k: sorted(v) for k, v in ids.items()},
        "top_level": sorted({o["name"].split("/")[0] for o in objects if "/" in o["name"]})[:200],
        "has_descriptor_pdf": any(re.search(r"data[-_ ]?descriptor.*\.pdf$", o["name"], re.IGNORECASE) for o in objects),
        "has_license": any(re.search(r"(^|/)licen[sc]e[^/]*\.(pdf|txt|md)?$", o["name"], re.IGNORECASE) for o in objects),
    }


async def fetch_bucket(token: str, dsv_uuid: str, transport: Optional[httpx.AsyncBaseTransport] = None) -> dict:
    name = bucket_name(dsv_uuid)
    out: dict = {"bucket": name, "summary": None, "error": None, "code": None}
    try:
        objects, truncated = await list_objects(token, name, transport=transport)
        out["summary"] = summarize(objects, truncated)
    except BucketError as exc:
        out["error"], out["code"] = str(exc), exc.code
    return out


def summary_text(summary: dict, max_folders: int = 60) -> str:
    """The summary as compact text for a prompt."""
    if not summary or not summary.get("files"):
        return "The bucket is empty."
    lines = [f"{summary['files']}{'+' if summary['truncated'] else ''} files, {summary['size']}.",
             "Files by extension: " + ", ".join(f".{k}: {v}" for k, v in list(summary["extensions"].items())[:25])]
    for f in summary["folders"][:max_folders]:
        lines.append(f"- {f['path']}/ ({f['files']} files, {f['size']}; e.g. {', '.join(f['examples'])})")
    if summary["identifiers"]:
        for kind, vals in summary["identifiers"].items():
            lines.append(f"Identifiers like '{kind}-…' in names ({len(vals)}): " + ", ".join(vals[:80]))
    return "\n".join(lines)
