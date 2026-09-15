import json
import requests


BASE_URL = "https://f2ki-h100-1.f2.htw-berlin.de:11435"


def show_response(name, response):
    print("=" * 70)
    print(name)
    print("URL:", response.url)
    print("Status:", response.status_code)
    print("Server:", response.headers.get("server"))
    print(
        "Content-Type:",
        response.headers.get("content-type")
    )
    print(
        "WWW-Authenticate:",
        response.headers.get("www-authenticate")
    )
    print("Body:")
    print(response.text[:2000])


session = requests.Session()

tags_response = session.get(
    BASE_URL + "/api/tags",
    headers={
        "accept": "application/json"
    },
    timeout=30,
    verify=True
)

show_response(
    "Native Ollama GET /api/tags",
    tags_response
)

chat_response = session.post(
    BASE_URL + "/api/chat",
    headers={
        "Content-Type": "application/json",
        "accept": "application/json"
    },
    json={
        "model": "qwen3.6:27b",
        "messages": [
            {
                "role": "user",
                "content": "Antworte nur mit Test"
            }
        ],
        "think": False,
        "stream": False,
        "keep_alive": "5m",
        "options": {
            "temperature": 0.0,
            "num_predict": 50
        }
    },
    timeout=180,
    verify=True
)

show_response(
    "Native Ollama POST /api/chat",
    chat_response
)

litellm_response = session.post(
    BASE_URL + "/v1/chat/completions",
    headers={
        "Content-Type": "application/json",
        "accept": "application/json"
    },
    json={
        "model": "qwen3.6:27b",
        "messages": [
            {
                "role": "user",
                "content": "Antworte nur mit Test"
            }
        ],
        "stream": False,
        "temperature": 0.0,
        "max_tokens": 50
    },
    timeout=180,
    verify=True
)

show_response(
    "LiteLLM POST /v1/chat/completions",
    litellm_response
)