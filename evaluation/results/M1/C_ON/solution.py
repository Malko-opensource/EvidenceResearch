"""Summarize the latest valid measurement for each normalized event id."""
from fractions import Fraction
import math


def summarize(rows):
    latest = {}
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
        previous = latest.get(event_id)
        if previous is None or timestamp >= previous[0]:
            latest[event_id] = (timestamp, group, value)

    totals = {}
    for timestamp, group, value in latest.values():
        count, total = totals.get(group, (0, Fraction(0)))
        totals[group] = (count + 1, total + Fraction.from_float(value))
    groups = {
        group: {"count": count, "mean": float(total / count)}
        for group, (count, total) in totals.items()
    }
    return {"groups": groups, "rejected": rejected, "duplicates": valid_count - len(latest)}
