"""Weighted CSV summaries with strict validation and exact centered moments."""

from fractions import Fraction
from math import isfinite


def summarize(rows):
    groups = {}
    rejected = 0
    for row in rows:
        group = row.get("group")
        if not isinstance(group, str) or not group.strip():
            rejected += 1
            continue
        group = group.strip()
        try:
            value = float(row["value"])
            weight = float(row["weight"])
        except (KeyError, TypeError, ValueError, OverflowError):
            rejected += 1
            continue
        if not isfinite(value) or not isfinite(weight) or weight <= 0:
            rejected += 1
            continue

        value_exact = Fraction.from_float(value)
        weight_exact = Fraction.from_float(weight)
        if group not in groups:
            groups[group] = [value_exact, 0, Fraction(0), Fraction(0), Fraction(0)]
        state = groups[group]
        delta = value_exact - state[0]
        state[1] += 1
        state[2] += weight_exact
        state[3] += weight_exact * delta
        state[4] += weight_exact * delta * delta

    result = {}
    for group, (anchor, count, total, weighted_delta, weighted_square) in groups.items():
        mean_delta = weighted_delta / total
        # Exact centered moments avoid loss from a large shared offset.
        variance = weighted_square / total - mean_delta * mean_delta
        result[group] = {
            "count": count,
            "weight": float(total),
            "mean": float(anchor + mean_delta),
            "variance": float(variance),
        }
    return {"groups": result, "rejected": rejected}
