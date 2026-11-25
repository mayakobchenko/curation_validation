import asyncio

from app import checks, kg_client
from app.models import new_validation_run
from tests.fakes import DSV, kg_transport


def snapshot():
    return asyncio.run(kg_client.pull_dataset_version_bundle(DSV, "tok", transport=kg_transport()))


def test_snapshot_reads_real_property_names_and_resolves_references():
    s = snapshot()
    dsv = s["datasetVersion"]
    assert dsv["fullName"] == "Whole brain imaging v1"
    assert dsv["license"] == ["Creative Commons Attribution 4.0"]
    assert dsv["technique"] == ["positron emission tomography"]
    assert dsv["digitalIdentifier"] == "https://doi.org/10.25493/AAAA-BBB"
    assert s["dataset"]["fullName"] == "Whole brain imaging"          # found through the neighbours of the version
    assert [p["name"] for p in s["people"] if p["role"] == "author"] == ["Ada Lovelace", "Alan Turing"]
    assert next(p for p in s["people"] if p["name"] == "Ada Lovelace")["orcid"] == "https://orcid.org/0000-0002-1825-0097"
    assert {"custodian": "Ada Lovelace"}.items() <= {p["role"]: p["name"] for p in s["people"]}.items()


def test_snapshot_embeds_states_and_keeps_all_specimens():
    s = snapshot()
    assert [x["internalIdentifier"] for x in s["subjects"]] == ["sub-01", "sub-02"]
    first = s["subjects"][0]
    assert first["states"][0]["age"]["value"] == 12 and first["states"][0]["ageCategory"] == ["adult"]
    assert first["species"] == ["Mus musculus"] and first["types"] == ["Subject"]
    assert s["tissueSamples"][0]["states"][0]["descendedFrom"]            # linked to the subject state


def test_checks_suggest_from_the_snapshot_and_name_what_is_missing():
    run = new_validation_run(DSV)
    run.kg_snapshot = snapshot()
    checks.apply_source_checks(run)
    by = {i.label: i for i in run.kge_metadata_checks.dataset_and_version}
    assert by["Full name"].auto_result == "YES" and "Whole brain imaging v1" in by["Full name"].auto_note
    assert by["Licence"].auto_result == "YES"
    assert by["Behavioral protocol"].auto_result == "NA"                  # empty, may not apply
    subj = {i.label: i for i in run.kge_metadata_checks.subjects}
    assert subj["Internal identifier"].auto_result == "YES"
    assert subj["Age"].auto_result == "NO" and "sub-02" in subj["Age"].auto_note   # sub-02 has no age
    assert subj["Sex"].auto_result == "NO" and "FDG-PET_sub-02" in subj["Sex"].auto_note
    tissue = {i.label: i for i in run.kge_metadata_checks.tissue_samples}
    assert tissue["Descended from"].auto_result == "YES"
    assert tissue["Origin"].auto_result == "NO"


def test_identical_value_on_dataset_and_version_is_flagged():
    dsv = {"fullName": "Same", "description": "d", "custodian": ["A"]}
    res = checks.ds_dsv_results(dsv, {"fullName": "Same", "description": "other", "custodian": ["B"]})
    assert res["Full name"][0] == "NO" and "inheritance" in res["Full name"][1]
    assert res["Description"][0] == "YES"
