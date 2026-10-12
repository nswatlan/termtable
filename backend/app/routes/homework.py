"""Your own assignments and the combined to-do list."""

from flask import Blueprint, g, request

from ..services import homework
from .auth import login_required

bp = Blueprint("homework", __name__)


@bp.get("/my-assignments")
@login_required
def list_mine():
    return homework.list_mine(g.user["id"], request.args.get("include_completed") in ("1", "true"))


@bp.post("/my-assignments")
@login_required
def create_mine():
    return homework.create(g.user["id"], request.get_json(silent=True)), 201


@bp.patch("/my-assignments/<int:assignment_id>")
@login_required
def update_mine(assignment_id):
    return homework.update(assignment_id, g.user["id"], request.get_json(silent=True))


@bp.delete("/my-assignments/<int:assignment_id>")
@login_required
def delete_mine(assignment_id):
    homework.delete(assignment_id, g.user["id"])
    return {"ok": True}


@bp.get("/homework")
@login_required
def todo_list():
    return homework.todo_list(g.user["id"], request.args.get("from"))
