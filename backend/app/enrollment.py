"""What a student is "taking": the sections in their committed schedules."""

from .courses import load_sections
from .db import in_clause, query


def enrolled_sections(user_id, term_ids=None):
    """Sections from the student's committed schedules, each with its meetings
    and its term's start_date/end_date/term_name."""
    where = """s.id IN (
                   SELECT ss.section_id FROM schedule_sections ss
                   JOIN schedules sc ON sc.id = ss.schedule_id
                   WHERE sc.user_id = %s AND sc.is_committed)"""
    args = [user_id]
    if term_ids is not None:
        if not term_ids:
            return []
        where += f" AND s.term_id IN ({in_clause(term_ids)})"
        args += list(term_ids)
    sections = load_sections(where, tuple(args))
    if not sections:
        return sections

    term_ids_used = sorted({s["term_id"] for s in sections})
    terms = {
        t["id"]: t
        for t in query(
            f"SELECT id, name, start_date, end_date FROM terms WHERE id IN ({in_clause(term_ids_used)})",
            tuple(term_ids_used),
        )
    }
    for s in sections:
        term = terms[s["term_id"]]
        s["term_name"] = term["name"]
        s["term_start"] = term["start_date"]
        s["term_end"] = term["end_date"]
    return sections
