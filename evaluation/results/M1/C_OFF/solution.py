"""Summarize valid CSV event rows without changing the input."""
import math
from fractions import Fraction


def summarize(rows):
    selected = {}
    rejected = 0
    valid_rows = 0
    for row in rows:
        try:
            event_id = row["event_id"].strip()
            group = row["group"].strip()
            timestamp = float(row["timestamp"])
            value = float(row["value"])
        except (KeyError, AttributeError, TypeError, ValueError, OverflowError):
            rejected += 1
            continue
        if not event_id or not group or not math.isfinite(timestamp) or not math.isfinite(value):
            rejected += 1
            continue
        valid_rows += 1
        previous = selected.get(event_id)
        if previous is None or timestamp >= previous[0]:
            selected[event_id] = (timestamp, group, value)

    totals = {}
    counts = {}
    for _, group, value in selected.values():
        counts[group] = counts.get(group, 0) + 1
        totals[group] = totals.get(group, Fraction(0)) + Fraction.from_float(value)
    groups = {
        group: {"count": counts[group], "mean": float(total / counts[group])}
        for group, total in totals.items()
    }
    return {"groups": groups, "rejected": rejected, "duplicates": valid_rows - len(selected)}
