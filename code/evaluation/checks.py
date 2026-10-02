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

import ast
import json
import re
from decimal import Decimal
from math import prod
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from evaluation.corpus import sha256_json
from evaluation.models import SCHEMA_VERSION

CHECK_VERSION = "1.1"

MATH_VARIABLE = "x"
_MATH_FUNCTIONS = ("sin", "cos", "tan", "exp", "log", "sqrt")
_MAX_EXPRESSION_LENGTH = 200

_LEVEL_NAME_PATTERN = re.compile(
    r"hilfestufe|stufe\s*\d|level\s*\d", re.IGNORECASE
)


def normalize_expression(text: str) -> str:
    """Whitespace-kollabierte, kleingeschriebene Vergleichsform."""
    return " ".join(str(text).split()).lower()


def _user_message(prompt_messages: Optional[List[dict]]) -> Optional[str]:
    if not isinstance(prompt_messages, list) or not prompt_messages or any(
        not isinstance(message, dict)
        or message.get("role") not in ("system", "user", "assistant")
        or not isinstance(message.get("content"), str)
        for message in prompt_messages
    ):
        return None
    content = "\n".join(
        message["content"]
        for message in prompt_messages
        if message.get("role") == "user"
    )
    return content if content.strip() else None


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
    from evaluation.runner import CODE_DIR, load_manifest, load_plan, verify_manifest

    manifest = load_manifest(run_dir)
    verify_manifest(run_dir, manifest)
    jobs = {job["job_id"]: job for job in load_plan(run_dir)}
    cases = {
        case.case_id: case
        for case in _load_cases(CODE_DIR / manifest["paths"]["corpus"])
    }
    profiles = {
        profile.profile_id: profile
        for profile in _load_profiles(
            CODE_DIR / manifest["paths"]["profiles"]
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
    prompt_available = user_message is not None
    user_message = user_message or ""
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
        ("pass" if not missing else "fail") if prompt_available else "inconclusive",
        {
            "prompt_available": prompt_available,
            "missing": missing if prompt_available else None,
            "checked_parts": [name for name, _ in required_parts],
        },
        ("" if not missing else "Erforderliche Kontexte fehlen im Prompt.")
        if prompt_available else "Keine echten prompt_messages verfuegbar.",
        attempt_id, job_id,
    ))

    # --- 4. Gesperrte Lösungsabschnitte im Prompt ---------------------
    leaked_prompt_parts: List[str] = []
    steps_locked = not profile.include_solution_steps or (
        not steps_allowed_by_level
    )
    # Student input is not a newly disclosed reference solution section.
    guard_message = normalize_expression(re.sub(
        r"<student_answer>.*?</student_answer>", "", user_message,
        flags=re.DOTALL,
    ))
    if steps_locked and reference.solution_steps and any(
        normalize_expression(step) in guard_message
        for step in reference.solution_steps
    ):
        leaked_prompt_parts.append("solution_steps")
    final_locked = not (
        profile.include_final_answer and level_policy.get("include_final_answer")
    )
    if final_locked and reference.final_answer:
        if any(
            normalize_expression(form) in guard_message
            for form in [reference.final_answer] + list(
                reference.equivalent_forms
            )
        ):
            leaked_prompt_parts.append("final_answer")
    records.append(_check(
        "prompt_solution_guard",
        ("fail" if leaked_prompt_parts else "pass")
        if prompt_available else "inconclusive",
        {
            "prompt_available": prompt_available,
            "leaked": leaked_prompt_parts if prompt_available else None,
            "steps_locked": steps_locked,
            "final_locked": final_locked,
        },
        ("" if not leaked_prompt_parts else "Gesperrte Loesungsabschnitte im Prompt.")
        if prompt_available else "Keine echten prompt_messages verfuegbar.",
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
                "final_answer_disclosure", "inconclusive",
                {
                    "present": None,
                    "sympy_available": sympy_available(),
                    "note": (
                        "Kein positiver literal/aequivalenter/symbolischer "
                        "Treffer; Abwesenheit ist nicht nachgewiesen."
                    ),
                },
                "Kein Endloesungstreffer; unvollstaendige Detektion.",
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
    """Prefer explicit math spans and standalone formulas, not prose fragments."""
    if limit <= 0 or len(hint) > 20000:
        return []
    matches = re.findall(
        r"```[^\n`]*\n(.*?)```|(?<!`)`([^`\n]+)`(?!`)"
        r"|\$\$(.*?)\$\$|(?<!\$)\$([^$\n]+)\$(?!\$)"
        r"|\\\[(.*?)\\\]|\\\((.*?)\\\)",
        hint, flags=re.DOTALL,
    )
    raw_spans = [span for match in matches for span in match if span]
    raw_spans += [line for span in raw_spans for line in span.splitlines()]
    raw_spans += hint.splitlines()
    allowed_names = set(_MATH_FUNCTIONS) | {MATH_VARIABLE, "e", "E", "pi"}
    candidates: List[str] = []
    for span in raw_spans:
        if len(span) > _MAX_EXPRESSION_LENGTH:
            continue
        cleaned = " ".join(span.split())
        if cleaned.count("=") == 1:
            label, expression = cleaned.split("=", 1)
            if re.fullmatch(r"[A-Za-z]'{0,2}(?:\([A-Za-z]\))?", label.strip()):
                cleaned = expression.strip()
        if not re.fullmatch(r"[A-Za-z0-9_+\-*/^().\s]+", cleaned):
            continue
        names = set(re.findall(r"\b[A-Za-z_][A-Za-z_0-9]*\b", cleaned))
        if not names <= allowed_names:
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
    """Compare bounded AST expressions; None means uncheckable, not absence."""
    try:
        import sympy
    except Exception as error:
        return None, "sympy nicht verfügbar: " + str(error)[:120]

    functions = {name: getattr(sympy, name) for name in _MATH_FUNCTIONS}
    constants = {"e": sympy.E, "E": sympy.E, "pi": sympy.pi}

    def parse_expression(text: str):
        if not isinstance(text, str) or not 0 < len(text) <= _MAX_EXPRESSION_LENGTH:
            raise ValueError("Ausdruck leer oder zu lang")
        source = text.strip().replace("^", "**")
        if not re.fullmatch(r"[A-Za-z0-9_+\-*/(). \t]+", source):
            raise ValueError("Unzulaessige Zeichen")
        tree = ast.parse(source, mode="eval")
        nodes = list(ast.walk(tree))
        function_count = sum(
            isinstance(node, ast.Call) or (
                isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow)
                and isinstance(node.left, ast.Name) and node.left.id in {"e", "E"}
            ) for node in nodes
        )
        if len(nodes) > 80 or function_count > 6:
            raise ValueError("Zu viele AST-Knoten oder Funktionsaufrufe")
        power_budget = 1

        def function_argument(argument):
            if (argument.has(sympy.Function) and not argument.free_symbols) or any(
                abs(number) > 64 for number in argument.atoms(sympy.Rational)
            ):
                raise ValueError("Funktionsargument ausserhalb der Parsergrenzen")
            return argument

        def build(node: ast.AST, depth: int = 0, function_depth: int = 0):
            nonlocal power_budget
            if depth > 12:
                raise ValueError("Ausdruck zu tief verschachtelt")
            if isinstance(node, ast.Constant) and type(node.value) in (int, float):
                literal = ast.get_source_segment(source, node) or ""
                if not re.fullmatch(
                    r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?",
                    literal,
                ) or len(literal) > 24:
                    raise ValueError("Unzulaessige Zahl")
                number = Decimal(literal)
                if (len(number.as_tuple().digits) > 12
                        or abs(number.as_tuple().exponent) > 12
                        or abs(number) > 1000000):
                    raise ValueError("Zahl ausserhalb der Parsergrenzen")
                return sympy.Rational(*number.as_integer_ratio())
            if isinstance(node, ast.Name):
                if node.id == variable:
                    return sympy.Symbol(variable)
                if node.id in constants:
                    return constants[node.id]
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                operand = build(node.operand, depth + 1, function_depth)
                if isinstance(node.op, ast.UAdd):
                    return operand
                return -operand if operand.is_Rational else sympy.Mul(
                    -1, operand, evaluate=False
                )
            if isinstance(node, ast.BinOp) and isinstance(
                node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
            ):
                exponential = (isinstance(node.op, ast.Pow)
                               and isinstance(node.left, ast.Name)
                               and node.left.id in {"e", "E"})
                left = build(node.left, depth + 1, function_depth)
                right = build(node.right, depth + 1, function_depth + int(exponential))
                numeric = bool(left.is_Rational and right.is_Rational)
                if isinstance(node.op, ast.Add):
                    result = sympy.Add(left, right, evaluate=numeric)
                elif isinstance(node.op, ast.Sub):
                    result = sympy.Add(
                        left, sympy.Mul(-1, right, evaluate=numeric), evaluate=numeric
                    )
                elif isinstance(node.op, ast.Mult):
                    result = sympy.Mul(left, right, evaluate=numeric)
                elif isinstance(node.op, ast.Div):
                    if right.is_zero is True:
                        raise ValueError("Division durch Null")
                    result = sympy.Mul(
                        left, sympy.Pow(right, -1, evaluate=numeric), evaluate=numeric
                    )
                else:
                    if exponential:
                        if function_depth >= 2:
                            raise ValueError("Zu viele verschachtelte Funktionen")
                        return sympy.exp(function_argument(right), evaluate=False)
                    if not right.is_Rational:
                        raise ValueError("Nur begrenzte numerische Potenzen erlaubt")
                    # Bound powers before SymPy can expand or evaluate them.
                    power_budget *= max(1, abs(right))
                    max_power = 16 if left.is_Atom else 4
                    if abs(right) > max_power or right.q > 8 or power_budget > 64:
                        raise ValueError("Potenz ausserhalb der Parsergrenzen")
                    result = sympy.Pow(left, right, evaluate=numeric)
                if result.is_Rational and (
                    abs(result) > 1000000 or max(
                        int(result.p).bit_length(), int(result.q).bit_length()
                    ) > 48
                ):
                    raise ValueError("Zahl ausserhalb der Parsergrenzen")
                return result
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in functions and len(node.args) == 1
                    and not node.keywords):
                if function_depth >= 2:
                    raise ValueError("Zu viele verschachtelte Funktionen")
                argument = build(node.args[0], depth + 1, function_depth + 1)
                return functions[node.func.id](function_argument(argument), evaluate=False)
            raise ValueError("Nicht unterstuetzte Syntax oder unbekannter Name")

        # Estimate expansion before the comparison, not after a costly simplify.
        def expansion_cost(expression) -> int:
            costs = [expansion_cost(argument) for argument in expression.args]
            if expression.is_Add:
                cost = sum(costs)
            elif expression.is_Mul:
                cost = prod(costs)
            elif expression.is_Pow:
                cost = costs[0] ** max(1, int(sympy.ceiling(abs(expression.exp))))
            else:
                cost = max(costs, default=1)
            if cost > 128:
                raise ValueError("Symbolische Expansion ausserhalb der Parsergrenzen")
            return cost

        expression = build(tree.body)
        expansion_cost(expression)
        return expression

    try:
        if (not isinstance(variable, str)
                or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,15}", variable)
                or variable in functions or variable in constants):
            raise ValueError("Unzulaessiger Variablenname")
        candidate_expr = parse_expression(candidate)
        reference_expr = parse_expression(reference)
    except Exception as error:
        return None, "Parse nicht moeglich: " + str(error)[:160]
    try:
        difference = sympy.simplify(candidate_expr - reference_expr, doit=False)
        if difference.has(sympy.nan, sympy.zoo, sympy.oo, -sympy.oo):
            return None, "Vergleich enthaelt einen undefinierten Wert"
    except Exception as error:
        return None, "Vergleich nicht abgeschlossen: " + str(error)[:160]
    if difference == 0:
        return True, "symbolisch gleich"
    return False, "symbolisch nicht gleich"
