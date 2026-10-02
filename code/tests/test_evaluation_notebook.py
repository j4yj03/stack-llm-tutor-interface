"""Notebook preparation, offline demo and mocked live workflow."""

import json

import pytest

from evaluation import runner as runner_module
from evaluation.checks import run_checks_for_run
from evaluation.corpus import load_cases, load_profiles
from evaluation.models import PROFILE_FLAG_NAMES
from evaluation.notebook import (
    prepare_run,
    preview_messages,
    read_jsonl,
    write_demo_results,
)
from evaluation.report import build_report, export_review_packet
from evaluation.runner import CODE_DIR, Runner, RunnerError, load_plan

EVAL_DIR = CODE_DIR / "evaluation"
NOTEBOOK_PATH = EVAL_DIR / "notebooks" / "testbench.ipynb"


@pytest.fixture
def run_options(tmp_path):
    flags = {name: False for name in PROFILE_FLAG_NAMES}
    flags.update(include_question_text=True, include_student_answer=True)
    return {
        "run_dir": tmp_path / "demo-001",
        "corpus_path": EVAL_DIR / "data" / "example_cases.jsonl",
        "profiles_path": EVAL_DIR / "data" / "context_profiles.json",
        "case_ids": ["chain-exp-missing-inner-001", "prod-missing-term-002"],
        "profile_ids": ["base", "custom"],
        "custom_flags": flags,
        "hint_levels": [1, 3],
        "model": None,
        "mode": "demo",
        "base_url": "http://tutor.test",
    }


def test_plan_freezes_selected_inputs_and_rejects_changed_configuration(run_options):
    manifest = prepare_run(**run_options)
    run_dir = run_options["run_dir"]
    assert manifest["execution_mode"] == "offline_demo"
    assert manifest["counts"]["jobs"] == 8
    assert len(load_cases(CODE_DIR / manifest["paths"]["corpus"])) == 2
    assert len(load_profiles(CODE_DIR / manifest["paths"]["profiles"]).profiles) == 2
    assert prepare_run(**run_options) == manifest
    original_plan = (run_dir / "plan.jsonl").read_bytes()
    with pytest.raises(RunnerError, match="Konfiguration geaendert"):
        prepare_run(**{**run_options, "hint_levels": [4]})
    assert (run_dir / "plan.jsonl").read_bytes() == original_plan
    assert not (run_dir / "generations.jsonl").exists()


@pytest.mark.parametrize("changes", [
    {"mode": "invalid"},
    {"mode": "live", "model": None},
    {"case_ids": ["unknown-case"]},
    {"profile_ids": ["unknown-profile"]},
    {"profile_ids": []},
    {"hint_levels": []},
    {"allow_unverified_cases": False},
])
def test_invalid_selection_writes_no_run(run_options, changes):
    with pytest.raises(ValueError):
        prepare_run(**{**run_options, **changes})
    assert not run_options["run_dir"].exists()


def test_empty_case_filter_selects_all_and_history_is_rejected(run_options):
    manifest = prepare_run(**{**run_options, "case_ids": []})
    assert manifest["counts"]["cases"] == 12
    flags = {**run_options["custom_flags"], "include_chat_history": True}
    with pytest.raises(ValueError, match="Historie"):
        prepare_run(**{**run_options, "custom_flags": flags})


def test_demo_checks_are_visible_but_excluded_from_quality_reporting(
    run_options, monkeypatch,
):
    import requests

    def forbid_network(*args, **kwargs):
        pytest.fail("Offline demo must not make a network request")

    monkeypatch.setattr(requests.sessions.Session, "request", forbid_network)
    prepare_run(**run_options)
    run_dir = run_options["run_dir"]
    records = write_demo_results(run_dir)
    assert write_demo_results(run_dir) == records
    assert len(records) == 8
    assert all(record["execution_source"] == "offline_demo" for record in records)
    assert all(record["duration_ms"] is None for record in records)
    assert all(record["returned"]["model"] == "offline-demo-kein-llm" for record in records)
    run_checks_for_run(run_dir)
    assert any(
        check["check_id"] == "final_answer_disclosure" and check["status"] == "fail"
        for check in read_jsonl(run_dir / "checks.jsonl")
    )
    assert export_review_packet(run_dir)["packet_rows"] == 0
    report = build_report(run_dir)
    assert report["coverage"]["generations_total"] == 0
    assert report["coverage"]["checks_total"] == 0
    with pytest.raises(RunnerError, match="Demolauf"):
        Runner(run_dir).run(execute_live=True)


def test_preview_uses_the_real_double_guard(run_options):
    prepare_run(**{**run_options, "profile_ids": ["solution"], "hint_levels": [1, 3, 4]})
    for job in load_plan(run_options["run_dir"]):
        payload = job["request_payload"]
        assert payload["stack"]["final_answer"]
        messages = preview_messages(payload)
        user_content = messages[-1]["content"]
        assert ("MUSTERL\u00d6SUNG" in user_content) == (job["hint_level"] == 4)
        assert ("L\u00d6SUNGSSCHRITTE" in user_content) == (job["hint_level"] >= 3)


def test_demo_cannot_overwrite_live_run(run_options):
    prepare_run(**{**run_options, "mode": "live", "model": "test-model"})
    with pytest.raises(RunnerError, match="Demolauf"):
        write_demo_results(run_options["run_dir"])
    assert not (run_options["run_dir"] / "generations.jsonl").exists()


def execute_cells(monkeypatch, tmp_path, overrides=None):
    """Execute trusted repository cells; notebook dependencies stay optional."""
    pytest.importorskip("pandas")
    pytest.importorskip("ipywidgets")
    matplotlib = pytest.importorskip("matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    monkeypatch.setattr(plt, "show", lambda: plt.close("all"))
    monkeypatch.setenv("TUTOR_EVALUATION_RUNS", str(tmp_path))
    monkeypatch.chdir(NOTEBOOK_PATH.parent)
    document = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    namespace = {"__name__": "__main__"}
    for cell in document["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = cell["source"]
        source = source if isinstance(source, str) else "".join(source)
        exec(compile(source, str(NOTEBOOK_PATH) + "#" + cell["id"], "exec"), namespace)
        if cell["id"] == "configuration" and overrides:
            namespace.update(overrides)
            namespace["run_dir"] = namespace["RUN_ROOT"] / namespace["RUN_ID"]
    return namespace, document


def test_notebook_run_all_is_offline_from_its_own_directory(monkeypatch, tmp_path):
    import requests

    def forbid_network(*args, **kwargs):
        pytest.fail("Default notebook execution must remain offline")

    monkeypatch.setattr(requests.sessions.Session, "request", forbid_network)
    namespace, document = execute_cells(monkeypatch, tmp_path)
    assert namespace["MODE"] == "demo"
    assert len(namespace["generations"]) == 24
    assert len(namespace["result_df"]) == 24
    assert namespace["report_result"]["coverage"]["responses_total"] == 0
    assert (namespace["derived_dir"] / "automatic_checks.png").is_file()
    assert (namespace["derived_dir"] / "ausgaben.csv").is_file()
    assert namespace["review_rows"] == []
    assert all(cell.get("outputs", []) == [] for cell in document["cells"])
    assert all(cell.get("execution_count") is None for cell in document["cells"])


def test_analysis_uses_snapshots_instead_of_original_files(monkeypatch, tmp_path):
    execute_cells(monkeypatch, tmp_path)
    namespace, _ = execute_cells(monkeypatch, tmp_path, {
        "MODE": "analyze", "CORPUS_FILE": tmp_path / "missing-corpus.jsonl",
        "PROFILES_FILE": tmp_path / "missing-profiles.json", "CASE_IDS": ["gone-case"],
        "PROFILE_IDS": ["gone-profile"],
    })
    assert len(namespace["generations"]) == 24
    assert namespace["is_demo"] is True
    assert namespace["case_selector"].disabled


def test_mocked_live_notebook_supports_ratings_and_paired_analysis(monkeypatch, tmp_path):
    calls = []

    def transport(method, url, payload, timeout):
        if method == "GET":
            return 200, {"default_model": "test-model", "tasks_loaded": 2}, None, ""
        calls.append(payload)
        return 200, {
            "chat_id": "mock-chat-" + str(len(calls)),
            "question_id": payload["stack"]["question_id"],
            "hint_level": payload["hint_level"],
            "model": payload["model"],
            "hint": "Welche Ableitungsregel hilft dir bei diesem eigenen Schritt?",
            "context_options": payload["context_options"],
            "prompt_messages": preview_messages(payload),
        }, None, ""

    monkeypatch.setattr(runner_module, "_request_transport", transport)
    namespace, document = execute_cells(monkeypatch, tmp_path, {
        "MODE": "live", "MODEL": "test-model", "EXECUTE_LIVE": True, "RUN_ID": "mock-live-001",
    })
    assert len(calls) == len(namespace["review_rows"]) == 24
    assert namespace["report_result"]["coverage"]["responses_missing_ratings"] == 24
    mapping = json.loads(
        (namespace["run_dir"] / "reviews" / "review_mapping.json").read_text(encoding="utf-8")
    )["mapping"]
    for profile_id, value in [("base", "3"), ("custom", "5")]:
        review_id = next(
            key for key, item in mapping.items()
            if item["case_id"] == "chain-exp-missing-inner-001"
            and item["hint_level"] == 1 and item["profile_id"] == profile_id
        )
        namespace["review_selector"].value = review_id
        namespace["rater_field"].value = "expert-1"
        namespace["rating_fields"]["hilfreichkeit_naechster_schritt"].value = value
        namespace["save_button"].click()
    for cell in document["cells"]:
        if cell["id"] in {"report", "rating-plot"}:
            exec("".join(cell["source"]), namespace)
    assert namespace["report_result"]["coverage"]["responses_with_ratings"] == 2
    assert len(namespace["paired_df"]) == 1
    assert namespace["paired_df"]["delta"].iloc[0] == 2
    assert (namespace["derived_dir"] / "ratings.png").is_file()
