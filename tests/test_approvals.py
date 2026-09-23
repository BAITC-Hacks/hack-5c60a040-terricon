import pytest

from akim import approvals

EXAMPLE = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(approvals, "STORE", tmp_path / "approved.json")


def test_approve_valid_plan_is_stored():
    item = approvals.approve(EXAMPLE, note="первый")
    assert item["score"] == 56.54
    assert item["budget_used"] == 95
    saved = approvals.approved()
    assert len(saved) == 1 and saved[0]["note"] == "первый"


def test_invalid_plan_cannot_be_approved():
    with pytest.raises(ValueError, match="недопустим"):
        approvals.approve(EXAMPLE[:4])
    assert approvals.approved() == []
