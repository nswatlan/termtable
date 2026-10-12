"""Homework tracking: assignments a student adds themselves, which they can
mark complete or delete, plus a combined to-do list with the course-provided
assignments from their committed schedules."""

from datetime import datetime, time, timedelta

from ..db import commit
from ..errors import bad_request, not_found, optional_str, parse_date, parse_datetime, require_object, require_str
from ..repositories import coursework as coursework_repo
from ..repositories import homework as homework_repo
from .enrollment import course_code, enrolled_sections, offerings


def serialize(row):
    row["completed"] = bool(row["completed"])
    row["course_code"] = f"{row['department']} {row['number']}" if row["course_id"] else None
    return row


def _owned(assignment_id, user_id):
    row = homework_repo.get(assignment_id, user_id)
    if row is None:
        raise not_found("Assignment")
    return serialize(row)


def _parse_course(user_id, data):
    """Optional link to a class the student is taking: course_id + term_id."""
    course_id, term_id = data.get("course_id"), data.get("term_id")
    if course_id in (None, "") and term_id in (None, ""):
        return None, None
    if not isinstance(course_id, int) or not isinstance(term_id, int):
        raise bad_request("'course_id' and 'term_id' must both be given as numbers")
    if not any(s["course_id"] == course_id for s in enrolled_sections(user_id, [term_id])):
        raise bad_request("Pick a class from your committed schedule")
    return course_id, term_id


def list_mine(user_id, include_completed=False):
    rows = homework_repo.list_all(user_id) if include_completed else homework_repo.list_incomplete(user_id)
    return [serialize(r) for r in rows]


def due_between(user_id, start, end):
    return [serialize(r) for r in homework_repo.list_due_between(user_id, start, end)]


def create(user_id, body):
    data = require_object(body)
    title = require_str(data, "title", max_len=200)
    due_at = parse_datetime(data.get("due_at"), "due_at")
    course_id, term_id = _parse_course(user_id, data)
    new_id = homework_repo.create(user_id, course_id, term_id, title, due_at,
                                  optional_str(data, "notes", max_len=5000))
    commit()
    return _owned(new_id, user_id)


def update(assignment_id, user_id, body):
    """Change any of title, due_at, notes, course, completed."""
    _owned(assignment_id, user_id)
    data = require_object(body)
    changes = {}
    if "title" in data:
        changes["title"] = require_str(data, "title", max_len=200)
    if "due_at" in data:
        changes["due_at"] = parse_datetime(data.get("due_at"), "due_at")
    if "notes" in data:
        changes["notes"] = optional_str(data, "notes", max_len=5000)
    if "course_id" in data or "term_id" in data:
        changes["course_id"], changes["term_id"] = _parse_course(user_id, data)
    if "completed" in data:
        if not isinstance(data["completed"], bool):
            raise bad_request("'completed' must be true or false")
        changes["completed"] = data["completed"]
        changes["completed_at"] = datetime.now().replace(microsecond=0) if data["completed"] else None
    if changes:
        homework_repo.update(assignment_id, user_id, changes)
        commit()
    return _owned(assignment_id, user_id)


def delete(assignment_id, user_id):
    _owned(assignment_id, user_id)
    homework_repo.delete(assignment_id, user_id)
    commit()


def todo_list(user_id, from_date=None):
    """Everything due from `from_date` (default: a week ago) onward: course
    assignments from committed schedules (with the student's score) and the
    student's own assignments. Also lists the classes an own assignment can
    be linked to."""
    start = parse_date(from_date, "from") if from_date else datetime.now().date() - timedelta(days=7)
    since = datetime.combine(start, time.min)

    sections = enrolled_sections(user_id)
    by_offering = offerings(sections)
    course_items = coursework_repo.scored_due_since(user_id, by_offering, since)
    for a in course_items:
        a["course_code"] = course_code(by_offering[(a["course_id"], a["term_id"])])

    return {
        "course_assignments": course_items,
        "my_assignments": [serialize(r) for r in homework_repo.list_since_or_incomplete(user_id, since)],
        "classes": [
            {"course_id": s["course_id"], "term_id": s["term_id"], "term_name": s["term_name"],
             "course_code": course_code(s), "title": s["title"]}
            for s in sorted(sections, key=lambda s: (s["term_start"], s["department"], s["number"]))
        ],
    }
