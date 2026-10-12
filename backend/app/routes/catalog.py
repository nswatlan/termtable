"""Terms, departments, course search and detail, sections, instructors."""

from flask import Blueprint, request

from ..services import catalog

bp = Blueprint("catalog", __name__)


@bp.get("/terms")
def list_terms():
    return catalog.list_terms()


@bp.get("/departments")
def list_departments():
    return catalog.list_departments()


@bp.get("/courses")
def search_courses():
    return catalog.search_courses(
        q=(request.args.get("q") or "").strip(),
        crn=request.args.get("crn") or "",
        department=(request.args.get("department") or "").strip(),
        term_id=request.args.get("term_id", type=int),
    )


@bp.get("/courses/<int:course_id>")
def get_course(course_id):
    return catalog.get_course(course_id, request.args.get("term_id", type=int))


@bp.get("/sections/by-crn/<crn>")
def section_by_crn(crn):
    return catalog.section_by_crn(crn)


@bp.get("/instructors")
def list_instructors():
    return catalog.list_instructors(
        department=(request.args.get("department") or "").strip(),
        course_id=request.args.get("course_id", type=int),
    )
