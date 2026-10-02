import hashlib
import json
from typing import Dict

from app import config
from app.hint_policy import HintPolicy
from app.schemas import ContextOptions


def effective_context_options(options: ContextOptions, level: int) -> ContextOptions:
    flags = options.model_dump()
    if level == config.MIN_HINT_LEVEL:
        flags = {
            name: enabled and config.TUTOR_STAGE0_CONTEXT_OPTIONS[name.removeprefix("include_")]
            for name, enabled in flags.items()
        }
    if config.TUTOR_DIAGNOSIS_MODE in {"model", "none"}:
        flags["include_diagnosis_code"] = False
        flags["include_prt_feedback"] = False
    return ContextOptions(**flags)


def public_configuration(policy: HintPolicy) -> Dict:
    defaults = ContextOptions(**{
        f"include_{name}": enabled
        for name, enabled in config.CONTEXT_OPTIONS_ENABLED.items()
    })
    all_options = ContextOptions(**{name: True for name in ContextOptions.model_fields})
    return {
        "schema_version": "tutor-config-1",
        "hint_policy": policy.levels,
        "generation": {
            "model": config.LLM_MODEL,
            "api_mode": config.LLM_API_MODE,
            "temperature": config.LLM_TEMPERATURE,
            "max_tokens": config.LLM_MAX_TOKENS,
            "disable_thinking_requested": config.LLM_DISABLE_THINKING,
            "timeout": config.LLM_TIMEOUT,
            "retry_delay": config.LLM_RETRY_DELAY
        },
        "tutor_rules": {
            "rules_id": config.TUTOR_RULES_ID,
            "diagnosis_mode": config.TUTOR_DIAGNOSIS_MODE,
            "policy_mode": config.TUTOR_POLICY_MODE,
            "response_format": config.TUTOR_RESPONSE_FORMAT,
            "ask_activating_question": config.TUTOR_ASK_ACTIVATING_QUESTION,
            "hide_hint_level": config.TUTOR_HIDE_HINT_LEVEL,
            "enforce_word_limit": config.TUTOR_ENFORCE_WORD_LIMIT,
            "latex_notation": config.TUTOR_LATEX_NOTATION
        },
        "start": {
            "mode": config.TUTOR_START_MODE,
            "level": config.DEFAULT_HINT_LEVEL,
            "min_level": config.MIN_HINT_LEVEL,
            "max_level": config.MAX_HINT_LEVEL
        },
        "adaptation": {
            "enabled": config.TUTOR_ADAPTIVE_ENABLED,
            "after_seconds": config.TUTOR_ADAPTIVE_AFTER_SECONDS,
            "step": config.TUTOR_ADAPTIVE_STEP,
            "max_level": config.TUTOR_ADAPTIVE_MAX_LEVEL,
            "confusion_phrases": list(config.TUTOR_ADAPTIVE_CONFUSION_PHRASES)
        },
        "limits": {
            "max_history_messages": config.MAX_HISTORY_MESSAGES,
            "max_student_answer_length": config.MAX_STUDENT_ANSWER_LENGTH,
            "max_question_text_length": config.MAX_QUESTION_TEXT_LENGTH,
            "max_context_question_text": config.MAX_CONTEXT_QUESTION_TEXT,
            "max_chat_message_length": config.MAX_CHAT_MESSAGE_LENGTH,
        },
        # Keep later-level defaults observable even when the starting level is 0.
        "context_defaults": effective_context_options(defaults, config.MAX_HINT_LEVEL).model_dump(),
        "stage0_context_options": effective_context_options(all_options, config.MIN_HINT_LEVEL).model_dump()
    }


def configuration_hash(configuration: Dict) -> str:
    excluded = {
        "api_key", "llm_api_key", "token", "evaluation_api_token",
        "authorization", "password", "secret", "credentials",
        "base_url", "llm_base_url", "allowed_models", "llm_allowed_models",
        "configuration_hash", "config_hash"
    }

    def nonsecret(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: nonsecret(item)
                for key, item in value.items()
                if key.lower() not in excluded
            }
        if isinstance(value, list):
            return [nonsecret(item) for item in value]
        return value

    canonical = json.dumps(
        nonsecret(configuration), sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
