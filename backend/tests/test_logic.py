from datetime import date, datetime, time

import pytest

from app.logic.conflicts import conflicting_section_ids, find_conflicts
from app.logic.grades import (compute_custom_grade, compute_grade, default_weights,
                              letter_grade, required_average)
from app.logic.recurrence import expand_event, expand_weekly_meeting, parse_weekdays


# --- grades ---------------------------------------------------------------

def item(category, score, max_points=100):
    return {"category": category, "score": score, "max_points": max_points}


def test_no_grades_means_no_overall():
    result = compute_grade([item("homework", None), item("final", None)])
    assert result["overall"] is None
    assert result["letter"] is None
    assert result["counted_weight"] == 0


def test_only_homework_and_quizzes_count_when_exams_ungraded():
    # Homework avg 90 (weight .2), quiz avg 70 (weight .1); exams ungraded.
    result = compute_grade([
        item("homework", 18, 20), item("homework", 45, 50),
        item("quiz", 7, 10),
        item("midterm", None), item("final", None, 150),
    ])
    assert result["overall"] == pytest.approx((90 * 0.2 + 70 * 0.1) / 0.3, abs=0.01)
    assert result["categories"]["midterm"]["counted"] is False
    assert result["categories"]["homework"]["graded"] == 2
    assert result["categories"]["final"]["total"] == 1
    assert result["counted_weight"] == pytest.approx(0.3)


def test_category_average_is_mean_of_percentages_not_points():
    # 10/10 and 50/100 -> mean of 100% and 50% = 75%, not 60/110.
    result = compute_grade([item("homework", 10, 10), item("homework", 50, 100)])
    assert result["categories"]["homework"]["average"] == 75
    assert result["overall"] == 75


def test_all_categories_use_fixed_weights():
    result = compute_grade([
        item("homework", 100), item("quiz", 80), item("midterm", 70), item("final", 90),
    ])
    assert result["overall"] == pytest.approx(100 * .2 + 80 * .1 + 70 * .3 + 90 * .4)
    assert result["letter"] == "B"


def test_zero_score_counts_but_missing_score_does_not():
    assert compute_grade([item("quiz", 0), item("quiz", None)])["overall"] == 0


def test_unknown_category_rejected():
    with pytest.raises(ValueError):
        compute_grade([item("project", 90)])


def test_letter_grades():
    assert letter_grade(93) == "A"
    assert letter_grade(92.99) == "A-"
    assert letter_grade(59.9) == "F"
    assert letter_grade(104) == "A"


def witem(score, weight, max_points=100, category="homework"):
    return {"category": category, "score": score, "max_points": max_points, "weight": weight}


def test_default_weights_split_category_weight_evenly():
    weights = default_weights([item("homework", None)] * 4 + [item("final", None)])
    # Only homework (.2) and final (.4) exist, rescaled to 100.
    assert weights[:4] == [pytest.approx(100 / 3 / 4, abs=0.001)] * 4
    assert weights[4] == pytest.approx(200 / 3, abs=0.001)
    assert sum(weights) == pytest.approx(100, abs=0.01)


def test_custom_grade_uses_individual_weights():
    result = compute_custom_grade([witem(100, 10), witem(50, 30), witem(None, 60)])
    # Only graded work counts: (100*10 + 50*30) / 40
    assert result["overall"] == pytest.approx(62.5)
    assert result["counted_weight"] == pytest.approx(0.4)
    assert result["total_weight"] == 100


def test_custom_grade_ignores_zero_weight_and_handles_nothing_graded():
    assert compute_custom_grade([witem(0, 0), witem(80, 5)])["overall"] == 80
    assert compute_custom_grade([witem(None, 50)])["overall"] is None


def test_required_average_custom_mode():
    # 40% of the grade done at 90%; need 80% overall -> (80*100 - 90*40) / 60
    items = [witem(90, 40), witem(None, 60)]
    result = required_average(items, 80, "custom")
    assert result["status"] == "possible"
    assert result["required"] == pytest.approx((8000 - 3600) / 60, abs=0.01)
    assert result["remaining"] == 1


def test_required_average_category_mode_matches_forward_calculation():
    items = [item("homework", 18, 20), item("quiz", 7, 10), item("midterm", None), item("final", None, 150)]
    result = required_average(items, 85, "category")
    needed = result["required"]
    filled = [dict(i, score=i["max_points"] * needed / 100) if i["score"] is None else i for i in items]
    assert compute_grade(filled)["overall"] == pytest.approx(85, abs=0.05)


def test_required_average_statuses():
    assert required_average([witem(100, 50), witem(None, 50)], 50, "custom")["status"] == "secured"
    assert required_average([witem(0, 90), witem(None, 10)], 50, "custom")["status"] == "out_of_reach"
    assert required_average([witem(80, 100)], 90, "custom")["status"] == "no_remaining"


# --- conflicts ------------------------------------------------------------

def meeting(section_id, day, start, end):
    return {"section_id": section_id, "day_of_week": day, "start_time": start, "end_time": end}


def test_overlap_on_same_day_conflicts():
    conflicts = find_conflicts([
        meeting(1, 0, time(9), time(9, 50)),
        meeting(2, 0, time(9, 30), time(10, 45)),
    ])
    assert len(conflicts) == 1
    assert conflicts[0]["section_ids"] == [1, 2]
    assert conflicts[0]["start"] == time(9, 30)
    assert conflicts[0]["end"] == time(9, 50)


def test_back_to_back_and_different_days_do_not_conflict():
    assert find_conflicts([
        meeting(1, 0, time(9), time(10)),
        meeting(2, 0, time(10), time(11)),
        meeting(3, 1, time(9), time(10)),
    ]) == []


def test_meetings_of_same_section_never_conflict():
    assert find_conflicts([meeting(1, 2, time(9), time(12)), meeting(1, 2, time(10), time(11))]) == []


def test_conflicting_section_ids():
    conflicts = find_conflicts([
        meeting(1, 0, time(9), time(10)), meeting(2, 0, time(9), time(10)),
        meeting(3, 4, time(13), time(14)), meeting(4, 4, time(13, 30), time(15)),
        meeting(5, 4, time(16), time(17)),
    ])
    assert conflicting_section_ids(conflicts) == [1, 2, 3, 4]


# --- recurrence -----------------------------------------------------------

def test_single_event_in_and_out_of_range():
    event = {"start_at": datetime(2026, 10, 5, 9), "end_at": datetime(2026, 10, 5, 10)}
    assert list(expand_event(event, datetime(2026, 10, 5), datetime(2026, 10, 6))) == [
        (datetime(2026, 10, 5, 9), datetime(2026, 10, 5, 10))
    ]
    assert list(expand_event(event, datetime(2026, 10, 6), datetime(2026, 10, 7))) == []


def test_weekly_on_multiple_days_with_until():
    event = {
        "start_at": datetime(2026, 9, 2, 16), "end_at": datetime(2026, 9, 2, 19),  # a Wednesday
        "recurrence_freq": "WEEKLY", "recurrence_days": "MO,WE",
        "recurrence_until": date(2026, 9, 14),
    }
    starts = [s for s, _ in expand_event(event, datetime(2026, 8, 1), datetime(2026, 10, 1))]
    assert starts == [
        datetime(2026, 9, 2, 16), datetime(2026, 9, 7, 16),
        datetime(2026, 9, 9, 16), datetime(2026, 9, 14, 16),
    ]


def test_weekly_always_includes_start_day():
    event = {
        "start_at": datetime(2026, 9, 1, 18), "end_at": datetime(2026, 9, 1, 19),  # Tuesday
        "recurrence_freq": "WEEKLY", "recurrence_days": "TH",
    }
    starts = [s for s, _ in expand_event(event, datetime(2026, 9, 1), datetime(2026, 9, 8))]
    assert starts == [datetime(2026, 9, 1, 18), datetime(2026, 9, 3, 18)]


def test_occurrence_spanning_range_start_is_included():
    event = {
        "start_at": datetime(2026, 9, 1, 22), "end_at": datetime(2026, 9, 2, 2),
        "recurrence_freq": "DAILY",
    }
    occurrences = list(expand_event(event, datetime(2026, 9, 3), datetime(2026, 9, 4)))
    assert occurrences == [
        (datetime(2026, 9, 2, 22), datetime(2026, 9, 3, 2)),
        (datetime(2026, 9, 3, 22), datetime(2026, 9, 4, 2)),
    ]


def test_daily_interval_and_monthly():
    every_other = {
        "start_at": datetime(2026, 9, 1, 7), "end_at": datetime(2026, 9, 1, 8),
        "recurrence_freq": "DAILY", "recurrence_interval": 2,
    }
    assert len(list(expand_event(every_other, datetime(2026, 9, 1), datetime(2026, 9, 11)))) == 5

    monthly = {
        "start_at": datetime(2026, 9, 1), "end_at": datetime(2026, 9, 2),
        "recurrence_freq": "MONTHLY",
    }
    starts = [s for s, _ in expand_event(monthly, datetime(2026, 10, 1), datetime(2027, 1, 1))]
    assert starts == [datetime(2026, 10, 1), datetime(2026, 11, 1), datetime(2026, 12, 1)]


def test_parse_weekdays():
    assert parse_weekdays("we, MO,we") == [0, 2]
    assert parse_weekdays(None) == []
    with pytest.raises(ValueError):
        parse_weekdays("XX")


def test_weekly_meeting_bounded_by_term_and_range():
    # Term Mon Aug 31 - Fri Dec 11 2026; class on Fridays.
    occurrences = list(expand_weekly_meeting(
        4, time(10), time(10, 50),
        date(2026, 8, 31), date(2026, 12, 11),
        datetime(2026, 12, 1), datetime(2026, 12, 31),
    ))
    assert [s.date() for s, _ in occurrences] == [date(2026, 12, 4), date(2026, 12, 11)]
    assert occurrences[0][1] == datetime(2026, 12, 4, 10, 50)


def test_weekly_meeting_outside_term_is_empty():
    assert list(expand_weekly_meeting(
        0, time(9), time(10), date(2027, 1, 19), date(2027, 5, 7),
        datetime(2026, 10, 1), datetime(2026, 11, 1),
    )) == []
