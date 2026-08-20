"""Hospital department registry parsed from the knowledge base.

knowledge/public/departments.md (or knowledge/departments.md) is the single
source of truth for the departments this hospital actually offers. Triage
recommendations are validated against this registry so the frontend can only
offer a "register" action for departments that really exist.
"""

import hashlib
import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from app.core.config import settings


@dataclass(frozen=True)
class Department:
    id: str
    name: str
    category: str
    description: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


_CATEGORY_RE = re.compile(r"^#+\s*(.+?)\s*$")
_ENTRY_RE = re.compile(r"^[-*]\s*(?:\[([A-Za-z0-9_-]+)\]\s*)?(.+?)(?:[：:]\s*(.*))?$")


def _default_id(name: str) -> str:
    return hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]


def _departments_path(root: Path) -> Path | None:
    """Find the departments registry, preferring the public scope directory."""
    for candidate in (root / "public" / "departments.md", root / "departments.md"):
        if candidate.exists():
            return candidate
    return None


def load_departments(kb_dir: str | None = None) -> list[Department]:
    """Parse the departments knowledge file into a structured registry."""
    root = Path(kb_dir or settings.KB_DIR)
    path = _departments_path(root)
    if path is None:
        return []

    departments: list[Department] = []
    category = ""
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        heading = _CATEGORY_RE.match(line)
        if heading:
            title = heading.group(1)
            if title and not title.startswith("科室介绍"):
                category = title
            continue
        entry = _ENTRY_RE.match(line)
        if entry and entry.group(2):
            dept_id = entry.group(1) or _default_id(entry.group(2).strip())
            name = entry.group(2).strip()
            description = (entry.group(3) or "").strip()
            departments.append(
                Department(
                    id=dept_id,
                    name=name,
                    category=category,
                    description=description,
                )
            )
    return departments


@lru_cache(maxsize=1)
def _department_index() -> tuple[Department, ...]:
    return tuple(load_departments())


def list_departments() -> list[dict[str, str]]:
    """All hospital departments as plain dicts for API responses."""
    return [d.to_dict() for d in _department_index()]


def match_departments(text: str) -> list[Department]:
    """Return the departments whose name occurs in text, in order of first occurrence."""
    if not text:
        return []
    index = _department_index()
    names = sorted((d.name for d in index), key=len, reverse=True)
    by_name = {d.name: d for d in index}
    hits: list[tuple[int, Department]] = []
    for name in names:
        idx = text.find(name)
        if idx >= 0:
            hits.append((idx, by_name[name]))
    hits.sort(key=lambda pair: pair[0])
    return [d for _, d in hits]


def resolve_primary(text: str) -> Department | None:
    """Extract the recommended department from the 推荐科室：X marker line.

    Falls back to the first department mentioned in the text when the marker
    is missing, is "无", or names a department the hospital does not offer.
    """
    value = _recommendation_value(text)
    if value and value != "无":
        by_marker = match_departments(value)
        if by_marker:
            return by_marker[0]
    mentioned = match_departments(text)
    return mentioned[0] if mentioned else None


def _recommendation_value(text: str) -> str:
    match = re.search(r"推荐科室[:：]\s*([^\n。；;]*)", text)
    return match.group(1).strip() if match else ""
