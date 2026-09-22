"""Deterministische Planung und kontrollierte Ausführung von Tutor-Runs.

Eigenschaften gemäß Evaluationsprotokoll:
- Planung ist offline und deterministisch (order_seed).
- Netzaufrufe nur mit expliziter Live-Freigabe (`execute_live=True`).
- Ein geplanter Job = ein Aufruf von POST /api/tutor/start mit frischem
  Chat (ohne chat_id/user_message), allen zehn Kontextschaltern und
  direkt gesetzter Hilfestufe.
- Versuchsjournal: Beginn wird vor dem Versand dauerhaft geschrieben;
  ein Abbruch nach Versand erzeugt einen unklaren Versuch, der bei
  Resume nicht automatisch wiederholt wird.
- Budget: logische Requests pro Stunde (konservativ, da der SAIA-Client
  pro Request bis zu zwei Upstream-Versuche auslösen kann).
- Keine automatischen Runner-Retries; `retry_failed` ist eine explizite,
  manuelle Entscheidung (never für unklare Transportversuche).
- Kein stiller Modellwechsel; Modellfeld kommt unverändert aus dem Plan.
"""

import json
import platform
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from evaluation.corpus import (
    build_request_payload,
    case_profile_eligible,
    load_cases,
    load_profiles,
    sha256_file,
    sha256_json,
)
from evaluation.models import Experiment, SCHEMA_VERSION

EVAL_DIR = Path(__file__).resolve().parent
CODE_DIR = EVAL_DIR.parent
POLICY_PATH = CODE_DIR / "config" / "hint_levels.json"

MANIFEST_FILE = "manifest.json"
PLAN_FILE = "plan.jsonl"
EVENTS_FILE = "events.jsonl"
GENERATIONS_FILE = "generations.jsonl"

BUDGET_WINDOW_SECONDS = 3600.0

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

    try:
        if method == "GET":
            response = requests.get(url, timeout=timeout)
        else:
            response = requests.post(url, json=payload, timeout=timeout)
        try:
            body = response.json()
        except ValueError:
            body = None
        return response.status_code, body, None, ""
    except requests.Timeout as error:
        return None, None, "timeout", str(error)[:300]
    except requests.ConnectionError as error:
        return None, None, "connection", str(error)[:300]
    except requests.RequestException as error:
        return None, None, "request", str(error)[:300]


def _source_fingerprint() -> str:
    """Hash über relevante Server- und Suite-Quellen (nicht .env/Daten)."""
    import hashlib

    files: List[Path] = []
    for pattern_root, pattern in [
        (CODE_DIR / "app", "**/*.py"),
        (EVAL_DIR, "*.py"),
        (CODE_DIR / "schemas", "*.json"),
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
    profile_by_id = profile_set.by_id()
    cases_by_id = {case.case_id: case for case in cases}

    mains: List[dict] = []
    controls: List[dict] = []
    exclusions: List[dict] = []
    seen_exclusions = set()

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
            case, profile, experiment.allow_unverified_cases
        )
        if reason is not None:
            key = (case.case_id, profile_id, level, reason)
            if key not in seen_exclusions:
                seen_exclusions.add(key)
                exclusions.append({
                    "record_type": "exclusion",
                    "case_id": case.case_id,
                    "profile_id": profile_id,
                    "hint_level": level,
                    "reason": reason,
                })
            return
        for repetition_number in range(1, repetition + 1):
            for model in experiment.models or [None]:
                payload = build_request_payload(
                    case, profile, level, model
                )
                target.append({
                    "record_type": "job",
                    "block": block,
                    "case_id": case.case_id,
                    "profile_id": profile_id,
                    "hint_level": level,
                    "model": model,
                    "model_label": model or "server_default",
                    "repetition": repetition_number,
                    "request_payload": payload,
                    "request_sha256": sha256_json(payload),
                })

    experiment.profiles = sorted(experiment.profiles)
    for case in sorted(cases, key=lambda item: item.case_id):
        for level in experiment.hint_levels:
            for profile_id in experiment.profiles:
                apply_grid(
                    case, profile_id, level,
                    experiment.repetitions, "main", mains,
                )
    for control in sorted(
        experiment.control_jobs,
        key=lambda item: (item.case_id, item.profile_id, item.hint_level),
    ):
        case = cases_by_id[control.case_id]
        for repetition_number in range(1, control.repetitions + 1):
            apply_grid(
                case, control.profile_id, control.hint_level,
                1, "control", controls,
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
    jobs = ordered + controls
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
) -> dict:
    """Erzeugt Manifest + Plan (offline, kein Netzaufruf)."""
    experiment = Experiment.model_validate(
        json.loads(experiment_path.read_text(encoding="utf-8"))
    )
    cases = load_cases(corpus_path)
    profile_set = load_profiles(profiles_path)
    jobs, exclusions = build_plan(experiment, cases, profiles_path)

    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_dir.name,
        "experiment_id": experiment.experiment_id,
        "protocol_version": experiment.protocol_version,
        "description": experiment.description,
        "allow_unverified_cases": experiment.allow_unverified_cases,
        "max_generations_per_hour": experiment.max_generations_per_hour,
        "order_seed": experiment.order_seed,
        "base_url": base_url,
        "http_timeout": http_timeout,
        "planned_at_utc": utc_now_iso(),
        "counts": {
            "cases": len(cases),
            "jobs": len(jobs),
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

    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_dir / MANIFEST_FILE, manifest)
    with open(run_dir / PLAN_FILE, "w", encoding="utf-8", newline="\n") as handle:
        for record in jobs + exclusions:
            handle.write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )
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
        if sha256_file(current) != hashes[key]:
            problems.append("Datei geändert: " + relative)
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
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


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

    # --- Budget -----------------------------------------------------
    def _wait_for_budget(self, limit: int) -> float:
        waited = 0.0
        while True:
            now = self.clock()
            self.dispatch_times = [
                stamp for stamp in self.dispatch_times
                if stamp > now - BUDGET_WINDOW_SECONDS
            ]
            if len(self.dispatch_times) < limit:
                return waited
            wait = (self.dispatch_times[0] + BUDGET_WINDOW_SECONDS) - now
            if wait > 0:
                self.sleep(wait)
                waited += wait
            else:
                # Fenster leer, aber Grenze noch gezählt: Kontrollschleife.
                self.dispatch_times.pop(0)

    # --- Ausführung -------------------------------------------------
    def run(
        self,
        execute_live: bool,
        resume: bool = False,
        retry_failed: bool = False,
    ) -> dict:
        if not execute_live:
            raise RunnerError(
                "Live-Ausführung erfordert explizite Freigabe "
                "(--execute-live). Ohne Freigabe gibt es keinen Netzaufruf."
            )
        if not resume and _read_jsonl(self.run_dir / GENERATIONS_FILE):
            raise RunnerError(
                "Run-Verzeichnis enthält bereits Ergebnisse. "
                "Für Fortsetzung --resume verwenden."
            )

        manifest = load_manifest(self.run_dir)
        verify_manifest(self.run_dir, manifest)
        jobs = load_plan(self.run_dir)
        repairs = _repair_in_flight(self.run_dir)

        generations = _read_jsonl(self.run_dir / GENERATIONS_FILE)
        attempted: Dict[str, str] = {}
        for record in generations:
            existing = attempted.get(record["job_id"])
            attempted[record["job_id"]] = _best_outcome(existing, record["outcome"])

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
            elif retry_failed and outcome in retryable:
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
            "skipped_completed": skipped_completed,
            "skipped_failed": skipped_failed,
            "in_flight_repaired": repairs,
            "budget_waits_seconds": 0.0,
        }
        if not pending:
            return stats

        runtime = self._preflight(manifest)
        if runtime is not None and resume is False:
            manifest_copy = dict(manifest)
            manifest_copy["runtime"] = runtime
            manifest_copy["runtime_recorded_at_utc"] = self.wall_clock()
            _write_json(self.run_dir / MANIFEST_FILE, manifest_copy)

        limit = int(manifest["max_generations_per_hour"])
        last_attempt_by_job: Dict[str, str] = {}
        for record in generations:
            last_attempt_by_job[record["job_id"]] = record["attempt_id"]

        for job in pending:
            wait = self._wait_for_budget(limit)
            stats["budget_waits_seconds"] += wait
            stats["dispatched"] += 1
            self.dispatch_times.append(self.clock())
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
                "task_instance_id": job["request_payload"].get(
                    "stack", {}
                ).get("question_id"),
                "profile_id": job["profile_id"],
                "hint_level": job["hint_level"],
                "requested_model": job.get("model"),
                "repetition": job["repetition"],
                "request_sha256": job["request_sha256"],
                "ts_utc": self.wall_clock(),
            }
            _append_jsonl(self.run_dir / EVENTS_FILE, event)
            started_clock = self.clock()
            status, body, error_kind, detail = self.transport(
                "POST",
                manifest["base_url"].rstrip("/")
                + "/api/tutor/start",
                job["request_payload"],
                float(manifest.get("http_timeout", 420.0)),
            )
            duration_ms = int((self.clock() - started_clock) * 1000)
            outcome = _classify(status, error_kind)

            record = {
                "schema_version": SCHEMA_VERSION,
                "run_id": manifest["run_id"],
                "attempt_id": attempt_id,
                "job_id": job["job_id"],
                "execution_source": "live_tutor_api",
                "case_id": job["case_id"],
                "task_instance_id": job[
                    "request_payload"
                ].get("stack", {}).get("question_id"),
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
                "tutor_http_status": status,
                "returned": _extract_returned(body) if outcome == "success" else None,
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
            stats[outcome] += 1
            if outcome != "success":
                # Kein automatischer Retry: Fehler bleiben protokolliert.
                continue
        return stats

    def _preflight(self, manifest: dict) -> Optional[dict]:
        """GET /health, um Instanz und Modell-Default zu dokumentieren."""
        status, body, error_kind, detail = self.transport(
            "GET",
            manifest["base_url"].rstrip("/") + "/health",
            None,
            float(manifest.get("http_timeout", 420.0)),
        )
        if status != 200 or not isinstance(body, dict):
            raise RunnerError(
                "Tutor-Instanz nicht erreichbar (status=" + str(status)
                + ", fehler=" + str(error_kind) + ", " + detail[:200] + ")"
            )
        return {
            "health_status": status,
            "tasks_loaded": body.get("tasks_loaded"),
            "default_model": body.get("default_model"),
        }


def _best_outcome(current: Optional[str], candidate: str) -> str:
    """Beste Auswertung eines Jobs über alle Versuche (success dominiert)."""
    order = [
        "success", "http_error", "rate_limited",
        "server_error", "transport_error", "transport_ambiguous",
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
    return {
        "chat_id": body.get("chat_id"),
        "question_id": body.get("question_id"),
        "hint_level": body.get("hint_level"),
        "model": body.get("model"),
        "hint": body.get("hint"),
        "prompt_messages": body.get("prompt_messages"),
        "context_options": body.get("context_options"),
    }


def _safe_error(
    status: Optional[int],
    detail: str,
    body: Optional[dict],
) -> str:
    """Safe, gekürzte Fehlerbeschreibung ohne Upstream-Rohdaten."""
    if isinstance(body, dict) and isinstance(body.get("detail"), str):
        text = body["detail"]
    elif isinstance(body, dict) and isinstance(body.get("detail"), dict):
        text = json.dumps(body["detail"], ensure_ascii=False)
    else:
        text = detail or "Kein Details vorhanden."
    prefix = "Tutor-HTTP-Status " + str(status) + ": " if status else ""
    return (prefix + text)[:600]
