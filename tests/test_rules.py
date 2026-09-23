import akim

VALID_PLAN = [
    {"measure": "M9", "district": "Нура"},
    {"measure": "M11", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M4", "district": "Нура"},
]


def codes(plan):
    return [v["code"] for v in akim.validate(plan)]


def test_normalize_plan_uppercases_measure_and_clears_empty_district():
    normalized = akim.normalize_plan([
        {"measure": "m7", "district": ""},
        {"measure": " m1 ", "district": None},
        {"measure": "M12"},
    ])
    assert normalized == [
        {"measure": "M7", "district": None},
        {"measure": "M1", "district": None},
        {"measure": "M12", "district": None},
    ]


def test_valid_plan_has_no_violations():
    assert akim.validate(VALID_PLAN) == []


def test_count_violation_when_not_five_decisions():
    violations = akim.validate(VALID_PLAN[:4])
    assert codes(VALID_PLAN[:4]) == ["count"]
    assert "4" in violations[0]["message"]


def test_duplicate_measure_violation():
    plan = VALID_PLAN + [VALID_PLAN[0]]
    assert "duplicate" in codes(plan)


def test_budget_exceeded_violation():
    plan = [
        {"measure": "M3", "district": "Нура"},
        {"measure": "M13", "district": "Байконур"},
        {"measure": "M7", "district": "Есиль"},
        {"measure": "M5", "district": "Алматы"},
        {"measure": "M6", "district": None},
    ]
    violations = akim.validate(plan)
    assert "budget" in [v["code"] for v in violations]
    message = next(v["message"] for v in violations if v["code"] == "budget")
    assert "127" in message and "100" in message


def test_district_required_for_district_scope_measure():
    plan = [{"measure": "M1", "district": None}] + VALID_PLAN[1:]
    assert "district_required" in codes(plan)


def test_district_not_allowed_for_city_scope_measure():
    plan = [{"measure": "M6", "district": "Нура"}] + VALID_PLAN[1:]
    assert "district_not_allowed" in codes(plan)


def test_direction_limit_violation_with_three_transport_measures():
    plan = [
        {"measure": "M1", "district": "Нура"},
        {"measure": "M2", "district": None},
        {"measure": "M3", "district": "Алматы"},
        {"measure": "M10", "district": "Нура"},
        {"measure": "M12", "district": None},
    ]
    assert "direction_limit" in codes(plan)


def test_conflict_m1_and_m3_any_district():
    plan = [
        {"measure": "M1", "district": "Нура"},
        {"measure": "M3", "district": "Алматы"},
        {"measure": "M10", "district": "Нура"},
        {"measure": "M9", "district": "Байконур"},
        {"measure": "M12", "district": None},
    ]
    assert "conflict" in codes(plan)


def test_conflict_m4_and_m7_same_district():
    plan = [
        {"measure": "M4", "district": "Нура"},
        {"measure": "M7", "district": "Нура"},
        {"measure": "M10", "district": "Нура"},
        {"measure": "M9", "district": "Байконур"},
        {"measure": "M12", "district": None},
    ]
    assert "conflict" in codes(plan)


def test_conflict_m4_and_m7_different_districts_is_ok():
    plan = [
        {"measure": "M4", "district": "Нура"},
        {"measure": "M7", "district": "Байконур"},
        {"measure": "M10", "district": "Нура"},
        {"measure": "M9", "district": "Есиль"},
        {"measure": "M12", "district": None},
    ]
    assert akim.validate(plan) == []


def test_conflict_m5_and_m13_same_district():
    plan = [
        {"measure": "M5", "district": "Нура"},
        {"measure": "M13", "district": "Нура"},
        {"measure": "M10", "district": "Байконур"},
        {"measure": "M9", "district": "Есиль"},
        {"measure": "M12", "district": None},
    ]
    assert "conflict" in codes(plan)


def test_unknown_measure_violation():
    plan = [{"measure": "M99", "district": None}] + VALID_PLAN[1:]
    assert "unknown_measure" in codes(plan)


def test_unknown_district_violation():
    plan = [{"measure": "M1", "district": "Марс"}] + VALID_PLAN[1:]
    assert "unknown_district" in codes(plan)
