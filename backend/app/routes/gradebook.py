"""Gradebook: per-class grades, weighting mode, target grade, what-if."""

from flask import Blueprint, g, request

from ..services import gradebook
from .auth import login_required

bp = Blueprint("gradebook", __name__)


@bp.get("/gradebook")
@login_required
def overview():
    return gradebook.overview(g.user["id"])


@bp.get("/gradebook/<int:term_id>/<int:course_id>")
@login_required
def course(term_id, course_id):
    return gradebook.course(g.user["id"], term_id, course_id)


@bp.put("/gradebook/<int:term_id>/<int:course_id>/settings")
@login_required
def update_settings(term_id, course_id):
    return gradebook.update_settings(g.user["id"], term_id, course_id, request.get_json(silent=True))


@bp.put("/gradebook/<int:term_id>/<int:course_id>/weights")
@login_required
def update_weights(term_id, course_id):
    return gradebook.update_weights(g.user["id"], term_id, course_id, request.get_json(silent=True))


@bp.delete("/gradebook/<int:term_id>/<int:course_id>/weights")
@login_required
def reset_weights(term_id, course_id):
    return gradebook.reset_weights(g.user["id"], term_id, course_id)


@bp.post("/gradebook/<int:term_id>/<int:course_id>/what-if")
@login_required
def what_if(term_id, course_id):
    return gradebook.what_if(g.user["id"], term_id, course_id, request.get_json(silent=True))


@bp.put("/grades/<int:assignment_id>")
@login_required
def set_grade(assignment_id):
    return gradebook.set_score(g.user["id"], assignment_id, request.get_json(silent=True))


@bp.delete("/grades/<int:assignment_id>")
@login_required
def clear_grade(assignment_id):
    return gradebook.clear_score(g.user["id"], assignment_id)
