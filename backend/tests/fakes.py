"""A small fake Knowledge Graph in the shape the real one answers (full property IRIs, @id references)."""
import json

import httpx

P = "https://openminds.om-i.org/props/"
T = "https://openminds.om-i.org/types/"
I = "https://kg.ebrains.eu/api/instances/"
DSV = "724d4af0-fe28-4032-8837-120b0d64a81c"
DS = "aaaaaaaa-0000-4000-8000-000000000001"


def ref(uid):
    return {"@id": I + uid}


def inst(uid, types, **props):
    return {"@id": I + uid, "@type": [T + t for t in types], **{P + k: v for k, v in props.items()}}


def kg_content():
    objs = {
        DSV: inst(DSV, ["DatasetVersion"], fullName="Whole brain imaging v1", description="A dataset.", versionIdentifier="v1",
                  license=[ref("lic")], technique=[ref("tech")], dataType=[ref("dt")], accessibility=ref("acc"), howToCite="Cite me",
                  digitalIdentifier=ref("doi"), repository=ref("repo"), versionInnovation="First version", fullDocumentation=ref("doc"),
                  ethicsAssessment=ref("eth"), experimentalApproach=[ref("ea")], preparationDesign=[ref("pd")], studyTarget=[ref("st")],
                  keyword=[ref("kw")], author=[ref("p2")]),
        DS: inst(DS, ["Dataset"], fullName="Whole brain imaging", description="The dataset.", author=[ref("p1"), ref("p2")], custodian=[ref("p1")]),
        "p1": inst("p1", ["Person"], givenName="Ada", familyName="Lovelace", digitalIdentifier=[ref("orcid1")]),
        "p2": inst("p2", ["Person"], givenName="Alan", familyName="Turing"),
        "orcid1": inst("orcid1", ["ORCID"], identifier="https://orcid.org/0000-0002-1825-0097"),
        "lic": inst("lic", ["License"], fullName="Creative Commons Attribution 4.0"),
        "tech": inst("tech", ["Technique"], name="positron emission tomography"),
        "dt": inst("dt", ["SemanticDataType"], name="PET"),
        "acc": inst("acc", ["ProductAccessibility"], name="free access"),
        "doi": inst("doi", ["DOI"], identifier="https://doi.org/10.25493/AAAA-BBB"),
        "repo": inst("repo", ["FileRepository"], iri={"@id": "https://data-proxy.ebrains.eu/api/v1/buckets/d-" + DSV}),
        "doc": inst("doc", ["DOI"], identifier="https://doi.org/10.25493/DOC"),
        "eth": inst("eth", ["ProductAccessibility"], name="no ethical issues"),
        "ea": inst("ea", ["ExperimentalApproach"], name="in vivo"),
        "pd": inst("pd", ["PreparationType"], name="in vivo"),
        "st": inst("st", ["Species"], name="Mus musculus"),
        "kw": inst("kw", ["Keyword"], name="PET imaging"),
        "mouse": inst("mouse", ["Species"], name="Mus musculus"),
        "male": inst("male", ["BiologicalSex"], name="male"),
        "adult": inst("adult", ["AgeCategory"], name="adult"),
        "attr": inst("attr", ["SubjectAttribute"], name="control"),
    }
    space = {
        "Subject": [
            inst("s1", ["Subject"], lookupLabel="FDG-PET_sub-01", internalIdentifier="sub-01", species=[ref("mouse")], biologicalSex=[ref("male")], studiedState=[ref("s1a")]),
            inst("s2", ["Subject"], lookupLabel="FDG-PET_sub-02", internalIdentifier="sub-02", studiedState=[ref("s2a")]),
        ],
        "SubjectState": [
            inst("s1a", ["SubjectState"], lookupLabel="s1-state", age={"@type": [T + "QuantitativeValue"], P + "value": 12, P + "unit": ref("wk")},
                 ageCategory=[ref("adult")], attribute=[ref("attr")]),
            inst("s2a", ["SubjectState"], lookupLabel="s2-state"),
        ],
        "TissueSample": [inst("t1", ["TissueSample"], lookupLabel="ts-1", internalIdentifier="ts-1", studiedState=[ref("t1a")])],
        "TissueSampleState": [inst("t1a", ["TissueSampleState"], descendedFrom=[ref("s1a")])],
    }
    objs["wk"] = inst("wk", ["UnitOfMeasurement"], name="week")
    for group in space.values():
        for o in group:
            uid = o["@id"].rsplit("/", 1)[-1]
            objs.setdefault(uid, o)
    return objs, space


def kg_transport():
    objs, space = kg_content()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/neighbors"):
            return httpx.Response(200, json={"data": {"inbound": [{"id": I + DS, "types": [T + "Dataset"]}], "outbound": []}})
        if path.endswith("/instances"):
            kind = request.url.params["type"].rsplit("/", 1)[-1]
            assert request.url.params["space"] == f"collab-d-{DSV}"
            return httpx.Response(200, json={"data": space.get(kind, [])})
        uid = path.rsplit("/", 1)[-1]
        if uid in objs:
            return httpx.Response(200, json={"data": objs[uid]})
        return httpx.Response(404, json={})

    return httpx.MockTransport(handler)
