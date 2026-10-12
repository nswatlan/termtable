"""Homework tracking: assignments a student adds themselves, which they can
mark complete or delete, plus a combined to-do list with the course-provided
assignments from their committed schedules. Both kinds appear on the calendar.
"""

from datetime import datetime, time, timedelta

from flask import Blueprint, g, request

from .auth import login_required
from .db import commit, execute, query
from .enrollment import enrolled_sections
from .errors import bad_request, json_body, not_found, optional_str, parse_date, parse_datetime, require_str

bp = Blueprint("homework", __name__)

FIELDS = """ua.id, ua.title, ua.due_at, ua.notes, ua.completed, ua.completed_at,
            ua.course_id, ua.term_id, c.department, c.number, c.title AS course_title"""


def _serialize(row):
    row["completed"] = bool(row["completed"])
    row["course_code"] = f"{row['department']} {row['number']}" if row["course_id"] else None
    return row


def user_assignments(user_id, where="TRUE", args=()):
    rows = query(
        f"""SELECT {FIELDS} FROM user_assignments ua
            LEFT JOIN courses c ON c.id = ua.course_id
            WHERE ua.user_id = %s AND {where}
            ORDER BY ua.due_at, ua.id""",
        (user_id, *args),
    )
    return [_serialize(r) for r in rows]


def _own(assignment_id):
    rows = user_assignments(g.user["id"], "ua.id = %s", (assignment_id,))
    if not rows:
        raise not_found("Assignment")
    return rows[0]


def _parse_course(data):
    """Optional link to a class the student is taking: course_id + term_id."""
    course_id, term_id = data.get("course_id"), data.get("term_id")
    if course_id in (None, "") and term_id in (None, ""):
        return None, None
    if not isinstance(course_id, int) or not isinstance(term_id, int):
        raise bad_request("'course_id' and 'term_id' must both be given as numbers")
    if not any(s["course_id"] == course_id for s in enrolled_sections(g.user["id"], [term_id])):
        raise bad_request("Pick a class from your committed schedule")
    return course_id, term_id


@bp.get("/my-assignments")
@login_required
def list_mine():
    if request.args.get("include_completed") in ("1", "true"):
        return user_assignments(g.user["id"])
    return user_assignments(g.user["id"], "NOT ua.completed")


@bp.post("/my-assignments")
@login_required
def create_mine():
    data = json_body()
    title = require_str(data, "title", max_len=200)
    due_at = parse_datetime(data.get("due_at"), "due_at")
    course_id, term_id = _parse_course(data)
    new_id = execute(
        """INSERT INTO user_assignments (user_id, course_id, term_id, title, due_at, notes)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (g.user["id"], course_id, term_id, title, due_at, optional_str(data, "notes", max_len=5000)),
    )
    commit()
    return _own(new_id), 201


@bp.patch("/my-assignments/<int:assignment_id>")
@login_required
def update_mine(assignment_id):
    _own(assignment_id)
    data = json_body()
    changes = {}
    if "title" in data:
        changes["title"] = require_str(data, "title", max_len=200)
    if "due_at" in data:
        changes["due_at"] = parse_datetime(data.get("due_at"), "due_at")
    if "notes" in data:
        changes["notes"] = optional_str(data, "notes", max_len=5000)
    if "course_id" in data or "term_id" in data:
        changes["course_id"], changes["term_id"] = _parse_course(data)
    if "completed" in data:
        if not isinstance(data["completed"], bool):
            raise bad_request("'completed' must be true or false")
        changes["completed"] = data["completed"]
        changes["completed_at"] = datetime.now().replace(microsecond=0) if data["completed"] else None
    if changes:
        execute(
            f"UPDATE user_assignments SET {', '.join(f'{k} = %s' for k in changes)} WHERE id = %s AND user_id = %s",
            (*changes.values(), assignment_id, g.user["id"]),
        )
        commit()
    return _own(assignment_id)


@bp.delete("/my-assignments/<int:assignment_id>")
@login_required
def delete_mine(assignment_id):
    _own(assignment_id)
    execute("DELETE FROM user_assignments WHERE id = %s AND user_id = %s", (assignment_id, g.user["id"]))
    commit()
    return {"ok": True}


@bp.get("/homework")
@login_required
def todo_list():
    """Everything due from `from` (default: a week ago) onward: course
    assignments from committed schedules (with the student's score) and the
    student's own assignments. Also lists the classes an own assignment can
    be linked to."""
    start = parse_date(request.args["from"], "from") if request.args.get("from") else (
        datetime.now().date() - timedelta(days=7))
    since = datetime.combine(start, time.min)

    sections = enrolled_sections(g.user["id"])
    offerings = {(s["course_id"], s["term_id"]): s for s in sections}
    course_items = []
    if offerings:
        pairs = list(offerings)
        placeholders = ", ".join(["(%s, %s)"] * len(pairs))
        rows = query(
            f"""SELECT a.id, a.course_id, a.term_id, a.title, a.category, a.due_at, a.max_points, gr.score
                FROM assignments a
                LEFT JOIN grades gr ON gr.assignment_id = a.id AND gr.user_id = %s
                WHERE (a.course_id, a.term_id) IN ({placeholders}) AND a.due_at >= %s
                ORDER BY a.due_at, a.id LIMIT 300""",
            (g.user["id"], *[v for p in pairs for v in p], since),
        )
        for a in rows:
            s = offerings[(a["course_id"], a["term_id"])]
            a["course_code"] = f"{s['department']} {s['number']}"
            course_items.append(a)

    return {
        "course_assignments": course_items,
        "my_assignments": user_assignments(
            g.user["id"], "(ua.due_at >= %s OR NOT ua.completed)", (since,)),
        "classes": [
            {"course_id": s["course_id"], "term_id": s["term_id"], "term_name": s["term_name"],
             "course_code": f"{s['department']} {s['number']}", "title": s["title"]}
            for s in sorted(sections, key=lambda s: (s["term_start"], s["department"], s["number"]))
        ],
    }
