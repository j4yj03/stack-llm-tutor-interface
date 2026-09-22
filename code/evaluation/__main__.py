"""CLI der Evaluationssuite.

Alle Befehle sind offline sicher bis auf `run`, das eine explizite
Live-Freigabe verlangt. Arbeitsverzeichnis: code/ (Paket `evaluation`).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List

from evaluation.corpus import (
    CorpusError,
    load_cases,
    load_experiment,
    load_profiles,
    validate_experiment,
)
from evaluation.report import (
    build_report,
    export_review_packet,
    import_review_ratings,
)
from evaluation.runner import Runner, RunnerError, create_run

EVAL_DIR = Path(__file__).resolve().parent
DEFAULT_CASES = EVAL_DIR / "data" / "example_cases.jsonl"
DEFAULT_PROFILES = EVAL_DIR / "data" / "context_profiles.json"
DEFAULT_EXPERIMENT = EVAL_DIR / "experiments" / "pilot.json"


def _print_json(payload) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _fail(message: str) -> int:
    print("FEHLER: " + message, file=sys.stderr)
    return 2


def cmd_validate(args: argparse.Namespace) -> int:
    """Prüft Korpus, Profile und Experiment (offline, kein Netz)."""
    try:
        cases = load_cases(Path(args.cases))
        profile_set = load_profiles(Path(args.profiles))
        experiment = load_experiment(Path(args.experiment))
        errors: List[str] = validate_experiment(
            experiment, cases, profile_set
        )
    except (CorpusError, FileNotFoundError) as error:
        return _fail(str(error))
    if errors:
        print("Experiment unbelegbar:")
        for error in errors:
            print("- " + error, file=sys.stderr)
        return 2
    unverified = sum(
        1 for case in cases if not case.is_mathematics_verified()
    )
    _print_json({
        "ok": True,
        "cases": len(cases),
        "cases_mathematics_verified": len(cases) - unverified,
        "cases_unverified": unverified,
        "profiles": [
            profile.profile_id for profile in profile_set.profiles
        ],
        "experiment_id": experiment.experiment_id,
        "allow_unverified_cases": experiment.allow_unverified_cases,
        "note": (
            "Vor einem fachlichen Lauf müssen die verifizierten Fälle "
            "belegt sein (verification/Belegreferenzen)."
        ),
    })
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """Erzeugt Manifest und Plan (offline, deterministisch)."""
    run_dir = Path(args.run_dir)
    if run_dir.exists() and any(run_dir.iterdir()):
        return _fail(
            "Run-Verzeichnis ist nicht leer: " + str(run_dir)
            + " (neue run-id wählen oder --resume nutzen)."
        )
    try:
        manifest = create_run(
            run_dir=run_dir,
            experiment_path=Path(args.experiment),
            corpus_path=Path(args.cases),
            profiles_path=Path(args.profiles),
            base_url=args.base_url.rstrip("/"),
            http_timeout=float(args.http_timeout),
        )
    except (CorpusError, FileNotFoundError, ValueError) as error:
        return _fail(str(error))
    print(
        "Plan erstellt: " + str(run_dir)
        + " · Jobs: " + str(manifest["counts"]["jobs"])
        + " · Ausschlüsse: " + str(manifest["counts"]["exclusions"])
    )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Führt den Plan aus; erfordert --execute-live."""
    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        return _fail("Run-Verzeichnis fehlt: " + str(run_dir))
    try:
        runner = Runner(run_dir=run_dir)
        stats = runner.run(
            execute_live=args.execute_live,
            resume=args.resume,
            retry_failed=args.retry_failed,
        )
    except (RunnerError, OSError, ValueError) as error:
        return _fail(str(error))
    _print_json(stats)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    """Führt automatische Prüfungen über gespeicherte Antworten aus."""
    from evaluation.checks import run_checks_for_run

    try:
        result = run_checks_for_run(Path(args.run_dir))
    except (RunnerError, FileNotFoundError, OSError) as error:
        return _fail(str(error))
    print(
        "Checks geschrieben: " + result["path"]
        + " · Datensätze: " + str(result["records"])
        + " · fehlgeschlagen: " + str(result["failed"])
    )
    return 0


def cmd_review_export(args: argparse.Namespace) -> int:
    try:
        result = export_review_packet(
            Path(args.run_dir),
            limit=args.limit,
        )
    except (FileNotFoundError, ValueError, OSError) as error:
        return _fail(str(error))
    _print_json(result)
    return 0


def cmd_review_import(args: argparse.Namespace) -> int:
    try:
        result = import_review_ratings(
            Path(args.run_dir), Path(args.file)
        )
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as error:
        return _fail(str(error))
    if result["errors"]:
        print("Hinweise beim Import:", file=sys.stderr)
        for error in result["errors"][:20]:
            print("- " + error, file=sys.stderr)
    _print_json({
        "imported": result["imported"],
        "saved": result["records"],
        "error_count": len(result["errors"]),
    })
    return 0 if result["imported"] > 0 else 2


def cmd_report(args: argparse.Namespace) -> int:
    try:
        result = build_report(Path(args.run_dir))
    except (FileNotFoundError, ValueError, OSError) as error:
        return _fail(str(error))
    _print_json(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m evaluation",
        description=(
            "Evaluations-Suite für den KI-Tutor: korpusbasierte, "
            "reproduzierbare Tutor-API-Experimente."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    default_profile_args = {
        "cases": str(DEFAULT_CASES),
        "profiles": str(DEFAULT_PROFILES),
        "experiment": str(DEFAULT_EXPERIMENT),
    }

    validate_parser = subparsers.add_parser(
        "validate", help="Korpus/Profile/Experiment strikt prüfen (offline)"
    )
    validate_parser.add_argument("--cases", default=default_profile_args["cases"])
    validate_parser.add_argument("--profiles", default=default_profile_args["profiles"])
    validate_parser.add_argument("--experiment", default=default_profile_args["experiment"])
    validate_parser.set_defaults(func=cmd_validate)

    plan_parser = subparsers.add_parser(
        "plan", help="Manifest + deterministischen Plan erzeugen (offline)"
    )
    plan_parser.add_argument("--cases", default=default_profile_args["cases"])
    plan_parser.add_argument("--profiles", default=default_profile_args["profiles"])
    plan_parser.add_argument("--experiment", default=default_profile_args["experiment"])
    plan_parser.add_argument("--run-dir", required=True)
    plan_parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    plan_parser.add_argument("--http-timeout", type=float, default=420.0)
    plan_parser.set_defaults(func=cmd_plan)

    run_parser = subparsers.add_parser(
        "run", help="Geplante Jobs gegen die Tutor-API ausführen"
    )
    run_parser.add_argument("--run-dir", required=True)
    run_parser.add_argument(
        "--execute-live", action="store_true",
        help="Explizite Freigabe: echte API-Aufrufe (Rate-Limit beachten)",
    )
    run_parser.add_argument(
        "--resume", action="store_true",
        help="Offene Jobs fortsetzen; Identität wird verifiziert",
    )
    run_parser.add_argument(
        "--retry-failed", action="store_true",
        help="Explizit fehlgeschlagene (nicht unklare) Jobs erneut senden",
    )
    run_parser.set_defaults(func=cmd_run)

    check_parser = subparsers.add_parser(
        "check", help="Automatische Prüfungen für gespeicherte Antworten"
    )
    check_parser.add_argument("--run-dir", required=True)
    check_parser.set_defaults(func=cmd_check)

    review_export_parser = subparsers.add_parser(
        "review-export", help="Neutralen Bewertungsbogen exportieren"
    )
    review_export_parser.add_argument("--run-dir", required=True)
    review_export_parser.add_argument("--limit", type=int, default=None)
    review_export_parser.set_defaults(func=cmd_review_export)

    review_import_parser = subparsers.add_parser(
        "review-import", help="Ausgefüllte Bewertungen importieren"
    )
    review_import_parser.add_argument("--run-dir", required=True)
    review_import_parser.add_argument("--file", required=True)
    review_import_parser.set_defaults(func=cmd_review_import)

    report_parser = subparsers.add_parser(
        "report", help="Zusammenfassung, Paarvergleiche und Bericht"
    )
    report_parser.add_argument("--run-dir", required=True)
    report_parser.set_defaults(func=cmd_report)

    return parser


def main(argv: List[str] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
