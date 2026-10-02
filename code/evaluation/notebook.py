"""Offline preparation and demonstration for the notebook testbench.

Live requests remain the responsibility of Runner. Demonstration answers are
hand-written fixtures, never LLM outputs or mathematical assessments.
"""

import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import urlsplit

from evaluation import runner
from evaluation.corpus import (
    case_profile_eligible,
    load_cases,
    load_profiles,
    sha256_file,
    sha256_json,
    validate_experiment,
    validate_public_configuration,
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
from evaluation.task_cases import DEFAULT_SCHEMA_PATH, cases_from_tasks, task_source_hashes


def read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _configuration_snapshot(value: dict) -> dict:
    public = validate_public_configuration(value)
    if {"rule_id", "judge_model", "judge_parameters"} <= set(value):
        from evaluation.judge import _checked_configuration

        public = _checked_configuration({
            **public, **{key: value[key] for key in ("rule_id", "judge_model", "judge_parameters")},
        })
    token = os.getenv("TUTOR_EVALUATION_TOKEN", "")
    if token and token in json.dumps(public, ensure_ascii=False):
        raise RunnerError("Evaluation credentials cannot enter a public notebook snapshot")
    return public


def load_expected_configuration(path: Path) -> dict:
    """Read a validated, credential-free public configuration offline."""
    return _configuration_snapshot(json.loads(Path(path).read_text(encoding="utf-8")))


def fetch_server_configuration(
    base_url: str,
    *,
    mode: str,
    fetch: bool = False,
    http_timeout: float = 420.0,
    transport: Optional[Callable] = None,
) -> Optional[dict]:
    """Explicit read gate, independent of generation; never fetch in demo/analyze.

    The Runner transport supplies X-Evaluation-Token from the local environment.
    No credential, transport error text or arbitrary response field is returned.
    """
    if not fetch or mode != "live":
        return None
    parsed = urlsplit(base_url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise RunnerError("Tutor URL must not contain credentials, query or fragment")
    try:
        status, body, error, _detail = (transport or runner._request_transport)(
            "GET", base_url.rstrip("/") + "/api/evaluation/config", None, http_timeout,
        )
    except Exception:
        raise RunnerError("Protected configuration read failed; no transport details retained") from None
    if status != 200 or error is not None:
        raise RunnerError("Protected configuration read failed (HTTP " + str(status) + ")")
    try:
        return _configuration_snapshot(body)
    except (ValueError, TypeError, RunnerError):
        raise RunnerError("Invalid public configuration response") from None


def verify_notebook_inputs(run_dir: Path, manifest: Optional[dict] = None) -> dict:
    """Verify suite identity and frozen notebook inputs, never original task paths."""
    run_dir = Path(run_dir).resolve()
    manifest = manifest if manifest is not None else load_manifest(run_dir)
    verify_manifest(run_dir, manifest)
    hashes = manifest.get("notebook_input_hashes") or {}
    if hashes and sha256_json(hashes) != manifest.get("notebook_inputs_sha256"):
        raise RunnerError("Notebook input snapshot identity changed")
    for relative, digest in hashes.items():
        path = (run_dir / relative).resolve()
        if (not path.is_relative_to(run_dir / "inputs") or not path.is_file()
                or sha256_file(path) != digest):
            raise RunnerError("Frozen notebook input changed: " + relative)
    expected_path = run_dir / "inputs" / "expected_configuration.json"
    if "inputs/expected_configuration.json" in hashes and load_expected_configuration(expected_path) != manifest.get("expected_configuration"):
        raise RunnerError("Expected notebook configuration differs from its frozen snapshot")
    return manifest


def prepare_run(
    run_dir: Path,
    corpus_path: Optional[Path],
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
    tasks_dir: Optional[Path] = None,
    condition_id: str = "default",
    expected_config: Optional[dict] = None,
    level_mode: str = "direct",
    use_server_context: bool = False,
    interaction_script: Optional[List[dict]] = None,
    request_budget_units_per_hour: int = 80,
    allow_task_derived_cases: bool = False,
    task_schema_path: Optional[Path] = None,
) -> dict:
    """Freeze a selected corpus and context configuration without networking.

    Re-execution can reuse an identical run but cannot overwrite or silently
    change it. tasks_dir selects authored examples instead of corpus_path; all
    selected source tasks and their schema are frozen. Empty case_ids selects all.
    The legacy JSONL/positional interface stays available for shipped callers.
    """
    if mode not in {"demo", "live"}:
        raise ValueError("Planung erfordert mode='demo' oder 'live'.")
    if mode == "live" and (not model or not model.strip()):
        raise ValueError("Fuer Live-Laeufe MODEL explizit aus der Allowlist setzen.")
    if tasks_dir is None and corpus_path is None:
        raise ValueError("Select tasks_dir or an explicit corpus_path")
    all_hashes = task_source_hashes(tasks_dir, task_schema_path) if tasks_dir is not None else {}
    cases = cases_from_tasks(tasks_dir, task_schema_path) if tasks_dir is not None else load_cases(Path(corpus_path))
    unknown = set(case_ids) - {case.case_id for case in cases}
    if unknown:
        raise ValueError("Unbekannte case_ids: " + ", ".join(sorted(unknown)))
    selected = sorted(
        [case for case in cases if not case_ids or case.case_id in case_ids],
        key=lambda case: case.case_id,
    )
    for case in selected:
        if (case.tutor_context.diagnosis_source is None
                and case.evaluation_only.provenance.response_origin == "synthetic_fixture"):
            # API vocabulary labels the authored hypothesis, not PRT evidence.
            case.tutor_context.diagnosis_source = "synthetic"
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
    if not interaction_script and any(profile.include_chat_history for profile in profiles.profiles):
        raise ValueError("Frische Einzel-Chats haben keine Historie; Flag ausschalten.")
    expected = _configuration_snapshot(expected_config) if expected_config is not None else None
    sources: Dict[str, Path] = {}
    source_hashes = {}
    if tasks_dir is not None:
        references = {
            case.evaluation_only.provenance.instantiated_task_ref.split("#", 1)[0]
            for case in selected
        }
        source_hashes = {reference: all_hashes[reference] for reference in sorted(references)}
        sources = {
            "inputs/" + reference: Path(tasks_dir) / Path(reference).name
            for reference in sorted(references)
        }
        sources["inputs/schemas/stack_ai_tutor_task.schema.json"] = Path(task_schema_path or DEFAULT_SCHEMA_PATH)
    snapshot_hashes = {relative: sha256_file(path) for relative, path in sources.items()}
    if any(snapshot_hashes["inputs/" + reference] != digest for reference, digest in source_hashes.items()):
        raise RunnerError("Task sources changed during preparation; use a new run ID")
    inputs_dir = run_dir.resolve() / "inputs"
    experiment = Experiment(
        schema_version="1.0",
        experiment_id="notebook-context-v1",
        protocol_version="eval-protocol-2",
        description="Kontrollierter Notebookvergleich; synthetische Referenzen und Fehler sind Hypothesen.",
        condition_id=condition_id,
        expected_config_sha256=expected["config_sha256"] if expected else None,
        level_mode=level_mode,
        use_server_context=use_server_context,
        interaction_script=interaction_script or [],
        corpus_file=str(inputs_dir / "cases.jsonl"),
        profiles=sorted(set(profile_ids)),
        hint_levels=hint_levels,
        repetitions=repetitions,
        models=[model] if model else [],
        max_generations_per_hour=max_generations_per_hour,
        request_budget_units_per_hour=request_budget_units_per_hour,
        order_seed=order_seed,
        allow_unverified_cases=allow_unverified_cases,
        allow_task_derived_cases=allow_task_derived_cases,
    )
    errors = validate_experiment(experiment, selected, profiles)
    if errors:
        raise ValueError("\n".join(errors))
    # Check eligibility before writing a directory with no executable jobs.
    if not any(
        case_profile_eligible(case, profile, allow_unverified_cases, allow_task_derived_cases) is None
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
        "expected_configuration": expected,
        "source_task_hashes": source_hashes,
        "source_snapshot_hashes": snapshot_hashes,
    }
    fingerprint = sha256_json(configuration)
    if run_dir.exists() and any(run_dir.iterdir()):
        manifest = load_manifest(run_dir)
        if manifest.get("notebook_configuration_sha256") != fingerprint:
            raise RunnerError("Konfiguration geaendert; einen neuen RUN_ID verwenden.")
        verify_notebook_inputs(run_dir, manifest)
        return manifest

    inputs_dir.mkdir(parents=True, exist_ok=True)
    for relative, source in sources.items():
        target = run_dir.resolve() / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        if sha256_file(target) != snapshot_hashes[relative]:
            raise RunnerError("Task source changed while preparing snapshots; use a new run ID")
    if tasks_dir is not None:
        derived_again = cases_from_tasks(inputs_dir / "tasks", inputs_dir / "schemas" / "stack_ai_tutor_task.schema.json")
        derived_by_id = {case.case_id: case for case in derived_again}
        for case in selected:
            derived = derived_by_id.get(case.case_id)
            if derived is None:
                raise RunnerError("Selected case is absent from the frozen task inputs")
            if derived.tutor_context.diagnosis_source is None:
                derived.tutor_context.diagnosis_source = "synthetic"
            if derived.model_dump() != case.model_dump():
                raise RunnerError("Task case and frozen source disagree; use a new run ID")
    if expected is not None:
        expected_path = inputs_dir / "expected_configuration.json"
        expected_path.write_text(json.dumps(expected, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
        snapshot_hashes["inputs/expected_configuration.json"] = sha256_file(expected_path)
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
        expected_config=expected,
    )
    manifest["execution_mode"] = "offline_demo" if mode == "demo" else "live_tutor_api"
    if expected is not None:
        manifest["expected_configuration"] = expected
    manifest["notebook_configuration_sha256"] = fingerprint
    manifest["case_source"] = "tasks" if tasks_dir is not None else "jsonl"
    manifest["source_task_hashes"] = source_hashes
    manifest["notebook_input_hashes"] = snapshot_hashes
    manifest["notebook_inputs_sha256"] = sha256_json(snapshot_hashes)
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    return manifest


def preview_messages(payload: dict) -> List[Dict[str, str]]:
    """Local pre-request preview, not a reconstruction of a returned prompt.

    Imports only pure prompt/schema modules, never app.main or the LLM client.
    Only an initial, directly selected level with explicit flags can be previewed.
    Individual selection, server defaults and follow-up history are not predicted.
    Local environment rules may still differ from the remote deployment.
    """
    if (not payload.get("stack") or payload.get("hint_level") is None
            or not isinstance(payload.get("context_options"), dict)):
        return []
    from app.hint_policy import HintPolicy, HintPolicyError
    from app.prompt_builder import PromptBuilder
    from app.schemas import ContextOptions, StackContext

    stack = dict(payload["stack"])
    if stack.get("diagnosis_source") == "synthetic_fixture":
        stack["diagnosis_source"] = "synthetic"
    local_policy = HintPolicy(path=POLICY_PATH)
    try:
        local_policy.get(payload["hint_level"])
    except HintPolicyError:
        return []
    return PromptBuilder(local_policy).build_messages(
        stack=StackContext(**stack),
        hint_level=payload["hint_level"],
        options=ContextOptions(**payload["context_options"]),
        history=[],
    )


def write_demo_results(run_dir: Path) -> List[dict]:
    """Persist visibly labelled hand-written outputs, without network or DB.

    Direct scripts use fixed requested levels, not simulated adaptive decisions.
    server_start stays unexecuted: no individual/model start decision is invented.
    One disclosing fixture exercises the check; there are no fabricated timings,
    operations, hypotheses or ratings. Local prompts are labelled demo evidence.
    """
    manifest = load_manifest(run_dir)
    if manifest.get("execution_mode") != "offline_demo":
        raise RunnerError("Demoausgaben duerfen nur in einem Demolauf gespeichert werden.")
    verify_notebook_inputs(run_dir, manifest)
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
    expected = manifest.get("expected_configuration") or {}
    configuration = expected.get("configuration") or {}
    if configuration:
        policy = configuration.get("hint_policy") or manifest["hint_policy"]
        rules = configuration.get("tutor_rules") or {}
    else:
        from app.hint_policy import HintPolicy
        from app.prompt_builder import config, effective_context_options
        from app.schemas import ContextOptions

        policy = HintPolicy(path=POLICY_PATH).levels
        rules = {"policy_mode": config.TUTOR_POLICY_MODE, "diagnosis_mode": config.TUTOR_DIAGNOSIS_MODE}
    policy_mode = rules.get("policy_mode", "tutor")
    direct = manifest.get("level_mode", "direct") == "direct"
    disclosure_job = next(
        (job["job_id"] for job in jobs
         if direct and not job.get("turn_index")
         and not (policy.get(str(job["hint_level"])) or {}).get("include_final_answer")),
        None,
    )
    records = []
    session_levels = {}
    for job in jobs:
        case = cases[job["case_id"]]
        payload = job["request_payload"]
        stack = payload.get("stack") or job.get("stack_context") or {}
        session_id = job.get("session_id", job["job_id"])
        level = payload.get("hint_level")
        if level is None and direct:
            level = session_levels[session_id]
        if direct:
            session_levels[session_id] = level
        options = dict(payload.get("context_options") or configuration.get("context_defaults") or {})
        if rules.get("diagnosis_mode") in {"model", "none"}:
            options["include_diagnosis_code"] = options["include_prt_feedback"] = False
        if level == 0 and configuration.get("stage0_context_options"):
            options = {key: enabled and configuration["stage0_context_options"].get(key, False) for key, enabled in options.items()}
        if direct and not configuration and payload.get("context_options") is not None:
            options = effective_context_options(ContextOptions(**options), level).model_dump()
        if not direct:
            hint = None
        elif job["job_id"] == disclosure_job:
            hint = (
                "Absichtlich zu ausfuehrliche Demoantwort (kein LLM): "
                + (case.evaluation_only.reference.final_answer or "Keine Referenz.")
            )
        elif level == 0:
            hint = "Handgeschriebene diagnostische Demo-Frage (kein LLM): Welche Regel hast du bisher angewendet?"
        elif job.get("turn_index"):
            hint = "Handgeschriebene Dialog-Demo (kein LLM, keine Adaptation): Welchen Teil moechtest du selbst untersuchen?"
        elif options.get("include_prt_feedback") and stack.get("prt_feedback"):
            hint = (
                "Handgeschriebene Demoantwort (kein LLM): "
                + stack["prt_feedback"]
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
            **{key: job.get(key) for key in (
                "condition_id", "session_id", "turn_index", "parent_job_id", "depends_on_job_id",
                "level_mode", "start_hint_level", "requested_hint_level", "use_server_context",
                "interaction_script_sha256", "stack_context", "request_method", "request_path",
            )},
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
            "outcome": "success" if direct else "not_executed",
            "effective_hint_level": level if direct else None,
            "demo_note": "Hand-written fixed-level fixture, no model/adaptation observation" if direct else "Server-selected start requires a live API response; no selection fabricated",
            "tutor_http_status": None,
            "returned": {
                "chat_id": None,
                "question_id": stack["question_id"],
                "hint_level": level,
                "baseline_hint_level": job["start_hint_level"],
                "stage": "diagnostic" if level == 0 else "hint",
                "policy_mode": policy_mode,
                "hint_policy": policy.get(str(level)),
                "policy_origin": "offline_snapshot_not_observed" if expected else "local_policy_not_observed",
                "model": "offline-demo-kein-llm",
                "hint": hint,
                "prompt_messages": preview_messages(payload) if not configuration else None,
                "context_options": options,
                "start_decision": None, "adaptation": None,
                "llm_operations": None, "diagnosis_hypothesis": None,
                "configuration": configuration or None,
                "config_sha256": expected.get("config_sha256"),
            } if direct else None,
            "safe_error": None,
            "retry_of_attempt_id": None,
        })
    results_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return records
