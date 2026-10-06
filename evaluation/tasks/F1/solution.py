"""Initial candidate provided identically to both comparison conditions."""
def summarize(rows):
    groups = {}
    rejected = 0
    for row in rows:
        try:
            value, weight = float(row["value"]), float(row["weight"])
        except (ValueError, KeyError):
            rejected += 1
            continue
        groups.setdefault(row["group"], []).append((value, weight))
    result = {}
    for group, values in groups.items():
        total = sum(w for _, w in values)
        mean = sum(v * w for v, w in values) / total
        result[group] = {"count": len(values), "weight": total, "mean": mean,
                         "variance": sum(v * v * w for v, w in values) / total - mean * mean}
    return {"groups": result, "rejected": rejected}
