import json

import pytest

from app import hint_policy as policy_module
from app.hint_policy import HintPolicy, HintPolicyError


def test_all_hint_levels_exist(hint_policy):
    for level in range(0, 5):
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
    [5, -1, "1", True, 1.0, None]
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


def test_stage_zero_is_diagnostic_without_reference_disclosure(hint_policy):
    level = hint_policy.get(0)
    assert level["name"] == "Diagnosephase"
    assert level["max_words"] == 70
    assert level["include_solution_steps"] is False
    assert level["max_solution_steps"] == 0
    assert level["include_final_answer"] is False


def test_missing_stage_zero_fails_without_implicit_migration(hint_policy_path):
    data = json.loads(hint_policy_path.read_text(encoding="utf-8"))
    del data["0"]
    hint_policy_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(HintPolicyError, match="Hilfestufe 0 fehlt"):
        HintPolicy(hint_policy_path)


@pytest.mark.parametrize("field,value", [
    ("name", ""), ("name", 1), ("goal", "  "), ("goal", []),
    ("max_words", 0), ("max_words", -1), ("max_words", True), ("max_words", 1.5),
    ("may_include", "a rule"), ("may_include", [1]), ("must_not_include", [""]),
    ("include_solution_steps", "false"), ("include_final_answer", 1),
    ("unknown", True)
])
def test_all_policy_fields_are_strictly_validated(hint_policy_path, field, value):
    data = json.loads(hint_policy_path.read_text(encoding="utf-8"))
    data["1"][field] = value
    hint_policy_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(HintPolicyError, match=field):
        HintPolicy(hint_policy_path)


@pytest.mark.parametrize("raw", ["[]", "{", '{"0": []}', '{"00": {}}'])
def test_invalid_policy_file_raises_domain_error(hint_policy_path, raw):
    hint_policy_path.write_text(raw, encoding="utf-8")
    with pytest.raises(HintPolicyError):
        HintPolicy(hint_policy_path)


@pytest.mark.parametrize("full", [False, True])
def test_json_override_applies_to_explicit_policy_path(hint_policy_path, monkeypatch, full):
    original = json.loads(hint_policy_path.read_text(encoding="utf-8"))
    overrides = original if full else {"1": {}}
    overrides["1"].update({"max_words": 42, "goal": "A generic experimental goal."})
    monkeypatch.setenv("TUTOR_HINT_POLICY_JSON", json.dumps(overrides))
    policy = HintPolicy(path=hint_policy_path)
    assert policy.get(1)["max_words"] == 42
    assert policy.get(1)["goal"] == "A generic experimental goal."
    assert policy.get(0)["name"] == "Diagnosephase"
    assert policy.get(4)["max_solution_steps"] is None
    assert json.loads(hint_policy_path.read_text(encoding="utf-8"))["1"]["max_words"] == 70


def test_per_level_overrides_take_precedence_without_templating(hint_policy_path, monkeypatch):
    monkeypatch.setenv("TUTOR_HINT_POLICY_JSON", '{"1":{"max_words":30,"name":"JSON name"}}')
    environment = {
        "NAME": "{student_answer.__class__} ${LLM_API_KEY}",
        "GOAL": "A configurable goal.",
        "MAX_WORDS": "40",
        "MAX_SOLUTION_STEPS": "2",
        "INCLUDE_SOLUTION_STEPS": "true",
        "INCLUDE_FINAL_ANSWER": "yes",
        "MAY_INCLUDE": '["a question, with a comma", "a rule"]',
        "MUST_NOT_INCLUDE": "a full derivation; a second question"
    }
    for suffix, value in environment.items():
        monkeypatch.setenv(f"TUTOR_LEVEL_1_{suffix}", value)
    level = HintPolicy(hint_policy_path).get(1)
    assert level == {
        "name": "{student_answer.__class__} ${LLM_API_KEY}",
        "goal": "A configurable goal.",
        "max_words": 40,
        "max_solution_steps": 2,
        "include_solution_steps": True,
        "include_final_answer": True,
        "may_include": ["a question, with a comma", "a rule"],
        "must_not_include": ["a full derivation", "a second question"]
    }


def test_per_level_null_limit_and_empty_lists(hint_policy_path, monkeypatch):
    monkeypatch.setenv("TUTOR_LEVEL_3_MAX_SOLUTION_STEPS", "null")
    monkeypatch.setenv("TUTOR_LEVEL_3_MAY_INCLUDE", "[]")
    monkeypatch.setenv("TUTOR_LEVEL_3_MUST_NOT_INCLUDE", "")
    monkeypatch.setenv("TUTOR_LEVEL_3_INCLUDE_SOLUTION_STEPS", "off")
    level = HintPolicy(hint_policy_path).get(3)
    assert level["max_solution_steps"] is None
    assert level["may_include"] == []
    assert level["must_not_include"] == []
    assert level["include_solution_steps"] is False


@pytest.mark.parametrize("raw", [
    "{", "[]", "null", '{"5": {}}', '{"1": []}',
    '{"1": {"max_words":0}}', '{"1": {"name":false}}',
    '{"1": {"include_final_answer":"true"}}', '{"1": {"typo":1}}'
])
def test_invalid_json_overrides_fail_fast(hint_policy_path, monkeypatch, raw):
    monkeypatch.setenv("TUTOR_HINT_POLICY_JSON", raw)
    with pytest.raises(HintPolicyError):
        HintPolicy(hint_policy_path)


@pytest.mark.parametrize("suffix,value", [
    ("MAX_WORDS", "0"), ("MAX_WORDS", "true"), ("MAX_WORDS", "many"),
    ("MAX_SOLUTION_STEPS", "-1"), ("MAX_SOLUTION_STEPS", "1.5"),
    ("INCLUDE_FINAL_ANSWER", "maybe"), ("NAME", ""), ("GOAL", ""),
    ("MAY_INCLUDE", "["), ("MAY_INCLUDE", '["one", 2]'),
    ("MAY_INCLUDE", '{"a":1}'), ("MAY_INCLUDE", '"a rule"'),
    ("MUST_NOT_INCLUDE", "null"), ("UNKNOWN", "1")
])
def test_invalid_per_level_overrides_fail_fast(hint_policy_path, monkeypatch, suffix, value):
    monkeypatch.setenv(f"TUTOR_LEVEL_1_{suffix}", value)
    with pytest.raises(HintPolicyError):
        HintPolicy(hint_policy_path)


def test_per_level_override_cannot_create_unconfigured_level(hint_policy_path, monkeypatch):
    monkeypatch.setenv("TUTOR_LEVEL_5_GOAL", "Not in the policy file.")
    with pytest.raises(HintPolicyError, match="TUTOR_LEVEL_5_GOAL"):
        HintPolicy(hint_policy_path)


def test_only_active_levels_are_exposed(hint_policy_path, monkeypatch):
    monkeypatch.setattr(policy_module, "MAX_HINT_LEVEL", 2)
    policy = HintPolicy(hint_policy_path)
    assert set(policy.levels) == {"0", "1", "2"}
    with pytest.raises(HintPolicyError):
        policy.get(3)


def test_extending_maximum_requires_explicit_policy_level(hint_policy_path, monkeypatch):
    monkeypatch.setattr(policy_module, "MAX_HINT_LEVEL", 5)
    with pytest.raises(HintPolicyError, match="Hilfestufe 5 fehlt"):
        HintPolicy(hint_policy_path)
    data = json.loads(hint_policy_path.read_text(encoding="utf-8"))
    data["5"] = dict(data["4"], name="Custom final level")
    hint_policy_path.write_text(json.dumps(data), encoding="utf-8")
    assert HintPolicy(hint_policy_path).get(5)["name"] == "Custom final level"
