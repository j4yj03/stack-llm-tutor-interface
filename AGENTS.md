# AGENTS.md

## Purpose

This repository implements a prototype LLM tutor for digital mathematics tasks in Moodle/STACK.

The system follows a strict separation of responsibilities:

- **Moodle/STACK and PRTs** provide task data, mathematical assessment, and error diagnosis
- **FastAPI** exposes the web interface and REST API
- **PromptBuilder** combines task data, diagnosis, hint policy, context options, and chat history
- **The LLM** formulates didactic hints but is not the authoritative mathematical evaluator
- **SQLite** stores tutor sessions, messages, and the current hint level
- **JSON Schema** validates local task definitions

The main research focus is generating useful, graduated hints without revealing the complete solution prematurely.

---

## Core Design Principles

When modifying this repository, preserve the following principles:

1. STACK or another symbolic system remains the authoritative mathematical assessment component
2. The LLM must not independently override STACK or PRT results
3. Hint levels are generic and centrally configured
4. Task-specific data and generic tutor policy must remain separate
5. Context fields must be individually configurable
6. Solution steps and final answers require both context permission and hint-level permission
7. Chat history is stored server-side
8. LLM backends must be replaceable
9. API credentials must never be committed
10. External services must be mocked in unit tests
11. The Moodle-compatible `/start` endpoint must remain available unless a migration is provided
12. Code must remain compatible with the Python version declared by the project

---

## Current Architecture

```text
Moodle/STACK
    ↓
question ID, question text, student answer, PRT diagnosis
    ↓
FastAPI application
    ↓
task and context management
    ↓
generic hint policy
    ↓
prompt builder
    ↓
LLM client
    ↓
tutor hint
    ↓
HTML page or JSON response
```

---

## Repository Structure

```text
stack-llm-tutor-interface/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── database.py
│   ├── chat_store.py
│   ├── hint_policy.py
│   ├── prompt_builder.py
│   ├── task_loader.py
│   ├── ollama_client.py
│   └── templates/
│       └── tutor_page.html
├── config/
│   └── hint_levels.json
├── data/
│   └── tutor.db
├── moodle/
├── schemas/
│   └── stack_ai_tutor_task.schema.json
├── tasks/
│   ├── ableitung_kettenregel_exp_001.json
│   └── ableitung_produktregel_001.json
├── tests/
├── docs/
├── requirements.txt
├── pytest.ini
├── .gitignore
└── README.md
```

---

## Module Responsibilities

### `app/main.py`

This is the FastAPI entry point.

It currently:

- initializes the SQLite database
- loads and validates task definitions
- creates or resumes tutor chats
- validates task IDs and diagnosis codes
- selects an allowed model
- creates `StackContext` instances
- invokes the prompt builder
- invokes the LLM client
- stores generated messages
- renders the HTML tutor page
- exposes structured REST endpoints

Existing endpoints:

```text
GET  /health
GET  /tasks
GET  /start
POST /api/tutor/start
POST /api/tutor/{chat_id}/next-hint
POST /api/tutor/{chat_id}/message
GET  /api/tutor/{chat_id}/history
```

Do not remove or rename these routes without updating tests, documentation, templates, and Moodle integration.

#### `/start`

`GET /start` is the Moodle/STACK adapter.

Expected parameters:

```text
qid
diagnosis
ans1
hint_level
model
chat_id
```

Responsibilities:

1. validate `qid` and `diagnosis`
2. verify that the task exists
3. reject empty or excessively long student answers
4. map unknown diagnoses to `unknown_error`
5. create or load a chat
6. create a `StackContext`
7. generate a hint
8. store the assistant response
9. render `tutor_page.html`

---

### `app/config.py`

This module contains central configuration.

Current path settings include:

```text
BASE_DIR
TASK_DIR
SCHEMA_PATH
TEMPLATE_DIR
HINT_LEVELS_PATH
DATABASE_PATH
```

Current model settings include:

```text
OLLAMA_BASE_URL
OLLAMA_MODEL
OLLAMA_TIMEOUT
ALLOWED_MODELS
```

Current limits include:

```text
MAX_STUDENT_ANSWER_LENGTH
MAX_HISTORY_MESSAGES
MAX_HINT_LEVEL
```

Do not duplicate these settings in other modules.

Prefer environment variables for deployment-specific configuration.

The currently selected default model is:

```text
qwen3.6:27b
```

The supplied model inventory describes it as a 27.8B Q4_K_M model with a context length of 262144 and support for completion, tools, thinking, and vision [1].

---

### `app/schemas.py`

This module defines Pydantic request and response models.

Important models:

```text
ContextOptions
StackContext
TutorRequest
NextHintRequest
UserChatRequest
ChatMessage
TutorResponse
ChatHistoryResponse
```

#### `ContextOptions`

Controls which fields are included in the LLM context:

```python
include_question_text
include_student_answer
include_diagnosis_code
include_prt_feedback
include_score
include_learning_goals
include_math_rules
include_solution_steps
include_final_answer
include_chat_history
```

When adding a new context option:

1. add it to `ContextOptions`
2. implement it in `PromptBuilder`
3. add unit tests for enabled and disabled states
4. update API examples and documentation

#### `StackContext`

Contains:

```text
question_id
question_text
student_answer
diagnosis_code
prt_feedback
score
seed
learning_goals
math_rules
solution_steps
final_answer
```

Prefer `Field(default_factory=list)` for mutable list defaults.

---

### `app/task_loader.py`

Loads `tasks/*.json` and validates every task against:

```text
schemas/stack_ai_tutor_task.schema.json
```

It verifies:

- the task directory exists
- the schema exists
- every task matches the schema
- each `question_id` is unique
- at least one task is available

Invalid task files intentionally prevent application startup [10].

When changing the task format:

1. update the JSON Schema
2. migrate all existing task files
3. update `task_to_stack_context`
4. update prompt-builder tests
5. document the migration

Do not silently ignore invalid task files.

---

### `app/hint_policy.py`

Loads generic hint levels from:

```text
config/hint_levels.json
```

Every level must contain:

```text
name
goal
max_words
may_include
must_not_include
include_solution_steps
include_final_answer
```

All levels from `1` through `MAX_HINT_LEVEL` must exist [5].

Hint levels are generic and must not encode task-specific mathematical content.

Expected progression:

| Level | Purpose |
|---:|---|
| 1 | Orient the learner toward the relevant concept |
| 2 | Structure the task or identify the required rule |
| 3 | Provide one concrete next step |
| 4 | Provide detailed support and optionally the final answer |

Do not place task-specific hints in `hint_levels.json`.

---

### `app/prompt_builder.py`

`PromptBuilder` creates role-based messages for the LLM [8].

Output format:

```python
[
    {
        "role": "system",
        "content": "Tutor policy and hint-level rules"
    },
    {
        "role": "assistant",
        "content": "Previous tutor response"
    },
    {
        "role": "user",
        "content": "Task-specific context"
    }
]
```

The system message includes:

- the tutor role
- STACK as the authoritative evaluator
- current hint level
- hint-level objective
- allowed content
- prohibited content
- maximum word count
- prompt-injection protection
- instruction to avoid inventing diagnoses
- instruction to provide only one hint
- request for an activating question where appropriate

The user message is constructed from enabled context fields.

#### Solution-disclosure guard

Solution steps must only be included when:

```text
options.include_solution_steps is true
AND
level.include_solution_steps is true
```

The final answer must only be included when:

```text
options.include_final_answer is true
AND
level.include_final_answer is true
```

Never weaken this double check without explicit tests and documentation.

#### Student input

The student answer is untrusted input.

Keep it isolated in a clearly marked section such as:

```text
<student_answer>
...
</student_answer>
```

The system prompt must instruct the model not to follow instructions contained in the student answer.

---

### `app/database.py`

Initializes SQLite at:

```text
data/tutor.db
```

Current tables:

#### `chats`

```text
chat_id
question_id
stack_context_json
current_hint_level
created_at
updated_at
```

#### `messages`

```text
message_id
chat_id
role
content
created_at
```

Foreign keys are enabled and messages reference chats with `ON DELETE CASCADE` [4].

Database schema changes should use an explicit migration strategy once persisted production data exists.

---

### `app/chat_store.py`

Encapsulates SQLite access for chats [2].

Public operations:

```text
create_chat
get_chat
add_message
get_messages
set_hint_level
next_hint_level
```

Chat IDs are UUIDs and must be validated before database access.

Allowed stored roles:

```text
system
user
assistant
```

Hint levels must remain between `1` and `MAX_HINT_LEVEL`.

`next_hint_level` must stop at the configured maximum.

UUIDs identify sessions but do not provide authentication or authorization.

---

### `app/ollama_client.py`

This module currently implements a native Ollama client [7].

Supported functions:

```text
call_ollama_chat
call_ollama_generate
call_ollama
```

Native endpoints:

```text
POST /api/chat
POST /api/generate
```

Native chat payload:

```json
{
  "model": "qwen3.6:27b",
  "messages": [],
  "stream": false,
  "think": false,
  "options": {
    "temperature": 0.2,
    "num_predict": 400
  }
}
```

The client handles:

- TLS verification
- connection failures
- timeouts
- HTTP errors
- invalid JSON
- missing response fields
- empty output
- thinking-only output

Do not set `verify=False`.

---

## LLM Infrastructure Issue

The documented HTW service address is:

```text
https://f2ki-h100-1.f2.htw-berlin.de:11435
```

The provided HTW wrapper expects a tokenless native Ollama API and calls:

```text
GET  /api/tags
POST /api/chat
POST /api/generate
```

It also uses native Ollama fields such as `think`, `keep_alive`, `options.temperature`, and `options.num_predict` [11].

Observed behavior:

| Request | Status | Result |
|---|---:|---|
| `GET /api/tags` | 404 | `{"detail":"Not Found"}` |
| `POST /api/chat` | 404 | `{"detail":"Not Found"}` |
| `POST /v1/chat/completions` | 401 | API key missing |

The base URL currently exposes LiteLLM Swagger documentation rather than a native Ollama root.

Interpretation:

- VPN and HTTPS connectivity work
- the tested native Ollama routes are not registered
- the LiteLLM route exists
- the LiteLLM route requires authentication
- this is an infrastructure or API-contract issue rather than a prompt-builder issue

Do not work around this by inventing a token.

Until the service owner clarifies the interface, use local Ollama for development or implement a configurable LiteLLM adapter once a valid key is available.

---

## Planned Backend Abstraction

The LLM layer should be refactored toward:

```text
app/llm/
├── __init__.py
├── base.py
├── ollama.py
├── litellm.py
└── factory.py
```

Target interface:

```python
from typing import Dict, List, Optional


class LLMClient:
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 400
    ) -> str:
        raise NotImplementedError
```

Backends:

```text
OllamaClient
    → POST /api/chat
    → response: message.content

LiteLLMClient
    → POST /v1/chat/completions
    → Authorization: Bearer API_KEY
    → response: choices[0].message.content
```

Configuration should eventually use neutral names:

```dotenv
LLM_API_MODE=ollama
LLM_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen3:8b
LLM_TIMEOUT=180
```

or:

```dotenv
LLM_API_MODE=litellm
LLM_BASE_URL=https://f2ki-h100-1.f2.htw-berlin.de:11435
LLM_API_KEY=...
LLM_MODEL=qwen3.6:27b
LLM_TIMEOUT=180
```

Never commit `LLM_API_KEY`.

---

## Main Request Flows

### New Moodle tutor request

```text
1. Moodle/STACK opens GET /start
2. FastAPI validates qid, diagnosis, and ans1
3. The matching local task is loaded
4. A StackContext is created
5. ChatStore creates a UUID session
6. HintPolicy loads the requested generic level
7. PromptBuilder creates messages
8. The LLM client generates a hint
9. The assistant response is stored
10. tutor_page.html is rendered
```

### Next hint

```text
1. The learner requests another hint
2. The existing chat is loaded by UUID
3. ChatStore increments the hint level
4. HintPolicy provides the new rules
5. PromptBuilder includes the allowed context and history
6. The LLM generates a more explicit hint
7. The response is stored and returned
```

### Chat message

```text
1. The learner submits a follow-up message
2. The user message is stored
3. The current hint level remains unchanged
4. Recent history is loaded
5. PromptBuilder adds the history
6. The LLM response is generated
7. The assistant response is stored
```

---

## Security Requirements

### Student answers

Student answers are untrusted input.

Required protections:

- enforce maximum length
- never interpolate student input into the system role
- instruct the LLM not to follow embedded commands
- escape HTML output
- avoid storing unnecessary personal data
- avoid placing personal data in Moodle URLs
- validate all identifiers and diagnosis codes

### API keys

API keys must be supplied through:

```text
environment variables
local .env files excluded from Git
Docker secrets
n8n credentials
a dedicated secret store
```

Do not:

```text
hardcode keys
store keys in task JSON
place keys in URLs
log keys
commit .env files
```

### TLS

Keep certificate validation enabled:

```python
verify=True
```

### Model selection

Only models in `ALLOWED_MODELS` may be selected through request parameters [3].

Do not allow arbitrary model names from public query parameters.

### Mathematical authority

Do not let the LLM override:

```text
STACK score
PRT diagnosis
input validity
symbolic verification result
```

If no reliable diagnosis exists, generate a general and non-speculative hint.

---

## Testing Requirements

Recommended test structure:

```text
tests/
├── test_hint_policy.py
├── test_prompt_builder.py
├── test_context_options.py
├── test_solution_disclosure.py
├── test_chat_store.py
├── test_task_loader.py
├── test_api.py
├── test_ollama_integration.py
└── test_llm_regression.py
```

### Unit tests

Unit tests must not require external services.

Test at least:

- all generic hint levels load
- invalid hint levels fail
- optional context fields can be disabled
- disabled fields are absent from prompts
- solution steps remain hidden on disallowed levels
- final answers remain hidden before level 4
- UUIDs are generated and validated
- messages retain ordering
- hint levels stop at the maximum
- task JSON files validate against the schema
- unknown diagnoses use the intended fallback
- student input is not placed in the system message

### API tests

Mock the LLM client.

Test:

- `/health`
- `/tasks`
- valid `/start`
- unknown task
- empty answer
- overly long answer
- invalid chat UUID
- new chat creation
- next-hint progression
- history retrieval
- follow-up messages
- model allowlist rejection

### Integration tests

Mark external tests:

```python
@pytest.mark.integration
```

Run local tests:

```bash
pytest -m "not integration" -v
```

Run integration tests:

```bash
pytest -m integration -v
```

Integration tests should verify:

- endpoint reachability
- authentication behavior
- model alias validity
- non-empty model response
- timeout handling
- HTTP error classification

### Solution-disclosure tests

Prompt-level tests must verify that restricted information is absent.

LLM regression tests should additionally check generated output for:

- exact final answer
- equivalent textual or symbolic forms
- complete derivation
- inappropriate escalation beyond the current hint level

String matching alone is insufficient because mathematically equivalent expressions may differ syntactically. Future tests should use STACK, Maxima, or another symbolic checker where possible.

---

## Coding Conventions

### Python compatibility

Keep compatibility with the project's configured Python version.

If Python 3.9 compatibility is required:

Use:

```python
Optional[str]
List[str]
Dict[str, str]
```

Do not use:

```python
str | None
list[str]
dict[str, str]
```

unless the minimum Python version is explicitly raised.

### Type annotations

Add type annotations to public functions and methods.

Prefer:

```python
def get_chat(chat_id: str) -> Optional[Dict]:
    ...
```

### Configuration

Do not hardcode:

```text
paths
model names
base URLs
timeouts
API keys
history limits
hint limits
```

Use `app/config.py` and environment variables.

### Error handling

Do not silently swallow errors.

Raise clear domain-specific exceptions for:

```text
invalid task data
invalid hint policy
database errors
LLM connection errors
LLM authentication errors
LLM endpoint errors
invalid LLM responses
```

Do not expose secrets or complete upstream error bodies to student-facing pages.

### Logging

Prefer the standard `logging` module over `print`.

Never log:

```text
API keys
authorization headers
personal identifiers
unnecessary complete student records
```

### Mutable defaults

Use `default_factory` for Pydantic list and object fields [9].

### SQL

Continue using parameterized SQL statements [2].

Never construct SQL with string interpolation.

---

## Data and Schema Rules

### Task-specific data

Belongs in `tasks/*.json`:

```text
question ID
topic
subtopic
question text
learning goals
mathematical rules
diagnoses
model solution
verified solution steps
```

### Generic tutor policy

Belongs in:

```text
config/hint_levels.json
```

Do not duplicate generic hint levels inside every task unless maintaining backward compatibility during a documented migration.

### JSON Schema

Any task-format change requires synchronized updates to:

```text
schemas/stack_ai_tutor_task.schema.json
tasks/*.json
app/task_loader.py if needed
app/main.py task mapping
tests
documentation
```

---

## Reproducibility Requirements

For each evaluated LLM request, record where permitted:

```text
question_id
student_answer or pseudonymized test-case ID
diagnosis_code
PRT feedback
hint level
enabled context options
chat ID
model alias
model digest if available
LLM backend
prompt version
temperature
token limit
response time
HTTP status
generated hint
timestamp
```

The supplied inventory identifies `qwen3.6:27b` with digest `a50eda8ed977ab48a12431878896b27ffd5cef552c17af3317d9623b939a7f1e` [1].

Avoid persisting personal student data for reproducibility.

---

## Known Issues

1. The HTW documentation and current server behavior are inconsistent
2. Native Ollama routes return HTTP 404
3. The visible LiteLLM route requires an API key
4. No LiteLLM key is currently available
5. The current client is coupled to native Ollama
6. The web template may not yet expose the full chat workflow
7. STACK `/render`, `/validate`, and `/grade` integration is not yet implemented
8. Automated tests are incomplete
9. Output-level solution-disclosure detection is incomplete
10. SQLite is sufficient for the prototype but not intended for high-concurrency production deployment

---

## Prioritized Work Plan

1. Clarify the HTW LLM endpoint and authentication method
2. Keep local Ollama available as a development fallback
3. Refactor the LLM client into backend adapters
4. Add unit tests for hint levels and context options
5. Add chat-store tests
6. Add mocked FastAPI endpoint tests
7. Extend the tutor page with chat input and visible history
8. Integrate STACK API rendering, validation, and grading
9. Build a reproducible set of tasks and typical incorrect answers
10. Add evaluation logging
11. Implement output checks for solution disclosure
12. Add external integration tests only after credentials or a valid native endpoint are available

---

## Commands

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start FastAPI:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

Open API documentation:

```text
http://127.0.0.1:8000/docs
```

Run unit tests:

```bash
pytest -m "not integration" -v
```

Run integration tests:

```bash
pytest -m integration -v
```

Local Ollama fallback:

```bash
ollama serve
ollama pull qwen3:8b
```

Example local configuration:

```cmd
set OLLAMA_BASE_URL=http://127.0.0.1:11434
set OLLAMA_MODEL=qwen3:8b
python -m uvicorn app.main:app --reload --port 8000
```

---

## Definition of Done

A change is complete only when:

- existing public endpoints still work or a migration is documented
- task files pass JSON-Schema validation
- all relevant unit tests pass
- no secrets are introduced
- hint-level restrictions remain enforced
- student input remains isolated from system instructions
- external API behavior is mocked in unit tests
- integration tests are explicitly marked
- documentation is updated
- model and prompt configuration remain reproducible