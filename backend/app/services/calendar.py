"""The combined calendar feed.

For a date range it merges five sources, none of which is copied into
calendar_events:
  - the student's own events (recurrences expanded),
  - events other students shared with them (accepted or still pending),
  - the student's own assignments,
  - class meetings from committed schedules (repeated weekly over the term),
  - course assignments from committed schedules, with the student's score.
"""

from datetime import datetime, time

from ..errors import bad_request, parse_date
from ..logic.recurrence import expand_event, expand_weekly_meeting
from ..repositories import coursework as coursework_repo
from ..repositories import events as events_repo
from . import homework
from .enrollment import course_code, enrolled_sections, offerings
from .events import serialize

MAX_RANGE_DAYS = 100


def feed(user_id, start, end):
    """Everything overlapping [start, end); both are ISO date strings."""
    start = parse_date(start, "start")
    end = parse_date(end, "end")
    if end <= start:
        raise bad_request("'end' must be after 'start'")
    if (end - start).days > MAX_RANGE_DAYS:
        raise bad_request(f"Range can be at most {MAX_RANGE_DAYS} days")
    range_start = datetime.combine(start, time.min)
    range_end = datetime.combine(end, time.min)

    items = []
    items += _own_event_items(user_id, range_start, range_end)
    items += _shared_items(user_id, range_start, range_end)
    items += _task_items(user_id, range_start, range_end)
    sections = enrolled_sections(user_id)
    items += _class_items(sections, range_start, range_end)
    items += _assignment_items(user_id, sections, range_start, range_end)
    items.sort(key=lambda i: (i["start"], i["type"] != "event"))
    return items


def _expand(event, range_start, range_end, **extra):
    """Calendar items for each occurrence of an event row in the range."""
    items = []
    for occ_start, occ_end in expand_event(event, range_start, range_end):
        items.append({
            "type": "event",
            "id": f"event-{event['id']}-{occ_start.isoformat()}",
            "title": event["title"],
            "start": occ_start,
            "end": occ_end,
            "all_day": event["all_day"],
            "color": event["color"],
            "location": event["location"],
            "description": event["description"],
            "recurring": event["recurrence_freq"] is not None,
            "event": event,
            **extra,
        })
    return items


def _own_event_items(user_id, range_start, range_end):
    rows = events_repo.owned_in_range(user_id, range_start, range_end)
    guests = events_repo.guest_counts([r["id"] for r in rows])
    items = []
    for event in rows:
        serialize(event)
        items += _expand(event, range_start, range_end, guest_count=guests.get(event["id"], 0))
    return items


def _shared_items(user_id, range_start, range_end):
    items = []
    for row in events_repo.shared_in_range(user_id, range_start, range_end):
        extra = {
            "type": "shared",
            "invitation_id": row.pop("invitation_id"),
            "invitation_status": row.pop("invitation_status"),
            "owner_name": row.pop("owner_name"),
        }
        items += [dict(item, id=f"shared-{item['id']}") for item in
                  _expand(serialize(row), range_start, range_end, **extra)]
    return items


def _task_items(user_id, range_start, range_end):
    return [{
        "type": "task",
        "id": f"task-{a['id']}",
        "task_id": a["id"],
        "title": a["title"],
        "start": a["due_at"],
        "end": a["due_at"],
        "all_day": False,
        "completed": a["completed"],
        "course_id": a["course_id"],
        "term_id": a["term_id"],
        "course_code": a["course_code"],
        "notes": a["notes"],
        "task": a,
    } for a in homework.due_between(user_id, range_start, range_end)]


def _class_items(sections, range_start, range_end):
    items = []
    for s in sections:
        code = course_code(s)
        for m in s["meetings"]:
            for occ_start, occ_end in expand_weekly_meeting(
                m["day_of_week"], m["start_time"], m["end_time"],
                s["term_start"], s["term_end"], range_start, range_end,
            ):
                items.append({
                    "type": "class",
                    "id": f"class-{m['id']}-{occ_start.date().isoformat()}",
                    "title": f"{code} {m['kind']}",
                    "start": occ_start,
                    "end": occ_end,
                    "all_day": False,
                    "course_id": s["course_id"],
                    "course_code": code,
                    "course_title": s["title"],
                    "section_code": s["section_code"],
                    "instructor": s["instructor"],
                    "location": s["location"],
                    "term_id": s["term_id"],
                })
    return items


def _assignment_items(user_id, sections, range_start, range_end):
    by_offering = offerings(sections)
    items = []
    for a in coursework_repo.scored_due_between(user_id, by_offering, range_start, range_end):
        s = by_offering[(a["course_id"], a["term_id"])]
        items.append({
            "type": "assignment",
            "id": f"assignment-{a['id']}",
            "assignment_id": a["id"],
            "title": a["title"],
            "start": a["due_at"],
            "end": a["due_at"],
            "all_day": False,
            "category": a["category"],
            "course_id": a["course_id"],
            "term_id": a["term_id"],
            "course_code": course_code(s),
            "max_points": a["max_points"],
            "score": a["score"],
        })
    return items
