import json

import pytest

from app import config
from app.runtime_config import (
    configuration_hash,
    effective_context_options,
    public_configuration
)
from app.schemas import ContextOptions


def test_stage_zero_caps_context_without_mutating_request(monkeypatch):
    monkeypatch.setattr(config, "TUTOR_DIAGNOSIS_MODE", "provided")
    monkeypatch.setattr(config, "TUTOR_STAGE0_CONTEXT_OPTIONS", config._parse_context_options(
        "question_text,student_answer,learning_goals,math_rules,chat_history"
    ))
    options = ContextOptions(**{name: True for name in ContextOptions.model_fields})
    effective = effective_context_options(options, 0)
    assert {name for name, enabled in effective.model_dump().items() if enabled} == {
        "include_question_text", "include_student_answer", "include_learning_goals",
        "include_math_rules", "include_chat_history"
    }
    assert all(options.model_dump().values())


def test_stage_zero_cap_is_independent_and_never_enables_requested_false(monkeypatch):
    monkeypatch.setattr(config, "TUTOR_DIAGNOSIS_MODE", "provided")
    monkeypatch.setattr(config, "TUTOR_STAGE0_CONTEXT_OPTIONS", config._parse_context_options(
        "score,diagnosis_code"
    ))
    options = ContextOptions(**{name: False for name in ContextOptions.model_fields})
    options.include_diagnosis_code = True
    effective = effective_context_options(options, 0)
    assert effective.include_diagnosis_code is True
    assert effective.include_score is False
    assert sum(effective.model_dump().values()) == 1


@pytest.mark.parametrize("level", [1, 3, 4])
def test_nonzero_context_remains_unchanged_in_provided_mode(monkeypatch, level):
    monkeypatch.setattr(config, "TUTOR_DIAGNOSIS_MODE", "provided")
    options = ContextOptions(include_score=True, include_math_rules=True, include_chat_history=False)
    assert effective_context_options(options, level).model_dump() == options.model_dump()


@pytest.mark.parametrize("mode", ["model", "none"])
@pytest.mark.parametrize("level", [0, 1, 4])
def test_diagnosis_modes_remove_provided_context_and_feedback(monkeypatch, mode, level):
    monkeypatch.setattr(config, "TUTOR_DIAGNOSIS_MODE", mode)
    monkeypatch.setattr(config, "TUTOR_STAGE0_CONTEXT_OPTIONS", config._parse_context_options(
        ",".join(config.CONTEXT_OPTIONS_ENABLED)
    ))
    options = ContextOptions(**{name: True for name in ContextOptions.model_fields})
    effective = effective_context_options(options, level).model_dump()
    assert effective["include_diagnosis_code"] is False
    assert effective["include_prt_feedback"] is False
    assert all(value for name, value in effective.items() if name not in {
        "include_diagnosis_code", "include_prt_feedback"
    })
    assert all(options.model_dump().values())


def test_public_configuration_records_effective_settings_without_secrets(hint_policy, monkeypatch):
    monkeypatch.setattr(config, "LLM_API_KEY", "test-provider-secret")
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://user:password@private-upstream.invalid/")
    monkeypatch.setattr(config, "EVALUATION_API_TOKEN", "test-evaluation-secret")
    monkeypatch.setattr(config, "ALLOWED_MODELS", {"not-a-selected-model"})
    values = public_configuration(hint_policy)
    assert values["schema_version"] == "tutor-config-1"
    assert values["hint_policy"] == hint_policy.levels
    assert values["generation"] == {
        "model": config.LLM_MODEL,
        "api_mode": config.LLM_API_MODE,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": config.LLM_MAX_TOKENS,
        "disable_thinking_requested": config.LLM_DISABLE_THINKING,
        "timeout": config.LLM_TIMEOUT,
        "retry_delay": config.LLM_RETRY_DELAY
    }
    assert values["tutor_rules"] == {
        "rules_id": config.TUTOR_RULES_ID,
        "diagnosis_mode": config.TUTOR_DIAGNOSIS_MODE,
        "policy_mode": config.TUTOR_POLICY_MODE,
        "response_format": config.TUTOR_RESPONSE_FORMAT,
        "ask_activating_question": config.TUTOR_ASK_ACTIVATING_QUESTION,
        "hide_hint_level": config.TUTOR_HIDE_HINT_LEVEL,
        "enforce_word_limit": config.TUTOR_ENFORCE_WORD_LIMIT,
        "latex_notation": config.TUTOR_LATEX_NOTATION
    }
    assert values["start"] == {
        "mode": config.TUTOR_START_MODE, "level": config.DEFAULT_HINT_LEVEL,
        "min_level": 0, "max_level": config.MAX_HINT_LEVEL
    }
    assert values["adaptation"] == {
        "enabled": config.TUTOR_ADAPTIVE_ENABLED,
        "after_seconds": config.TUTOR_ADAPTIVE_AFTER_SECONDS,
        "step": config.TUTOR_ADAPTIVE_STEP,
        "max_level": config.TUTOR_ADAPTIVE_MAX_LEVEL,
        "confusion_phrases": config.TUTOR_ADAPTIVE_CONFUSION_PHRASES
    }
    assert set(values["context_defaults"]) == set(ContextOptions.model_fields)
    assert set(values["stage0_context_options"]) == set(ContextOptions.model_fields)
    assert values["limits"]["max_history_messages"] == config.MAX_HISTORY_MESSAGES
    serialized = json.dumps(values)
    for forbidden in (
        "test-provider-secret", "test-evaluation-secret", "private-upstream",
        "password", "not-a-selected-model", "api_key", "base_url", "allowed_models"
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize("mode", ["provided", "model", "none"])
def test_public_context_flags_match_effective_generation(hint_policy, monkeypatch, mode):
    monkeypatch.setattr(config, "TUTOR_DIAGNOSIS_MODE", mode)
    monkeypatch.setattr(config, "DEFAULT_HINT_LEVEL", 0)
    monkeypatch.setattr(config, "TUTOR_STAGE0_CONTEXT_OPTIONS", config._parse_context_options(
        "question_text,diagnosis_code,prt_feedback,math_rules"
    ))
    defaults = ContextOptions(**{
        f"include_{name}": enabled for name, enabled in config.CONTEXT_OPTIONS_ENABLED.items()
    })
    values = public_configuration(hint_policy)
    assert values["context_defaults"] == effective_context_options(defaults, config.MAX_HINT_LEVEL).model_dump()
    assert values["stage0_context_options"]["include_math_rules"] is True
    assert values["stage0_context_options"]["include_diagnosis_code"] == (mode == "provided")
    assert values["stage0_context_options"]["include_prt_feedback"] == (mode == "provided")


def test_hash_keeps_later_defaults_observable_when_starting_at_zero(hint_policy, monkeypatch):
    monkeypatch.setattr(config, "TUTOR_DIAGNOSIS_MODE", "provided")
    monkeypatch.setattr(config, "DEFAULT_HINT_LEVEL", 0)
    monkeypatch.setattr(config, "MAX_HINT_LEVEL", 4)
    monkeypatch.setattr(config, "TUTOR_STAGE0_CONTEXT_OPTIONS", config._parse_context_options(
        "question_text,student_answer"
    ))
    monkeypatch.setattr(config, "CONTEXT_OPTIONS_ENABLED", config._parse_context_options("question_text"))
    before = public_configuration(hint_policy)
    monkeypatch.setattr(config, "CONTEXT_OPTIONS_ENABLED", config._parse_context_options("question_text,score"))
    after = public_configuration(hint_policy)
    assert before["stage0_context_options"] == after["stage0_context_options"]
    assert before["context_defaults"]["include_score"] is False
    assert after["context_defaults"]["include_score"] is True
    assert configuration_hash(before) != configuration_hash(after)


def test_configuration_hash_is_canonical_and_tracks_effective_changes(hint_policy, monkeypatch):
    values = public_configuration(hint_policy)
    original = configuration_hash(values)
    assert len(original) == 64
    assert int(original, 16) >= 0
    assert configuration_hash(dict(reversed(list(values.items())))) == original
    assert configuration_hash(json.loads(json.dumps(values, ensure_ascii=True))) == original
    monkeypatch.setattr(config, "TUTOR_RULES_ID", "new-condition")
    assert configuration_hash(public_configuration(hint_policy)) != original


def test_configuration_hash_excludes_credentials_allowlists_and_its_own_hash(hint_policy):
    values = public_configuration(hint_policy)
    original = configuration_hash(values)
    values.update({
        "LLM_API_KEY": "any-test-secret", "EVALUATION_API_TOKEN": "test-token",
        "allowed_models": ["different-model"], "configuration_hash": "self-reference"
    })
    values["generation"].update({
        "api_key": "secret", "base_url": "https://user:password@upstream.invalid/",
        "credentials": {"password": "secret"}
    })
    assert configuration_hash(values) == original


def test_configuration_hash_rejects_nonfinite_values():
    with pytest.raises(ValueError):
        configuration_hash({"temperature": float("nan")})


def test_history_retention_changes_configuration_identity(hint_policy, monkeypatch):
    before = configuration_hash(public_configuration(hint_policy))
    monkeypatch.setattr(config, "MAX_HISTORY_MESSAGES", 8)
    assert configuration_hash(public_configuration(hint_policy)) != before
