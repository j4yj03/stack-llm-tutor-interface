import re
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.task_loader import load_all_tasks
from app.prompt_builder import build_prompt
from app.ollama_client import call_ollama, OllamaClientError


app = FastAPI(title="STACK AI Tutor Prototype")

templates = Jinja2Templates(directory="app/templates")

TASKS = load_all_tasks()

QID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
DIAGNOSIS_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")

DEFAULT_MODEL = "qwen3.6:27b"

ALLOWED_MODELS = {
    "qwen3.6:27b",
   # "qwen3.6:35b",
   # "granite4.1:30b",
    "mistral-medium-3.5:128b"
}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "tasks_loaded": len(TASKS),
        "default_model": DEFAULT_MODEL
    }


@app.get("/tasks")
def list_tasks():
    return [
        {
            "question_id": task["question_id"],
            "topic": task["topic"],
            "subtopic": task["subtopic"],
            "status": task["status"]
        }
        for task in TASKS.values()
    ]


@app.get("/start", response_class=HTMLResponse)
def start(
    request: Request,
    qid: str = Query(..., description="Question ID der STACK-Aufgabe"),
    diagnosis: str = Query(..., description="Diagnosecode aus dem STACK-PRT"),
    ans1: str = Query("", description="URL-kodierte Studierendenantwort"),
    hint_level: int = Query(1, ge=1, le=4),
    model: Optional[str] = Query(
        None,
        description="Optionaler erlaubter Ollama-Modellname"
    )
):
    if not QID_PATTERN.fullmatch(qid):
        raise HTTPException(
            status_code=400,
            detail="Ungültige question_id"
        )

    if not DIAGNOSIS_PATTERN.fullmatch(diagnosis):
        raise HTTPException(
            status_code=400,
            detail="Ungültiger diagnosis-Code"
        )

    if qid not in TASKS:
        raise HTTPException(
            status_code=404,
            detail="Unbekannte question_id"
        )

    if not ans1.strip():
        raise HTTPException(
            status_code=400,
            detail="Studierendenantwort fehlt"
        )

    if len(ans1) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Studierendenantwort ist zu lang"
        )

    selected_model = model or DEFAULT_MODEL

    if selected_model not in ALLOWED_MODELS:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Nicht erlaubtes Modell",
                "allowed_models": sorted(ALLOWED_MODELS)
            }
        )

    task = TASKS[qid]

    if diagnosis not in task["diagnoses"]:
        diagnosis = "unknown_error"

    if diagnosis not in task["diagnoses"]:
        raise HTTPException(
            status_code=500,
            detail="unknown_error ist in der Aufgaben-JSON nicht definiert"
        )

    prompt = build_prompt(
        task=task,
        diagnosis_code=diagnosis,
        student_answer=ans1,
        hint_level=hint_level
    )

    try:
        tutor_answer = call_ollama(
            prompt=prompt,
            model=selected_model
        )
    except OllamaClientError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Fehler beim Aufruf des Hochschul-LLM: {exc}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unerwarteter interner Fehler: {exc}"
        )

    return templates.TemplateResponse(
        "tutor_page.html",
        {
            "request": request,
            "question_id": qid,
            "topic": task["topic"],
            "subtopic": task["subtopic"],
            "question_text": task["question_text"],
            "student_answer": ans1,
            "diagnosis_code": diagnosis,
            "diagnosis_title": task["diagnoses"][diagnosis]["title"],
            "hint_level": hint_level,
            "model": selected_model,
            "tutor_answer": tutor_answer,
            "prompt": prompt
        }
    )