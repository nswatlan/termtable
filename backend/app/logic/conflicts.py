"""Time-conflict detection for a schedule's sections."""

from itertools import combinations


def find_conflicts(meetings):
    """Find overlapping meetings that belong to different sections.

    meetings: iterable of dicts with "section_id", "day_of_week" and
    "start_time"/"end_time" (anything mutually comparable: time, timedelta,
    minutes). Back-to-back meetings (one ends exactly when the next starts)
    do not conflict.

    Returns a list of dicts, one per conflicting pair of meetings:
        {"section_ids": [a, b], "day_of_week": d, "start": ..., "end": ...}
    where start/end bound the overlapping window.
    """
    by_day = {}
    for m in meetings:
        by_day.setdefault(m["day_of_week"], []).append(m)

    conflicts = []
    for day in sorted(by_day):
        for a, b in combinations(by_day[day], 2):
            if a["section_id"] == b["section_id"]:
                continue
            if a["start_time"] < b["end_time"] and b["start_time"] < a["end_time"]:
                conflicts.append({
                    "section_ids": sorted([a["section_id"], b["section_id"]]),
                    "day_of_week": day,
                    "start": max(a["start_time"], b["start_time"]),
                    "end": min(a["end_time"], b["end_time"]),
                })
    return conflicts


def conflicting_section_ids(conflicts):
    return sorted({sid for c in conflicts for sid in c["section_ids"]})
