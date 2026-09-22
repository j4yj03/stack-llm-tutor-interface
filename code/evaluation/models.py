"""Strenge Datenmodelle der Evaluationssuite.

Alle Modelle weisen unbekannte Felder zurück (`extra="forbid"`), damit
Tippfehler in Experiment-/Korpusdateien nicht stillschweigend ignoriert
werden. Das Paket importiert nicht `app.main`; die Feldgrenzen spiegeln
die bekannten Servergrenzen wider, damit geplante Requests bereits hier
validiert werden.
"""

import re
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1.0"

# Die zehn Kontextschalter der Tutor-API (Reihenfolge = Prompt-Semantik).
PROFILE_FLAG_NAMES = [
    "include_question_text",
    "include_student_answer",
    "include_diagnosis_code",
    "include_prt_feedback",
    "include_score",
    "include_learning_goals",
    "include_math_rules",
    "include_solution_steps",
    "include_final_answer",
    "include_chat_history",
]

_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]*$")


def _require_id(value: str) -> str:
    if not _ID_PATTERN.match(value):
        raise ValueError(
            "ID darf nur Buchstaben, Ziffern, Unterstrich und Bindestrich "
            "enthalten und muss mit Buchstabe/Ziffer beginnen: " + repr(value)
        )
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ContextProfile(StrictModel):
    """Volständige Kontextbedingung: alle zehn Schalter explizit."""

    profile_id: str
    description: str = ""
    include_question_text: bool
    include_student_answer: bool
    include_diagnosis_code: bool
    include_prt_feedback: bool
    include_score: bool
    include_learning_goals: bool
    include_math_rules: bool
    include_solution_steps: bool
    include_final_answer: bool
    include_chat_history: bool

    @field_validator("profile_id")
    @classmethod
    def _check_profile_id(cls, value: str) -> str:
        return _require_id(value)

    def flags(self) -> dict:
        return {name: getattr(self, name) for name in PROFILE_FLAG_NAMES}


class ContextProfileSet(StrictModel):
    schema_version: str
    profiles: List[ContextProfile]

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(
                "Erwartete schema_version " + SCHEMA_VERSION + ", erhalten: "
                + repr(value)
            )
        return value

    def by_id(self) -> dict:
        return {profile.profile_id: profile for profile in self.profiles}


class CaseInstanceMeta(StrictModel):
    instance_id: Optional[str] = None
    seed: Optional[int] = None
    variable: str = "x"
    domain_assumptions: List[str] = Field(default_factory=list)


class CaseReference(StrictModel):
    """Bewertungsreferenz: niemals Teil eines Tutor-Requests."""

    expected_input_validity: Optional[str] = None
    expected_correctness: Optional[str] = None
    final_answer: Optional[str] = None
    equivalent_forms: List[str] = Field(default_factory=list)
    solution_steps: List[str] = Field(default_factory=list)
    expected_diagnosis: Optional[str] = None

    @field_validator("expected_input_validity")
    @classmethod
    def _check_validity(cls, value: Optional[str]) -> Optional[str]:
        allowed = {None, "valid", "invalid", "unknown"}
        if value not in allowed:
            raise ValueError(
                "expected_input_validity muss valid|invalid|unknown sein"
            )
        return value

    @field_validator("expected_correctness")
    @classmethod
    def _check_correctness(cls, value: Optional[str]) -> Optional[str]:
        allowed = {None, "correct", "incorrect", "unknown"}
        if value not in allowed:
            raise ValueError(
                "expected_correctness muss correct|incorrect|unknown sein"
            )
        return value


class CaseVerification(StrictModel):
    """Prüfstatus; Forschungseignung wird daraus abgeleitet."""

    mathematics_status: str = "pending"
    diagnosis_status: str = "pending"
    method: Optional[str] = None
    tool_and_version: Optional[str] = None
    reviewer_id: Optional[str] = None
    evidence_refs: List[str] = Field(default_factory=list)

    @field_validator("mathematics_status", "diagnosis_status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        allowed = {"pending", "verified", "rejected"}
        if value not in allowed:
            raise ValueError("Prüfstatus muss pending|verified|rejected sein")
        return value


class CaseProvenance(StrictModel):
    response_origin: str
    question_export_ref: Optional[str] = None
    instantiated_task_ref: Optional[str] = None
    prt_test_result_ref: Optional[str] = None
    student_attempt_ref: Optional[str] = None


class CaseEvaluationOnly(StrictModel):
    instance: CaseInstanceMeta = Field(default_factory=CaseInstanceMeta)
    reference: CaseReference = Field(default_factory=CaseReference)
    verification: CaseVerification = Field(default_factory=CaseVerification)
    provenance: CaseProvenance


class CaseTutorContext(StrictModel):
    """Verfügbare Eingaben; das Experiment wählt per Profil davon aus."""

    question_id: str
    question_text: str = Field(min_length=1)
    student_answer: str = Field(min_length=1)
    diagnosis_code: Optional[str] = Field(None, max_length=200)
    prt_feedback: Optional[str] = Field(None, max_length=5000)
    score: Optional[float] = Field(None, ge=0.0, le=1.0)
    seed: Optional[int] = None
    learning_goals: List[str] = Field(default_factory=list)
    math_rules: List[str] = Field(default_factory=list)
    solution_steps: List[str] = Field(default_factory=list)
    final_answer: Optional[str] = None

    @field_validator("question_id")
    @classmethod
    def _check_question_id(cls, value: str) -> str:
        return _require_id(value)


class Case(StrictModel):
    schema_version: str
    case_id: str
    readiness: str
    tags: List[str] = Field(default_factory=list)
    task_instance_id: Optional[str] = None
    tutor_context: CaseTutorContext
    evaluation_only: CaseEvaluationOnly

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(
                "Erwartete schema_version " + SCHEMA_VERSION + ", erhalten: "
                + repr(value)
            )
        return value

    @field_validator("case_id")
    @classmethod
    def _check_case_id(cls, value: str) -> str:
        return _require_id(value)

    @field_validator("readiness")
    @classmethod
    def _check_readiness(cls, value: str) -> str:
        allowed = {"draft", "review", "released"}
        if value not in allowed:
            raise ValueError("readiness muss draft|review|released sein")
        return value

    def is_mathematics_verified(self) -> bool:
        return self.evaluation_only.verification.mathematics_status == (
            "verified"
        )

    def is_research_eligible(self, allow_unverified_cases: bool) -> bool:
        """Forschungseignung aus Prüfstatus ableiten, nicht aus readiness."""
        if allow_unverified_cases:
            return True
        return self.is_mathematics_verified()


class ControlJob(StrictModel):
    case_id: str
    profile_id: str
    hint_level: int = Field(ge=1, le=4)
    repetitions: int = Field(1, ge=1, le=10)


class Experiment(StrictModel):
    schema_version: str
    experiment_id: str
    protocol_version: str
    description: str = ""
    corpus_file: str
    profiles: List[str]
    hint_levels: List[int]
    repetitions: int = Field(1, ge=1, le=10)
    # Leere Liste/null-Einträge: Modellfeld wird im Request weggelassen
    # (Server-Default). Jeder nichtleere Eintrag muss zur Server-Allowlist
    # passen; das prüft erst der Lauf gegen die reale Instanz.
    models: List[Optional[str]] = Field(default_factory=list)
    control_jobs: List[ControlJob] = Field(default_factory=list)
    max_generations_per_hour: int = Field(35, ge=1, le=1000)
    order_seed: int = 0
    allow_unverified_cases: bool = False

    @field_validator("schema_version")
    @classmethod
    def _check_version(cls, value: str) -> str:
        if value != SCHEMA_VERSION:
            raise ValueError(
                "Erwartete schema_version " + SCHEMA_VERSION + ", erhalten: "
                + repr(value)
            )
        return value

    @field_validator("experiment_id", "protocol_version")
    @classmethod
    def _check_ids(cls, value: str) -> str:
        return _require_id(value)

    @field_validator("hint_levels")
    @classmethod
    def _check_levels(cls, value: List[int]) -> List[int]:
        if not value:
            raise ValueError("hint_levels darf nicht leer sein")
        for level in value:
            if not 1 <= level <= 4:
                raise ValueError(
                    "Hilfestufen müssen zwischen 1 und 4 liegen: " + repr(level)
                )
        return sorted(set(value))
