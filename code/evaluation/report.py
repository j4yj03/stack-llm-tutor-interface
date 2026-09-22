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

from evaluation.checks import load_policy
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
    ["review_id", "hilfestufe", "hilfestufenziel", "aufgabenstellung",
     "studentische_antwort", "referenz_endloesung", "erwarteter_fehlerfall",
     "tutorhinweis"]
    + LIKERT_FIELDS + CHOICE_FIELDS + ["begruendung"]
)
_CHOICE_VALUES = {"ja", "nein", "unklar", "nicht_anwendbar", ""}


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


def _load_run_core(run_dir: Path):
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            "Kein Manifest im Run-Verzeichnis: " + str(run_dir)
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    generations = [
        record for record in _read_jsonl(run_dir / GENERATIONS_FILE)
        if record.get("execution_source") == "live_tutor_api"
    ]
    checks = _read_jsonl(run_dir / CHECKS_FILE)
    ratings = _read_jsonl(run_dir / REVIEW_DIR / "ratings.jsonl")
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
    review_dir = run_dir / REVIEW_DIR
    review_dir.mkdir(parents=True, exist_ok=True)
    policy = manifest.get("hint_policy")
    if not policy:
        from evaluation.runner import POLICY_PATH

        policy = load_policy(POLICY_PATH)

    packet_rows: List[dict] = []
    mapping: Dict[str, dict] = {}
    for record in generations:
        if record.get("outcome") != "success":
            continue
        returned = record.get("returned") or {}
        hint = returned.get("hint") or ""
        level = record.get("hint_level")
        level_policy = policy.get(str(level), {})
        review_id = _review_id(manifest["run_id"], record["attempt_id"])
        payload = record.get("request_payload") or {}
        stack = payload.get("stack") or {}
        packet_rows.append({
            "review_id": review_id,
            "hilfestufe": level,
            "hilfestufenziel": level_policy.get("goal", ""),
            "aufgabenstellung": stack.get("question_text", ""),
            "studentische_antwort": stack.get("student_answer", ""),
            "referenz_endloesung": "",
            "erwarteter_fehlerfall": "",
            "tutorhinweis": hint,
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
        }
    if limit is not None:
        packet_rows = packet_rows[:limit]
        limited_ids = {row["review_id"] for row in packet_rows}
        mapping = {
            key: value for key, value in mapping.items()
            if key in limited_ids
        }

    packet_path = review_dir / "review_packet.csv"
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
    review_dir = run_dir / REVIEW_DIR
    mapping_path = review_dir / "review_mapping.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))["mapping"]
    rubric_version = "rubric-1.0"

    imported = 0
    errors: List[str] = []
    records: List[dict] = []
    with open(ratings_csv, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for line_number, row in enumerate(reader, start=2):
            review_id = (row.get("review_id") or "").strip()
            if not review_id:
                continue
            if review_id not in mapping:
                errors.append(
                    "Zeile " + str(line_number) + ": unbekannte review_id "
                    + review_id
                )
                continue
            rater_id = (row.get("rater_id") or "").strip()
            if not rater_id:
                errors.append(
                    "Zeile " + str(line_number) + ": rater_id fehlt"
                )
                continue
            likert, likert_errors = _parse_likert(row, line_number)
            errors.extend(likert_errors)
            choices, choice_errors = _parse_choices(row, line_number)
            errors.extend(choice_errors)
            if likert_errors or choice_errors:
                continue
            records.append({
                "schema_version": SCHEMA_VERSION,
                "rubric_version": rubric_version,
                "review_id": review_id,
                "attempt_id": mapping[review_id]["attempt_id"],
                "rater_id": rater_id,
                "ratings": {**likert, **choices},
                "begruendung": (row.get("begruendung") or "").strip(),
                "imported_at": row.get("imported_at", ""),
            })
            imported += 1
    if errors and imported == 0:
        raise ValueError(
            "Bewertungsimport vollständig fehlgeschlagen:\n- "
            + "\n- ".join(errors[:20])
        )
    if records:
        existing = {
            (record["review_id"], record["rater_id"])
            for record in _read_jsonl(review_dir / "ratings.jsonl")
        }
        with open(review_dir / "ratings.jsonl", "a", encoding="utf-8") as handle:
            for record in records:
                key = (record["review_id"], record["rater_id"])
                if key in existing:
                    continue
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"imported": imported, "errors": errors, "records": len(records)}


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
        values[field] = None if raw == "" else raw
    return values, errors


def _field_summary(values: List) -> dict:
    numeric = [value for value in values if isinstance(value, (int, float))]
    if not numeric:
        return {"n": len(values), "median": None}
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
    derived_dir = run_dir / DERIVED_DIR
    derived_dir.mkdir(parents=True, exist_ok=True)
    ratings_by_attempt: Dict[str, List[dict]] = defaultdict(list)
    for rating in ratings:
        ratings_by_attempt[rating["attempt_id"]].append(rating)
    checks_by_attempt: Dict[str, List[dict]] = defaultdict(list)
    for check in checks:
        checks_by_attempt[check["attempt_id"]].append(check)

    outcome_counts: Dict[str, int] = defaultdict(int)
    durations: List[int] = []
    for record in generations:
        outcome_counts[record.get("outcome", "unknown")] += 1
        if record.get("duration_ms") is not None:
            durations.append(int(record["duration_ms"]))

    summary_rows: List[dict] = []
    disclosure_rows: List[dict] = []
    paired_rows: List[dict] = []

    groups: Dict[Tuple[str, int], List[dict]] = defaultdict(list)
    for record in generations:
        if record.get("outcome") != "success":
            continue
        groups[(record.get("profile_id", "?"), record.get("hint_level", 0))].append(
            record
        )

    for (profile_id, level), records in sorted(groups.items()):
        row: dict = {
            "profile_id": profile_id,
            "hint_level": level,
            "n_success": len(records),
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
            for check in checks_by_attempt.get(record["attempt_id"], [])
            if check.get("status") == "fail"
        )
        present = prohibited = 0
        for record in records:
            for check in checks_by_attempt.get(record["attempt_id"], []):
                if check["check_id"] != "final_answer_disclosure":
                    continue
                evidence = check.get("evidence", {})
                if evidence.get("present"):
                    present += 1
                    if check["status"] == "fail":
                        prohibited += 1
        row["complete_solution_present"] = present
        row["prohibited_disclosure"] = prohibited
        for field in LIKERT_FIELDS:
            values = [
                rating["ratings"].get(field)
                for record in records
                for rating in ratings_by_attempt.get(record["attempt_id"], [])
                if rating["ratings"].get(field) is not None
            ]
            summary = _field_summary(values)
            row["rating_" + field] = summary.get("median")
            row["rating_" + field + "_n"] = summary.get("n")
        summary_rows.append(row)

        disclosure_rows.append({
            "profile_id": profile_id,
            "hint_level": level,
            "n_success": len(records),
            "complete_solution_present": present,
            "prohibited_disclosure": prohibited,
        })

    by_key: Dict[Tuple, dict] = {}
    for record in generations:
        if record.get("outcome") != "success":
            continue
        key = (
            record.get("case_id"), record.get("hint_level"),
            record.get("repetition"),
        )
        by_key.setdefault(key, {})[record.get("profile_id")] = record
    for (case_id, level, repetition), profile_map in sorted(by_key.items()):
        base_record = profile_map.get("base")
        base_helpfulness = _helpfulness(base_record, ratings_by_attempt)
        for profile_id, record in sorted(profile_map.items()):
            if profile_id == "base":
                continue
            helpfulness = _helpfulness(record, ratings_by_attempt)
            if helpfulness is None or base_helpfulness is None:
                continue
            paired_rows.append({
                "case_id": case_id,
                "hint_level": level,
                "repetition": repetition,
                "profile_id": profile_id,
                "compared_to": "base",
                "hilfreichkeit": helpfulness,
                "hilfreichkeit_base": base_helpfulness,
                "delta": helpfulness - base_helpfulness,
            })

    coverage = {
        "generations_total": len(generations),
        "generations_live_success": sum(
            1 for record in generations if record.get("outcome") == "success"
        ),
        "checks_total": len(checks),
        "ratings_total": len(ratings),
        "attempts_with_ratings": len(
            {rating["attempt_id"] for rating in ratings}
        ),
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


def _helpfulness(record: Optional[dict], ratings_by_attempt) -> Optional[int]:
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
                 + " · Protokoll " + manifest.get("protocol_version", "?"))
    lines.append("*Instanz:* " + manifest.get("base_url", "?"))
    lines.append("")
    if manifest.get("allow_unverified_cases"):
        lines.append(
            "> **Demonstrationslauf:** Korpus enthält nicht verifizierte "
            "Fälle. Ergebnisse dienen der Werkzeugprüfung, nicht der "
            "fachlichen Aussage."
        )
        lines.append("")
    lines.append("## Durchlauf")
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
            + " ms · p95 " + str(p95) + " ms"
        )
        lines.append("")
    lines.append("## Abdeckung")
    lines.append("")
    for key, value in coverage.items():
        lines.append("- " + key + ": " + str(value))
    lines.append("")
    if summary_rows:
        lines.append("## Profile × Stufe (nur erfolgreiche Live-Antworten)")
        lines.append("")
        lines.append("| Profil | Stufe | n | Prüffehler | Lösung vorhanden | "
                     "unzulässig | Hilfreichkeit (Median/n) |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|")
        for row in summary_rows:
            lines.append(
                "| " + str(row["profile_id"])
                + " | " + str(row["hint_level"])
                + " | " + str(row["n_success"])
                + " | " + str(row["check_failures"])
                + " | " + str(row["complete_solution_present"])
                + " | " + str(row["prohibited_disclosure"])
                + " | "
                + str(row.get("rating_hilfreichkeit_naechster_schritt"))
                + " / "
                + str(row.get("rating_hilfreichkeit_naechster_schritt_n"))
                + " |"
            )
        lines.append("")
    if paired_rows:
        lines.append("## Paarvergleiche gegen base")
        lines.append("")
        lines.append("| Fall | Stufe | Profil | Δ Hilfreichkeit |")
        lines.append("|---|---:|---|---:|")
        for row in paired_rows:
            lines.append(
                "| " + str(row["case_id"])
                + " | " + str(row["hint_level"])
                + " | " + str(row["profile_id"])
                + " | " + str(row["delta"])
                + " |"
            )
        lines.append("")
    lines.append("## Grenzen")
    lines.append("")
    for note in [
        "Fehlende/fehlgeschlagene Aufrufe sind im Rohdatensatz enthalten "
        "und werden nicht still entfernt.",
        "Nicht bewertbare mathematische Attribute bleiben unbestimmt "
        "(inconclusive) und zählen nicht als bestanden.",
        "Bewertungen fehlen teilweise; Kennzahlen weisen n aus.",
        "Telemetrie (Token, Upstream-Versuche) laut Manifest unbekannt.",
    ]:
        lines.append("- " + note)
    lines.append("")
    return "\n".join(lines)
