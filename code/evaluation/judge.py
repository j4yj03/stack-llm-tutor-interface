"""Offline preparation, explicitly gated model judging and separate summaries.

Transport: (method, url, payload, timeout) -> (status, body, error_kind, detail).
The default transport reads TUTOR_EVALUATION_TOKEN only while dispatching; neither
credentials nor transport error bodies enter artifacts. An injected budget must
implement wait_for_budget(cost: int) -> float and share the run's event journals.
Dispatch is serial: judge starts cost 2; legacy/unweighted generator starts cost
4. Concurrent runs or other clients sharing a provider key are not covered.
"""

import csv
import hashlib
import json
import os
import re
import statistics
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import urlsplit

from evaluation import report, runner
from evaluation.corpus import load_cases, sha256_file, sha256_json


JUDGE_RULE_ID = "judge-rubric-1.0-v2"
JUDGE_SOURCE = "live_judge_api"
CHOICES = ("ja", "nein", "unklar", "nicht_anwendbar")
POLICY_FIELDS = (
    "name", "goal", "may_include", "must_not_include", "max_words",
    "include_solution_steps", "include_final_answer", "max_solution_steps",
)
GENERATOR_RULE_FIELDS = (
    "diagnosis_mode", "ask_activating_question", "hide_hint_level", "enforce_word_limit",
)
RESULTS_FILE = "judgements.jsonl"
MAX_RESPONSE_BYTES = 500000


class JudgeRunError(runner.RunnerError):
    """Invalid judge inputs, artifact identity, live authorization or protocol."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _judge_dir(run_dir: Path, judge_run_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", judge_run_id):
        raise JudgeRunError("judge_run_id must be a bounded identifier, not a path.")
    return Path(run_dir) / "reviews" / "judge" / judge_run_id


def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise JudgeRunError("A journal record must be a JSON object.")
                records.append(value)
    return records


def _append_jsonl(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")


def _checked_configuration(value: dict) -> dict:
    required = {"configuration", "config_sha256", "rule_id", "judge_model", "judge_parameters"}
    if not isinstance(value, dict) or required - set(value) or not isinstance(value.get("configuration"), dict):
        raise JudgeRunError("The evaluation configuration response is missing.")
    canonical = json.dumps(value["configuration"], sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    if value.get("config_sha256") != hashlib.sha256(canonical.encode("utf-8")).hexdigest():
        raise JudgeRunError("The evaluation configuration hash does not match.")
    if value.get("rule_id") != JUDGE_RULE_ID:
        raise JudgeRunError("Unsupported judge rule identity.")
    model = value.get("judge_model")
    if model is not None and (not isinstance(model, str) or not model or len(model) > 200):
        raise JudgeRunError("Invalid configured judge model alias.")
    params = value.get("judge_parameters")
    if (not isinstance(params, dict) or set(params) != {"temperature", "max_tokens", "json_output"}
            or type(params["temperature"]) not in (int, float)
            or not 0 <= params["temperature"] <= 2
            or type(params["max_tokens"]) is not int or not 1 <= params["max_tokens"] <= 32768
            or params["json_output"] is not True):
        raise JudgeRunError("Missing or invalid judge generation parameters.")
    # Public snapshots are not a place for credentials, even with a valid hash.
    def check_keys(data) -> None:
        if isinstance(data, dict):
            for key, item in data.items():
                if (key.lower() in {"token", "credentials"} or any(part in key.lower() for part in ("api_key", "api_token", "evaluation_token", "authorization", "password", "secret"))) and type(item) is not bool:
                    raise JudgeRunError("Credentials cannot be stored in a public configuration snapshot.")
                check_keys(item)
        elif isinstance(data, list):
            for item in data:
                check_keys(item)

    check_keys(value)
    return {key: value[key] for key in ("configuration", "config_sha256", "rule_id", "judge_model", "judge_parameters")}


def _base_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise JudgeRunError("Tutor base URL must be HTTP(S), without credentials, query or fragment.")
    return value.rstrip("/")


def _active_policy(record: dict, manifest: dict, level: int) -> tuple:
    returned = record.get("returned") or {}
    policy = returned.get("hint_policy")
    if isinstance(policy, dict):
        origin = "observed_response"
    else:
        configuration = returned.get("configuration") or {}
        policy = (configuration.get("hint_policy") or {}).get(str(level))
        origin = "observed_configuration"
    if not isinstance(policy, dict):
        policy = (manifest.get("hint_policy") or {}).get(str(level))
        origin = "saved_manifest_not_observed"
    if not isinstance(policy, dict):
        raise JudgeRunError("No active policy exists for target level " + str(level) + ".")
    policy = {key: policy[key] for key in POLICY_FIELDS if key in policy}
    required = set(POLICY_FIELDS) - {"name", "max_solution_steps"}
    if required - set(policy):
        raise JudgeRunError("The saved active policy is incomplete.")
    if (not isinstance(policy["goal"], str) or not 1 <= len(policy["goal"]) <= 2000
            or type(policy["max_words"]) is not int or not 1 <= policy["max_words"] <= 2000
            or type(policy["include_solution_steps"]) is not bool
            or type(policy["include_final_answer"]) is not bool):
        raise JudgeRunError("The saved active policy has invalid field values.")
    for field in ("may_include", "must_not_include"):
        if (not isinstance(policy[field], list) or len(policy[field]) > 32
                or any(not isinstance(item, str) or len(item) > 1000 for item in policy[field])):
            raise JudgeRunError("The saved active policy has invalid content lists.")
    limit = policy.get("max_solution_steps")
    if limit is not None and (type(limit) is not int or not 0 <= limit <= 64):
        raise JudgeRunError("The saved active policy has an invalid step limit.")
    return policy, origin


def prepare_judge_run(
    run_dir: Path,
    judge_run_id: str,
    *,
    judge_model: Optional[str] = None,
    configuration: Optional[dict] = None,
    target_attempt_ids: Optional[List[str]] = None,
    base_url: Optional[str] = None,
    max_budget_units_per_hour: int = 80,
    http_timeout: Optional[float] = None,
) -> dict:
    """Freeze latest saved live successes and common references, without networking.

    Actual returned ``hint_policy`` / ``configuration.hint_policy`` takes priority
    over the generator manifest. Only saved actual ``prompt_messages`` establishes
    observed_context; no request fields or local preview replace missing evidence.
    Separate returned diagnosis hypotheses and submitted follow-up messages never
    replace the initial answer/reference. Rule switches come only from the saved
    returned configuration; absent settings remain unknown.
    A run ID is immutable. Changed inputs require a new ID, never hash editing.
    """
    run_dir = Path(run_dir).resolve()
    directory = _judge_dir(run_dir, judge_run_id)
    source = runner.load_manifest(run_dir)
    if source.get("execution_mode") == "offline_demo":
        raise JudgeRunError("Offline demo runs cannot be model judged.")
    runner.verify_manifest(run_dir, source)
    if directory.exists():
        raise JudgeRunError("Judge run already exists; use resume or a new judge_run_id.")
    if judge_model is not None and (not isinstance(judge_model, str) or not 1 <= len(judge_model) <= 200):
        raise JudgeRunError("Invalid requested judge model alias.")
    if type(max_budget_units_per_hour) is not int or not 2 <= max_budget_units_per_hour <= 100:
        raise JudgeRunError("Weighted budget must be 2..100 provider-call units per hour.")
    expected = _checked_configuration(configuration) if configuration is not None else None
    corpus = (source.get("paths") or {}).get("corpus")
    if not corpus:
        raise JudgeRunError("A frozen source corpus is required; references cannot be guessed.")
    cases = {case.case_id: case.model_dump() for case in load_cases(runner.CODE_DIR / corpus)}
    targets = report._successful_results([
        record for record in _read_jsonl(run_dir / runner.GENERATIONS_FILE)
        if record.get("execution_source") == "live_tutor_api"
    ])
    if target_attempt_ids is not None:
        selected = set(target_attempt_ids)
        if len(selected) != len(target_attempt_ids) or selected - {item["attempt_id"] for item in targets}:
            raise JudgeRunError("Targets must be unique, latest successful live attempt IDs.")
        targets = [item for item in targets if item["attempt_id"] in selected]
    if not targets:
        raise JudgeRunError("There are no saved successful live outputs to judge.")
    jobs = []
    selected_cases = {}
    model = judge_model or (expected or {}).get("judge_model")
    for record in targets:
        case = cases.get(record.get("case_id"))
        if case is None:
            raise JudgeRunError("A target case is missing from the frozen source corpus.")
        selected_cases[case["case_id"]] = case
        context = case["tutor_context"]
        reference = case["evaluation_only"].get("reference") or {}
        verification = case["evaluation_only"].get("verification") or {}
        returned = record.get("returned") or {}
        generator_model = returned.get("model") or record.get("requested_model")
        if model and model == generator_model:
            raise JudgeRunError("The judge model must differ from the saved generator alias.")
        hint = returned.get("hint")
        level = returned.get("hint_level", record.get("hint_level"))
        if not isinstance(hint, str) or not hint.strip() or len(hint) > 20000:
            raise JudgeRunError("A successful target has no bounded, nonempty hint.")
        max_level = ((returned.get("configuration") or {}).get("start") or {}).get("max_level")
        if max_level is None:
            max_level = max(int(key) for key in source["hint_policy"])
        if type(level) is not int or type(max_level) is not int or not 0 <= level <= max_level:
            raise JudgeRunError("A target has an invalid hint level.")
        request = record.get("request_payload") or {}
        stack = request.get("stack") or record.get("stack_context") or {}
        for field in ("question_text", "student_answer"):
            if field in stack and stack[field] != context[field]:
                raise JudgeRunError("Target task variant/answer does not match its frozen reference case.")
        policy, policy_origin = _active_policy(record, source, level)
        observed_rules = ((returned.get("configuration") or {}).get("tutor_rules") or {})
        settings = {field: observed_rules.get(field) for field in GENERATOR_RULE_FIELDS}
        if settings["diagnosis_mode"] not in (None, "provided", "model", "none") or any(
            settings[field] is not None and type(settings[field]) is not bool
            for field in GENERATOR_RULE_FIELDS[1:]
        ):
            raise JudgeRunError("Observed generator rule settings are invalid.")
        hypothesis = returned.get("diagnosis_hypothesis")
        current_message = request.get("message")
        turn_index = record.get("turn_index")
        for name, value in (("diagnosis_hypothesis", hypothesis), ("current_message", current_message)):
            if value is not None and (not isinstance(value, str) or len(value) > 2000):
                raise JudgeRunError("A target has an invalid or unbounded " + name + ".")
        if turn_index is not None and (type(turn_index) is not int or not 0 <= turn_index <= 1000):
            raise JudgeRunError("A target has an invalid turn_index.")
        policy_mode = returned.get("policy_mode", observed_rules.get("policy_mode", record.get("policy_mode", request.get("policy_mode", "tutor"))))
        stage = returned.get("stage", record.get("stage", "diagnostic" if level == 0 else "hint"))
        if policy_mode not in {"tutor", "general"} or stage != ("diagnostic" if level == 0 else "hint"):
            raise JudgeRunError("Invalid policy mode or stage on a target.")
        prompt = returned.get("prompt_messages")
        observed = None
        if prompt is not None and prompt != []:
            if (not isinstance(prompt, list) or not prompt or len(prompt) > 30
                    or any(not isinstance(message, dict) or set(message) != {"role", "content"}
                           or message["role"] not in {"system", "developer", "assistant", "user"}
                           or not isinstance(message["content"], str) or len(message["content"]) > 30000
                           for message in prompt)):
                raise JudgeRunError("Observed generator prompt is malformed or unbounded.")
            observed = {"prompt_messages": prompt, "context_options": returned.get("context_options")}
        payload = {
            "review_id": report._review_id(source["run_id"], record["attempt_id"]),
            "target_attempt_id": record["attempt_id"],
            "hint_sha256": hashlib.sha256(hint.encode("utf-8")).hexdigest(),
            "question_text": context["question_text"],
            "student_answer": context["student_answer"],
            "reference_answer": reference.get("final_answer"),
            "equivalent_forms": reference.get("equivalent_forms") or [],
            "solution_steps": reference.get("solution_steps") or [],
            "expected_error": reference.get("expected_diagnosis"),
            "verification": {key: verification[key] for key in (
                "mathematics_status", "diagnosis_status", "method", "tool_and_version", "evidence_refs"
            ) if key in verification},
            "hint": hint,
            "diagnosis_hypothesis": hypothesis,
            "current_message": current_message,
            "turn_index": turn_index,
            "hint_level": level,
            "hint_policy": policy,
            "generator_rule_settings": settings,
            "observed_context": observed,
            "policy_mode": policy_mode,
            "stage": stage,
        }
        if judge_model:
            payload["judge_model"] = judge_model
        jobs.append({
            "review_id": payload["review_id"],
            "target_attempt_id": record["attempt_id"],
            "case_id": record.get("case_id"),
            "profile_id": record.get("profile_id"),
            "condition_id": record.get("condition_id", source.get("condition_id")),
            "turn_index": turn_index,
            "generator_model": generator_model,
            "hint_level": level,
            "policy_mode": policy_mode,
            "stage": stage,
            "repetition": record.get("repetition"),
            "policy_origin": policy_origin,
            "hint_policy_sha256": sha256_json(policy),
            "generator_config_sha256": returned.get("config_sha256"),
            "rules_id": observed_rules.get("rules_id"),
            "request_payload": payload,
            "request_sha256": sha256_json(payload),
        })
    timeout = http_timeout if http_timeout is not None else source.get("http_timeout", 420.0)
    if type(timeout) not in (int, float) or not 0 < timeout <= 900:
        raise JudgeRunError("HTTP timeout must be positive and at most 900 seconds.")
    manifest = {
        "schema_version": "1.0",
        "judge_run_id": judge_run_id,
        "source_run_id": source["run_id"],
        "execution_source": JUDGE_SOURCE,
        "planned_at_utc": _utc_now(),
        "base_url": _base_url(base_url or source["base_url"]),
        "http_timeout": timeout,
        "requested_judge_model": judge_model,
        "expected_configuration": expected,
        "rule_id": JUDGE_RULE_ID,
        "reference_authority": "task_derived_hypothesis_not_authoritative",
        "max_budget_units_per_hour": max_budget_units_per_hour,
        "budget": {"judge_cost": 2, "unweighted_generator_cost": 4, "scope": "serial_source_run_event_journals"},
        "counts": {"targets": len(jobs), "cases": len(selected_cases)},
        "hashes": {
            "source_manifest": sha256_file(run_dir / runner.MANIFEST_FILE),
            "source_generations": sha256_file(run_dir / runner.GENERATIONS_FILE),
            "source_fingerprint": runner._source_fingerprint(),
        },
    }
    inputs = directory / "inputs"
    inputs.mkdir(parents=True)
    _write_json(inputs / "source_manifest.json", source)
    for name, records in (("cases.jsonl", list(selected_cases.values())), ("targets.jsonl", targets), ("requests.jsonl", jobs)):
        for record in records:
            _append_jsonl(inputs / name, record)
    manifest["hashes"]["inputs"] = {path.name: sha256_file(path) for path in sorted(inputs.iterdir())}
    _write_json(directory / "manifest.json", manifest)
    return manifest


def _load_checked(run_dir: Path, judge_run_id: str) -> tuple:
    directory = _judge_dir(run_dir, judge_run_id)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    source = runner.load_manifest(run_dir)
    runner.verify_manifest(run_dir, source)
    hashes = manifest["hashes"]
    if (manifest.get("judge_run_id") != judge_run_id or manifest.get("source_run_id") != source["run_id"]
            or manifest.get("rule_id") != JUDGE_RULE_ID
            or hashes["source_fingerprint"] != runner._source_fingerprint()
            or hashes["source_manifest"] != sha256_file(run_dir / runner.MANIFEST_FILE)
            or hashes["source_generations"] != sha256_file(run_dir / runner.GENERATIONS_FILE)
            or any(sha256_file(directory / "inputs" / name) != digest for name, digest in hashes["inputs"].items())):
        raise JudgeRunError("Judge run/source identity changed; use matching sources or a new run.")
    for event in _read_jsonl(directory / "events.jsonl"):
        if event.get("manifest_sha256") and event["manifest_sha256"] != sha256_json(manifest):
            raise JudgeRunError("Judge manifest identity changed after execution began.")
        if event.get("runtime_sha256"):
            runtime_path = directory / "runtime_configuration.json"
            if not runtime_path.exists() or sha256_json(json.loads(runtime_path.read_text(encoding="utf-8"))) != event["runtime_sha256"]:
                raise JudgeRunError("Saved judge runtime configuration identity changed.")
    jobs = _read_jsonl(directory / "inputs" / "requests.jsonl")
    if len(jobs) != manifest["counts"]["targets"] or any(sha256_json(job["request_payload"]) != job["request_sha256"] for job in jobs):
        raise JudgeRunError("Judge request snapshot identity is invalid.")
    return directory, manifest, jobs


class JudgeRequestBudget:
    """Serial weighted budget reconstructed from generator and all judge journals."""

    def __init__(
        self, run_dir: Path, limit: int = 80,
        sleep: Callable[[float], None] = time.sleep,
        wall_clock: Callable[[], str] = _utc_now,
    ) -> None:
        if type(limit) is not int or not 2 <= limit <= 100:
            raise JudgeRunError("Weighted budget limit must be 2..100.")
        self.run_dir = Path(run_dir)
        self.limit = limit
        self.sleep = sleep
        self.wall_clock = wall_clock

    def wait_for_budget(self, cost: int) -> float:
        if type(cost) is not int or not 1 <= cost <= self.limit:
            raise JudgeRunError("Request cost exceeds the shared weighted budget.")
        waited = 0.0
        while True:
            now = datetime.fromisoformat(self.wall_clock())
            if now.tzinfo is None:
                raise JudgeRunError("Budget timestamps must include a timezone.")
            active = []
            paths = [self.run_dir / "events.jsonl"] + sorted((self.run_dir / "reviews" / "judge").glob("*/events.jsonl"))
            for path in paths:
                for event in _read_jsonl(path):
                    if event.get("event") != "attempt_started":
                        continue
                    units = event.get("budget_cost", 4 if path.parent == self.run_dir else 2)
                    try:
                        age = (now - datetime.fromisoformat(event["ts_utc"])).total_seconds()
                    except (KeyError, TypeError, ValueError) as error:
                        raise JudgeRunError("Invalid budget journal timestamp.") from error
                    if type(units) is not int or units < 1:
                        raise JudgeRunError("Invalid budget cost in the shared journal.")
                    if age < runner.BUDGET_WINDOW_SECONDS:
                        active.append((runner.BUDGET_WINDOW_SECONDS - max(age, 0.0), units))
            used = sum(units for _expiry, units in active)
            if used + cost <= self.limit:
                return waited
            delay = 0.0
            for expiry, units in sorted(active):
                used -= units
                delay = expiry
                if used + cost <= self.limit:
                    break
            self.sleep(max(delay, 0.001))
            waited += max(delay, 0.001)


def _request_transport(method: str, url: str, payload: Optional[dict], timeout: float) -> runner.TransportOutcome:
    import requests

    token = os.getenv("TUTOR_EVALUATION_TOKEN", "")
    if not token:
        raise JudgeRunError("TUTOR_EVALUATION_TOKEN is required for live evaluation requests.")
    try:
        response = requests.request(
            method, url, json=payload if method == "POST" else None,
            headers={"X-Evaluation-Token": token}, timeout=timeout,
            verify=True, allow_redirects=False,
        )
        if len(response.content) > MAX_RESPONSE_BYTES:
            return response.status_code, None, "invalid_response", "Response exceeds the size limit."
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


def _checked_judgement(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) - {"ratings", "diagnostic_question_quality", "diagnosis_match", "justification", "evidence"}:
        raise JudgeRunError("Invalid judgement object.")
    ratings = value.get("ratings")
    if not isinstance(ratings, dict) or set(ratings) != set(report.LIKERT_FIELDS + report.CHOICE_FIELDS):
        raise JudgeRunError("Judge ratings must contain every rubric field and no extras.")
    for field in report.LIKERT_FIELDS + ["diagnostic_question_quality"]:
        item = ratings[field] if field in ratings else value.get(field)
        if item is not None and (type(item) is not int or not 1 <= item <= 5):
            raise JudgeRunError("Invalid judge Likert rating.")
    for field in report.CHOICE_FIELDS + ["diagnosis_match"]:
        item = ratings[field] if field in ratings else value.get(field)
        if item is not None and item not in CHOICES:
            raise JudgeRunError("Invalid judge categorical rating.")
    reason = value.get("justification")
    evidence = value.get("evidence")
    if (not isinstance(reason, str) or len(reason) > 4000 or not isinstance(evidence, list)
            or len(evidence) > 12 or any(not isinstance(item, str) or len(item) > 1000 for item in evidence)):
        raise JudgeRunError("Invalid judge justification or evidence.")
    json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
    adverse = {
        "mat_falsch": "ja", "widerspruch_pruefergebnis": "ja", "erfundene_diagnose": "ja",
        "stufe_angemessen": "nein", "loesungsverrat_unzulaessig": "ja",
    }
    low = any(ratings[field] is not None and ratings[field] <= 2 for field in report.LIKERT_FIELDS)
    quality = value.get("diagnostic_question_quality")
    if (low or (quality is not None and quality <= 2) or value.get("diagnosis_match") == "nein"
            or any(ratings[field] == negative for field, negative in adverse.items())) and not reason.strip():
        raise JudgeRunError("Adverse judge findings require justification.")
    return {**value, "diagnostic_question_quality": quality, "diagnosis_match": value.get("diagnosis_match")}


def _checked_result(body: dict, job: dict, runtime: dict) -> dict:
    if not isinstance(body, dict) or len(json.dumps(body, ensure_ascii=False).encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise JudgeRunError("Invalid or oversized judge response.")
    request = job["request_payload"]
    for key in ("review_id", "target_attempt_id", "hint_sha256", "hint_level", "policy_mode", "stage"):
        if type(body.get(key)) is not type(request[key]) or body.get(key) != request[key]:
            raise JudgeRunError("Judge response target identity does not match.")
    for key in ("configuration", "config_sha256", "rule_id", "judge_parameters"):
        if body.get(key) != runtime["remote"][key]:
            raise JudgeRunError("Judge response configuration identity does not match.")
    model = body.get("judge_model")
    if model != runtime["selected_judge_model"] or model == job.get("generator_model"):
        raise JudgeRunError("Judge response model identity does not match the distinct selected alias.")
    if body.get("execution_source") != JUDGE_SOURCE or body.get("reference_authority") != "task_derived_hypothesis_not_authoritative":
        raise JudgeRunError("Judge provenance is missing or invalid.")
    verification = {
        "mathematics_status": "unknown", "diagnosis_status": "unknown", "method": None,
        "tool_and_version": None, "evidence_refs": [], **(request.get("verification") or {}),
    }
    if body.get("verification") != verification:
        raise JudgeRunError("Judge response altered the reported verification evidence.")
    messages = body.get("prompt_messages")
    if (not isinstance(messages, list) or len(messages) != 2
            or [message.get("role") if isinstance(message, dict) else None for message in messages] != ["system", "user"]
            or any(set(message) != {"role", "content"} or not isinstance(message["content"], str)
                   or not message["content"] or len(message["content"]) > 200000 for message in messages)):
        raise JudgeRunError("Actual judge prompt evidence is missing or malformed.")
    judgement = _checked_judgement(body.get("judgement"))
    if request["stage"] == "hint" and judgement["diagnostic_question_quality"] is not None:
        raise JudgeRunError("Diagnostic quality does not apply to a hint-stage output.")
    raw = body.get("raw_response")
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 32768:
        raise JudgeRunError("Raw structured judge response is missing or too large.")
    try:
        if _checked_judgement(json.loads(raw)) != _checked_judgement(body["judgement"]):
            raise JudgeRunError("Raw judge response and validated judgement differ.")
    except (ValueError, TypeError, RecursionError) as error:
        raise JudgeRunError("Raw judge response is invalid JSON.") from error
    generation = body.get("generation")
    params = runtime["remote"]["judge_parameters"]
    if (not isinstance(generation, dict) or generation.get("requested_model") != model
            or generation.get("model_alias") != model
            or generation.get("requested_temperature") != params["temperature"]
            or generation.get("requested_max_tokens") != params["max_tokens"]
            or generation.get("json_output") is not True):
        raise JudgeRunError("Judge generation telemetry does not match requested settings.")
    return body


def execute_judge_run(
    run_dir: Path,
    judge_run_id: str,
    *,
    execute_live: bool = False,
    resume: bool = False,
    retry_failed: bool = False,
    transport: Optional[Callable] = None,
    budget: Optional[object] = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    wall_clock: Callable[[], str] = _utc_now,
) -> dict:
    """Judge serially with a live gate, durable starts and no automatic retries.

    GET /api/evaluation/config is the only preflight (no LLM call). Its public
    identity is pinned separately on first execution and checked on resume and
    every POST response. Known HTTP failures require explicit retry_failed;
    ambiguous or invalid-protocol attempts are never replayed.
    """
    if not execute_live:
        raise JudgeRunError("Judge execution requires explicit execute_live=True; no request was sent.")
    run_dir = Path(run_dir).resolve()
    directory, manifest, jobs = _load_checked(run_dir, judge_run_id)
    dispatch = transport or _request_transport
    if transport is None and not os.getenv("TUTOR_EVALUATION_TOKEN", ""):
        raise JudgeRunError("TUTOR_EVALUATION_TOKEN is required for live evaluation requests.")
    events = _read_jsonl(directory / "events.jsonl")
    results = [item for item in _read_jsonl(directory / RESULTS_FILE) if item.get("execution_source") == JUDGE_SOURCE]
    if not resume and (results or any(event.get("event") == "attempt_started" for event in events)):
        raise JudgeRunError("Judge attempts already exist; explicitly resume this run.")
    job_by_review = {job["review_id"]: job for job in jobs}
    finished = {result["attempt_id"] for result in results}
    repaired = 0
    for event in events:
        if event.get("event") != "attempt_started" or event["attempt_id"] in finished:
            continue
        result = {
            **{key: event.get(key) for key in ("attempt_id", "review_id", "target_attempt_id", "request_sha256")},
            "execution_source": JUDGE_SOURCE, "outcome": "transport_ambiguous",
            "started_at_utc": event["ts_utc"], "finished_at_utc": wall_clock(),
            "judge_http_status": None, "duration_ms": None, "returned": None,
            "safe_error": "An in-flight attempt has an unknown outcome; it will not be replayed.",
        }
        _append_jsonl(directory / RESULTS_FILE, result)
        _append_jsonl(directory / "events.jsonl", {"event": "attempt_finished", "attempt_id": event["attempt_id"], "outcome": result["outcome"], "ts_utc": wall_clock()})
        results.append(result)
        finished.add(event["attempt_id"])
        repaired += 1
    outcomes = {}
    last_attempt = {}
    for result in results:
        review_id = result["review_id"]
        if review_id not in job_by_review:
            raise JudgeRunError("A judge journal result references an unknown target.")
        candidate = "transport_ambiguous" if result["outcome"] == "invalid_response" else result["outcome"]
        outcomes[review_id] = runner._best_outcome(outcomes.get(review_id), candidate)
        last_attempt[review_id] = result["attempt_id"]
    retryable = {"http_error", "server_error", "rate_limited"}
    pending = [job for job in jobs if job["review_id"] not in outcomes
               or (retry_failed and outcomes[job["review_id"]] in retryable)]
    stats = {
        "judge_run_id": judge_run_id, "planned": len(jobs), "dispatched": 0,
        "success": 0, "http_error": 0, "server_error": 0, "rate_limited": 0,
        "transport_ambiguous": 0, "invalid_response": 0,
        "skipped_completed": sum(outcome == "success" for outcome in outcomes.values()),
        "skipped_failed": len(jobs) - len(pending) - sum(outcome == "success" for outcome in outcomes.values()),
        "in_flight_repaired": repaired, "budget_waits_seconds": 0.0,
    }
    if not pending:
        return stats
    manifest_hash = sha256_json(manifest)
    _append_jsonl(directory / "events.jsonl", {"event": "configuration_requested", "manifest_sha256": manifest_hash, "ts_utc": wall_clock()})
    try:
        status, body, error, _detail = dispatch("GET", manifest["base_url"] + "/api/evaluation/config", None, float(manifest["http_timeout"]))
    except Exception:
        raise JudgeRunError("Protected evaluation configuration preflight transport failed.") from None
    if status != 200 or error is not None:
        raise JudgeRunError("Protected evaluation configuration preflight failed (HTTP " + str(status) + ").")
    remote = _checked_configuration(body)
    if manifest.get("expected_configuration") is not None and remote != manifest["expected_configuration"]:
        raise JudgeRunError("Observed server configuration differs from the prepared identity.")
    if not remote["judge_model"]:
        raise JudgeRunError("The server must configure an explicit evaluation judge model.")
    model = manifest.get("requested_judge_model") or remote["judge_model"]
    if any(not job.get("generator_model") or model == job["generator_model"] for job in pending):
        raise JudgeRunError("A distinct judge requires a known, different saved generator alias for every target.")
    runtime = {"remote": remote, "selected_judge_model": model}
    runtime_path = directory / "runtime_configuration.json"
    if runtime_path.exists():
        if json.loads(runtime_path.read_text(encoding="utf-8")) != runtime:
            raise JudgeRunError("Judge server configuration/model changed; resume is forbidden.")
    else:
        _write_json(runtime_path, runtime)
    runtime_hash = sha256_json(runtime)
    if any(event.get("runtime_sha256") and event["runtime_sha256"] != runtime_hash for event in events):
        raise JudgeRunError("Saved judge runtime identity changed.")
    _append_jsonl(directory / "events.jsonl", {"event": "configuration_observed", "runtime_sha256": runtime_hash, "manifest_sha256": manifest_hash, "ts_utc": wall_clock()})
    limiter = budget or JudgeRequestBudget(run_dir, manifest["max_budget_units_per_hour"], sleep=sleep, wall_clock=wall_clock)
    for job in pending:
        waited = limiter.wait_for_budget(2)
        stats["budget_waits_seconds"] += waited
        attempt_id = "judge-" + uuid.uuid4().hex[:16]
        started = wall_clock()
        event = {
            "event": "attempt_started", "request_kind": "judge", "budget_cost": 2,
            "execution_source": JUDGE_SOURCE, "attempt_id": attempt_id,
            "review_id": job["review_id"], "target_attempt_id": job["target_attempt_id"],
            "request_sha256": job["request_sha256"], "requested_model": model,
            "manifest_sha256": manifest_hash, "runtime_sha256": runtime_hash,
            "ts_utc": started,
        }
        _append_jsonl(directory / "events.jsonl", event)
        started_clock = clock()
        safe_error = None
        returned = None
        try:
            status, body, error, _detail = dispatch("POST", manifest["base_url"] + "/api/evaluation/judge", job["request_payload"], float(manifest["http_timeout"]))
            if error is not None or status is None:
                outcome = "invalid_response" if status == 200 else "transport_ambiguous"
            elif status == 200:
                try:
                    returned = _checked_result(body, job, runtime)
                    outcome = "success"
                except (JudgeRunError, ValueError, TypeError, RecursionError):
                    outcome = "invalid_response"
            elif status == 429:
                outcome = "rate_limited"
            elif status >= 500:
                outcome = "server_error"
            else:
                outcome = "http_error"
        except Exception:
            status = None
            outcome = "transport_ambiguous"
        if outcome != "success":
            safe_error = "Judge attempt outcome: " + outcome + "; HTTP " + str(status) + ". No upstream body or credential was retained."
        result = {
            "schema_version": "1.0", "judge_run_id": judge_run_id,
            "attempt_id": attempt_id, "review_id": job["review_id"],
            "target_attempt_id": job["target_attempt_id"], "request_sha256": job["request_sha256"],
            "hint_sha256": job["request_payload"]["hint_sha256"],
            "execution_source": JUDGE_SOURCE, "outcome": outcome,
            "started_at_utc": started, "finished_at_utc": wall_clock(),
            "duration_ms": int((clock() - started_clock) * 1000),
            "judge_http_status": status, "returned": returned, "safe_error": safe_error,
            "retry_of_attempt_id": last_attempt.get(job["review_id"]) if retry_failed else None,
            "runtime_sha256": runtime_hash,
        }
        _append_jsonl(directory / RESULTS_FILE, result)
        _append_jsonl(directory / "events.jsonl", {"event": "attempt_finished", "attempt_id": attempt_id, "outcome": outcome, "ts_utc": wall_clock()})
        stats["dispatched"] += 1
        stats[outcome] += 1
    return stats


def _write_csv(path: Path, rows: List[dict], columns: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def summarize_judgements(run_dir: Path, judge_run_id: str, *, compare_humans: bool = False) -> dict:
    """Write separate criterion CSV/Markdown and optional human disagreement rows.

    Failures stay technical attempts; only latest valid live judge successes enter
    content statistics. Human ratings are read, never written, pooled or imported.
    Missing, uncertain and not-applicable values have separate denominators.
    """
    run_dir = Path(run_dir).resolve()
    directory, manifest, jobs = _load_checked(run_dir, judge_run_id)
    results = [item for item in _read_jsonl(directory / RESULTS_FILE) if item.get("execution_source") == JUDGE_SOURCE]
    runtime_path = directory / "runtime_configuration.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8")) if runtime_path.exists() else None
    job_by_review = {job["review_id"]: job for job in jobs}
    successes = {}
    for result in results:
        if result.get("outcome") != "success":
            continue
        job = job_by_review.get(result.get("review_id"))
        if job is None or runtime is None:
            raise JudgeRunError("A successful judge result has no matching frozen target/runtime.")
        _checked_result(result.get("returned"), job, runtime)
        if result.get("runtime_sha256") != sha256_json(runtime):
            raise JudgeRunError("Successful judge result runtime identity changed.")
        successes[job["review_id"]] = result
    judge_model = runtime["selected_judge_model"] if runtime else manifest.get("requested_judge_model") or "unknown"
    groups = defaultdict(list)
    for job in jobs:
        groups[(
            job.get("generator_model") or "unknown", judge_model, job.get("profile_id") or "unknown",
            job.get("condition_id") or "unknown", job.get("turn_index"), job["hint_level"],
            job["policy_mode"], job["stage"], job["hint_policy_sha256"],
            job.get("generator_config_sha256") or "unknown", job.get("rules_id") or "unknown",
        )].append(job)
    summary = []
    identity_columns = ["generator_model", "judge_model", "profile_id", "condition_id", "turn_index", "hint_level", "policy_mode", "stage", "hint_policy_sha256", "generator_config_sha256", "rules_id"]
    numeric_fields = report.LIKERT_FIELDS + ["diagnostic_question_quality"]
    for key, group in sorted(groups.items(), key=lambda item: tuple(str(value) for value in item[0])):
        judgements = [successes[job["review_id"]]["returned"]["judgement"] for job in group if job["review_id"] in successes]
        for field in numeric_fields + report.CHOICE_FIELDS + ["diagnosis_match"]:
            values = [item["ratings"].get(field) if field in report.LIKERT_FIELDS + report.CHOICE_FIELDS else item.get(field) for item in judgements]
            observed = [value for value in values if value is not None]
            row = {
                **dict(zip(identity_columns, key)), "criterion": field,
                "N_targets": len(group), "N_success": len(judgements),
                "targets_missing_judgement": len(group) - len(judgements),
                "n_observed": len(observed), "n_missing": len(values) - len(observed),
                "median": statistics.median(observed) if observed and field in numeric_fields else None,
                "mean": statistics.mean(observed) if observed and field in numeric_fields else None,
                **{choice + "_n": values.count(choice) for choice in CHOICES},
            }
            summary.append(row)
    disagreements = []
    if compare_humans:
        _source, _generations, _checks, humans = report._load_run_core(run_dir)
        for human in humans:
            success = successes.get(human.get("review_id"))
            if success is None or human.get("attempt_id") != success["target_attempt_id"]:
                continue
            judgement = success["returned"]["judgement"]
            for field in report.LIKERT_FIELDS + report.CHOICE_FIELDS:
                judge_value = judgement["ratings"].get(field)
                human_value = (human.get("ratings") or {}).get(field)
                if human_value is None or judge_value is None:
                    continue
                numeric = type(judge_value) is int and type(human_value) is int
                comparable = numeric or (judge_value in {"ja", "nein"} and human_value in {"ja", "nein"})
                disagreements.append({
                    "review_id": human["review_id"], "target_attempt_id": human["attempt_id"],
                    "rater_id": human["rater_id"], "judge_model": judge_model,
                    "condition_id": job_by_review[human["review_id"]].get("condition_id"),
                    "turn_index": job_by_review[human["review_id"]].get("turn_index"),
                    "criterion": field, "judge_value": judge_value, "human_value": human_value,
                    "comparable": comparable, "disagrees": judge_value != human_value if comparable else None,
                    "likert_delta": judge_value - human_value if numeric else None,
                })
    rated = sum(any(value is not None for value in item["returned"]["judgement"]["ratings"].values())
                or item["returned"]["judgement"].get("diagnostic_question_quality") is not None for item in successes.values())
    coverage = {
        "targets": len(jobs), "judge_attempts": len(results), "successful_judgements": len(successes),
        "targets_missing_judgement": len(jobs) - len(successes), "responses_with_ratings": rated,
        "responses_without_ratings": len(jobs) - rated,
        "targets_without_observed_context": sum(job["request_payload"]["observed_context"] is None for job in jobs),
        "human_pairs": len(disagreements),
        "human_comparable_pairs": sum(item["comparable"] for item in disagreements),
        "human_disagreements": sum(item["disagrees"] is True for item in disagreements),
    }
    derived = directory / "derived"
    derived.mkdir(exist_ok=True)
    columns = identity_columns + ["criterion", "N_targets", "N_success", "targets_missing_judgement", "n_observed", "n_missing", "median", "mean"] + [choice + "_n" for choice in CHOICES]
    _write_csv(derived / "judge_summary.csv", summary, columns)
    _write_csv(derived / "expert_disagreements.csv", disagreements, ["review_id", "target_attempt_id", "rater_id", "judge_model", "condition_id", "turn_index", "criterion", "judge_value", "human_value", "comparable", "disagrees", "likert_delta"])
    lines = [
        "# Second-model judgements: " + judge_run_id, "",
        "Model ratings are separate from human ratings and are not mathematical verification.",
        "References and expected errors are task-derived hypotheses, not authoritative PRT verdicts.",
        "No compensating overall grade. Repetitions are not independent tasks.", "", "## Coverage", "",
    ]
    lines.extend("- " + key + ": " + str(value) for key, value in coverage.items())
    lines.extend(["", "## Technical Outcomes", ""])
    lines.extend("- " + key + ": " + str(value) for key, value in sorted(Counter(item.get("outcome", "unknown") for item in results).items()))
    lines.extend(["", "## Criteria", "", "N_targets includes missing/failed judgements; N_success includes only valid live results.", "Missing values are not passed. unklar and nicht_anwendbar remain separate.", "", "| Generator | Judge | Profile | Condition | Turn | Level | Mode | Stage | Policy SHA256 | Generator Config | Rules ID | Criterion | n/N_success | N_targets | Median | ja | nein | unklar | nicht_anwendbar | Missing |", "|---|---|---|---|---:|---:|---|---|---|---|---|---|---|---:|---|---:|---:|---:|---:|---:|"])
    for row in summary:
        cells = [row[column] for column in identity_columns] + [row["criterion"], str(row["n_observed"]) + "/" + str(row["N_success"]), row["N_targets"], row["median"]] + [row[choice + "_n"] for choice in CHOICES] + [row["n_missing"]]
        lines.append("| " + " | ".join(str(cell).replace("|", "\\|").replace("\n", " ") if cell is not None else "unknown" for cell in cells) + " |")
    lines.extend(["", "## Limits", "", "- No offline/demo/mock outputs contribute to judge content metrics.", "- Missing observed generator prompts remain unknown; they are never reconstructed.", "- Model aliases are observed/requested aliases, not provider model digests.", "- Provider attempts, token usage and effective thinking mode remain unknown unless returned.", "- Budgets cover serial generator/judge journals of this source run, not other provider-key users.", "- Human comparison rows are separate paired observations, not pooled ratings or calibration evidence.", ""])
    path = derived / "judge_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return {"coverage": coverage, "summary_rows": len(summary), "report_path": str(path), "summary_path": str(derived / "judge_summary.csv"), "disagreements_path": str(derived / "expert_disagreements.csv")}
