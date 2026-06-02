from core.models import Leftover
from data.leftovers_repository import (
    add_leftover,
    delete_leftovers_by_ids,
    load_leftovers,
)


def apply_leftovers_result(
    consumed_leftover_ids: list[str],
    new_leftovers: list[Leftover],
) -> dict:
    deleted = 0
    added = 0

    if consumed_leftover_ids:
        deleted = delete_leftovers_by_ids(consumed_leftover_ids)

    for leftover in new_leftovers:
        add_leftover(leftover)
        added += 1

    total = len(load_leftovers())

    return {
        "deleted": deleted,
        "added": added,
        "total": total,
    }