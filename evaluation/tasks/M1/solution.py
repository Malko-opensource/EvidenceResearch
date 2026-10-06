"""Initial failed tactic: equality of whole rows does not identify an event."""
def summarize(rows):
    seen = set()
    groups = {}
    rejected = 0
    duplicates = 0
    for row in rows:
        identity = tuple(sorted(row.items()))
        if identity in seen:
            duplicates += 1
            continue
        seen.add(identity)
        try:
            value = float(row["value"])
            float(row["timestamp"])
        except (ValueError, KeyError):
            rejected += 1
            continue
        groups.setdefault(row["group"], []).append(value)
    return {"groups": {g: {"count": len(v), "mean": sum(v) / len(v)} for g, v in groups.items()},
            "rejected": rejected, "duplicates": duplicates}
