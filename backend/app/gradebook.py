"""Per-class grade tracking for the courses in a student's committed schedules.

Each student chooses, per class, between the fixed category weights and their
own per-assignment weights (to match the real syllabus), can set a target
grade, and can try out hypothetical ("what-if") scores without saving them.
"""

from decimal import Decimal

from flask import Blueprint, g

from .auth import login_required
from .db import commit, execute, in_clause, query, query_one
from .enrollment import enrolled_sections
from .errors import ApiError, bad_request, json_body, not_found, require_decimal
from .logic.grades import (CATEGORIES, CATEGORY_WEIGHTS, MODES, default_weights,
                           grade_for_mode, required_average)

bp = Blueprint("gradebook", __name__)


def _assignments_with_scores(course_id, term_id):
    rows = query(
        """SELECT a.id, a.title, a.category, a.due_at, a.max_points, a.description,
                  gr.score, gw.weight AS custom_weight
           FROM assignments a
           LEFT JOIN grades gr ON gr.assignment_id = a.id AND gr.user_id = %s
           LEFT JOIN grade_weights gw ON gw.assignment_id = a.id AND gw.user_id = %s
           WHERE a.course_id = %s AND a.term_id = %s
           ORDER BY a.due_at, a.id""",
        (g.user["id"], g.user["id"], course_id, term_id),
    )
    # Every assignment gets a weight: the student's own, or the share of its
    # category weight it would have by default.
    for row, default in zip(rows, default_weights(rows)):
        row["default_weight"] = default
        row["weight"] = float(row["custom_weight"]) if row["custom_weight"] is not None else default
        row["has_custom_weight"] = row.pop("custom_weight") is not None
    return rows


def _settings(course_id, term_id):
    row = query_one(
        "SELECT mode, target_grade FROM grade_settings WHERE user_id = %s AND course_id = %s AND term_id = %s",
        (g.user["id"], course_id, term_id),
    )
    return row or {"mode": "category", "target_grade": None}


def _enrolled_section(course_id, term_id):
    for s in enrolled_sections(g.user["id"], [term_id]):
        if s["course_id"] == course_id:
            return s
    return None


def _require_section(course_id, term_id):
    section = _enrolled_section(course_id, term_id)
    if section is None:
        raise not_found("Class in your committed schedule")
    return section


def _target(items, settings):
    if settings["target_grade"] is None:
        return None
    return required_average(items, float(settings["target_grade"]), settings["mode"])


def _course_detail(section):
    assignments = _assignments_with_scores(section["course_id"], section["term_id"])
    settings = _settings(section["course_id"], section["term_id"])
    return {
        "course_id": section["course_id"],
        "term_id": section["term_id"],
        "term_name": section["term_name"],
        "course_code": f"{section['department']} {section['number']}",
        "title": section["title"],
        "section_code": section["section_code"],
        "instructor": section["instructor"],
        "mode": settings["mode"],
        "target_grade": settings["target_grade"],
        "weights": CATEGORY_WEIGHTS,
        "categories": list(CATEGORIES),
        "assignments": assignments,
        "grade": grade_for_mode(assignments, settings["mode"]),
        "target": _target(assignments, settings),
    }


@bp.get("/gradebook")
@login_required
def gradebook_overview():
    classes = []
    for s in enrolled_sections(g.user["id"]):
        detail = _course_detail(s)
        assignments = detail.pop("assignments")
        detail["graded_count"] = sum(1 for a in assignments if a["score"] is not None)
        detail["assignment_count"] = len(assignments)
        detail["term_start"] = s["term_start"]
        classes.append(detail)
    classes.sort(key=lambda c: (c["term_start"], c["course_code"]), reverse=False)
    return classes


@bp.get("/gradebook/<int:term_id>/<int:course_id>")
@login_required
def gradebook_course(term_id, course_id):
    return _course_detail(_require_section(course_id, term_id))


@bp.put("/gradebook/<int:term_id>/<int:course_id>/settings")
@login_required
def update_settings(term_id, course_id):
    """Change the grading mode and/or the target grade (null clears it)."""
    section = _require_section(course_id, term_id)
    data = json_body()
    settings = _settings(course_id, term_id)
    mode, target = settings["mode"], settings["target_grade"]
    if "mode" in data:
        if data["mode"] not in MODES:
            raise bad_request("'mode' must be category or custom")
        mode = data["mode"]
    if "target_grade" in data:
        target = None if data["target_grade"] in (None, "") else require_decimal(
            data, "target_grade", minimum=0, maximum=150)
    execute(
        """INSERT INTO grade_settings (user_id, course_id, term_id, mode, target_grade)
           VALUES (%s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE mode = VALUES(mode), target_grade = VALUES(target_grade)""",
        (g.user["id"], course_id, term_id, mode, target),
    )
    commit()
    return _course_detail(section)


@bp.put("/gradebook/<int:term_id>/<int:course_id>/weights")
@login_required
def update_weights(term_id, course_id):
    """Set per-assignment weights: {"weights": {"<assignment id>": weight or null}}.
    null resets that assignment to its default weight."""
    section = _require_section(course_id, term_id)
    weights = json_body().get("weights")
    if not isinstance(weights, dict) or not weights:
        raise bad_request("'weights' must map assignment ids to weights")
    try:
        ids = [int(k) for k in weights]
    except ValueError:
        raise bad_request("'weights' keys must be assignment ids")
    valid = {
        r["id"] for r in query(
            f"SELECT id FROM assignments WHERE course_id = %s AND term_id = %s AND id IN ({in_clause(ids)})",
            (course_id, term_id, *ids),
        )
    }
    if set(ids) - valid:
        raise not_found("Assignment in this class")
    for key, value in weights.items():
        if value is None or value == "":
            execute("DELETE FROM grade_weights WHERE user_id = %s AND assignment_id = %s",
                    (g.user["id"], int(key)))
        else:
            weight = require_decimal({"weight": value}, "weight", minimum=0, maximum=100)
            execute(
                """INSERT INTO grade_weights (user_id, assignment_id, weight) VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE weight = VALUES(weight)""",
                (g.user["id"], int(key), weight),
            )
    commit()
    return _course_detail(section)


@bp.delete("/gradebook/<int:term_id>/<int:course_id>/weights")
@login_required
def reset_weights(term_id, course_id):
    section = _require_section(course_id, term_id)
    execute(
        """DELETE gw FROM grade_weights gw JOIN assignments a ON a.id = gw.assignment_id
           WHERE gw.user_id = %s AND a.course_id = %s AND a.term_id = %s""",
        (g.user["id"], course_id, term_id),
    )
    commit()
    return _course_detail(section)


@bp.post("/gradebook/<int:term_id>/<int:course_id>/what-if")
@login_required
def what_if(term_id, course_id):
    """Grade with hypothetical scores. Nothing is saved.

    Body: {"scores": {"<assignment id>": score or null},
           "extra": [{"title", "category", "max_points", "score", "weight"}],
           "target_grade": optional number}
    """
    _require_section(course_id, term_id)
    data = json_body()
    settings = _settings(course_id, term_id)
    items = _assignments_with_scores(course_id, term_id)

    scores = data.get("scores") or {}
    if not isinstance(scores, dict):
        raise bad_request("'scores' must map assignment ids to scores")
    by_id = {str(a["id"]): a for a in items}
    for key, value in scores.items():
        if key not in by_id:
            raise not_found("Assignment in this class")
        by_id[key]["score"] = None if value in (None, "") else require_decimal(
            {"score": value}, "score", minimum=0, maximum=9999)

    extra = data.get("extra") or []
    if not isinstance(extra, list) or len(extra) > 50:
        raise bad_request("'extra' must be a list of at most 50 assignments")
    for e in extra:
        if not isinstance(e, dict):
            raise bad_request("Each extra assignment must be an object")
        category = e.get("category", "homework")
        if category not in CATEGORIES:
            raise bad_request(f"'category' must be one of {', '.join(CATEGORIES)}")
        items.append({
            "category": category,
            "max_points": require_decimal(e, "max_points", minimum=Decimal("0.01"), maximum=9999),
            "score": None if e.get("score") in (None, "") else require_decimal(e, "score", minimum=0, maximum=9999),
            "weight": float(require_decimal(e, "weight", minimum=0, maximum=100)) if e.get("weight") not in (None, "") else 0.0,
        })

    if "target_grade" in data:
        target_value = data["target_grade"]
        settings = dict(settings, target_grade=None if target_value in (None, "") else
                        require_decimal(data, "target_grade", minimum=0, maximum=150))
    return {
        "mode": settings["mode"],
        "grade": grade_for_mode(items, settings["mode"]),
        "target": _target(items, settings),
    }


def _gradeable_assignment(assignment_id):
    """The assignment, provided the student is taking its course that term."""
    assignment = query_one(
        "SELECT id, course_id, term_id, max_points FROM assignments WHERE id = %s",
        (assignment_id,),
    )
    if assignment is None:
        raise not_found("Assignment")
    section = _enrolled_section(assignment["course_id"], assignment["term_id"])
    if section is None:
        raise ApiError(403, "Add this class to your calendar before entering grades for it")
    return assignment, section


@bp.put("/grades/<int:assignment_id>")
@login_required
def set_grade(assignment_id):
    _, section = _gradeable_assignment(assignment_id)
    # Scores above max_points are allowed for extra credit.
    score = require_decimal(json_body(), "score", minimum=0, maximum=9999)
    execute(
        """INSERT INTO grades (user_id, assignment_id, score) VALUES (%s, %s, %s)
           ON DUPLICATE KEY UPDATE score = VALUES(score)""",
        (g.user["id"], assignment_id, score),
    )
    commit()
    return _course_detail(section)


@bp.delete("/grades/<int:assignment_id>")
@login_required
def clear_grade(assignment_id):
    _, section = _gradeable_assignment(assignment_id)
    execute(
        "DELETE FROM grades WHERE user_id = %s AND assignment_id = %s",
        (g.user["id"], assignment_id),
    )
    commit()
    return _course_detail(section)
