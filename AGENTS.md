# AGENTS.md

Last synchronized with the workspace implementation: 2026-10-02.
This describes the prototype, not a guarantee about deployment configuration.

## Purpose

This repository implements a prototype LLM tutor for digital mathematics tasks in Moodle/STACK.

The system follows a strict separation of responsibilities:

- **Moodle/STACK or another symbolic system** provides authoritative mathematical
  assessment when actually integrated and evidenced; a Tutor link does not grade
- **FastAPI** exposes the web interface and REST API
- **PromptBuilder** combines task data, diagnosis, hint policy, context options, and chat history
- **The LLM** formulates diagnostic questions/hints and, in an explicit model
  condition, uncertain error hypotheses; it is not the authoritative evaluator
- **SQLite** stores sessions, messages, current level, immutable initial baseline
  and session state
- **JSON Schema** validates local task definitions
- **The evaluation suite and Jupyter testbench** compare explicit context, rule,
  generation, start and adaptation conditions through the API; technical checks,
  disclosure indicators, human ratings and optional second-model ratings stay separate

The research focus is useful, appropriately graduated support and controlled
comparison of pedagogical rules, not treating current defaults as proven optimal.

The first empirical study can use authored task/answer/reference hypotheses
without a PRT. Real live outputs on synthetic cases are empirical observations;
hand-written demos are not. Pending references and expected errors remain
hypotheses, never fabricated STACK evidence. Learning effectiveness, motivation,
PRT accuracy and wider deployment readiness are not established by this tooling.

---

## Core Design Principles

When modifying this repository, preserve the following principles:

1. STACK or another symbolic system remains the authoritative mathematical assessment component
2. Actually supplied verified STACK/PRT or symbolic results remain binding; an uncertain model hypothesis or synthetic label is not such a result
3. Hint levels and pedagogical rules are generic, centrally configurable experimental conditions, not hardcoded task-specific escalation
4. Task-specific data and generic tutor policy must remain separate
5. Context fields must be individually configurable
6. Solution steps and final answers require both context permission and hint-level permission
7. Chat history is stored server-side
8. LLM backends must be replaceable
9. API credentials must never be committed
10. External services must be mocked in unit tests
11. The Moodle-compatible `/start` endpoint must remain available unless a migration is provided
12. Code must remain compatible with the Python version declared by the project
13. Evaluation must never start live LLM calls implicitly; demo data must not enter research metrics
14. Verification, missing evidence, failed requests, and unknown telemetry must remain explicit
15. Human and judge ratings must not be pooled, imported as each other, or combined into a compensating overall grade
16. Adaptation requires a new interaction and corroborating signals; never infer learning from idle or scripted time

---

## Current Architecture

```text
Moodle/STACK or a controlled task/answer case
    -> FastAPI validation and stored context
    -> explicit/fixed start or a separate individual LLM start decision
    -> active generic policy + effective context + optional history/current message
    -> one PromptBuilder path -> replaceable LLM client
    -> successful response/level/state commit
    -> HTML or JSON with observed policy/configuration/decision metadata
```

The evaluation client is separate from the server:

```text
cases + profiles + deployment condition + start selection + explicit script
    -> deterministic session/turn plan, hashes and input snapshots (offline)
    -> authorized health/config preflight and fresh POST /api/tutor/start
    -> dependent /message turns, only after predecessor success
    -> actual outputs/prompts/options/policy/configuration/decisions
    -> automatic checks + human ratings + separately gated optional judge
    -> separate reports and model-/condition-/turn-aware paired comparisons
```

---

## Repository Structure

```text
stack-llm-tutor-interface/
├── code/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── runtime_config.py
│   │   ├── adaptation.py
│   │   ├── evaluation_api.py
│   │   ├── schemas.py
│   │   ├── database.py
│   │   ├── chat_store.py
│   │   ├── hint_policy.py
│   │   ├── prompt_builder.py
│   │   ├── task_loader.py
│   │   ├── llm/
│   │   │   ├── base.py
│   │   │   ├── _http.py
│   │   │   ├── saia.py
│   │   │   ├── ollama.py
│   │   │   └── factory.py
│   │   ├── ollama_client.py
│   │   └── templates/tutor_page.html
│   ├── config/hint_levels.json
│   ├── data/                       # SQLite, not committed
│   ├── evaluation/
│   │   ├── models.py
│   │   ├── corpus.py
│   │   ├── runner.py
│   │   ├── notebook.py
│   │   ├── checks.py
│   │   ├── report.py
│   │   ├── task_cases.py
│   │   ├── judge.py
│   │   ├── __main__.py
│   │   ├── data/                   # cases JSONL and context profiles
│   │   ├── experiments/            # explicit conditions; older protocol-1 presets
│   │   ├── notebooks/
│   │   │   ├── testbench.ipynb
│   │   │   └── auswertung.ipynb
│   │   ├── imports/                # raw exports, git-ignored
│   │   ├── runs/                   # run artifacts, git-ignored
│   │   ├── rubric.md
│   │   └── README.md
│   ├── moodle/
│   │   ├── question_variables.txt
│   │   ├── fragetext_castext.html
│   │   ├── prt_feedback.html
│   │   └── README.md
│   ├── schemas/stack_ai_tutor_task.schema.json
│   ├── tasks/
│   │   ├── ableitung_kettenregel_exp_001.json
│   │   └── ableitung_produktregel_001.json
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-evaluation.txt
│   ├── pytest.ini
│   ├── .env.example
│   └── README.md
├── docs/
│   ├── evaluation_protocol.md
│   ├── expose/
│   ├── literatur/                  # PDFs and literature notes
│   └── README.md
├── AGENTS.md
├── .gitignore
└── README.md
```

Unless explicitly prefixed with `code/` or `docs/`, module and application-data
paths below are relative to `code/`. The `evaluation/` subsection uses paths
relative to `code/evaluation/`. Run Python application, CLI, and pytest commands
from `code/`; run Moodle snippet tests from the repository root.

Current documentation:

- Setup and overview: `README.md`, `code/README.md`
- API and UI behavior: `code/app/README.md`
- Configuration/overrides: `code/config/README.md`, `code/.env.example`
- Evaluation design: `docs/evaluation_protocol.md` (`eval-protocol-2`)
- Evaluation usage and ratings: `code/evaluation/README.md`, `code/evaluation/rubric.md`
- Moodle field integration: `code/moodle/README.md`
- Research documents: `docs/expose/expose_4.pdf`, `docs/literatur/literatur.md`

Some architecture and infrastructure notes in `docs/` describe older Ollama/
LiteLLM states. Do not treat them as current operational instructions.
Historical experiment presets/manifests keep their own protocol version;
do not retroactively rename or edit old identities to match new studies.

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
- selects an explicit/fixed/individual start and preserves its initial baseline
- decides optional adaptation at the next interaction, not on a background timer
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
POST /tutor/{chat_id}/message
POST /tutor/{chat_id}/retry
POST /api/tutor/start
POST /api/tutor/{chat_id}/next-hint
POST /api/tutor/{chat_id}/message
GET  /api/tutor/{chat_id}/history
GET  /api/evaluation/config     # opt-in, authenticated, no provider operation
POST /api/evaluation/judge      # opt-in, authenticated second-model review
```

Do not remove or rename these routes without updating tests, documentation, templates, and Moodle integration.

#### `/start`

`GET /start` is the Moodle/STACK adapter.

Expected parameters:

```text
qid
diagnosis
ans1
hint_level (optional, 0..MAX_HINT_LEVEL; explicit value overrides start selection)
model
chat_id
question_text (optional, full instantiated Moodle task text)
funktion (optional, instantiated function; composed with question_text_template)
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

`question_text` (full text) and `funktion` (composed with the task's
`question_text_template`) are mutually exclusive. When the resulting task text
differs from the local `question_text`, it is a Moodle variant: persist the
supplied context and use it for display and all subsequent hints/messages.
The local `model_solution` is example data of a fixed variant and must never
be attached to a variant. `question_text`, `question_text_template` and
`given_data` are generic; the instantiated function always comes from
Moodle/STACK. An existing chat must reject changed task/answer/diagnosis
parameters and lower hint levels.

New sessions without an explicit level use `TUTOR_START_LEVEL` (default 1) in
`fixed` mode. `individual` first calls the LLM for a bounded JSON start decision
within `0..MAX_HINT_LEVEL`, then generates the answer; no silent selection
fallback. API selection uses request `context_options` intersected with the
stage-0 cap and diagnosis mode; HTML uses its configured defaults. Record the
separate actual `start_prompt_messages` and selection options, not a reconstructed
preview. Existing chats without a level retain their current level.
The unchanged Moodle snippets explicitly send level 1 and bypass default selection.

#### HTML chat and prompt debugging

`POST /tutor/{chat_id}/message` accepts HTML form fields `message` and `model`
and re-renders without JavaScript. Default adaptation is disabled; enabled
adaptation may raise the attempted level on this next interaction.
Form parsing requires the pinned `python-multipart` dependency.
Invalid messages do not enter the history. On LLM failure the submitted message
remains stored and the page shows a safe error plus, when HTML debugging is
enabled, the attempted prompt.

`POST /tutor/{chat_id}/retry` is the HTML retry action for a failed generation: it never
re-stores the user question, targets the attempted hint level (form field,
never below the stored level), and on success stores just the new assistant
response. The failed page renders the retry inline next to the unanswered
user question, or in the error box when no chat question exists (typical
`/start` failures). Only an inline retry beside an unanswered user question
disables the chat form's send button. An initial hint failure with no user
question does not disable it. This is UI guidance, not API idempotency or locking.
The endpoint does not verify a durable failure state or consume a retry token;
manually reposting it can generate another assistant response.

The HTML debug area contains a hint-level selector for the current or a higher
level. A successful generation commits the attempted level; failed next-hint
generations leave the stored level unchanged. Lower levels are rejected.

`generate_hint` returns `(hint, messages, diagnosis_hypothesis)`; display actual messages passed
to the client, never rebuild a debug prompt after saving the new response.
JSON generation responses additionally expose `prompt_messages`,
`requested_context_options` versus effective `context_options`,
`baseline_hint_level`, `start_decision`,
`start_prompt_messages`, `adaptation`, effective `hint_policy`, `configuration`,
`config_sha256`, `policy_mode`, `stage`, `diagnosis_hypothesis` and logical
`llm_operations`. Level 0 is `stage="diagnostic"`; positive levels are `hint`.
Logical operations are not provider attempt counts or token usage.
Individual selection records its effective flags as `start_decision.context_options`.
This debug view is for development, not an authenticated production feature or
a durable request log. History endpoints keep their existing format.

`POST /api/tutor/start` does not mathematically verify supplied context against
STACK. Existing-chat requests compare the declared Pydantic `StackContext`
against persistence and reject changed context or lower levels. This is identity
validation, not authentication or grading. Evaluations start fresh per session;
only explicit script turns reuse that session.

When effective history is disabled, including by a stage-0 cap, the latest user
question remains visible via isolated `current_message`. When history is enabled,
main keeps the current question in raw user history without duplicating it.
Never put these strings in the system role. Structured mode validates exactly
`hint: string` and `diagnosis_hypothesis: string|null`; only model diagnosis mode
permits a string hypothesis. Bounded structured hint/hypothesis lengths are
20000/2000 characters, selection reasons at most 2000. Save only the hint in chat.

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
LLM_API_MODE
LLM_BASE_URL
LLM_API_KEY
LLM_MODEL
LLM_TEMPERATURE
LLM_MAX_TOKENS
LLM_TIMEOUT
LLM_RETRY_DELAY
LLM_DISABLE_THINKING
ALLOWED_MODELS
```

`LLM_ALLOWED_MODELS` is the comma-separated environment variable used to build
`ALLOWED_MODELS`; the configured default `LLM_MODEL` is always added.

Current limits include:

```text
MAX_STUDENT_ANSWER_LENGTH
MAX_QUESTION_TEXT_LENGTH
MAX_CONTEXT_QUESTION_TEXT
MAX_CHAT_MESSAGE_LENGTH
MAX_HISTORY_MESSAGES
MIN_HINT_LEVEL
MAX_HINT_LEVEL
DEFAULT_HINT_LEVEL
DEBUG_MODE
CONTEXT_OPTIONS
```

`CONTEXT_OPTIONS` (comma/semicolon-separated) selects the default context options of
the tutor flows and the JSON defaults of `ContextOptions` (unknown names
prevent startup). `DEBUG_MODE=1` keeps the prompt/options debugger and the
STACK diagnosis box on the tutor page; it also controls the HTML hint-level
selector. `DEBUG_MODE=0` hides the entire HTML debug area, including that
selector, while the LLM context is unchanged. It does not suppress the JSON
API's debug response fields. While a chat question is
unanswered, the send button of the chat form is disabled and only the
inline retry remains available.

The default selection includes question text, student answer, supplied diagnosis/
feedback, learning goals, solution steps, final answer, and history.
Solution fields remain subject to both context and level permission.
Score and mathematical rules are disabled by default.

`MAX_CONTEXT_QUESTION_TEXT` is derived from `MAX_QUESTION_TEXT_LENGTH` with a
minimum of 10000, not a separate environment override. `MIN_HINT_LEVEL=0` is fixed;
environment `MAX_HINT_LEVEL` is an integer `0..32`, default 4. Default start level
1 is invalid if maximum is 0; explicitly set `TUTOR_START_LEVEL=0` in that case.

Runtime controls and defaults (full reference: `code/config/README.md`):

| Environment control | Default / constraint |
|---|---|
| `LLM_TEMPERATURE`, `LLM_MAX_TOKENS` | `0.2`, `400`; finite `0..2`, integer `1..32768` |
| `LLM_TIMEOUT`, `LLM_RETRY_DELAY` | `180`, `2`; positive integer seconds, finite nonnegative backoff |
| `TUTOR_START_LEVEL`, `TUTOR_START_MODE` | `1`, `fixed`; level in range, `fixed\|individual` |
| `TUTOR_DIAGNOSIS_MODE` | `provided`; `provided\|model\|none` |
| `TUTOR_POLICY_MODE`, `TUTOR_RESPONSE_FORMAT` | `tutor`, `text`; `tutor\|general`, `text\|structured` |
| `TUTOR_RULES_ID` | Nonempty `default-policy` label, not proof of identical rules |
| `TUTOR_ASK_ACTIVATING_QUESTION`, `TUTOR_HIDE_HINT_LEVEL`, `TUTOR_ENFORCE_WORD_LIMIT` | All true; optional tutor prompt rules, not production output filtering |
| `TUTOR_STAGE0_CONTEXT_OPTIONS` | `question_text,student_answer,learning_goals,math_rules,chat_history`; cap only, never enable a disabled request flag |
| `TUTOR_ADAPTIVE_ENABLED`, `TUTOR_ADAPTIVE_AFTER_SECONDS` | False, `120`; finite nonnegative threshold |
| `TUTOR_ADAPTIVE_STEP`, `TUTOR_ADAPTIVE_MAX_LEVEL` | `1`, active maximum; positive integer step, ceiling within range |
| `TUTOR_ADAPTIVE_CONFUSION_PHRASES` | `ich verstehe nicht,keine ahnung,ich weiss nicht,no idea`; comma/semicolon list |
| `HINT_LEVELS_PATH`, `TUTOR_HINT_POLICY_JSON` | `config/hint_levels.json`, empty; relative file paths use `BASE_DIR`, JSON overrides existing levels |
| `EVALUATION_API_ENABLED`, `EVALUATION_API_TOKEN` | False, empty; enabling without a nonempty server token fails startup |
| `EVALUATION_JUDGE_MODEL` | Empty; must be explicitly configured and allowed before judge use |
| `EVALUATION_JUDGE_TEMPERATURE`, `EVALUATION_JUDGE_MAX_TOKENS` | `0.0`, `1200`; finite `0..2`, integer `1..32768` |

Boolean/mode/numeric controls and unknown context names fail fast. Environment
values are loaded at process start. The active policy in `app.state.hint_policy`
is shared by generation, health and protected config/judge metadata: no file
hot reload or request-level arbitrary policy override. Changes require restart
and a new evaluation condition/run. Do not read or log real `.env` secrets to
refresh documentation.

Do not duplicate these settings in other modules.

Prefer environment variables for deployment-specific configuration.

The currently selected default model is:

```text
qwen3.8-27b
```

It is served by the GWDG SAIA platform. The model inventory was
verified on 2026-09-15 via `GET /v1/models`; model names change,
so re-verify before switching defaults. Do not make live provider calls merely
to refresh documentation.

---

### `app/runtime_config.py` and `app/adaptation.py`

`effective_context_options(options, level)` returns a new `ContextOptions`.
Stage 0 intersects requested flags with its independent cap; `model|none`
removes supplied diagnosis code/feedback. Score remains independently selectable.
The double solution permission is still enforced by PromptBuilder afterwards.

`public_configuration(policy)` returns `schema_version="tutor-config-1"`, all
active levels, generation settings, tutor rules, start, adaptation, history/text
limits, context defaults and stage-0 flags. Changing history retention therefore
changes the configuration identity. `configuration_hash` uses canonical compact sorted
ASCII JSON and SHA-256. No API keys, evaluation tokens, upstream credential URL,
DB path or model allowlist enters the snapshot. `/health` reports the same
`config_sha256`; the protected config route also reports separate judge identity.
Requested thinking/parameters and model aliases are not observed provider internals.

`decide_hint_level` is a pure next-interaction decision: adaptation needs time
threshold **and** corroborating self-report/script signal, caps the increase,
and never lowers a level. Explicit allowed target levels take precedence.
Normal elapsed time uses monotonic time only if persisted `clock_id` matches
the current process UUID. After restart/worker change it is `None`, not inferred
from wall time; active confusion then produces `time_unknown`. No active-work
tracking, timer or autonomous LLM generation. Simulation is per request, not a
sticky time source. Commit level/response/time/decision only after generation
success; user questions may already be stored on failure. Baseline never advances.

### `app/evaluation_api.py`

`GET /api/evaluation/config` and `POST /api/evaluation/judge` are disabled by
default (404). Enabled routes require `X-Evaluation-Token`, checked against
server `EVALUATION_API_TOKEN`; missing/wrong credentials give 401. Client
environment is `TUTOR_EVALUATION_TOKEN`, not a provider API key. The same guard
protects JSON follow-up simulation fields (`simulation_elapsed_seconds` finite
`0..86400`, optional `confusion_signal`). Ordinary tutor/debug routes remain
unauthenticated; evaluation auth is not complete production access control.

The optional judge uses `judge-rubric-1.0-v2`, bounded strict requests/results,
explicit allowlisted alias and separate judge generation parameters. Inputs
include target/review identity, UTF-8 hint SHA-256, common reference hypothesis,
verification, active policy, observed prompt, optional separate diagnosis
hypothesis (`diagnosis_hypothesis`), `current_message`, `turn_index` and
`generator_rule_settings`. All are quoted
untrusted data, never new judge instructions. Unknown visibility/settings stay
unknown; a follow-up answer does not inherit the initial reference verdict.
No chat creation or DB mutation in the judge router. Tooling requires a judge
alias different from every saved generator alias; alias difference is not proof
of independent weights. Keep human and judge ratings/artifacts separate.

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
2. update the valid-option registry and default mapping in `app/config.py`
3. implement it in `PromptBuilder`
4. synchronize evaluation flag names, profile models/data, payloads, checks, and notebook controls
5. add unit tests for enabled and disabled states and configuration/profile consistency
6. update API examples and documentation

#### `StackContext`

Contains:

```text
question_id
question_text
student_answer
diagnosis_code
diagnosis_source
prt_feedback
score
seed
learning_goals
math_rules
solution_steps
final_answer
```

Prefer `Field(default_factory=list)` for mutable list defaults.
`diagnosis_source` is optional `synthetic|provided|prt|stack|stack_prt|unknown`
or null, not an eleventh context flag or evidence by itself. The core corpus
payload normalizes `synthetic_fixture` provenance to API `synthetic` (including
CLI task cases); unknown origins remain unknown, never a fabricated PRT source.
`TutorRequest.hint_level` is optional/null for server start selection. Additive
response metadata distinguishes requested/effective flags, baseline, stage and
actual selection/generation prompts; history endpoint shapes remain unchanged.

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
- an optional `question_text_template` contains `{funktion}` and has enough
  length headroom for the instantiated function

Invalid task files intentionally prevent application startup.

When changing the task format:

1. update the JSON Schema
2. migrate all existing task files
3. update `task_to_stack_context`
4. update prompt-builder tests
5. document the migration

Do not silently ignore invalid task files.

---

### `app/hint_policy.py`

Loads generic levels from configurable `HINT_LEVELS_PATH`, default:

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
max_solution_steps
include_final_answer
```

All levels from `0` through `MAX_HINT_LEVEL` must exist; only active levels are
exposed. Required fields and all file entries are type-validated, unknown fields
rejected. Invalid custom policies prevent startup, not implicit migration.

Hint levels are generic and must not encode task-specific mathematical content.

`max_solution_steps` defaults to `0`, `0`, `0`, `3`, `null` for levels 0..4
(`null` means all). Add stage 0 and missing required fields to custom policies
explicitly. This policy migration does not modify task legacy fields or DB rows;
the separate additive DB migration is described below.
The prompt builder limits the step list and stops before a step containing the
literal final answer when final-answer permission is missing. This is not a
symbolic equivalence check or an output-level solution detector.

Default progression (not an immutable empirical optimum):

| Level | Purpose |
|---:|---|
| 0 | Ask a short diagnostic question about understanding or prior approach |
| 1 | Orient the learner toward the relevant concept |
| 2 | Structure the task or identify the required rule |
| 3 | Provide one concrete next step |
| 4 | Provide detailed support and optionally the final answer |

Do not place task-specific hints in `hint_levels.json`.

Override order: file, optional full/partial `TUTOR_HINT_POLICY_JSON`, then
`TUTOR_LEVEL_<N>_NAME/GOAL/MAX_WORDS/MAX_SOLUTION_STEPS/INCLUDE_SOLUTION_STEPS/
INCLUDE_FINAL_ANSWER/MAY_INCLUDE/MUST_NOT_INCLUDE`. Explicit `HintPolicy(path=...)`
still applies these overrides. Text is literal data, never a template or Python
expression; lists prefer JSON (comma/semicolon text also accepted). Existing-level
keys, types, positive word limits and nonnegative/null step limits fail fast.
Generic goals, permissions and wording can be experimental variables; always
record effective values and preserve both reference permissions, even in general mode.

---

### `app/prompt_builder.py`

`PromptBuilder` creates role-based messages for the LLM.

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

In tutor mode the system message includes:

- the tutor role
- STACK as the authoritative evaluator
- current hint level
- hint-level objective
- allowed content
- prohibited content
- maximum word count when `TUTOR_ENFORCE_WORD_LIMIT` is active
- prompt-injection protection
- the configured diagnosis mode, not an unconditional ban on independent model analysis
- instruction to provide only one hint
- instruction not to mention internal levels when `TUTOR_HIDE_HINT_LEVEL` is active
- activating question rule when `TUTOR_ASK_ACTIVATING_QUESTION` is active

The user message is constructed from enabled context fields.

`build_messages(..., history, current_message: Optional[str]=None)` uses one
prompt path. The current message is isolated with `<current_message>` even
when history is disabled/capped; do not duplicate it in provided history.
`general` removes the specialized tutor role, level/goal/may/must and optional
didactic rules, not input isolation, authority constraints or reference guards.
Diagnosis mode and structured output remain independently configured.

`provided` respects the supplied scenario with uncertainty and avoids invented
diagnoses/re-evaluation; `none` requests no diagnosis or independent re-evaluation.
`model` removes supplied diagnosis/feedback and permits bounded independent
analysis as an explicitly uncertain hypothesis, not objective grading. An
actually supplied verified result remains binding in every mode. Generic
`BEREITGESTELLTE DIAGNOSE`/feedback labels do not claim PRT verification;
only explicit authoritative source labels use PRT names, which still are not
authentication/evidence. Score selection is independent of diagnosis mode.

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

Keep this double check in every mode; content-list changes must not bypass it.
Permission changes are explicit configured conditions with tests and metadata,
not a second path that forwards locked reference fields.

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
baseline_hint_level
session_state_json
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

Foreign keys are enabled and messages reference chats with `ON DELETE CASCADE`.

Database schema changes should use an explicit migration strategy once persisted production data exists.

Current initialization performs an explicit additive migration for the two new
chat columns. Existing rows receive their current level as legacy baseline, not
a reconstructed historical start level; session state starts at `{}`. Preserve
old chats/messages/timestamps. New sessions keep their initially chosen baseline
while current level evolves. State includes start decision, last successful UTC
timestamp, monotonic clock value/process ID and current adaptation metadata.
UTC persistence does not permit cross-worker/restart elapsed-time inference.
Bounded structured model texts are not mathematical or legacy-state verification.

---

### `app/chat_store.py`

Encapsulates SQLite access for chats.

Public operations:

```text
create_chat
get_chat
add_message
get_messages
set_hint_level
next_hint_level
set_session_state
```

Chat IDs are UUIDs and must be validated before database access.

Allowed stored roles:

```text
system
user
assistant
```

Hint levels must remain between `MIN_HINT_LEVEL=0` and `MAX_HINT_LEVEL`.

`next_hint_level` must stop at the configured maximum.

UUIDs identify sessions but do not provide authentication or authorization.
Generation/store calls are not a per-session transaction/lock or idempotency
protocol; preserve failure semantics and do not assume concurrent calls are serialized.

---

### `app/llm/`

Backend-Abstraktion für alle LLM-Zugriffe:

```text
app/llm/
├── __init__.py   # Exporte: LLMClient, Fehlerklassen, create_llm_client
├── base.py       # abstraktes Interface + Fehlhierarchie + Nachrichtenvalidierung
├── _http.py      # gemeinsames requests-POST mit Fehlerzuordnung
├── saia.py       # OpenAI-kompatibler Client für GWDG SAIA
├── ollama.py     # nativer Ollama-Client (/api/chat) als Dev-Fallback
└── factory.py    # Backend-Wahl nach LLM_API_MODE
```

Fehlhierarchie:

```text
LLMError
├── LLMConnectionError   # Netzwerk, TLS, Timeout, allgemeine HTTP-Fehler
├── LLMAuthError         # kein Key gesetzt, HTTP 401/403
├── LLMRateLimitError    # HTTP 429, liest Retry-After
└── LLMResponseError     # leere/ungültige Antwort, ungültiges JSON
```

Interface:

```python
from typing import Dict, List, Optional


class LLMClient:
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 400,
        json_output: bool = False
    ) -> str:
        raise NotImplementedError
```

Tutor/start orchestration passes configured temperature/token limits explicitly;
judge uses separate parameters. SAIA may retry once without its thinking extension
on `LLMConnectionError` when the field was present. Native Ollama sends
`think=not LLM_DISABLE_THINKING`, plus `format="json"` only for `json_output=True`.
Neither JSON mode nor thinking flags prove semantic correctness/effective provider
internals. External behavior must be mocked in offline tests.

### `app/ollama_client.py`

Kompatibilitäts-Wrapper. `call_ollama_chat`, `call_ollama_generate`,
`call_ollama` und der Fehlername `OllamaClientError` bleiben erhalten,
delegieren aber an die Backend-Fabrik. Neue Module sollen
`app.llm` direkt verwenden.

---

### `evaluation/`

This is a separate client-side evaluation package. It compares controlled
deployment/context/start/adaptation conditions through fresh `POST /api/tutor/start`
sessions, explicit dependent `/message` turns and optional protected judge
requests, never direct provider calls.
Do not import `app.main`, initialize a database, or start an LLM client from
the evaluation package or notebooks. The local pre-request preview may import
only schema, hint-policy, and prompt-builder modules. Live API calls do store
chats on the server, so use an isolated Tutor instance with its own database.

| Module | Responsibility |
|---|---|
| `models.py` | Strict Pydantic 2 models for cases, profiles, experiments; unknown fields rejected |
| `corpus.py` | Loading, duplicate/reference checks, profile eligibility, request payloads |
| `runner.py` | Deterministic session/turn plan, condition/config hashes, journal, weighted budget, live gate, resume |
| `notebook.py` | Frozen cases/profiles/task/schema/config inputs, local preview, clearly marked hand-written demos |
| `checks.py` | Actual prompt/option checks, word limits, level mentions, limited disclosure detection |
| `report.py` | Neutral human review CSV, validated rating import, condition/phase/turn-aware reports and `compare_runs` |
| `task_cases.py` | Offline case derivation from explicit authored task examples, never STACK/PRT evidence |
| `judge.py` | Offline judge preparation, independent live gate, separate model ratings/reports and optional human disagreements |
| `__main__.py` | CLI: `cases-from-tasks`, `validate`, `plan`, `run`, `check`, `review-export`, `review-import`, `report`; no judge subcommands |

#### Cases and research readiness

The evaluation case format (`schema_version="1.0"`) is distinct from the local
task JSON schema. One case binds an instantiated task, a concrete answer, and
reference/verification evidence:

- `tutor_context`: available task text, answer, diagnosis, feedback, score,
  learning goals, and mathematical rules
- `evaluation_only`: instance metadata, reference answer/equivalent forms,
  ordered steps, expected validity/correctness/diagnosis, verification, provenance

Do not forward evaluation-only metadata to the generator. An authored expected
error may be explicitly selected as supplied synthetic context in `provided`,
never as hidden evidence or a verified PRT result. Independent `model` analysis
must not receive that code/feedback in either selection or generation prompts.
Reference solution steps/final answer are copied only for profiles that request
them. If steps are sent, the matching reference final answer is also required
as an internal literal-guard value even with `include_final_answer=false`.
An API request field is not automatically visible LLM context; both prompt
permissions still apply. Never attach the reference of a different variant.

The two shipped tasks contain optional `evaluation_examples` with one explicit
fixed function per task, matching that task's local `model_solution`. Offline
`cases_from_tasks`/CLI `cases-from-tasks` derives 15 authored cases: 9 for
`-5*exp(x^2-2*exp(x))`, 6 for `x^2*sin(x)`. They include 9 specific error answers,
2 correct controls, 2 syntax controls and 2 unknown-error scenarios. Correct
controls have no supplied error key; never invent one or assume a zero score.
Task-derived cases retain `draft`, `synthetic_fixture`, pending mathematics/
diagnosis and `score=None`, `seed=None`. They need both explicit
`allow_task_derived_cases=true` and `allow_unverified_cases=true`.
These are valid controlled empirical conditions, not verification opt-ins.

The function, error and reference must not be inferred from an LLM answer.
Tasks without `evaluation_examples` contribute no cases. Schema validity does
not verify reference mathematics; optional independent reference audits should
record actual evidence, never fabricated checks. `build_request_payload`
normalizes synthetic provenance to API `diagnosis_source="synthetic"` in all
paths, including CLI task exports; absent origins stay unknown.

The older, separate `data/example_cases.jsonl` contains 12 synthetic fixtures
for 4 task instances; do not count or silently merge it as the new 15-case bank:

| Function | Cases |
|---|---:|
| `-5*exp(x^2-2*exp(x))` | 5 |
| `x^2*sin(x)` | 3 |
| `3*exp(2*x+1)` | 2 |
| `x^3*exp(x)` | 2 |

These cover 9 error cases, 2 correct controls, and 1 syntax/prompt-injection
control. They remain `draft`, `response_origin="synthetic_fixture"`, with
mathematics and diagnosis status `pending`. Local symbolic plausibility tests
do not constitute STACK/PRT verification or research release.

The first empirical study does not require PRTs or verified reference labels.
Authorized live outputs on pending authored cases are empirical observations
against controlled reference hypotheses. A later study claiming verified
external grading needs actual evidence and `allow_unverified_cases=false`;
that gate currently checks `verification.mathematics_status="verified"` only.
Diagnosis provenance must be reviewed separately; the gate is not an independent
diagnosis verifier. `readiness="released"` alone proves nothing. The optional
planned `data/cases_research.jsonl` is not supplied. Never change pending fixtures
to verified merely to pass a gate. Missing values remain `null`.

#### Context profiles

All ten flags in `PROFILE_FLAG_NAMES` must be explicit and kept in sync with
`ContextOptions`. Fixed profiles are stored in `data/context_profiles.json`:

| Profile | Additional context compared with `base` |
|---|---|
| `base` | Task and student answer only |
| `diagnosis` | Diagnosis code |
| `feedback` | Feedback text without diagnosis code |
| `diagnosis_feedback` | Diagnosis and feedback |
| `knowledge` | Diagnosis/feedback plus learning goals and mathematical rules |
| `steps` | Knowledge plus solution steps; separate level-3 comparison |
| `solution` | Steps plus reference answer; separate level-4 comparison |

Score and history are false in the fixed profiles. Notebook `custom` permits
an explicit exploratory field selection. Enabled score requires an actual
value (`0.0` is valid); steps require both reference steps and the guard answer.
Missing required fields exclude that condition, never silently reduce context.
Fixed profiles disable history. Notebook/experiment validation requires an
explicit `interaction_script` for enabled history, including controls. A fresh
empty history is not a history experiment. The task-derived bank has no score
or `math_rules`; exclude profiles requiring them instead of inventing values.

The context and level flags govern reference disclosure in the **prompt**.
The current **output** disclosure check uses the level policy: a full answer
on level 4 is not automatically prohibited merely because the reference was
absent from the prompt. Keep `complete_solution_present` separate from
`prohibited_disclosure`; do not weaken the prompt double guard.
For custom policies use actual permissions, not a universal hardcoded level-4
output boundary. General mode makes didactic output rules inactive, not the
prompt's double reference permissions. The latest message remains visible
when effective history is false, including at stage 0.

#### Jupyter testbench

`notebooks/testbench.ipynb` provides case/profile/level selectors, `custom`
checkboxes, request/preview inspection, generation, checks, tables/plots,
casewise output comparison, notebook/CSV ratings, and report/export.
It resolves `code/` from the notebook directory without changing the CWD.

- `MODE='demo'` is the default: hand-written `execution_source='offline_demo'`
  outputs, no networking/LLM/database. One deliberately disclosing answer
  demonstrates the check; model quality, response times, and ratings are not invented.
  Direct scripted demos use fixed levels; `server_start` stays `not_executed`
  rather than fabricating a model start/adaptation decision.
- `MODE='live'` additionally requires `EXECUTE_LIVE=True` and an explicit
  `MODEL` accepted by the server allowlist. Keys stay in server configuration.
- `FETCH_SERVER_CONFIGURATION=True` explicitly authorizes a protected GET only
  in live mode, independently of generator dispatch; it makes no provider call.
  `EXPECTED_CONFIG_FILE` can instead load a saved nonsecret snapshot offline.
- `EXECUTE_JUDGE_LIVE=False` is independent of generator authorization. Judge
  needs saved live successes, explicit distinct `JUDGE_MODEL` and its own run ID.
- `MODE='analyze'` loads existing snapshots/artifacts without new API calls;
  selection widgets are disabled. For notebook-prepared runs, original input
  files are not required; analyze loads the inputs referenced by the manifest.

Default grid: `CASE_SOURCE='tasks'`, 4 selected task error cases x 3 profiles
(`base`, `diagnosis_feedback`, `custom`) x levels 0/1 x 1 repetition = 24 jobs.
Notebook `protocol_version` is `eval-protocol-2`; `CASE_SOURCE='jsonl'` retains
the older corpus route. `prepare_run` freezes selected cases, profiles, experiment,
source tasks/schema and optional public configuration under
`runs/<RUN_ID>/inputs/`. Identical preparation is reusable; changed conditions
or demo/live mode require a new `RUN_ID`, never overwrite an existing run.
`TUTOR_EVALUATION_RUNS` and `TUTOR_BASE_URL` optionally override output root
and Tutor URL. `notebooks/auswertung.ipynb` is the separate offline artifact
reader; it does not generate Tutor outputs.

`CONDITION_ID`, `LEVEL_MODE=direct|server_start`, `USE_SERVER_CONTEXT`,
`INTERACTION_SCRIPT`, expected configuration and both opt-ins are recorded.
The notebook cannot change deployment rules through arbitrary prompt overrides.
The common empirically chosen pilot baseline must be selected manually from
documented pilot evidence and frozen before contrasts; there is no automatic
baseline optimizer or proven optimal level. Do not confuse it with profile
`base`, the operational default 1 or a session's stored initial baseline.

Analyze is not strictly read-only: Run All recomputes checks and derived
artifacts. It therefore still requires matching source/policy hashes; CLI
planned runs also need their manifest-referenced original input files.

The older `auswertung.ipynb` still uses CWD-relative paths and hand-written
aggregations rather than the current reporting functions. Prefer testbench
`MODE='analyze'` or `report.py` for authoritative model-aware, demo-excluding
metrics until that older notebook is synchronized. Do not assume its path
bootstrap or paired comparisons are identical to the testbench.

The local preview is only for direct initial targets with explicit context
flags, not server selection/defaults or guessed follow-up history. It is not an
observed server prompt. For live findings use only
the API-returned `prompt_messages`; never replace missing messages with a
reconstructed preview. Escape task text, student input, and generated hints
when rendering them in notebook HTML. Keep committed notebooks output-free;
Jupyter checkpoints and run/import artifacts are git-ignored.

#### Runner and artifacts

One session = case x profile x start condition x model x repetition. Turn 0
starts fresh with no reused `chat_id`/`user_message`. Each job is an initial
generation or one explicit dependent script turn. The original student answer
and instance reference stay fixed across turns; a scripted corrected answer is
not observed learning and does not inherit the initial reference verdict.
The notebook requires an explicit live model; the tooling CLI pilot may omit
it and must then record the returned server alias, not invent one.

`level_mode="direct"` sends explicit targets including 0. `server_start`
requires plan `hint_levels=[0]` (control levels also 0) but sends `hint_level=null`;
0 is then only a placeholder. Fixed/individual start is a deployment condition.
`use_server_context=true` omits context flags, not the profile-selected data pool.
Script entries bind message, finite `elapsed_seconds` in `0..86400`, optional
confusion signal and target level; they send authenticated simulation fields,
never sleep to imitate learning time.

Planning is offline, deterministic (`order_seed`), and records exclusions.
Manifest hashes pin corpus, profiles, experiment, policy, and relevant source.
They also pin plan, condition and full script identity; source fingerprints
include task JSON/schema. `expected_config_sha256` or a saved `expected_config`
can pin the intended remote condition. Every initial execution/resume observes
health identity and, when required by the condition/token, protected config.
Each successful response must match that runtime hash and identity. Config drift
blocks the run; local policy/source hashes are not remote deployment evidence.
Resume and recomputing checks fail on changed identity. Do not edit snapshots
or hashes to bypass that check; use the matching source version or a new run.

Each attempt is journaled before dispatch. No automatic Runner retry or model
fallback. Explicit `retry_failed` may repeat known HTTP/server/rate-limit
start failures only; failed follow-up POSTs are never replayed without API
idempotency, since their user message may already be stored. A failed predecessor
blocks dependent turns. An ambiguous attempt blocks further retries even if an earlier
attempt failed with a known error. Successful results are not replayed.

The default shared serial source-run budget is 80 units/hour: generator attempt
4, judge attempt 2. It reserves possible individual selection plus hint and
SAIA fallback, not measured provider calls. Without judge requests this limits
generation to 20/hour, below the additional logical generator ceiling of 35/hour.
Failures/open/ambiguous dispatches consume budget. Resume reconstructs it from
generator and all associated `reviews/judge/*/events.jsonl` journals. Other runs,
concurrent clients and provider-key users are not covered; this is not a global
quota or lock. Do not parallelize live batches by default.

Important artifacts in `runs/<RUN_ID>/`:

```text
inputs/cases.jsonl, inputs/profiles.json, inputs/experiment.json  # notebook snapshots
inputs/tasks/*.json, inputs/schemas/*.json, inputs/expected_configuration.json  # when selected
manifest.json, plan.jsonl
events.jsonl, generations.jsonl
checks.jsonl
reviews/review_packet.csv, reviews/review_mapping.json, reviews/ratings.jsonl
derived/summary.csv, derived/paired_comparisons.csv, derived/report.md
derived/ausgaben.csv, derived/pruefbefunde.csv, derived/*.png     # notebook exports
reviews/judge/<ID>/manifest.json, inputs/, runtime_configuration.json
reviews/judge/<ID>/events.jsonl, judgements.jsonl, derived/       # never human ratings
```

For CLI runs, the corpus/profile arguments remain authoritative: selecting an
experiment does not automatically apply its `corpus_file`. Use `--cases` and
`--profiles` explicitly for non-default inputs. Validate before planning.
Older `pilot.json` and `context_core.json` preserve `eval-protocol-1`; the latter
expects a missing verified corpus and is not the prerequisite for all empirical
work. New presets/conditions need their own protocol-2 identity and validation,
not retroactive editing of legacy presets. Duplicate main/control cells are rejected.

Protocol-2 pilots are supplied as `rule_comparison.json`,
`start_comparison.json`, and `adaptation_comparison.json`. They require the
explicit authored task export passed via `--cases`; they do not enable their
own deployment rules or dispatch themselves. Assign a distinct `condition_id`
and expected server identity before comparing separately configured runs.

#### Checks and expert ratings

Automatic checks cover response identity, returned context flags, required
observed prompt parts (including score), prompt solution permissions, word
count, internal-level mentions, and final-answer disclosure indicators.

- Check outcomes remain `pass`, `fail`, `inconclusive`, or `not_applicable`.
  Failed generations have no assessable hint; missing real prompt messages
  make prompt checks inconclusive, not automatically passed or failed.
- Use observed effective flags/policy/configuration, including the separate
  start-selection context check. Disabled word-limit/hide-level rules or general
  mode are not policy violations merely because old defaults would forbid them.
- Correct answers already inside `<student_answer>` are not newly leaked
  reference sections. Preserve that distinction in prompt-guard tests.
- Disclosure uses literal/equivalent-form matching and optional, bounded
  SymPy equivalence. Parse only allowlisted AST arithmetic/math functions;
  never `eval` or a general unrestricted parser on untrusted LLM text.
- No positive answer match is `inconclusive` with unknown presence, never
  proof of absence. Detection has no complete LaTeX, derivation, or semantic
  coverage and does not enforce output filtering in production.

`rubric.md` (`rubric-1.0`) defines five separate 1-5 Likert criteria and six
yes/no/unclear/not-applicable criteria. Export neutral `review_id` plus
`rater_id`, reference answer, expected error, validity, and correctness; omit
model/profile columns. Do not give `review_mapping.json` or prior profile views
to blinded reviewers. Notebook self-rating alone does not ensure blinding.
Phase, turn, current message, rule mode, verification and diagnosis origin are
review fields; visible rules/phase can reveal a condition. Stage 0 is assessed
as a diagnostic question, not a missing next-step hint. Human question-quality
criteria require a separately authored rubric, not invented CSV fields.

Review CSV is semicolon-separated UTF-8 with or without BOM. `review_id` and
`rater_id` headers are required; validate provided rating values. Empty fields
remain missing, not good/passed. Negative findings and Likert values <= 2
need justification. Store the first valid
rating per `(review_id, rater_id)`; duplicates within a file or reimports do not
add ratings or overwrite an earlier partial rating. Entirely empty sheets and
Likert-only `n_a` rows do not count as assessed answers. Re-export must preserve
edited rating fields, or fail rather than drop them. Older artifacts without a
corpus path remain readable with blank
references, never guessed values.

Generator/human research metrics include only `execution_source='live_tutor_api'`
and its associated checks/human ratings. Judge metrics use only actual
`live_judge_api` responses in a separate report. Offline demos/mocks never contribute.
Technical attempt counts retain all failures; content metrics use the latest
successful answer per job. Report incomplete ratings and disclosure uncertainty
with explicit n/N. Pair against `base` within the same condition, case, start
selection, repetition, model, full script and turn. `compare_runs` pairs distinct
conditions against the first supplied run; effective levels/phases are outcomes,
not match keys that hide adaptive differences. Repetitions/turns are not independent tasks. Never combine
mathematical safety and language scores into a compensating overall grade.

#### Optional second-model review

`prepare_judge_run` freezes latest successful saved live targets and references
offline. `execute_judge_run` requires independent explicit live authorization
and protected configuration preflight; known judge HTTP failures need explicit
retry, ambiguous/invalid-protocol attempts never replay. `summarize_judgements`
is offline, with separate coverage and optional paired human disagreements.
No CLI judge commands currently exist; use these Python functions or notebook gates.

Judge v2 receives task/initial answer, common reference hypothesis/status,
hint/UTF-8 hash, observed generator prompt/policy, separate diagnosis hypothesis,
current message, turn and observed `generator_rule_settings`. Missing prompt
stays `observed_context=None`, never reconstructed or satisfied by request text.
Missing rule flags stay unknown, not true. Reports preserve condition and turn.
`diagnostic_question_quality` and `diagnosis_match` are judge extras, not human
CSV criteria. Optional disagreement rows never overwrite/import/pool human
ratings. Distinct aliases do not prove independent weights or calibrated judgments.

### `moodle/`

Integration consists of field-specific Maxima/CASText snippets, not standalone
JavaScript files or a complete Moodle question export. `question_variables.txt`
defines the variables; `fragetext_castext.html` creates the STACK-JS Tutor link;
`prt_feedback.html` provides answer-bound diagnosis markers.
Preserve the STACK sandbox/bridge boundaries and conservative `unknown_error`
fallback for missing, stale, conflicting, or unmatched feedback. A link does
not perform or authenticate mathematical grading.

Moodle's question variable `debug:0` suppresses diagnosis-marker transmission,
so the link normally carries `unknown_error`. Server `DEBUG_MODE=0` only hides
the HTML debug UI and does not remove diagnosis data from the LLM context.
Do not conflate these switches. Full deployed STACK/Maxima/Moodle validation
remains outstanding; the Node smoke test uses test doubles only.
The snippets remain unchanged and explicitly send hint level 1. They neither
activate level 0 from a changed server default nor sign/authenticate a PRT result.
Server `/start` marks their supplied task/diagnosis context as `provided`.

---

## Interaction Flows

### New Moodle tutor request

```text
1. Moodle/STACK opens GET /start
2. FastAPI validates qid, diagnosis, and ans1
3. The matching local task is loaded
4. A StackContext is created
5. Explicit level or configured fixed/individual start selects the initial level
6. ChatStore creates a UUID session with baseline and start decision
7. Active HintPolicy and effective flags drive one PromptBuilder path
8. The LLM client generates a diagnostic question or hint
9. Success commits assistant response, level and clock/state metadata
10. tutor_page.html is rendered; failure retains safe retry semantics
```

### Next hint

```text
1. The learner requests another hint
2. The existing chat is loaded by UUID
3. The target level is computed without changing the stored level
4. HintPolicy provides the new rules
5. PromptBuilder includes the allowed context and history
6. The LLM generates a more explicit hint
7. On success the new level and assistant response are stored and returned
8. On failure the stored level is unchanged; retry targets the attempted level
```

### Chat message

```text
1. The learner submits a follow-up message
2. Validate message, optional target and protected simulation before storing
3. Decide target at this interaction; default adaptation is disabled
4. Store the user message, load recent history and compute effective flags
5. Keep current message visible even without history; never duplicate it
6. Generate through the same PromptBuilder path and configured client
7. Success commits response/level/state; failure retains question, not level rise
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

The same restrictions apply to server/client evaluation tokens. Keep
`EVALUATION_API_TOKEN` on the server and `TUTOR_EVALUATION_TOKEN` in the client
environment; never put either in URLs, notebooks, prompts or run snapshots.
Judge processing can expose references and observed prompts beyond the hint;
authorize it separately and review retention/recipients, not just generator access.

### TLS

Keep certificate validation enabled:

```python
verify=True
```

### Model selection

Only models in `ALLOWED_MODELS` may be selected through request parameters.

Do not allow arbitrary model names from public query parameters.

### Mathematical authority

Do not let the LLM override actually supplied authoritative results:

```text
STACK score
PRT diagnosis
input validity
symbolic verification result
```

In `provided`, missing/unreliable diagnosis yields general non-speculative
support; `none` requests no diagnosis/re-evaluation. Only configured `model`
permits independent visible-task/answer analysis as an uncertain hypothesis,
not grading. Do not turn synthetic expected labels into verified results.

TLS, institutionally hosted inference and UUIDs do not prove legal compliance
or authorization. Before real student data review legal basis, information/
consent where required, roles, recipients, storage/retention, deletion, access
and backup/log handling. Moodle GET URLs can persist in browser/proxy logs;
HTTPS, URL encoding and `noreferrer` do not remove those records.

---

## Testing Requirements

Current test structure (all paths relative to `code/`):

```text
tests/
├── conftest.py
├── test_config.py
├── test_runtime_config.py
├── test_hint_policy.py
├── test_prompt_builder.py
├── test_solution_disclosure.py
├── test_chat_store.py
├── test_task_loader.py
├── test_api.py
├── test_tutor_rules.py
├── test_llm_factory.py
├── test_llm_saia.py
├── test_llm_ollama.py
├── test_llm_integration.py        # external, integration marker
├── test_tutor_regression.py      # external, integration marker
├── test_evaluation_corpus.py
├── test_task_cases.py
├── test_evaluation_conditions.py
├── test_evaluation_runner.py
├── test_evaluation_checks.py
├── test_evaluation_report.py
├── test_evaluation_judge.py
├── test_evaluation_notebook.py
└── test_moodle_snippets.js        # Node test doubles, not pytest
```

### Unit tests

Unit tests must not require external services.

Test at least:

- all active generic hint levels including 0 load
- invalid hint levels fail
- optional context fields can be disabled
- disabled fields are absent from prompts
- solution steps remain hidden on disallowed levels
- final answers remain hidden where effective policy forbids them (default levels 0..3)
- UUIDs are generated and validated
- messages retain ordering
- hint levels stop at the maximum
- task JSON files validate against the schema
- unknown diagnoses use the intended fallback
- student input is not placed in the system message
- environment values fail fast; policy file/JSON/per-level override precedence
  and no unsafe templating; relative policy paths use `BASE_DIR`
- tutor/general and provided/model/none rules agree with metadata, including
  stage-0 caps and current messages with history disabled

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
- exact attempted prompt/options, HTML escaping, and debug visibility
- successful retry without duplicate user messages and no level advancement on failure
- Moodle variants never receiving a fixed local example solution
- explicit/fixed/individual starts, bounded structured output and actual
  separate selection/generation messages with requested/effective context flags
- immutable baseline and additive DB migration without dropping old records
- adaptation requires threshold and signal at a new turn; no timer/idle inference,
  monotonic process clock, unknown elapsed time after restart and nonsticky simulation
- protected config/judge/simulation: disabled 404, wrong token 401, no secrets,
  active policy snapshot identical to health/generation, no file hot reload
- existing-chat declared context identity checks and safe failure commits

### Evaluation and notebook tests

Use the evaluation dependencies as well as the app/test dependencies when
testing the full notebook workflow. These tests must remain entirely offline:

- Example corpus: schema, unique IDs, variant-specific references, synthetic
  provenance, pending verification, optional local symbolic plausibility
- Context: all ten explicit flags, eligibility exclusions, score `None` vs.
  `0.0`, solution steps requiring their matching guard answer
- Planning: deterministic grids, frozen selected inputs, no changed run reuse
- Task-derived bank: 15 authored cases, explicit function/reference matching,
  pending labels, separate opt-ins, no invented score/seed and core API-source normalization
- Runner: explicit live gate, attempt journal before dispatch, known failures,
  ambiguity blocking retries, 4/2 weighted budget reconstruction across generator/
  judge journals, remote configuration drift, blocked dependent turns and no failed-message replay
- Checks: no false pass on missing prompts/no positive solution match, correct
  answers within student input, double permissions, safe symbolic-parser bounds
- Ratings/report: neutral references, UTF-8 BOM and header validation,
  first-valid-rating deduplication, negative-rating justification, preservation
  of edited sheets, no demo contamination, model-aware paired comparisons
- Conditions/judge: full script/turn/start identity, effective levels as outcomes,
  distinct explicit aliases, separate ratings/reports, hypothesis/current-message/
  rule settings evidence and unknown visibility when real prompts are missing
- Notebook: output-free committed cells, offline Run All from its own
  directory, analysis using only snapshots, mocked live/rating/report roundtrip

`test_evaluation_notebook.py` executes trusted repository code cells and uses
temporary run directories. Optional notebook/SymPy dependencies can produce
explicit skips; skips are not proof that these paths work. For notebook
changes, install `requirements-evaluation.txt` and ensure those tests run.
Never modify the checked-in corpus to simulate resume changes; use a temporary
corpus copy. Do not write tests against the user's real database or existing runs.

### Integration tests

Mark external tests:

```python
@pytest.mark.integration
```

Run local tests:

```bash
pytest -m "not integration" -v
```

Run integration tests only when explicitly authorized:

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

String matching alone is insufficient because equivalent expressions can differ
syntactically. The evaluation suite already includes bounded, optional SymPy
equivalence, but no-match and parse uncertainty remain inconclusive. Complete
STACK/Maxima-backed output checking and detection of full derivations remain
future work; do not present the existing heuristic as a production solution filter.

---

## Coding Conventions

### Python compatibility

Keep compatibility with the project's configured Python version.

Python 3.11 is the reference environment for the pinned server stack and the
separate notebook dependencies. The current pinned FastAPI release requires
Python >=3.10; old Python 3.9+ notes are not a promise for this dependency set.
Change declared support and dependencies together, not through an incidental
typing or documentation cleanup.

Prefer the existing typing style when editing application/public functions:

```python
Optional[str]
List[str]
Dict[str, str]
```

Built-in generics (`list[str]`, `dict[str, str]`) exist since Python 3.9;
`str | None` requires Python 3.10. These are different compatibility questions.
Avoid unnecessary annotation-only migrations; verify new syntax and standard
library features against the reference environment.

`requirements.txt` pins the main runtime dependencies; `pytest` and `httpx`
are not pinned, and Pydantic 2 is brought in by FastAPI. The evaluation file
explicitly requires Pydantic 2 and adds JupyterLab, widgets, pandas,
matplotlib, SymPy, jsonschema, nbformat, and nbclient using version ranges. Neither file
is a complete environment lock; do not claim bit-for-bit dependency reproducibility.

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

Evaluation client settings belong in its experiment or notebook configuration,
not in the server defaults. Record all selected options explicitly in the plan
and manifest; do not add a hidden deployment-dependent evaluation condition.

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

Use `default_factory` for Pydantic list and object fields.

### SQL

Continue using parameterized SQL statements.

Never construct SQL with string interpolation.

---

## Data and Schema Rules

### Task-specific data

Belongs in `tasks/*.json`:

```text
question ID
topic
subtopic
question text (generic instruction)
question text template (generic instruction with {funktion})
given_data (generic metadata, no function values)
learning goals
diagnoses
model solution (local example)
ordered solution steps (local example)
evaluation_examples (optional, authored fixed instance and concrete answers)
```

`StackContext` and evaluation cases support `math_rules`, but the current
local-task JSON Schema does not define that top-level field and rejects
unknown properties. Do not add it to `tasks/*.json` without synchronizing
the schema, mapping, tests, and documentation. Local example solution data
is not by itself STACK verification evidence for a research case.
An `evaluation_examples` function must match that task's fixed reference;
do not infer functions or attach another variant's reference. Correct controls
must not acquire an invented error key. Schema validation is not mathematical
verification; task `published` does not release its pending evaluation cases.

### Generic tutor policy

Belongs in:

```text
config/hint_levels.json
```

Do not duplicate generic hint levels inside every task unless maintaining backward compatibility during a documented migration.

The current local-task schema still requires the legacy fields `tutor_policy`,
`hint_levels`, and `prompt_context_policy`. They remain in the shipped task
files but are not the runtime source of the generic HintPolicy. Do not delete
them or switch back to task-specific escalation without an explicit schema/data
migration. The central policy and the double solution permission stay authoritative.

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

For each evaluated LLM request, record where permitted and observable:

```text
question_id
student_answer or pseudonymized test-case ID
diagnosis_code
supplied feedback and diagnosis source/verification status
hint level
baseline level, stage, condition/session/turn and start/adaptation decisions
enabled context options
requested versus effective options and actual selection/generation prompts
chat ID
model alias
model digest if available
LLM backend
prompt version
active policy, public configuration and config/condition/script/input hashes
temperature
token limit
response time
HTTP status
generated hint
timestamp
```

The GWDG SAIA platform is the configured default backend;
there is no per-model digest, but model aliases are
verifiable via `GET /v1/models`.

The Tutor API exposes hint, chat/task/level/model identity, actual generation/
selection messages, requested/effective flags, baseline, decisions, stage,
hypothesis, active policy and public configuration/hash. The runner records
requests, condition/script/plan/source hashes, local and observed policy/config,
attempts, timing and Tutor HTTP outcomes. The notebook additionally freezes
selected input/task/schema/config files; source hashes
are not archived source-code copies.
It does not receive token usage, provider request/model IDs, upstream attempt
counts, finish reason, or effective thinking mode; these stay unknown in the
manifest. A local prompt preview or local source hash is not proof of the
deployed server's actual configuration.

Avoid persisting personal student data for reproducibility.

---

## Known Issues

1. The native HTW Ollama API was shut down on 2026-09-01; the GWDG SAIA platform is the replacement
2. SAIA enforces a rate limit of roughly 100 requests per hour
3. SAIA API keys expire after 6 months and must be rotated via the SAIA dashboard
4. HTML chat and prompt debugging are available without JavaScript; authentication, request idempotency and production debug-access controls remain open
5. STACK `/render`, `/validate`, and `/grade` integration is not yet implemented
6. Output-level solution-disclosure detection is incomplete
7. SQLite is sufficient for the prototype but not intended for high-concurrency production deployment
8. `chat_template_kwargs.enable_thinking` is a vLLM-specific extension. Observed on 2026-09-21: the SAIA gateway returned HTTP 500 with an empty body for requests containing this field, plus sporadic 500s without it. The client retries once without the field (`LLM_RETRY_DELAY`) and logs the cause server-side. If errors persist, check the SAIA dashboard, switch `LLM_MODEL`, or set `LLM_DISABLE_THINKING=0` to omit the field. Reasoning may consume tokens or leave empty `content`; effective thinking mode remains unknown.
9. The 15 task-derived cases and older 12 fixtures remain pending hypotheses; no verified external-grading corpus is supplied, but authorized controlled empirical comparisons do not require PRTs
10. Existing-chat JSON identity compares declared Pydantic context, but UUID access is unauthenticated and concurrent generation/store calls have no session lock or idempotency protocol
11. Full Moodle/STACK deployment validation remains outstanding; local snippet tests use test doubles only
12. Weighted budgeting shares only one source run's serial generator/judge journals, not concurrent runs or other clients using the same provider key
13. The older `auswertung.ipynb` has not been synchronized with the testbench's path handling and model-aware reporting; prefer `MODE='analyze'` in the testbench or CLI reports
14. Monotonic elapsed time is unknown after restart or worker change; no active-work tracker or validated learner-state inference exists
15. An optional judge is an uncertain model rating, not calibrated human expertise or symbolic verification; distinct aliases do not prove independent weights

---

## Prioritized Work Plan

1. Define protocol-2 pilots/contrasts on explicit task/answer hypotheses, audit references where possible, document split/criteria and manually freeze a pilot baseline
2. Execute only explicitly authorized empirical comparisons through the existing tooling; collect independent human ratings and optionally separate judge observations
3. Validate STACK-JS snippets on the deployed Moodle/STACK installation and later integrate rendering/validation/grading with actual evidence, not invented PRT labels
4. Extend disclosure detection beyond literal/bounded-symbolic indicators, especially LaTeX and complete derivations
5. Address authentication, debug access, idempotency/concurrency, governance and data retention before wider deployment
6. Supply evidence-backed instance references and reviewed diagnosis provenance before claiming verified external grading; this is not a prerequisite for the initial controlled hypothesis study
7. Maintain offline tests and local Ollama fallback; watch total provider-key use beyond the run-local budget

The example corpus, evaluation logging/journal, baseline output checks, and
interactive testbench already exist. Extend them rather than creating another
independent evaluation or prompt-generation path.

---

## Commands

Unless stated otherwise, run the following commands from `code/`.
Do not run unfiltered pytest when only offline verification is intended:
integration tests may make real LLM calls if credentials are configured.

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Install the separate evaluation/notebook environment:

```bash
python -m pip install -r requirements-evaluation.txt
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

Run integration tests only when explicitly authorized:

```bash
pytest -m integration -v
```

Run the offline evaluation/notebook tests:

```bash
python -m pytest tests/test_tutor_rules.py tests/test_task_cases.py \
    tests/test_runtime_config.py tests/test_evaluation_corpus.py \
    tests/test_evaluation_conditions.py tests/test_evaluation_runner.py \
    tests/test_evaluation_checks.py tests/test_evaluation_report.py \
    tests/test_evaluation_judge.py tests/test_evaluation_notebook.py \
    -m "not integration" -v
```

Open the testbench (default `MODE='demo'`, no network/LLM/database):

```bash
python -m jupyterlab evaluation/notebooks/testbench.ipynb
```

Validate or plan a pilot without dispatching any requests:

```bash
python -m evaluation validate --experiment evaluation/experiments/pilot.json
python -m evaluation plan --experiment evaluation/experiments/pilot.json --run-dir evaluation/runs/pilot-001
```

These are historical protocol-1 tooling presets. For authored task cases,
offline `cases-from-tasks --tasks-dir tasks --output <new-jsonl-path>` exports
only hypotheses; pass that file explicitly with `--cases` and use a separately
validated protocol-2 experiment. The supplied rule/start/adaptation comparison
presets are offline-valid pilot plans, not completed empirical studies.

The plan command requires a new empty run directory. A planned run never
starts itself. Only when a live batch has been explicitly authorized:

```bash
python -m evaluation run --run-dir evaluation/runs/pilot-001 --execute-live
python -m evaluation run --run-dir evaluation/runs/pilot-001 --execute-live --resume
```

Offline checks, neutral expert review, and reporting for saved results:

```bash
python -m evaluation check --run-dir evaluation/runs/pilot-001
python -m evaluation review-export --run-dir evaluation/runs/pilot-001
python -m evaluation review-import --run-dir evaluation/runs/pilot-001 --file bewertungen.csv
python -m evaluation report --run-dir evaluation/runs/pilot-001
```

Run the Moodle snippet smoke tests from the repository root:

```bash
node --test code/tests/test_moodle_snippets.js
```

Local Ollama fallback:

```bash
ollama serve
ollama pull qwen3:8b
```

Example local configuration:

```cmd
set LLM_API_MODE=ollama
set LLM_BASE_URL=http://127.0.0.1:11434
set LLM_MODEL=qwen3:8b
set LLM_ALLOWED_MODELS=qwen3:8b
python -m uvicorn app.main:app --reload --port 8000
```

SAIA configuration is read from `code/.env`
(see `code/.env.example`); never commit the key.

---

## Definition of Done

A change is complete only when:

- existing public endpoints still work or a migration is documented
- task files pass JSON-Schema validation
- all relevant unit tests pass
- no secrets are introduced
- hint-level restrictions remain enforced
- active generic permissions remain configurable, with the prompt double guard
  always enforced and actually supplied authoritative assessment respected
- student input remains isolated from system instructions
- external API behavior is mocked in unit tests
- integration tests are explicitly marked
- documentation is updated
- model and prompt configuration remain reproducible
- environment/policy overrides are validated; health/config/generation observe
  the same active policy/hash without credentials or unapproved live preflight
- evaluation changes preserve live gating, input snapshots, demo exclusion,
  honest missing-data/uncertainty states, and model-aware paired comparisons
- stage-0/current-message, explicit/fixed/individual start, immutable baseline,
  next-turn adaptation/failure semantics and additive migration remain tested
- generator/human and judge reports/ratings stay separate, with condition/turn
  aware coverage; synthetic evidence and scripted improvements are never graded as real learning
- notebook changes pass offline execution and the mocked rating/report workflow;
  committed notebooks contain no cell outputs or execution counts
