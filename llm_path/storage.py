"""Storage layer for trace records."""

import json
from pathlib import Path

from .models import TraceRecord


class JSONLStorage:
    """Append-only JSONL storage for trace records."""

    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)
        # Ensure parent directory exists
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        # Open file once in append mode
        self._file = open(self.filepath, "a", encoding="utf-8")

    def append(self, record: TraceRecord) -> None:
        """Append a trace record to the JSONL file."""
        json.dump(record.to_dict(), self._file, ensure_ascii=False)
        self._file.write("\n")
        self._file.flush()

    def close(self) -> None:
        """Close the file handle."""
        if self._file and not self._file.closed:
            self._file.close()

    def read_all(self) -> list[TraceRecord]:
        """Read all records from the JSONL file."""
        if not self.filepath.exists():
            return []

        records = []
        with open(self.filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    records.append(
                        TraceRecord(
                            id=data["id"],
                            timestamp=data["timestamp"],
                            request=data["request"],
                            response=data.get("response"),
                            duration_ms=data.get("duration_ms", 0),
                            error=data.get("error"),
                        )
                    )
        return records
