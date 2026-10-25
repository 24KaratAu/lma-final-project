"""Read and write the contract files."""

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from src.common.schemas import Lease

M = TypeVar("M", bound=BaseModel)


def read_jsonl(path: str | Path, model: type[M]) -> list[M]:
    with open(path, encoding="utf-8") as f:
        return [model.model_validate_json(line) for line in f if line.strip()]


def write_jsonl(path: str | Path, records: list[BaseModel]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(r.model_dump_json() + "\n")


def read_lease(path: str | Path) -> Lease:
    return Lease.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def read_leases(folder: str | Path) -> dict[str, Lease]:
    leases = [read_lease(p) for p in sorted(Path(folder).glob("*.json"))]
    return {lease.lease_id: lease for lease in leases}
