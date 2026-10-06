"""Select the latest valid measurement per event and summarize its group."""

import math
import statistics


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

    groups = {}
    for _, group, value in retained.values():
        groups.setdefault(group, []).append(value)

    return {
        "groups": {
            group: {"count": len(values), "mean": statistics.mean(values)}
            for group, values in groups.items()
        },
        "rejected": rejected,
        "duplicates": valid_count - len(retained),
    }

