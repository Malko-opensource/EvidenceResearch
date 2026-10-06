"""Summarize all finite measurements in strict three-second windows."""
import math
from fractions import Fraction


def summarize(rows):
    measurements = []
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
        measurements.append((timestamp, Fraction(value)))

    measurements.sort(key=lambda measurement: measurement[0])
    samples = []
    left = 0
    end = 0
    total = Fraction(0)
    while end < len(measurements):
        timestamp = measurements[end][0]
        next_end = end
        while next_end < len(measurements) and measurements[next_end][0] == timestamp:
            total += measurements[next_end][1]
            next_end += 1

        cutoff = timestamp - 3.0
        while left < end and measurements[left][0] <= cutoff:
            total -= measurements[left][1]
            left += 1
        count = next_end - left
        samples.append({
            "timestamp": timestamp,
            "count": count,
            "mean": float(total / count),
        })
        end = next_end

    return {"samples": samples, "rejected": rejected}
