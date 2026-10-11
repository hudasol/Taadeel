"""Point-in-time reconstruction with effective-date uncertainty.

A timeline is a base version plus amending versions. Each version has an
optional ``valid_from`` and a status. The reconstruction never silently
guesses: if a version that might apply has an uncertain or unknown effective
date, the result is flagged ``uncertain`` and lists the candidates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class Version:
    version_id: str
    valid_from: date | None
    status: str                    # known | uncertain | unknown
    issue_date: date | None = None


@dataclass
class PointInTime:
    as_of: date
    version_id: str | None         # best determinate version, None if law not yet in force
    certainty: str                 # "certain" | "uncertain" | "not_in_force"
    candidates: list[str] = field(default_factory=list)   # later versions that may already apply
    note: str = ""


def as_of(versions: list[Version], d: date) -> PointInTime:
    known = sorted(
        (v for v in versions if v.status == "known" and v.valid_from is not None),
        key=lambda v: v.valid_from,  # type: ignore[arg-type,return-value]
    )
    applicable = [v for v in known if v.valid_from <= d]  # type: ignore[operator]
    # Versions that could already apply but whose effective date is not determined.
    maybe = [
        v for v in versions
        if v.status != "known" and (v.issue_date is None or v.issue_date <= d)
    ]
    if not applicable:
        if maybe:
            return PointInTime(d, None, "uncertain", [v.version_id for v in maybe],
                               "No version has a known effective date on or before this date; undated versions may apply.")
        return PointInTime(d, None, "not_in_force", [], "No version is known to be in force on this date.")
    best = applicable[-1]
    if maybe:
        return PointInTime(d, best.version_id, "uncertain", [v.version_id for v in maybe],
                           "A later version has an uncertain effective date and may already apply.")
    return PointInTime(d, best.version_id, "certain")
