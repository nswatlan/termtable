"""Candidate schedules for the planner."""

from flask import Blueprint, g, request

from ..services import schedules
from .auth import login_required

bp = Blueprint("schedules", __name__)


@bp.get("/schedules")
@login_required
def list_schedules():
    return schedules.list_schedules(g.user["id"], request.args.get("term_id", type=int))


@bp.post("/schedules")
@login_required
def create_schedule():
    return schedules.create_schedule(g.user["id"], request.get_json(silent=True)), 201


@bp.get("/schedules/<int:schedule_id>")
@login_required
def get_schedule(schedule_id):
    return schedules.get_schedule(schedule_id, g.user["id"])


@bp.patch("/schedules/<int:schedule_id>")
@login_required
def rename_schedule(schedule_id):
    return schedules.rename_schedule(schedule_id, g.user["id"], request.get_json(silent=True))


@bp.delete("/schedules/<int:schedule_id>")
@login_required
def delete_schedule(schedule_id):
    schedules.delete_schedule(schedule_id, g.user["id"])
    return {"ok": True}


@bp.post("/schedules/<int:schedule_id>/sections")
@login_required
def add_section(schedule_id):
    return schedules.add_section(schedule_id, g.user["id"], request.get_json(silent=True))


@bp.delete("/schedules/<int:schedule_id>/sections/<int:section_id>")
@login_required
def remove_section(schedule_id, section_id):
    return schedules.remove_section(schedule_id, section_id, g.user["id"])


@bp.post("/schedules/<int:schedule_id>/commit")
@login_required
def commit_schedule(schedule_id):
    return schedules.commit_schedule(schedule_id, g.user["id"])


@bp.delete("/schedules/<int:schedule_id>/commit")
@login_required
def uncommit_schedule(schedule_id):
    return schedules.uncommit_schedule(schedule_id, g.user["id"])
