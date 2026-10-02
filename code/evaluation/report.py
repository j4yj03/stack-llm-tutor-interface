"""Bewertungsexport/-import und offline Auswertungen.

- review-export: neutrale Bewertungsbögen (ohne Modell/Profil) + Mapping
- review-import: validierte CSV-Bewertungen -> ratings.jsonl
- report: Manifest/Generierungen/Checks/Ratings -> summary, Paarvergleiche,
  Markdown-Bericht (vollständig aus gespeicherten Artefakten reproduzierbar)

Mock-/Fixture-Auskünfte (execution_source != live_tutor_api) fließen
standardmäßig nicht in fachliche Qualitätskennzahlen ein.
"""

import csv
import hashlib
import json
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from evaluation import runner
from evaluation.checks import load_policy
from evaluation.corpus import load_cases, sha256_json
from evaluation.models import SCHEMA_VERSION

GENERATIONS_FILE = "generations.jsonl"
CHECKS_FILE = "checks.jsonl"
REVIEW_DIR = "reviews"
DERIVED_DIR = "derived"

LIKERT_FIELDS = [
    "passung_fehler",
    "verstaendlichkeit",
    "hilfreichkeit_naechster_schritt",
    "aktivierung",
    "sprachliche_praezision",
]
CHOICE_FIELDS = [
    "mat_falsch",
    "widerspruch_pruefergebnis",
    "erfundene_diagnose",
    "stufe_angemessen",
    "loesung_vollstaendig",
    "loesungsverrat_unzulaessig",
]
RFC_REVIEW_COLUMNS = (
    ["review_id", "rater_id", "hilfestufe", "hilfestufenziel", "aufgabenstellung",
     "studentische_antwort", "referenz_endloesung", "erwarteter_fehlerfall",
     "erwartete_validitaet", "erwartete_korrektheit", "tutorhinweis",
     "phase", "dialogschritt", "aktuelle_nachricht", "regelmodus",
     "referenzstatus_mathematik", "referenzstatus_diagnose", "diagnoseherkunft"]
    + LIKERT_FIELDS + CHOICE_FIELDS + ["begruendung"]
)
_CHOICE_VALUES = ("ja", "nein", "unklar", "nicht_anwendbar")


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _successful_results(generations: List[dict]) -> List[dict]:
    """Letzter erfolgreicher Versuch je Job in JSONL-Journalreihenfolge."""
    by_job: Dict[str, dict] = {}
    for record in generations:
        if record.get("outcome") == "success":
            by_job[(record.get("condition_id", "default"), record["job_id"])] = record
    return list(by_job.values())


def _has_ratings(values: dict) -> bool:
    return any(
        values.get(field) not in (None, "", "n_a")
        for field in LIKERT_FIELDS + CHOICE_FIELDS
    )


def _model_key(record: dict) -> str:
    return (
        record.get("requested_model")
        or (record.get("returned") or {}).get("model") or "server_default"
    )


def _effective_level(record: dict):
    return (record.get("returned") or {}).get("hint_level", record.get("hint_level"))


def _stage(record: dict) -> str:
    return (record.get("returned") or {}).get(
        "stage", "diagnostic" if _effective_level(record) == 0 else "hint",
    )


def _start_level_key(record: dict):
    if record.get("level_mode") == "server_start":
        return "server_start"
    return record.get("start_hint_level", record.get("hint_level"))


def _load_run_core(
    run_dir: Path,
) -> Tuple[dict, List[dict], List[dict], List[dict]]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            "Kein Manifest im Run-Verzeichnis: " + str(run_dir)
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    generations = []
    for record in _read_jsonl(run_dir / GENERATIONS_FILE):
        if record.get("execution_source") != "live_tutor_api":
            continue
        record.setdefault("condition_id", manifest.get("condition_id", "default"))
        record.setdefault("turn_index", 0)
        record.setdefault("level_mode", manifest.get("level_mode", "direct"))
        record.setdefault("interaction_script_sha256", manifest.get(
            "interaction_script_sha256", sha256_json(manifest.get("interaction_script", [])),
        ))
        generations.append(record)
    live_attempt_ids = {record["attempt_id"] for record in generations}
    result_ids = {
        record["attempt_id"] for record in _successful_results(generations)
    }
    checks = [
        check for check in _read_jsonl(run_dir / CHECKS_FILE)
        if check.get("attempt_id") in live_attempt_ids
    ]
    ratings: List[dict] = []
    seen = set()
    for rating in _read_jsonl(run_dir / REVIEW_DIR / "ratings.jsonl"):
        key = (rating.get("review_id"), rating.get("rater_id"))
        if (rating.get("attempt_id") not in result_ids
                or rating.get("rating_source", "human") != "human"
                or rating.get("execution_source") not in {None, "human", "human_review"}
                or not _has_ratings(rating.get("ratings") or {})
                or key in seen):
            continue
        ratings.append(rating)
        seen.add(key)
    return manifest, generations, checks, ratings


def _review_id(run_id: str, attempt_id: str) -> str:
    digest = hashlib.sha256(
        (run_id + "|" + attempt_id).encode("utf-8")
    ).hexdigest()
    return "R" + digest[:10]


def export_review_packet(run_dir: Path, limit: Optional[int] = None) -> dict:
    """Erzeugt neutralen Bewertungsbogen + Mapping (blind gegenüber
    Modell und Kontextprofil)."""
    manifest, generations, _checks, _ratings = _load_run_core(run_dir)
    paths = manifest.get("paths") or {}
    corpus_path = paths.get("corpus")
    # Alte Laufartefakte ohne Korpuspfad haben keine Bewertungsreferenzen.
    cases = {
        case.case_id: case
        for case in load_cases(runner.CODE_DIR / corpus_path)
    } if corpus_path else {}
    policy = manifest.get("hint_policy")
    if not policy:
        policy_path = paths.get("policy")
        policy = load_policy(
            runner.CODE_DIR / policy_path if policy_path else runner.POLICY_PATH
        )

    packet_rows: List[dict] = []
    mapping: Dict[str, dict] = {}
    for record in _successful_results(generations):
        case = cases.get(record.get("case_id"))
        if corpus_path and case is None:
            raise ValueError(
                "Fall fehlt im Laufkorpus: " + str(record.get("case_id"))
            )
        reference = case.evaluation_only.reference.model_dump() if case else {}
        returned = record.get("returned") or {}
        hint = returned.get("hint") or ""
        level = _effective_level(record)
        configuration = returned.get("configuration") or {}
        level_policy = returned.get("hint_policy") or (
            (configuration.get("hint_policy") or {}).get(str(level))
        ) or policy.get(str(level), {})
        policy_mode = returned.get("policy_mode", (configuration.get("tutor_rules") or {}).get("policy_mode", "tutor"))
        review_id = _review_id(manifest["run_id"], record["attempt_id"])
        payload = record.get("request_payload") or {}
        stack = payload.get("stack") or record.get("stack_context") or {}
        packet_rows.append({
            "review_id": review_id,
            "rater_id": "",
            "hilfestufe": level,
            "hilfestufenziel": level_policy.get("goal", "") if policy_mode == "tutor" else "",
            "aufgabenstellung": stack.get("question_text", ""),
            "studentische_antwort": stack.get("student_answer", ""),
            "referenz_endloesung": reference.get("final_answer") or "",
            "erwarteter_fehlerfall": reference.get("expected_diagnosis") or "",
            "erwartete_validitaet": reference.get("expected_input_validity") or "",
            "erwartete_korrektheit": reference.get("expected_correctness") or "",
            "tutorhinweis": hint,
            "phase": _stage(record),
            "dialogschritt": record.get("turn_index", 0),
            "aktuelle_nachricht": payload.get("message", ""),
            "regelmodus": policy_mode,
            "referenzstatus_mathematik": case.evaluation_only.verification.mathematics_status if case else "",
            "referenzstatus_diagnose": case.evaluation_only.verification.diagnosis_status if case else "",
            "diagnoseherkunft": (
                case.tutor_context.diagnosis_source or case.evaluation_only.provenance.response_origin
            ) if case else "",
            **{field: "" for field in LIKERT_FIELDS},
            **{field: "" for field in CHOICE_FIELDS},
            "begruendung": "",
        })
        mapping[review_id] = {
            "attempt_id": record["attempt_id"],
            "job_id": record["job_id"],
            "case_id": record.get("case_id"),
            "profile_id": record.get("profile_id"),
            "requested_model": record.get("requested_model"),
            "hint_level": level,
            "condition_id": record.get("condition_id", "default"),
            "session_id": record.get("session_id"),
            "turn_index": record.get("turn_index", 0),
            "stage": _stage(record),
        }
    if limit is not None:
        packet_rows = packet_rows[:limit]
        limited_ids = {row["review_id"] for row in packet_rows}
        mapping = {
            key: value for key, value in mapping.items()
            if key in limited_ids
        }

    review_dir = run_dir / REVIEW_DIR
    review_dir.mkdir(parents=True, exist_ok=True)
    packet_path = review_dir / "review_packet.csv"
    # Re-running a notebook must not erase edits in the exported rating sheet.
    if packet_path.exists():
        with packet_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=";")
            if "review_id" not in (reader.fieldnames or []):
                raise ValueError("Vorhandener Bewertungsbogen hat keine review_id-Spalte.")
            edited: Dict[str, List[dict]] = defaultdict(list)
            editable_fields = ["rater_id", "begruendung"] + LIKERT_FIELDS + CHOICE_FIELDS
            for row in reader:
                if any((row.get(field) or "").strip() for field in editable_fields):
                    edited[row["review_id"]].append(row)
        if set(edited) - set(mapping):
            raise ValueError(
                "Ausgefuellte Bewertungen wuerden beim Export entfallen; "
                "bestehenden Bogen getrennt aufbewahren und importieren."
            )
        packet_rows = [
            {**row, **{field: old.get(field, "") for field in editable_fields}}
            for row in packet_rows
            for old in edited.get(row["review_id"], [{}])
        ]
    with open(packet_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=RFC_REVIEW_COLUMNS, delimiter=";"
        )
        writer.writeheader()
        for row in packet_rows:
            writer.writerow(row)
    with open(review_dir / "review_mapping.json", "w", encoding="utf-8") as handle:
        json.dump({
            "schema_version": SCHEMA_VERSION,
            "run_id": manifest["run_id"],
            "blind_note": (
                "Mapping nicht an Bewerter verteilen: enthält Modell/Profil."
            ),
            "mapping": mapping,
        }, handle, ensure_ascii=False, indent=2)
    return {"packet_rows": len(packet_rows), "path": str(packet_path)}


def import_review_ratings(run_dir: Path, ratings_csv: Path) -> dict:
    """Liest Bewertungs-CSV ein und validiert gegen das Raster."""
    _manifest, generations, _checks, ratings = _load_run_core(run_dir)
    result_ids = {
        record["attempt_id"] for record in _successful_results(generations)
    }
    review_dir = run_dir / REVIEW_DIR
    mapping_path = review_dir / "review_mapping.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))["mapping"]
    rubric_version = "rubric-1.0"

    imported = 0
    valid_rows = 0
    errors: List[str] = []
    records: List[dict] = []
    existing = {
        (record["review_id"], record["rater_id"])
        for record in ratings
    }
    with open(ratings_csv, "r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        missing_columns = {"review_id", "rater_id"} - set(reader.fieldnames or [])
        if missing_columns:
            raise ValueError("Bewertungsspalten fehlen: " + ", ".join(sorted(missing_columns)))
        for line_number, row in enumerate(reader, start=2):
            review_id = (row.get("review_id") or "").strip()
            if not review_id or not any(
                (row.get(field) or "").strip()
                for field in LIKERT_FIELDS + CHOICE_FIELDS
            ):
                continue
            if review_id not in mapping:
                errors.append(
                    "Zeile " + str(line_number) + ": unbekannte review_id "
                    + review_id
                )
                continue
            if mapping[review_id]["attempt_id"] not in result_ids:
                errors.append(
                    "Zeile " + str(line_number)
                    + ": kein aktueller erfolgreicher Live-Versuch fuer " + review_id
                )
                continue
            likert, likert_errors = _parse_likert(row, line_number)
            errors.extend(likert_errors)
            choices, choice_errors = _parse_choices(row, line_number)
            errors.extend(choice_errors)
            if likert_errors or choice_errors:
                continue
            values = {**likert, **choices}
            if not _has_ratings(values):
                continue
            rater_id = (row.get("rater_id") or "").strip()
            if row.get("rating_source", "human") != "human" or row.get(
                "execution_source", "human_review"
            ) not in {"human", "human_review"}:
                errors.append("Zeile " + str(line_number) + ": only human ratings may be imported")
                continue
            if not rater_id:
                errors.append("Zeile " + str(line_number) + ": rater_id fehlt")
                continue
            reason = (row.get("begruendung") or "").strip()
            needs_reason = any(
                value is not None and value <= 2 for value in likert.values()
            ) or any(
                choices[field] == negative
                for field, negative in {
                    "mat_falsch": "ja",
                    "widerspruch_pruefergebnis": "ja",
                    "erfundene_diagnose": "ja",
                    "stufe_angemessen": "nein",
                    "loesungsverrat_unzulaessig": "ja",
                }.items()
            )
            if needs_reason and not reason:
                errors.append(
                    "Zeile " + str(line_number)
                    + ": begruendung fehlt fuer negative Markierung "
                    "oder Bewertung <= 2"
                )
                continue
            valid_rows += 1
            key = (review_id, rater_id)
            if key in existing:
                continue
            records.append({
                "schema_version": SCHEMA_VERSION,
                "rubric_version": rubric_version,
                "rating_source": "human",
                "review_id": review_id,
                "attempt_id": mapping[review_id]["attempt_id"],
                "rater_id": rater_id,
                "ratings": values,
                "begruendung": reason,
                "imported_at": row.get("imported_at", ""),
            })
            existing.add(key)
    if errors and valid_rows == 0:
        raise ValueError(
            "Bewertungsimport vollstaendig fehlgeschlagen:\n- "
            + "\n- ".join(errors[:20])
        )
    if records:
        with open(review_dir / "ratings.jsonl", "a", encoding="utf-8") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                imported += 1
    return {"imported": imported, "errors": errors, "records": imported}


def _parse_likert(row: dict, line_number: int) -> Tuple[dict, List[str]]:
    values: Dict[str, Optional[int]] = {}
    errors: List[str] = []
    for field in LIKERT_FIELDS:
        raw = (row.get(field) or "").strip()
        if raw == "":
            values[field] = None
            continue
        if raw not in {str(number) for number in range(1, 6)} and raw != "n_a":
            errors.append(
                "Zeile " + str(line_number) + ": " + field
                + " muss 1-5 oder n_a sein, erhalten: " + raw
            )
            values[field] = None
            continue
        values[field] = None if raw == "n_a" else int(raw)
    return values, errors


def _parse_choices(row: dict, line_number: int) -> Tuple[dict, List[str]]:
    values: Dict[str, Optional[str]] = {}
    errors: List[str] = []
    for field in CHOICE_FIELDS:
        raw = (row.get(field) or "").strip().lower()
        if raw == "":
            values[field] = None
            continue
        if raw not in _CHOICE_VALUES:
            errors.append(
                "Zeile " + str(line_number) + ": " + field
                + " muss ja/nein/unklar/nicht_anwendbar sein, erhalten: "
                + raw
            )
            values[field] = None
            continue
        values[field] = raw
    return values, errors


def _field_summary(values: List) -> dict:
    numeric = [value for value in values if isinstance(value, (int, float))]
    if not numeric:
        return {"n": 0, "median": None}
    return {
        "n": len(numeric),
        "median": round(statistics.median(numeric), 3),
        "mean": round(statistics.mean(numeric), 3),
        "min": min(numeric),
        "max": max(numeric),
    }


def build_report(run_dir: Path) -> dict:
    """Aggregiert technisches Ergebnis, Checks und Ratings offline."""
    manifest, generations, checks, ratings = _load_run_core(run_dir)
    results = _successful_results(generations)
    derived_dir = run_dir / DERIVED_DIR
    derived_dir.mkdir(parents=True, exist_ok=True)
    ratings_by_attempt: Dict[str, List[dict]] = defaultdict(list)
    for rating in ratings:
        ratings_by_attempt[rating["attempt_id"]].append(rating)
    checks_by_attempt: Dict[str, Dict[str, dict]] = defaultdict(dict)
    for check in checks:
        checks_by_attempt[check["attempt_id"]][check["check_id"]] = check

    outcome_counts: Dict[str, int] = defaultdict(int)
    durations: List[int] = []
    for record in generations:
        outcome_counts[record.get("outcome", "unknown")] += 1
        if record.get("duration_ms") is not None:
            durations.append(int(record["duration_ms"]))

    summary_rows: List[dict] = []
    paired_rows: List[dict] = []

    groups: Dict[Tuple, List[dict]] = defaultdict(list)
    for record in results:
        returned = record.get("returned") or {}
        groups[(
            record.get("condition_id", "default"), _model_key(record),
            record.get("profile_id", "?"), _effective_level(record),
            _stage(record), record.get("turn_index", 0),
            returned.get("policy_mode", "tutor"),
            record.get("interaction_script_sha256", sha256_json([])),
            _start_level_key(record),
        )].append(record)

    for (condition_id, model, profile_id, level, stage, turn_index, policy_mode, script_hash, start_level), records in sorted(
        groups.items(), key=lambda item: str(item[0]),
    ):
        group_ratings = [
            rating
            for record in records
            for rating in ratings_by_attempt.get(record["attempt_id"], [])
        ]
        n_rated = sum(
            bool(ratings_by_attempt.get(record["attempt_id"])) for record in records
        )
        row: dict = {
            "condition_id": condition_id,
            "model": model,
            "profile_id": profile_id,
            "hint_level": level,
            "effective_hint_level": level,
            "stage": stage,
            "turn_index": turn_index,
            "policy_mode": policy_mode,
            "interaction_script_sha256": script_hash,
            "start_level": start_level,
            "baseline_hint_levels": json.dumps(sorted({(record.get("returned") or {}).get("baseline_hint_level")
                                                        for record in records}, key=str)),
            "n_success": len(records),
            "n_rated": n_rated,
            "n_missing_ratings": len(records) - n_rated,
            "n_ratings": len(group_ratings),
            "n_duration_median_ms": None,
        }
        durations_group = [
            record["duration_ms"] for record in records
            if record.get("duration_ms") is not None
        ]
        if durations_group:
            row["n_duration_median_ms"] = int(statistics.median(durations_group))
        row["check_failures"] = sum(
            1 for record in records
            for check in checks_by_attempt.get(record["attempt_id"], {}).values()
            if check.get("status") == "fail"
        )
        present = prohibited = inconclusive = not_applicable = missing = 0
        for record in records:
            check = checks_by_attempt.get(record["attempt_id"], {}).get(
                "final_answer_disclosure"
            )
            if check is None:
                missing += 1
            elif check.get("status") == "inconclusive":
                inconclusive += 1
            elif check.get("status") == "not_applicable":
                not_applicable += 1
                present += (check.get("evidence") or {}).get("present") is True
            elif check.get("status") in {"pass", "fail"}:
                present += (check.get("evidence") or {}).get("present") is True
                prohibited += check["status"] == "fail"
        row["complete_solution_present"] = present
        row["prohibited_disclosure"] = prohibited
        row["disclosure_inconclusive"] = inconclusive
        row["disclosure_not_applicable"] = not_applicable
        row["disclosure_missing"] = missing
        for field in LIKERT_FIELDS:
            values = [
                rating["ratings"].get(field)
                for rating in group_ratings
                if rating["ratings"].get(field) is not None
            ]
            summary = _field_summary(values)
            row["rating_" + field] = summary.get("median")
            row["rating_" + field + "_n"] = summary.get("n")
        for field in CHOICE_FIELDS:
            counts = dict.fromkeys(_CHOICE_VALUES + ("fehlend",), 0)
            for rating in group_ratings:
                value = rating["ratings"].get(field)
                counts[value or "fehlend"] += 1
            for value, count in counts.items():
                row["rating_" + field + "_" + value + "_n"] = count
            row["rating_" + field + "_N"] = len(group_ratings)
        summary_rows.append(row)

    by_key: Dict[Tuple, dict] = {}
    ambiguous_pair_cells = set()
    for record in results:
        key = (
            record.get("condition_id", "default"),
            record.get("interaction_script_sha256", sha256_json([])),
            record.get("case_id"), _start_level_key(record),
            record.get("repetition"), _model_key(record),
            record.get("turn_index", 0),
        )
        profile_map = by_key.setdefault(key, {})
        if record.get("profile_id") in profile_map:
            profile_map[record.get("profile_id")] = None
            ambiguous_pair_cells.add(key + (record.get("profile_id"),))
        else:
            profile_map[record.get("profile_id")] = record
    for (condition_id, script_hash, case_id, level, repetition, model, turn_index), profile_map in sorted(
        by_key.items(), key=lambda item: str(item[0]),
    ):
        base_record = profile_map.get("base")
        base_helpfulness = _helpfulness(base_record, ratings_by_attempt)
        for profile_id, record in sorted(profile_map.items()):
            if profile_id == "base":
                continue
            helpfulness = _helpfulness(record, ratings_by_attempt)
            if helpfulness is None or base_helpfulness is None:
                continue
            paired_rows.append({
                "condition_id": condition_id,
                "interaction_script_sha256": script_hash,
                "case_id": case_id,
                "hint_level": level,
                "effective_hint_level": _effective_level(record),
                "base_effective_hint_level": _effective_level(base_record),
                "baseline_hint_level": (record.get("returned") or {}).get("baseline_hint_level"),
                "base_baseline_hint_level": (base_record.get("returned") or {}).get("baseline_hint_level"),
                "stage": _stage(record),
                "base_stage": _stage(base_record),
                "turn_index": turn_index,
                "repetition": repetition,
                "model": model,
                "profile_id": profile_id,
                "compared_to": "base",
                "hilfreichkeit": helpfulness,
                "hilfreichkeit_base": base_helpfulness,
                "delta": helpfulness - base_helpfulness,
            })

    coverage = {
        "planned_jobs": (manifest.get("counts") or {}).get("jobs"),
        "generations_total": len(generations),
        "generations_live_success": sum(
            1 for record in generations if record.get("outcome") == "success"
        ),
        "responses_total": len(results),
        "checks_total": len(checks),
        "ratings_total": len(ratings),
        "attempts_with_ratings": len(ratings_by_attempt),
        "responses_with_ratings": len(ratings_by_attempt),
        "responses_missing_ratings": len(results) - len(ratings_by_attempt),
        "sessions_total": len({record["session_id"] for record in results if record.get("session_id")}),
        "conditions_total": len({record.get("condition_id", "default") for record in results}),
        "ambiguous_pair_cells": len(ambiguous_pair_cells),
        "dependency_blocked_jobs": len({
            event.get("job_id") for event in _read_jsonl(run_dir / runner.EVENTS_FILE)
            if event.get("event") == "job_blocked"
            and event.get("job_id") not in {record["job_id"] for record in results}
        }),
    }

    _write_csv(derived_dir / "summary.csv", summary_rows)
    _write_csv(derived_dir / "paired_comparisons.csv", paired_rows)
    report_path = derived_dir / "report.md"
    report_path.write_text(
        _render_report(manifest, coverage, outcome_counts, durations,
                       summary_rows, paired_rows),
        encoding="utf-8",
    )
    return {
        "summary_rows": len(summary_rows),
        "paired_rows": len(paired_rows),
        "coverage": coverage,
        "report_path": str(report_path),
    }


def compare_runs(run_dirs: List[Path]) -> dict:
    """Pair conditions against the first run, using only saved live/human evidence.

    Match case/profile/start selection/model/repetition/turn and the complete
    script fingerprint. Effective levels and stages are outcomes, not keys.
    Missing answers or ratings stay explicit; no judge scores are pooled.
    """
    if len(run_dirs) < 2:
        raise ValueError("Condition comparison requires at least two runs")
    cores = [_load_run_core(Path(directory)) for directory in run_dirs]
    conditions = [manifest.get("condition_id", "default") for manifest, *_rest in cores]
    if len(set(conditions)) != len(conditions):
        raise ValueError("Compared runs must have distinct condition_id values")
    maps = []
    planned_keys = []
    ratings_maps = []
    case_hashes = []
    for manifest, generations, _checks, ratings in cores:
        records = _successful_results(generations)
        cells = {}
        by_attempt = defaultdict(list)
        corpus_path = (manifest.get("paths") or {}).get("corpus")
        corpus_hash = (manifest.get("hashes") or {}).get("corpus_file")
        if corpus_path and corpus_hash and runner.sha256_file(runner.CODE_DIR / corpus_path) != corpus_hash:
            raise ValueError("Frozen comparison corpus identity changed")
        case_hashes.append({
            case.case_id: sha256_json(case.model_dump(mode="json"))
            for case in load_cases(runner.CODE_DIR / corpus_path)
        } if corpus_path else {})
        for rating in ratings:
            by_attempt[rating["attempt_id"]].append(rating)
        for record in records:
            key = (
                record.get("case_id"), record.get("profile_id"),
                _start_level_key(record), record.get("repetition"), _model_key(record),
                record.get("turn_index", 0), record["interaction_script_sha256"],
            )
            if key in cells:
                raise ValueError("Multiple responses occupy a condition comparison cell")
            cells[key] = record
        keys = set(cells)
        plan_path = Path(run_dirs[len(maps)]) / runner.PLAN_FILE
        if plan_path.exists() and manifest.get("execution_mode") != "offline_demo":
            plan_hash = manifest.get("plan_sha256") or (manifest.get("hashes") or {}).get("plan_file")
            if plan_hash and runner.sha256_file(plan_path) != plan_hash:
                raise ValueError("Frozen comparison plan identity changed")
            successful_by_job = {record["job_id"]: record for record in records}
            for job in _read_jsonl(plan_path):
                if job.get("record_type") != "job":
                    continue
                model = _model_key(successful_by_job[job["job_id"]]) if job["job_id"] in successful_by_job else (
                    job.get("model") or (manifest.get("runtime") or {}).get("default_model") or "server_default"
                )
                keys.add((
                    job.get("case_id"), job.get("profile_id"), _start_level_key(job),
                    job.get("repetition"), model, job.get("turn_index", 0),
                    job.get("interaction_script_sha256", manifest.get("interaction_script_sha256", sha256_json([]))),
                ))
        maps.append(cells)
        planned_keys.append(keys)
        ratings_maps.append(by_attempt)
    reference = maps[0]
    rows = []
    exclusions = []
    for index, cells in enumerate(maps[1:], start=1):
        for key in sorted(planned_keys[0] | planned_keys[index], key=str):
            case_id, profile_id, start_level, repetition, model, turn_index, script_hash = key
            identity = {
                "reference_condition_id": conditions[0], "condition_id": conditions[index],
                "case_id": case_id, "profile_id": profile_id, "start_level": start_level,
                "repetition": repetition, "model": model, "turn_index": turn_index,
                "interaction_script_sha256": script_hash,
            }
            baseline, candidate = reference.get(key), cells.get(key)
            if baseline is None or candidate is None:
                exclusions.append({
                    **identity, "reason": "missing_matching_live_response",
                    "reference_available": baseline is not None,
                    "condition_available": candidate is not None,
                })
                continue
            baseline_hash = baseline.get("case_sha256") or case_hashes[0].get(case_id)
            candidate_hash = candidate.get("case_sha256") or case_hashes[index].get(case_id)
            if baseline_hash is None or candidate_hash is None or baseline_hash != candidate_hash:
                exclusions.append({**identity, "reason": "case_identity_missing_or_changed"})
                continue
            baseline_score = _helpfulness(baseline, ratings_maps[0])
            candidate_score = _helpfulness(candidate, ratings_maps[index])
            rows.append({
                **identity,
                "reference_run_id": cores[0][0]["run_id"],
                "run_id": cores[index][0]["run_id"],
                "reference_attempt_id": baseline["attempt_id"], "attempt_id": candidate["attempt_id"],
                "reference_effective_hint_level": _effective_level(baseline),
                "effective_hint_level": _effective_level(candidate),
                "reference_baseline_hint_level": (baseline.get("returned") or {}).get("baseline_hint_level"),
                "baseline_hint_level": (candidate.get("returned") or {}).get("baseline_hint_level"),
                "reference_stage": _stage(baseline), "stage": _stage(candidate),
                "reference_config_sha256": (baseline.get("returned") or {}).get("config_sha256"),
                "config_sha256": (candidate.get("returned") or {}).get("config_sha256"),
                "case_sha256": baseline_hash,
                "reference_hilfreichkeit": baseline_score, "hilfreichkeit": candidate_score,
                "delta": None if baseline_score is None or candidate_score is None else candidate_score - baseline_score,
                "rating_pair_status": "complete" if baseline_score is not None and candidate_score is not None else "missing_human_rating",
            })
    return {
        "reference_condition_id": conditions[0], "paired_rows": rows, "exclusions": exclusions,
        "comparison_basis": "controlled_hypotheses_not_authoritative" if any(
            manifest.get("allow_unverified_cases") for manifest, *_rest in cores
        ) else "reported_verification_not_independently_verified",
        "coverage": {
            "expected_comparison_cells": len(rows) + len(exclusions),
            "paired_responses": len(rows),
            "paired_human_ratings": sum(row["delta"] is not None for row in rows),
            "pairs_missing_human_ratings": sum(row["delta"] is None for row in rows),
            "unmatched_cells": len(exclusions),
        },
    }


def _helpfulness(
    record: Optional[dict], ratings_by_attempt: Dict[str, List[dict]],
) -> Optional[float]:
    if record is None:
        return None
    ratings = ratings_by_attempt.get(record["attempt_id"], [])
    values = [
        rating["ratings"].get("hilfreichkeit_naechster_schritt")
        for rating in ratings
        if rating["ratings"].get("hilfreichkeit_naechster_schritt") is not None
    ]
    if not values:
        return None
    return statistics.median(values)


def _write_csv(path: Path, rows: List[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: List[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _render_report(
    manifest: dict,
    coverage: dict,
    outcome_counts: Dict[str, int],
    durations: List[int],
    summary_rows: List[dict],
    paired_rows: List[dict],
) -> str:
    lines: List[str] = []
    lines.append("# Evaluationsbericht " + manifest["run_id"])
    lines.append("")
    lines.append("*Experiment:* " + manifest.get("experiment_id", "?")
                 + " / Protokoll " + manifest.get("protocol_version", "?"))
    lines.append("*Instanz:* " + manifest.get("base_url", "?"))
    lines.append("")
    if manifest.get("allow_unverified_cases"):
        lines.append(
            "> **Kontrollierte Hypothesen:** Empirische Live-Ausgaben auf "
            "synthetischen oder nicht verifizierten Faellen. Referenzen und "
            "Fehlerdiagnosen sind Hypothesen, keine nachgewiesenen STACK-/PRT-Urteile. "
            "Offline-Demos bleiben von diesen Kennzahlen ausgeschlossen."
        )
        lines.append("")
    lines.append("## Technische Live-Versuche")
    lines.append("")
    lines.append("| Ausgang | Anzahl |")
    lines.append("|---|---:|")
    for outcome, count in sorted(outcome_counts.items()):
        lines.append("| " + outcome + " | " + str(count) + " |")
    lines.append("")
    if durations:
        ordered = sorted(durations)
        p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
        lines.append(
            "*Dauer:* Median " + str(int(statistics.median(durations)))
            + " ms / p95 " + str(p95) + " ms"
        )
        lines.append("")
    lines.append("## Abdeckung")
    lines.append("")
    for key, value in coverage.items():
        lines.append("- " + key + ": " + str(value))
    lines.append("")
    lines.append(
        "Bewertete Antworten: " + str(coverage["responses_with_ratings"])
        + "/" + str(coverage["responses_total"])
        + "; Antworten ohne Ratings: " + str(coverage["responses_missing_ratings"])
        + ". Teilratings zaehlen als bewertet, leere Felder bleiben fehlend."
    )
    lines.append("")
    if summary_rows:
        lines.append("## Modell / Profil / Stufe")
        lines.append("")
        lines.append("Nur die neueste erfolgreiche Live-Antwort je Job; "
                     "Fehlversuche bleiben technische Attempts.")
        lines.append("")
        lines.append("| Modell | Profil | Stufe | N Antworten | Bewertet | "
                      "Ohne Rating | Prueffehler | Loesung vorhanden | "
                      "Unzulaessig | inconclusive | Nicht anwendbar | "
                      "Check fehlt | Hilfreichkeit (Median/n) | Bedingung | Phase | Turn |")
        lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|")
        for row in summary_rows:
            lines.append(
                "| " + str(row["model"])
                + " | " + str(row["profile_id"])
                + " | " + str(row["hint_level"])
                + " | " + str(row["n_success"])
                + " | " + str(row["n_rated"])
                + " | " + str(row["n_missing_ratings"])
                + " | " + str(row["check_failures"])
                + " | " + str(row["complete_solution_present"])
                + " | " + str(row["prohibited_disclosure"])
                + " | " + str(row["disclosure_inconclusive"])
                + " | " + str(row["disclosure_not_applicable"])
                + " | " + str(row["disclosure_missing"])
                + " | "
                + str(row.get("rating_hilfreichkeit_naechster_schritt"))
                + " / "
                + str(row.get("rating_hilfreichkeit_naechster_schritt_n"))
                + " | " + str(row["condition_id"])
                + " | " + str(row["stage"])
                + " | " + str(row["turn_index"])
                + " |"
            )
        lines.append("")
        lines.append("## Fachliche Kriterien")
        lines.append("")
        lines.append(
            "Jedes Kriterium getrennt als n/N; N = Ratingboegen (einschliesslich "
            "Teilratings), nicht unabhaengige Antworten. Antworten ohne Rating "
            "stehen separat oben. Keine kompensierende Gesamtnote."
        )
        lines.append("")
        lines.append("| Modell | Profil | Stufe | Kriterium | ja | nein | "
                      "unklar | nicht_anwendbar | fehlend | Bedingung | Phase | Turn |")
        lines.append("|---|---|---:|---|---:|---:|---:|---:|---:|---|---|---:|")
        for row in summary_rows:
            for field in CHOICE_FIELDS:
                prefix = "rating_" + field
                cells = [
                    str(row[key]) for key in ("model", "profile_id", "hint_level")
                ]
                cells.append(field)
                cells.extend(
                    str(row[prefix + "_" + value + "_n"])
                    + "/" + str(row[prefix + "_N"])
                    for value in _CHOICE_VALUES + ("fehlend",)
                )
                cells.extend(str(row[key]) for key in ("condition_id", "stage", "turn_index"))
                lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    if paired_rows:
        lines.append("## Paarvergleiche gegen base")
        lines.append("")
        lines.append("| Fall | Stufe | Wiederholung | Modell | Profil | "
                      "Delta Hilfreichkeit | Bedingung | Turn | Effektiv | base Effektiv |")
        lines.append("|---|---:|---:|---|---|---:|---|---:|---:|---:|")
        for row in paired_rows:
            lines.append(
                "| " + str(row["case_id"])
                + " | " + str(row["hint_level"])
                + " | " + str(row["repetition"])
                + " | " + str(row["model"])
                + " | " + str(row["profile_id"])
                + " | " + str(row["delta"])
                + " | " + str(row["condition_id"])
                + " | " + str(row["turn_index"])
                + " | " + str(row["effective_hint_level"])
                + " | " + str(row["base_effective_hint_level"])
                + " |"
            )
        lines.append("")
    lines.append("## Grenzen")
    lines.append("")
    for note in [
        "Nur execution_source=live_tutor_api wird ausgewertet; Checks und "
        "Ratings fuer Offline-Demos, unbekannte oder ersetzte Antworten "
        "fliessen nicht in Inhaltskennzahlen ein.",
        "Fehlende/fehlgeschlagene Aufrufe bleiben im Rohdatensatz. "
        "Retry-Erfolge sind keine zusaetzlichen unabhaengigen Antworten.",
        "Offenlegung mit status=inconclusive bleibt getrennt von "
        "positiven Befunden und zaehlt nicht als bestanden oder vorhanden. "
        "Ein fehlender Formeltreffer beweist keine Abwesenheit von Loesungsverrat.",
        "Bewertungen fehlen teilweise; Kennzahlen weisen ihre Nenner aus.",
        "Modellkey: requested_model, sonst zurueckgegebener Alias, sonst "
        "server_default (tatsaechlicher Alias unbekannt).",
        "Bedingung, effektive Stufe, Phase und Turn bleiben getrennt. "
        "Paarvergleiche kontrollieren Startwahl und Skript; adaptive Endstufen sind Ergebnisse.",
        "Nur menschliche Ratings gehen in diese Kriterien ein; Zweitmodell-Urteile "
        "bleiben separate Artefakte. Wiederholungen sind keine unabhaengigen Aufgaben.",
        "Telemetrie (Token, Upstream-Versuche) laut Manifest unbekannt.",
    ]:
        lines.append("- " + note)
    lines.append("")
    return "\n".join(lines)
