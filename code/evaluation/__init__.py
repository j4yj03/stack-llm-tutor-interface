"""Evaluation Suite für den KI-Tutor (fachliche, API-basierte Tests).

Diese Paket ist bewusst import-sicher getrennt von `app.main`:
Es importiert weder die Serveranwendung noch startet es Datenbank oder
Netzaufrufe. Der Runner nutzt ausschließlich die HTTP-Schnittstelle der
Tutor-API (`POST /api/tutor/start`) und benötigt dafür eine explizite
Live-Freigabe (`--execute-live`).

Kernbausteine:
- models: strenge Datenmodelle (Case, Kontextprofil, Experiment)
- corpus: Laden/Prüfen des Fallbestands und der Kontextprofile
- runner: deterministische Planung + kontrollierte API-Ausführung
- checks: automatische Prüfungen einer Antwort (inkl. begrenzter
  symbolischer Formelprüfung, sofern sympy installiert ist)
- report: Review-Export/-Import, Aggregationen und Markdown-Bericht
"""

from evaluation.models import (
    Case,
    ContextProfile,
    Experiment,
    PROFILE_FLAG_NAMES,
)

__all__ = [
    "Case",
    "ContextProfile",
    "Experiment",
    "PROFILE_FLAG_NAMES",
]
