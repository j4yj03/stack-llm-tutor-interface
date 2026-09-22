from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.config import (
    MAX_CHAT_MESSAGE_LENGTH,
    MAX_CONTEXT_QUESTION_TEXT,
    MAX_HINT_LEVEL,
    MAX_QUESTION_TEXT_LENGTH,
    MAX_STUDENT_ANSWER_LENGTH
)


class ContextOptions(BaseModel):
    include_question_text: bool = True
    include_student_answer: bool = True
    include_diagnosis_code: bool = True
    include_prt_feedback: bool = True
    include_score: bool = False
    include_learning_goals: bool = False
    include_math_rules: bool = False
    include_solution_steps: bool = False
    include_final_answer: bool = False
    include_chat_history: bool = True


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


class TutorRequest(BaseModel):
    stack: StackContext
    chat_id: Optional[str] = None
    user_message: Optional[str] = Field(
        None,
        max_length=MAX_CHAT_MESSAGE_LENGTH
    )
    hint_level: int = Field(
        1,
        ge=1,
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


class ChatHistoryResponse(BaseModel):
    chat_id: str
    question_id: str
    current_hint_level: int
    messages: List[ChatMessage]
