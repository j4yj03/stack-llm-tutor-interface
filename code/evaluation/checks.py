"""Automatische fachliche Prüfungen einer Tutor-Antwort.

Drei Ebenen bleiben getrennt:
- technische Konsistenz (Instanz, Optionen, Prompt-Zusammensetzung)
- Policy-Konformität (Wortzahl, Stufennennung)
- Offenlegungsindikatoren (literal/äquivalente/symbolische Endlösung)

Wichtig: Ein fehlender literaler Treffer ist kein Beweis für Abwesenheit
von Lösungsverrat; die symbolische Prüfung ist bei Parse- oder
Extraktionsproblemen ausdrücklich "inconclusive" und zählt nicht als
"nicht enthalten".
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from evaluation.corpus import sha256_json
from evaluation.models import SCHEMA_VERSION

CHECK_VERSION = "1.0"

MATH_VARIABLE = "x"

_LEVEL_NAME_PATTERN = re.compile(
    r"hilfestufe|stufe\s*\d|level\s*\d", re.IGNORECASE
)


def normalize_expression(text: str) -> str:
    """Whitespace-kollabierte, kleingeschriebene Vergleichsform."""
    return " ".join(str(text).split()).lower()


def _user_message(prompt_messages: Optional[List[dict]]) -> str:
    if not prompt_messages:
        return ""
    return "\n".join(
        message.get("content", "")
        for message in prompt_messages
        if message.get("role") == "user"
    )


def _check(
    check_id: str,
    status: str,
    evidence: dict,
    reason: str = "",
    attempt_id: str = "",
    job_id: str = "",
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "check_version": CHECK_VERSION,
        "check_id": check_id,
        "status": status,  # pass | fail | inconclusive | not_applicable
        "attempt_id": attempt_id,
        "job_id": job_id,
        "evidence": evidence,
        "reason": reason,
    }


def load_policy(policy_path: Path) -> Dict[str, dict]:
    return json.loads(policy_path.read_text(encoding="utf-8"))


def run_checks_for_run(run_dir: Path) -> dict:
    """Prüft alle gespeicherten Generierungen eines Runs; schreibt checks.jsonl.

    Nutzt bewusst dieselben Bausteine wie die CLI (Manifest, Plan, Korpus,
    Profile, eingebettete Policy), damit Notebook und CLI identisch werten.
    """
    import json as _json

    from evaluation.corpus import load_cases as _load_cases
    from evaluation.corpus import load_profiles as _load_profiles
    from evaluation.runner import load_manifest, load_plan, verify_manifest

    manifest = load_manifest(run_dir)
    verify_manifest(run_dir, manifest)
    jobs = {job["job_id"]: job for job in load_plan(run_dir)}
    cases = {
        case.case_id: case
        for case in _load_cases(Path(manifest["paths"]["corpus"]))
    }
    profiles = {
        profile.profile_id: profile
        for profile in _load_profiles(
            Path(manifest["paths"]["profiles"])
        ).profiles
    }
    policy = manifest.get("hint_policy") or {}

    generations_path = run_dir / "generations.jsonl"
    if not generations_path.exists():
        raise FileNotFoundError(
            "Keine Generierungen vorhanden: " + str(generations_path)
        )
    records: List[dict] = []
    with open(generations_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            generation = _json.loads(line)
            case = cases.get(generation.get("case_id"))
            profile = profiles.get(generation.get("profile_id"))
            if case is None or profile is None:
                records.append(_check(
                    "corpus_reference",
                    "fail",
                    {"case_id": generation.get("case_id"),
                     "profile_id": generation.get("profile_id")},
                    "Fall/Profil zum Generierungsdatensatz nicht gefunden.",
                    generation.get("attempt_id", ""),
                    generation.get("job_id", ""),
                ))
                continue
            records.extend(
                run_checks(generation, case, profile, policy)
            )
    checks_path = run_dir / "checks.jsonl"
    with open(checks_path, "w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(_json.dumps(record, ensure_ascii=False) + "\n")
    failed = sum(1 for record in records if record.get("status") == "fail")
    return {
        "records": len(records),
        "failed": failed,
        "path": str(checks_path),
    }


def sympy_available() -> bool:
    try:
        import sympy  # noqa: F401
    except Exception:
        return False
    return True


def run_checks(
    generation: dict,
    case,
    profile,
    policy: Optional[Dict[str, dict]] = None,
) -> List[dict]:
    """Prüft einen Generierungsdatensatz gegen Fall, Profil und Policy."""
    records: List[dict] = []
    attempt_id = generation.get("attempt_id", "")
    job_id = generation.get("job_id", "")
    outcome = generation.get("outcome")
    level = generation.get("hint_level")
    payload = generation.get("request_payload") or {}

    if outcome != "success":
        records.append(_check(
            "response_available",
            "not_applicable",
            {"outcome": outcome},
            "Keine erfolgreiche Antwort; fachliche Checks nicht anwendbar.",
            attempt_id, job_id,
        ))
        return records

    returned = generation.get("returned") or {}
    hint = returned.get("hint") or ""
    user_message = _user_message(returned.get("prompt_messages"))
    level_policy = (policy or {}).get(str(level)) or {}

    # --- 1. Identität ---------------------------------------------
    identities_ok = (
        returned.get("question_id")
        == payload.get("stack", {}).get("question_id")
        and returned.get("hint_level") == level
        and (
            payload.get("model") is None
            or returned.get("model") == payload.get("model")
        )
    )
    records.append(_check(
        "response_identity",
        "pass" if identities_ok else "fail",
        {
            "returned_question_id": returned.get("question_id"),
            "returned_hint_level": returned.get("hint_level"),
            "returned_model": returned.get("model"),
            "requested_model": payload.get("model"),
        },
        "" if identities_ok else "Zurückgegebene Identität weicht ab.",
        attempt_id, job_id,
    ))

    # --- 2. Kontextoptionen -----------------------------------------
    expected_options = payload.get("context_options", {})
    returned_options = returned.get("context_options") or {}
    options_ok = (
        set(returned_options) == set(expected_options)
        and all(
            returned_options.get(name) == expected
            for name, expected in expected_options.items()
        )
    )
    records.append(_check(
        "context_options_match",
        "pass" if options_ok else "fail",
        {
            "expected_sha256": sha256_json(expected_options),
            "returned_options": returned_options,
        },
        "" if options_ok else "Zurückgegebene Kontextoptionen weichen ab.",
        attempt_id, job_id,
    ))

    # --- 3. Erforderliche Kontexte im Prompt -------------------------
    required_parts: List[Tuple[str, str]] = []
    if profile.include_question_text:
        required_parts.append(
            ("question_text", case.tutor_context.question_text)
        )
    if profile.include_student_answer:
        required_parts.append(
            ("student_answer", case.tutor_context.student_answer)
        )
    if profile.include_diagnosis_code and case.tutor_context.diagnosis_code:
        required_parts.append(
            ("diagnosis_code", case.tutor_context.diagnosis_code)
        )
    if profile.include_prt_feedback and case.tutor_context.prt_feedback:
        required_parts.append(
            ("prt_feedback", case.tutor_context.prt_feedback)
        )
    if profile.include_learning_goals and case.tutor_context.learning_goals:
        required_parts.append(
            ("learning_goals", case.tutor_context.learning_goals[0])
        )
    if profile.include_math_rules and case.tutor_context.math_rules:
        required_parts.append(
            ("math_rules", case.tutor_context.math_rules[0])
        )
    reference = case.evaluation_only.reference

    # Lösungsschritte nur erwarten, wenn die serverseitige Doppelprüfung
    # (Kontextoption UND Stufenfreigabe) sie zulässt.
    steps_allowed_by_level = bool(level_policy.get("include_solution_steps"))
    if profile.include_solution_steps and steps_allowed_by_level and (
        reference.solution_steps
    ):
        required_parts.append(("solution_steps", reference.solution_steps[0]))

    missing = [
        name for name, part in required_parts
        if normalize_expression(part) not in normalize_expression(user_message)
    ]
    records.append(_check(
        "prompt_required_content",
        "pass" if not missing else "fail",
        {
            "missing": missing,
            "checked_parts": [name for name, _ in required_parts],
        },
        "" if not missing else "Erforderliche Kontexte fehlen im Prompt.",
        attempt_id, job_id,
    ))

    # --- 4. Gesperrte Lösungsabschnitte im Prompt ---------------------
    leaked_prompt_parts: List[str] = []
    steps_locked = not profile.include_solution_steps or (
        not steps_allowed_by_level
    )
    if steps_locked and reference.solution_steps and any(
        normalize_expression(step) in normalize_expression(user_message)
        for step in reference.solution_steps
    ):
        leaked_prompt_parts.append("solution_steps")
    final_locked = not profile.include_final_answer
    if final_locked and reference.final_answer:
        if any(
            normalize_expression(form) in normalize_expression(user_message)
            for form in [reference.final_answer] + list(
                reference.equivalent_forms
            )
        ):
            leaked_prompt_parts.append("final_answer")
    records.append(_check(
        "prompt_solution_guard",
        "fail" if leaked_prompt_parts else "pass",
        {
            "leaked": leaked_prompt_parts,
            "steps_locked": steps_locked,
            "final_locked": final_locked,
        },
        "" if not leaked_prompt_parts else (
            "Gesperrte Lösungsabschnitte im Prompt."
        ),
        attempt_id, job_id,
    ))

    # --- 5. Wortzahl gegen aktive Policy ------------------------------
    word_count = len(re.findall(r"\S+", hint))
    if not level_policy:
        records.append(_check(
            "word_count", "inconclusive", {"word_count": word_count},
            "Keine Policy für Stufe verfügbar.", attempt_id, job_id,
        ))
    else:
        max_words = level_policy.get("max_words")
        within = 0 < word_count <= max_words
        records.append(_check(
            "word_count",
            "pass" if within else "fail",
            {"word_count": word_count, "max_words": max_words},
            "" if within else "Wortzahl verletzt Policy oder Antwort leer.",
            attempt_id, job_id,
        ))

    # --- 6. Interne Stufe im Hinweis genannt ---------------------------
    mentioned = bool(_LEVEL_NAME_PATTERN.search(hint))
    records.append(_check(
        "hint_level_mention",
        "fail" if mentioned else "pass",
        {"pattern": "hilfestufe|stufe N|level N"},
        "" if not mentioned else "Hinweis nennt die interne Hilfestufe.",
        attempt_id, job_id,
    ))

    # --- 7. Endlösungs-Offenlegung -------------------------------------
    reference_answer = reference.final_answer
    if not reference_answer:
        records.append(_check(
            "final_answer_disclosure", "not_applicable",
            {"reference_available": False},
            "Keine verifizierte Referenzendlösung verfügbar.",
            attempt_id, job_id,
        ))
    else:
        matched_form, match_kind = _match_final_answer(
            hint, reference_answer, reference.equivalent_forms
        )
        # Output-Policy kommt von der Stufe (siehe Doppelprüfung): Auf
        # Stufe 4 ist die Endlösung erlaubt, auch wenn der Prompt sie
        # nicht enthält ("Referenzlösung gesperrt" != "Ausgabe verboten").
        if level_policy:
            allowed = bool(level_policy.get("include_final_answer"))
        else:
            allowed = level == 4
        if matched_form is None:
            records.append(_check(
                "final_answer_disclosure", "pass",
                {
                    "present": False,
                    "sympy_available": sympy_available(),
                    "note": (
                        "Kein literal/äquivalenter Treffer; symbolische "
                        "Prüfung bleibt bei Parseproblemen unbestimmt."
                    ),
                },
                "" if sympy_available() else (
                    "Ohne Treffer; sympy fehlt, symbolische Tiefe begrenzt."
                ),
                attempt_id, job_id,
            ))
        else:
            records.append(_check(
                "final_answer_disclosure",
                "pass" if allowed else "fail",
                {
                    "present": True,
                    "matched_form": matched_form,
                    "match_kind": match_kind,
                    "allowed_at_level": allowed,
                },
                (
                    "Endlösung vorhanden; auf dieser Stufe erlaubt."
                    if allowed
                    else "Unzulässiger Lösungsverrat gegen Stufenregel."
                ),
                attempt_id, job_id,
            ))
    return records


def _match_final_answer(
    hint: str,
    reference_answer: str,
    equivalent_forms: List[str],
) -> Tuple[Optional[str], str]:
    """Sucht die Endlösung: literal -> äquivalente Form -> symbolisch."""
    normalized_hint = normalize_expression(hint)
    candidates = [reference_answer] + list(equivalent_forms)
    for form in candidates:
        if normalize_expression(form) in normalized_hint:
            return form, "literal_or_equivalent"
    if not sympy_available():
        return None, ""
    for candidate in _extract_candidate_expressions(hint):
        equivalent, _reason = symbolic_equivalence(
            candidate, reference_answer, MATH_VARIABLE
        )
        if equivalent:
            return candidate, "symbolic"
    return None, ""


def _extract_candidate_expressions(hint: str, limit: int = 8) -> List[str]:
    """Konservative Heuristik für Formelkandidaten in Prosa.

    Kein Parseranspruch: nur mathematisch anmutende Züge mit Operator
    und Operand werden geprüft; keine Umlaute (deutsche Wörter), Länge
    und Tokenzahl begrenzt. Alles Unklare bleibt unbestimmt.
    """
    raw_spans = re.findall(r"[A-Za-z0-9_+\-*/^().,\s]{3,200}", hint)
    candidates: List[str] = []
    for span in raw_spans:
        cleaned = span.strip()
        if len(cleaned) < 3:
            continue
        has_operator = any(symbol in cleaned for symbol in "+-*/^")
        has_operand = any(character.isalnum() for character in cleaned)
        if not (has_operator and has_operand):
            continue
        if re.search(r"[äöüßÄÖÜ]", cleaned):
            continue
        if len(cleaned.split()) > 24:
            continue
        if cleaned not in candidates:
            candidates.append(cleaned)
        if len(candidates) >= limit:
            break
    return candidates


def symbolic_equivalence(
    candidate: str,
    reference: str,
    variable: str = MATH_VARIABLE,
) -> Tuple[Optional[bool], str]:
    """Prüft Äquivalenz zweier Ausdrücke begrenzt und ohne freies eval.

    Rückgabe: (True | False | None, Grund). None heißt ausdrücklich:
    nicht bewertbar (Import/Parse/Aufwand) und wird als "inconclusive"
    berichtet, niemals als Bestehen.
    """
    try:
        import sympy
        from sympy import Symbol, simplify
        from sympy.parsing.sympy_parser import (
            convert_xor,
            parse_expr,
            standard_transformations,
        )
    except Exception as error:
        return None, "sympy nicht verfügbar: " + str(error)[:120]

    if len(candidate) > 200 or len(reference) > 200:
        return None, "Ausdruck zu lang für begrenzte Prüfung"
    forbidden = ("__", ";", ":", "[", "]", "{", "}", "!", "=", "|", "\n")
    if any(token in candidate for token in forbidden):
        return None, "Kandidat enthält unzulässige Zeichen"
    if any(token in reference for token in forbidden):
        return None, "Referenz enthält unzulässige Zeichen"

    transformations = standard_transformations + (convert_xor,)
    namespace = {name: getattr(sympy, name) for name in dir(sympy)}
    symbol_map = {variable: Symbol(variable)}
    try:
        candidate_expr = parse_expr(
            candidate,
            local_dict=symbol_map,
            global_dict=namespace,
            transformations=transformations,
        )
        reference_expr = parse_expr(
            reference,
            local_dict=symbol_map,
            global_dict=namespace,
            transformations=transformations,
        )
    except Exception as error:
        return None, "Parse nicht möglich: " + str(error)[:160]
    if candidate_expr is None or reference_expr is None:
        return None, "Leerer Ausdruck"
    try:
        difference = simplify(candidate_expr - reference_expr)
    except Exception as error:
        return None, "Vergleich nicht abgeschlossen: " + str(error)[:160]
    if difference == 0:
        return True, "symbolisch gleich"
    return False, "symbolisch nicht gleich"
