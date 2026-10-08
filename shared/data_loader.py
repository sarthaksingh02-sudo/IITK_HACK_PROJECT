"""
shared/data_loader.py
Validates every file in /data/real/ against its schema and reports what is
missing, placeholder, or malformed.

STRICT RULE: This module NEVER auto-fills, invents, or corrects data.
If a file is missing or contains placeholder content, it is reported as such
and the caller decides how to proceed.

Usage:
  python shared/data_loader.py          # prints full report to stdout
  python shared/data_loader.py --json   # machine-readable JSON report

Importable:
  from shared.data_loader import load_and_validate, DataStatus

Returns a DataReport containing per-file FileReport items.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

# Allow running as script from repo root
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

try:
    import yaml
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

from pydantic import ValidationError

from shared.schemas import (
    ImmunizationRule,
    RedFlagRule,
    PathwayEntry,
    Education,
)

# ── Repo paths ────────────────────────────────────────────────────────────────

REPO_ROOT       = pathlib.Path(__file__).parent.parent
REAL_DIR        = REPO_ROOT / "data" / "real"
NOTICES_DIR     = REAL_DIR / "notices"
HEALTH_DIR      = REAL_DIR / "health"
IMMUNIZATION_FILE = HEALTH_DIR / "immunization_schedule.yaml"
RED_FLAGS_FILE    = HEALTH_DIR / "red_flags.yaml"
PATHWAYS_FILE     = REAL_DIR / "pathways.yaml"


# ── Status enum ───────────────────────────────────────────────────────────────

class DataStatus(str, Enum):
    OK          = "OK"           # File exists, real data, schema-valid
    PLACEHOLDER = "PLACEHOLDER"  # File exists but contains placeholder content
    MISSING     = "MISSING"      # File does not exist
    MALFORMED   = "MALFORMED"    # File exists, not placeholder, but fails schema


# ── Report dataclasses ────────────────────────────────────────────────────────

@dataclass
class FileReport:
    path:               str
    status:             DataStatus
    details:            str
    items_found:        int       = 0   # how many schema-valid items were parsed
    items_placeholder:  int       = 0   # how many items were placeholders
    items_invalid:      int       = 0   # how many items failed schema validation
    errors:             list[str] = field(default_factory=list)

    def is_usable(self) -> bool:
        """True only when status is OK and at least one valid item found."""
        return self.status == DataStatus.OK and self.items_found > 0


@dataclass
class DataReport:
    files: list[FileReport] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return all(f.status == DataStatus.OK for f in self.files)

    @property
    def usable_files(self) -> list[FileReport]:
        return [f for f in self.files if f.is_usable()]

    @property
    def blocking_files(self) -> list[FileReport]:
        return [f for f in self.files if not f.is_usable()]

    def summary(self) -> str:
        total = len(self.files)
        ok = sum(1 for f in self.files if f.status == DataStatus.OK)
        placeholder = sum(1 for f in self.files if f.status == DataStatus.PLACEHOLDER)
        missing = sum(1 for f in self.files if f.status == DataStatus.MISSING)
        malformed = sum(1 for f in self.files if f.status == DataStatus.MALFORMED)
        return (
            f"{total} file(s) checked — "
            f"OK: {ok}, PLACEHOLDER: {placeholder}, MISSING: {missing}, MALFORMED: {malformed}"
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_placeholder_value(v: object) -> bool:
    """Return True if a string value looks like an unfilled placeholder."""
    if not isinstance(v, str):
        return False
    low = v.lower()
    return any(kw in low for kw in (
        "placeholder", "fill in", "required", "do not use",
        "must be replaced", "todo", "tbd", "<", ">"
    ))


def _load_yaml(path: pathlib.Path) -> Optional[dict]:
    """Load YAML. Returns None and raises ValueError on failure."""
    if not _YAML_AVAILABLE:
        raise ValueError("PyYAML not installed. Run: pip install pyyaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── Per-file validators ───────────────────────────────────────────────────────

def _validate_notices_dir() -> FileReport:
    """
    Check /data/real/notices/ for .txt or .pdf files.
    Each .txt file must start with a line containing 'SOURCE:'.
    """
    rel = str(NOTICES_DIR.relative_to(REPO_ROOT))
    if not NOTICES_DIR.exists():
        return FileReport(
            path=rel,
            status=DataStatus.MISSING,
            details="Directory /data/real/notices/ does not exist.",
        )

    notice_files = [
        f for f in NOTICES_DIR.iterdir()
        if f.suffix in (".txt", ".pdf") and f.name != "README.md"
    ]

    if not notice_files:
        return FileReport(
            path=rel,
            status=DataStatus.PLACEHOLDER,
            details=(
                "No notice files (.txt or .pdf) found. "
                "Add official government notices before running the ingest pipeline. "
                "See data/real/notices/README.md for instructions."
            ),
        )

    found = 0
    errors: list[str] = []
    for f in notice_files:
        if f.suffix == ".pdf":
            found += 1
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            errors.append(f"{f.name}: file is empty")
            continue
        # Look for SOURCE: header in first 5 non-blank lines
        header_ok = any("SOURCE:" in l.upper() for l in lines[:5])
        if not header_ok:
            errors.append(
                f"{f.name}: missing 'SOURCE: <url> | RETRIEVED: <date>' header "
                "in first 5 lines"
            )
        else:
            found += 1

    status = DataStatus.MALFORMED if errors else DataStatus.OK
    details = (
        f"{found} notice file(s) with valid SOURCE header."
        + (f" {len(errors)} file(s) missing header." if errors else "")
    )
    return FileReport(
        path=rel,
        status=status,
        details=details,
        items_found=found,
        items_invalid=len(errors),
        errors=errors,
    )


def _validate_immunization_file() -> FileReport:
    """Validate immunization_schedule.yaml against ImmunizationRule schema."""
    rel = str(IMMUNIZATION_FILE.relative_to(REPO_ROOT))
    if not IMMUNIZATION_FILE.exists():
        return FileReport(
            path=rel,
            status=DataStatus.MISSING,
            details="File not found. Copy the NIS schedule from MoHFW source.",
        )
    try:
        data = _load_yaml(IMMUNIZATION_FILE)
    except Exception as e:
        return FileReport(
            path=rel,
            status=DataStatus.MALFORMED,
            details=f"YAML parse error: {e}",
            errors=[str(e)],
        )

    if isinstance(data, dict) and data.get("_status", "").upper().startswith("PLACEHOLDER"):
        return FileReport(
            path=rel,
            status=DataStatus.PLACEHOLDER,
            details=(
                "File contains placeholder content. "
                f"Source: {data.get('_source_url', 'unknown')}. "
                "Populate from official MoHFW NIS PDF before use."
            ),
        )

    schedule_items = data.get("schedule", []) if isinstance(data, dict) else []
    found, placeholder_count, errors = 0, 0, []

    for i, item in enumerate(schedule_items):
        # Check for any placeholder values in the item
        if any(_is_placeholder_value(v) for v in item.values() if isinstance(v, str)):
            placeholder_count += 1
            continue
        try:
            ImmunizationRule(**item)
            found += 1
        except (ValidationError, TypeError) as e:
            errors.append(f"Item {i} ({item.get('vaccine','?')}): {e}")

    if placeholder_count == len(schedule_items) and len(schedule_items) > 0:
        return FileReport(
            path=rel,
            status=DataStatus.PLACEHOLDER,
            details="All schedule items are placeholders.",
            items_placeholder=placeholder_count,
        )

    status = DataStatus.MALFORMED if errors else DataStatus.OK
    return FileReport(
        path=rel,
        status=status,
        details=(
            f"{found} immunization rule(s) validated. "
            f"{placeholder_count} placeholder(s). "
            f"{len(errors)} error(s)."
        ),
        items_found=found,
        items_placeholder=placeholder_count,
        items_invalid=len(errors),
        errors=errors,
    )


def _validate_red_flags_file() -> FileReport:
    """Validate red_flags.yaml against RedFlagRule schema."""
    rel = str(RED_FLAGS_FILE.relative_to(REPO_ROOT))
    if not RED_FLAGS_FILE.exists():
        return FileReport(
            path=rel,
            status=DataStatus.MISSING,
            details="File not found. Copy from ASHA/IMCI guidelines.",
        )
    try:
        data = _load_yaml(RED_FLAGS_FILE)
    except Exception as e:
        return FileReport(
            path=rel,
            status=DataStatus.MALFORMED,
            details=f"YAML parse error: {e}",
            errors=[str(e)],
        )

    if isinstance(data, dict) and data.get("_status", "").upper().startswith("PLACEHOLDER"):
        return FileReport(
            path=rel,
            status=DataStatus.PLACEHOLDER,
            details=(
                "File contains placeholder content. "
                f"Source: {data.get('_source_url', 'unknown')}. "
                "Populate from official ASHA/IMCI source before use."
            ),
        )

    items = data.get("red_flags", []) if isinstance(data, dict) else []
    found, placeholder_count, errors = 0, 0, []

    for i, item in enumerate(items):
        if any(_is_placeholder_value(v) for v in item.values() if isinstance(v, str)):
            placeholder_count += 1
            continue
        try:
            RedFlagRule(**item)
            found += 1
        except (ValidationError, TypeError) as e:
            errors.append(f"Item {i} ({item.get('symptom','?')[:40]}): {e}")

    if placeholder_count == len(items) and len(items) > 0:
        return FileReport(
            path=rel,
            status=DataStatus.PLACEHOLDER,
            details="All red-flag items are placeholders.",
            items_placeholder=placeholder_count,
        )

    status = DataStatus.MALFORMED if errors else DataStatus.OK
    return FileReport(
        path=rel,
        status=status,
        details=(
            f"{found} red-flag rule(s) validated. "
            f"{placeholder_count} placeholder(s). "
            f"{len(errors)} error(s)."
        ),
        items_found=found,
        items_placeholder=placeholder_count,
        items_invalid=len(errors),
        errors=errors,
    )


def _validate_pathways_file() -> FileReport:
    """Validate pathways.yaml — each entry against PathwayEntry schema."""
    rel = str(PATHWAYS_FILE.relative_to(REPO_ROOT))
    if not PATHWAYS_FILE.exists():
        return FileReport(
            path=rel,
            status=DataStatus.MISSING,
            details="File not found. Populate from official sources (NCS, SSC, UPSC, etc.).",
        )
    try:
        data = _load_yaml(PATHWAYS_FILE)
    except Exception as e:
        return FileReport(
            path=rel,
            status=DataStatus.MALFORMED,
            details=f"YAML parse error: {e}",
            errors=[str(e)],
        )

    if isinstance(data, dict) and data.get("_status", "").upper().startswith("PLACEHOLDER"):
        # Check if ALL education levels contain only placeholder entries
        pathways = data.get("pathways", {})
        all_items = [item for items in pathways.values() for item in items]
        all_placeholder = all(
            any(_is_placeholder_value(str(v)) for v in item.values() if isinstance(v, str))
            for item in all_items
        ) if all_items else True

        if all_placeholder:
            return FileReport(
                path=rel,
                status=DataStatus.PLACEHOLDER,
                details=(
                    "All pathway entries are placeholders. "
                    "Populate from official sources (NCS, SSC, UPSC, state PSC, PMKVY). "
                    "Every entry must have a valid source_url."
                ),
                items_placeholder=len(all_items),
            )

    pathways = data.get("pathways", {}) if isinstance(data, dict) else {}
    found, placeholder_count, errors = 0, 0, []
    valid_edu_levels = {e.value for e in Education}

    for level_str, entries in pathways.items():
        if level_str not in valid_edu_levels:
            errors.append(
                f"Unknown education level key '{level_str}'. "
                f"Valid: {sorted(valid_edu_levels)}"
            )
        if not isinstance(entries, list):
            errors.append(f"Level '{level_str}': expected list, got {type(entries).__name__}")
            continue
        for item in entries:
            if any(_is_placeholder_value(str(v)) for v in item.values() if isinstance(v, str)):
                placeholder_count += 1
                continue
            try:
                PathwayEntry(**item)
                found += 1
            except (ValidationError, TypeError) as e:
                errors.append(
                    f"Level '{level_str}', id='{item.get('id','?')}': {e}"
                )

    if placeholder_count > 0 and found == 0:
        return FileReport(
            path=rel,
            status=DataStatus.PLACEHOLDER,
            details=f"All {placeholder_count} pathway entries are placeholders.",
            items_placeholder=placeholder_count,
        )

    status = DataStatus.MALFORMED if errors else DataStatus.OK
    return FileReport(
        path=rel,
        status=status,
        details=(
            f"{found} pathway entry/ies validated across "
            f"{len(pathways)} education level(s). "
            f"{placeholder_count} placeholder(s). "
            f"{len(errors)} error(s)."
        ),
        items_found=found,
        items_placeholder=placeholder_count,
        items_invalid=len(errors),
        errors=errors,
    )


# ── Main entry point ──────────────────────────────────────────────────────────

def load_and_validate() -> DataReport:
    """
    Validate all /data/real/ files.
    Returns a DataReport — never raises, never auto-fills.
    """
    report = DataReport()
    report.files.append(_validate_notices_dir())
    report.files.append(_validate_immunization_file())
    report.files.append(_validate_red_flags_file())
    report.files.append(_validate_pathways_file())
    return report


def print_report(report: DataReport, verbose: bool = False) -> None:
    icons = {
        DataStatus.OK:          "✅",
        DataStatus.PLACEHOLDER: "🔶",
        DataStatus.MISSING:     "❌",
        DataStatus.MALFORMED:   "🔴",
    }
    print()
    print("━" * 60)
    print("  AccessAI — /data/real/ Validation Report")
    print("━" * 60)
    for fr in report.files:
        icon = icons[fr.status]
        print(f"\n{icon} [{fr.status}]  {fr.path}")
        print(f"   {fr.details}")
        if fr.items_found:
            print(f"   Valid items: {fr.items_found}")
        if fr.items_placeholder:
            print(f"   Placeholders: {fr.items_placeholder}")
        if fr.items_invalid:
            print(f"   Invalid: {fr.items_invalid}")
        if verbose and fr.errors:
            for err in fr.errors:
                print(f"   ⚠ {err}")
    print()
    print("━" * 60)
    print(f"  {report.summary()}")
    if report.blocking_files:
        print()
        print("  ⚠ The following files must be populated before the system")
        print("    can serve real data (run `python shared/data_loader.py` for details):")
        for bf in report.blocking_files:
            print(f"    • {bf.path}  [{bf.status}]")
    print("━" * 60)
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate /data/real/ files and report status."
    )
    parser.add_argument(
        "--json", action="store_true", help="Output machine-readable JSON"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show individual error messages"
    )
    args = parser.parse_args()

    if not _YAML_AVAILABLE:
        print("ERROR: PyYAML not installed. Run: pip install pyyaml")
        sys.exit(1)

    report = load_and_validate()

    if args.json:
        output = {
            "summary": report.summary(),
            "all_ok": report.all_ok,
            "files": [
                {
                    "path": f.path,
                    "status": f.status.value,
                    "details": f.details,
                    "items_found": f.items_found,
                    "items_placeholder": f.items_placeholder,
                    "items_invalid": f.items_invalid,
                    "errors": f.errors,
                }
                for f in report.files
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        print_report(report, verbose=args.verbose)

    # Exit 1 if any file is MISSING or MALFORMED (not just PLACEHOLDER)
    bad = [
        f for f in report.files
        if f.status in (DataStatus.MISSING, DataStatus.MALFORMED)
    ]
    sys.exit(1 if bad else 0)
