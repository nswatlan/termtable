"""Course reviews: per course, cross-course search, and your own review."""

from flask import Blueprint, g, request, session

from ..services import reviews
from .auth import login_required

bp = Blueprint("reviews", __name__)


@bp.get("/courses/<int:course_id>/reviews")
def list_reviews(course_id):
    return reviews.for_course(course_id, session.get("user_id"),
                              sort=request.args.get("sort"),
                              instructor=request.args.get("instructor") or "")


@bp.get("/reviews")
def search_reviews():
    return reviews.search(session.get("user_id"),
                          sort=request.args.get("sort"),
                          instructor=request.args.get("instructor") or "",
                          department=request.args.get("department") or "",
                          course=request.args.get("course") or "")


@bp.put("/courses/<int:course_id>/reviews/mine")
@login_required
def save_my_review(course_id):
    return reviews.save_mine(course_id, g.user["id"], request.get_json(silent=True))


@bp.delete("/courses/<int:course_id>/reviews/mine")
@login_required
def delete_my_review(course_id):
    reviews.delete_mine(course_id, g.user["id"])
    return {"ok": True}
