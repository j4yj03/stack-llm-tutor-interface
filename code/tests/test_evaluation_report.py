"""Tests für Review-Export/-Import und Berichtserstellung (offline)."""

import csv
import json
from pathlib import Path
from typing import List

import pytest

from evaluation import runner
from evaluation.corpus import load_cases
from evaluation.report import (
    CHOICE_FIELDS,
    LIKERT_FIELDS,
    RFC_REVIEW_COLUMNS,
    build_report,
    export_review_packet,
    import_review_ratings,
)

CODE_DIR = Path(__file__).resolve().parents[1]
EVAL_DIR = CODE_DIR / "evaluation"


def write_line(path: Path, record: dict) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> List[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_csv(path: Path, delimiter: str = ",") -> List[dict]:
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_ratings(path: Path, rows: List[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RFC_REVIEW_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


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
    assert "rater_id" in header
    # Shipped Legacy-Testartefakt: kein Korpuspfad, keine erfundenen Referenzen.
    for row in rows:
        assert row["rater_id"] == ""
        assert row["referenz_endloesung"] == ""
        assert row["erwarteter_fehlerfall"] == ""
        assert row["erwartete_validitaet"] == ""
        assert row["erwartete_korrektheit"] == ""
    mapping = json.loads(
        (run_dir / "reviews" / "review_mapping.json").read_text(encoding="utf-8")
    )
    assert set(mapping["mapping"]) == {row["review_id"] for row in rows}
    # Mapping enthält die echten Kontexte (für Auswertung, nicht für Bewerter).
    profile_ids = {value["profile_id"] for value in mapping["mapping"].values()}
    assert "diagnosis" in profile_ids


def test_repeated_export_keeps_edited_ratings_and_imports_utf8_bom(run_dir):
    export_review_packet(run_dir)
    path = run_dir / "reviews" / "review_packet.csv"
    rows = read_csv(path, delimiter=";")
    rows[0].update(rater_id="expert-1", hilfreichkeit_naechster_schritt="4")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RFC_REVIEW_COLUMNS, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    assert import_review_ratings(run_dir, path)["imported"] == 1
    export_review_packet(run_dir)
    preserved = read_csv(path, delimiter=";")
    assert preserved[0]["rater_id"] == "expert-1"
    assert preserved[0]["hilfreichkeit_naechster_schritt"] == "4"
    assert import_review_ratings(run_dir, path)["imported"] == 0
    original = path.read_bytes()
    with pytest.raises(ValueError, match="entfallen"):
        export_review_packet(run_dir, limit=0)
    assert path.read_bytes() == original


def test_rating_import_rejects_missing_required_headers(run_dir):
    export_review_packet(run_dir)
    path = run_dir / "wrong-header.csv"
    path.write_text("unknown;rater_id\nvalue;expert\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Bewertungsspalten fehlen"):
        import_review_ratings(run_dir, path)


def test_review_import_validates_and_report_aggregates(run_dir):
    exported = export_review_packet(run_dir)
    assert exported["packet_rows"] == 2
    packet_path = run_dir / "reviews" / "review_packet.csv"
    with open(packet_path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    rating_rows = []
    for row, likert in zip(rows, (1, 5)):
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
    write_ratings(ratings_csv, rating_rows)

    imported = import_review_ratings(run_dir, ratings_csv)
    assert imported["imported"] == 2

    # Neu, bereits gespeichert und ungueltig: nur neues Rating zaehlen.
    bad_rows = [
        rating_rows[0],
        {**rating_rows[0], "rater_id": "expert-2"},
        {**rating_rows[1], "hilfreichkeit_naechster_schritt": "99"},
    ]
    bad_csv = run_dir / "bad.csv"
    write_ratings(bad_csv, bad_rows)
    result_bad = import_review_ratings(run_dir, bad_csv)
    assert result_bad["imported"] == result_bad["records"] == 1
    assert result_bad["errors"]
    repeated = import_review_ratings(run_dir, bad_csv)
    assert repeated["imported"] == repeated["records"] == 0
    assert repeated["errors"] == result_bad["errors"]
    # Vollständig ungültige Datei: Importer bricht mit Fehler ab.
    only_bad_csv = run_dir / "only_bad.csv"
    write_ratings(only_bad_csv, [
        {**rating_rows[1], "hilfreichkeit_naechster_schritt": "99"},
    ])
    with pytest.raises(ValueError):
        import_review_ratings(run_dir, only_bad_csv)

    built = build_report(run_dir)
    coverage = built["coverage"]
    # Rohprotokoll zählt Live-Datensätze inkl. fehlgeschlagenem Versuch;
    # Mock (a4) bleibt außen und geht in keine Kennzahlen ein.
    assert coverage["generations_total"] == 3
    assert coverage["generations_live_success"] == 2
    assert coverage["ratings_total"] == 3
    assert coverage["responses_total"] == coverage["responses_with_ratings"] == 2
    assert coverage["responses_missing_ratings"] == 0
    summary_path = run_dir / "derived" / "summary.csv"
    assert summary_path.exists()
    report_text = (run_dir / "derived" / "report.md").read_text(encoding="utf-8")
    assert "Unzulaessig" in report_text
    assert "Keine kompensierende Gesamtnote" in report_text
    assert "| m | base | 1 | loesungsverrat_unzulaessig | 2/2 |" in report_text
    assert "Demonstrationslauf" in report_text  # allow_unverified_cases=true


def test_review_import_deduplicates_rows_and_repeat_import(run_dir):
    export_review_packet(run_dir)
    packet_path = run_dir / "reviews" / "review_packet.csv"
    with open(packet_path, encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter=";"))
    rating_rows = []
    for rater_id in ("expert-1", "expert-2"):
        for index, review_row in enumerate(rows, start=1):
            row = {**review_row, "rater_id": rater_id}
            row["hilfreichkeit_naechster_schritt"] = str(2 + index)
            rating_rows.append(row)
    ratings_csv = run_dir / "double.csv"
    write_ratings(ratings_csv, rating_rows + [
        {**row, "hilfreichkeit_naechster_schritt": "5"} for row in rating_rows
    ])
    result = import_review_ratings(run_dir, ratings_csv)
    assert result["imported"] == result["records"] == 4
    # Doppelimport: Zeilen wurden bereits erfasst → kein Duplikat.
    rerun = import_review_ratings(run_dir, ratings_csv)
    assert rerun["imported"] == rerun["records"] == 0
    ratings_path = run_dir / "reviews" / "ratings.jsonl"
    assert len([
        line for line in ratings_path.read_text(encoding="utf-8")
        .splitlines() if line.strip()
    ]) == 4
    assert [
        record["ratings"]["hilfreichkeit_naechster_schritt"]
        for record in read_jsonl(ratings_path)
    ] == [3, 4, 3, 4]
    coverage = build_report(run_dir)["coverage"]
    assert coverage["attempts_with_ratings"] == 2
    assert coverage["ratings_total"] == 4
    assert coverage["responses_missing_ratings"] == 0


@pytest.mark.parametrize("relative_path", [True, False])
def test_snapshot_export_import_roundtrip_from_other_cwd(
    run_dir: Path, tmp_path: Path, monkeypatch, relative_path: bool,
):
    selected = {"chain-exp-missing-inner-001", "robustness-prompt-injection-001"}
    cases = [
        case.model_dump()
        for case in load_cases(EVAL_DIR / "data" / "example_cases.jsonl")
        if case.case_id in selected
    ]
    snapshot_dir = run_dir / "inputs"
    snapshot_dir.mkdir()
    for index, case in enumerate(cases, start=1):
        case["case_id"] = "fall-" + str(index)
        write_line(snapshot_dir / "cases.jsonl", case)
    policy_path = snapshot_dir / "policy.json"
    policy = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["hint_policy"]
    policy["1"]["goal"] = "Snapshot-Ziel"
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    monkeypatch.setattr(runner, "CODE_DIR", tmp_path)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest.pop("hint_policy")
    manifest["paths"] = {
        "corpus": str((snapshot_dir / "cases.jsonl").relative_to(tmp_path))
        if relative_path else str(snapshot_dir / "cases.jsonl"),
        "policy": str(policy_path.relative_to(tmp_path))
        if relative_path else str(policy_path),
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    template = read_jsonl(run_dir / "generations.jsonl")[0]
    for index, case in enumerate(cases, start=1):
        record = {
            **template, "attempt_id": "snapshot-" + str(index),
            "case_id": case["case_id"],
            "job_id": "job-a" + str(index),
            "request_payload": {"stack": case["tutor_context"]},
            "returned": {**template["returned"], "hint": "LLM behauptet falsche Referenz"},
        }
        write_line(run_dir / "generations.jsonl", record)
    other_cwd = tmp_path / "other-cwd"
    other_cwd.mkdir()
    monkeypatch.chdir(other_cwd)

    exported = export_review_packet(run_dir)
    assert exported["packet_rows"] == 2
    rows = read_csv(Path(exported["path"]), ";")
    for row, case in zip(rows, cases):
        reference = case["evaluation_only"]["reference"]
        assert row["rater_id"] == ""
        assert row["aufgabenstellung"] == case["tutor_context"]["question_text"]
        assert row["studentische_antwort"] == case["tutor_context"]["student_answer"]
        assert row["referenz_endloesung"] == reference["final_answer"]
        assert row["erwarteter_fehlerfall"] == reference["expected_diagnosis"]
        assert row["erwartete_validitaet"] == reference["expected_input_validity"]
        assert row["erwartete_korrektheit"] == reference["expected_correctness"]
        assert row["hilfestufenziel"] == "Snapshot-Ziel"
        assert not any("model" in key or "profil" in key for key in row)
        row.update({"rater_id": "expert-1", "verstaendlichkeit": "4"})
    ratings_csv = run_dir / "snapshot-ratings.csv"
    write_ratings(ratings_csv, rows)
    imported = import_review_ratings(run_dir, ratings_csv)
    assert imported == {"imported": 2, "records": 2, "errors": []}
    assert build_report(run_dir)["coverage"]["responses_with_ratings"] == 2


def test_export_does_not_invent_missing_reference_fields(run_dir: Path):
    template = load_cases(EVAL_DIR / "data" / "example_cases.jsonl")[0].model_dump()
    corpus_path = run_dir / "cases.jsonl"
    for index in (1, 2):
        case = {**template, "case_id": "fall-" + str(index)}
        case["evaluation_only"] = {**template["evaluation_only"], "reference": {}}
        write_line(corpus_path, case)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["paths"] = {"corpus": str(corpus_path)}
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    template_generation = read_jsonl(run_dir / "generations.jsonl")[0]
    for index in (1, 2):
        write_line(run_dir / "generations.jsonl", {
            **template_generation, "attempt_id": "ref-" + str(index),
            "job_id": "job-a" + str(index), "case_id": "fall-" + str(index),
            "request_payload": {"stack": {
                "final_answer": "Nicht als Referenz verwenden",
                "diagnosis_code": "LLM-oder-Request-Diagnose",
            }},
        })
    rows = read_csv(Path(export_review_packet(run_dir)["path"]), ";")
    assert all(
        row[field] == "" for row in rows
        for field in ("referenz_endloesung", "erwarteter_fehlerfall",
                      "erwartete_validitaet", "erwartete_korrektheit")
    )
    manifest["paths"]["corpus"] = str(run_dir / "missing-corpus.jsonl")
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="Korpusdatei nicht gefunden"):
        export_review_packet(run_dir)
    manifest["paths"]["corpus"] = str(corpus_path)
    (run_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    write_line(run_dir / "generations.jsonl", {
        **template_generation, "attempt_id": "missing-case", "job_id": "missing-case",
        "case_id": "not-in-snapshot",
    })
    with pytest.raises(ValueError, match="Fall fehlt im Laufkorpus"):
        export_review_packet(run_dir)


def test_blank_rows_and_partial_ratings_keep_missing_values(run_dir: Path):
    export_review_packet(run_dir)
    packet_path = run_dir / "reviews" / "review_packet.csv"
    assert import_review_ratings(run_dir, packet_path) == {
        "imported": 0, "records": 0, "errors": [],
    }
    assert not (run_dir / "reviews" / "ratings.jsonl").exists()
    rows = read_csv(packet_path, ";")
    rows[0].update({
        "rater_id": "expert-1", "begruendung": "Nur Kommentar, kein Rating",
        "passung_fehler": "n_a",
    })
    rows[1].update({
        "rater_id": "expert-1", "verstaendlichkeit": "4", "passung_fehler": "n_a",
    })
    ratings_csv = run_dir / "partial.csv"
    write_ratings(ratings_csv, rows)
    assert import_review_ratings(run_dir, ratings_csv)["imported"] == 1
    saved = read_jsonl(run_dir / "reviews" / "ratings.jsonl")
    assert len(saved) == 1
    assert saved[0]["ratings"] == {
        **dict.fromkeys(LIKERT_FIELDS + CHOICE_FIELDS), "verstaendlichkeit": 4,
    }
    coverage = build_report(run_dir)["coverage"]
    assert coverage["ratings_total"] == coverage["responses_with_ratings"] == 1
    assert coverage["responses_missing_ratings"] == 1
    summary = {row["profile_id"]: row for row in read_csv(run_dir / "derived" / "summary.csv")}
    assert summary["base"]["n_missing_ratings"] == "1"
    assert summary["diagnosis"]["rating_mat_falsch_fehlend_n"] == "1"
    assert summary["diagnosis"]["rating_mat_falsch_N"] == "1"
    assert summary["diagnosis"]["rating_passung_fehler_n"] == "0"
    text = (run_dir / "derived" / "report.md").read_text(encoding="utf-8")
    assert "Bewertete Antworten: 1/2; Antworten ohne Ratings: 1" in text


@pytest.mark.parametrize("field,value", [
    ("passung_fehler", "1"), ("hilfreichkeit_naechster_schritt", "2"),
    ("mat_falsch", "ja"), ("widerspruch_pruefergebnis", "ja"),
    ("erfundene_diagnose", "ja"), ("stufe_angemessen", "nein"),
    ("loesungsverrat_unzulaessig", "ja"),
])
def test_negative_or_low_rating_requires_reason(run_dir: Path, field: str, value: str):
    row = read_csv(Path(export_review_packet(run_dir)["path"]), ";")[0]
    row.update({"rater_id": "expert-1", field: value, "begruendung": "   "})
    ratings_csv = run_dir / "negative.csv"
    write_ratings(ratings_csv, [row])
    with pytest.raises(ValueError, match="begruendung fehlt"):
        import_review_ratings(run_dir, ratings_csv)
    assert not (run_dir / "reviews" / "ratings.jsonl").exists()
    row["begruendung"] = "Textbeleg aus dem Hinweis"
    write_ratings(ratings_csv, [row])
    assert import_review_ratings(run_dir, ratings_csv)["imported"] == 1


def test_allowed_solution_and_nonnegative_choices_need_no_reason(run_dir: Path):
    template = read_jsonl(run_dir / "generations.jsonl")[0]
    write_line(run_dir / "generations.jsonl", {
        **template, "attempt_id": "level4", "job_id": "level4", "hint_level": 4,
    })
    rows = read_csv(Path(export_review_packet(run_dir)["path"]), ";")
    row = next(row for row in rows if row["hilfestufe"] == "4")
    row.update({
        "rater_id": "expert-1", "mat_falsch": "nein", "stufe_angemessen": "ja",
        "widerspruch_pruefergebnis": "nicht_anwendbar", "erfundene_diagnose": "unklar",
        "loesung_vollstaendig": "ja", "loesungsverrat_unzulaessig": "nein",
    })
    ratings_csv = run_dir / "allowed.csv"
    write_ratings(ratings_csv, [row])
    assert import_review_ratings(run_dir, ratings_csv)["imported"] == 1
    write_line(run_dir / "checks.jsonl", {
        "attempt_id": "level4", "check_id": "final_answer_disclosure",
        "status": "pass", "evidence": {"present": True, "allowed_at_level": True},
    })
    build_report(run_dir)
    level4 = next(
        row for row in read_csv(run_dir / "derived" / "summary.csv")
        if row["hint_level"] == "4"
    )
    assert level4["complete_solution_present"] == "1"
    assert level4["prohibited_disclosure"] == "0"


def test_reporting_separates_uncertainty_choices_and_excludes_demo(run_dir: Path):
    export_review_packet(run_dir)
    rows = read_csv(run_dir / "reviews" / "review_packet.csv", ";")
    ratings_csv = run_dir / "choices.csv"
    rating_rows = []
    for index, value in enumerate(("ja", "nein", "unklar", "nicht_anwendbar", "")):
        rating_rows.append({
            **rows[0], "rater_id": "expert-" + str(index), "mat_falsch": value,
            "verstaendlichkeit": "4", "begruendung": "Textbeleg" if value == "ja" else "",
        })
    write_ratings(ratings_csv, rating_rows)
    assert import_review_ratings(run_dir, ratings_csv)["imported"] == 5
    write_line(run_dir / "checks.jsonl", {
        "attempt_id": "a2", "check_id": "final_answer_disclosure",
        "status": "inconclusive", "evidence": {"present": True},
    })
    before = build_report(run_dir)
    before_summary = (run_dir / "derived" / "summary.csv").read_text(encoding="utf-8")
    before_report = (run_dir / "derived" / "report.md").read_text(encoding="utf-8")
    records = read_jsonl(run_dir / "generations.jsonl")
    demo = {
        **records[0], "attempt_id": "demo", "execution_source": "offline_demo",
        "returned": {**records[0]["returned"], "model": "demo-model"},
        "duration_ms": 999999,
    }
    write_line(run_dir / "generations.jsonl", demo)
    for attempt in ("a4", "demo", "unknown-attempt"):
        write_line(run_dir / "checks.jsonl", {
            "attempt_id": attempt, "check_id": "final_answer_disclosure",
            "status": "fail", "evidence": {"present": True},
        })
    # Auch bereits gespeicherte Alt-Duplikate und leere Ratings bleiben draussen.
    saved = read_jsonl(run_dir / "reviews" / "ratings.jsonl")[0]
    write_line(run_dir / "reviews" / "ratings.jsonl", saved)
    for attempt in ("a4", "demo", "unknown-attempt", "a3"):
        write_line(run_dir / "reviews" / "ratings.jsonl", {
            **saved, "attempt_id": attempt, "review_id": "R-" + attempt,
        })
    write_line(run_dir / "reviews" / "ratings.jsonl", {
        **saved, "attempt_id": "a2", "review_id": rows[1]["review_id"],
        "ratings": dict.fromkeys(LIKERT_FIELDS + CHOICE_FIELDS),
    })
    after = build_report(run_dir)
    assert after["coverage"] == before["coverage"]
    assert after["coverage"]["checks_total"] == 3
    assert after["coverage"]["ratings_total"] == 5
    assert after["coverage"]["responses_with_ratings"] == 1
    assert (run_dir / "derived" / "summary.csv").read_text(encoding="utf-8") == before_summary
    assert (run_dir / "derived" / "report.md").read_text(encoding="utf-8") == before_report
    summary = {row["profile_id"]: row for row in read_csv(run_dir / "derived" / "summary.csv")}
    assert summary["diagnosis"]["disclosure_inconclusive"] == "1"
    assert summary["diagnosis"]["complete_solution_present"] == "0"
    assert summary["diagnosis"]["prohibited_disclosure"] == "0"
    for value in ("ja", "nein", "unklar", "nicht_anwendbar", "fehlend"):
        assert summary["base"]["rating_mat_falsch_" + value + "_n"] == "1"
    assert summary["base"]["rating_mat_falsch_N"] == "5"
    text = (run_dir / "derived" / "report.md").read_text(encoding="utf-8")
    assert "| m | base | 1 | mat_falsch | 1/5 | 1/5 | 1/5 | 1/5 | 1/5 |" in text
    assert "inconclusive" in text
    assert "demo-model" not in text
    assert export_review_packet(run_dir)["packet_rows"] == 2
    # Ein fremder Mapping-Eintrag darf keine Demo importierbar machen.
    mapping_path = run_dir / "reviews" / "review_mapping.json"
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    mapping["mapping"]["R-demo"] = {"attempt_id": "demo"}
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    # Gespeicherte Demo-Ratings duerfen auch keine echte Bewertung blockieren.
    write_line(run_dir / "reviews" / "ratings.jsonl", {
        **saved, "attempt_id": "demo", "review_id": rows[1]["review_id"],
    })
    live_row = {**rows[1], "rater_id": saved["rater_id"], "verstaendlichkeit": "4"}
    write_ratings(ratings_csv, [live_row, {**live_row, "review_id": "R-demo"}])
    imported = import_review_ratings(run_dir, ratings_csv)
    assert imported["imported"] == imported["records"] == 1
    assert len(imported["errors"]) == 1
    assert "kein aktueller erfolgreicher Live-Versuch" in imported["errors"][0]


def test_retry_result_is_one_answer_and_stale_mapping_cannot_import(run_dir: Path):
    exported = export_review_packet(run_dir)
    rows = read_csv(Path(exported["path"]), ";")
    rows[0].update({"rater_id": "expert-1", "hilfreichkeit_naechster_schritt": "5"})
    rows[1].update({"rater_id": "expert-1", "hilfreichkeit_naechster_schritt": "4"})
    ratings_csv = run_dir / "initial.csv"
    write_ratings(ratings_csv, rows)
    assert import_review_ratings(run_dir, ratings_csv)["imported"] == 2
    records = read_jsonl(run_dir / "generations.jsonl")
    for attempt, outcome, returned in (
        ("a1-failed", "server_error", None),
        ("a1-retry", "success", {**records[0]["returned"], "hint": "Neuer Hinweis"}),
        ("a1-late-failure", "server_error", None),
    ):
        write_line(run_dir / "generations.jsonl", {
            **records[0], "attempt_id": attempt, "outcome": outcome, "returned": returned,
            "retry_of_attempt_id": "a1",
        })
    write_line(run_dir / "generations.jsonl", {
        **records[2], "attempt_id": "a3-retry", "outcome": "success",
        "returned": {**records[0]["returned"], "hint": "Erfolg nach Fehler"},
        "retry_of_attempt_id": "a3",
    })
    write_line(run_dir / "checks.jsonl", {
        "attempt_id": "a1-retry", "check_id": "final_answer_disclosure",
        "status": "inconclusive", "evidence": {"present": True},
    })
    write_ratings(ratings_csv, [rows[0]])
    with pytest.raises(ValueError, match="kein aktueller erfolgreicher Live-Versuch"):
        import_review_ratings(run_dir, ratings_csv)
    assert export_review_packet(run_dir)["packet_rows"] == 3
    mapping = json.loads((run_dir / "reviews" / "review_mapping.json").read_text(encoding="utf-8"))["mapping"]
    assert {value["attempt_id"] for value in mapping.values()} == {"a1-retry", "a2", "a3-retry"}
    built = build_report(run_dir)
    assert built["coverage"]["generations_total"] == 7
    assert built["coverage"]["generations_live_success"] == 4
    assert built["coverage"]["responses_total"] == 3
    assert built["coverage"]["ratings_total"] == 1
    assert built["coverage"]["responses_missing_ratings"] == 2
    base = next(row for row in read_csv(run_dir / "derived" / "summary.csv") if row["profile_id"] == "base")
    assert base["n_success"] == "2"
    assert base["check_failures"] == base["complete_solution_present"] == "0"
    assert base["disclosure_inconclusive"] == "1"
    assert base["disclosure_missing"] == "1"


def test_pairing_and_summary_do_not_mix_models_cases_levels_or_repetitions(run_dir: Path):
    template = read_jsonl(run_dir / "generations.jsonl")[0]
    cells = [
        ("m2-base", "fall-a", "base", 1, 1, "m", "m2", "5"),
        ("m2-diagnosis", "fall-a", "diagnosis", 1, 1, "m", "m2", "3"),
        ("m3-only", "fall-a", "diagnosis", 1, 1, "m3", "m3", "3"),
        ("other-case", "fall-b", "diagnosis", 1, 1, "m", None, "3"),
        ("other-level", "fall-a", "diagnosis", 2, 1, "m", None, "3"),
        ("other-repeat", "fall-a", "diagnosis", 1, 2, "m", None, "3"),
    ]
    scores = {"a1": "3", "a2": "4"}
    for attempt, case, profile, level, repetition, model, requested, score in cells:
        write_line(run_dir / "generations.jsonl", {
            **template, "attempt_id": attempt, "job_id": "job-" + attempt,
            "case_id": case, "profile_id": profile, "hint_level": level,
            "repetition": repetition, "requested_model": requested,
            "returned": {**template["returned"], "model": model},
        })
        scores[attempt] = score
    rows = read_csv(Path(export_review_packet(run_dir)["path"]), ";")
    mapping = json.loads((run_dir / "reviews" / "review_mapping.json").read_text(encoding="utf-8"))["mapping"]
    for row in rows:
        row.update({
            "rater_id": "expert-1",
            "hilfreichkeit_naechster_schritt": scores[mapping[row["review_id"]]["attempt_id"]],
        })
    ratings_csv = run_dir / "multi-model.csv"
    write_ratings(ratings_csv, rows)
    assert import_review_ratings(run_dir, ratings_csv)["imported"] == 8
    assert build_report(run_dir)["paired_rows"] == 2
    pairs = read_csv(run_dir / "derived" / "paired_comparisons.csv")
    assert {row["model"]: float(row["delta"]) for row in pairs} == {"m": 1.0, "m2": -2.0}
    assert all(
        (row["case_id"], row["hint_level"], row["repetition"]) == ("fall-a", "1", "1")
        for row in pairs
    )
    summary = read_csv(run_dir / "derived" / "summary.csv")
    assert {row["model"] for row in summary} == {"m", "m2", "m3"}
    assert all(row["n_success"] == "1" for row in summary if row["profile_id"] == "base")
