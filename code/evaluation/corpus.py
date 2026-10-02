"""Fallbestand (Korpus) und Kontextprofile der Evaluationssuite.

Verantwortung:
- Laden und striktes Validieren von cases-JSONL und Profilen-JSON
- Eignungsprüfung pro (Fall, Profil) — fehlende Belege schließen
  Forschungsbedingungen aus, statt still schlechtere Kontexte zu senden
- Aufbau des Tutor-Request-Payloads aus Fall + Profil + Hilfestufe

Der Korpus trennt strikt:
- tutor_context: pool an Daten, die (profilabhängig) an den Tutor gehen
- evaluation_only: Referenzen/Provenienz; Schritte/Endloesung nur fuer
  explizite Loesungsprofile, keine Bewertungsmetadaten im Tutor-Request
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from evaluation.models import (
    Case,
    ContextProfile,
    ContextProfileSet,
    Experiment,
    PROFILE_FLAG_NAMES,
    SCHEMA_VERSION,
)


class CorpusError(ValueError):
    """Gültigkeitsfehler in Korpus-, Profil- oder Experimentdaten."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(payload) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def configuration_sha256(configuration: dict) -> str:
    """Hash the public API configuration using its ASCII canonical encoding."""
    canonical = json.dumps(
        configuration, ensure_ascii=True, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_public_configuration(value: dict) -> dict:
    """Validate a config response/snapshot without importing server modules."""
    if not isinstance(value, dict) or not isinstance(value.get("configuration"), dict):
        raise CorpusError("A public configuration snapshot is required")

    def reject_credentials(data) -> None:
        if isinstance(data, dict):
            for key, item in data.items():
                name = key.lower()
                if (name in {"token", "credentials"} or any(
                    part in name for part in (
                        "api_key", "api_token", "evaluation_token", "authorization",
                        "password", "secret",
                    )
                )) and type(item) is not bool:
                    raise CorpusError("Credentials cannot enter public configuration snapshots")
                reject_credentials(item)
        elif isinstance(data, list):
            for item in data:
                reject_credentials(item)

    reject_credentials(value["configuration"])
    digest = configuration_sha256(value["configuration"])
    if value.get("config_sha256") != digest:
        raise CorpusError("The public configuration hash does not match its snapshot")
    token = os.getenv("TUTOR_EVALUATION_TOKEN", "")
    if token and token in json.dumps(value["configuration"], ensure_ascii=False):
        raise CorpusError("Evaluation credentials cannot enter a public configuration snapshot")
    return {"configuration": value["configuration"], "config_sha256": digest}


def load_cases(path: Path) -> List[Case]:
    """Lädt ein cases-JSONL; doppelte case_ids werden abgewiesen."""
    cases: List[Case] = []
    seen = set()
    if not path.exists():
        raise CorpusError("Korpusdatei nicht gefunden: " + str(path))
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as error:
                raise CorpusError(
                    "Zeile " + str(line_number) + " ist kein gültiges JSON: "
                    + str(error)
                ) from error
            try:
                case = Case.model_validate(raw)
            except Exception as error:
                raise CorpusError(
                    "Zeile " + str(line_number) + " (case_id="
                    + str(raw.get("case_id"))
                    + ") verletzt das Case-Schema: " + str(error)
                ) from error
            if case.case_id in seen:
                raise CorpusError(
                    "Doppelte case_id in Zeile " + str(line_number) + ": "
                    + case.case_id
                )
            seen.add(case.case_id)
            cases.append(case)
    if not cases:
        raise CorpusError("Korpus enthält keinen gültigen Fall: " + str(path))
    return cases


def load_profiles(path: Path) -> ContextProfileSet:
    if not path.exists():
        raise CorpusError("Profildatei nicht gefunden: " + str(path))
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    profile_set = ContextProfileSet.model_validate(raw)
    ids = [profile.profile_id for profile in profile_set.profiles]
    if len(ids) != len(set(ids)):
        raise CorpusError("Doppelte profile_id in " + str(path))
    return profile_set


def load_experiment(path: Path) -> Experiment:
    if not path.exists():
        raise CorpusError("Experimentdatei nicht gefunden: " + str(path))
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return Experiment.model_validate(raw)


def validate_experiment(
    experiment: Experiment,
    cases: List[Case],
    profile_set: ContextProfileSet,
) -> List[str]:
    """Querverweise und grobe Machbarkeit prüfen; Liste von Fehlern."""
    errors: List[str] = []
    profile_ids = set(profile_set.by_id())
    case_ids = {case.case_id for case in cases}
    for profile_id in experiment.profiles:
        if profile_id not in profile_ids:
            errors.append("Unbekanntes Profil im Experiment: " + profile_id)
    if not experiment.profiles:
        errors.append("Experiment enthält keine Profile")
    if not experiment.interaction_script and any(
        profile_set.by_id()[profile_id].include_chat_history
        for profile_id in experiment.profiles if profile_id in profile_ids
    ):
        errors.append("Chat history requires an explicit interaction_script")
    for control in experiment.control_jobs:
        if control.case_id not in case_ids:
            errors.append(
                "control_job mit unbekannter case_id: " + control.case_id
            )
        if control.profile_id not in profile_ids:
            errors.append(
                "control_job mit unbekanntem Profil: " + control.profile_id
            )
    # Kontrollzellen dürfen Hauptprofile nutzen, dürfen aber keine
    # Zelle des Hauptrasters verdoppeln (sonst identische Doppeljobs).
    main_cells = {
        (case.case_id, profile_id, level, repetition)
        for case in sorted(cases, key=lambda item: item.case_id)
        for profile_id in experiment.profiles
        for level in experiment.hint_levels
        for repetition in range(1, experiment.repetitions + 1)
    }
    control_cells = set()
    for control in experiment.control_jobs:
        for repetition in range(1, control.repetitions + 1):
            cell = (control.case_id, control.profile_id, control.hint_level, repetition)
            if cell in main_cells or cell in control_cells:
                errors.append(
                    "control_job verdoppelt eine Raster-Zelle: "
                    + control.case_id + "/" + control.profile_id
                    + "/L" + str(control.hint_level)
                )
            control_cells.add(cell)
        if (not experiment.interaction_script and control.profile_id in profile_ids
                and profile_set.by_id()[control.profile_id].include_chat_history):
            errors.append("Control chat history requires an explicit interaction_script")
    return errors


def profile_requires(
    profile: ContextProfile, case: Case
) -> Optional[str]:
    """Liefert Fehlgrund, wenn dem Profil notwendige Falldaten fehlen."""
    if profile.include_diagnosis_code and not case.tutor_context.diagnosis_code:
        return "diagnosis_code fehlt im Fall"
    if profile.include_prt_feedback and not case.tutor_context.prt_feedback:
        return "prt_feedback fehlt im Fall"
    if profile.include_score and case.tutor_context.score is None:
        return "score fehlt im Fall"
    if profile.include_learning_goals and (
        not case.tutor_context.learning_goals
    ):
        return "learning_goals fehlen im Fall"
    if profile.include_math_rules and not case.tutor_context.math_rules:
        return "math_rules fehlen im Fall"
    if profile.include_solution_steps and not (
        case.evaluation_only.reference.solution_steps
    ):
        return "solution_steps fehlen in der Referenz"
    if profile.include_solution_steps and not case.evaluation_only.reference.final_answer:
        return "final_answer als Guard fuer solution_steps fehlt in der Referenz"
    if profile.include_final_answer and not (
        case.evaluation_only.reference.final_answer
    ):
        return "final_answer fehlt in der Referenz"
    return None


def case_profile_eligible(
    case: Case,
    profile: ContextProfile,
    allow_unverified_cases: bool,
    allow_task_derived_cases: Optional[bool] = None,
) -> Optional[str]:
    """Data eligibility; pass the experiment's explicit task-derived live gate."""
    provenance = case.evaluation_only.provenance
    if ("task_derived" in case.tags or (
        provenance.instantiated_task_ref or ""
    ).endswith("#evaluation_examples")) and allow_task_derived_cases is False:
        return "Task-derived synthetic cases require allow_task_derived_cases=true"
    if not case.is_research_eligible(allow_unverified_cases):
        return (
            "Mathematik nicht verifiziert (mathematics_status="
            + case.evaluation_only.verification.mathematics_status
            + ")"
        )
    return profile_requires(profile, case)


def build_request_payload(
    case: Case,
    profile: ContextProfile,
    hint_level: Optional[int],
    model: Optional[str],
    use_server_context: bool = False,
) -> dict:
    """Baut POST /api/tutor/start Payload (frischer Chat, ohne user_message).

    - Ausgeschlossene optionale Felder werden ausdrücklich als null/leer
      gesendet, damit die Bedingung nicht von Defaults abhängt.
    - solution_steps: Der Prompt-Builder des Servers braucht bei
      übertragenen Schritten die passende final_answer als Vergleichswert
      für seinen internen Schutz (Doppelprüfung), selbst wenn
      include_final_answer=false ist und der Schritt-Wert gesperrt bleibt.
    """
    tutor = case.tutor_context
    reference = case.evaluation_only.reference
    diagnosis_source = tutor.diagnosis_source
    if diagnosis_source == "synthetic_fixture":
        diagnosis_source = "synthetic"
    elif diagnosis_source is None:
        diagnosis_source = (
            "synthetic" if case.evaluation_only.provenance.response_origin == "synthetic_fixture"
            else "unknown"
        )

    include_steps = profile.include_solution_steps and bool(
        reference.solution_steps
    )
    include_final = profile.include_final_answer and bool(
        reference.final_answer
    )

    stack = {
        "question_id": tutor.question_id,
        "question_text": tutor.question_text,
        "student_answer": tutor.student_answer,
        "diagnosis_code": (
            tutor.diagnosis_code
            if profile.include_diagnosis_code
            else None
        ),
        "diagnosis_source": (
            diagnosis_source
            if ((profile.include_diagnosis_code and tutor.diagnosis_code)
                or (profile.include_prt_feedback and tutor.prt_feedback))
            else None
        ),
        "prt_feedback": (
            tutor.prt_feedback if profile.include_prt_feedback else None
        ),
        "score": tutor.score if profile.include_score else None,
        "seed": tutor.seed,
        "learning_goals": (
            list(tutor.learning_goals)
            if profile.include_learning_goals
            else []
        ),
        "math_rules": (
            list(tutor.math_rules) if profile.include_math_rules else []
        ),
        "solution_steps": (
            list(reference.solution_steps)
            if include_steps
            else []
        ),
        # Guard-Daten: nur bei übertragenen Schritten, damit der
        # serverseitige Literal-Schutz den Endantwort-Schritt erkennen kann.
        "final_answer": (
            reference.final_answer
            if (include_steps or include_final)
            else None
        ),
    }

    payload: dict = {
        "stack": stack,
        "chat_id": None,
        "user_message": None,
        "hint_level": hint_level,
    }
    if not use_server_context:
        payload["context_options"] = profile.flags()
    if model:
        payload["model"] = model
    return payload


def check_payload_profile_consistency(payload: dict, profile: ContextProfile) -> List[str]:
    """Manipulationsprüfung: Payload muss das Profil exakt abbilden."""
    problems: List[str] = []
    options = payload.get("context_options", {})
    expected = profile.flags()
    for name in PROFILE_FLAG_NAMES:
        if options.get(name) != expected[name]:
            problems.append(
                "Kontextschalter " + name + " entspricht nicht dem Profil"
            )
    stack = payload.get("stack", {})
    if profile.include_diagnosis_code and not stack.get("diagnosis_code"):
        problems.append("Profil verlangt diagnosis_code, Payload ist leer")
    if not profile.include_diagnosis_code and stack.get("diagnosis_code"):
        problems.append("Profil schließt diagnosis_code aus, Payload enthält ihn")
    if profile.include_prt_feedback and not stack.get("prt_feedback"):
        problems.append("Profil verlangt prt_feedback, Payload ist leer")
    if not profile.include_prt_feedback and stack.get("prt_feedback"):
        problems.append("Profil schließt prt_feedback aus, Payload enthält ihn")
    return problems


def load_corpus_bundle(
    corpus_file: Path,
    profiles_file: Path,
    experiment: Experiment,
):
    """Lädt alles zusammen und wirft bei Querverletzungen."""
    cases = load_cases(corpus_file)
    profile_set = load_profiles(profiles_file)
    errors = validate_experiment(experiment, cases, profile_set)
    if errors:
        raise CorpusError(
            "Experimentwidrigkeiten:\n- " + "\n- ".join(errors)
        )
    return cases, profile_set
