import pytest

import akim
from akim import teams


EXAMPLE = [
    {"measure": "M7", "district": "Нура"},
    {"measure": "M8", "district": "Нура"},
    {"measure": "M10", "district": "Нура"},
    {"measure": "M12", "district": None},
    {"measure": "M5", "district": "Сарыарка"},
]


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(teams, "STORE", tmp_path / "teams.json")


def test_submit_and_leaderboard_compare_teams():
    example = akim.submit("Terricon", EXAMPLE)
    assert example["score"] == 56.54
    assert example["rank"] == 566
    assert example["total"] == 694395
    assert example["budget_used"] == 95
    assert example["weakest"] == {"name": "Нура", "d": 52.96}

    best = akim.submit("Другая команда", akim.top(1)[0]["plan"])
    assert best["rank"] == 1
    board = akim.leaderboard()
    assert [row["team"] for row in board] == ["Другая команда", "Terricon"]
    assert [row["place"] for row in board] == [1, 2]
    assert board[0]["score"] == 57.24


def test_invalid_submission_does_not_change_board():
    with pytest.raises(ValueError, match="имя"):
        akim.submit("  ", EXAMPLE)
    with pytest.raises(ValueError, match="недопустим"):
        akim.submit("Terricon", EXAMPLE[:4])
    assert akim.leaderboard() == []


def test_second_submission_replaces_same_team():
    akim.submit("Terricon", EXAMPLE)
    replacement = akim.submit(" Terricon ", akim.top(1)[0]["plan"])
    board = akim.leaderboard()
    assert len(board) == 1
    assert board[0]["team"] == "Terricon"
    assert board[0]["score"] == replacement["score"] == 57.24
