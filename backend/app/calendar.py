"""Personal calendar: the student's own events, events other students shared
with them, their own assignments, and, from their committed schedules,
recurring class meetings and assignment due dates.

Class meetings and assignments are not copied into calendar_events. They are
read live from sections/meeting_times/assignments, so the assignment on the
calendar is the same row the gradebook grades.
"""

from datetime import datetime, time, timedelta

from flask import Blueprint, g, request

from .auth import login_required
from .db import commit, execute, in_clause, query, query_one
from .enrollment import enrolled_sections
from .errors import (bad_request, json_body, not_found, optional_str, parse_date,
                     parse_datetime, require_int, require_str)
from .logic.recurrence import (FREQUENCIES, expand_event, expand_weekly_meeting,
                               format_weekdays, parse_weekdays)

bp = Blueprint("calendar", __name__)

COLORS = ("blue", "green", "red", "yellow", "purple", "orange", "teal", "gray")
MAX_RANGE_DAYS = 100
EVENT_FIELDS = """id, title, description, location, color, start_at, end_at, all_day,
                  recurrence_freq, recurrence_interval, recurrence_days, recurrence_until"""


def _serialize_event(row):
    row["all_day"] = bool(row["all_day"])
    return row


def _own_event(event_id):
    event = query_one(
        f"SELECT {EVENT_FIELDS} FROM calendar_events WHERE id = %s AND user_id = %s",
        (event_id, g.user["id"]),
    )
    if event is None:
        raise not_found("Event")
    return _serialize_event(event)


# --- the combined feed ----------------------------------------------------

@bp.get("/calendar")
@login_required
def calendar_feed():
    """Everything on the student's calendar overlapping [start, end).
    start/end are ISO dates; end is exclusive."""
    start = parse_date(request.args.get("start"), "start")
    end = parse_date(request.args.get("end"), "end")
    if end <= start:
        raise bad_request("'end' must be after 'start'")
    if (end - start).days > MAX_RANGE_DAYS:
        raise bad_request(f"Range can be at most {MAX_RANGE_DAYS} days")
    range_start = datetime.combine(start, time.min)
    range_end = datetime.combine(end, time.min)

    items = []
    items += _personal_items(range_start, range_end)
    items += _shared_items(range_start, range_end)
    items += _task_items(range_start, range_end)
    sections = enrolled_sections(g.user["id"])
    items += _class_items(sections, range_start, range_end)
    items += _assignment_items(sections, range_start, range_end)
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


def _shared_items(range_start, range_end):
    """Other students' events I accepted (or haven't answered yet)."""
    fields = ", ".join("e." + f.strip() for f in EVENT_FIELDS.split(","))
    rows = query(
        f"""SELECT {fields}, i.id AS invitation_id, i.status AS invitation_status,
                   o.display_name AS owner_name
            FROM event_invitations i
            JOIN calendar_events e ON e.id = i.event_id
            JOIN users o ON o.id = e.user_id
            WHERE i.invitee_id = %s AND i.status IN ('accepted', 'pending')
              AND e.start_at < %s AND (e.end_at > %s OR e.recurrence_freq IS NOT NULL)""",
        (g.user["id"], range_end, range_start),
    )
    items = []
    for row in rows:
        extra = {
            "type": "shared",
            "invitation_id": row.pop("invitation_id"),
            "invitation_status": row.pop("invitation_status"),
            "owner_name": row.pop("owner_name"),
        }
        items += [dict(item, id=f"shared-{item['id']}") for item in
                  _expand(_serialize_event(row), range_start, range_end, **extra)]
    return items


def _task_items(range_start, range_end):
    """The student's own assignments, shown at their due time."""
    from .homework import user_assignments  # avoid a circular import
    rows = user_assignments(g.user["id"], "ua.due_at >= %s AND ua.due_at < %s", (range_start, range_end))
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
    } for a in rows]


def _personal_items(range_start, range_end):
    # Non-recurring events must overlap the range; recurring ones need only
    # have started before it ends (expand_event handles recurrence_until).
    rows = query(
        f"""SELECT {EVENT_FIELDS} FROM calendar_events
            WHERE user_id = %s AND start_at < %s
              AND (end_at > %s OR recurrence_freq IS NOT NULL)""",
        (g.user["id"], range_end, range_start),
    )
    guests = {}
    if rows:
        ids = [r["id"] for r in rows]
        for row in query(
            f"""SELECT event_id, COUNT(*) AS n FROM event_invitations
                WHERE event_id IN ({in_clause(ids)}) AND status <> 'declined' GROUP BY event_id""",
            tuple(ids),
        ):
            guests[row["event_id"]] = row["n"]
    items = []
    for event in rows:
        _serialize_event(event)
        items += _expand(event, range_start, range_end, guest_count=guests.get(event["id"], 0))
    return items


def _class_items(sections, range_start, range_end):
    items = []
    for s in sections:
        code = f"{s['department']} {s['number']}"
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


def _assignment_items(sections, range_start, range_end):
    offerings = {(s["course_id"], s["term_id"]): s for s in sections}
    if not offerings:
        return []
    pairs = list(offerings)
    placeholders = ", ".join(["(%s, %s)"] * len(pairs))
    rows = query(
        f"""SELECT a.id, a.course_id, a.term_id, a.title, a.category, a.due_at,
                   a.max_points, gr.score
            FROM assignments a
            LEFT JOIN grades gr ON gr.assignment_id = a.id AND gr.user_id = %s
            WHERE (a.course_id, a.term_id) IN ({placeholders})
              AND a.due_at >= %s AND a.due_at < %s""",
        (g.user["id"], *[v for p in pairs for v in p], range_start, range_end),
    )
    items = []
    for a in rows:
        s = offerings[(a["course_id"], a["term_id"])]
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
            "course_code": f"{s['department']} {s['number']}",
            "max_points": a["max_points"],
            "score": a["score"],
        })
    return items


# --- personal event CRUD --------------------------------------------------

def _parse_event(data):
    title = require_str(data, "title", max_len=200)
    all_day = data.get("all_day", False)
    if not isinstance(all_day, bool):
        raise bad_request("'all_day' must be true or false")
    start_at = parse_datetime(data.get("start_at"), "start_at")
    end_at = parse_datetime(data.get("end_at"), "end_at")
    if all_day:
        # All-day events span whole days with an exclusive end.
        start_at = datetime.combine(start_at.date(), time.min)
        end_at = datetime.combine(end_at.date(), time.min)
        if end_at <= start_at:
            end_at = start_at + timedelta(days=1)
    if end_at <= start_at:
        raise bad_request("The event must end after it starts")

    color = data.get("color") or "blue"
    if color not in COLORS:
        raise bad_request(f"'color' must be one of {', '.join(COLORS)}")

    freq = data.get("recurrence_freq") or None
    interval, days, until = 1, None, None
    if freq is not None:
        if freq not in FREQUENCIES:
            raise bad_request("'recurrence_freq' must be DAILY, WEEKLY or MONTHLY")
        if data.get("recurrence_interval") is not None:
            interval = require_int(data, "recurrence_interval", minimum=1, maximum=99)
        if freq == "WEEKLY":
            try:
                weekday_list = parse_weekdays(data.get("recurrence_days"))
            except ValueError as e:
                raise bad_request(str(e))
            if start_at.weekday() not in weekday_list:
                weekday_list.append(start_at.weekday())
            days = format_weekdays(weekday_list)
        if data.get("recurrence_until"):
            until = parse_date(data["recurrence_until"], "recurrence_until")
            if until < start_at.date():
                raise bad_request("The repeat end date must be on or after the start date")

    return {
        "title": title,
        "description": optional_str(data, "description", max_len=5000),
        "location": optional_str(data, "location", max_len=200),
        "color": color,
        "start_at": start_at,
        "end_at": end_at,
        "all_day": all_day,
        "recurrence_freq": freq,
        "recurrence_interval": interval,
        "recurrence_days": days,
        "recurrence_until": until,
    }


@bp.get("/events/<int:event_id>")
@login_required
def get_event(event_id):
    return _own_event(event_id)


@bp.post("/events")
@login_required
def create_event():
    fields = _parse_event(json_body())
    columns = ", ".join(fields)
    event_id = execute(
        f"INSERT INTO calendar_events (user_id, {columns}) VALUES (%s, {in_clause(fields)})",
        (g.user["id"], *fields.values()),
    )
    commit()
    return _own_event(event_id), 201


@bp.put("/events/<int:event_id>")
@login_required
def update_event(event_id):
    _own_event(event_id)
    fields = _parse_event(json_body())
    assignments = ", ".join(f"{k} = %s" for k in fields)
    execute(
        f"UPDATE calendar_events SET {assignments} WHERE id = %s AND user_id = %s",
        (*fields.values(), event_id, g.user["id"]),
    )
    commit()
    return _own_event(event_id)


@bp.delete("/events/<int:event_id>")
@login_required
def delete_event(event_id):
    _own_event(event_id)
    execute("DELETE FROM calendar_events WHERE id = %s AND user_id = %s", (event_id, g.user["id"]))
    commit()
    return {"ok": True}
