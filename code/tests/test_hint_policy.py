import json

import pytest

from app.hint_policy import HintPolicy, HintPolicyError


def test_all_hint_levels_exist(hint_policy):
    for level in range(1, 5):
        config = hint_policy.get(level)
        assert config["name"]
        assert config["goal"]


def test_level_one_hides_solution(hint_policy):
    level = hint_policy.get(1)

    assert level["include_solution_steps"] is False
    assert level["include_final_answer"] is False
    assert "Endergebnis" in level[
        "must_not_include"
    ]


def test_level_four_allows_final_answer(
    hint_policy
):
    level = hint_policy.get(4)

    assert level["include_solution_steps"] is True
    assert level["include_final_answer"] is True


@pytest.mark.parametrize(
    "level",
    [0, 5, -1]
)
def test_invalid_hint_level_is_rejected(
    hint_policy,
    level
):
    with pytest.raises(HintPolicyError):
        hint_policy.get(level)


@pytest.mark.parametrize("limit", [-1, 1.5, "3", True])
def test_invalid_solution_step_limit_is_rejected(hint_policy_path, limit):
    data = json.loads(hint_policy_path.read_text(encoding="utf-8"))
    data["3"]["max_solution_steps"] = limit
    hint_policy_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(HintPolicyError, match="max_solution_steps"):
        HintPolicy(hint_policy_path)


def test_missing_solution_step_limit_is_rejected(hint_policy_path):
    data = json.loads(hint_policy_path.read_text(encoding="utf-8"))
    del data["3"]["max_solution_steps"]
    hint_policy_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(HintPolicyError, match="max_solution_steps"):
        HintPolicy(hint_policy_path)
