"""
Reads files from the Collaboratory Drive (Seafile) of a dataset: the data descriptor Word file and the metadata draft
that the Metadata Wizard keeps there. Read-only; runs with the curator's own EBRAINS token (scope collab.drive), so
the Drive decides what the curator may see.

The library of a dataset has the name of its Collab, d-<dataset version UUID>. The calls are the ones the wizard uses
(token exchange, library lookup, directory listing, download link).
"""
from __future__ import annotations

import re
from typing import Optional

import httpx

from .config import settings

DRAFT_FILE = "metadata_wizard_draft.json"
DESCRIPTOR_NAME = re.compile(r"(data[-_ ]?descriptor).*\.(docx?|odt)$", re.IGNORECASE)
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024


class DriveError(Exception):
    def __init__(self, message: str, code: str = "DRIVE_ERROR"):
        super().__init__(message)
        self.code = code


def _client(transport: Optional[httpx.AsyncBaseTransport] = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=30, transport=transport, follow_redirects=True)


async def _call(client: httpx.AsyncClient, url: str, headers: dict) -> httpx.Response:
    try:
        return await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise DriveError(f"The Collab drive could not be reached ({exc}).", "DRIVE_UNREACHABLE")


async def drive_token(client: httpx.AsyncClient, ebrains_token: str) -> str:
    resp = await _call(client, f"{settings.DRIVE_BASE}/api2/account/token/",
                       {"Authorization": f"Bearer {ebrains_token}", "Accept": "text/plain"})
    if resp.status_code in (401, 403):
        raise DriveError("Your EBRAINS login does not give access to the Collab drive. "
                         "The login needs the scope collab.drive (see OIDC_SCOPE); then log out and log in again.", "NO_DRIVE_ACCESS")
    if resp.status_code != 200:
        raise DriveError(f"The Collab drive answered {resp.status_code} when asked for access.")
    token = resp.text.strip().strip('"')
    if not token:
        raise DriveError("The Collab drive did not give an access token.", "NO_DRIVE_ACCESS")
    return token


async def _authed(client: httpx.AsyncClient, url: str, token: str) -> httpx.Response:
    headers = {"Accept": "application/json"}
    resp = await _call(client, url, {**headers, "Authorization": f"Token {token}"})
    if resp.status_code == 401:
        resp = await _call(client, url, {**headers, "Authorization": f"Bearer {token}"})
    return resp


async def find_library(client: httpx.AsyncClient, token: str, name: str) -> dict:
    resp = await _authed(client, f"{settings.DRIVE_BASE}/api2/repos/", token)
    if resp.status_code in (401, 403):
        raise DriveError("The Collab drive did not accept your login.", "NO_DRIVE_ACCESS")
    if resp.status_code != 200:
        raise DriveError(f"The Collab drive answered {resp.status_code} when listing your libraries.")
    libs = resp.json()
    for lib in libs if isinstance(libs, list) else []:
        if lib.get("name") == name:
            return lib
    raise DriveError(f"No Collab drive named {name} was found among the libraries you can access "
                     "(you must be a member of that Collab).", "NO_LIBRARY")


async def list_dir(client: httpx.AsyncClient, token: str, repo_id: str, path: str = "/") -> list[dict]:
    from urllib.parse import quote
    resp = await _authed(client, f"{settings.DRIVE_BASE}/api2/repos/{repo_id}/dir/?p={quote(path)}", token)
    if resp.status_code == 404:
        return []
    if resp.status_code != 200:
        raise DriveError(f"The Collab drive answered {resp.status_code} when listing {path}.")
    data = resp.json()
    return data if isinstance(data, list) else []


async def download(client: httpx.AsyncClient, token: str, repo_id: str, path: str) -> Optional[bytes]:
    from urllib.parse import quote
    link = await _authed(client, f"{settings.DRIVE_BASE}/api2/repos/{repo_id}/file/?p={quote(path)}&reuse=1", token)
    if link.status_code == 404:
        return None
    if link.status_code != 200:
        raise DriveError(f"The Collab drive answered {link.status_code} when asked for {path}.")
    url = link.text.strip().strip('"')
    resp = await _call(client, url, {})
    if resp.status_code != 200:
        raise DriveError(f"The file {path} could not be downloaded ({resp.status_code}).")
    if len(resp.content) > MAX_DOWNLOAD_BYTES:
        raise DriveError(f"The file {path} is larger than {MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB.")
    return resp.content


def pick_descriptor(entries: list[dict]) -> Optional[dict]:
    """The data descriptor among the files at the top of the drive: data-descriptor_<id>.doc(x); the newest one wins."""
    files = [e for e in entries if e.get("type") == "file" and DESCRIPTOR_NAME.search(e.get("name", ""))]
    if not files:
        files = [e for e in entries if e.get("type") == "file"
                 and re.search(r"descriptor.*\.(docx?|odt)$", e.get("name", ""), re.IGNORECASE)]
    files.sort(key=lambda e: e.get("mtime", 0), reverse=True)
    return files[0] if files else None


async def fetch_drive_sources(ebrains_token: str, dsv_uuid: str,
                              transport: Optional[httpx.AsyncBaseTransport] = None) -> dict:
    """The data descriptor file and the wizard's metadata draft of the dataset's drive, or the reason they are missing.

    -> {"library": name | None, "files": [names at the top], "descriptor": {"name", "bytes"} | None,
        "draft": {"name", "text"} | None, "error": str | None, "code": str | None}
    """
    out: dict = {"library": None, "files": [], "descriptor": None, "draft": None, "error": None, "code": None}
    name = f"d-{dsv_uuid.lower()}"
    try:
        async with _client(transport) as client:
            token = await drive_token(client, ebrains_token)
            lib = await find_library(client, token, name)
            out["library"] = name
            entries = await list_dir(client, token, lib["id"], "/")
            out["files"] = sorted(e.get("name", "") for e in entries)
            chosen = pick_descriptor(entries)
            if chosen:
                data = await download(client, token, lib["id"], "/" + chosen["name"])
                if data is not None:
                    out["descriptor"] = {"name": chosen["name"], "bytes": data}
            if any(e.get("name") == DRAFT_FILE for e in entries):
                data = await download(client, token, lib["id"], "/" + DRAFT_FILE)
                if data is not None:
                    out["draft"] = {"name": DRAFT_FILE, "text": data.decode("utf-8", errors="replace")}
    except DriveError as exc:
        out["error"], out["code"] = str(exc), exc.code
    return out
