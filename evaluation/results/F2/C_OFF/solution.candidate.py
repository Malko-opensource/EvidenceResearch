"""Summarize finite observations in strict three-second trailing windows."""
from fractions import Fraction
import math


def summarize(rows):
    valid = []
    rejected = 0
    for row in rows:
        try:
            timestamp = float(row["timestamp"])
            value = float(row["value"])
        except (KeyError, TypeError, ValueError, OverflowError):
            rejected += 1
            continue
        if not math.isfinite(timestamp) or not math.isfinite(value):
            rejected += 1
            continue
        valid.append((timestamp, Fraction.from_float(value)))

    valid.sort(key=lambda observation: observation[0])
    samples = []
    left = 0
    right = 0
    total = Fraction(0)
    while right < len(valid):
        timestamp = valid[right][0]
        while right < len(valid) and valid[right][0] == timestamp:
            total += valid[right][1]
            right += 1
        # Comparing elapsed time preserves the boundary for large timestamps.
        while left < right and timestamp - valid[left][0] >= 3.0:
            total -= valid[left][1]
            left += 1
        count = right - left
        samples.append({
            "timestamp": timestamp,
            "count": count,
            "mean": float(total / count),
        })
    return {"samples": samples, "rejected": rejected}
