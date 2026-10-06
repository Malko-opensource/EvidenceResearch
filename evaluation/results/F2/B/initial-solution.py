"""Initial candidate provided identically to both comparison conditions."""
def summarize(rows):
    seen = []
    samples = []
    rejected = 0
    for row in rows:
        try:
            timestamp, value = float(row["timestamp"]), float(row["value"])
        except (ValueError, KeyError):
            rejected += 1
            continue
        seen.append((timestamp, value))
        window = [v for t, v in seen if timestamp - 3 <= t <= timestamp]
        samples.append({"timestamp": timestamp, "count": len(window),
                        "mean": sum(window) / len(window)})
    return {"samples": samples, "rejected": rejected}
