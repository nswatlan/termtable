"""Candidate schedules: named sets of sections a student builds for a term,
with conflict detection, comparison stats, and committing one per term."""

from datetime import datetime

from ..db import commit
from ..errors import bad_request, not_found, require_int, require_object, require_str
from ..logic.conflicts import conflicting_section_ids, find_conflicts
from ..repositories import catalog as catalog_repo
from ..repositories import schedules as schedules_repo
from .catalog import rating_summaries


def _owned(schedule_id, user_id):
    schedule = schedules_repo.get_owned(schedule_id, user_id)
    if schedule is None:
        raise not_found("Schedule")
    schedule["is_committed"] = bool(schedule["is_committed"])
    return schedule


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
    """Add sections (with ratings and conflict flags), conflicts and stats."""
    section_ids = schedules_repo.section_ids([schedule["id"]])[schedule["id"]]
    sections = catalog_repo.sections_by_ids(section_ids)
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


def _reload(schedule_id, user_id):
    return _detail(_owned(schedule_id, user_id))


def list_schedules(user_id, term_id=None):
    # Full detail for each: the planner shows the stats in its compare view,
    # and a student only ever has a handful of schedules.
    schedules = schedules_repo.list_for_user(user_id, term_id)
    for s in schedules:
        s["is_committed"] = bool(s["is_committed"])
        _detail(s)
    return schedules


def get_schedule(schedule_id, user_id):
    return _reload(schedule_id, user_id)


def create_schedule(user_id, body):
    """New empty schedule for a term, or a copy of an existing one."""
    data = require_object(body)
    name = require_str(data, "name", max_len=100)
    copy_from = data.get("copy_from")
    if copy_from is not None:
        term_id = _owned(require_int(data, "copy_from"), user_id)["term_id"]
    else:
        term_id = require_int(data, "term_id")
        if not catalog_repo.term_exists(term_id):
            raise bad_request("Unknown term")

    schedule_id = schedules_repo.create(user_id, term_id, name)
    if copy_from is not None:
        schedules_repo.copy_sections(schedule_id, copy_from)
    commit()
    return _reload(schedule_id, user_id)


def rename_schedule(schedule_id, user_id, body):
    _owned(schedule_id, user_id)
    name = require_str(require_object(body), "name", max_len=100)
    schedules_repo.rename(schedule_id, name)
    commit()
    return _reload(schedule_id, user_id)


def delete_schedule(schedule_id, user_id):
    _owned(schedule_id, user_id)
    schedules_repo.delete(schedule_id)
    commit()


def add_section(schedule_id, user_id, body):
    """Add a section. A schedule holds at most one section per course, so
    picking a different section of a course swaps it in."""
    schedule = _owned(schedule_id, user_id)
    section_id = require_int(require_object(body), "section_id")
    section = catalog_repo.section_basics(section_id)
    if section is None:
        raise not_found("Section")
    if section["term_id"] != schedule["term_id"]:
        raise bad_request("That section is offered in a different term than this schedule")
    schedules_repo.remove_course(schedule_id, section["course_id"])
    schedules_repo.add_section(schedule_id, section_id)
    schedules_repo.touch(schedule_id, datetime.now())
    commit()
    return _reload(schedule_id, user_id)


def remove_section(schedule_id, section_id, user_id):
    _owned(schedule_id, user_id)
    if not schedules_repo.remove_section(schedule_id, section_id):
        raise not_found("Section in this schedule")
    schedules_repo.touch(schedule_id, datetime.now())
    commit()
    return _reload(schedule_id, user_id)


def commit_schedule(schedule_id, user_id):
    """Make this the student's schedule for its term: its classes and
    assignments appear on the calendar and in the gradebook. Any other
    committed schedule for the same term is uncommitted."""
    schedule = _owned(schedule_id, user_id)
    schedules_repo.uncommit_others(user_id, schedule["term_id"], schedule_id)
    schedules_repo.set_committed(schedule_id, True)
    commit()
    return _reload(schedule_id, user_id)


def uncommit_schedule(schedule_id, user_id):
    _owned(schedule_id, user_id)
    schedules_repo.set_committed(schedule_id, False)
    commit()
    return _reload(schedule_id, user_id)
