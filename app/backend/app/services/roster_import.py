"""Strict CSV parsing for atomic student roster imports."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RosterRow:
    row: int
    student_number: str
    name: str
    email: str
    batch: str
    division_id: str


@dataclass(frozen=True)
class RosterError:
    row: int
    field: str
    message: str


@dataclass
class RosterImportResult:
    rows: list[RosterRow] = field(default_factory=list)
    errors: list[RosterError] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def parse_roster_csv(content: str, division_id: str) -> RosterImportResult:
    result = RosterImportResult()
    reader = csv.DictReader(io.StringIO(content))
    required = {"student_number", "name"}
    headers = set(reader.fieldnames or [])
    missing = sorted(required - headers)
    if missing:
        result.errors.append(RosterError(1, ",".join(missing), "Missing required column(s)"))
        return result

    seen: set[str] = set()
    for row_number, raw in enumerate(reader, start=2):
        student_number = (raw.get("student_number") or "").strip()
        name = (raw.get("name") or "").strip()
        email = (raw.get("email") or "").strip().lower()
        batch = (raw.get("batch") or "").strip()
        if not student_number:
            result.errors.append(RosterError(row_number, "student_number", "Student number is required"))
            continue
        if not name:
            result.errors.append(RosterError(row_number, "name", "Student name is required"))
            continue
        normalized = student_number.casefold()
        if normalized in seen:
            result.errors.append(RosterError(row_number, "student_number", "Duplicate student number in file"))
            continue
        if email and ("@" not in email or email.startswith("@") or email.endswith("@")):
            result.errors.append(RosterError(row_number, "email", "Invalid email address"))
            continue
        seen.add(normalized)
        result.rows.append(RosterRow(
            row=row_number, student_number=student_number, name=name,
            email=email, batch=batch, division_id=division_id,
        ))
    return result
