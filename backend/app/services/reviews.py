"""Course reviews: listing with professor filter and sorting, cross-course
search, and each student's one review per course."""

from ..db import commit
from ..errors import bad_request, not_found, optional_str, require_int, require_object, require_str
from ..repositories import catalog as catalog_repo
from ..repositories import reviews as reviews_repo
from .catalog import require_course

SORTS = tuple(reviews_repo.ORDER_BY)


def _check_sort(sort):
    sort = sort or "newest"
    if sort not in SORTS:
        raise bad_request(f"'sort' must be one of {', '.join(SORTS)}")
    return sort


def _mark_mine(reviews, viewer_id):
    for r in reviews:
        r["mine"] = r.pop("user_id") == viewer_id
    return reviews


def for_course(course_id, viewer_id, sort=None, instructor=""):
    require_course(course_id)
    rows = reviews_repo.for_course(course_id, _check_sort(sort), instructor.strip() or None)
    return _mark_mine(rows, viewer_id)


def search(viewer_id, sort=None, instructor="", department="", course=""):
    sort = _check_sort(sort)
    rows = reviews_repo.search(sort, instructor=instructor.strip() or None,
                               department=department.strip() or None, course=course.strip() or None)
    return _mark_mine(rows, viewer_id)


def save_mine(course_id, user_id, body):
    """Create or replace the student's review. `instructor`, if given, must
    teach a section of the course."""
    require_course(course_id)
    data = require_object(body)
    rating = require_int(data, "rating", minimum=1, maximum=5)
    text = require_str(data, "body", max_len=5000)
    instructor = optional_str(data, "instructor", max_len=100)
    if instructor is not None and not catalog_repo.instructor_teaches(course_id, instructor):
        raise bad_request("Pick a professor who teaches this course")
    reviews_repo.upsert(course_id, user_id, rating, instructor, text)
    commit()
    return reviews_repo.get_mine(course_id, user_id)


def delete_mine(course_id, user_id):
    if not reviews_repo.delete_mine(course_id, user_id):
        raise not_found("Review")
    commit()
