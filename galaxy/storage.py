"""Local high scores: validated JSON, bounded history, atomic replacement."""

import json
import os
from pathlib import Path
from datetime import datetime, timezone
from .algorithms import insertion_sort, insert_ordered

MODES = ("standard", "relaxed", "endless")


def clean_name(value: str) -> str:
    return "".join(c for c in str(value) if c.isprintable()).strip()[:18] or "PILOT"


class ScoreStore:
    def __init__(self, directory: Path | None = None):
        if directory is None:
            override = os.environ.get("GALAXY_DEFENDER_DATA_DIR")
            directory = Path(override) if override else Path.home() / ".galaxy_defender"
        self.directory = Path(directory)
        self.path = self.directory / "profile.json"
        self.warning = ""
        self.name = "PILOT"
        self.records = {mode: [] for mode in MODES}
        self.load()

    def load(self):
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("version") != 1:
                raise ValueError("Unknown save format")
            self.name = clean_name(raw.get("name", "PILOT"))
            for mode in MODES:
                valid = []
                entries = raw.get("records", {}).get(mode, [])
                if not isinstance(entries, list):
                    continue
                for record in entries[:100]:
                    if not isinstance(record, dict):
                        continue
                    score = record.get("score")
                    if type(score) is not int or not 0 <= score <= 1_000_000_000_000_000:
                        continue
                    valid.append({"name": clean_name(record.get("name", "PILOT")),
                                  "score": score,
                                  "result": "victory" if record.get("result") == "victory" else "defeat",
                                  "date": str(record.get("date", ""))[:10],
                                  "wave": record.get("wave", 0) if type(record.get("wave")) is int and 0 <= record["wave"] <= 1_000_000 else 0})
                self.records[mode] = insertion_sort(valid, key=lambda r: r["score"], reverse=True)[:10]
        except (OSError, ValueError, TypeError, AttributeError):
            self.warning = "Saved scores could not be read. A new board will be used."

    def best(self, mode: str) -> int:
        rows = self.records.get(mode, [])
        return rows[0]["score"] if rows else 0

    def record(self, name: str, score: int, mode: str, result: str, wave: int = 0) -> bool:
        """Return whether this run beats the previous record, even if disk fails."""
        if mode not in MODES or type(score) is not int or score < 0:
            raise ValueError("Invalid score or mode")
        new_best = score > self.best(mode)
        self.name = clean_name(name)
        row = {"name": self.name, "score": score, "result": result,
               "date": datetime.now(timezone.utc).date().isoformat(), "wave": max(0, int(wave))}
        self.records[mode] = insert_ordered(self.records[mode], row,
                                            key=lambda r: r["score"], reverse=True)[:10]
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            temporary = self.directory / f"profile.{os.getpid()}.tmp"
            temporary.write_text(json.dumps({"version": 1, "name": self.name,
                                             "records": self.records}, indent=2), encoding="utf-8")
            temporary.replace(self.path)
            self.warning = ""
        except OSError:
            self.warning = "Score kept for this session; unable to save it to disk."
        return new_best
