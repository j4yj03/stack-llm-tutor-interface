"""Deterministische Planung und kontrollierte Ausführung von Tutor-Runs.

Eigenschaften gemäß Evaluationsprotokoll:
- Planung ist offline und deterministisch (order_seed).
- Netzaufrufe nur mit expliziter Live-Freigabe (`execute_live=True`).
- Sessions beginnen mit einem frischen Chat; explizite Skript-Turns
  folgen seriell und nur nach erfolgreicher Vorgaengerantwort.
- Versuchsjournal: Beginn wird vor dem Versand dauerhaft geschrieben;
  ein Abbruch nach Versand erzeugt einen unklaren Versuch, der bei
  Resume nicht automatisch wiederholt wird.
- Budget: logische Requests und gewichtete Generator-/Judge-Kosten.
- Keine automatischen Runner-Retries; `retry_failed` ist eine explizite,
  manuelle Entscheidung (never für unklare Transportversuche).
- Kein stiller Modellwechsel; Modellfeld kommt unverändert aus dem Plan.
"""

import json
import os
import platform
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from evaluation.corpus import (
    CorpusError,
    build_request_payload,
    case_profile_eligible,
    configuration_sha256,
    load_cases,
    load_profiles,
    sha256_file,
    sha256_json,
    validate_experiment,
    validate_public_configuration,
)
from evaluation.models import Experiment, MAX_EVALUATION_HINT_LEVEL, SCHEMA_VERSION

EVAL_DIR = Path(__file__).resolve().parent
CODE_DIR = EVAL_DIR.parent
POLICY_PATH = CODE_DIR / "config" / "hint_levels.json"

MANIFEST_FILE = "manifest.json"
PLAN_FILE = "plan.jsonl"
EVENTS_FILE = "events.jsonl"
GENERATIONS_FILE = "generations.jsonl"

BUDGET_WINDOW_SECONDS = 3600.0
GENERATOR_BUDGET_COST = 4
JUDGE_BUDGET_COST = 2

TransportOutcome = Tuple[Optional[int], Optional[dict], Optional[str], str]


class RunnerError(RuntimeError):
    """Lauf- oder Integritätsfehler der Evaluationssuite."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _request_transport(
    method: str,
    url: str,
    payload: Optional[dict],
    timeout: float,
) -> TransportOutcome:
    """Standardtransport: echte HTTP-Aufrufe an die Tutor-API."""
    import requests

    token = os.getenv("TUTOR_EVALUATION_TOKEN", "")
    headers = {"X-Evaluation-Token": token} if token else {}
    if url.endswith("/api/evaluation/config") and not token:
        raise RunnerError("TUTOR_EVALUATION_TOKEN is required for protected evaluation requests")
    try:
        if method == "GET":
            response = requests.get(
                url, headers=headers, timeout=timeout, verify=True, allow_redirects=False,
            )
        else:
            response = requests.post(
                url, json=payload, headers=headers, timeout=timeout,
                verify=True, allow_redirects=False,
            )
        try:
            body = response.json()
        except ValueError:
            body = None
        return response.status_code, body, None, ""
    except requests.Timeout:
        return None, None, "timeout", "Transport timeout; dispatch outcome is unknown."
    except requests.ConnectionError:
        return None, None, "connection", "Connection failure; dispatch outcome is unknown."
    except requests.RequestException:
        return None, None, "request", "Transport failure; dispatch outcome is unknown."


def _source_fingerprint() -> str:
    """Hash über relevante Server- und Suite-Quellen (nicht .env/Daten)."""
    import hashlib

    files: List[Path] = []
    for pattern_root, pattern in [
        (CODE_DIR / "app", "**/*.py"),
        (EVAL_DIR, "*.py"),
        (CODE_DIR / "schemas", "*.json"),
        (CODE_DIR / "tasks", "*.json"),
    ]:
        files.extend(sorted(pattern_root.glob(pattern)))
    files.append(POLICY_PATH)
    digest = hashlib.sha256()
    for path in sorted(set(files)):
        if not path.is_file():
            continue
        digest.update(str(path.relative_to(CODE_DIR)).encode("utf-8"))
        digest.update(sha256_file(path).encode("utf-8"))
    return digest.hexdigest()


def _git_info() -> dict:
    info = {"git_revision": None, "git_dirty_fingerprint": None}
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(CODE_DIR),
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout.strip()
        info["git_revision"] = revision
    except Exception:
        return info
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(CODE_DIR),
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout
        import hashlib

        info["git_dirty_fingerprint"] = hashlib.sha256(
            status.encode("utf-8")
        ).hexdigest()
    except Exception:
        pass
    return info


def build_plan(
    experiment: Experiment,
    cases,
    profiles_file: Path,
) -> Tuple[List[dict], List[dict]]:
    """Erzeugt deterministisch Job- und Ausschlussliste (offline)."""
    profile_set = load_profiles(profiles_file)
    experiment = Experiment.model_validate(experiment.model_dump())
    errors = validate_experiment(experiment, cases, profile_set)
    if errors:
        raise CorpusError("Invalid experiment:\n- " + "\n- ".join(errors))
    profile_by_id = profile_set.by_id()
    cases_by_id = {case.case_id: case for case in cases}

    mains: List[dict] = []
    controls: List[dict] = []
    exclusions: List[dict] = []
    seen_exclusions = set()
    script_sha256 = sha256_json([
        turn.model_dump(mode="json") for turn in experiment.interaction_script
    ])

    def apply_grid(
        case,
        profile_id: str,
        level: int,
        repetition: int,
        block: str,
        target: List[dict],
    ) -> None:
        profile = profile_by_id[profile_id]
        reason = case_profile_eligible(
            case, profile, experiment.allow_unverified_cases,
            experiment.allow_task_derived_cases,
        )
        if reason is not None:
            key = (case.case_id, profile_id, level, reason)
            if key not in seen_exclusions:
                seen_exclusions.add(key)
                exclusions.append({
                    "record_type": "exclusion",
                    "case_id": case.case_id,
                    "case_sha256": sha256_json(case.model_dump(mode="json")),
                    "profile_id": profile_id,
                    "hint_level": level,
                    "condition_id": experiment.condition_id,
                    "reason": reason,
                })
            return
        for repetition_number in range(1, repetition + 1):
            for model in experiment.models or [None]:
                payload = build_request_payload(
                    case, profile,
                    None if experiment.level_mode == "server_start" else level,
                    model, use_server_context=experiment.use_server_context,
                )
                target.append({
                    "record_type": "job",
                    "block": block,
                    "case_id": case.case_id,
                    "case_sha256": sha256_json(case.model_dump(mode="json")),
                    "question_id": case.tutor_context.question_id,
                    "task_instance_id": case.task_instance_id,
                    "profile_id": profile_id,
                    "hint_level": level,
                    "model": model,
                    "model_label": model or "server_default",
                    "repetition": repetition_number,
                    "request_payload": payload,
                    "request_sha256": sha256_json(payload),
                    "condition_id": experiment.condition_id,
                    "level_mode": experiment.level_mode,
                    "start_hint_level": payload["hint_level"],
                    "requested_hint_level": payload["hint_level"],
                    "requested_context_options": profile.flags(),
                    "use_server_context": experiment.use_server_context,
                    "interaction_script_sha256": script_sha256,
                    "llm_budget_units": GENERATOR_BUDGET_COST,
                })

    for case in sorted(cases, key=lambda item: item.case_id):
        for level in experiment.hint_levels:
            for profile_id in sorted(experiment.profiles):
                apply_grid(
                    case, profile_id, level,
                    experiment.repetitions, "main", mains,
                )
    for control in sorted(
        experiment.control_jobs,
        key=lambda item: (item.case_id, item.profile_id, item.hint_level),
    ):
        case = cases_by_id[control.case_id]
        apply_grid(
            case, control.profile_id, control.hint_level,
            control.repetitions, "control", controls,
        )

    import random

    rng = random.Random(experiment.order_seed)
    ordered = sorted(
        mains,
        key=lambda job: (
            job["case_id"], job["profile_id"], job["hint_level"],
            job["repetition"], job["model_label"],
        ),
    )
    rng.shuffle(ordered)
    jobs = []
    for start_job in ordered + controls:
        start_id = "job-" + str(len(jobs) + 1).zfill(4)
        session_id = "session-" + sha256_json({
            key: start_job[key] for key in (
                "condition_id", "case_id", "profile_id", "level_mode",
                "start_hint_level", "model", "repetition", "interaction_script_sha256",
            )
        })[:16]
        start_job.update({
            "session_id": session_id, "turn_index": 0,
            "parent_job_id": None, "depends_on_job_id": None,
            "request_method": "POST", "request_path": "/api/tutor/start",
        })
        jobs.append(start_job)
        previous_id = start_id
        for turn_index, turn in enumerate(experiment.interaction_script, start=1):
            payload = {
                "message": turn.message,
                "simulation_elapsed_seconds": turn.elapsed_seconds,
            }
            if turn.confusion_signal is not None:
                payload["confusion_signal"] = turn.confusion_signal
            if turn.hint_level is not None:
                payload["hint_level"] = turn.hint_level
            if not experiment.use_server_context:
                payload["context_options"] = start_job["requested_context_options"]
            if start_job["model"]:
                payload["model"] = start_job["model"]
            jobs.append({
                **start_job, "turn_index": turn_index,
                "parent_job_id": start_id, "depends_on_job_id": previous_id,
                "request_path": "/api/tutor/{chat_id}/message",
                "request_payload": payload, "request_sha256": sha256_json(payload),
                "requested_hint_level": turn.hint_level,
                "stack_context": start_job["request_payload"]["stack"],
            })
            previous_id = "job-" + str(len(jobs)).zfill(4)
    for index, job in enumerate(jobs, start=1):
        job["job_id"] = "job-" + str(index).zfill(4)
        job["plan_index"] = index
    return jobs, exclusions


def create_run(
    run_dir: Path,
    experiment_path: Path,
    corpus_path: Path,
    profiles_path: Path,
    base_url: str,
    http_timeout: float = 420.0,
    expected_config: Optional[dict] = None,
) -> dict:
    """Freeze a session plan offline; expected_config is a public API snapshot."""
    parsed_url = urlsplit(base_url)
    if (parsed_url.scheme not in {"http", "https"} or not parsed_url.hostname
            or parsed_url.username or parsed_url.password or parsed_url.query or parsed_url.fragment):
        raise RunnerError("Tutor base URL must be HTTP(S), without credentials, query or fragment")
    if run_dir.exists() and (
        not run_dir.is_dir() or any(path.name != "inputs" for path in run_dir.iterdir())
    ):
        raise RunnerError("Run directory is not empty; use resume or a new run ID")
    experiment = Experiment.model_validate(
        json.loads(experiment_path.read_text(encoding="utf-8"))
    )
    cases = load_cases(corpus_path)
    jobs, exclusions = build_plan(experiment, cases, profiles_path)
    expected = validate_public_configuration(expected_config) if expected_config is not None else None
    expected_hash = experiment.expected_config_sha256
    if expected is not None:
        if expected_hash is not None and expected_hash != expected["config_sha256"]:
            raise RunnerError("expected_config differs from the experiment configuration hash")
        expected_hash = expected["config_sha256"]

    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "experiment_id": experiment.experiment_id,
        "protocol_version": experiment.protocol_version,
        "description": experiment.description,
        "condition_id": experiment.condition_id,
        "expected_config_sha256": expected_hash,
        "expected_configuration": expected,
        "level_mode": experiment.level_mode,
        "use_server_context": experiment.use_server_context,
        "interaction_script": [turn.model_dump(mode="json") for turn in experiment.interaction_script],
        "interaction_script_sha256": sha256_json([
            turn.model_dump(mode="json") for turn in experiment.interaction_script
        ]),
        "allow_unverified_cases": experiment.allow_unverified_cases,
        "allow_task_derived_cases": experiment.allow_task_derived_cases,
        "reference_authority": "controlled_hypotheses_not_authoritative" if (
            experiment.allow_unverified_cases
        ) else "reported_verification_not_independently_verified",
        "max_generations_per_hour": experiment.max_generations_per_hour,
        "request_budget_units_per_hour": experiment.request_budget_units_per_hour,
        "budget": {
            "generator_cost": GENERATOR_BUDGET_COST, "judge_cost": JUDGE_BUDGET_COST,
            "scope": "serial_run_event_journals",
        },
        "order_seed": experiment.order_seed,
        "base_url": base_url.rstrip("/"),
        "http_timeout": http_timeout,
        "planned_at_utc": utc_now_iso(),
        "counts": {
            "cases": len(cases),
            "jobs": len(jobs),
            "sessions": sum(job["turn_index"] == 0 for job in jobs),
            "exclusions": len(exclusions),
        },
        "paths": {
            "experiment": _relpath(experiment_path),
            "corpus": _relpath(corpus_path),
            "profiles": _relpath(profiles_path),
            "policy": _relpath(POLICY_PATH),
        },
        "hashes": {
            "experiment_file": sha256_file(experiment_path),
            "corpus_file": sha256_file(corpus_path),
            "profiles_file": sha256_file(profiles_path),
            "policy_file": sha256_file(POLICY_PATH),
            "source_fingerprint": _source_fingerprint(),
        },
        "git": _git_info(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
        },
        "hint_policy": policy,
        "telemetry_limits": {
            "upstream_attempt_count": "unbekannt (Anwendung liefert keine Werte)",
            "provider_model_id": "unbekannt",
            "provider_request_id": "unbekannt",
            "token_usage": "unbekannt",
            "finish_reason": "unbekannt",
            "effective_thinking_mode": "unbekannt",
        },
    }
    condition_fields = (
        "condition_id", "expected_config_sha256", "level_mode", "use_server_context",
        "interaction_script_sha256", "allow_unverified_cases", "allow_task_derived_cases",
    )
    manifest["condition_sha256"] = sha256_json({key: manifest[key] for key in condition_fields})

    run_dir.mkdir(parents=True, exist_ok=True)
    with open(run_dir / PLAN_FILE, "w", encoding="utf-8", newline="\n") as handle:
        for record in jobs + exclusions:
            handle.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )
    manifest["hashes"]["plan_file"] = sha256_file(run_dir / PLAN_FILE)
    manifest["plan_sha256"] = manifest["hashes"]["plan_file"]
    _write_json(run_dir / MANIFEST_FILE, manifest)
    return manifest


def _relpath(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(CODE_DIR))
    except ValueError:
        return str(path)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_plan(run_dir: Path) -> List[dict]:
    plan_path = run_dir / PLAN_FILE
    if not plan_path.exists():
        raise RunnerError(
            "Kein Plan gefunden; zuerst 'plan' ausführen: " + str(plan_path)
        )
    jobs = []
    with open(plan_path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                record = json.loads(line)
                if record.get("record_type") == "job":
                    jobs.append(record)
    if not jobs:
        raise RunnerError("Plan enthält keine Jobs: " + str(plan_path))
    return jobs


def load_manifest(run_dir: Path) -> dict:
    manifest_path = run_dir / MANIFEST_FILE
    if not manifest_path.exists():
        raise RunnerError(
            "Kein Manifest gefunden; zuerst 'plan' ausführen: "
            + str(manifest_path)
        )
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def verify_manifest(run_dir: Path, manifest: dict) -> None:
    """Resume-Identitätsprüfung: geänderte Grundlagen brechen ab."""
    problems = []
    paths = manifest["paths"]
    hashes = manifest["hashes"]
    code_dir_files = {
        "experiment_file": paths["experiment"],
        "corpus_file": paths["corpus"],
        "profiles_file": paths["profiles"],
        "policy_file": paths["policy"],
    }
    for key, relative in code_dir_files.items():
        current = CODE_DIR / relative
        if not current.is_file() or sha256_file(current) != hashes[key]:
            problems.append("Datei geändert: " + relative)
    plan_hash = manifest.get("plan_sha256") or hashes.get("plan_file")
    if plan_hash is not None and (
        not (run_dir / PLAN_FILE).is_file()
        or sha256_file(run_dir / PLAN_FILE) != plan_hash
        or (hashes.get("plan_file") is not None and hashes["plan_file"] != plan_hash)
    ):
        problems.append("Session plan changed")
    expected = manifest.get("expected_configuration")
    if expected is not None:
        try:
            checked = validate_public_configuration(expected)
            if checked["config_sha256"] != manifest.get("expected_config_sha256"):
                problems.append("Expected configuration identity changed")
        except (CorpusError, ValueError, TypeError):
            problems.append("Expected configuration snapshot is invalid")
    condition_hash = manifest.get("condition_sha256")
    if condition_hash and condition_hash != sha256_json({
        key: manifest.get(key) for key in (
            "condition_id", "expected_config_sha256", "level_mode", "use_server_context",
            "interaction_script_sha256", "allow_unverified_cases", "allow_task_derived_cases",
        )
    }):
        problems.append("Condition identity changed")
    if manifest.get("interaction_script_sha256") is not None and sha256_json(
        manifest.get("interaction_script", [])
    ) != manifest["interaction_script_sha256"]:
        problems.append("Interaction script identity changed")
    for event in _read_jsonl(run_dir / EVENTS_FILE):
        if event.get("plan_sha256") and event["plan_sha256"] != plan_hash:
            problems.append("Journal plan identity changed")
        if event.get("config_sha256") and event["config_sha256"] != (
            (manifest.get("runtime") or {}).get("config_sha256")
        ):
            problems.append("Journal runtime configuration identity changed")
        if event.get("condition_sha256") and event["condition_sha256"] != condition_hash:
            problems.append("Journal condition identity changed")
    if _source_fingerprint() != hashes["source_fingerprint"]:
        problems.append("Quellcode-Fingerprint geändert")
    current_policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if current_policy != manifest.get("hint_policy"):
        problems.append("Hilfestufen-Policy geändert")
    if problems:
        raise RunnerError(
            "Resume abgebrochen; Identität des Laufs nicht mehr gegeben:\n- "
            + "\n- ".join(problems)
        )


def _append_jsonl(path: Path, record: dict) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


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


def _repair_in_flight(run_dir: Path) -> int:
    """Markiert beim Start noch offene Versuche als unklar (kein Replay)."""
    events = _read_jsonl(run_dir / EVENTS_FILE)
    generations = _read_jsonl(run_dir / GENERATIONS_FILE)
    finished_attempts = {
        record.get("attempt_id") for record in generations
    }
    repairs = 0
    for event in events:
        if event.get("event") != "attempt_started":
            continue
        attempt_id = event.get("attempt_id")
        if attempt_id in finished_attempts:
            continue
        job_id = event.get("job_id")
        _append_jsonl(run_dir / EVENTS_FILE, {
            "event": "attempt_finished",
            "attempt_id": attempt_id,
            "job_id": job_id,
            "outcome": "transport_ambiguous",
            "reason": "resume_in_flight",
            "ts_utc": utc_now_iso(),
        })
        _append_jsonl(run_dir / GENERATIONS_FILE, {
            "schema_version": SCHEMA_VERSION,
            "attempt_id": attempt_id,
            "job_id": job_id,
            "outcome": "transport_ambiguous",
            "execution_source": event.get("execution_source", "live_tutor_api"),
            "case_id": event.get("case_id"),
            "task_instance_id": event.get("task_instance_id"),
            "profile_id": event.get("profile_id"),
            "hint_level": event.get("hint_level"),
            "requested_model": event.get("requested_model"),
            "repetition": event.get("repetition"),
            "request_sha256": event.get("request_sha256"),
            **{key: event.get(key) for key in (
                "condition_id", "session_id", "turn_index", "parent_job_id",
                "depends_on_job_id", "level_mode", "start_hint_level",
                "requested_hint_level", "interaction_script_sha256",
                "request_method", "request_path", "request_payload", "stack_context",
                "requested_context_options", "use_server_context", "budget_cost",
                "config_sha256", "plan_sha256",
                "condition_sha256", "case_sha256", "question_id", "llm_budget_units",
                "session_retry_safe",
            )},
            "started_at_utc": event.get("ts_utc"),
            "finished_at_utc": utc_now_iso(),
            "duration_ms": None,
            "tutor_http_status": None,
            "safe_error": (
                "Versuch war beim Resume noch offen; Ergebnis unbekannt."
            ),
            "retry_of_attempt_id": None,
        })
        finished_attempts.add(attempt_id)
        repairs += 1
    return repairs


class Runner:
    """Führt geplante Jobs kontrolliert gegen die reale Tutor-API aus."""

    def __init__(
        self,
        run_dir: Path,
        transport: Optional[Callable[[str, str, Optional[dict], float], TransportOutcome]] = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], str] = utc_now_iso,
    ) -> None:
        self.run_dir = run_dir
        self.transport = transport or _request_transport
        self.sleep = sleep
        self.clock = clock
        self.wall_clock = wall_clock
        self.dispatch_times: List[float] = []
        self._budget_entries: Dict[Tuple[str, str], Tuple[float, int, bool]] = {}
        self._budget_limit: Optional[int] = None
        self._generation_limit: Optional[int] = None

    # --- Budget -----------------------------------------------------
    def wait_for_budget(self, cost: int) -> float:
        """Reconstruct serial generator/judge costs, including unfinished attempts."""
        if self._budget_limit is None:
            manifest = load_manifest(self.run_dir)
            self._budget_limit = int(manifest.get("request_budget_units_per_hour", 80))
            self._generation_limit = int(manifest["max_generations_per_hour"])
        if type(cost) is not int or not 1 <= cost <= self._budget_limit:
            raise RunnerError("Request cost exceeds the weighted run budget")
        waited = 0.0
        while True:
            now = self.clock()
            wall_now = datetime.fromisoformat(self.wall_clock())
            if wall_now.tzinfo is None:
                raise RunnerError("Budget timestamps must include a timezone")
            paths = [self.run_dir / EVENTS_FILE] + sorted(
                (self.run_dir / "reviews" / "judge").glob("*/events.jsonl")
            )
            for path in paths:
                generator = path.parent == self.run_dir
                for index, event in enumerate(_read_jsonl(path)):
                    if event.get("event") != "attempt_started":
                        continue
                    key = (str(path), event.get("attempt_id") or str(index))
                    if key in self._budget_entries:
                        continue
                    units = event.get("budget_cost", event.get(
                        "llm_budget_units", GENERATOR_BUDGET_COST if generator else JUDGE_BUDGET_COST,
                    ))
                    if type(units) is not int or units < 1:
                        raise RunnerError("Invalid budget cost in the shared run journal")
                    try:
                        stamp = datetime.fromisoformat(event["ts_utc"])
                        age = (wall_now - stamp).total_seconds()
                    except (KeyError, ValueError, TypeError) as error:
                        raise RunnerError("Invalid timestamp in the shared run journal") from error
                    self._budget_entries[key] = (now - max(age, 0.0), units, generator)
            active = sorted(
                entry for entry in self._budget_entries.values()
                if entry[0] > now - BUDGET_WINDOW_SECONDS
            )
            self.dispatch_times = [
                stamp for stamp, _units, generator in active if generator
            ]
            used = sum(units for _stamp, units, _generator in active)
            count = len(self.dispatch_times)
            logical_cost = int(cost == GENERATOR_BUDGET_COST)
            if (used + cost <= self._budget_limit
                    and count + logical_cost <= self._generation_limit):
                return waited
            delay = 0.0
            for stamp, units, generator in active:
                used -= units
                count -= int(generator)
                delay = stamp + BUDGET_WINDOW_SECONDS - now
                if (used + cost <= self._budget_limit
                        and count + logical_cost <= self._generation_limit):
                    break
            self.sleep(max(delay, 0.001))
            waited += max(delay, 0.001)

    # --- Ausführung -------------------------------------------------
    def run(
        self,
        execute_live: bool,
        resume: bool = False,
        retry_failed: bool = False,
    ) -> dict:
        """Dispatch serially; retry_failed replays known failed starts only.

        Follow-up POSTs may have stored messages/advanced simulation before an
        error. Without API idempotency, their failures block the rest of a session.
        """
        if not execute_live:
            raise RunnerError(
                "Live-Ausführung erfordert explizite Freigabe "
                "(--execute-live). Ohne Freigabe gibt es keinen Netzaufruf."
            )
        manifest = load_manifest(self.run_dir)
        if manifest.get("execution_mode") == "offline_demo":
            raise RunnerError("Ein Demolauf darf nicht gegen die Live-API ausgefuehrt werden.")
        if not resume and (
            _read_jsonl(self.run_dir / GENERATIONS_FILE)
            or any(event.get("event") == "attempt_started" for event in _read_jsonl(self.run_dir / EVENTS_FILE))
        ):
            raise RunnerError(
                "Run-Verzeichnis enthält bereits Ergebnisse. "
                "Für Fortsetzung --resume verwenden."
            )

        verify_manifest(self.run_dir, manifest)
        jobs = load_plan(self.run_dir)
        repairs = _repair_in_flight(self.run_dir)

        generations = _read_jsonl(self.run_dir / GENERATIONS_FILE)
        attempted: Dict[str, str] = {}
        successful: Dict[str, dict] = {}
        for record in generations:
            existing = attempted.get(record["job_id"])
            attempted[record["job_id"]] = _best_outcome(existing, record["outcome"])
            if record["outcome"] == "success":
                successful[record["job_id"]] = record

        retryable = {"http_error", "server_error", "rate_limited"}
        pending: List[dict] = []
        skipped_completed = 0
        skipped_failed = 0
        for job in jobs:
            outcome = attempted.get(job["job_id"])
            if outcome is None or outcome == "pending":
                pending.append(job)
            elif outcome == "success":
                skipped_completed += 1
            elif retry_failed and outcome in retryable and not job.get("turn_index"):
                pending.append(job)
            else:
                skipped_failed += 1

        stats = {
            "run_id": manifest["run_id"],
            "planned": len(jobs),
            "dispatched": 0,
            "success": 0,
            "http_error": 0,
            "rate_limited": 0,
            "server_error": 0,
            "transport_ambiguous": 0,
            "transport_error": 0,
            "configuration_mismatch": 0,
            "invalid_response": 0,
            "skipped_completed": skipped_completed,
            "skipped_failed": skipped_failed,
            "skipped_dependency": 0,
            "skipped_configuration": 0,
            "in_flight_repaired": repairs,
            "budget_waits_seconds": 0.0,
        }
        runtime = self._preflight(manifest)
        if manifest.get("runtime") is None or (
            not (manifest.get("runtime") or {}).get("config_sha256")
            and runtime.get("config_sha256")
        ):
            manifest["runtime"] = runtime
            manifest["runtime_recorded_at_utc"] = self.wall_clock()
            _write_json(self.run_dir / MANIFEST_FILE, manifest)
        if any(record.get("outcome") == "configuration_mismatch" for record in generations):
            raise RunnerError("A configuration-mismatched run cannot dispatch further requests; use a new run ID")
        if not pending:
            return stats
        self._budget_limit = int(manifest.get("request_budget_units_per_hour", 80))
        self._generation_limit = int(manifest["max_generations_per_hour"])
        last_attempt_by_job: Dict[str, str] = {}
        for record in generations:
            last_attempt_by_job[record["job_id"]] = record["attempt_id"]

        configuration_invalid = False
        for job in pending:
            dependency = job.get("depends_on_job_id")
            predecessor = successful.get(dependency) if dependency else None
            if configuration_invalid or (dependency and predecessor is None):
                stats["skipped_configuration"] += int(configuration_invalid)
                stats["skipped_dependency"] += int(bool(dependency))
                _append_jsonl(self.run_dir / EVENTS_FILE, {
                    "event": "job_blocked", "job_id": job["job_id"],
                    "depends_on_job_id": dependency,
                    "dependency_outcome": attempted.get(dependency, "not_dispatched"),
                    "outcome": "configuration_blocked" if configuration_invalid else "dependency_blocked",
                    "ts_utc": self.wall_clock(),
                    "reason": "configuration_mismatch" if configuration_invalid else "predecessor_not_successful",
                })
                continue
            path = job.get("request_path", "/api/tutor/start")
            previous_returned = (predecessor or {}).get("returned") or {}
            if dependency:
                chat_id = previous_returned.get("chat_id")
                try:
                    chat_id = str(uuid.UUID(chat_id))
                except (ValueError, TypeError, AttributeError):
                    raise RunnerError("A successful predecessor has no usable chat UUID") from None
                path = path.replace("{chat_id}", chat_id)
            if (dependency and self.transport is _request_transport
                    and not os.getenv("TUTOR_EVALUATION_TOKEN", "")):
                raise RunnerError("Scripted simulation requires TUTOR_EVALUATION_TOKEN")
            cost = int(job.get("llm_budget_units", GENERATOR_BUDGET_COST))
            wait = self.wait_for_budget(cost)
            stats["budget_waits_seconds"] += wait
            stats["dispatched"] += 1
            attempt_id = "attempt-" + uuid.uuid4().hex[:12]
            retry_of = (
                last_attempt_by_job.get(job["job_id"])
                if retry_failed else None
            )
            event = {
                "event": "attempt_started",
                "attempt_id": attempt_id,
                "job_id": job["job_id"],
                "execution_source": "live_tutor_api",
                "case_id": job["case_id"],
                "task_instance_id": job.get("task_instance_id"),
                "profile_id": job["profile_id"],
                "hint_level": job["hint_level"],
                "requested_model": job.get("model"),
                "repetition": job["repetition"],
                "request_sha256": job["request_sha256"],
                "request_payload": job["request_payload"],
                "request_method": job.get("request_method", "POST"),
                "request_path": path,
                "budget_cost": cost,
                "llm_budget_units": cost,
                "request_kind": "generator",
                "session_retry_safe": not bool(job.get("turn_index")),
                "config_sha256": runtime.get("config_sha256"),
                "plan_sha256": manifest.get("plan_sha256"),
                "condition_sha256": manifest.get("condition_sha256"),
                **{key: job.get(key) for key in (
                    "condition_id", "session_id", "turn_index", "parent_job_id",
                    "depends_on_job_id", "level_mode", "start_hint_level",
                    "requested_hint_level", "requested_context_options", "use_server_context",
                    "interaction_script_sha256", "stack_context", "question_id",
                    "case_sha256",
                )},
                "ts_utc": self.wall_clock(),
            }
            _append_jsonl(self.run_dir / EVENTS_FILE, event)
            self._budget_entries[(str(self.run_dir / EVENTS_FILE), attempt_id)] = (
                self.clock(), cost, True,
            )
            started_clock = self.clock()
            try:
                status, body, error_kind, detail = self.transport(
                    job.get("request_method", "POST"),
                    manifest["base_url"].rstrip("/") + path,
                    job["request_payload"], float(manifest.get("http_timeout", 420.0)),
                )
            except Exception:
                status, body, error_kind, detail = None, None, "timeout", ""
            duration_ms = int((self.clock() - started_clock) * 1000)
            outcome = _classify(status, error_kind)
            if outcome == "success" and runtime.get("config_sha256"):
                if not isinstance(body, dict) or body.get("config_sha256") != runtime["config_sha256"]:
                    outcome = "configuration_mismatch"
                elif body.get("configuration") is not None:
                    try:
                        observed = validate_public_configuration(body)
                        if (runtime.get("configuration") is not None
                                and observed["configuration"] != runtime["configuration"]):
                            outcome = "configuration_mismatch"
                    except (CorpusError, ValueError, TypeError):
                        outcome = "configuration_mismatch"
            if outcome == "success" and (runtime.get("config_sha256") or dependency
                                         or manifest.get("interaction_script")
                                         or manifest.get("level_mode") == "server_start"):
                try:
                    uuid.UUID(body["chat_id"])
                    level = body["hint_level"]
                    if type(level) is not int or not 0 <= level <= MAX_EVALUATION_HINT_LEVEL:
                        raise ValueError("Invalid effective level")
                    bounds = (runtime.get("configuration") or {}).get("start") or {}
                    if (type(bounds.get("max_level")) is int
                            and not bounds.get("min_level", 0) <= level <= bounds["max_level"]):
                        raise ValueError("Effective level exceeds the pinned server bounds")
                    if body.get("question_id") != job.get("question_id"):
                        raise ValueError("Task identity changed")
                    if job.get("model") and body.get("model") != job["model"]:
                        raise ValueError("Model identity changed")
                    desired = job["request_payload"].get("hint_level")
                    if desired is not None and level != desired:
                        raise ValueError("Explicit target level changed")
                    if body.get("stage") is not None and body["stage"] != (
                        "diagnostic" if level == 0 else "hint"
                    ):
                        raise ValueError("Stage identity changed")
                    if dependency and body["chat_id"] != previous_returned.get("chat_id"):
                        raise ValueError("Chat identity changed")
                    if dependency and body.get("model") != previous_returned.get("model"):
                        raise ValueError("Session model alias changed")
                    if not isinstance(body.get("hint"), str) or not body["hint"].strip():
                        raise ValueError("Missing hint")
                except (KeyError, ValueError, TypeError, AttributeError):
                    outcome = "invalid_response"

            record = {
                **{key: value for key, value in event.items() if key not in {"event", "ts_utc"}},
                "schema_version": SCHEMA_VERSION,
                "run_id": manifest["run_id"],
                "attempt_id": attempt_id,
                "job_id": job["job_id"],
                "execution_source": "live_tutor_api",
                "case_id": job["case_id"],
                "task_instance_id": job.get("task_instance_id"),
                "profile_id": job["profile_id"],
                "hint_level": job["hint_level"],
                "requested_model": job.get("model"),
                "repetition": job["repetition"],
                "request_payload": job["request_payload"],
                "request_sha256": job["request_sha256"],
                "started_at_utc": event["ts_utc"],
                "finished_at_utc": self.wall_clock(),
                "duration_ms": duration_ms,
                "outcome": outcome,
                "effective_hint_level": body.get("hint_level") if isinstance(body, dict) else None,
                "session_retry_safe": not bool(job.get("turn_index")),
                "hint_policy_sha256": sha256_json(body["hint_policy"]) if (
                    isinstance(body, dict) and isinstance(body.get("hint_policy"), dict)
                ) else None,
                "tutor_http_status": status,
                "returned": _extract_returned(body) if status == 200 else None,
                "safe_error": (
                    _safe_error(status, detail, body)
                    if outcome != "success" else None
                ),
                "retry_of_attempt_id": retry_of,
            }
            _append_jsonl(self.run_dir / GENERATIONS_FILE, record)
            _append_jsonl(self.run_dir / EVENTS_FILE, {
                "event": "attempt_finished",
                "attempt_id": attempt_id,
                "job_id": job["job_id"],
                "outcome": outcome,
                "ts_utc": self.wall_clock(),
            })
            last_attempt_by_job[job["job_id"]] = attempt_id
            attempted[job["job_id"]] = _best_outcome(attempted.get(job["job_id"]), outcome)
            stats[outcome] += 1
            if outcome == "success":
                successful[job["job_id"]] = record
            if outcome == "configuration_mismatch":
                configuration_invalid = True
        return stats

    def _preflight(self, manifest: dict) -> dict:
        """Observe health/config identity on every execution, including resume."""
        base_url = manifest["base_url"].rstrip("/")
        timeout = float(manifest.get("http_timeout", 420.0))
        try:
            status, body, error_kind, _detail = self.transport("GET", base_url + "/health", None, timeout)
        except Exception:
            raise RunnerError("Tutor health preflight transport failed") from None
        if status != 200 or error_kind is not None or not isinstance(body, dict):
            raise RunnerError(
                "Tutor health preflight failed (HTTP " + str(status) + ")"
            )
        expected = manifest.get("expected_config_sha256")
        previous = manifest.get("runtime") or {}
        digest = body.get("config_sha256")
        token = os.getenv("TUTOR_EVALUATION_TOKEN", "")
        default_model = body.get("default_model")
        if token and isinstance(default_model, str) and token in default_model:
            raise RunnerError("Evaluation credentials cannot enter recorded runtime metadata")
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise RunnerError("Invalid configuration hash in Tutor health response")
        for pinned in (expected, previous.get("config_sha256")):
            if pinned is not None and digest != pinned:
                raise RunnerError("Tutor health configuration differs from the pinned identity or is missing")
        runtime = {
            "health_status": status,
            "tasks_loaded": body.get("tasks_loaded"),
            "default_model": default_model,
            "config_sha256": digest,
        }
        needs_config = bool(
            expected or manifest.get("use_server_context")
            or manifest.get("level_mode") == "server_start"
            or manifest.get("interaction_script") or previous.get("configuration")
            or os.getenv("TUTOR_EVALUATION_TOKEN", "")
        )
        if needs_config:
            try:
                status, config_body, error_kind, _detail = self.transport(
                    "GET", base_url + "/api/evaluation/config", None, timeout,
                )
            except Exception:
                raise RunnerError("Protected evaluation configuration preflight failed") from None
            if status != 200 or error_kind is not None:
                raise RunnerError("Protected evaluation configuration preflight failed (HTTP " + str(status) + ")")
            try:
                observed = validate_public_configuration(config_body)
            except (CorpusError, ValueError, TypeError):
                raise RunnerError("Invalid public configuration response") from None
            if digest is not None and observed["config_sha256"] != digest:
                raise RunnerError("Health and evaluation configuration identities differ")
            if expected is not None and observed["config_sha256"] != expected:
                raise RunnerError("Observed configuration differs from the prepared condition")
            if previous.get("configuration") is not None and observed["configuration"] != previous["configuration"]:
                raise RunnerError("Server configuration changed; resume is forbidden")
            runtime.update(observed)
        if previous.get("default_model") is not None and runtime.get("default_model") != previous["default_model"]:
            raise RunnerError("Observed server default model changed; resume is forbidden")
        start = (runtime.get("configuration") or {}).get("start") or {}
        if start:
            minimum, maximum = start.get("min_level", 0), start.get("max_level")
            for job in load_plan(self.run_dir):
                desired = job.get("request_payload", {}).get("hint_level")
                if (desired is not None and type(maximum) is int
                        and not minimum <= desired <= maximum):
                    raise RunnerError("Requested hint level exceeds the observed server policy bounds")
        return runtime


def _best_outcome(current: Optional[str], candidate: str) -> str:
    """Success dominates; otherwise an ambiguous attempt blocks further retries."""
    order = [
        "success", "configuration_mismatch", "invalid_response", "transport_ambiguous", "http_error", "rate_limited",
        "server_error", "transport_error",
        "pending",
    ]
    ranking = {name: rank for rank, name in enumerate(order)}
    if current is None:
        return candidate
    return current if ranking.get(current, 99) <= ranking.get(candidate, 99) else candidate


def _classify(status: Optional[int], error_kind: Optional[str]) -> str:
    if error_kind is None and status == 200:
        return "success"
    if error_kind is None and status == 429:
        return "rate_limited"
    if error_kind is None and status is not None and 400 <= status < 500:
        return "http_error"
    if error_kind is None and status is not None and status >= 500:
        return "server_error"
    if error_kind in {"timeout", "connection"}:
        return "transport_ambiguous"
    return "transport_error"


def _extract_returned(body: Optional[dict]) -> Optional[dict]:
    if not isinstance(body, dict):
        return None
    returned = {key: body.get(key) for key in (
        "chat_id", "question_id", "hint_level", "model", "hint",
        "prompt_messages", "context_options",
    )}
    for key in (
        "baseline_hint_level", "start_decision", "adaptation", "hint_policy",
        "configuration", "config_sha256", "policy_mode", "stage",
        "diagnosis_hypothesis", "start_prompt_messages", "llm_operations",
        "requested_context_options",
    ):
        if key in body:
            returned[key] = body[key]
    # Fail closed if the purported public response contains credentials.
    if isinstance(returned.get("configuration"), dict):
        try:
            validate_public_configuration({
                "configuration": returned["configuration"],
                "config_sha256": configuration_sha256(returned["configuration"]),
            })
        except (CorpusError, ValueError, TypeError):
            returned["configuration"] = None
    token = os.getenv("TUTOR_EVALUATION_TOKEN", "")

    def redact(value):
        if isinstance(value, dict):
            return {
                key: redact(item) for key, item in value.items()
                if not (key.lower() in {"token", "credentials"} or any(
                    part in key.lower() for part in (
                        "api_key", "api_token", "evaluation_token", "authorization", "password", "secret",
                    )
                )) or type(item) is bool
            }
        if isinstance(value, list):
            return [redact(item) for item in value]
        if token and isinstance(value, str):
            return value.replace(token, "[redacted evaluation credential]")
        return value

    return redact(returned)


def _safe_error(
    status: Optional[int],
    detail: str,
    body: Optional[dict],
) -> str:
    """No credentials, arbitrary transport detail or upstream body is retained."""
    return "Tutor-HTTP-Status " + str(status) + "; attempt failed. No upstream error body retained."
