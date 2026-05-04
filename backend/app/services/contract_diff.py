"""Contract diff between two ProjectVersion schema_snapshots.

Spec §7.3 defines breaking vs non-breaking output-contract changes:
- breaking: field removed, type changed, required tightened (false→true),
  enum narrowed, required field added
- non_breaking: description edited, optional field added, required loosened
  (true→false), enum widened, examples changed

Top-level output contract changes (e.g. dropping array<object>) are not
allowed in v1; the schema_snapshot shape itself is fixed.
"""
from __future__ import annotations

from typing import Any

from app.schemas.contract_diff import ContractDiffItem, ContractDiffOut


def _by_name(snapshot: list[dict]) -> dict[str, dict]:
    return {f.get("name"): f for f in snapshot if isinstance(f, dict) and f.get("name")}


def _is_required(field: dict) -> bool:
    # Default required=True in SchemaField; mirror that for diffs from raw JSON.
    return bool(field.get("required", True))


def _enum(field: dict) -> list[str] | None:
    e = field.get("enum")
    return list(e) if isinstance(e, list) else None


def diff_schema_snapshots(
    old_snapshot: list[dict] | None,
    new_snapshot: list[dict] | None,
) -> ContractDiffOut:
    old = _by_name(old_snapshot or [])
    new = _by_name(new_snapshot or [])
    items: list[ContractDiffItem] = []

    for name, old_f in old.items():
        if name not in new:
            items.append(
                ContractDiffItem(
                    kind="field_removed",
                    severity="breaking",
                    field_name=name,
                    before=old_f,
                    after=None,
                    message=f"field '{name}' removed from contract",
                )
            )
            continue

        new_f = new[name]
        old_type = old_f.get("type")
        new_type = new_f.get("type")
        if old_type != new_type:
            items.append(
                ContractDiffItem(
                    kind="type_changed",
                    severity="breaking",
                    field_name=name,
                    before=old_type,
                    after=new_type,
                    message=f"field '{name}' type changed: {old_type} -> {new_type}",
                )
            )

        old_req = _is_required(old_f)
        new_req = _is_required(new_f)
        if not old_req and new_req:
            items.append(
                ContractDiffItem(
                    kind="required_tightened",
                    severity="breaking",
                    field_name=name,
                    before=False,
                    after=True,
                    message=f"field '{name}' became required",
                )
            )
        elif old_req and not new_req:
            items.append(
                ContractDiffItem(
                    kind="required_loosened",
                    severity="non_breaking",
                    field_name=name,
                    before=True,
                    after=False,
                    message=f"field '{name}' is now optional",
                )
            )

        old_enum = _enum(old_f)
        new_enum = _enum(new_f)
        if old_enum is not None and new_enum is not None:
            old_set = set(old_enum)
            new_set = set(new_enum)
            removed = old_set - new_set
            added = new_set - old_set
            if removed:
                items.append(
                    ContractDiffItem(
                        kind="enum_narrowed",
                        severity="breaking",
                        field_name=name,
                        before=sorted(old_set),
                        after=sorted(new_set),
                        message=f"field '{name}' enum dropped: {sorted(removed)}",
                    )
                )
            elif added:
                items.append(
                    ContractDiffItem(
                        kind="enum_widened",
                        severity="non_breaking",
                        field_name=name,
                        before=sorted(old_set),
                        after=sorted(new_set),
                        message=f"field '{name}' enum widened: +{sorted(added)}",
                    )
                )
        elif old_enum is None and new_enum is not None:
            # Adding an enum constraint where none existed narrows allowed values.
            items.append(
                ContractDiffItem(
                    kind="enum_narrowed",
                    severity="breaking",
                    field_name=name,
                    before=None,
                    after=sorted(set(new_enum)),
                    message=f"field '{name}' gained an enum constraint",
                )
            )
        elif old_enum is not None and new_enum is None:
            items.append(
                ContractDiffItem(
                    kind="enum_widened",
                    severity="non_breaking",
                    field_name=name,
                    before=sorted(set(old_enum)),
                    after=None,
                    message=f"field '{name}' enum constraint dropped",
                )
            )

        if old_f.get("description") != new_f.get("description"):
            items.append(
                ContractDiffItem(
                    kind="description_changed",
                    severity="non_breaking",
                    field_name=name,
                    before=old_f.get("description"),
                    after=new_f.get("description"),
                    message=f"field '{name}' description edited",
                )
            )

    for name, new_f in new.items():
        if name in old:
            continue
        if _is_required(new_f):
            items.append(
                ContractDiffItem(
                    kind="required_field_added",
                    severity="breaking",
                    field_name=name,
                    before=None,
                    after=new_f,
                    message=f"required field '{name}' added",
                )
            )
        else:
            items.append(
                ContractDiffItem(
                    kind="optional_field_added",
                    severity="non_breaking",
                    field_name=name,
                    before=None,
                    after=new_f,
                    message=f"optional field '{name}' added",
                )
            )

    has_breaking = any(i.severity == "breaking" for i in items)
    return ContractDiffOut(
        has_breaking_changes=has_breaking,
        items=items,
    )
