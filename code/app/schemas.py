from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from app.config import (
    CONTEXT_OPTIONS_ENABLED,
    MAX_CHAT_MESSAGE_LENGTH,
    MAX_CONTEXT_QUESTION_TEXT,
    MAX_HINT_LEVEL,
    MAX_QUESTION_TEXT_LENGTH,
    MAX_STUDENT_ANSWER_LENGTH
)


class ContextOptions(BaseModel):
    # Defaultwerte aus CONTEXT_OPTIONS in der .env (Keys ohne "include_").
    include_question_text: bool = CONTEXT_OPTIONS_ENABLED[
        "question_text"
    ]
    include_student_answer: bool = CONTEXT_OPTIONS_ENABLED[
        "student_answer"
    ]
    include_diagnosis_code: bool = CONTEXT_OPTIONS_ENABLED[
        "diagnosis_code"
    ]
    include_prt_feedback: bool = CONTEXT_OPTIONS_ENABLED[
        "prt_feedback"
    ]
    include_score: bool = CONTEXT_OPTIONS_ENABLED["score"]
    include_learning_goals: bool = CONTEXT_OPTIONS_ENABLED[
        "learning_goals"
    ]
    include_math_rules: bool = CONTEXT_OPTIONS_ENABLED[
        "math_rules"
    ]
    include_solution_steps: bool = CONTEXT_OPTIONS_ENABLED[
        "solution_steps"
    ]
    include_final_answer: bool = CONTEXT_OPTIONS_ENABLED[
        "final_answer"
    ]
    include_chat_history: bool = CONTEXT_OPTIONS_ENABLED[
        "chat_history"
    ]


class StackContext(BaseModel):
    question_id: str = Field(
        ...,
        min_length=1,
        max_length=200
    )
    question_text: str = Field(
        ...,
        min_length=1,
        # Preserve existing API payloads and persisted chats (previously 10000).
        max_length=MAX_CONTEXT_QUESTION_TEXT
    )
    student_answer: str = Field(
        ...,
        min_length=1,
        max_length=MAX_STUDENT_ANSWER_LENGTH
    )
    diagnosis_code: Optional[str] = Field(
        None,
        max_length=200
    )
    prt_feedback: Optional[str] = Field(
        None,
        max_length=5000
    )
    score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0
    )
    seed: Optional[int] = None
    learning_goals: List[str] = Field(
        default_factory=list
    )
    math_rules: List[str] = Field(
        default_factory=list
    )
    solution_steps: List[str] = Field(
        default_factory=list
    )
    final_answer: Optional[str] = None
    diagnosis_source: Optional[Literal["synthetic", "provided", "prt", "stack", "stack_prt", "unknown"]] = None


class TutorRequest(BaseModel):
    stack: StackContext
    chat_id: Optional[str] = None
    user_message: Optional[str] = Field(
        None,
        max_length=MAX_CHAT_MESSAGE_LENGTH
    )
    hint_level: Optional[int] = Field(
        None,
        ge=0,
        le=MAX_HINT_LEVEL
    )
    model: Optional[str] = None
    context_options: ContextOptions = Field(
        default_factory=ContextOptions
    )


class NextHintRequest(BaseModel):
    model: Optional[str] = None
    context_options: ContextOptions = Field(
        default_factory=ContextOptions
    )


class UserChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=MAX_CHAT_MESSAGE_LENGTH
    )
    model: Optional[str] = None
    context_options: ContextOptions = Field(
        default_factory=ContextOptions
    )
    hint_level: Optional[int] = Field(None, ge=0, le=MAX_HINT_LEVEL)
    simulation_elapsed_seconds: Optional[float] = Field(None, ge=0, le=86400, allow_inf_nan=False)
    confusion_signal: Optional[bool] = None


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: str


class TutorResponse(BaseModel):
    chat_id: str
    question_id: str
    hint_level: int
    model: str
    hint: str
    history: List[ChatMessage]
    prompt_messages: Optional[List[Dict[str, str]]] = None
    context_options: Optional[Dict[str, bool]] = None
    requested_context_options: Optional[Dict[str, bool]] = None
    baseline_hint_level: int
    start_decision: Dict[str, Any] = Field(default_factory=dict)
    adaptation: Dict[str, Any] = Field(default_factory=dict)
    hint_policy: Dict[str, Any] = Field(default_factory=dict)
    configuration: Dict[str, Any] = Field(default_factory=dict)
    config_sha256: str
    policy_mode: str
    stage: str
    diagnosis_hypothesis: Optional[str] = None
    start_prompt_messages: Optional[List[Dict[str, str]]] = None
    llm_operations: int = 1


class ChatHistoryResponse(BaseModel):
    chat_id: str
    question_id: str
    current_hint_level: int
    messages: List[ChatMessage]
