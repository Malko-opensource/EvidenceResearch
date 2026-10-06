"""Validate CSV measurements and calculate stable weighted summaries."""
import math
from fractions import Fraction


def summarize(rows):
    groups = {}
    rejected = 0
    for row in rows:
        group = row.get("group")
        if not isinstance(group, str) or not group.strip():
            rejected += 1
            continue
        try:
            value = float(row["value"])
            weight = float(row["weight"])
        except (KeyError, TypeError, ValueError, OverflowError):
            rejected += 1
            continue
        if not math.isfinite(value) or not math.isfinite(weight) or weight <= 0:
            rejected += 1
            continue
        groups.setdefault(group.strip(), []).append(
            (Fraction.from_float(value), Fraction.from_float(weight))
        )

    result = {}
    for group, values in groups.items():
        total = sum(weight for _, weight in values)
        origin = values[0][0]
        delta = sum(weight * (value - origin) for value, weight in values) / total
        mean = origin + delta
        variance = sum(
            weight * ((value - origin) - delta) ** 2 for value, weight in values
        ) / total
        result[group] = {
            "count": len(values),
            "weight": float(total),
            "mean": float(mean),
            "variance": float(variance),
        }
    return {"groups": result, "rejected": rejected}
