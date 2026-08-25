from app.ollama_client import DEFAULT_MODEL, OllamaClientError, call_ollama_generate


prompt = """
Du bist ein Mathematik-Tutor.

Ein Studierender soll die Funktion
f(x) = -5*exp(x^2 - 2*exp(x))
ableiten.

Die innere Ableitung wurde vergessen.

Gib genau einen kurzen Hinweis.
Gib nicht die vollständige Lösung aus.
""".strip()


try:
    print(f"Verwendetes Modell: {DEFAULT_MODEL}")

    answer = call_ollama_generate(
        prompt=prompt,
        temperature=0.2,
        max_tokens=150
    )

    print("\nAntwort:")
    print(answer)

except OllamaClientError as exc:
    print(f"Ollama-Fehler: {exc}")