"""Pure next-interaction decisions; time alone never implies misunderstanding."""

from typing import Dict, Optional

from app import config


def decide_hint_level(
    current_level: int,
    message: str,
    elapsed_seconds: Optional[float],
    confusion_signal: Optional[bool] = None,
    requested_level: Optional[int] = None,
    time_source: str = "observed_server_interval",
) -> Dict:
    translations = str.maketrans({"\u00df": "ss", "\u00e4": "ae", "\u00f6": "oe", "\u00fc": "ue"})
    normalized = message.lower().translate(translations)
    confused = confusion_signal if confusion_signal is not None else any(
        phrase.lower().translate(translations) in normalized for phrase in config.TUTOR_ADAPTIVE_CONFUSION_PHRASES
    )
    target = current_level
    reason = "disabled" if not config.TUTOR_ADAPTIVE_ENABLED else "no_corroborating_signal"
    if requested_level is not None:
        target, reason = requested_level, "explicit_request"
    elif config.TUTOR_ADAPTIVE_ENABLED and confused:
        reason = "time_unknown" if elapsed_seconds is None else "threshold_not_reached"
        if elapsed_seconds is not None and elapsed_seconds >= config.TUTOR_ADAPTIVE_AFTER_SECONDS:
            target = max(current_level, min(current_level + config.TUTOR_ADAPTIVE_STEP, config.TUTOR_ADAPTIVE_MAX_LEVEL))
            reason = "time_and_confusion" if target > current_level else "ceiling_reached"
    return {
        "previous_level": current_level, "candidate_level": target,
        "elapsed_seconds": elapsed_seconds, "time_source": time_source,
        "confusion_signal": confused,
        "signal_source": "scripted" if confusion_signal is not None else "self_report_phrase",
        "reason": reason, "applied": False,
    }
