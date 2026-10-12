"""What a student is "taking": the sections in their committed schedules."""

from ..repositories import catalog as catalog_repo


def enrolled_sections(user_id, term_ids=None):
    """Sections from the student's committed schedules, each with its meetings
    and its term's start_date/end_date/term_name."""
    if term_ids is not None and not term_ids:
        return []
    sections = catalog_repo.committed_sections(user_id, term_ids)
    if not sections:
        return sections
    terms = {t["id"]: t for t in catalog_repo.terms_by_ids(sorted({s["term_id"] for s in sections}))}
    for s in sections:
        term = terms[s["term_id"]]
        s["term_name"] = term["name"]
        s["term_start"] = term["start_date"]
        s["term_end"] = term["end_date"]
    return sections


def enrolled_section(user_id, course_id, term_id):
    """The student's section of a course in a term, or None."""
    for s in enrolled_sections(user_id, [term_id]):
        if s["course_id"] == course_id:
            return s
    return None


def offerings(sections):
    """{(course_id, term_id): section} for a list of enrolled sections."""
    return {(s["course_id"], s["term_id"]): s for s in sections}


def course_code(section):
    return f"{section['department']} {section['number']}"
