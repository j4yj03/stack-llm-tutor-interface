"""Tests für Review-Export/-Import und Berichtserstellung (offline)."""

import csv
import json
from pathlib import Path

import pytest

from evaluation.report import (
    build_report,
    export_review_packet,
    import_review_ratings,
)

CODE_DIR = Path(__file__).resolve().parents[1]
EVAL_DIR = CODE_DIR / "evaluation"


def write_line(path: Path, record) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


@pytest.fixture()
def run_dir(tmp_path):
    run_dir = tmp_path / "runs" / "report-001"
    run_dir.mkdir(parents=True)
    policy = json.loads(
        (CODE_DIR / "config" / "hint_levels.json").read_text(encoding="utf-8")
    )
    manifest = {
        "run_id": "report-001",
        "experiment_id": "exp-test",
        "protocol_version": "eval-protocol-1",
        "base_url": "http://tutor.test",
        "allow_unverified_cases": True,
        "hint_policy": policy,
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )

    context_options = {"include_question_text": True, "include_student_answer": True}
    prompt = [
        {"role": "system", "content": "policy"},
        {"role": "user", "content": "Aufgabe Antwort"},
    ]

    def generation(attempt, case, profile, level, hint, outcome="success",
                   source="live_tutor_api"):
        return {
            "schema_version": "1.0",
            "run_id": "report-001",
            "attempt_id": attempt,
            "job_id": "job-" + attempt,
            "execution_source": source,
            "case_id": case,
            "task_instance_id": case,
            "profile_id": profile,
            "hint_level": level,
            "requested_model": None,
            "repetition": 1,
            "request_payload": {
                "stack": {"question_id": case},
                "context_options": context_options,
            },
            "request_sha256": "0" * 64,
            "started_at_utc": "2026-09-21T10:00:00+00:00",
            "finished_at_utc": "2026-09-21T10:00:01+00:00",
            "duration_ms": 100,
            "outcome": outcome,
            "returned": None if outcome != "success" else {
                "chat_id": "chat",
                "question_id": case,
                "hint_level": level,
                "model": "m",
                "hint": hint,
                "prompt_messages": prompt,
                "context_options": context_options,
            },
            "safe_error": None,
            "retry_of_attempt_id": None,
        }

    write_line(run_dir / "generations.jsonl", generation(
        "a1", "fall-a", "base", 1, "Prüfe die äußere Funktion.", source="live_tutor_api"))
    write_line(run_dir / "generations.jsonl", generation(
        "a2", "fall-a", "diagnosis", 1, "Prüfe die innere Ableitung.", source="live_tutor_api"))
    # Fehlgeschlagen und unklar bleiben im Protokoll.
    failed = generation("a3", "fall-a", "base", 1, "",
                        outcome="server_error")
    failed["returned"] = None
    failed["safe_error"] = "Tutor-HTTP-Status 502: X"
    write_line(run_dir / "generations.jsonl", failed)
    # Mock-Daten zählen nicht.
    write_line(run_dir / "generations.jsonl", generation(
        "a4", "fall-a", "base", 1, "Mockantwort", source="mock"))
    # Checks: Offenlegung fail auf Stufe 1, Prüffehler vorhanden.
    write_line(run_dir / "checks.jsonl", {
        "schema_version": "1.0", "check_version": "1.0",
        "check_id": "final_answer_disclosure", "status": "fail",
        "attempt_id": "a1", "job_id": "job-a1",
        "evidence": {"present": True, "allowed_at_level": False},
        "reason": "",
    })
    write_line(run_dir / "checks.jsonl", {
        "schema_version": "1.0", "check_version": "1.0",
        "check_id": "word_count", "status": "pass",
        "attempt_id": "a2", "job_id": "job-a2",
        "evidence": {}, "reason": "",
    })
    return run_dir


def test_review_export_excludes_mock_and_blinds_profile(run_dir):
    result = export_review_packet(run_dir)
    assert result["packet_rows"] == 2  # a3 fehlerhaft, a4 mock → raus
    packet_path = run_dir / "reviews" / "review_packet.csv"
    with open(packet_path, encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        header = reader.fieldnames or []
        rows = list(reader)
    # Blind gegenüber Modell/Kontextprofil: keine solchen Spalten im Bogen.
    assert not any(
        "profil" in column or "modell" in column or "model" in column
        for column in header
    )
    mapping = json.loads(
        (run_dir / "reviews" / "review_mapping.json").read_text(encoding="utf-8")
    )
    assert set(mapping["mapping"]) == {row["review_id"] for row in rows}
    # Mapping enthält die echten Kontexte (für Auswertung, nicht für Bewerter).
    profile_ids = {value["profile_id"] for value in mapping["mapping"].values()}
    assert "diagnosis" in profile_ids


def test_review_import_validates_and_report_aggregates(run_dir):
    exported = export_review_packet(run_dir)
    assert exported["packet_rows"] == 2
    packet_path = run_dir / "reviews" / "review_packet.csv"
    with open(packet_path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    ratings_values = {"1": (1, 3), "2": (5, 5)}
    rating_rows = []
    for index, row in enumerate(rows, start=1):
        likert, _reference = ratings_values[str(index)]
        row["rater_id"] = "expert-1"
        row["passung_fehler"] = str(likert)
        row["verstaendlichkeit"] = "4"
        row["hilfreichkeit_naechster_schritt"] = str(likert)
        row["aktivierung"] = "4"
        row["sprachliche_praezision"] = "4"
        row["mat_falsch"] = "nein"
        row["widerspruch_pruefergebnis"] = "nein"
        row["erfundene_diagnose"] = "nein"
        row["stufe_angemessen"] = "ja"
        row["loesung_vollstaendig"] = "ja" if likert == 1 else "nein"
        row["loesungsverrat_unzulaessig"] = "ja" if likert == 1 else "nein"
        row["begruendung"] = "textbeleg"
        rating_rows.append(row)
    ratings_csv = run_dir / "bewertungen.csv"
    with open(ratings_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rating_rows[0].keys()), delimiter=";"
        )
        writer.writeheader()
        for row in rating_rows:
            writer.writerow(row)

    imported = import_review_ratings(run_dir, ratings_csv)
    assert imported["imported"] == 2

    # Teilweise ungültige Datei: gültige Zeile importiert, Fehler gemeldet.
    bad_rows = [
        rating_rows[0],
        {**rating_rows[1], "hilfreichkeit_naechster_schritt": "99"},
    ]
    bad_csv = run_dir / "bad.csv"
    with open(bad_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rating_rows[0].keys()), delimiter=";"
        )
        writer.writeheader()
        for row in bad_rows:
            writer.writerow(row)
    result_bad = import_review_ratings(run_dir, bad_csv)
    assert result_bad["imported"] == 1
    assert result_bad["errors"]
    # Vollständig ungültige Datei: Importer bricht mit Fehler ab.
    only_bad_csv = run_dir / "only_bad.csv"
    with open(only_bad_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rating_rows[0].keys()), delimiter=";"
        )
        writer.writeheader()
        writer.writerow(
            {**rating_rows[1], "hilfreichkeit_naechster_schritt": "99"}
        )
    with pytest.raises(ValueError):
        import_review_ratings(run_dir, only_bad_csv)

    built = build_report(run_dir)
    coverage = built["coverage"]
    # Rohprotokoll zählt Live-Datensätze inkl. fehlgeschlagenem Versuch;
    # Mock (a4) bleibt außen und geht in keine Kennzahlen ein.
    assert coverage["generations_total"] == 3
    assert coverage["generations_live_success"] == 2
    assert coverage["ratings_total"] == 2
    summary_path = run_dir / "derived" / "summary.csv"
    assert summary_path.exists()
    report_text = (run_dir / "derived" / "report.md").read_text(encoding="utf-8")
    assert "unzulässig" in report_text
    assert "Demonstrationslauf" in report_text  # allow_unverified_cases=true


def test_reporting_flags_rater_agreement_shape(run_dir):
    export_review_packet(run_dir)
    packet_path = run_dir / "reviews" / "review_packet.csv"
    with open(packet_path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    rating_rows = []
    for rater_id in ("expert-1", "expert-2"):
        for index, review_row in enumerate(rows, start=1):
            row = {**review_row, "rater_id": rater_id}
            row["hilfreichkeit_naechster_schritt"] = str(1 + index)
            rating_rows.append(row)
    ratings_csv = run_dir / "double.csv"
    with open(ratings_csv, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(rating_rows[0].keys()), delimiter=";"
        )
        writer.writeheader()
        for row in rating_rows:
            writer.writerow(row)
    import_review_ratings(run_dir, ratings_csv)
    # Doppelimport: Zeilen wurden bereits erfasst → kein Duplikat.
    rerun = import_review_ratings(run_dir, ratings_csv)
    assert rerun["imported"] == 4
    ratings_path = run_dir / "reviews" / "ratings.jsonl"
    assert len([
        line for line in ratings_path.read_text(encoding="utf-8")
        .splitlines() if line.strip()
    ]) == 4
    coverage = build_report(run_dir)["coverage"]
    assert coverage["attempts_with_ratings"] == 2
