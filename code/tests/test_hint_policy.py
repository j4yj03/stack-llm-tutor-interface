import pytest

from app.hint_policy import HintPolicyError


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