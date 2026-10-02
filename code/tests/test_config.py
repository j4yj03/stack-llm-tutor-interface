import os
import runpy

import pytest

from app import config


def test_default_context_options_match_expected_html_set():
    parsed = config._parse_context_options(
        config._DEFAULT_CONTEXT_OPTIONS
    )

    assert parsed == {
        "question_text": True,
        "student_answer": True,
        "diagnosis_code": True,
        "prt_feedback": True,
        "score": False,
        "learning_goals": True,
        "math_rules": False,
        "solution_steps": True,
        "final_answer": True,
        "chat_history": True,
    }


def test_parse_accepts_include_prefix_and_whitespace():
    parsed = config._parse_context_options(
        " include_score , include_chat_history ,"
    )

    assert parsed["score"] is True
    assert parsed["chat_history"] is True
    assert parsed["learning_goals"] is False


@pytest.mark.parametrize("raw", ["nonsense", "question_text,foo", "SCORES"])
def test_parse_unknown_option_prevents_startup(raw):
    with pytest.raises(RuntimeError, match="Unbekannte Kontextoption"):
        config._parse_context_options(raw)


def test_schema_fields_match_configured_options():
    # Drift-Sicherung: Jede ContextOptions-Option muss in der .env-
    # Konfiguration (Keys ohne include_-Praefix) vorhanden sein.
    from app.schemas import ContextOptions

    fields = {
        name.removeprefix("include_")
        for name in ContextOptions.model_fields
    }

    assert fields == set(config.CONTEXT_OPTIONS_ENABLED.keys())


def test_context_option_defaults_follow_config():
    # Wiring-Prüfung: Die Defaultwerte jeder ContextOptions-Option
    # stammen 1:1 aus CONTEXT_OPTIONS_ENABLED (also aus der .env).
    from app.schemas import ContextOptions

    for name, field in ContextOptions.model_fields.items():
        key = name.removeprefix("include_")
        assert field.default == config.CONTEXT_OPTIONS_ENABLED[key]


@pytest.fixture
def clean_configuration_environment(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    for name in list(os.environ):
        if name.startswith(("LLM_", "TUTOR_", "EVALUATION_")) or name in {
            "MAX_HINT_LEVEL", "HINT_LEVELS_PATH", "CONTEXT_OPTIONS", "DEBUG_MODE"
        }:
            monkeypatch.delenv(name)


def test_runtime_configuration_defaults(clean_configuration_environment):
    values = runpy.run_path(config.__file__)
    expected = {
        "MIN_HINT_LEVEL": 0,
        "MAX_HINT_LEVEL": 4,
        "DEFAULT_HINT_LEVEL": 1,
        "TUTOR_START_MODE": "fixed",
        "TUTOR_DIAGNOSIS_MODE": "provided",
        "TUTOR_POLICY_MODE": "tutor",
        "TUTOR_RESPONSE_FORMAT": "text",
        "TUTOR_RULES_ID": "default-policy",
        "LLM_TEMPERATURE": 0.2,
        "LLM_MAX_TOKENS": 400,
        "TUTOR_ASK_ACTIVATING_QUESTION": True,
        "TUTOR_HIDE_HINT_LEVEL": True,
        "TUTOR_ENFORCE_WORD_LIMIT": True,
        "TUTOR_LATEX_NOTATION": True,
        "TUTOR_ADAPTIVE_ENABLED": False,
        "TUTOR_ADAPTIVE_AFTER_SECONDS": 120.0,
        "TUTOR_ADAPTIVE_STEP": 1,
        "TUTOR_ADAPTIVE_MAX_LEVEL": 4,
        "TUTOR_ADAPTIVE_CONFUSION_PHRASES": [
            "ich verstehe nicht", "keine ahnung", "ich weiss nicht", "no idea"
        ],
        "EVALUATION_API_ENABLED": False,
        "EVALUATION_API_TOKEN": "",
        "EVALUATION_JUDGE_MODEL": "",
        "EVALUATION_JUDGE_TEMPERATURE": 0.0,
        "EVALUATION_JUDGE_MAX_TOKENS": 1200
    }
    assert {name: values[name] for name in expected} == expected
    assert values["HINT_LEVELS_PATH"] == config.BASE_DIR / "config" / "hint_levels.json"
    assert values["TUTOR_STAGE0_CONTEXT_OPTIONS"] == config._parse_context_options(
        "question_text,student_answer,learning_goals,math_rules,chat_history"
    )


@pytest.mark.parametrize("name,value", [
    ("MAX_HINT_LEVEL", "-1"),
    ("MAX_HINT_LEVEL", "33"),
    ("MAX_HINT_LEVEL", "1.5"),
    ("TUTOR_START_LEVEL", "-1"),
    ("TUTOR_START_LEVEL", "5"),
    ("TUTOR_START_MODE", "auto"),
    ("TUTOR_DIAGNOSIS_MODE", "prt"),
    ("TUTOR_POLICY_MODE", "special"),
    ("TUTOR_RESPONSE_FORMAT", "json"),
    ("TUTOR_RULES_ID", " "),
    ("HINT_LEVELS_PATH", ""),
    ("LLM_TEMPERATURE", "nan"),
    ("LLM_TEMPERATURE", "inf"),
    ("LLM_TEMPERATURE", "-0.1"),
    ("LLM_TEMPERATURE", "2.1"),
    ("LLM_MAX_TOKENS", "0"),
    ("LLM_MAX_TOKENS", "32769"),
    ("LLM_MAX_TOKENS", "1.5"),
    ("LLM_DISABLE_THINKING", "maybe"),
    ("LLM_TIMEOUT", "0"),
    ("LLM_RETRY_DELAY", "nan"),
    ("LLM_RETRY_DELAY", "-1"),
    ("TUTOR_ADAPTIVE_ENABLED", "maybe"),
    ("TUTOR_ADAPTIVE_AFTER_SECONDS", "-1"),
    ("TUTOR_ADAPTIVE_AFTER_SECONDS", "inf"),
    ("TUTOR_ADAPTIVE_STEP", "0"),
    ("TUTOR_ADAPTIVE_STEP", "1.5"),
    ("TUTOR_ADAPTIVE_MAX_LEVEL", "5"),
    ("TUTOR_ASK_ACTIVATING_QUESTION", "maybe"),
    ("TUTOR_HIDE_HINT_LEVEL", ""),
    ("TUTOR_ENFORCE_WORD_LIMIT", "maybe"),
    ("TUTOR_LATEX_NOTATION", "maybe"),
    ("TUTOR_STAGE0_CONTEXT_OPTIONS", "answer"),
    ("EVALUATION_API_ENABLED", "maybe"),
    ("EVALUATION_JUDGE_TEMPERATURE", "nan"),
    ("EVALUATION_JUDGE_TEMPERATURE", "2.1"),
    ("EVALUATION_JUDGE_MAX_TOKENS", "0"),
    ("EVALUATION_JUDGE_MAX_TOKENS", "32769")
])
def test_invalid_runtime_environment_fails_startup(
    clean_configuration_environment, monkeypatch, name, value
):
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=name):
        runpy.run_path(config.__file__)


def test_runtime_environment_controls_are_independent(
    clean_configuration_environment, monkeypatch
):
    environment = {
        "MAX_HINT_LEVEL": "3",
        "TUTOR_START_LEVEL": "0",
        "TUTOR_START_MODE": " INDIVIDUAL ",
        "TUTOR_DIAGNOSIS_MODE": "MODEL",
        "TUTOR_POLICY_MODE": "general",
        "TUTOR_RESPONSE_FORMAT": "structured",
        "TUTOR_RULES_ID": "condition-b",
        "LLM_TEMPERATURE": "2",
        "LLM_MAX_TOKENS": "32768",
        "TUTOR_ADAPTIVE_ENABLED": "yes",
        "TUTOR_ADAPTIVE_AFTER_SECONDS": "0",
        "TUTOR_ADAPTIVE_STEP": "2",
        "TUTOR_ADAPTIVE_MAX_LEVEL": "2",
        "TUTOR_ADAPTIVE_CONFUSION_PHRASES": " No Idea ; KEINE AHNUNG,no idea,, ",
        "TUTOR_ASK_ACTIVATING_QUESTION": "off",
        "TUTOR_HIDE_HINT_LEVEL": "false",
        "TUTOR_ENFORCE_WORD_LIMIT": "0",
        "TUTOR_LATEX_NOTATION": "off",
        "TUTOR_STAGE0_CONTEXT_OPTIONS": "include_question_text;include_score"
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    values = runpy.run_path(config.__file__)
    assert values["MAX_HINT_LEVEL"] == 3
    assert values["DEFAULT_HINT_LEVEL"] == 0
    assert values["TUTOR_START_MODE"] == "individual"
    assert values["TUTOR_DIAGNOSIS_MODE"] == "model"
    assert values["TUTOR_POLICY_MODE"] == "general"
    assert values["TUTOR_RESPONSE_FORMAT"] == "structured"
    assert values["TUTOR_RULES_ID"] == "condition-b"
    assert values["LLM_TEMPERATURE"] == 2.0
    assert values["LLM_MAX_TOKENS"] == 32768
    assert values["TUTOR_ADAPTIVE_ENABLED"] is True
    assert values["TUTOR_ADAPTIVE_AFTER_SECONDS"] == 0.0
    assert values["TUTOR_ADAPTIVE_STEP"] == 2
    assert values["TUTOR_ADAPTIVE_MAX_LEVEL"] == 2
    assert values["TUTOR_ADAPTIVE_CONFUSION_PHRASES"] == ["no idea", "keine ahnung"]
    assert values["TUTOR_ASK_ACTIVATING_QUESTION"] is False
    assert values["TUTOR_HIDE_HINT_LEVEL"] is False
    assert values["TUTOR_ENFORCE_WORD_LIMIT"] is False
    assert values["TUTOR_LATEX_NOTATION"] is False
    assert values["TUTOR_STAGE0_CONTEXT_OPTIONS"] == config._parse_context_options(
        "question_text,score"
    )


@pytest.mark.parametrize("maximum", [0, 2, 6])
def test_start_and_adaptive_levels_use_configured_range(
    clean_configuration_environment, monkeypatch, maximum
):
    monkeypatch.setenv("MAX_HINT_LEVEL", str(maximum))
    monkeypatch.setenv("TUTOR_START_LEVEL", str(maximum))
    values = runpy.run_path(config.__file__)
    assert values["DEFAULT_HINT_LEVEL"] == maximum
    assert values["TUTOR_ADAPTIVE_MAX_LEVEL"] == maximum


@pytest.mark.parametrize("absolute", [False, True])
def test_hint_policy_path_resolves_against_base_directory(
    clean_configuration_environment, monkeypatch, tmp_path, absolute
):
    path = tmp_path / "policy.json" if absolute else "other/policy.json"
    monkeypatch.setenv("HINT_LEVELS_PATH", str(path))
    values = runpy.run_path(config.__file__)
    assert values["HINT_LEVELS_PATH"] == (path if absolute else config.BASE_DIR / path)


@pytest.mark.parametrize("token", ["", "   "])
def test_evaluation_api_requires_token_when_enabled(
    clean_configuration_environment, monkeypatch, token
):
    monkeypatch.setenv("EVALUATION_API_ENABLED", "1")
    monkeypatch.setenv("EVALUATION_API_TOKEN", token)
    with pytest.raises(RuntimeError, match="EVALUATION_API_TOKEN"):
        runpy.run_path(config.__file__)


def test_evaluation_configuration_does_not_select_implicit_judge(
    clean_configuration_environment, monkeypatch
):
    monkeypatch.setenv("EVALUATION_API_ENABLED", "true")
    monkeypatch.setenv("EVALUATION_API_TOKEN", "offline-test-token")
    values = runpy.run_path(config.__file__)
    assert values["EVALUATION_API_ENABLED"] is True
    assert values["EVALUATION_API_TOKEN"] == "offline-test-token"
    assert values["EVALUATION_JUDGE_MODEL"] == ""
