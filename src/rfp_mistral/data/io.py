from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from rfp_mistral.schemas import RFPRecord, TrainingExample


def load_rfp_records(path: str | Path) -> list[RFPRecord]:
    records: list[RFPRecord] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            records.append(RFPRecord.from_dict(json.loads(line)))
    return records


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def write_training_examples(path: str | Path, rows: Iterable[TrainingExample]) -> None:
    write_jsonl(path, (row.to_dict() for row in rows))

