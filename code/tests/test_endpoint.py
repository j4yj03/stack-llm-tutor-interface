import requests


url = (
    "https://f2ki-h100-1.f2.htw-berlin.de:"
    "11435/v1/chat/completions"
)

payload = {
    "model": "qwen3.6:27b",
    "messages": [
        {
            "role": "user",
            "content": "Antworte nur mit dem Wort Test"
        }
    ],
    "temperature": 0.0,
    "max_tokens": 50,
    "stream": False
}

response = requests.post(
    url,
    json=payload,
    timeout=180,
    verify=True
)

print("Status:", response.status_code)
print("Antwort:", response.text)