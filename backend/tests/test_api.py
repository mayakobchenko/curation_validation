import json

from fastapi.testclient import TestClient

from app import bucket_client, drive_client, kg_client
from app.config import settings
from app.main import app
from tests.fakes import DSV, kg_transport
from tests.test_sources import ANSWER, drive_transport, bucket_transport, llm_transport, make_docx
from app import llm_review

import asyncio


def login() -> TestClient:
    client = TestClient(app, follow_redirects=False)
    client.get("/auth/dev-login")
    return client


def patch_sources(monkeypatch, draft=None, files=("data-descriptor_120b0d64a81c.doc", "metadata_wizard_draft.json")):
    real_kg, real_drive, real_bucket = kg_client.pull_dataset_version_bundle, drive_client.fetch_drive_sources, bucket_client.fetch_bucket

    async def kg(uuid, token, transport=None):
        return await real_kg(uuid, token, transport=kg_transport())

    async def drive(token, uuid, transport=None):
        return await real_drive(token, uuid, transport=drive_transport(list(files), draft=draft))

    async def bucket(token, uuid, transport=None):
        return await real_bucket(token, uuid, transport=bucket_transport(["LICENSE.pdf", "sub-01/a.nii.gz"]))

    monkeypatch.setattr(kg_client, "pull_dataset_version_bundle", kg)
    monkeypatch.setattr(drive_client, "fetch_drive_sources", drive)
    monkeypatch.setattr(bucket_client, "fetch_bucket", bucket)


def test_a_run_needs_only_the_dataset_version_and_the_gitlab_issue(monkeypatch):
    patch_sources(monkeypatch, draft={"dataset1": {"dataTitle": "Whole brain imaging v1"},
                                      "subjectMetadata": {"subjects": [{"subjectID": "FDG-PET_sub-01", "states": [{}]}]}})
    c = login()
    r = c.post("/api/validations", json={"dataset_version_uuid": DSV.upper(), "gitlab_issue_url": "https://gitlab.ebrains.eu/x/-/issues/1913"})
    assert r.status_code == 200, r.text
    run = r.json()
    info = run["dataset_info"]
    assert info["dataset_title"] == "Whole brain imaging v1" and info["version_identifier"] == "v1" and info["dataset_uuid"]
    assert info["gitlab_issue_url"].endswith("1913") and info["dataset_version_uuid"] == DSV
    assert run["secondary_curator_info"]["secondary_curator_name"] == "Dev Curator" and run["secondary_curator_info"]["validation_date"]
    assert run["sources"]["kg"]["subjects"] == 2 and run["sources"]["drive"]["descriptor"] == "data-descriptor_120b0d64a81c.doc"
    assert run["sources"]["bucket"]["files"] == 2 and run["descriptor"]["text"].startswith("Title")
    assert run["comparison"]["draft"]["counts"]["only_in_kg"] >= 1
    t3 = {i["label"]: i for i in run["data_descriptor_checks"]["items"]}
    assert t3["Data Descriptor present and uploaded"]["auto_result"] == "NO"          # the bucket has no descriptor PDF
    t6 = {i["label"]: i for i in run["file_repository_checks"]["items"]}
    assert t6["Naming convention followed"]["auto_result"] == "YES"


def test_a_missing_drive_does_not_stop_the_validation(monkeypatch):
    real = drive_client.fetch_drive_sources
    patch_sources(monkeypatch)

    async def failing(token, uuid, transport=None):
        return await real(token, uuid, transport=drive_transport([], token_status=403))

    monkeypatch.setattr(drive_client, "fetch_drive_sources", failing)
    run = login().post("/api/validations", json={"dataset_version_uuid": DSV}).json()
    assert run["sources"]["kg"]["ok"] and not run["sources"]["drive"]["ok"] and "collab.drive" in run["sources"]["drive"]["error"]
    assert run["descriptor"] is None and run["kg_snapshot"]["subjects"]


def test_bad_uuid_and_unknown_dataset_are_refused(monkeypatch):
    c = login()
    assert c.post("/api/validations", json={"dataset_version_uuid": "not-a-uuid"}).status_code == 400
    monkeypatch.setattr(kg_client, "pull_dataset_version_bundle", lambda *a, **k: (_ for _ in ()).throw(kg_client.KGError("nope", 404)))

    async def boom(*a, **k):
        raise kg_client.KGError("The dataset version x was not found in the Knowledge Graph.", 404)

    monkeypatch.setattr(kg_client, "pull_dataset_version_bundle", boom)
    r = c.post("/api/validations", json={"dataset_version_uuid": DSV})
    assert r.status_code == 404 and "not found" in r.json()["detail"]


def test_saving_answers_keeps_fetched_data_and_suggestions(monkeypatch):
    patch_sources(monkeypatch)
    c = login()
    run = c.post("/api/validations", json={"dataset_version_uuid": DSV}).json()
    run["data_descriptor_checks"]["items"][0]["answer"] = "YES"
    run["descriptor"] = {"name": "tampered", "text": "tampered"}                     # a stale copy from the browser
    run["data_descriptor_checks"]["items"][0]["auto_result"] = "NA"
    saved = c.put(f"/api/validations/{run['id']}", json=run).json()
    assert saved["data_descriptor_checks"]["items"][0]["answer"] == "YES"
    assert saved["descriptor"]["name"] != "tampered"
    assert saved["data_descriptor_checks"]["items"][0]["auto_result"] != "NA"
    listed = c.get("/api/validations").json()
    assert listed[0]["id"] == run["id"] and "kg_snapshot" not in listed[0] and "descriptor" not in listed[0]


def test_llm_review_flow(monkeypatch):
    patch_sources(monkeypatch)
    c = login()
    run = c.post("/api/validations", json={"dataset_version_uuid": DSV}).json()
    assert c.get("/api/llm").json()["available"] is False
    assert c.post(f"/api/validations/{run['id']}/llm-review").status_code == 503
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://llm.example/v1")
    monkeypatch.setattr(settings, "LLM_API_KEY", "k")
    monkeypatch.setattr(settings, "LLM_MODEL", "m")
    real = llm_review.review

    async def review(text, snap, cmp, bucket, transport=None):
        return await real(text, snap, cmp, bucket, transport=llm_transport(ANSWER))

    monkeypatch.setattr(llm_review, "review", review)
    assert c.get("/api/llm").json()["available"] is True
    done = c.post(f"/api/validations/{run['id']}/llm-review").json()
    assert done["llm_review"]["findings"][0]["area"] == "Subjects"
    t3 = {i["label"]: i for i in done["data_descriptor_checks"]["items"]}
    m = t3["Data Descriptor matches the dataset content"]
    assert m["auto_result"] == "NO" and m["auto_note"].startswith("AI suggestion") and m["answer"] == "PENDING"   # a suggestion only
    assert "secret" not in json.dumps(done)
