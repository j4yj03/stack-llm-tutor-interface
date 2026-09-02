import requests

base_url = "https://f2ki-h100-1.f2.htw-berlin.de:11435"

tests = [
    (
        "/api/chat",
        {
            "model": "qwen3.6:27b",
            "messages": [
                {
                    "role": "user",
                    "content": "Antworte nur mit Test"
                }
            ],
            "stream": False
        }
    ),
    (
        "/api/generate",
        {
            "model": "qwen3.6:27b",
            "prompt": "Antworte nur mit Test",
            "stream": False
        }
    )
]

for endpoint, payload in tests:
    url = base_url + endpoint

    response = requests.post(
        url,
        json=payload,
        timeout=180
    )

    print("\nURL:", url)
    print("Status:", response.status_code)
    print("Antwort:", response.text[:1000])