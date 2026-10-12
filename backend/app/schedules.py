"""Candidate schedules: named sets of sections a student builds for a term."""

from datetime import datetime

from flask import Blueprint, g, request

from .auth import login_required
from .courses import load_sections, rating_summaries
from .db import commit, execute, in_clause, query, query_one
from .errors import bad_request, json_body, not_found, require_int, require_str
from .logic.conflicts import conflicting_section_ids, find_conflicts

bp = Blueprint("schedules", __name__)


def _own_schedule(schedule_id):
    schedule = query_one(
        """SELECT s.id, s.term_id, s.name, s.is_committed, s.created_at, s.updated_at,
                  t.name AS term_name
           FROM schedules s JOIN terms t ON t.id = s.term_id
           WHERE s.id = %s AND s.user_id = %s""",
        (schedule_id, g.user["id"]),
    )
    if schedule is None:
        raise not_found("Schedule")
    schedule["is_committed"] = bool(schedule["is_committed"])
    return schedule


def _section_ids(schedule_ids):
    """{schedule_id: [section_id, ...]}"""
    result = {sid: [] for sid in schedule_ids}
    if schedule_ids:
        for row in query(
            f"SELECT schedule_id, section_id FROM schedule_sections WHERE schedule_id IN ({in_clause(schedule_ids)})",
            tuple(schedule_ids),
        ):
            result[row["schedule_id"]].append(row["section_id"])
    return result


def _minutes(t):
    return t.hour * 60 + t.minute


def _stats(sections, conflicts, ratings):
    meetings = [m for s in sections for m in s["meetings"]]
    rated = [ratings[s["course_id"]]["avg_rating"] for s in sections
             if ratings[s["course_id"]]["avg_rating"] is not None]
    return {
        "section_count": len(sections),
        "credits": sum(s["credits"] for s in sections),
        "conflict_count": len(conflicts),
        "days": sorted({m["day_of_week"] for m in meetings}),
        "earliest_start": min((m["start_time"] for m in meetings), default=None),
        "latest_end": max((m["end_time"] for m in meetings), default=None),
        "weekly_class_minutes": sum(_minutes(m["end_time"]) - _minutes(m["start_time"]) for m in meetings),
        "avg_course_rating": round(sum(rated) / len(rated), 2) if rated else None,
    }


def _detail(schedule):
    section_ids = _section_ids([schedule["id"]])[schedule["id"]]
    sections = (
        load_sections(f"s.id IN ({in_clause(section_ids)})", tuple(section_ids))
        if section_ids else []
    )
    ratings = rating_summaries(list({s["course_id"] for s in sections}))
    for s in sections:
        s.update(ratings[s["course_id"]])

    conflicts = find_conflicts(m for s in sections for m in s["meetings"])
    in_conflict = set(conflicting_section_ids(conflicts))
    for s in sections:
        s["has_conflict"] = s["id"] in in_conflict

    schedule["sections"] = sections
    schedule["conflicts"] = conflicts
    schedule["stats"] = _stats(sections, conflicts, ratings)
    return schedule


@bp.get("/schedules")
@login_required
def list_schedules():
    term_id = request.args.get("term_id", type=int)
    sql = """SELECT s.id, s.term_id, s.name, s.is_committed, s.created_at, s.updated_at,
                    t.name AS term_name
             FROM schedules s JOIN terms t ON t.id = s.term_id
             WHERE s.user_id = %s"""
    args = [g.user["id"]]
    if term_id:
        sql += " AND s.term_id = %s"
        args.append(term_id)
    sql += " ORDER BY t.start_date, s.created_at"
    schedules = query(sql, tuple(args))
    # Full detail for each: the planner shows the stats in its compare view,
    # and a student only ever has a handful of schedules.
    for s in schedules:
        s["is_committed"] = bool(s["is_committed"])
        _detail(s)
    return schedules


@bp.post("/schedules")
@login_required
def create_schedule():
    data = json_body()
    name = require_str(data, "name", max_len=100)
    copy_from = data.get("copy_from")

    if copy_from is not None:
        source = _own_schedule(require_int(data, "copy_from"))
        term_id = source["term_id"]
    else:
        term_id = require_int(data, "term_id")
        if query_one("SELECT id FROM terms WHERE id = %s", (term_id,)) is None:
            raise bad_request("Unknown term")

    schedule_id = execute(
        "INSERT INTO schedules (user_id, term_id, name) VALUES (%s, %s, %s)",
        (g.user["id"], term_id, name),
    )
    if copy_from is not None:
        execute(
            """INSERT INTO schedule_sections (schedule_id, section_id)
               SELECT %s, section_id FROM schedule_sections WHERE schedule_id = %s""",
            (schedule_id, copy_from),
        )
    commit()
    return _detail(_own_schedule(schedule_id)), 201


@bp.get("/schedules/<int:schedule_id>")
@login_required
def get_schedule(schedule_id):
    return _detail(_own_schedule(schedule_id))


@bp.patch("/schedules/<int:schedule_id>")
@login_required
def rename_schedule(schedule_id):
    _own_schedule(schedule_id)
    name = require_str(json_body(), "name", max_len=100)
    execute("UPDATE schedules SET name = %s WHERE id = %s", (name, schedule_id))
    commit()
    return _detail(_own_schedule(schedule_id))


@bp.delete("/schedules/<int:schedule_id>")
@login_required
def delete_schedule(schedule_id):
    _own_schedule(schedule_id)
    execute("DELETE FROM schedules WHERE id = %s", (schedule_id,))
    commit()
    return {"ok": True}


@bp.post("/schedules/<int:schedule_id>/sections")
@login_required
def add_section(schedule_id):
    schedule = _own_schedule(schedule_id)
    section_id = require_int(json_body(), "section_id")
    section = query_one("SELECT id, course_id, term_id FROM sections WHERE id = %s", (section_id,))
    if section is None:
        raise not_found("Section")
    if section["term_id"] != schedule["term_id"]:
        raise bad_request("That section is offered in a different term than this schedule")

    # A schedule holds at most one section per course: picking a different
    # section of a course swaps it in.
    execute(
        """DELETE ss FROM schedule_sections ss JOIN sections s ON s.id = ss.section_id
           WHERE ss.schedule_id = %s AND s.course_id = %s""",
        (schedule_id, section["course_id"]),
    )
    execute(
        "INSERT INTO schedule_sections (schedule_id, section_id) VALUES (%s, %s)",
        (schedule_id, section_id),
    )
    execute("UPDATE schedules SET updated_at = %s WHERE id = %s", (datetime.now(), schedule_id))
    commit()
    return _detail(_own_schedule(schedule_id))


@bp.delete("/schedules/<int:schedule_id>/sections/<int:section_id>")
@login_required
def remove_section(schedule_id, section_id):
    _own_schedule(schedule_id)
    removed = execute(
        "DELETE FROM schedule_sections WHERE schedule_id = %s AND section_id = %s",
        (schedule_id, section_id),
    )
    if not removed:
        raise not_found("Section in this schedule")
    execute("UPDATE schedules SET updated_at = %s WHERE id = %s", (datetime.now(), schedule_id))
    commit()
    return _detail(_own_schedule(schedule_id))


@bp.post("/schedules/<int:schedule_id>/commit")
@login_required
def commit_schedule(schedule_id):
    """Make this the student's schedule for its term: its classes and
    assignments appear on the calendar and in the gradebook. Any other
    committed schedule for the same term is uncommitted."""
    schedule = _own_schedule(schedule_id)
    execute(
        "UPDATE schedules SET is_committed = FALSE WHERE user_id = %s AND term_id = %s AND id <> %s",
        (g.user["id"], schedule["term_id"], schedule_id),
    )
    execute("UPDATE schedules SET is_committed = TRUE WHERE id = %s", (schedule_id,))
    commit()
    return _detail(_own_schedule(schedule_id))


@bp.delete("/schedules/<int:schedule_id>/commit")
@login_required
def uncommit_schedule(schedule_id):
    _own_schedule(schedule_id)
    execute("UPDATE schedules SET is_committed = FALSE WHERE id = %s", (schedule_id,))
    commit()
    return _detail(_own_schedule(schedule_id))
