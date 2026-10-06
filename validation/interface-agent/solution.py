def summarize(rows):
    totals = {}
    counts = {}
    for row in rows:
        group = row["group"]
        totals[group] = totals.get(group, 0.0) + float(row["value"])
        counts[group] = counts.get(group, 0) + 1
    return {"groups": {group: total / counts[group] for group, total in totals.items()}}
