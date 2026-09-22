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
