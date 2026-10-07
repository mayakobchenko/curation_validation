"""
Pydantic models for the curation-validation checklist, mirroring
curation-validation_<UUID>.md table-for-table, so a validation run on this
app maps 1:1 onto the existing manual form and nothing in the sign-off
gets lost in translation.
"""
from __future__ import annotations
from typing import Optional, Literal
from pydantic import BaseModel, Field

CheckAnswer = Literal["YES", "NO", "NA", "PENDING"]


class CheckItem(BaseModel):
    label: str
    answer: CheckAnswer = "PENDING"
    comment: str = ""
    # filled in automatically by a mechanical check; None if this item has
    # no automated check and is left to the secondary curator's judgement
    auto_result: Optional[CheckAnswer] = None
    auto_note: Optional[str] = None


class DatasetInfo(BaseModel):
    """Table 1."""
    primary_curator_name: str = ""
    dataset_title: str = ""
    gitlab_issue_url: str = ""
    dataset_version_uuid: str = ""


class SecondaryCuratorInfo(BaseModel):
    """Table 2."""
    secondary_curator_name: str = ""
    validation_date: str = ""


class DataDescriptorChecks(BaseModel):
    """Table 3 — kept fully manual: text-matching/content-quality
    judgement calls are out of scope for automation in v1."""
    items: list[CheckItem] = Field(default_factory=list)


class StructureChecks(BaseModel):
    """Table 4."""
    items: list[CheckItem] = Field(default_factory=list)


class KGEMetadataChecks(BaseModel):
    """Table 5 — dataset/version, subject(group)(state),
    tissue sample (collection)(state), and project fields."""
    dataset_and_version: list[CheckItem] = Field(default_factory=list)
    subjects: list[CheckItem] = Field(default_factory=list)
    tissue_samples: list[CheckItem] = Field(default_factory=list)
    project: list[CheckItem] = Field(default_factory=list)


class FileRepositoryChecks(BaseModel):
    """Table 6."""
    items: list[CheckItem] = Field(default_factory=list)


class ValidationRun(BaseModel):
    id: Optional[str] = None
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    status: Literal["draft", "submitted"] = "draft"

    dataset_info: DatasetInfo = DatasetInfo()
    secondary_curator_info: SecondaryCuratorInfo = SecondaryCuratorInfo()
    data_descriptor_checks: DataDescriptorChecks = DataDescriptorChecks()
    structure_checks: StructureChecks = StructureChecks()
    kge_metadata_checks: KGEMetadataChecks = KGEMetadataChecks()
    file_repository_checks: FileRepositoryChecks = FileRepositoryChecks()

    # raw KG pull, kept alongside the run so the exported document can
    # quote exact field values and so a re-opened draft doesn't need to
    # re-fetch the KG to show what it last saw
    kg_snapshot: Optional[dict] = None


DEFAULT_TABLE3_ITEMS = [
    "Data Descriptor present and uploaded",
    "Data Descriptor matches the dataset content",
    "Data Descriptor free of placeholder/template text",
]

DEFAULT_TABLE4_ITEMS = [
    "Overall file/folder structure is logical and documented",
    "File naming is consistent across the dataset",
]

DEFAULT_TABLE5_DS_DSV_ITEMS = [
    "Full name",
    "Description",
    "Custodian",
    "Authors",
    "Version identifier",
    "Version innovation",
    "File repository",
    "DOI",
    "How to cite",
    "Accessibility",
    "Licence",
    "Full documentation",
    "Ethics assessment",
    "Related publication",
    "Data type",
    "Experimental approach",
    "Technique",
    "Behavioral protocol",
    "Preparation design",
    "Study target",
    "Keywords",
]

DEFAULT_TABLE5_SUBJECT_ITEMS = [
    "Internal identifier",
    "Age",
    "Age category",
    "Sex",
    "Strain",
    "Attribute",
]

DEFAULT_TABLE5_TISSUE_ITEMS = [
    "Internal identifier",
    "Type",
    "Strain",
    "Sex",
    "Origin",
    "Anatomical location",
    "Descended from",
]

DEFAULT_TABLE5_PROJECT_ITEMS = [
    "Project linked to dataset version",
]

DEFAULT_TABLE6_ITEMS = [
    "Naming convention followed",
    "Organization consistent with Data Descriptor",
    "Licence / Data Descriptor PDF uploaded",
    "KG indexing complete",
    "Embargo / HDG privacy settings correct",
    "Content types as expected",
]


def new_validation_run(dataset_version_uuid: str = "") -> ValidationRun:
    return ValidationRun(
        dataset_info=DatasetInfo(dataset_version_uuid=dataset_version_uuid),
        data_descriptor_checks=DataDescriptorChecks(
            items=[CheckItem(label=l) for l in DEFAULT_TABLE3_ITEMS]
        ),
        structure_checks=StructureChecks(
            items=[CheckItem(label=l) for l in DEFAULT_TABLE4_ITEMS]
        ),
        kge_metadata_checks=KGEMetadataChecks(
            dataset_and_version=[CheckItem(label=l) for l in DEFAULT_TABLE5_DS_DSV_ITEMS],
            subjects=[CheckItem(label=l) for l in DEFAULT_TABLE5_SUBJECT_ITEMS],
            tissue_samples=[CheckItem(label=l) for l in DEFAULT_TABLE5_TISSUE_ITEMS],
            project=[CheckItem(label=l) for l in DEFAULT_TABLE5_PROJECT_ITEMS],
        ),
        file_repository_checks=FileRepositoryChecks(
            items=[CheckItem(label=l) for l in DEFAULT_TABLE6_ITEMS]
        ),
    )
