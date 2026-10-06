def summarize(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row["group"], []).append(float(row["value"]))
    return {"groups": {group: sum(values) / len(values) for group, values in groups.items()}}
