"""Course catalog: terms, course search (including CRN search), course
detail with sections and rating summary, instructors."""

from ..errors import not_found
from ..repositories import catalog as catalog_repo


def list_terms():
    return catalog_repo.list_terms()


def list_departments():
    return catalog_repo.list_departments()


def rating_summaries(course_ids):
    """{course_id: {"avg_rating": float|None, "review_count": int}}"""
    summaries = {cid: {"avg_rating": None, "review_count": 0} for cid in course_ids}
    for row in catalog_repo.rating_stats(course_ids):
        summaries[row["course_id"]] = {
            "avg_rating": round(float(row["avg_rating"]), 2),
            "review_count": row["review_count"],
        }
    return summaries


def search_courses(q="", crn="", department="", term_id=None):
    """Courses matching the filters, each with its rating summary and its
    sections (only the chosen term's, and only matching ones for a CRN search)."""
    crn_digits = "".join(ch for ch in crn if ch.isdigit())
    if crn and not crn_digits:
        return []  # a CRN search with no digits matches nothing
    courses = catalog_repo.search_courses(q=q or None, crn_prefix=crn_digits or None,
                                          department=department or None, term_id=term_id)
    ids = [c["id"] for c in courses]
    ratings = rating_summaries(ids)
    sections_by_course = {cid: [] for cid in ids}
    for section in catalog_repo.sections_for_courses(ids, term_id=term_id, crn_prefix=crn_digits or None):
        sections_by_course[section["course_id"]].append(section)
    for c in courses:
        c.update(ratings[c["id"]])
        c["sections"] = sections_by_course[c["id"]]
    return courses


def get_course(course_id, term_id=None):
    course = catalog_repo.get_course(course_id)
    if course is None:
        raise not_found("Course")
    course.update(rating_summaries([course_id])[course_id])
    distribution = {str(n): 0 for n in range(1, 6)}
    for row in catalog_repo.rating_counts(course_id):
        distribution[str(row["rating"])] = row["n"]
    course["rating_distribution"] = distribution
    course["sections"] = catalog_repo.sections_for_course(course_id, term_id or None)
    return course


def section_by_crn(crn):
    section = catalog_repo.section_by_crn(crn.strip())
    if section is None:
        raise not_found("Section with that CRN")
    return section


def list_instructors(department="", course_id=None):
    return catalog_repo.instructors(department=department or None, course_id=course_id)


def require_course(course_id):
    if not catalog_repo.course_exists(course_id):
        raise not_found("Course")
