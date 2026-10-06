"""Summarize valid events without mutating the input rows."""

import math
from fractions import Fraction


def summarize(rows):
    retained = {}
    rejected = 0
    valid_count = 0

    for row in rows:
        try:
            event_id = row["event_id"].strip()
            group = row["group"].strip()
            timestamp = float(row["timestamp"])
            value = float(row["value"])
        except (KeyError, ValueError, TypeError, AttributeError, OverflowError):
            rejected += 1
            continue

        if not event_id or not group or not math.isfinite(timestamp) or not math.isfinite(value):
            rejected += 1
            continue

        valid_count += 1
        previous = retained.get(event_id)
        if previous is None or timestamp >= previous[0]:
            retained[event_id] = (timestamp, group, value)

    totals = {}
    counts = {}
    for _, group, value in retained.values():
        totals[group] = totals.get(group, Fraction(0)) + Fraction.from_float(value)
        counts[group] = counts.get(group, 0) + 1

    groups = {
        group: {"count": count, "mean": float(totals[group] / count)}
        for group, count in counts.items()
    }
    return {
        "groups": groups,
        "rejected": rejected,
        "duplicates": valid_count - len(retained),
    }

