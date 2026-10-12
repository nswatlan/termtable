"""Weighted grade calculation.

There are two ways to weight a course, chosen per student per class:

- "category" (the default): every course uses the same fixed category weights.
- "custom": the student gives each assignment its own weight (a share of the
  course grade), to match the real syllabus. compute_custom_grade handles it.

In category mode: Grades are averaged within
a category (each assignment counts equally, as a percentage of its own max
points), then categories are combined by weight. Categories with no graded
work are left out and the remaining weights are rescaled, so ungraded work
never counts as zero.
"""

CATEGORY_WEIGHTS = {
    "homework": 0.20,
    "quiz": 0.10,
    "midterm": 0.30,
    "final": 0.40,
}
CATEGORIES = tuple(CATEGORY_WEIGHTS)
MODES = ("category", "custom")

LETTER_CUTOFFS = [
    (93, "A"), (90, "A-"), (87, "B+"), (83, "B"), (80, "B-"),
    (77, "C+"), (73, "C"), (70, "C-"), (67, "D+"), (60, "D"), (0, "F"),
]


def letter_grade(percent):
    if percent is None:
        return None
    for cutoff, letter in LETTER_CUTOFFS:
        if percent >= cutoff:
            return letter
    return "F"


def compute_grade(items):
    """Compute a course grade.

    items: iterable of dicts with keys "category", "score" (None if ungraded)
    and "max_points".

    Returns a dict:
        overall:     weighted percent (0-100+) or None if nothing is graded
        letter:      letter grade for overall, or None
        categories:  {category: {weight, average, graded, total, counted}}
        counted_weight: sum of the weights that contributed to overall
    """
    by_category = {c: [] for c in CATEGORIES}
    totals = {c: 0 for c in CATEGORIES}
    for item in items:
        category = item["category"]
        if category not in by_category:
            raise ValueError(f"unknown category: {category!r}")
        totals[category] += 1
        if item["score"] is not None:
            max_points = float(item["max_points"])
            if max_points <= 0:
                raise ValueError("max_points must be positive")
            by_category[category].append(float(item["score"]) / max_points * 100)

    categories = {}
    weighted_sum = 0.0
    counted_weight = 0.0
    for category, weight in CATEGORY_WEIGHTS.items():
        percents = by_category[category]
        average = sum(percents) / len(percents) if percents else None
        if average is not None:
            weighted_sum += average * weight
            counted_weight += weight
        categories[category] = {
            "weight": weight,
            "average": None if average is None else round(average, 2),
            "graded": len(percents),
            "total": totals[category],
            "counted": average is not None,
        }

    overall = round(weighted_sum / counted_weight, 2) if counted_weight else None
    return {
        "overall": overall,
        "letter": letter_grade(overall),
        "categories": categories,
        "counted_weight": round(counted_weight, 4),
    }


# --- custom per-assignment weights -----------------------------------------

def default_weights(items):
    """Per-assignment weights (percent of the course grade) equivalent to the
    fixed category weights: each category's weight is split evenly across its
    assignments. Categories with no assignments drop out and the rest are
    rescaled, so the weights always total 100."""
    counts = {}
    for item in items:
        counts[item["category"]] = counts.get(item["category"], 0) + 1
    present = sum(CATEGORY_WEIGHTS[c] for c in counts)
    if not present:
        return [0.0 for _ in items]
    return [
        round(CATEGORY_WEIGHTS[i["category"]] / present / counts[i["category"]] * 100, 3)
        for i in items
    ]


def compute_custom_grade(items):
    """Grade from per-assignment weights.

    items: dicts with "score" (None if ungraded), "max_points" and "weight".
    The grade is the weighted mean of the graded assignments' percentages,
    so ungraded work never counts as zero (same rule as category mode).

    Returns overall, letter, counted_weight (share of the total weight that
    is graded, 0-1) and total_weight (sum of all weights, ideally 100).
    """
    total_weight = 0.0
    graded_weight = 0.0
    weighted_sum = 0.0
    for item in items:
        weight = float(item.get("weight") or 0)
        if weight < 0:
            raise ValueError("weights cannot be negative")
        total_weight += weight
        if item["score"] is None or weight == 0:
            continue
        max_points = float(item["max_points"])
        if max_points <= 0:
            raise ValueError("max_points must be positive")
        weighted_sum += float(item["score"]) / max_points * 100 * weight
        graded_weight += weight

    overall = round(weighted_sum / graded_weight, 2) if graded_weight else None
    return {
        "overall": overall,
        "letter": letter_grade(overall),
        "counted_weight": round(graded_weight / total_weight, 4) if total_weight else 0,
        "total_weight": round(total_weight, 3),
    }


def grade_for_mode(items, mode):
    if mode == "custom":
        return compute_custom_grade(items)
    return compute_grade(items)


# --- target grade -----------------------------------------------------------

def required_average(items, target, mode="category"):
    """What average (percent) the student needs on every remaining ungraded
    assignment to finish with `target` percent.

    Both grading modes are linear in the remaining scores once everything is
    graded, so the answer comes from the final grade with every remaining
    assignment at 0% and at 100%.

    Returns {target, required, status, remaining, lowest, highest} where
    status is one of:
        "secured"       - the target is reached even with 0% on the rest
        "possible"      - `required` percent on the rest reaches it
        "out_of_reach"  - even 100% on the rest falls short
        "no_remaining"  - nothing left to grade
    """
    def counts(item):
        return mode == "category" or float(item.get("weight") or 0) > 0

    remaining = [i for i in items if i["score"] is None and counts(i)]
    result = {"target": target, "required": None, "remaining": len(remaining),
              "lowest": None, "highest": None}
    if not remaining:
        current = grade_for_mode(items, mode)["overall"]
        result["status"] = "no_remaining"
        result["lowest"] = result["highest"] = current
        return result

    def finished_at(percent):
        filled = [
            dict(i, score=float(i["max_points"]) * percent / 100) if i["score"] is None else i
            for i in items
        ]
        return grade_for_mode(filled, mode)["overall"]

    lowest, highest = finished_at(0), finished_at(100)
    result["lowest"], result["highest"] = lowest, highest
    if target <= lowest:
        result["status"] = "secured"
        result["required"] = 0.0
    elif target > highest:
        result["status"] = "out_of_reach"
        result["required"] = round((target - lowest) / (highest - lowest) * 100, 2)
    else:
        result["status"] = "possible"
        result["required"] = round((target - lowest) / (highest - lowest) * 100, 2)
    return result
