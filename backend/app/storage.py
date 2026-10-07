"""
Minimal JSON-file storage for validation runs (draft + submitted), keyed
by a UUID — matching the existing naming convention
`curation-validation_<UUID>`. Swap for a real database later if the
volume of concurrent validations ever justifies it; for a per-dataset
curator checklist, one file per run is plenty and keeps a human-readable
audit trail on disk (same spirit as the wizard's data.json approach).
"""
import json
import os
import uuid
from datetime import datetime, timezone

from .config import settings
from .models import ValidationRun

os.makedirs(settings.DATA_DIR, exist_ok=True)


def _path(run_id: str) -> str:
    return os.path.join(settings.DATA_DIR, f"curation-validation_{run_id}.json")


def create(run: ValidationRun, created_by: str) -> ValidationRun:
    run.id = str(uuid.uuid4())
    run.created_at = datetime.now(timezone.utc).isoformat()
    run.created_by = created_by
    save(run)
    return run


def save(run: ValidationRun) -> None:
    with open(_path(run.id), "w", encoding="utf-8") as f:
        f.write(run.model_dump_json(indent=2))


def load(run_id: str) -> ValidationRun:
    with open(_path(run_id), "r", encoding="utf-8") as f:
        return ValidationRun.model_validate_json(f.read())


def list_all() -> list[ValidationRun]:
    runs = []
    for fname in sorted(os.listdir(settings.DATA_DIR), reverse=True):
        if fname.startswith("curation-validation_") and fname.endswith(".json"):
            run_id = fname[len("curation-validation_"):-len(".json")]
            try:
                runs.append(load(run_id))
            except Exception:
                continue
    return runs
