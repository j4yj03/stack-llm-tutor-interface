"""Offline preparation and demonstration for the notebook testbench.

Live requests remain the responsibility of Runner. Demonstration answers are
hand-written fixtures, never LLM outputs or mathematical assessments.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

from evaluation.corpus import (
    case_profile_eligible,
    load_cases,
    load_profiles,
    sha256_json,
    validate_experiment,
)
from evaluation.models import ContextProfile, ContextProfileSet, Experiment
from evaluation.runner import (
    GENERATIONS_FILE,
    POLICY_PATH,
    RunnerError,
    create_run,
    load_manifest,
    load_plan,
    utc_now_iso,
    verify_manifest,
)


def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def prepare_run(
    run_dir: Path,
    corpus_path: Path,
    profiles_path: Path,
    case_ids: List[str],
    profile_ids: List[str],
    custom_flags: Dict[str, bool],
    hint_levels: List[int],
    model: Optional[str],
    mode: str,
    base_url: str,
    repetitions: int = 1,
    max_generations_per_hour: int = 35,
    order_seed: int = 20261002,
    allow_unverified_cases: bool = True,
    http_timeout: float = 420.0,
) -> dict:
    """Freeze a selected corpus and context configuration without networking.

    Re-execution can reuse an identical run but cannot overwrite or silently
    change it. Empty case_ids selects the entire supplied corpus.
    """
    if mode not in {"demo", "live"}:
        raise ValueError("Planung erfordert mode='demo' oder 'live'.")
    if mode == "live" and (not model or not model.strip()):
        raise ValueError("Fuer Live-Laeufe MODEL explizit aus der Allowlist setzen.")
    cases = load_cases(corpus_path)
    unknown = set(case_ids) - {case.case_id for case in cases}
    if unknown:
        raise ValueError("Unbekannte case_ids: " + ", ".join(sorted(unknown)))
    selected = sorted(
        [case for case in cases if not case_ids or case.case_id in case_ids],
        key=lambda case: case.case_id,
    )
    available = load_profiles(profiles_path).by_id()
    if "custom" in profile_ids:
        available["custom"] = ContextProfile(
            profile_id="custom",
            description="Im Notebook festgelegter Kontext.",
            **custom_flags,
        )
    unknown = set(profile_ids) - set(available)
    if unknown:
        raise ValueError("Unbekannte Profile: " + ", ".join(sorted(unknown)))
    profiles = ContextProfileSet(
        schema_version="1.0",
        profiles=[available[key] for key in sorted(set(profile_ids))],
    )
    if any(profile.include_chat_history for profile in profiles.profiles):
        raise ValueError("Frische Einzel-Chats haben keine Historie; Flag ausschalten.")
    inputs_dir = run_dir.resolve() / "inputs"
    experiment = Experiment(
        schema_version="1.0",
        experiment_id="notebook-context-v1",
        protocol_version="eval-protocol-1",
        description="Notebook-Kontextvergleich; synthetische Faelle nur als Pilot.",
        corpus_file=str(inputs_dir / "cases.jsonl"),
        profiles=sorted(set(profile_ids)),
        hint_levels=hint_levels,
        repetitions=repetitions,
        models=[model] if model else [],
        max_generations_per_hour=max_generations_per_hour,
        order_seed=order_seed,
        allow_unverified_cases=allow_unverified_cases,
    )
    errors = validate_experiment(experiment, selected, profiles)
    if errors:
        raise ValueError("\n".join(errors))
    # Check eligibility before writing a directory with no executable jobs.
    if not any(
        case_profile_eligible(case, profile, allow_unverified_cases) is None
        for case in selected for profile in profiles.profiles
    ):
        raise ValueError("Keine geeigneten Jobs; Fallverifizierung und Profile pruefen.")
    configuration = {
        "cases": [case.model_dump() for case in selected],
        "profiles": profiles.model_dump(),
        "experiment": experiment.model_dump(),
        "mode": mode,
        "base_url": base_url,
        "http_timeout": http_timeout,
    }
    fingerprint = sha256_json(configuration)
    if run_dir.exists() and any(run_dir.iterdir()):
        manifest = load_manifest(run_dir)
        if manifest.get("notebook_configuration_sha256") != fingerprint:
            raise RunnerError("Konfiguration geaendert; einen neuen RUN_ID verwenden.")
        verify_manifest(run_dir, manifest)
        return manifest

    inputs_dir.mkdir(parents=True, exist_ok=True)
    corpus_snapshot = inputs_dir / "cases.jsonl"
    corpus_snapshot.write_text(
        "".join(case.model_dump_json() + "\n" for case in selected),
        encoding="utf-8",
    )
    profiles_snapshot = inputs_dir / "profiles.json"
    profiles_snapshot.write_text(profiles.model_dump_json(indent=2), encoding="utf-8")
    experiment_snapshot = inputs_dir / "experiment.json"
    experiment_snapshot.write_text(experiment.model_dump_json(indent=2), encoding="utf-8")
    manifest = create_run(
        run_dir=run_dir,
        experiment_path=experiment_snapshot,
        corpus_path=corpus_snapshot,
        profiles_path=profiles_snapshot,
        base_url=base_url,
        http_timeout=http_timeout,
    )
    manifest["execution_mode"] = "offline_demo" if mode == "demo" else "live_tutor_api"
    manifest["notebook_configuration_sha256"] = fingerprint
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return manifest


def preview_messages(payload: dict) -> List[Dict[str, str]]:
    """Local pre-request preview, not a reconstruction of a returned prompt.

    Imports only pure prompt/schema modules, never app.main or the LLM client.
    All context flags are explicit, so environment defaults do not select them.
    """
    from app.hint_policy import HintPolicy
    from app.prompt_builder import PromptBuilder
    from app.schemas import ContextOptions, StackContext

    return PromptBuilder(HintPolicy(path=POLICY_PATH)).build_messages(
        stack=StackContext(**payload["stack"]),
        hint_level=payload["hint_level"],
        options=ContextOptions(**payload["context_options"]),
        history=[],
    )


def write_demo_results(run_dir: Path) -> List[dict]:
    """Persist visibly labelled hand-written outputs, without network or DB.

    One deliberately disclosing answer exercises the disclosure check. No
    response times, human ratings or model performance are fabricated.
    """
    manifest = load_manifest(run_dir)
    if manifest.get("execution_mode") != "offline_demo":
        raise RunnerError("Demoausgaben duerfen nur in einem Demolauf gespeichert werden.")
    verify_manifest(run_dir, manifest)
    results_path = run_dir / GENERATIONS_FILE
    if results_path.exists():
        records = read_jsonl(results_path)
        if any(record.get("execution_source") != "offline_demo" for record in records):
            raise RunnerError("Demolauf enthaelt andere Daten; kein Ueberschreiben.")
        return records
    jobs = load_plan(run_dir)
    from evaluation.runner import CODE_DIR

    cases = {
        case.case_id: case
        for case in load_cases(CODE_DIR / manifest["paths"]["corpus"])
    }
    disclosure_job = next(
        (job["job_id"] for job in jobs
         if not manifest["hint_policy"][str(job["hint_level"])]["include_final_answer"]),
        None,
    )
    records = []
    for job in jobs:
        case = cases[job["case_id"]]
        payload = job["request_payload"]
        if job["job_id"] == disclosure_job:
            hint = (
                "Absichtlich zu ausfuehrliche Demoantwort (kein LLM): "
                + (case.evaluation_only.reference.final_answer or "Keine Referenz.")
            )
        elif payload["stack"].get("prt_feedback"):
            hint = (
                "Handgeschriebene Demoantwort (kein LLM): "
                + payload["stack"]["prt_feedback"]
                + " Welche Regel hilft dir beim naechsten eigenen Schritt?"
            )
        else:
            hint = (
                "Handgeschriebene Demoantwort (kein LLM): "
                "Betrachte den Aufbau der Funktion. Welche Ableitungsregel "
                "passt zu dieser Struktur?"
            )
        timestamp = utc_now_iso()
        records.append({
            "schema_version": "1.0",
            "run_id": manifest["run_id"],
            "attempt_id": "demo-" + job["job_id"],
            "job_id": job["job_id"],
            "execution_source": "offline_demo",
            "case_id": job["case_id"],
            "task_instance_id": case.task_instance_id,
            "profile_id": job["profile_id"],
            "hint_level": job["hint_level"],
            "requested_model": job.get("model"),
            "repetition": job["repetition"],
            "request_payload": payload,
            "request_sha256": job["request_sha256"],
            "started_at_utc": timestamp,
            "finished_at_utc": timestamp,
            "duration_ms": None,
            "outcome": "success",
            "tutor_http_status": None,
            "returned": {
                "chat_id": None,
                "question_id": payload["stack"]["question_id"],
                "hint_level": job["hint_level"],
                "model": "offline-demo-kein-llm",
                "hint": hint,
                "prompt_messages": preview_messages(payload),
                "context_options": payload["context_options"],
            },
            "safe_error": None,
            "retry_of_attempt_id": None,
        })
    results_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return records
